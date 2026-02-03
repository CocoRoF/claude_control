"""
Redis Client for Claude Control

Claude 세션을 Redis에서 관리하기 위한 클라이언트
Multi-pod 환경에서 Redis가 true source 역할을 함
"""
import os
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Redis 연결이 가능한지 확인
import redis
REDIS_AVAILABLE = True

class RedisClient:
    """
    Claude 세션 관리용 Redis 클라이언트
    
    싱글톤 패턴으로 구현되어 애플리케이션 전체에서 하나의 인스턴스만 사용
    """
    
    _instance: Optional['RedisClient'] = None
    _initialized: bool = False
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        key_prefix: str = "claude-control"
    ):
        # 이미 초기화된 경우 스킵 (싱글톤)
        if RedisClient._initialized:
            return
            
        if not REDIS_AVAILABLE:
            logger.error("Redis 패키지가 없어 초기화할 수 없습니다")
            self._connection_available = False
            RedisClient._initialized = True
            return
        
        # 환경 변수에서 Redis 연결 정보 읽기
        self._host = host or os.getenv('REDIS_HOST', 'redis')
        self._port = port or int(os.getenv('REDIS_PORT', '6379'))
        self._db = db or int(os.getenv('REDIS_DB', '0'))
        self._password = password or os.getenv('REDIS_PASSWORD')
        
        # 연결 타임아웃 설정
        self._socket_timeout = float(os.getenv('REDIS_SOCKET_TIMEOUT', '5'))
        self._socket_connect_timeout = float(os.getenv('REDIS_CONNECT_TIMEOUT', '3'))
        
        # 키 프리픽스 (multi-tenant 지원)
        self._key_prefix = key_prefix
        
        # 연결 상태
        self._connection_available = False
        self._redis_client: Optional['redis.Redis'] = None
        
        # Redis 연결 시도
        self._connect()
        
        RedisClient._initialized = True
    
    def _connect(self) -> bool:
        """Redis 서버에 연결"""
        try:
            self._redis_client = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=True,
                socket_timeout=self._socket_timeout,
                socket_connect_timeout=self._socket_connect_timeout
            )
            
            # 연결 테스트
            self._redis_client.ping()
            self._connection_available = True
            logger.info(f"✅ Redis 연결 성공: {self._host}:{self._port}")
            return True
            
        except redis.exceptions.ConnectionError as e:
            logger.warning(f"⚠️  Redis 연결 실패: {self._host}:{self._port}")
            logger.warning(f"   원인: {e}")
            logger.warning(f"   💡 Redis 서버가 실행 중인지 확인하세요")
            self._connection_available = False
            return False
            
        except redis.exceptions.TimeoutError as e:
            logger.warning(f"⚠️  Redis 연결 타임아웃: {self._host}:{self._port}")
            logger.warning(f"   💡 네트워크 연결을 확인하세요")
            self._connection_available = False
            return False
            
        except Exception as e:
            logger.warning(f"⚠️  Redis 초기화 오류: {e}")
            self._connection_available = False
            return False
    
    @classmethod
    def get_instance(cls) -> 'RedisClient':
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """인스턴스 초기화 (테스트용)"""
        cls._instance = None
        cls._initialized = False
    
    # ========== 연결 관리 ==========
    
    @property
    def is_connected(self) -> bool:
        """Redis 연결 상태 확인"""
        return self._connection_available
    
    def health_check(self) -> bool:
        """Redis 연결 상태 체크"""
        if not self._connection_available or not self._redis_client:
            return False
        try:
            return self._redis_client.ping()
        except Exception as e:
            logger.error(f"Redis health check 실패: {e}")
            self._connection_available = False
            return False
    
    def reconnect(self) -> bool:
        """Redis 재연결 시도"""
        logger.info("Redis 재연결 시도...")
        return self._connect()
    
    # ========== 키 관리 ==========
    
    def _make_key(self, *parts: str) -> str:
        """키 생성 (prefix 포함)"""
        return f"{self._key_prefix}:{':'.join(parts)}"
    
    # ========== 세션 관리 ==========
    
    def save_session(self, session_id: str, session_data: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        세션 정보 저장
        
        Args:
            session_id: 세션 ID
            session_data: 세션 데이터 (dict)
            ttl: TTL (초), None이면 영구 저장
            
        Returns:
            성공 여부
        """
        if not self._connection_available:
            logger.warning("Redis 연결 불가 - 세션 저장 스킵")
            return False
            
        try:
            key = self._make_key("session", session_id)
            
            # datetime 객체를 ISO format 문자열로 변환
            data_to_save = self._serialize_session_data(session_data)
            
            if ttl:
                self._redis_client.setex(key, ttl, json.dumps(data_to_save))
            else:
                self._redis_client.set(key, json.dumps(data_to_save))
            
            # 세션 목록에도 추가
            sessions_set_key = self._make_key("sessions")
            self._redis_client.sadd(sessions_set_key, session_id)
            
            logger.debug(f"세션 저장 완료: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"세션 저장 실패: {session_id} - {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        세션 정보 조회
        
        Args:
            session_id: 세션 ID
            
        Returns:
            세션 데이터 또는 None
        """
        if not self._connection_available:
            return None
            
        try:
            key = self._make_key("session", session_id)
            data = self._redis_client.get(key)
            
            if data:
                session_data = json.loads(data)
                return self._deserialize_session_data(session_data)
            return None
            
        except Exception as e:
            logger.error(f"세션 조회 실패: {session_id} - {e}")
            return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        세션 삭제
        
        Args:
            session_id: 세션 ID
            
        Returns:
            성공 여부
        """
        if not self._connection_available:
            return False
            
        try:
            key = self._make_key("session", session_id)
            self._redis_client.delete(key)
            
            # 세션 목록에서도 제거
            sessions_set_key = self._make_key("sessions")
            self._redis_client.srem(sessions_set_key, session_id)
            
            logger.debug(f"세션 삭제 완료: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"세션 삭제 실패: {session_id} - {e}")
            return False
    
    def list_sessions(self) -> List[str]:
        """
        모든 세션 ID 목록 조회
        
        Returns:
            세션 ID 리스트
        """
        if not self._connection_available:
            return []
            
        try:
            sessions_set_key = self._make_key("sessions")
            return list(self._redis_client.smembers(sessions_set_key))
            
        except Exception as e:
            logger.error(f"세션 목록 조회 실패: {e}")
            return []
    
    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """
        모든 세션 데이터 조회
        
        Returns:
            세션 데이터 리스트
        """
        if not self._connection_available:
            return []
            
        try:
            session_ids = self.list_sessions()
            sessions = []
            
            for session_id in session_ids:
                session_data = self.get_session(session_id)
                if session_data:
                    sessions.append(session_data)
                    
            return sessions
            
        except Exception as e:
            logger.error(f"전체 세션 조회 실패: {e}")
            return []
    
    def session_exists(self, session_id: str) -> bool:
        """
        세션 존재 여부 확인
        
        Args:
            session_id: 세션 ID
            
        Returns:
            존재 여부
        """
        if not self._connection_available:
            return False
            
        try:
            key = self._make_key("session", session_id)
            return self._redis_client.exists(key) > 0
            
        except Exception as e:
            logger.error(f"세션 존재 확인 실패: {session_id} - {e}")
            return False
    
    def update_session_field(self, session_id: str, field: str, value: Any) -> bool:
        """
        세션의 특정 필드만 업데이트
        
        Args:
            session_id: 세션 ID
            field: 필드명
            value: 새 값
            
        Returns:
            성공 여부
        """
        if not self._connection_available:
            return False
            
        try:
            session_data = self.get_session(session_id)
            if not session_data:
                logger.warning(f"업데이트할 세션을 찾을 수 없음: {session_id}")
                return False
                
            session_data[field] = value
            return self.save_session(session_id, session_data)
            
        except Exception as e:
            logger.error(f"세션 필드 업데이트 실패: {session_id}.{field} - {e}")
            return False
    
    # ========== 유틸리티 ==========
    
    def _serialize_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """세션 데이터 직렬화 (datetime -> ISO string)"""
        result = {}
        for key, value in data.items():
            if isinstance(value, datetime):
                result[key] = value.isoformat()
            elif isinstance(value, dict):
                result[key] = self._serialize_session_data(value)
            else:
                result[key] = value
        return result
    
    def _deserialize_session_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """세션 데이터 역직렬화 (ISO string -> datetime)"""
        result = {}
        datetime_fields = ['created_at', 'updated_at', 'started_at', 'stopped_at']
        
        for key, value in data.items():
            if key in datetime_fields and isinstance(value, str):
                try:
                    result[key] = datetime.fromisoformat(value)
                except ValueError:
                    result[key] = value
            elif isinstance(value, dict):
                result[key] = self._deserialize_session_data(value)
            else:
                result[key] = value
        return result
    
    def clear_all_sessions(self) -> bool:
        """
        모든 세션 삭제 (주의: 위험한 작업)
        
        Returns:
            성공 여부
        """
        if not self._connection_available:
            return False
            
        try:
            session_ids = self.list_sessions()
            for session_id in session_ids:
                self.delete_session(session_id)
            
            logger.info(f"전체 세션 삭제 완료: {len(session_ids)}개")
            return True
            
        except Exception as e:
            logger.error(f"전체 세션 삭제 실패: {e}")
            return False
    
    # ========== 일반 키-값 저장 ==========
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        일반 키-값 저장
        
        Args:
            key: 키 (prefix 자동 추가)
            value: 값 (자동 JSON 직렬화)
            ttl: TTL (초)
            
        Returns:
            성공 여부
        """
        if not self._connection_available:
            return False
            
        try:
            full_key = self._make_key(key)
            data = json.dumps(value) if not isinstance(value, str) else value
            
            if ttl:
                self._redis_client.setex(full_key, ttl, data)
            else:
                self._redis_client.set(full_key, data)
                
            return True
            
        except Exception as e:
            logger.error(f"Redis set 실패: {key} - {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        일반 키-값 조회
        
        Args:
            key: 키 (prefix 자동 추가)
            default: 기본값
            
        Returns:
            값 또는 기본값
        """
        if not self._connection_available:
            return default
            
        try:
            full_key = self._make_key(key)
            data = self._redis_client.get(full_key)
            
            if data is None:
                return default
                
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                return data
                
        except Exception as e:
            logger.error(f"Redis get 실패: {key} - {e}")
            return default
    
    def delete(self, key: str) -> bool:
        """
        일반 키 삭제
        
        Args:
            key: 키 (prefix 자동 추가)
            
        Returns:
            성공 여부
        """
        if not self._connection_available:
            return False
            
        try:
            full_key = self._make_key(key)
            self._redis_client.delete(full_key)
            return True
            
        except Exception as e:
            logger.error(f"Redis delete 실패: {key} - {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """
        키 존재 여부 확인
        
        Args:
            key: 키 (prefix 자동 추가)
            
        Returns:
            존재 여부
        """
        if not self._connection_available:
            return False
            
        try:
            full_key = self._make_key(key)
            return self._redis_client.exists(full_key) > 0
            
        except Exception as e:
            logger.error(f"Redis exists 실패: {key} - {e}")
            return False
    
    # ========== 통계 ==========
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Redis 상태 및 세션 통계 반환
        
        Returns:
            통계 정보
        """
        stats = {
            "connected": self._connection_available,
            "host": self._host,
            "port": self._port,
            "db": self._db,
            "key_prefix": self._key_prefix,
            "session_count": 0,
            "redis_info": None
        }
        
        if not self._connection_available:
            return stats
            
        try:
            stats["session_count"] = len(self.list_sessions())
            
            # Redis 서버 정보
            info = self._redis_client.info()
            stats["redis_info"] = {
                "version": info.get("redis_version"),
                "connected_clients": info.get("connected_clients"),
                "used_memory_human": info.get("used_memory_human"),
                "uptime_in_days": info.get("uptime_in_days")
            }
            
        except Exception as e:
            logger.error(f"Redis 통계 조회 실패: {e}")
            
        return stats


# 편의를 위한 전역 함수
def get_redis_client() -> RedisClient:
    """Redis 클라이언트 싱글톤 인스턴스 반환"""
    return RedisClient.get_instance()
