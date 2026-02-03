"""
Pod Information Manager

Kubernetes Pod 정보를 자동으로 감지하는 모듈
Multi-pod 환경에서 세션 라우팅을 위해 사용

환경변수 설정 없이도 자동으로 동작:
- Pod Name: hostname에서 자동 추출
- Pod IP: 네트워크 인터페이스에서 자동 감지
"""
import os
import socket
import logging
from typing import Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PodInfo:
    """Pod 정보"""
    pod_name: str
    pod_ip: str
    pod_namespace: str
    node_name: str
    service_port: int
    
    def get_internal_url(self, path: str = "") -> str:
        """내부 통신용 URL 생성"""
        return f"http://{self.pod_ip}:{self.service_port}{path}"
    
    def __str__(self) -> str:
        return f"Pod({self.pod_name}@{self.pod_ip}:{self.service_port})"


# 싱글톤 인스턴스
_pod_info: Optional[PodInfo] = None


def _get_all_local_ips() -> List[str]:
    """모든 로컬 IP 주소 가져오기"""
    ips = []
    try:
        # 모든 네트워크 인터페이스의 IP 가져오기
        hostname = socket.gethostname()
        ips = socket.gethostbyname_ex(hostname)[2]
        # 127.0.0.1 제외
        ips = [ip for ip in ips if not ip.startswith('127.')]
    except Exception:
        pass
    return ips


def _get_local_ip() -> str:
    """
    로컬 IP 주소 자동 감지
    
    여러 방법으로 시도:
    1. 외부 연결 시도로 기본 인터페이스 IP 확인
    2. hostname으로 IP 조회
    3. 모든 인터페이스에서 non-localhost IP 찾기
    """
    # 방법 1: UDP 소켓으로 외부 연결 시도 (실제로 패킷을 보내지 않음)
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.1)
        # 실제로 연결하지 않고 로컬 IP만 확인
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    
    # 방법 2: hostname으로 IP 조회
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        if ip and not ip.startswith('127.'):
            return ip
    except Exception:
        pass
    
    # 방법 3: 모든 인터페이스에서 찾기
    ips = _get_all_local_ips()
    if ips:
        return ips[0]
    
    # 최후의 수단
    return "127.0.0.1"


def _get_pod_name() -> str:
    """
    Pod 이름 자동 감지
    
    Kubernetes에서 hostname은 Pod 이름과 동일
    """
    # 환경변수 우선 (설정되어 있다면)
    if os.getenv('POD_NAME'):
        return os.getenv('POD_NAME')
    
    if os.getenv('HOSTNAME'):
        return os.getenv('HOSTNAME')
    
    # hostname 사용 (Kubernetes에서는 Pod 이름)
    try:
        return socket.gethostname()
    except Exception:
        pass
    
    # fallback
    import uuid
    return f"mcp-station-{uuid.uuid4().hex[:8]}"


def _get_namespace() -> str:
    """
    Kubernetes 네임스페이스 자동 감지
    
    ServiceAccount 마운트 경로에서 읽기
    """
    # 환경변수 우선
    if os.getenv('POD_NAMESPACE'):
        return os.getenv('POD_NAMESPACE')
    
    # Kubernetes ServiceAccount 마운트에서 읽기
    namespace_file = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    try:
        if os.path.exists(namespace_file):
            with open(namespace_file, 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    
    return 'default'


def init_pod_info(
    pod_name: Optional[str] = None,
    pod_ip: Optional[str] = None,
    pod_namespace: Optional[str] = None,
    node_name: Optional[str] = None,
    service_port: Optional[int] = None
) -> PodInfo:
    """
    Pod 정보 자동 초기화
    
    환경변수 설정 없이도 자동으로 감지:
    - pod_name: hostname (Kubernetes에서는 Pod 이름)
    - pod_ip: 네트워크 인터페이스에서 자동 감지
    - pod_namespace: ServiceAccount 마운트에서 읽기
    
    Args:
        pod_name: Pod 이름 (미지정 시 자동 감지)
        pod_ip: Pod IP (미지정 시 자동 감지)
        pod_namespace: 네임스페이스 (미지정 시 자동 감지)
        node_name: 노드 이름
        service_port: 서비스 포트 (기본값: APP_PORT 또는 8000)
    
    Returns:
        PodInfo 인스턴스
    """
    global _pod_info
    
    detected_name = pod_name or _get_pod_name()
    detected_ip = pod_ip or os.getenv('POD_IP') or _get_local_ip()
    detected_namespace = pod_namespace or _get_namespace()
    detected_port = service_port or int(os.getenv('APP_PORT', '8000'))
    
    _pod_info = PodInfo(
        pod_name=detected_name,
        pod_ip=detected_ip,
        pod_namespace=detected_namespace,
        node_name=node_name or os.getenv('NODE_NAME', 'unknown'),
        service_port=detected_port
    )
    
    logger.info(f"✅ Pod 정보 자동 감지 완료: {_pod_info}")
    logger.info(f"   - Name: {detected_name} (자동 감지)")
    logger.info(f"   - IP: {detected_ip} (자동 감지)")
    logger.info(f"   - Namespace: {detected_namespace}")
    logger.info(f"   - Port: {detected_port}")
    
    return _pod_info


def get_pod_info() -> PodInfo:
    """
    Pod 정보 가져오기 (싱글톤)
    
    초기화되지 않은 경우 자동 초기화
    """
    global _pod_info
    
    if _pod_info is None:
        _pod_info = init_pod_info()
    
    return _pod_info


def is_same_pod(target_pod_name: str) -> bool:
    """현재 Pod와 같은 Pod인지 확인"""
    pod_info = get_pod_info()
    return pod_info.pod_name == target_pod_name


def is_same_pod_ip(target_pod_ip: str) -> bool:
    """현재 Pod IP와 같은지 확인"""
    pod_info = get_pod_info()
    return pod_info.pod_ip == target_pod_ip
