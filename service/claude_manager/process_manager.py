"""
Claude Code 프로세스 관리

claude CLI를 프로세스로 실행하고 관리합니다.
각 세션은 독립적인 프로세스와 스토리지를 가집니다.
"""
import asyncio
import logging
import os
import signal
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, List
from datetime import datetime

from service.claude_manager.models import SessionStatus
from service.utils.utils import now_kst

logger = logging.getLogger(__name__)

# 버퍼 제한: 16MB
STDIO_BUFFER_LIMIT = 16 * 1024 * 1024

# Claude 실행 타임아웃 (기본 5분)
CLAUDE_DEFAULT_TIMEOUT = 300.0

# 기본 스토리지 루트 경로
DEFAULT_STORAGE_ROOT = os.environ.get('CLAUDE_STORAGE_ROOT', '/tmp/claude_sessions')


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
        storage_root: Optional[str] = None
    ):
        self.session_id = session_id
        self.session_name = session_name
        self.model = model
        self.max_turns = max_turns
        self.env_vars = env_vars or {}
        
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
            
            # claude CLI 확인
            claude_path = shutil.which("claude")
            if claude_path is None:
                raise FileNotFoundError("claude CLI가 설치되어 있지 않습니다. 'npm install -g @anthropic-ai/claude-cli'로 설치하세요.")
            
            logger.info(f"[{self.session_id}] Found claude CLI at: {claude_path}")
            
            self.status = SessionStatus.RUNNING
            logger.info(f"[{self.session_id}] ✅ Session initialized successfully")
            return True
            
        except Exception as e:
            self.status = SessionStatus.ERROR
            self.error_message = str(e)
            logger.error(f"[{self.session_id}] Failed to initialize session: {e}")
            return False

    async def execute(
        self, 
        prompt: str, 
        timeout: float = CLAUDE_DEFAULT_TIMEOUT
    ) -> Dict:
        """
        Claude에게 프롬프트 실행
        
        Args:
            prompt: Claude에게 전달할 프롬프트
            timeout: 실행 타임아웃 (초)
            
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
                # 환경 변수 준비
                env = os.environ.copy()
                env.update(self.env_vars)
                
                # claude 명령어 구성
                cmd = ["claude", "--print"]
                
                # 모델 지정
                if self.model:
                    cmd.extend(["--model", self.model])
                
                # 최대 턴 수 지정
                if self.max_turns:
                    cmd.extend(["--max-turns", str(self.max_turns)])
                
                # 프롬프트 추가
                cmd.extend(["-p", prompt])
                
                logger.info(f"[{self.session_id}] Executing: {' '.join(cmd)}")
                
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
