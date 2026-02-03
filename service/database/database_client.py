"""
HTTP 기반 데이터베이스 서비스 클라이언트

외부 컨테이너(xgen-core)에서 관리하는 데이터베이스에 HTTP로 접근할 수 있도록 지원합니다.
기존 AppDatabaseManager와 100% 호환되는 인터페이스를 제공합니다.

xgen-core 엔드포인트:
    - GET  /db/health           - 헬스 체크
    - GET  /db/tables           - 테이블 목록
    - POST /db/table/schema     - 테이블 스키마
    - POST /db/insert           - 레코드 삽입
    - POST /db/update           - 레코드 업데이트 (ID 기반)
    - POST /db/update-by-condition - 조건부 업데이트
    - POST /db/delete           - 레코드 삭제 (ID 기반)
    - POST /db/delete-by-condition - 조건부 삭제
    - POST /db/find-by-id       - ID로 조회
    - POST /db/find-all         - 전체 조회 (join_user 지원)
    - POST /db/find-by-condition - 조건부 조회 (join_user 지원)
    - POST /db/query            - Raw SQL 실행
    - POST /db/pool/refresh     - 풀 리프레시
    - POST /db/reconnect        - 재연결

사용법:
    from service.database import AppDatabaseManager
    # 또는
    from service.database.database_client import DatabaseClient

    app_db = AppDatabaseManager()  # 또는 DatabaseClient()
    app_db.initialize_connection()

    # join_user 사용 예시 (users 테이블과 LEFT JOIN하여 username, full_name 추가)
    prompts = app_db.find_by_condition(
        Prompts,
        conditions={"user_id": user_id},
        join_user=True  # 결과에 username, full_name 필드가 추가됨
    )
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, TypeVar, Union
from datetime import datetime, date, time
from uuid import UUID
from decimal import Decimal
import logging
import os
import json
import httpx

logger = logging.getLogger("database-client")

# 환경변수 설정
CORE_SERVICE_BASE_URL = os.getenv("CORE_SERVICE_BASE_URL", "http://xgen-core:8000")
DEFAULT_BASE_URL = f"{CORE_SERVICE_BASE_URL}/api/data/db"
DEFAULT_TIMEOUT = float(os.getenv("CORE_SERVICE_TIMEOUT", "60"))
DEFAULT_API_KEY = os.getenv("XGEN_INTERNAL_API_KEY", "xgen-internal-key-2024")
DEFAULT_HEADERS = {
    "Content-Type": "application/json",
}

T = TypeVar('T')


class DatabaseClient:
    """
    HTTP 기반 데이터베이스 클라이언트

    기존 AppDatabaseManager와 100% 호환되는 인터페이스 제공
    내부적으로 xgen-core 서버에 HTTP 요청을 보냄

    config 활용 키:
        - base_url: 데이터베이스 서비스 베이스 URL (미설정 시 기본값 사용)
        - timeout: 요청 타임아웃(초) (기본: 60)
        - api_key: API 키 (기본: 환경변수에서 로드)
        - default_headers: 고정적으로 전송할 추가 헤더(dict)
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        초기화

        Args:
            config: 클라이언트 설정 (선택사항)
        """
        config = config or {}

        base_url = config.get("base_url") or DEFAULT_BASE_URL
        self.base_url = base_url.rstrip("/")
        self.timeout = float(config.get("timeout") or DEFAULT_TIMEOUT)
        self.api_key = config.get("api_key") or DEFAULT_API_KEY

        self.default_headers: Dict[str, str] = dict(DEFAULT_HEADERS)
        self.default_headers["X-API-Key"] = self.api_key
        self.default_headers.update({
            str(k): str(v) for k, v in (config.get("default_headers") or {}).items()
        })

        self.logger = logger
        self._models_registry: List[Type] = []

        # 복구 및 재시도 설정 (호환성 유지)
        self._max_retries = 3
        self._retry_delay = 1.0
        self._retry_backoff = 2.0
        self._auto_recover = True

        # 가상 config_db_manager (호환성 유지)
        self.config_db_manager = _VirtualConfigDbManager(self)

        logger.info(
            "DatabaseClient initialized: base_url=%s",
            self.base_url,
        )

    # ------------------------------------------------------------------ #
    # Helper methods
    # ------------------------------------------------------------------ #
    def _build_url(self, endpoint: str) -> str:
        """엔드포인트 URL 생성"""
        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            return endpoint
        return f"{self.base_url}/{endpoint.lstrip('/')}"

    def _build_headers(self, override_headers: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """요청 헤더 생성"""
        headers: Dict[str, str] = dict(self.default_headers)
        if override_headers:
            headers.update({str(key): str(value) for key, value in override_headers.items()})
        return headers

    async def _async_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """비동기 HTTP 요청"""
        url = self._build_url(endpoint)
        headers = self._build_headers(extra_headers)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers)
                else:
                    response = await client.request(method, url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error from database service (%s %s): %s",
                method,
                url,
                exc.response.text if exc.response else exc,
            )
            raise ValueError(f"Database service HTTP error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Database service request failed (%s %s): %s", method, url, exc)
            raise ValueError(f"Database service request failed: {exc}") from exc

    def _sync_request(
        self,
        method: str,
        endpoint: str,
        payload: Optional[Dict[str, Any]] = None,
        extra_headers: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """동기 HTTP 요청"""
        url = self._build_url(endpoint)
        headers = self._build_headers(extra_headers)

        try:
            with httpx.Client(timeout=self.timeout) as client:
                if method.upper() == "GET":
                    response = client.get(url, headers=headers)
                else:
                    response = client.request(method, url, json=payload, headers=headers)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "HTTP error from database service (%s %s): %s",
                method,
                url,
                exc.response.text if exc.response else exc,
            )
            raise ValueError(f"Database service HTTP error: {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            logger.error("Database service request failed (%s %s): %s", method, url, exc)
            raise ValueError(f"Database service request failed: {exc}") from exc

    def _serialize_value(self, value: Any) -> Any:
        """값을 JSON 직렬화 가능한 형태로 변환"""
        if value is None:
            return None
        # datetime 타입 처리
        if isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, date):
            return value.isoformat()
        elif isinstance(value, time):
            return value.isoformat()
        # UUID 처리
        elif isinstance(value, UUID):
            return str(value)
        # Decimal 처리
        elif isinstance(value, Decimal):
            return float(value)
        # Pydantic 모델 처리
        elif hasattr(value, 'model_dump'):  # Pydantic v2
            return self._serialize_value(value.model_dump())
        elif hasattr(value, 'dict'):  # Pydantic v1
            return self._serialize_value(value.dict())
        # 컬렉션 처리
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        # bytes 처리
        elif isinstance(value, bytes):
            return value.decode('utf-8', errors='replace')
        return value

    def _model_to_table_and_data(self, model) -> tuple:
        """BaseModel 인스턴스를 테이블명과 데이터 딕셔너리로 변환

        TEXT 타입 컬럼에 dict/list가 들어가면 JSON 문자열로 자동 변환합니다.
        PostgreSQL 배열 타입 (TEXT[], VARCHAR[] 등)은 리스트를 그대로 유지합니다.
        """
        table_name = model.get_table_name()

        # get_schema()로 컬럼 정보 가져오기
        schema = model.get_schema()
        data = {}

        for column_name, column_type in schema.items():
            if hasattr(model, column_name):
                value = getattr(model, column_name)
                serialized_value = self._serialize_value(value)

                # TEXT 타입 컬럼에 dict/list가 들어가면 JSON 문자열로 변환
                # (PostgreSQL TEXT, JSONB 등 문자열 기반 컬럼 처리)
                if isinstance(serialized_value, (dict, list)):
                    column_type_upper = column_type.upper() if column_type else ""

                    # PostgreSQL 배열 타입 (TEXT[], VARCHAR[], INTEGER[] 등)은 리스트 그대로 유지
                    # 서버에서 psycopg3가 자동으로 PostgreSQL 배열로 변환함
                    if '[]' in column_type_upper:
                        # 배열 타입은 리스트를 그대로 유지
                        pass
                    # TEXT, VARCHAR, CHAR 등 문자열 타입이면 JSON 문자열로 변환
                    # JSONB, JSON 타입은 dict 그대로 전송 (서버에서 처리)
                    elif 'TEXT' in column_type_upper or 'VARCHAR' in column_type_upper or 'CHAR' in column_type_upper:
                        serialized_value = json.dumps(serialized_value, ensure_ascii=False)

                data[column_name] = serialized_value

        return table_name, data

    # ------------------------------------------------------------------ #
    # Connection & Health Check Methods (AppDatabaseManager 호환)
    # ------------------------------------------------------------------ #

    def check_health(self) -> bool:
        """
        데이터베이스 연결 상태 확인

        Returns:
            bool: 연결이 정상이면 True
        """
        try:
            result = self._sync_request("GET", "/health")
            return result.get("healthy", False)
        except Exception as e:
            self.logger.error("Database health check failed: %s", e)
            return False

    def reconnect(self) -> bool:
        """
        데이터베이스 재연결

        Returns:
            bool: 재연결 성공 여부
        """
        try:
            result = self._sync_request("POST", "/reconnect")
            success = result.get("success", False)
            if success:
                self.logger.info("Database reconnection successful")
            else:
                self.logger.error("Database reconnection failed")
            return success
        except Exception as e:
            self.logger.error(f"Failed to reconnect database: {e}")
            return False

    def get_pool_stats(self) -> Dict[str, Any]:
        """
        커넥션 풀 상태 통계 반환

        Returns:
            dict: 풀 상태 정보
        """
        try:
            result = self._sync_request("GET", "/health")
            return result.get("pool_stats", {})
        except Exception as e:
            self.logger.error("Failed to get pool stats: %s", e)
            return {}

    def check_and_refresh_pool(self) -> bool:
        """
        풀 상태 확인 및 필요시 리프레시

        Returns:
            bool: 리프레시 성공 여부
        """
        try:
            result = self._sync_request("POST", "/pool/refresh")
            return result.get("success", False)
        except Exception as e:
            self.logger.error("Failed to refresh pool: %s", e)
            return False

    # ------------------------------------------------------------------ #
    # Model Registration Methods (호환성 유지 - 클라이언트에서는 no-op)
    # ------------------------------------------------------------------ #

    def register_model(self, model_class: Type):
        """모델 클래스를 등록 (HTTP 클라이언트에서는 로컬 레지스트리만 유지)"""
        if model_class not in self._models_registry:
            self._models_registry.append(model_class)
            self.logger.info("Registered model: %s", model_class.__name__)

    def register_models(self, model_classes: List[Type]):
        """여러 모델 클래스를 한 번에 등록"""
        for model_class in model_classes:
            self.register_model(model_class)

    # ------------------------------------------------------------------ #
    # Initialization Methods (호환성 유지)
    # ------------------------------------------------------------------ #

    def initialize_database(self, create_tables: bool = True) -> bool:
        """
        데이터베이스 연결 확인

        HTTP 클라이언트에서는 실제 테이블 생성을 하지 않고
        연결 상태만 확인합니다. (테이블 생성은 xgen-core에서 담당)

        Args:
            create_tables: 무시됨 (호환성을 위해 유지)

        Returns:
            bool: 연결 성공 여부
        """
        return self.initialize_connection()

    def initialize_connection(self) -> bool:
        """
        데이터베이스 연결 확인

        Returns:
            bool: 연결 성공 여부
        """
        try:
            healthy = self.check_health()
            if healthy:
                self.logger.info("Connected to database service at %s", self.base_url)
            else:
                self.logger.warning("Database service is not healthy")
            return healthy
        except Exception as e:
            self.logger.error("Failed to connect to database service: %s", e)
            return False

    def create_tables(self) -> bool:
        """테이블 생성 (HTTP 클라이언트에서는 no-op - xgen-core에서 담당)"""
        self.logger.info("create_tables called on HTTP client - tables are managed by xgen-core")
        return True

    # ------------------------------------------------------------------ #
    # CRUD Operations
    # ------------------------------------------------------------------ #

    def insert(self, model) -> Optional[Dict[str, Any]]:
        """
        모델 인스턴스를 데이터베이스에 삽입

        Args:
            model: BaseModel 인스턴스

        Returns:
            dict: {"result": "success", "id": inserted_id} 또는 None
        """
        try:
            table_name, data = self._model_to_table_and_data(model)

            payload = {
                "table_name": table_name,
                "data": data
            }

            self.logger.debug("Inserting into %s: %s", table_name, list(data.keys()))

            result = self._sync_request("POST", "/insert", payload)

            if result.get("success"):
                inserted_id = result.get("id")
                self.logger.info("Insert successful into %s, id=%s", table_name, inserted_id)
                return {"result": "success", "id": inserted_id}
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error("Insert failed into %s: %s", table_name, error_msg)
                return None

        except Exception as e:
            self.logger.error("Failed to insert %s: %s", model.__class__.__name__, e, exc_info=True)
            return None

    def update(self, model) -> Optional[Dict[str, Any]]:
        """
        모델 인스턴스를 데이터베이스에서 업데이트

        Args:
            model: BaseModel 인스턴스 (id 필수)

        Returns:
            dict: {"result": "success"} 또는 None (기존 AppDatabaseManager 호환)
        """
        try:
            table_name, data = self._model_to_table_and_data(model)
            record_id = getattr(model, 'id', None)

            if record_id is None:
                self.logger.error("Cannot update model without id")
                return None

            payload = {
                "table_name": table_name,
                "data": data,
                "record_id": record_id
            }

            result = self._sync_request("POST", "/update", payload)
            if result.get("success"):
                return {"result": "success"}
            else:
                self.logger.error("Update failed: %s", result.get("error"))
                return None

        except Exception as e:
            self.logger.error("Failed to update %s: %s", model.__class__.__name__, e)
            return None

    def update_config(self, env_name: str, config_path: str, config_value: Any,
                     data_type: str = "string", category: str = None) -> bool:
        """
        설정 값 업데이트

        Args:
            env_name: 환경 이름
            config_path: 설정 경로
            config_value: 설정 값
            data_type: 데이터 타입
            category: 카테고리

        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            # 기존 레코드 확인
            find_result = self._sync_request("POST", "/find-by-condition", {
                "table_name": "persistent_configs",
                "conditions": {"env_name": env_name},
                "limit": 1
            })

            value_str = json.dumps(config_value) if isinstance(config_value, (dict, list)) else str(config_value)

            if find_result.get("success") and find_result.get("row_count", 0) > 0:
                # 업데이트
                result = self._sync_request("POST", "/update-by-condition", {
                    "table_name": "persistent_configs",
                    "updates": {
                        "config_path": config_path,
                        "config_value": value_str,
                        "data_type": data_type,
                        "category": category
                    },
                    "conditions": {"env_name": env_name}
                })
            else:
                # 새로 삽입
                result = self._sync_request("POST", "/insert", {
                    "table_name": "persistent_configs",
                    "data": {
                        "env_name": env_name,
                        "config_path": config_path,
                        "config_value": value_str,
                        "data_type": data_type,
                        "category": category
                    }
                })

            return result.get("success", False)

        except Exception as e:
            self.logger.error("Failed to update config in DB: %s - %s", env_name, e)
            return False

    def delete(self, model_class: Type, record_id: int) -> bool:
        """
        ID로 레코드 삭제

        Args:
            model_class: 모델 클래스
            record_id: 삭제할 레코드 ID

        Returns:
            bool: 삭제 성공 여부
        """
        try:
            table_name = model_class().get_table_name()

            payload = {
                "table_name": table_name,
                "record_id": record_id
            }

            result = self._sync_request("POST", "/delete", payload)
            return result.get("success", False)

        except Exception as e:
            self.logger.error("Failed to delete %s with id %s: %s",
                            model_class.__name__, record_id, e)
            return False

    def delete_by_condition(self, model_class: Type, conditions: Dict[str, Any]) -> bool:
        """
        조건으로 레코드 삭제

        Args:
            model_class: 모델 클래스
            conditions: 삭제 조건

        Returns:
            bool: 삭제 성공 여부
        """
        try:
            if not conditions:
                self.logger.warning("No conditions provided for delete_by_condition. Aborting.")
                return False

            table_name = model_class().get_table_name()

            payload = {
                "table_name": table_name,
                "conditions": conditions
            }

            result = self._sync_request("POST", "/delete-by-condition", payload)
            return result.get("success", False)

        except Exception as e:
            self.logger.error("Failed to delete %s by condition: %s", model_class.__name__, e)
            return False

    def find_by_id(self, model_class: Type[T], record_id: int,
                   select_columns: List[str] = None,
                   ignore_columns: List[str] = None) -> Optional[T]:
        """
        ID로 레코드 조회

        Args:
            model_class: 모델 클래스
            record_id: 조회할 레코드 ID
            select_columns: 조회할 컬럼 목록
            ignore_columns: 제외할 컬럼 목록

        Returns:
            BaseModel 인스턴스 또는 None
        """
        try:
            table_name = model_class().get_table_name()

            payload = {
                "table_name": table_name,
                "record_id": record_id
            }

            if select_columns:
                payload["select_columns"] = select_columns
            if ignore_columns:
                payload["ignore_columns"] = ignore_columns

            result = self._sync_request("POST", "/find-by-id", payload)

            if result.get("success") and result.get("data"):
                return model_class.from_dict(result["data"])
            return None

        except Exception as e:
            self.logger.error("Failed to find %s with id %s: %s",
                            model_class.__name__, record_id, e)
            return None

    def find_all(self, model_class: Type[T], limit: int = 500, offset: int = 0,
                 select_columns: List[str] = None, ignore_columns: List[str] = None,
                 join_user: bool = False) -> List[T]:
        """
        모든 레코드 조회 (페이징 지원)

        Args:
            model_class: 모델 클래스
            limit: 최대 조회 개수
            offset: 시작 위치
            select_columns: 조회할 컬럼 목록
            ignore_columns: 제외할 컬럼 목록
            join_user: 사용자 정보 조인 여부 (users 테이블과 조인하여 username, full_name 반환)

        Returns:
            BaseModel 인스턴스 리스트
        """
        try:
            table_name = model_class().get_table_name()

            payload = {
                "table_name": table_name,
                "limit": limit,
                "offset": offset,
                "join_user": join_user
            }

            if select_columns:
                payload["select_columns"] = select_columns
            if ignore_columns:
                payload["ignore_columns"] = ignore_columns

            result = self._sync_request("POST", "/find-all", payload)

            if result.get("success") and result.get("data"):
                data = result["data"]
                if isinstance(data, list):
                    return [model_class.from_dict(row) for row in data]
            return []

        except Exception as e:
            self.logger.error("Failed to find all %s: %s", model_class.__name__, e)
            return []

    def find_by_condition(self, model_class: Type[T],
                         conditions: Dict[str, Any],
                         limit: int = 500,
                         offset: int = 0,
                         orderby: str = "id",
                         orderby_asc: bool = False,
                         return_list: bool = False,
                         select_columns: List[str] = None,
                         ignore_columns: List[str] = None,
                         join_user: bool = False) -> Union[List[T], List[Dict[str, Any]]]:
        """
        조건으로 레코드 조회

        지원하는 조건 연산자:
        - key: 동등 비교 (=)
        - key__like__: LIKE 검색
        - key__not__: 부정 (!=)
        - key__gte__: 크거나 같음 (>=)
        - key__lte__: 작거나 같음 (<=)
        - key__gt__: 큼 (>)
        - key__lt__: 작음 (<)
        - key__in__: IN 조건
        - key__notin__: NOT IN 조건

        Args:
            model_class: 모델 클래스
            conditions: 조회 조건
            limit: 최대 조회 개수
            offset: 시작 위치
            orderby: 정렬 기준 컬럼
            orderby_asc: 오름차순 여부
            return_list: True면 dict 리스트, False면 모델 리스트 반환
            select_columns: 조회할 컬럼 목록
            ignore_columns: 제외할 컬럼 목록
            join_user: 사용자 정보 조인 여부 (users 테이블과 조인하여 username, full_name 반환)

        Returns:
            BaseModel 인스턴스 리스트 또는 dict 리스트
        """
        try:
            table_name = model_class().get_table_name()

            # 조건 값 직렬화 (datetime, UUID 등 처리)
            serialized_conditions = {}
            for key, value in conditions.items():
                serialized_conditions[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "conditions": serialized_conditions,
                "limit": limit,
                "offset": offset,
                "orderby": orderby,
                "orderby_asc": orderby_asc,
                "join_user": join_user
            }

            if select_columns:
                payload["select_columns"] = select_columns
            if ignore_columns:
                payload["ignore_columns"] = ignore_columns

            result = self._sync_request("POST", "/find-by-condition", payload)

            if result.get("success") and result.get("data"):
                data = result["data"]
                if isinstance(data, list):
                    if return_list:
                        return data
                    return [model_class.from_dict(row) for row in data]
            return []

        except Exception as e:
            self.logger.error("Failed to find %s by condition: %s", model_class.__name__, e)
            return []

    def update_list_columns(self, model_class: Type,
                           updates: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """
        리스트 컬럼을 포함한 모델 업데이트

        Args:
            model_class: 모델 클래스
            updates: 업데이트할 데이터
            conditions: 업데이트 조건

        Returns:
            bool: 업데이트 성공 여부
        """
        try:
            table_name = model_class().get_table_name()

            # 리스트/딕셔너리 값 직렬화
            serialized_updates = {}
            for key, value in updates.items():
                serialized_updates[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "updates": serialized_updates,
                "conditions": conditions
            }

            result = self._sync_request("POST", "/update-by-condition", payload)
            return result.get("success", False)

        except Exception as e:
            self.logger.error("Failed to update list columns for %s: %s", model_class.__name__, e)
            return False

    # ------------------------------------------------------------------ #
    # Table Name Based CRUD Operations (테이블 이름 기반 CRUD)
    # ------------------------------------------------------------------ #

    def insert_record(self, table_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        테이블 이름 기반 레코드 삽입

        Args:
            table_name: 테이블 이름
            data: 삽입할 데이터

        Returns:
            dict: {"success": bool, "id": inserted_id, "error": str}
        """
        try:
            # 데이터 직렬화
            serialized_data = {}
            for key, value in data.items():
                serialized_data[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "data": serialized_data
            }

            result = self._sync_request("POST", "/insert", payload)

            if result.get("success"):
                self.logger.info("Insert successful into %s, id=%s", table_name, result.get("id"))
                return {"success": True, "id": result.get("id")}
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error("Insert failed into %s: %s", table_name, error_msg)
                return {"success": False, "error": error_msg}

        except Exception as e:
            self.logger.error("Failed to insert into %s: %s", table_name, e)
            return {"success": False, "error": str(e)}

    def update_record(self, table_name: str, data: Dict[str, Any], record_id: int) -> Dict[str, Any]:
        """
        테이블 이름 기반 레코드 업데이트 (ID 기반)

        Args:
            table_name: 테이블 이름
            data: 업데이트할 데이터
            record_id: 레코드 ID

        Returns:
            dict: {"success": bool, "affected_rows": int, "error": str}
        """
        try:
            # 데이터 직렬화
            serialized_data = {}
            for key, value in data.items():
                serialized_data[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "data": serialized_data,
                "record_id": record_id
            }

            result = self._sync_request("POST", "/update", payload)

            if result.get("success"):
                self.logger.info("Update successful in %s, id=%s", table_name, record_id)
                return {"success": True, "affected_rows": result.get("affected_rows", 1)}
            else:
                error_msg = result.get("error", "Unknown error")
                self.logger.error("Update failed in %s: %s", table_name, error_msg)
                return {"success": False, "error": error_msg, "affected_rows": 0}

        except Exception as e:
            self.logger.error("Failed to update record in %s: %s", table_name, e)
            return {"success": False, "error": str(e), "affected_rows": 0}

    def update_records_by_condition(self, table_name: str, updates: Dict[str, Any], conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        테이블 이름 기반 조건부 레코드 업데이트

        Args:
            table_name: 테이블 이름
            updates: 업데이트할 데이터
            conditions: WHERE 조건

        Returns:
            dict: {"success": bool, "affected_rows": int, "error": str}
        """
        try:
            # 데이터 직렬화
            serialized_updates = {}
            for key, value in updates.items():
                serialized_updates[key] = self._serialize_value(value)

            serialized_conditions = {}
            for key, value in conditions.items():
                serialized_conditions[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "updates": serialized_updates,
                "conditions": serialized_conditions
            }

            result = self._sync_request("POST", "/update-by-condition", payload)

            if result.get("success"):
                return {"success": True, "affected_rows": result.get("affected_rows", 0)}
            else:
                return {"success": False, "error": result.get("error"), "affected_rows": 0}

        except Exception as e:
            self.logger.error("Failed to update records in %s: %s", table_name, e)
            return {"success": False, "error": str(e), "affected_rows": 0}

    def delete_record(self, table_name: str, record_id: int) -> Dict[str, Any]:
        """
        테이블 이름 기반 레코드 삭제 (ID 기반)

        Args:
            table_name: 테이블 이름
            record_id: 레코드 ID

        Returns:
            dict: {"success": bool, "affected_rows": int, "error": str}
        """
        try:
            payload = {
                "table_name": table_name,
                "record_id": record_id
            }

            result = self._sync_request("POST", "/delete", payload)

            if result.get("success"):
                self.logger.info("Delete successful from %s, id=%s", table_name, record_id)
                return {"success": True, "affected_rows": result.get("affected_rows", 1)}
            else:
                return {"success": False, "error": result.get("error"), "affected_rows": 0}

        except Exception as e:
            self.logger.error("Failed to delete record from %s: %s", table_name, e)
            return {"success": False, "error": str(e), "affected_rows": 0}

    def delete_records_by_condition(self, table_name: str, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        테이블 이름 기반 조건부 레코드 삭제

        Args:
            table_name: 테이블 이름
            conditions: WHERE 조건

        Returns:
            dict: {"success": bool, "affected_rows": int, "error": str}
        """
        try:
            if not conditions:
                self.logger.warning("No conditions provided for delete_records_by_condition. Aborting.")
                return {"success": False, "error": "Conditions required", "affected_rows": 0}

            serialized_conditions = {}
            for key, value in conditions.items():
                serialized_conditions[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "conditions": serialized_conditions
            }

            result = self._sync_request("POST", "/delete-by-condition", payload)

            if result.get("success"):
                return {"success": True, "affected_rows": result.get("affected_rows", 0)}
            else:
                return {"success": False, "error": result.get("error"), "affected_rows": 0}

        except Exception as e:
            self.logger.error("Failed to delete records from %s: %s", table_name, e)
            return {"success": False, "error": str(e), "affected_rows": 0}

    def find_record_by_id(self, table_name: str, record_id: int, select_columns: List[str] = None) -> Dict[str, Any]:
        """
        테이블 이름 기반 ID로 레코드 조회

        Args:
            table_name: 테이블 이름
            record_id: 레코드 ID
            select_columns: 조회할 컬럼 목록

        Returns:
            dict: {"success": bool, "data": dict or None, "error": str}
        """
        try:
            payload = {
                "table_name": table_name,
                "record_id": record_id
            }

            if select_columns:
                payload["select_columns"] = select_columns

            result = self._sync_request("POST", "/find-by-id", payload)

            if result.get("success"):
                return {"success": True, "data": result.get("data")}
            else:
                return {"success": False, "data": None, "error": result.get("error")}

        except Exception as e:
            self.logger.error("Failed to find record in %s with id %s: %s", table_name, record_id, e)
            return {"success": False, "data": None, "error": str(e)}

    def find_records(self, table_name: str, limit: int = 500, offset: int = 0,
                     select_columns: List[str] = None, ignore_columns: List[str] = None,
                     join_user: bool = False) -> Dict[str, Any]:
        """
        테이블 이름 기반 전체 레코드 조회 (페이징 지원)

        Args:
            table_name: 테이블 이름
            limit: 최대 조회 개수
            offset: 시작 위치
            select_columns: 조회할 컬럼 목록
            ignore_columns: 제외할 컬럼 목록
            join_user: 사용자 정보 조인 여부

        Returns:
            dict: {"success": bool, "data": list, "row_count": int, "error": str}
        """
        try:
            payload = {
                "table_name": table_name,
                "limit": limit,
                "offset": offset,
                "join_user": join_user
            }

            if select_columns:
                payload["select_columns"] = select_columns
            if ignore_columns:
                payload["ignore_columns"] = ignore_columns

            result = self._sync_request("POST", "/find-all", payload)

            if result.get("success"):
                data = result.get("data", [])
                return {"success": True, "data": data, "row_count": len(data)}
            else:
                return {"success": False, "data": [], "row_count": 0, "error": result.get("error")}

        except Exception as e:
            self.logger.error("Failed to find records in %s: %s", table_name, e)
            return {"success": False, "data": [], "row_count": 0, "error": str(e)}

    def find_records_by_condition(self, table_name: str, conditions: Dict[str, Any],
                                  limit: int = 500, offset: int = 0,
                                  orderby: str = "id", orderby_asc: bool = False,
                                  select_columns: List[str] = None, ignore_columns: List[str] = None,
                                  join_user: bool = False) -> List[Dict[str, Any]]:
        """
        테이블 이름 기반 조건부 레코드 조회

        지원하는 조건 연산자:
        - key: 동등 비교 (=)
        - key__like__: LIKE 검색
        - key__not__: 부정 (!=)
        - key__gte__: 크거나 같음 (>=)
        - key__lte__: 작거나 같음 (<=)
        - key__gt__: 큼 (>)
        - key__lt__: 작음 (<)
        - key__in__: IN 조건
        - key__notin__: NOT IN 조건

        Args:
            table_name: 테이블 이름
            conditions: 조회 조건
            limit: 최대 조회 개수
            offset: 시작 위치
            orderby: 정렬 기준 컬럼
            orderby_asc: 오름차순 여부
            select_columns: 조회할 컬럼 목록
            ignore_columns: 제외할 컬럼 목록
            join_user: 사용자 정보 조인 여부

        Returns:
            list: 조회된 레코드 리스트 (빈 리스트일 수 있음)
        """
        try:
            # 조건 값 직렬화
            serialized_conditions = {}
            for key, value in conditions.items():
                serialized_conditions[key] = self._serialize_value(value)

            payload = {
                "table_name": table_name,
                "conditions": serialized_conditions,
                "limit": limit,
                "offset": offset,
                "orderby": orderby,
                "orderby_asc": orderby_asc,
                "join_user": join_user
            }

            if select_columns:
                payload["select_columns"] = select_columns
            if ignore_columns:
                payload["ignore_columns"] = ignore_columns

            result = self._sync_request("POST", "/find-by-condition", payload)

            if result.get("success"):
                return result.get("data", [])
            else:
                self.logger.warning("find_records_by_condition failed for %s: %s", table_name, result.get("error"))
                return []

        except Exception as e:
            self.logger.error("Failed to find records in %s by condition: %s", table_name, e)
            return []

    # ------------------------------------------------------------------ #
    # Table Schema Methods
    # ------------------------------------------------------------------ #

    def get_table_list(self) -> List[Dict[str, Any]]:
        """
        데이터베이스의 모든 테이블 목록 조회

        Returns:
            테이블 목록
        """
        try:
            result = self._sync_request("GET", "/tables")
            return result.get("data", [])
        except Exception as e:
            self.logger.error("Failed to get table list: %s", e)
            return []

    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        테이블 스키마(컬럼 정보) 조회

        Args:
            table_name: 테이블 이름

        Returns:
            스키마 정보 리스트
        """
        try:
            payload = {"table_name": table_name}
            result = self._sync_request("POST", "/table/schema", payload)
            return result.get("data", [])
        except Exception as e:
            self.logger.error("Failed to get table schema for %s: %s", table_name, e)
            return []

    def get_base_model_by_table_name(self, table_name: str) -> Optional[Type]:
        """
        테이블 이름으로 동적 Pydantic 모델 클래스 생성

        Args:
            table_name: 테이블 이름

        Returns:
            동적으로 생성된 모델 클래스 또는 None
        """
        try:
            from pydantic import create_model

            schema = self.get_table_schema(table_name)
            if not schema:
                self.logger.warning(f"No schema found for table: {table_name}")
                return None

            type_mapping = {
                'integer': int,
                'bigint': int,
                'smallint': int,
                'numeric': float,
                'real': float,
                'double precision': float,
                'character varying': str,
                'varchar': str,
                'character': str,
                'char': str,
                'text': str,
                'boolean': bool,
                'timestamp without time zone': str,
                'timestamp with time zone': str,
                'date': str,
                'time': str,
                'json': dict,
                'jsonb': dict,
                'ARRAY': list,
                'INTEGER': int,
                'REAL': float,
                'TEXT': str,
                'BLOB': bytes,
            }

            fields = {}

            for row in schema:
                col_name = row.get('column_name') or row.get('name')
                data_type = row.get('data_type') or row.get('type', '')
                is_nullable = row.get('is_nullable', 'YES') == 'YES'

                python_type = type_mapping.get(data_type.lower() if data_type else '', str)
                if is_nullable:
                    fields[col_name] = (Optional[python_type], None)
                else:
                    fields[col_name] = (python_type, ...)

            model_name = f"{table_name.capitalize()}Model"
            dynamic_model = create_model(model_name, **fields)

            return dynamic_model

        except Exception as e:
            self.logger.error("Failed to create BaseModel for table %s: %s", table_name, e)
            return None

    # ------------------------------------------------------------------ #
    # Raw Query Execution
    # ------------------------------------------------------------------ #

    def execute_raw_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """
        임의의 SQL 쿼리 실행

        보안상 SELECT 쿼리만 허용됩니다.

        Args:
            query: SQL 쿼리
            params: 쿼리 파라미터

        Returns:
            dict: {"success": bool, "data": list, "row_count": int}
        """
        try:
            payload = {
                "query": query,
                "params": list(params) if params else None
            }

            result = self._sync_request("POST", "/query", payload)
            return result

        except Exception as e:
            self.logger.error("Failed to execute raw query: %s", e)
            return {
                "success": False,
                "error": str(e),
                "data": []
            }

    # ------------------------------------------------------------------ #
    # Migration Methods (호환성 유지 - HTTP 클라이언트에서는 no-op)
    # ------------------------------------------------------------------ #

    def run_migrations(self) -> bool:
        """데이터베이스 스키마 마이그레이션 (xgen-core에서 담당)"""
        self.logger.info("run_migrations called on HTTP client - migrations are managed by xgen-core")
        return True

    # ------------------------------------------------------------------ #
    # Cleanup Methods
    # ------------------------------------------------------------------ #

    def close(self):
        """연결 종료 (HTTP 클라이언트에서는 특별한 정리 필요 없음)"""
        self.logger.info("DatabaseClient closed (HTTP client - no persistent connections)")

    async def cleanup(self):
        """비동기 정리 작업"""
        self.logger.info("DatabaseClient async cleanup called (no-op)")


class _VirtualConfigDbManager:
    """
    호환성을 위한 가상 config_db_manager

    기존 코드에서 app_db.config_db_manager.db_type 등을 접근하는 경우를 위해 제공

    xgen-core의 /query 엔드포인트는 내부 통신 전용이므로
    SELECT, INSERT, UPDATE, DELETE 등 모든 SQL 쿼리를 제한 없이 실행합니다.
    """

    def __init__(self, client: DatabaseClient):
        self._client = client
        self._db_type = "postgresql"  # 기본값

    @property
    def db_type(self) -> str:
        """데이터베이스 타입 반환"""
        return self._db_type

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """
        SQL 쿼리 실행

        xgen-core /query 엔드포인트를 통해 모든 SQL 쿼리 실행
        (SELECT, INSERT, UPDATE, DELETE 등 제한 없음)
        """
        result = self._client.execute_raw_query(query, params)
        return result.get("data", [])

    def execute_query_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """단일 결과 조회"""
        result = self._client.execute_raw_query(query, params)
        data = result.get("data", [])
        return data[0] if data else None

    def execute_insert(self, query: str, params: tuple = None) -> Optional[int]:
        """INSERT 실행 - 삽입된 레코드 ID 반환"""
        result = self._client.execute_raw_query(query, params)
        return result.get("id") if result.get("success") else None

    def execute_update_delete(self, query: str, params: tuple = None) -> Optional[int]:
        """UPDATE/DELETE 실행 - 영향받은 행 수 반환"""
        result = self._client.execute_raw_query(query, params)
        return result.get("row_count", 0) if result.get("success") else 0

    def connect(self) -> bool:
        """연결 확인 (HTTP 클라이언트에서는 health check)"""
        return self._client.check_health()

    def disconnect(self):
        """연결 종료 (HTTP 클라이언트에서는 no-op)"""
        self._client.close()

    def health_check(self, auto_recover: bool = True) -> bool:
        """헬스 체크"""
        return self._client.check_health()

    def reconnect(self) -> bool:
        """재연결"""
        return self._client.reconnect()

    def get_pool_stats(self) -> Dict[str, Any]:
        """풀 상태"""
        return self._client.get_pool_stats()

    def check_and_refresh_pool(self) -> bool:
        """풀 리프레시"""
        return self._client.check_and_refresh_pool()


# ------------------------------------------------------------------ #
# Alias for compatibility
# ------------------------------------------------------------------ #

# AppDatabaseManager 호환 alias
AppDatabaseManager = DatabaseClient


# ------------------------------------------------------------------ #
# Singleton / Default Client (독립 함수용)
# ------------------------------------------------------------------ #

_default_client: Optional[DatabaseClient] = None


def _get_default_client() -> DatabaseClient:
    """기본 클라이언트 인스턴스 반환 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = DatabaseClient()
    return _default_client


def get_database_client(config: Optional[Dict[str, Any]] = None) -> DatabaseClient:
    """
    DatabaseClient 인스턴스 가져오기

    Args:
        config: 설정 (None이면 기본 싱글톤 반환)

    Returns:
        DatabaseClient 인스턴스
    """
    if config:
        return DatabaseClient(config)
    return _get_default_client()
