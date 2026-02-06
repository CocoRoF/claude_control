"""
Claude Session Manager

Uses Redis as the true source for multi-pod environment support.
Local processes are managed in memory, session metadata is stored in Redis.
"""
import logging
import uuid
from typing import Dict, Optional, List

from service.claude_manager.process_manager import ClaudeProcess
from service.claude_manager.models import (
    SessionStatus,
    SessionInfo,
    CreateSessionRequest,
    MCPConfig
)
from service.redis.redis_client import RedisClient, get_redis_client
from service.pod.pod_info import get_pod_info
from service.logging.session_logger import get_session_logger, remove_session_logger

logger = logging.getLogger(__name__)


def merge_mcp_configs(base: Optional[MCPConfig], override: Optional[MCPConfig]) -> Optional[MCPConfig]:
    """
    Merge two MCP configurations (override takes priority).
    """
    if not base and not override:
        return None
    if not base:
        return override
    if not override:
        return base

    merged_servers = {**base.servers, **override.servers}
    return MCPConfig(servers=merged_servers)


class SessionManager:
    """
    Claude Session Manager.

    - Redis: True source for session metadata (multi-pod sharing)
    - Local memory: Manages processes running on current pod
    - Global MCP: MCP configuration automatically applied to all sessions
    """

    def __init__(self, redis_client: Optional[RedisClient] = None):
        # Local process storage (only processes running on current pod)
        self._local_processes: Dict[str, ClaudeProcess] = {}

        # Redis client (for session metadata storage)
        self._redis: Optional[RedisClient] = redis_client

        # Global MCP configuration (automatically applied to all sessions)
        self._global_mcp_config: Optional[MCPConfig] = None

    def set_redis_client(self, redis_client: RedisClient):
        """Set Redis client (lazy injection)."""
        self._redis = redis_client
        logger.info("✅ Redis client connected to SessionManager")

    def set_global_mcp_config(self, config: MCPConfig):
        """Set global MCP configuration (automatically applied to all sessions)."""
        self._global_mcp_config = config
        if config and config.servers:
            logger.info(f"✅ Global MCP config registered: {list(config.servers.keys())}")

    @property
    def global_mcp_config(self) -> Optional[MCPConfig]:
        """Return global MCP configuration."""
        return self._global_mcp_config

    @property
    def redis(self) -> Optional[RedisClient]:
        """Return Redis client (try to get from singleton if not set)."""
        if self._redis is None:
            try:
                self._redis = get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
        return self._redis

    @property
    def sessions(self) -> Dict[str, ClaudeProcess]:
        """Sessions property for compatibility (returns local processes)."""
        return self._local_processes

    async def create_session(self, request: CreateSessionRequest) -> SessionInfo:
        """
        Create a new Claude session.

        Args:
            request: Session creation request.

        Returns:
            Created session information.
        """
        session_id = str(uuid.uuid4())

        logger.info(f"[{session_id}] Creating new Claude session...")
        logger.info(f"[{session_id}]   session_name: {request.session_name}")
        logger.info(f"[{session_id}]   working_dir: {request.working_dir}")
        logger.info(f"[{session_id}]   model: {request.model}")

        # Merge global MCP config with session MCP config
        # Session config takes priority over global config
        merged_mcp_config = merge_mcp_configs(self._global_mcp_config, request.mcp_config)

        if merged_mcp_config and merged_mcp_config.servers:
            logger.info(f"[{session_id}]   mcp_servers: {list(merged_mcp_config.servers.keys())}")

        # Create ClaudeProcess instance
        process = ClaudeProcess(
            session_id=session_id,
            session_name=request.session_name,
            working_dir=request.working_dir,
            env_vars=request.env_vars,
            model=request.model,
            max_turns=request.max_turns,
            mcp_config=merged_mcp_config  # Use merged MCP config
        )

        # Initialize session
        success = await process.initialize()

        if not success:
            raise RuntimeError(f"Failed to initialize session: {process.error_message}")

        # Store local process
        self._local_processes[session_id] = process

        # Get pod information
        pod_info = get_pod_info()

        # Create SessionInfo
        session_info = SessionInfo(
            session_id=session_id,
            session_name=process.session_name,
            status=process.status,
            created_at=process.created_at,
            pid=process.pid,
            error_message=process.error_message,
            model=process.model,
            storage_path=process.storage_path,
            pod_name=pod_info.pod_name,
            pod_ip=pod_info.pod_ip
        )

        # Save session metadata to Redis
        self._save_session_to_redis(session_id, session_info)

        # Create session logger
        session_logger = get_session_logger(session_id, request.session_name, create_if_missing=True)
        if session_logger:
            session_logger.log_session_event("created", {
                "model": request.model,
                "working_dir": request.working_dir,
                "max_turns": request.max_turns
            })
            logger.info(f"[{session_id}] 📝 Session logger created")

        logger.info(f"[{session_id}] ✅ Session created successfully")
        return session_info

    def get_process(self, session_id: str) -> Optional[ClaudeProcess]:
        """
        Get session process (local).

        Only returns processes running on local pod.
        Sessions on other pods can only be queried for metadata from Redis.
        """
        return self._local_processes.get(session_id)

    def get_session_info(self, session_id: str) -> Optional[SessionInfo]:
        """
        Get session metadata (Redis priority).

        Retrieves session info from Redis (supports multi-pod environment).
        """
        # First try Redis
        if self.redis and self.redis.is_connected:
            session_data = self.redis.get_session(session_id)
            if session_data:
                return self._dict_to_session_info(session_data)

        # If not in Redis, generate from local process
        process = self._local_processes.get(session_id)
        if process:
            return self._process_to_session_info(session_id, process)

        return None

    def list_sessions(self) -> List[SessionInfo]:
        """
        List all sessions.

        If Redis is available, queries Redis (all sessions across multi-pod).
        Otherwise returns only local processes.
        """
        sessions_info = []

        # Query all sessions from Redis (multi-pod environment)
        if self.redis and self.redis.is_connected:
            all_sessions = self.redis.get_all_sessions()

            for session_data in all_sessions:
                session_id = session_data.get('session_id')

                # Update status if local process exists
                local_process = self._local_processes.get(session_id)
                if local_process:
                    # Check and update process status
                    if not local_process.is_alive() and local_process.status == SessionStatus.RUNNING:
                        local_process.status = SessionStatus.STOPPED
                        session_data['status'] = SessionStatus.STOPPED.value
                        self.redis.update_session_field(session_id, 'status', SessionStatus.STOPPED.value)
                    else:
                        session_data['status'] = local_process.status.value
                        session_data['pid'] = local_process.pid

                sessions_info.append(self._dict_to_session_info(session_data))

            return sessions_info

        # Without Redis, return only local processes
        for session_id, process in self._local_processes.items():
            # Update process status
            if not process.is_alive() and process.status == SessionStatus.RUNNING:
                process.status = SessionStatus.STOPPED

            sessions_info.append(self._process_to_session_info(session_id, process))

        return sessions_info

    async def delete_session(self, session_id: str, cleanup_storage: bool = True) -> bool:
        """
        Delete session and terminate process.

        Args:
            session_id: Session ID to delete.
            cleanup_storage: Whether to also delete storage.

        Returns:
            Whether deletion was successful.
        """
        # Check local process
        process = self._local_processes.get(session_id)

        if process:
            logger.info(f"[{session_id}] Deleting session...")

            # Log session end event
            session_logger = get_session_logger(session_id, create_if_missing=False)
            if session_logger:
                session_logger.log_session_event("deleted")

            # Stop process
            await process.stop()

            # Cleanup storage
            if cleanup_storage:
                await process.cleanup_storage()

            # Remove session logger
            remove_session_logger(session_id)

            # Remove from local
            del self._local_processes[session_id]

        # Also delete from Redis
        if self.redis and self.redis.is_connected:
            self.redis.delete_session(session_id)
            logger.info(f"[{session_id}] Session deleted from Redis")
            return True

        # If only deleted from local (no Redis)
        return process is not None

    async def cleanup_dead_sessions(self):
        """Cleanup dead sessions (based on local processes)."""
        dead_sessions = [
            session_id
            for session_id, process in self._local_processes.items()
            if not process.is_alive()
        ]

        for session_id in dead_sessions:
            logger.info(f"[{session_id}] Cleaning up dead session")
            await self.delete_session(session_id)

    # ========== Helper Methods ==========

    def _save_session_to_redis(self, session_id: str, session_info: SessionInfo):
        """Save session information to Redis."""
        if not self.redis or not self.redis.is_connected:
            logger.warning(f"No Redis connection - session {session_id} stored locally only")
            return

        session_data = {
            'session_id': session_id,
            'session_name': session_info.session_name,
            'status': session_info.status.value if session_info.status else None,
            'created_at': session_info.created_at,
            'pid': session_info.pid,
            'error_message': session_info.error_message,
            'model': session_info.model,
            'storage_path': session_info.storage_path,
            'pod_name': session_info.pod_name,
            'pod_ip': session_info.pod_ip
        }

        self.redis.save_session(session_id, session_data)
        logger.debug(f"Session saved to Redis: {session_id}")

    def _process_to_session_info(self, session_id: str, process: ClaudeProcess) -> SessionInfo:
        """Convert ClaudeProcess to SessionInfo."""
        pod_info = get_pod_info()
        return SessionInfo(
            session_id=session_id,
            session_name=process.session_name,
            status=process.status,
            created_at=process.created_at,
            pid=process.pid,
            error_message=process.error_message,
            model=process.model,
            storage_path=process.storage_path,
            pod_name=pod_info.pod_name,
            pod_ip=pod_info.pod_ip
        )

    def _dict_to_session_info(self, data: dict) -> SessionInfo:
        """Convert dictionary to SessionInfo."""
        status = data.get('status')
        if isinstance(status, str):
            status = SessionStatus(status)

        return SessionInfo(
            session_id=data.get('session_id', ''),
            session_name=data.get('session_name'),
            status=status,
            created_at=data.get('created_at'),
            pid=data.get('pid'),
            error_message=data.get('error_message'),
            model=data.get('model'),
            storage_path=data.get('storage_path'),
            pod_name=data.get('pod_name'),
            pod_ip=data.get('pod_ip')
        )


# Singleton session manager
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """Return singleton session manager instance."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
