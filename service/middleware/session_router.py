"""
Session Routing Middleware

Multi-pod 환경에서 세션 기반 요청 라우팅
세션이 다른 Pod에 있으면 해당 Pod로 프록시
"""
import re
import logging
from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from service.redis.redis_client import RedisClient
from service.pod.pod_info import get_pod_info, PodInfo
from service.proxy.internal_proxy import get_internal_proxy, PROXY_HEADER

logger = logging.getLogger(__name__)

# 세션 ID를 추출할 URL 패턴들
SESSION_URL_PATTERNS = [
    # /api/mcp/sessions/{session_id}
    re.compile(r'^/api/mcp/sessions/([a-f0-9-]{36})(?:/.*)?$'),
    # /api/mcp/mcp-request (body에서 session_id 추출 필요)
]

# 세션 라우팅이 필요한 경로들
SESSION_ROUTES = [
    '/api/mcp/sessions/',  # GET, DELETE /api/mcp/sessions/{session_id}
    '/api/mcp/mcp-request',  # POST (body에 session_id)
]

# 세션 라우팅에서 제외할 경로
EXCLUDED_ROUTES = [
    '/api/mcp/sessions',  # 목록 조회 (POST로 세션 생성 포함)
    '/health',
    '/redis/stats',
    '/',
]


class SessionRoutingMiddleware(BaseHTTPMiddleware):
    """
    세션 기반 요청 라우팅 미들웨어
    
    세션이 현재 Pod에 없으면 해당 세션이 있는 Pod로 프록시
    """
    
    def __init__(self, app: ASGIApp, redis_client: Optional[RedisClient] = None):
        super().__init__(app)
        self._redis: Optional[RedisClient] = redis_client
        
    def set_redis_client(self, redis_client: RedisClient):
        """Redis 클라이언트 설정 (지연 주입)"""
        self._redis = redis_client
    
    @property
    def redis(self) -> Optional[RedisClient]:
        """Redis 클라이언트 반환"""
        if self._redis is None:
            from service.redis.redis_client import get_redis_client
            try:
                self._redis = get_redis_client()
            except Exception:
                pass
        return self._redis
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        요청 처리
        
        1. 프록시된 요청이면 바로 처리
        2. 세션 라우팅이 필요한 경로인지 확인
        3. 세션이 다른 Pod에 있으면 프록시
        4. 현재 Pod에 있으면 로컬 처리
        """
        path = request.url.path
        method = request.method
        
        logger.info(f"🔍 [SessionRouter] Incoming request: {method} {path}")
        
        # 이미 프록시된 요청이면 바로 처리
        if request.headers.get(PROXY_HEADER) == "true":
            source_pod = request.headers.get("X-MCP-Station-Source-Pod", "unknown")
            logger.debug(f"📥 Handling proxied request from {source_pod}: {path}")
            return await call_next(request)
        
        # 제외할 경로 확인
        if self._is_excluded_route(path):
            return await call_next(request)
        
        # 세션 라우팅이 필요한 경로인지 확인
        if not self._needs_session_routing(path):
            return await call_next(request)
        
        # 세션 ID 추출
        session_id = await self._extract_session_id(request)
        
        logger.info(f"🔍 [SessionRouter] Session ID extracted: {session_id}")
        
        if not session_id:
            # 세션 ID가 없으면 로컬 처리
            logger.info(f"🔍 [SessionRouter] No session_id, processing locally")
            return await call_next(request)
        
        # Redis에서 세션의 Pod 정보 확인
        routing_result = self._get_session_pod_info(session_id)
        
        logger.info(f"🔍 [SessionRouter] Routing result: {routing_result}")
        
        if routing_result is None:
            # 세션 정보가 없으면 로컬 처리 (404 반환 예상)
            logger.warning(f"Session not found in Redis: {session_id}")
            return await call_next(request)
        
        target_pod_name, target_pod_ip = routing_result
        
        # 현재 Pod와 같은지 확인
        pod_info = get_pod_info()
        
        logger.info(f"🔍 [SessionRouter] Target: {target_pod_name}@{target_pod_ip}, Current: {pod_info.pod_name}@{pod_info.pod_ip}")
        
        if target_pod_name == pod_info.pod_name or target_pod_ip == pod_info.pod_ip:
            # 현재 Pod에서 처리
            logger.info(f"📍 Session {session_id[:8]}... is on this pod, processing locally")
            return await call_next(request)
        
        # 다른 Pod로 프록시
        logger.info(f"🔀 Session {session_id[:8]}... is on {target_pod_name} ({target_pod_ip}), proxying...")
        
        proxy = get_internal_proxy()
        return await proxy.proxy_request(
            target_pod_ip=target_pod_ip,
            target_port=pod_info.service_port,
            request=request,
            source_pod_name=pod_info.pod_name
        )
    
    def _is_excluded_route(self, path: str) -> bool:
        """제외할 경로인지 확인"""
        # 정확히 일치하는 경우
        if path in EXCLUDED_ROUTES:
            return True
        
        # 세션 목록 조회 (정확히 /api/mcp/sessions)
        if path == '/api/mcp/sessions':
            return True
            
        return False
    
    def _needs_session_routing(self, path: str) -> bool:
        """세션 라우팅이 필요한 경로인지 확인"""
        for route in SESSION_ROUTES:
            if path.startswith(route):
                return True
        return False
    
    async def _extract_session_id(self, request: Request) -> Optional[str]:
        """
        요청에서 세션 ID 추출
        
        URL 경로 또는 요청 본문에서 세션 ID를 추출
        """
        path = request.url.path
        
        # URL 패턴에서 추출
        for pattern in SESSION_URL_PATTERNS:
            match = pattern.match(path)
            if match:
                return match.group(1)
        
        # POST /api/mcp/mcp-request의 경우 body에서 추출
        if path == '/api/mcp/mcp-request' and request.method == 'POST':
            try:
                # body를 읽고 다시 설정 (미들웨어에서 body를 두 번 읽을 수 있도록)
                body = await request.body()
                
                import json
                data = json.loads(body)
                return data.get('session_id')
            except Exception as e:
                logger.warning(f"Failed to extract session_id from body: {e}")
        
        return None
    
    def _get_session_pod_info(self, session_id: str) -> Optional[tuple]:
        """
        Redis에서 세션의 Pod 정보 조회
        
        Returns:
            (pod_name, pod_ip) 또는 None
        """
        if not self.redis or not self.redis.is_connected:
            logger.warning("Redis not available for session routing")
            return None
        
        try:
            session_data = self.redis.get_session(session_id)
            
            if not session_data:
                return None
            
            pod_name = session_data.get('pod_name')
            pod_ip = session_data.get('pod_ip')
            
            if not pod_name or not pod_ip:
                logger.warning(f"Session {session_id} has no pod info")
                return None
            
            return (pod_name, pod_ip)
            
        except Exception as e:
            logger.error(f"Failed to get session pod info: {e}")
            return None
