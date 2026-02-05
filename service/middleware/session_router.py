"""
Session Routing Middleware

Session-based request routing in multi-pod environments
Proxies to the appropriate Pod if session is on a different Pod
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

# URL patterns to extract session ID from
SESSION_URL_PATTERNS = [
    # /api/sessions/{session_id}
    re.compile(r'^/api/sessions/([a-f0-9-]{36})(?:/.*)?$'),
]

# Routes that require session routing
SESSION_ROUTES = [
    '/api/sessions/',  # GET, DELETE /api/sessions/{session_id}
]

# Routes excluded from session routing
EXCLUDED_ROUTES = [
    '/api/sessions',  # List view (including POST for session creation)
    '/health',
    '/redis/stats',
    '/',
]


class SessionRoutingMiddleware(BaseHTTPMiddleware):
    """
    Session-based request routing middleware

    Proxies to the Pod containing the session if not on current Pod
    """

    def __init__(self, app: ASGIApp, redis_client: Optional[RedisClient] = None):
        super().__init__(app)
        self._redis: Optional[RedisClient] = redis_client

    def set_redis_client(self, redis_client: RedisClient):
        """Set Redis client (lazy injection)"""
        self._redis = redis_client

    @property
    def redis(self) -> Optional[RedisClient]:
        """Return Redis client"""
        if self._redis is None:
            from service.redis.redis_client import get_redis_client
            try:
                self._redis = get_redis_client()
            except Exception:
                pass
        return self._redis

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request

        1. If already proxied, process directly
        2. Check if route needs session routing
        3. Proxy if session is on different Pod
        4. Process locally if on current Pod
        """
        path = request.url.path
        method = request.method

        logger.debug(f"🔍 [SessionRouter] Incoming request: {method} {path}")

        # If already proxied, process directly
        if request.headers.get(PROXY_HEADER) == "true":
            source_pod = request.headers.get("X-Claude-Control-Source-Pod", "unknown")
            logger.debug(f"📥 Handling proxied request from {source_pod}: {path}")
            return await call_next(request)

        # Check excluded routes
        if self._is_excluded_route(path):
            return await call_next(request)

        # Check if route needs session routing
        if not self._needs_session_routing(path):
            return await call_next(request)

        # Extract session ID
        session_id = await self._extract_session_id(request)

        logger.info(f"🔍 [SessionRouter] Session ID extracted: {session_id}")

        if not session_id:
            # No session ID, process locally
            logger.debug(f"🔍 [SessionRouter] No session_id, processing locally")
            return await call_next(request)

        # Check session's Pod info from Redis
        routing_result = self._get_session_pod_info(session_id)

        logger.debug(f"🔍 [SessionRouter] Routing result: {routing_result}")

        if routing_result is None:
            # No session info, process locally (expect 404)
            logger.warning(f"Session not found in Redis: {session_id}")
            return await call_next(request)

        target_pod_name, target_pod_ip = routing_result

        # Check if same as current Pod
        pod_info = get_pod_info()

        logger.debug(f"🔍 [SessionRouter] Target: {target_pod_name}@{target_pod_ip}, Current: {pod_info.pod_name}@{pod_info.pod_ip}")

        if target_pod_name == pod_info.pod_name or target_pod_ip == pod_info.pod_ip:
            # Process on current Pod
            logger.info(f"📍 Session {session_id[:8]}... is on this pod, processing locally")
            return await call_next(request)

        # Proxy to different Pod
        logger.info(f"🔀 Session {session_id[:8]}... is on {target_pod_name} ({target_pod_ip}), proxying...")

        proxy = get_internal_proxy()
        return await proxy.proxy_request(
            target_pod_ip=target_pod_ip,
            target_port=pod_info.service_port,
            request=request,
            source_pod_name=pod_info.pod_name
        )

    def _is_excluded_route(self, path: str) -> bool:
        """Check if route should be excluded"""
        # Exact match
        if path in EXCLUDED_ROUTES:
            return True

        # Session list view (exactly /api/sessions)
        if path == '/api/sessions':
            return True

        return False

    def _needs_session_routing(self, path: str) -> bool:
        """Check if route needs session routing"""
        for route in SESSION_ROUTES:
            if path.startswith(route):
                return True
        return False

    async def _extract_session_id(self, request: Request) -> Optional[str]:
        """
        Extract session ID from request

        Extracts session ID from URL path
        """
        path = request.url.path

        # Extract from URL pattern
        for pattern in SESSION_URL_PATTERNS:
            match = pattern.match(path)
            if match:
                return match.group(1)

        return None

    def _get_session_pod_info(self, session_id: str) -> Optional[tuple]:
        """
        Get session's Pod info from Redis

        Returns:
            (pod_name, pod_ip) or None
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
