"""
Claude Code 프로세스 관리

claude CLI를 프로세스로 실행하고 관리합니다.
각 세션은 독립적인 프로세스와 스토리지를 가집니다.
"""
import asyncio
import json
import logging
import os
import signal
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from datetime import datetime

from service.claude_manager.models import SessionStatus, MCPConfig
from service.utils.utils import now_kst

if TYPE_CHECKING:
    from service.claude_manager.models import MCPConfig

logger = logging.getLogger(__name__)

# 버퍼 제한: 16MB
STDIO_BUFFER_LIMIT = 16 * 1024 * 1024

# Claude 실행 타임아웃 (기본 5분)
CLAUDE_DEFAULT_TIMEOUT = 300.0

# 기본 스토리지 루트 경로
DEFAULT_STORAGE_ROOT = os.environ.get('CLAUDE_STORAGE_ROOT', '/tmp/claude_sessions')

# Claude Code 관련 환경 변수 키 목록 (이 변수들은 자동으로 세션에 전달됨)
CLAUDE_ENV_KEYS = [
    # Anthropic API
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_AUTH_TOKEN',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL',
    'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL',
    
    # Claude Code 설정
    'MAX_THINKING_TOKENS',
    'BASH_DEFAULT_TIMEOUT_MS',
    'BASH_MAX_TIMEOUT_MS',
    'BASH_MAX_OUTPUT_LENGTH',
    
    # 비활성화 옵션
    'DISABLE_AUTOUPDATER',
    'DISABLE_ERROR_REPORTING',
    'DISABLE_TELEMETRY',
    'DISABLE_COST_WARNINGS',
    'DISABLE_PROMPT_CACHING',
    
    # 프록시
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'NO_PROXY',
    
    # AWS Bedrock
    'CLAUDE_CODE_USE_BEDROCK',
    'AWS_REGION',
    'AWS_ACCESS_KEY_ID',
    'AWS_SECRET_ACCESS_KEY',
    'AWS_BEARER_TOKEN_BEDROCK',
    
    # Google Vertex AI
    'CLAUDE_CODE_USE_VERTEX',
    'GOOGLE_CLOUD_PROJECT',
    'GOOGLE_CLOUD_REGION',
    
    # Microsoft Foundry
    'CLAUDE_CODE_USE_FOUNDRY',
    'ANTHROPIC_FOUNDRY_API_KEY',
    'ANTHROPIC_FOUNDRY_BASE_URL',
    'ANTHROPIC_FOUNDRY_RESOURCE',
]


def get_claude_env_vars() -> Dict[str, str]:
    """
    Claude Code 실행에 필요한 환경 변수 수집
    
    Returns:
        Claude Code에 전달할 환경 변수 딕셔너리
    """
    env_vars = {}
    for key in CLAUDE_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env_vars[key] = value
    return env_vars


class ClaudeProcess:
    """
    개별 Claude Code 프로세스
    
    claude CLI를 실행하고 관리합니다.
    각 인스턴스는 고유한 세션 ID와 스토리지 경로를 가집니다.
    """

    def __init__(
        self,
        session_id: str,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        model: Optional[str] = None,
        max_turns: Optional[int] = None,
        storage_root: Optional[str] = None,
        mcp_config: Optional[MCPConfig] = None
    ):
        self.session_id = session_id
        self.session_name = session_name
        self.model = model
        self.max_turns = max_turns
        self.env_vars = env_vars or {}
        self.mcp_config = mcp_config
        
        # 스토리지 설정
        self._storage_root = storage_root or DEFAULT_STORAGE_ROOT
        self._storage_path = os.path.join(self._storage_root, session_id)
        
        # working_dir이 지정되지 않으면 스토리지 경로 사용
        self.working_dir = working_dir or self._storage_path
        
        # 프로세스 상태
        self.process: Optional[asyncio.subprocess.Process] = None
        self.status = SessionStatus.STOPPED
        self.error_message: Optional[str] = None
        self.created_at = now_kst()
        
        # 현재 실행 중인 프로세스 (execute 명령용)
        self._current_process: Optional[asyncio.subprocess.Process] = None
        self._execution_lock = asyncio.Lock()

    @property
    def storage_path(self) -> str:
        """세션 전용 스토리지 경로"""
        return self._storage_path
    
    @property
    def pid(self) -> Optional[int]:
        """현재 실행 중인 프로세스 ID"""
        if self._current_process:
            return self._current_process.pid
        return None

    async def initialize(self) -> bool:
        """
        세션 초기화
        
        스토리지 디렉토리를 생성하고 세션을 준비합니다.
        MCP 설정이 있으면 .mcp.json 파일을 생성합니다.
        """
        try:
            self.status = SessionStatus.STARTING
            logger.info(f"[{self.session_id}] Initializing Claude session...")
            
            # 스토리지 디렉토리 생성
            os.makedirs(self._storage_path, exist_ok=True)
            logger.info(f"[{self.session_id}] Storage created: {self._storage_path}")
            
            # working_dir도 생성 (다른 경로인 경우)
            if self.working_dir != self._storage_path:
                os.makedirs(self.working_dir, exist_ok=True)
            
            # MCP 설정 파일 생성 (.mcp.json)
            if self.mcp_config and self.mcp_config.servers:
                await self._create_mcp_config()
            
            # claude CLI 확인 (Claude Code)
            claude_path = shutil.which("claude")
            if claude_path is None:
                raise FileNotFoundError("Claude Code가 설치되어 있지 않습니다. 'npm install -g @anthropic-ai/claude-code'로 설치하세요.")
            
            logger.info(f"[{self.session_id}] Found claude CLI at: {claude_path}")
            
            self.status = SessionStatus.RUNNING
            logger.info(f"[{self.session_id}] ✅ Session initialized successfully")
            return True
            
        except Exception as e:
            self.status = SessionStatus.ERROR
            self.error_message = str(e)
            logger.error(f"[{self.session_id}] Failed to initialize session: {e}")
            return False
    
    async def _create_mcp_config(self) -> None:
        """
        .mcp.json 파일 생성
        
        세션의 working_dir에 MCP 설정 파일을 생성합니다.
        Claude Code가 이 파일을 자동으로 읽어 MCP 서버에 연결합니다.
        """
        if not self.mcp_config:
            return
        
        mcp_json_path = os.path.join(self.working_dir, ".mcp.json")
        mcp_data = self.mcp_config.to_mcp_json()
        
        try:
            with open(mcp_json_path, 'w', encoding='utf-8') as f:
                json.dump(mcp_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"[{self.session_id}] 🔌 MCP config created: {mcp_json_path}")
            logger.info(f"[{self.session_id}] MCP servers: {list(self.mcp_config.servers.keys())}")
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to create MCP config: {e}")

    async def execute(
        self, 
        prompt: str, 
        timeout: float = CLAUDE_DEFAULT_TIMEOUT,
        skip_permissions: Optional[bool] = None,
        system_prompt: Optional[str] = None,
        max_turns: Optional[int] = None
    ) -> Dict:
        """
        Claude에게 프롬프트 실행
        
        Args:
            prompt: Claude에게 전달할 프롬프트
            timeout: 실행 타임아웃 (초)
            skip_permissions: 권한 프롬프트 건너뛰기 (None이면 환경변수 사용)
            system_prompt: 추가 시스템 프롬프트 (자율 모드 지침 등)
            max_turns: 이 실행의 최대 턴 수 (None이면 세션 설정 사용)
            
        Returns:
            실행 결과 딕셔너리 (success, output, error, cost_usd, duration_ms)
        """
        async with self._execution_lock:
            if self.status != SessionStatus.RUNNING:
                return {
                    "success": False,
                    "error": f"Session is not running (status: {self.status})"
                }
            
            start_time = datetime.now()
            
            try:
                # 환경 변수 준비 (시스템 환경 변수 + Claude 관련 환경 변수 + 사용자 지정 환경 변수)
                env = os.environ.copy()
                env.update(get_claude_env_vars())  # Claude Code 관련 환경 변수 자동 추가
                env.update(self.env_vars)  # 세션별 사용자 지정 환경 변수
                
                # claude 명령어 구성
                cmd = ["claude", "--print"]
                
                # 권한 프롬프트 건너뛰기 옵션 (자율 모드 필수)
                # 1. 함수 인자로 지정된 경우 우선
                # 2. 환경 변수 CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS 확인
                should_skip_permissions = skip_permissions
                if should_skip_permissions is None:
                    env_skip = os.environ.get('CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS', 'true').lower()
                    should_skip_permissions = env_skip in ('true', '1', 'yes', 'on')
                
                if should_skip_permissions:
                    cmd.append("--dangerously-skip-permissions")
                    logger.info(f"[{self.session_id}] 🤖 Autonomous mode: --dangerously-skip-permissions enabled")
                
                # 모델 지정
                if self.model:
                    cmd.extend(["--model", self.model])
                
                # 최대 턴 수 지정 (실행별 설정 > 세션 설정)
                effective_max_turns = max_turns or self.max_turns
                if effective_max_turns:
                    cmd.extend(["--max-turns", str(effective_max_turns)])
                
                # 시스템 프롬프트 추가 (자율 모드 지침)
                if system_prompt:
                    cmd.extend(["--append-system-prompt", system_prompt])
                    logger.info(f"[{self.session_id}] 📝 Custom system prompt applied")
                
                # 프롬프트 추가
                cmd.extend(["-p", prompt])
                
                logger.info(f"[{self.session_id}] Executing: {' '.join(cmd[:5])}...")  # 보안을 위해 일부만 로깅
                
                # 프로세스 실행
                self._current_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    limit=STDIO_BUFFER_LIMIT
                )
                
                # 출력 수집
                try:
                    stdout, stderr = await asyncio.wait_for(
                        self._current_process.communicate(),
                        timeout=timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[{self.session_id}] Execution timed out after {timeout}s")
                    await self._kill_current_process()
                    return {
                        "success": False,
                        "error": f"Execution timed out after {timeout} seconds"
                    }
                
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                stdout_text = stdout.decode('utf-8', errors='replace') if stdout else ""
                stderr_text = stderr.decode('utf-8', errors='replace') if stderr else ""
                
                if self._current_process.returncode == 0:
                    logger.info(f"[{self.session_id}] ✅ Execution completed in {duration_ms}ms")
                    return {
                        "success": True,
                        "output": stdout_text,
                        "duration_ms": duration_ms
                    }
                else:
                    logger.error(f"[{self.session_id}] ❌ Execution failed: {stderr_text}")
                    return {
                        "success": False,
                        "output": stdout_text,
                        "error": stderr_text or f"Process exited with code {self._current_process.returncode}",
                        "duration_ms": duration_ms
                    }
                    
            except Exception as e:
                logger.error(f"[{self.session_id}] Execution error: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
            finally:
                self._current_process = None
    
    async def _kill_current_process(self):
        """현재 실행 중인 프로세스 강제 종료"""
        if self._current_process:
            try:
                self._current_process.kill()
                await self._current_process.wait()
            except Exception as e:
                logger.warning(f"[{self.session_id}] Failed to kill process: {e}")

    def list_storage_files(self, subpath: str = "") -> List[Dict]:
        """
        스토리지 파일 목록 조회
        
        Args:
            subpath: 하위 경로 (빈 문자열이면 루트)
            
        Returns:
            파일 정보 리스트
        """
        target_path = Path(self._storage_path)
        if subpath:
            target_path = target_path / subpath
        
        if not target_path.exists():
            return []
        
        files = []
        try:
            for item in target_path.iterdir():
                stat = item.stat()
                files.append({
                    "name": item.name,
                    "path": str(item.relative_to(self._storage_path)),
                    "is_dir": item.is_dir(),
                    "size": stat.st_size if item.is_file() else None,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime)
                })
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to list files: {e}")
        
        return files
    
    def read_storage_file(self, file_path: str, encoding: str = "utf-8") -> Optional[Dict]:
        """
        스토리지 파일 내용 읽기
        
        Args:
            file_path: 파일 경로 (스토리지 루트 기준 상대 경로)
            encoding: 파일 인코딩
            
        Returns:
            파일 내용 딕셔너리 또는 None
        """
        target_path = Path(self._storage_path) / file_path
        
        # 경로 검증 (디렉토리 트래버설 방지)
        try:
            target_path.resolve().relative_to(Path(self._storage_path).resolve())
        except ValueError:
            logger.warning(f"[{self.session_id}] Invalid file path: {file_path}")
            return None
        
        if not target_path.exists() or not target_path.is_file():
            return None
        
        try:
            content = target_path.read_text(encoding=encoding)
            return {
                "file_path": file_path,
                "content": content,
                "size": len(content),
                "encoding": encoding
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to read file: {e}")
            return None

    async def stop(self):
        """세션 중지 및 정리"""
        try:
            logger.info(f"[{self.session_id}] Stopping session...")
            
            # 현재 실행 중인 프로세스 종료
            await self._kill_current_process()
            
            self.status = SessionStatus.STOPPED
            logger.info(f"[{self.session_id}] Session stopped")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] Error stopping session: {e}")
            self.status = SessionStatus.STOPPED
    
    async def cleanup_storage(self):
        """스토리지 디렉토리 삭제"""
        try:
            if os.path.exists(self._storage_path):
                shutil.rmtree(self._storage_path)
                logger.info(f"[{self.session_id}] Storage cleaned up: {self._storage_path}")
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to cleanup storage: {e}")

    def is_alive(self) -> bool:
        """세션이 활성 상태인지 확인"""
        return self.status == SessionStatus.RUNNING
