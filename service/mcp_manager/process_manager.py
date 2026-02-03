"""
MCP 서버 프로세스 관리
"""
import asyncio
import logging
import re
import shlex
import shutil
import signal
import os
import json
from typing import Optional, Dict, List
from service.mcp_manager.models import MCPServerType, MCPServerStatus
from service.utils.utils import now_kst

logger = logging.getLogger(__name__)

# 버퍼 제한: 16MB (기본값 64KB에서 증가 - 큰 MCP 응답 처리용)
STDIO_BUFFER_LIMIT = 16 * 1024 * 1024

# MCP 초기화 타임아웃 (npx 패키지 다운로드 포함)
MCP_INIT_TIMEOUT = 60.0

# MCP 요청 타임아웃
MCP_REQUEST_TIMEOUT = 30.0


class MCPProcess:
    """개별 MCP 서버 프로세스"""

    def __init__(
        self,
        session_id: str,
        server_type: MCPServerType,
        command: str,
        args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        working_dir: Optional[str] = None,
        session_name: Optional[str] = None,
        additional_commands: Optional[List[str]] = None
    ):
        self.session_id = session_id
        self.session_name = session_name
        self.server_type = server_type
        self.command = command
        self.args = args or []
        self.env_vars = env_vars or {}
        self.working_dir = working_dir
        self.additional_commands = additional_commands or []

        self.process: Optional[asyncio.subprocess.Process] = None
        self.status = MCPServerStatus.STOPPED
        self.error_message: Optional[str] = None
        self.created_at = now_kst()  # Asia/Seoul 시간대로 생성 시간 저장

        # stdio를 위한 큐
        self.stdout_queue = asyncio.Queue()
        self.stderr_queue = asyncio.Queue()
        
        # MCP 초기화 상태
        self._initialized = False
        self._request_id_counter = 0

    def _get_next_request_id(self) -> int:
        """JSON-RPC request ID 생성"""
        self._request_id_counter += 1
        return self._request_id_counter

    async def start(self) -> bool:
        """프로세스 시작"""
        try:
            self.status = MCPServerStatus.STARTING
            logger.info(f"Starting MCP server process for session {self.session_id}")

            env = os.environ.copy()
            env.update(self.env_vars)

            def replace_var(match):
                var_name = match.group(1)
                value = env.get(var_name)
                if value is None:
                    logger.warning(f"Environment variable '${{{var_name}}}' not found")
                    return match.group(0)
                logger.debug(f"Replaced ${{{var_name}}}")
                return value
            
            self.args = [
                re.sub(r'\$\{([^}]+)\}', replace_var, arg) 
                for arg in self.args
            ]
            # 실행 명령어 구성
            if self.server_type == MCPServerType.PYTHON:
                cmd = ["python", "-u", self.command] + self.args

                # 프로세스 실행 (stdio를 통한 통신)
                # start_new_session=True로 새 프로세스 그룹 생성 (자식 프로세스 포함 종료 가능)
                self.process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    start_new_session=True,
                    limit=STDIO_BUFFER_LIMIT
                )

            elif self.server_type == MCPServerType.NODE:
                npx_path = shutil.which("npx", path=env.get("PATH", os.environ.get("PATH")))
                if npx_path is None:
                    logger.error("Node.js/npm is NOT installed on this server/container.")
                    raise FileNotFoundError("Node.js/npm is NOT installed on this server/container.")
                
                # Node 타입인 경우 shell을 통해 실행 (npx, npm 등을 위해)
                # command와 args를 결합하여 shell 명령어 생성
                logger.info(f"Found npx at: {npx_path}")
                quoted_args = [shlex.quote(arg) for arg in self.args]
                full_command = f"{npx_path} {' '.join(quoted_args)}"

                # start_new_session=True로 새 프로세스 그룹 생성 (자식 프로세스 포함 종료 가능)
                self.process = await asyncio.create_subprocess_shell(
                    full_command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    start_new_session=True,
                    limit=STDIO_BUFFER_LIMIT
                )
            else:
                raise ValueError(f"Unsupported server type: {self.server_type}")

            self.status = MCPServerStatus.RUNNING
            logger.info(f"MCP server started with PID {self.process.pid}")

            # stdout, stderr 읽기 태스크 시작
            asyncio.create_task(self._read_stdout())
            asyncio.create_task(self._read_stderr())

            # 추가 명령어 실행 (MCP 서버 시작 후)
            if self.additional_commands:
                logger.info(f"[{self.session_id}] Scheduling {len(self.additional_commands)} additional command(s)")
                task = asyncio.create_task(self._run_additional_commands(env))
                # 태스크 예외를 로깅하기 위한 콜백 추가
                task.add_done_callback(self._on_additional_commands_done)
            else:
                logger.info(f"[{self.session_id}] No additional_commands to run")

            # MCP 초기화 핸드셰이크 (백그라운드에서 실행)
            asyncio.create_task(self._initialize_mcp())

            return True

        except Exception as e:
            self.status = MCPServerStatus.ERROR
            self.error_message = str(e)
            logger.error(f"Failed to start MCP server: {e}")
            return False

    async def _initialize_mcp(self):
        """MCP 프로토콜 초기화 핸드셰이크"""
        try:
            logger.info(f"[{self.session_id}] Starting MCP initialization handshake...")
            
            # MCP 서버가 준비될 때까지 대기 (최대 MCP_INIT_TIMEOUT초)
            # initialize 요청 전송
            init_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": True},
                        "sampling": {}
                    },
                    "clientInfo": {
                        "name": "mcp-station",
                        "version": "1.0.0"
                    }
                }
            }
            
            # 초기화 요청 전송 (긴 타임아웃)
            response = await self._send_request_internal(init_request, timeout=MCP_INIT_TIMEOUT)
            
            if response is None:
                logger.error(f"[{self.session_id}] MCP initialization failed: no response")
                return
            
            if "error" in response:
                logger.error(f"[{self.session_id}] MCP initialization error: {response['error']}")
                return
            
            logger.info(f"[{self.session_id}] MCP initialize response received")
            
            # initialized 알림 전송
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            
            await self._send_notification(initialized_notification)
            
            self._initialized = True
            logger.info(f"[{self.session_id}] ✅ MCP initialization complete")
            
        except Exception as e:
            logger.error(f"[{self.session_id}] MCP initialization error: {e}", exc_info=True)

    async def _send_notification(self, notification: Dict):
        """알림 전송 (응답 없음)"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")
        
        try:
            notification_str = json.dumps(notification) + "\n"
            self.process.stdin.write(notification_str.encode())
            await self.process.stdin.drain()
            logger.debug(f"[{self.session_id}] Sent notification: {notification.get('method')}")
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to send notification: {e}")

    async def _send_request_internal(self, request: Dict, timeout: float = MCP_REQUEST_TIMEOUT) -> Optional[Dict]:
        """내부용 요청 전송 (초기화 포함)"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")

        try:
            request_str = json.dumps(request) + "\n"
            self.process.stdin.write(request_str.encode())
            await self.process.stdin.drain()
            
            logger.debug(f"[{self.session_id}] Sent request: {request.get('method')} (id={request.get('id')})")

            # stdout에서 응답 대기
            try:
                response_line = await asyncio.wait_for(
                    self.stdout_queue.get(),
                    timeout=timeout
                )
                return json.loads(response_line)
            except asyncio.TimeoutError:
                logger.error(f"[{self.session_id}] Timeout waiting for MCP response ({timeout}s)")
                return None

        except Exception as e:
            logger.error(f"[{self.session_id}] Error sending request: {e}")
            raise

    def _on_additional_commands_done(self, task: asyncio.Task):
        """추가 명령어 태스크 완료 콜백"""
        try:
            exc = task.exception()
            if exc:
                logger.error(f"[{self.session_id}] Additional commands task failed with exception: {exc}", exc_info=exc)
            else:
                logger.info(f"[{self.session_id}] Additional commands task finished successfully")
        except asyncio.CancelledError:
            logger.warning(f"[{self.session_id}] Additional commands task was cancelled")
        except Exception as e:
            logger.error(f"[{self.session_id}] Error in additional commands done callback: {e}")

    async def _read_stdout(self):
        """stdout 읽기"""
        if not self.process or not self.process.stdout:
            return

        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                await self.stdout_queue.put(line.decode().strip())
        except Exception as e:
            logger.error(f"Error reading stdout: {e}")

    async def _read_stderr(self):
        """stderr 읽기"""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                stderr_line = line.decode().strip()
                await self.stderr_queue.put(stderr_line)
                logger.warning(f"MCP stderr [{self.session_id}]: {stderr_line}")
        except Exception as e:
            logger.error(f"Error reading stderr: {e}")

    async def _run_additional_commands(self, env: Dict[str, str]):
        """
        MCP 서버 시작 후 추가 명령어 순차 실행
        
        Args:
            env: 환경 변수 딕셔너리
        """
        logger.info(f"[{self.session_id}] _run_additional_commands started")
        logger.info(f"[{self.session_id}] additional_commands: {self.additional_commands}")
        
        if not self.additional_commands:
            logger.info(f"[{self.session_id}] No additional commands to run")
            return

        # MCP 서버가 완전히 시작될 때까지 잠시 대기
        await asyncio.sleep(2.0)
        logger.info(f"[{self.session_id}] Starting {len(self.additional_commands)} additional command(s)")

        for idx, cmd in enumerate(self.additional_commands, 1):
            if not cmd or not cmd.strip():
                logger.warning(f"[{self.session_id}] Skipping empty command at index {idx}")
                continue

            try:
                logger.info(f"[{self.session_id}] ========================================")
                logger.info(f"[{self.session_id}] Executing additional command ({idx}/{len(self.additional_commands)})")
                logger.info(f"[{self.session_id}] Command: {cmd}")
                logger.info(f"[{self.session_id}] Working dir: {self.working_dir}")
                logger.info(f"[{self.session_id}] ========================================")

                # 명령어 실행 (shell=True로 전체 명령어 실행)
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir
                )
                logger.info(f"[{self.session_id}] Process started with PID: {proc.pid}")

                # 명령어 완료 대기 (타임아웃 5분)
                try:
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(),
                        timeout=300.0
                    )

                    stdout_text = stdout.decode().strip() if stdout else ""
                    stderr_text = stderr.decode().strip() if stderr else ""

                    logger.info(f"[{self.session_id}] Command finished with return code: {proc.returncode}")
                    
                    if stdout_text:
                        logger.info(f"[{self.session_id}] STDOUT:\n{stdout_text}")
                    
                    if stderr_text:
                        # stderr가 있어도 return code가 0이면 warning, 아니면 error
                        if proc.returncode == 0:
                            logger.warning(f"[{self.session_id}] STDERR:\n{stderr_text}")
                        else:
                            logger.error(f"[{self.session_id}] STDERR:\n{stderr_text}")

                    if proc.returncode == 0:
                        logger.info(f"[{self.session_id}] ✅ Command completed successfully: {cmd}")
                    else:
                        logger.error(f"[{self.session_id}] ❌ Command failed with code {proc.returncode}: {cmd}")

                except asyncio.TimeoutError:
                    logger.error(f"[{self.session_id}] ⏱️ Command timed out after 5 minutes: {cmd}")
                    try:
                        proc.kill()
                        await proc.wait()
                        logger.info(f"[{self.session_id}] Killed timed-out process")
                    except Exception as kill_err:
                        logger.error(f"[{self.session_id}] Failed to kill timed-out process: {kill_err}")

            except Exception as e:
                logger.error(f"[{self.session_id}] ❌ Exception executing command '{cmd}': {e}", exc_info=True)

        logger.info(f"[{self.session_id}] All additional commands completed")

    async def send_request(self, request: Dict) -> Optional[Dict]:
        """
        MCP 서버로 JSON-RPC 요청 전송 (stdio)
        
        MCP 초기화가 완료될 때까지 대기 후 요청 전송
        """
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not started")

        # MCP 초기화 완료 대기 (최대 MCP_INIT_TIMEOUT초)
        if not self._initialized:
            logger.info(f"[{self.session_id}] Waiting for MCP initialization...")
            wait_time = 0
            check_interval = 0.5
            while not self._initialized and wait_time < MCP_INIT_TIMEOUT:
                await asyncio.sleep(check_interval)
                wait_time += check_interval
                
                # 프로세스가 종료되었는지 확인
                if not self.is_alive():
                    logger.error(f"[{self.session_id}] MCP process died during initialization")
                    return None
            
            if not self._initialized:
                logger.warning(f"[{self.session_id}] MCP initialization not confirmed, proceeding anyway...")

        try:
            logger.debug(f"[{self.session_id}] Sending request: {request.get('method')} (id={request.get('id')})")
            
            # JSON-RPC 요청 직렬화
            request_str = json.dumps(request) + "\n"

            # stdin으로 전송
            self.process.stdin.write(request_str.encode())
            await self.process.stdin.drain()

            # stdout에서 응답 대기
            try:
                response_line = await asyncio.wait_for(
                    self.stdout_queue.get(),
                    timeout=MCP_REQUEST_TIMEOUT
                )
                return json.loads(response_line)
            except asyncio.TimeoutError:
                logger.error(f"[{self.session_id}] Timeout waiting for MCP response ({MCP_REQUEST_TIMEOUT}s)")
                return None

        except Exception as e:
            logger.error(f"[{self.session_id}] Error sending request to MCP server: {e}")
            raise

    async def stop(self):
        """프로세스 중지"""
        if not self.process:
            return

        try:
            pid = self.process.pid
            logger.info(f"Stopping MCP server process {pid}")

            # 프로세스 그룹 전체에 SIGTERM 전송 (자식 프로세스 포함)
            try:
                os.killpg(os.getpgid(pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError) as e:
                logger.warning(f"Failed to send SIGTERM to process group: {e}")
                # 프로세스 그룹 kill 실패 시 직접 시도
                try:
                    self.process.send_signal(signal.SIGTERM)
                except ProcessLookupError:
                    pass

            # 종료 대기 (최대 3초)
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                # 강제 종료 - 프로세스 그룹 전체에 SIGKILL
                logger.warning("Process didn't stop gracefully, forcing kill")
                try:
                    os.killpg(os.getpgid(pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError) as e:
                    logger.warning(f"Failed to kill process group: {e}")
                    try:
                        self.process.kill()
                    except ProcessLookupError:
                        pass

                # kill 후에도 짧은 타임아웃으로 대기
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    logger.error(f"Process {pid} did not terminate even after SIGKILL")

            self.status = MCPServerStatus.STOPPED
            logger.info("MCP server stopped")

        except Exception as e:
            logger.error(f"Error stopping process: {e}")
            self.status = MCPServerStatus.STOPPED

    @property
    def pid(self) -> Optional[int]:
        """프로세스 ID"""
        return self.process.pid if self.process else None

    def is_alive(self) -> bool:
        """프로세스가 살아있는지 확인"""
        if not self.process:
            return False
        return self.process.returncode is None
