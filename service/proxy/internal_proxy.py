"""
Internal Proxy Client

Multi-pod 환경에서 다른 Pod로 요청을 전달하는 프록시 클라이언트
"""
import logging
from typing import Optional, Dict, Any, Tuple
import httpx
from fastapi import Request, Response

logger = logging.getLogger(__name__)

# 프록시 요청 타임아웃 (초)
PROXY_TIMEOUT = 60.0

# 프록시 헤더 (무한 루프 방지)
PROXY_HEADER = "X-Claude-Control-Proxied"
PROXY_SOURCE_HEADER = "X-Claude-Control-Source-Pod"


class InternalProxy:
    """
    내부 Pod 간 프록시 클라이언트
    
    세션이 다른 Pod에 있을 경우 해당 Pod로 요청을 전달
    """
    
    _instance: Optional['InternalProxy'] = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, timeout: float = PROXY_TIMEOUT):
        if hasattr(self, '_initialized') and self._initialized:
            return
            
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._initialized = True
        
        logger.info("✅ Internal Proxy 초기화 완료")
    
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 가져오기 (lazy initialization)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                follow_redirects=True
            )
        return self._client
    
    async def close(self):
        """클라이언트 종료"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
    
    def is_proxied_request(self, request: Request) -> bool:
        """
        이미 프록시된 요청인지 확인 (무한 루프 방지)
        """
        return request.headers.get(PROXY_HEADER) == "true"
    
    async def proxy_request(
        self,
        target_pod_ip: str,
        target_port: int,
        request: Request,
        source_pod_name: str
    ) -> Response:
        """
        요청을 다른 Pod로 프록시
        
        Args:
            target_pod_ip: 대상 Pod의 IP 주소
            target_port: 대상 Pod의 포트
            request: 원본 FastAPI Request
            source_pod_name: 현재 Pod 이름 (로깅용)
            
        Returns:
            프록시된 응답
        """
        client = await self._get_client()
        
        # 대상 URL 구성
        target_url = f"http://{target_pod_ip}:{target_port}{request.url.path}"
        if request.url.query:
            target_url += f"?{request.url.query}"
        
        logger.info(f"🔀 Proxying request: {request.method} {request.url.path} -> {target_pod_ip}:{target_port}")
        
        # 헤더 복사 및 프록시 헤더 추가
        headers = dict(request.headers)
        headers[PROXY_HEADER] = "true"
        headers[PROXY_SOURCE_HEADER] = source_pod_name
        
        # host 헤더 제거 (대상 서버에 맞게 설정되도록)
        headers.pop("host", None)
        
        try:
            # 요청 본문 읽기
            body = await request.body()
            
            # 프록시 요청 전송
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body
            )
            
            logger.info(f"✅ Proxy response: {response.status_code}")
            
            # FastAPI Response로 변환
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type")
            )
            
        except httpx.TimeoutException:
            logger.error(f"❌ Proxy timeout: {target_url}")
            return Response(
                content='{"error": "Proxy timeout"}',
                status_code=504,
                media_type="application/json"
            )
            
        except httpx.ConnectError as e:
            logger.error(f"❌ Proxy connection error: {target_url} - {e}")
            return Response(
                content='{"error": "Target pod unreachable"}',
                status_code=502,
                media_type="application/json"
            )
            
        except Exception as e:
            logger.error(f"❌ Proxy error: {e}", exc_info=True)
            return Response(
                content=f'{{"error": "Proxy error: {str(e)}"}}',
                status_code=500,
                media_type="application/json"
            )
    
    async def check_pod_health(self, pod_ip: str, port: int) -> bool:
        """
        대상 Pod의 상태 확인
        
        Args:
            pod_ip: Pod IP
            port: 포트
            
        Returns:
            Pod가 살아있는지 여부
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"http://{pod_ip}:{port}/health",
                timeout=5.0
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Pod health check failed: {pod_ip}:{port} - {e}")
            return False


# 싱글톤 인스턴스
_proxy: Optional[InternalProxy] = None


def get_internal_proxy() -> InternalProxy:
    """Internal Proxy 싱글톤 인스턴스 반환"""
    global _proxy
    if _proxy is None:
        _proxy = InternalProxy()
    return _proxy
