"""
MCP 서버 세션 관리

Redis를 true source로 사용하여 multi-pod 환경 지원
로컬 프로세스는 메모리에서 관리하고, 세션 메타데이터는 Redis에 저장
"""
import logging
import uuid
from typing import Dict, Optional, List
from service.mcp_manager.process_manager import MCPProcess
from service.mcp_manager.models import (
    MCPServerStatus,
    SessionInfo,
    CreateSessionRequest
)
from service.redis.redis_client import RedisClient, get_redis_client
from service.pod.pod_info import get_pod_info, is_same_pod

logger = logging.getLogger(__name__)

class SessionManager:
    """
    MCP 서버 세션 관리자
    
    - Redis: 세션 메타데이터의 true source (multi-pod 공유)
    - 로컬 메모리: 현재 pod에서 실행 중인 프로세스 관리
    """

    def __init__(self, redis_client: Optional[RedisClient] = None):
        # 로컬 프로세스 저장 (현재 pod에서 실행 중인 프로세스만)
        self._local_processes: Dict[str, MCPProcess] = {}
        
        # Redis 클라이언트 (세션 메타데이터 저장용)
        self._redis: Optional[RedisClient] = redis_client
    
    def set_redis_client(self, redis_client: RedisClient):
        """Redis 클라이언트 설정 (지연 주입)"""
        self._redis = redis_client
        logger.info("✅ SessionManager에 Redis 클라이언트 연결됨")
    
    @property
    def redis(self) -> Optional[RedisClient]:
        """Redis 클라이언트 반환 (없으면 싱글톤에서 가져오기 시도)"""
        if self._redis is None:
            try:
                self._redis = get_redis_client()
            except Exception as e:
                logger.warning(f"Redis 클라이언트를 가져올 수 없음: {e}")
        return self._redis
    
    @property
    def sessions(self) -> Dict[str, MCPProcess]:
        """호환성을 위한 sessions 프로퍼티 (로컬 프로세스 반환)"""
        return self._local_processes

    async def create_session(self, request: CreateSessionRequest) -> SessionInfo:
        """
        새로운 MCP 서버 세션 생성
        """
        session_id = str(uuid.uuid4())

        logger.info(f"Creating new session {session_id} for {request.server_type}")
        logger.info(f"[{session_id}] Request details:")
        logger.info(f"[{session_id}]   server_command: {request.server_command}")
        logger.info(f"[{session_id}]   server_args: {request.server_args}")
        logger.info(f"[{session_id}]   env_vars: {request.env_vars}")
        logger.info(f"[{session_id}]   working_dir: {request.working_dir}")
        logger.info(f"[{session_id}]   session_name: {request.session_name}")
        logger.info(f"[{session_id}]   additional_commands: {request.additional_commands}")

        # MCPProcess 인스턴스 생성
        process = MCPProcess(
            session_id=session_id,
            server_type=request.server_type,
            command=request.server_command,
            args=request.server_args,
            env_vars=request.env_vars,
            working_dir=request.working_dir,
            session_name=request.session_name,
            additional_commands=request.additional_commands
        )

        # 프로세스 시작
        success = await process.start()

        if not success:
            raise RuntimeError(f"Failed to start MCP server: {process.error_message}")

        # 로컬 프로세스 저장
        self._local_processes[session_id] = process
        
        # Pod 정보 가져오기
        pod_info = get_pod_info()
        
        # Redis에 세션 메타데이터 저장 (Pod 정보 포함)
        session_info = SessionInfo(
            session_id=session_id,
            session_name=process.session_name,
            server_type=request.server_type,
            status=process.status,
            created_at=process.created_at,
            pid=process.pid,
            error_message=process.error_message,
            server_command=process.command,
            server_args=process.args,
            additional_commands=process.additional_commands,
            mcp_initialized=getattr(process, '_initialized', False),
            pod_name=pod_info.pod_name,
            pod_ip=pod_info.pod_ip
        )
        
        self._save_session_to_redis(session_id, session_info, process)

        return session_info

    def get_session(self, session_id: str) -> Optional[MCPProcess]:
        """
        세션 조회 (로컬 프로세스)
        
        로컬 pod에서 실행 중인 프로세스만 반환
        다른 pod의 세션은 Redis에서 메타데이터만 조회 가능
        """
        return self._local_processes.get(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """
        세션 메타데이터 조회 (Redis 우선)
        
        Redis에서 세션 정보를 가져옴 (multi-pod 환경 지원)
        """
        # 먼저 Redis에서 조회
        if self.redis and self.redis.is_connected:
            session_data = self.redis.get_session(session_id)
            if session_data:
                return self._dict_to_session_info(session_data)
        
        # Redis에 없으면 로컬 프로세스에서 생성
        process = self._local_processes.get(session_id)
        if process:
            return self._process_to_session_info(session_id, process)
        
        return None

    def list_sessions(self) -> List[SessionInfo]:
        """
        모든 세션 목록 조회
        
        Redis가 사용 가능하면 Redis에서 조회 (multi-pod 전체 세션)
        아니면 로컬 프로세스만 반환
        """
        sessions_info = []
        
        # Redis에서 모든 세션 조회 (multi-pod 환경)
        if self.redis and self.redis.is_connected:
            all_sessions = self.redis.get_all_sessions()
            
            for session_data in all_sessions:
                session_id = session_data.get('session_id')
                
                # 로컬 프로세스가 있으면 상태 업데이트
                local_process = self._local_processes.get(session_id)
                if local_process:
                    # 프로세스 상태 체크 및 업데이트
                    if not local_process.is_alive() and local_process.status == MCPServerStatus.RUNNING:
                        local_process.status = MCPServerStatus.STOPPED
                        session_data['status'] = MCPServerStatus.STOPPED.value
                        self.redis.update_session_field(session_id, 'status', MCPServerStatus.STOPPED.value)
                    else:
                        session_data['status'] = local_process.status.value
                        session_data['pid'] = local_process.pid
                
                sessions_info.append(self._dict_to_session_info(session_data))
            
            return sessions_info
        
        # Redis 없으면 로컬 프로세스만 반환
        for session_id, process in self._local_processes.items():
            # 프로세스 상태 업데이트
            if not process.is_alive() and process.status == MCPServerStatus.RUNNING:
                process.status = MCPServerStatus.STOPPED

            sessions_info.append(self._process_to_session_info(session_id, process))

        return sessions_info

    async def delete_session(self, session_id: str) -> bool:
        """세션 삭제 및 프로세스 종료"""
        # 로컬 프로세스 확인
        process = self._local_processes.get(session_id)

        if process:
            logger.info(f"Deleting local session {session_id}")
            # 프로세스 중지
            await process.stop()
            # 로컬에서 제거
            del self._local_processes[session_id]
        
        # Redis에서도 삭제
        if self.redis and self.redis.is_connected:
            self.redis.delete_session(session_id)
            logger.info(f"Deleted session from Redis: {session_id}")
            return True
        
        # Redis 없이 로컬만 삭제한 경우
        return process is not None

    async def cleanup_dead_sessions(self):
        """죽은 세션 정리 (로컬 프로세스 기준)"""
        dead_sessions = [
            session_id
            for session_id, process in self._local_processes.items()
            if not process.is_alive()
        ]

        for session_id in dead_sessions:
            logger.info(f"Cleaning up dead session {session_id}")
            await self.delete_session(session_id)
    
    # ========== 헬퍼 메서드 ==========
    
    def _save_session_to_redis(self, session_id: str, session_info: SessionInfo, process: MCPProcess):
        """세션 정보를 Redis에 저장"""
        if not self.redis or not self.redis.is_connected:
            logger.warning(f"Redis 연결 없음 - 세션 {session_id}는 로컬에만 저장됨")
            return
        
        session_data = {
            'session_id': session_id,
            'session_name': session_info.session_name,
            'server_type': session_info.server_type.value if session_info.server_type else None,
            'status': session_info.status.value if session_info.status else None,
            'created_at': session_info.created_at,
            'pid': session_info.pid,
            'error_message': session_info.error_message,
            'server_command': session_info.server_command,
            'server_args': session_info.server_args,
            'additional_commands': session_info.additional_commands,
            'mcp_initialized': session_info.mcp_initialized,
            'pod_name': session_info.pod_name,
            'pod_ip': session_info.pod_ip
        }
        
        self.redis.save_session(session_id, session_data)
        logger.debug(f"세션 Redis 저장 완료: {session_id}")
    
    def _process_to_session_info(self, session_id: str, process: MCPProcess) -> SessionInfo:
        """MCPProcess를 SessionInfo로 변환"""
        pod_info = get_pod_info()
        return SessionInfo(
            session_id=session_id,
            session_name=process.session_name,
            server_type=process.server_type,
            status=process.status,
            created_at=process.created_at,
            pid=process.pid,
            error_message=process.error_message,
            server_command=process.command,
            server_args=process.args,
            additional_commands=process.additional_commands,
            mcp_initialized=getattr(process, '_initialized', False),
            pod_name=pod_info.pod_name,
            pod_ip=pod_info.pod_ip
        )
    
    def _dict_to_session_info(self, data: dict) -> SessionInfo:
        """딕셔너리를 SessionInfo로 변환"""
        from service.mcp_manager.models import MCPServerType
        
        server_type = data.get('server_type')
        if isinstance(server_type, str):
            server_type = MCPServerType(server_type)
        
        status = data.get('status')
        if isinstance(status, str):
            status = MCPServerStatus(status)
        
        return SessionInfo(
            session_id=data.get('session_id', ''),
            session_name=data.get('session_name'),
            server_type=server_type,
            status=status,
            created_at=data.get('created_at'),
            pid=data.get('pid'),
            error_message=data.get('error_message'),
            server_command=data.get('server_command'),
            server_args=data.get('server_args'),
            additional_commands=data.get('additional_commands'),
            mcp_initialized=data.get('mcp_initialized', False),
            pod_name=data.get('pod_name'),
            pod_ip=data.get('pod_ip')
        )
