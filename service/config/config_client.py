"""
Config Client

xgen-core의 Config API를 통해 설정을 관리하는 HTTP 클라이언트입니다.

xgen-core가 Config의 True Source 역할을 하며,
이 클라이언트는 HTTP를 통해 xgen-core의 /api/data/config 엔드포인트를 호출합니다.

사용 예시:
    # 싱글톤 인스턴스 사용
    config_client = ConfigClient()
    
    # 설정 값 조회
    value = config_client.get_config_value("OPENAI_API_KEY", "default_key")
    
    # 설정 저장
    config_client.set_config(
        config_path="openai.api_key",
        config_value="sk-xxx",
        data_type="string",
        category="openai",
        env_name="OPENAI_API_KEY"
    )
    
    # 카테고리별 설정 조회
    category_config = config_client.get_config_by_category_name("openai")
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List, Generic, TypeVar

import httpx

logger = logging.getLogger("config-client")

T = TypeVar('T')


# ============================================================== #
# PersistentConfig 클래스
# ============================================================== #

class PersistentConfig(Generic[T]):
    """
    설정 값을 담는 클래스
    """

    def __init__(
        self,
        env_name: str,
        config_path: str,
        value: T,
        env_value: T = None,
        config_value: T = None,
        data_type: str = "string",
        category: str = None
    ):
        self.env_name = env_name
        self.config_path = config_path
        self.value = value
        self.env_value = env_value if env_value is not None else value
        self.config_value = config_value
        self.data_type = data_type
        self.category = category

    def __str__(self):
        return str(self.value)

    def __repr__(self):
        return f"PersistentConfig(env_name='{self.env_name}', value={self.value})"

    @property
    def __dict__(self):
        raise TypeError(
            "PersistentConfig object cannot be converted to dict, use .value instead."
        )

    def __getattribute__(self, item):
        if item == "__dict__":
            raise TypeError(
                "PersistentConfig object cannot be converted to dict, use .value instead."
            )
        return super().__getattribute__(item)

    def refresh(self):
        """설정 새로고침 (HTTP 클라이언트에서는 항상 최신 상태)"""
        logger.debug("PersistentConfig refresh called: %s", self.env_name)

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 형태로 변환"""
        return {
            'env_name': self.env_name,
            'path': self.config_path,
            'value': self.value,
            'type': self.data_type,
            'category': self.category,
            'config_value': self.config_value,
            'env_value': self.env_value
        }


class DynamicCategoryConfig:
    """
    동적 카테고리 설정 클래스
    각 설정을 속성으로 접근 가능
    """

    def __init__(self, category_name: str):
        self.category_name = category_name
        self.configs: Dict[str, PersistentConfig] = {}

    def __repr__(self):
        config_names = list(self.configs.keys())
        return f"DynamicCategoryConfig(category='{self.category_name}', configs={config_names})"

    def __getattribute__(self, item):
        # 내부 속성은 정상적으로 반환
        if item in ['category_name', 'configs', '__dict__', '__class__', '__repr__']:
            return super().__getattribute__(item)

        # configs에 있는 경우 PersistentConfig 반환
        configs = super().__getattribute__('configs')
        if item in configs:
            return configs[item]

        # 그 외는 정상적으로 처리
        return super().__getattribute__(item)

    def get_all_configs(self) -> Dict[str, PersistentConfig]:
        """모든 설정 반환"""
        return self.configs


# ============================================================== #
# ConfigClient - HTTP 기반 Config 클라이언트
# ============================================================== #

class ConfigClient:
    """
    xgen-core Config API를 호출하는 HTTP 클라이언트
    """

    def __init__(self):
        """
        ConfigClient 초기화
        """
        base_url = os.getenv("CORE_SERVICE_BASE_URL", "http://xgen-core:8000")
                
        # 환경변수 또는 설정에서 값 읽기
        self.base_url = base_url.rstrip("/") + "/api/data/config"
        self.timeout = float(os.getenv("CORE_SERVICE_TIMEOUT", "60"))
        self.api_key = os.getenv("XGEN_INTERNAL_API_KEY", "xgen-internal-key-2024")
        
        # HTTP 클라이언트
        self._client: Optional[httpx.Client] = None
        self._async_client: Optional[httpx.AsyncClient] = None
        
        logger.info(
            "ConfigClient 초기화: base_url=%s, timeout=%s",
            self.base_url, self.timeout
        )

    # ========== HTTP Client Management ==========

    def _get_client(self) -> httpx.Client:
        """동기 HTTP 클라이언트 반환"""
        if self._client is None:
            self._client = httpx.Client(
                timeout=self.timeout,
                headers=self._get_headers()
            )
        return self._client

    def _get_async_client(self) -> httpx.AsyncClient:
        """비동기 HTTP 클라이언트 반환"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=self._get_headers()
            )
        return self._async_client

    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def close(self):
        """클라이언트 리소스 정리"""
        if self._client:
            self._client.close()
            self._client = None
        if self._async_client:
            # 비동기 클라이언트는 별도 처리 필요
            self._async_client = None

    # ========== Helper Methods ==========

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        동기 HTTP 요청 수행

        Args:
            method: HTTP 메서드 (GET, POST 등)
            endpoint: 엔드포인트 경로 (예: "/get", "/set")
            data: 요청 본문 데이터

        Returns:
            응답 JSON
        """
        url = f"{self.base_url}{endpoint}"
        client = self._get_client()

        try:
            if method.upper() == "GET":
                response = client.get(url)
            else:
                response = client.post(url, json=data or {})

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error %s: %s", e.response.status_code, e.response.text)
            return {"success": False, "error": str(e)}
        except httpx.RequestError as e:
            logger.error("Request error: %s", e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return {"success": False, "error": str(e)}

    async def _make_request_async(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """비동기 HTTP 요청 수행"""
        url = f"{self.base_url}{endpoint}"
        client = self._get_async_client()

        try:
            if method.upper() == "GET":
                response = await client.get(url)
            else:
                response = await client.post(url, json=data or {})

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error %s: %s", e.response.status_code, e.response.text)
            return {"success": False, "error": str(e)}
        except httpx.RequestError as e:
            logger.error("Request error: %s", e)
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            return {"success": False, "error": str(e)}

    def _dict_to_persistent_config(self, config_dict: Dict[str, Any]) -> PersistentConfig:
        """딕셔너리를 PersistentConfig 객체로 변환"""
        # config_dict가 딕셔너리가 아닌 경우 방어적 처리
        if not isinstance(config_dict, dict):
            logger.warning(f"_dict_to_persistent_config received non-dict: {type(config_dict)} = {config_dict}")
            return PersistentConfig(
                env_name=str(config_dict) if config_dict else '',
                config_path='',
                value=config_dict,
                data_type='string',
                category=None
            )
        
        return PersistentConfig(
            env_name=config_dict.get('env_name', ''),
            config_path=config_dict.get('path', config_dict.get('config_path', '')),
            value=config_dict.get('value', config_dict.get('data')),
            env_value=config_dict.get('env_value'),
            config_value=config_dict.get('config_value', config_dict.get('value')),
            data_type=config_dict.get('type', config_dict.get('data_type', 'string')),
            category=config_dict.get('category')
        )

    # ========== Health Check ==========

    def health_check(self) -> bool:
        """Config 서비스 연결 상태 확인"""
        try:
            result = self._make_request("GET", "/health")
            return result.get("healthy", False)
        except Exception as e:
            logger.error("Health check failed: %s", e)
            return False

    # ========== Config 값 조회 ==========

    def get_config_value(self, env_name: str, default: Any = None) -> Any:
        """
        설정 값만 조회 (env_name 기준)

        Args:
            env_name: 환경 변수 이름
            default: 기본값

        Returns:
            설정 값 또는 기본값
        """
        try:
            result = self._make_request("POST", "/get-value", {
                "env_name": env_name,
                "default": default
            })

            if result.get("success"):
                return result.get("value", default)
            return default

        except Exception as e:
            logger.error("Config 조회 실패: %s - %s", env_name, e)
            return default

    def get_config(self, env_name: str) -> Optional[Dict[str, Any]]:
        """
        설정 값과 메타데이터 조회 (env_name 기준)

        Args:
            env_name: 환경 변수 이름

        Returns:
            설정 데이터 (value, type, category, path, env_name)
        """
        try:
            result = self._make_request("POST", "/get", {
                "env_name": env_name
            })

            if result.get("success") and result.get("data") is not None:
                return {
                    "value": result.get("data"),
                    "type": result.get("data_type", "string"),
                    "category": result.get("category"),
                    "path": result.get("config_path", ""),
                    "env_name": result.get("env_name", env_name)
                }
            return None

        except Exception as e:
            logger.error("Config 조회 실패: %s - %s", env_name, e)
            return None

    # ========== Config 저장/업데이트/삭제 ==========

    def set_config(
        self,
        config_path: str,
        config_value: Any,
        data_type: str = "string",
        category: str = None,
        env_name: str = None
    ) -> bool:
        """
        설정 값 저장

        Args:
            config_path: 설정 경로 (예: "openai.api_key")
            config_value: 설정 값
            data_type: 데이터 타입
            category: 카테고리
            env_name: 환경 변수 이름

        Returns:
            bool: 성공 여부
        """
        try:
            result = self._make_request("POST", "/set", {
                "config_path": config_path,
                "config_value": config_value,
                "data_type": data_type,
                "category": category,
                "env_name": env_name or config_path.replace(".", "_").upper()
            })

            return result.get("success", False)

        except Exception as e:
            logger.error("Config 저장 실패: %s - %s", config_path, e)
            return False

    def update_config(
        self,
        env_name: str,
        config_value: Any,
        data_type: Optional[str] = None,
        category: Optional[str] = None,
        config_path: Optional[str] = None,
        db_manager=None
    ) -> bool:
        """
        설정 값 업데이트

        Args:
            env_name: 환경 변수 이름
            config_value: 새로운 설정 값
            data_type: 데이터 타입 (없으면 기존 타입 유지)
            category: 카테고리 (없으면 기존 카테고리 유지)
            config_path: 설정 경로 (없으면 기존 경로 유지)
            db_manager: DB 매니저 (호환성, 미사용)

        Returns:
            bool: 성공 여부
        """
        try:
            result = self._make_request("POST", "/update", {
                "config_name": env_name,
                "value": config_value
            })

            return result.get("success", False)

        except Exception as e:
            logger.error("Config 업데이트 실패: %s - %s", env_name, e)
            return False

    def delete_config(self, env_name: str) -> bool:
        """
        설정 삭제

        Args:
            env_name: 환경 변수 이름

        Returns:
            bool: 성공 여부
        """
        try:
            result = self._make_request("POST", "/delete", {
                "env_name": env_name
            })

            return result.get("success", False)

        except Exception as e:
            logger.error("Config 삭제 실패: %s - %s", env_name, e)
            return False

    def exists(self, env_name: str) -> bool:
        """
        설정 존재 여부 확인

        Args:
            env_name: 환경 변수 이름

        Returns:
            bool: 존재 여부
        """
        try:
            result = self._make_request("POST", "/exists", {
                "env_name": env_name
            })

            return result.get("exists", False)

        except Exception as e:
            logger.error("Config 존재 확인 실패: %s - %s", env_name, e)
            return False

    # ========== 카테고리 관련 ==========

    def get_category_configs(self, category: str) -> List[Dict[str, Any]]:
        """
        특정 카테고리의 모든 설정 조회 (리스트 형태)

        Args:
            category: 카테고리 이름

        Returns:
            설정 리스트
        """
        try:
            result = self._make_request("POST", "/category", {
                "category": category
            })

            if result.get("success"):
                configs = result.get("configs", [])
                
                # 디버깅을 위한 로깅 (INFO 레벨로 변경하여 실제 응답 확인)
                logger.info(f"Category '{category}' raw response: success={result.get('success')}, configs type={type(configs)}")
                if configs:
                    logger.info(f"Category '{category}' first config sample: {configs[0] if isinstance(configs, list) and len(configs) > 0 else configs}")
                
                # 리스트가 아닌 경우 처리
                if configs is None:
                    return []
                
                # 딕셔너리 형태인 경우 (key: config_name, value: config_dict)
                if isinstance(configs, dict):
                    result_list = []
                    for key, value in configs.items():
                        if isinstance(value, dict):
                            # value가 이미 딕셔너리면 그대로 사용
                            if 'env_name' not in value:
                                value['env_name'] = key
                            result_list.append(value)
                        else:
                            # value가 단순 값이면 딕셔너리로 변환
                            result_list.append({
                                'env_name': key,
                                'value': value,
                                'path': f"{category}.{key}",
                                'category': category
                            })
                    return result_list
                
                # 리스트 형태인 경우
                if isinstance(configs, list):
                    result_list = []
                    for config in configs:
                        if isinstance(config, dict):
                            result_list.append(config)
                        elif isinstance(config, str):
                            # 문자열인 경우 (키 이름만 있는 경우)
                            logger.warning(f"Config item is string, not dict: {config}")
                            result_list.append({
                                'env_name': config,
                                'value': None,
                                'path': f"{category}.{config}",
                                'category': category
                            })
                        else:
                            logger.warning(f"Unexpected config type: {type(config)}, value: {config}")
                    return result_list
                
                logger.warning(f"Unexpected configs type: {type(configs)}")
                return []
            return []

        except Exception as e:
            logger.error("카테고리 Config 조회 실패: %s - %s", category, e)
            return []

    def get_category_configs_nested(self, category: str) -> Dict[str, Any]:
        """
        특정 카테고리의 모든 설정 조회 (중첩 딕셔너리 형태)

        Args:
            category: 카테고리 이름

        Returns:
            중첩된 딕셔너리 형태의 설정
        """
        try:
            configs = self.get_category_configs(category)
            result = {}

            for config in configs:
                path = config.get('path', config.get('config_path', ''))
                value = config.get('value')

                if not path:
                    continue

                # 경로를 '.'로 분리하여 중첩 딕셔너리 생성
                keys = path.split('.')
                current = result

                for key in keys[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]

                if keys:
                    current[keys[-1]] = value

            return result

        except Exception as e:
            logger.error("카테고리 중첩 Config 조회 실패: %s - %s", category, e)
            return {}

    def get_all_categories(self) -> List[str]:
        """
        모든 카테고리 목록 조회

        Returns:
            카테고리 목록
        """
        try:
            result = self._make_request("GET", "/categories")

            if result.get("success"):
                return result.get("categories", [])
            return []

        except Exception as e:
            logger.error("카테고리 목록 조회 실패: %s", e)
            return []

    def get_all_configs_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        카테고리별 모든 설정 조회 (호환성 메서드)

        Args:
            category: 카테고리 이름

        Returns:
            설정 리스트
        """
        return self.get_category_configs(category)

    # ========== 전체 조회 ==========

    def get_all_configs(self) -> List[Dict[str, Any]]:
        """
        모든 설정 조회

        Returns:
            모든 설정 리스트
        """
        try:
            result = self._make_request("GET", "/all")

            if result.get("success"):
                configs = result.get("configs", [])
                # 딕셔너리 형태인 경우 리스트로 변환
                if isinstance(configs, dict):
                    return list(configs.values())
                return configs
            return []

        except Exception as e:
            logger.error("전체 Config 조회 실패: %s", e)
            return []

    # ========== Bulk Operations ==========

    def bulk_get(self, env_names: List[str]) -> Dict[str, Any]:
        """
        다중 설정 조회

        Args:
            env_names: 환경 변수 이름 목록

        Returns:
            설정 값 딕셔너리
        """
        try:
            result = self._make_request("POST", "/bulk-get", {
                "env_names": env_names
            })

            if result.get("success"):
                return result.get("configs", {})
            return {}

        except Exception as e:
            logger.error("Bulk Config 조회 실패: %s", e)
            return {}

    def bulk_set(self, configs: List[Dict[str, Any]]) -> bool:
        """
        다중 설정 저장

        Args:
            configs: 설정 목록
                각 항목: {config_path, config_value, data_type, category, env_name}

        Returns:
            bool: 성공 여부
        """
        try:
            result = self._make_request("POST", "/bulk-set", {
                "configs": configs
            })

            return result.get("success", False)

        except Exception as e:
            logger.error("Bulk Config 저장 실패: %s", e)
            return False

    # ========== ConfigComposer 호환성 메서드 ==========

    def get_config_by_name(self, config_name: str) -> PersistentConfig:
        """
        이름으로 특정 설정 가져오기 (ConfigComposer 호환)

        Args:
            config_name: 설정 이름 (예: "OPENAI_API_KEY")

        Returns:
            PersistentConfig: 설정 객체

        Raises:
            KeyError: 설정이 존재하지 않는 경우
        """
        config_data = self.get_config(config_name)

        if config_data:
            return self._dict_to_persistent_config(config_data)

        # 모든 config에서 검색
        all_configs = self.get_all_configs()
        for config in all_configs:
            if config.get('env_name') == config_name or config.get('path') == config_name:
                return self._dict_to_persistent_config(config)

            # path의 마지막 부분이 config_name과 일치하는 경우
            path = config.get('path', '')
            if path:
                path_parts = path.split('.')
                if path_parts[-1] == config_name:
                    return self._dict_to_persistent_config(config)

        raise KeyError(f"Configuration '{config_name}' not found")

    def get_config_by_category_name(self, category_name: str) -> DynamicCategoryConfig:
        """
        카테고리 이름으로 특정 설정 그룹 가져오기 (ConfigComposer 호환)

        Args:
            category_name: 카테고리 이름 (예: "openai", "database")

        Returns:
            DynamicCategoryConfig: 해당 카테고리의 모든 설정

        Raises:
            KeyError: 카테고리가 존재하지 않는 경우
        """
        category_configs = self.get_category_configs(category_name)

        if not category_configs:
            raise KeyError(f"Configuration category '{category_name}' not found")

        # 동적 설정 객체 생성
        dynamic_config = DynamicCategoryConfig(category_name)

        for config in category_configs:
            try:
                # config가 딕셔너리가 아닌 경우 스킵
                if not isinstance(config, dict):
                    logger.warning(f"Skipping non-dict config: {type(config)} = {config}")
                    continue
                    
                persistent_config = self._dict_to_persistent_config(config)
                env_name = config.get('env_name', '')
                if env_name:
                    setattr(dynamic_config, env_name, persistent_config)
                    dynamic_config.configs[env_name] = persistent_config
            except Exception as e:
                logger.warning(f"Failed to process config item: {config}, error: {e}")
                continue

        return dynamic_config

    def get_all_config(self, **kwargs) -> Dict[str, Any]:
        """
        모든 설정을 카테고리별로 구조화하여 반환 (ConfigComposer 호환)

        Returns:
            Dict: {category_name: {nested configs}, all_configs: [...]}
        """
        try:
            result = {}
            categories = self.get_all_categories()

            for category in categories:
                result[category] = self.get_category_configs_nested(category)

            result["all_configs"] = self.get_all_configs()
            return result

        except Exception as e:
            logger.error("전체 Config 조회 실패: %s", e)
            return {"all_configs": []}

    def get_config_summary(self) -> Dict[str, Any]:
        """
        모든 설정의 요약 정보 반환 (ConfigComposer 호환)

        Returns:
            Dict: 설정 요약 정보
        """
        try:
            result = self._make_request("GET", "/summary")

            if result.get("success"):
                return result
            return {
                "total_configs": 0,
                "discovered_categories": [],
                "categories": {}
            }

        except Exception as e:
            logger.error("Config 요약 정보 조회 실패: %s", e)
            return {
                "total_configs": 0,
                "discovered_categories": [],
                "categories": {},
                "error": str(e)
            }

    def refresh_all(self) -> None:
        """
        모든 설정을 새로고침 (ConfigComposer 호환)
        """
        try:
            result = self._make_request("POST", "/refresh")
            if result.get("success"):
                logger.info("All configs refreshed successfully")
            else:
                logger.warning("Config refresh may have failed: %s", result.get("error"))
        except Exception as e:
            logger.error("Config refresh 실패: %s", e)

    def ensure_redis_sync(self) -> None:
        """
        Redis/Local 동기화 (ConfigComposer 호환)
        """
        try:
            result = self._make_request("POST", "/sync")
            if result.get("success"):
                logger.info("Config sync completed successfully")
            else:
                logger.warning("Config sync may have failed: %s", result.get("error"))
        except Exception as e:
            logger.error("Config sync 실패: %s", e)

    # ========== 검색 ==========

    def search_configs(self, pattern: str) -> Dict[str, Any]:
        """
        설정 검색

        Args:
            pattern: 검색 패턴

        Returns:
            매칭된 설정 딕셔너리
        """
        try:
            result = self._make_request("POST", "/search", {
                "pattern": pattern
            })

            if result.get("success"):
                return result.get("configs", {})
            return {}

        except Exception as e:
            logger.error("Config 검색 실패: %s", e)
            return {}

    # ========== PersistentConfig 객체 반환 메서드 ==========

    def get_all_persistent_configs(self) -> List[PersistentConfig]:
        """
        모든 설정을 PersistentConfig 객체 리스트로 반환

        Returns:
            List[PersistentConfig]: 모든 설정 객체 리스트
        """
        try:
            all_configs = self.get_all_configs()
            return [self._dict_to_persistent_config(config) for config in all_configs]
        except Exception as e:
            logger.error("전체 PersistentConfig 조회 실패: %s", e)
            return []

    def get_category_persistent_configs(self, category: str) -> List[PersistentConfig]:
        """
        특정 카테고리의 모든 설정을 PersistentConfig 객체 리스트로 반환

        Args:
            category: 카테고리 이름

        Returns:
            List[PersistentConfig]: 카테고리 설정 객체 리스트
        """
        try:
            category_configs = self.get_category_configs(category)
            return [self._dict_to_persistent_config(config) for config in category_configs]
        except Exception as e:
            logger.error("카테고리 PersistentConfig 조회 실패: %s - %s", category, e)
            return []

    def refresh_all_configs(self):
        """모든 PersistentConfig 객체를 새로고침"""
        self.refresh_all()

    def export_config_summary(self) -> Dict[str, Any]:
        """설정 요약 정보 반환 (PersistentConfig 형태)"""
        try:
            all_configs = self.get_all_configs()

            return {
                "total_configs": len(all_configs),
                "storage_type": "http_client",
                "configs": [
                    {
                        "env_name": config.get("env_name", ""),
                        "config_path": config.get("path", config.get("config_path", "")),
                        "current_value": config.get("value"),
                        "default_value": config.get("env_value"),
                        "is_saved": config.get("config_value") is not None,
                        "data_type": config.get("type", config.get("data_type", "string")),
                        "category": config.get("category")
                    }
                    for config in all_configs
                ]
            }
        except Exception as e:
            logger.error("설정 요약 정보 생성 실패: %s", e)
            return {
                "total_configs": 0,
                "storage_type": "http_client",
                "configs": [],
                "error": str(e)
            }

    def get_registry_statistics(self) -> Dict[str, Any]:
        """레지스트리 통계 정보 반환"""
        try:
            all_configs = self.get_all_configs()
            config_paths = [config.get('path', config.get('config_path', '')) for config in all_configs]
            env_names = [config.get('env_name', '') for config in all_configs]

            # 중복 검사
            duplicate_paths = []
            duplicate_names = []
            seen_paths = set()
            seen_names = set()

            for path in config_paths:
                if path and path in seen_paths:
                    duplicate_paths.append(path)
                seen_paths.add(path)

            for name in env_names:
                if name and name in seen_names:
                    duplicate_names.append(name)
                seen_names.add(name)

            return {
                "total_configs": len(all_configs),
                "unique_config_paths": len(set(filter(None, config_paths))),
                "unique_env_names": len(set(filter(None, env_names))),
                "duplicate_config_paths": duplicate_paths,
                "duplicate_env_names": duplicate_names,
                "has_duplicates": len(duplicate_paths) > 0 or len(duplicate_names) > 0,
                "categories": self.get_all_categories(),
                "storage_type": "http_client"
            }
        except Exception as e:
            logger.error("통계 정보 조회 실패: %s", e)
            return {
                "total_configs": 0,
                "error": str(e)
            }


# ============================================================== #
# Singleton / Default Client
# ============================================================== #

_default_client: Optional[ConfigClient] = None


def _get_default_client() -> ConfigClient:
    """기본 클라이언트 인스턴스 반환 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = ConfigClient()
    return _default_client


def get_config_client(config: Optional[Dict[str, Any]] = None) -> ConfigClient:
    """
    ConfigClient 인스턴스 가져오기

    Args:
        config: 설정 (None이면 기본 싱글톤 반환)

    Returns:
        ConfigClient 인스턴스
    """
    if config:
        return ConfigClient(config)
    return _get_default_client()
