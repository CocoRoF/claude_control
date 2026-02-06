"""
Claude Code Process Manager

Manages Claude CLI as subprocess instances.
Each session has its own independent process and storage directory.
"""
import asyncio
import json
import logging
import os
import platform
import signal
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple, TYPE_CHECKING
from datetime import datetime

from service.claude_manager.models import SessionStatus, MCPConfig
from service.utils.utils import now_kst

if TYPE_CHECKING:
    from service.claude_manager.models import MCPConfig

logger = logging.getLogger(__name__)

# Buffer limit: 16MB
STDIO_BUFFER_LIMIT = 16 * 1024 * 1024

# Claude execution timeout (default 5 minutes)
CLAUDE_DEFAULT_TIMEOUT = 300.0

# Platform detection
IS_WINDOWS = platform.system() == 'Windows'
IS_MACOS = platform.system() == 'Darwin'
IS_LINUX = platform.system() == 'Linux'

# Default storage root path (cross-platform)
def _get_default_storage_root() -> str:
    """Get platform-appropriate default storage root."""
    env_storage = os.environ.get('CLAUDE_STORAGE_ROOT')
    if env_storage:
        return env_storage

    # Use platform-appropriate temp directory
    if IS_WINDOWS:
        # On Windows, use LOCALAPPDATA or TEMP
        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        return str(Path(base) / 'claude_sessions')
    elif IS_MACOS:
        # On macOS, use ~/Library/Application Support or /tmp
        app_support = Path.home() / 'Library' / 'Application Support' / 'claude_sessions'
        try:
            app_support.mkdir(parents=True, exist_ok=True)
            return str(app_support)
        except (PermissionError, OSError):
            return '/tmp/claude_sessions'
    else:
        # On Linux and other Unix-like systems, use /tmp
        return '/tmp/claude_sessions'

DEFAULT_STORAGE_ROOT = _get_default_storage_root()

# Claude Code environment variable keys (automatically passed to sessions)
CLAUDE_ENV_KEYS = [
    # Anthropic API
    'ANTHROPIC_API_KEY',
    'ANTHROPIC_AUTH_TOKEN',
    'ANTHROPIC_MODEL',
    'ANTHROPIC_DEFAULT_SONNET_MODEL',
    'ANTHROPIC_DEFAULT_OPUS_MODEL',
    'ANTHROPIC_DEFAULT_HAIKU_MODEL',

    # Claude Code settings
    'MAX_THINKING_TOKENS',
    'BASH_DEFAULT_TIMEOUT_MS',
    'BASH_MAX_TIMEOUT_MS',
    'BASH_MAX_OUTPUT_LENGTH',

    # Disable options
    'DISABLE_AUTOUPDATER',
    'DISABLE_ERROR_REPORTING',
    'DISABLE_TELEMETRY',
    'DISABLE_COST_WARNINGS',
    'DISABLE_PROMPT_CACHING',

    # Proxy settings
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

    # GitHub (for git push, PR creation)
    'GITHUB_TOKEN',
    'GH_TOKEN',
    'GITHUB_USERNAME',
]


def get_claude_env_vars() -> Dict[str, str]:
    """
    Collect environment variables required for Claude Code execution.

    Returns:
        Dictionary of environment variables to pass to Claude Code.
    """
    env_vars = {}
    for key in CLAUDE_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env_vars[key] = value
    return env_vars


def find_claude_executable() -> Optional[str]:
    """
    Find the Claude CLI executable path (cross-platform).

    Search order:
    1. 'claude' in PATH (works on all platforms)
    2. Windows-specific: 'claude.cmd', 'claude.exe', 'claude.bat' in PATH
    3. Windows-specific: Common npm global installation paths

    Returns:
        Full path to Claude CLI executable, or None if not found.
    """
    if IS_WINDOWS:
        # On Windows, prioritize finding .cmd/.bat files explicitly
        # because shutil.which may return path without extension
        
        # First, check for explicit .cmd (most common for npm global installs)
        for ext in ['.cmd', '.bat', '.exe']:
            claude_path = shutil.which(f"claude{ext}")
            if claude_path:
                logger.debug(f"Found claude via which('claude{ext}'): {claude_path}")
                return claude_path

        # Check common npm global installation paths on Windows
        npm_paths = []

        # APPDATA/npm (most common for npm global installs)
        appdata = os.environ.get('APPDATA')
        if appdata:
            npm_paths.append(Path(appdata) / 'npm' / 'claude.cmd')
            npm_paths.append(Path(appdata) / 'npm' / 'claude.exe')

        # User home directory fallback
        npm_paths.append(Path.home() / 'AppData' / 'Roaming' / 'npm' / 'claude.cmd')
        npm_paths.append(Path.home() / 'AppData' / 'Roaming' / 'npm' / 'claude.exe')

        for npm_path in npm_paths:
            if npm_path.exists():
                logger.debug(f"Found claude at npm path: {npm_path}")
                return str(npm_path)

        # Finally try without extension (shutil.which will search PATHEXT)
        claude_path = shutil.which("claude")
        if claude_path:
            logger.debug(f"Found claude via which('claude'): {claude_path}")
            return claude_path

    else:
        # On Unix-like systems, try the basic 'claude' command first
        claude_path = shutil.which("claude")
        if claude_path:
            logger.debug(f"Found claude via which('claude'): {claude_path}")
            return claude_path

        # Also check common paths on Unix
        unix_paths = [
            Path.home() / '.npm-global' / 'bin' / 'claude',
            Path('/usr/local/bin/claude'),
            Path('/usr/bin/claude'),
        ]
        for unix_path in unix_paths:
            if unix_path.exists() and unix_path.is_file():
                logger.debug(f"Found claude at: {unix_path}")
                return str(unix_path)

    logger.warning("Claude CLI executable not found in any known location")
    return None


def _build_shell_command(executable: str, args: List[str]) -> Tuple[str, List[str], bool]:
    """
    Build the appropriate shell command based on platform and executable type.

    Args:
        executable: The executable path or name.
        args: Additional arguments.

    Returns:
        Tuple of (shell_executable, full_args, use_shell)
        - shell_executable: The actual executable to run
        - full_args: Complete list of arguments including the executable
        - use_shell: Whether to use shell=True (generally avoided)
    """
    if IS_WINDOWS:
        # Normalize path separators for Windows
        executable = executable.replace('/', '\\')
        ext = Path(executable).suffix.lower()

        # If no extension, check if a .cmd or .bat version exists
        # This handles cases where shutil.which returns path without extension
        if not ext or ext not in ('.cmd', '.bat', '.exe', '.ps1'):
            # Check if this is actually a .cmd file (common for npm)
            cmd_path = executable + '.cmd'
            bat_path = executable + '.bat'
            
            if Path(cmd_path).exists():
                logger.debug(f"Detected {executable} is actually {cmd_path}")
                executable = cmd_path
                ext = '.cmd'
            elif Path(bat_path).exists():
                logger.debug(f"Detected {executable} is actually {bat_path}")
                executable = bat_path
                ext = '.bat'
            else:
                # Check if the file itself is a script by reading first line
                try:
                    if Path(executable).exists():
                        with open(executable, 'rb') as f:
                            first_bytes = f.read(256)
                            # Check for batch file signatures
                            if first_bytes.startswith(b'@') or b'\r\n@' in first_bytes:
                                logger.debug(f"Detected {executable} is a batch script by content")
                                ext = '.cmd'  # Treat as batch file
                except (IOError, OSError):
                    pass

        if ext in ('.cmd', '.bat'):
            # Batch files must be run via cmd.exe /c
            # This is a Windows requirement, not a choice
            full_args = ['cmd.exe', '/c', executable] + args
            logger.debug(f"Using cmd.exe wrapper for batch file: {executable}")
            return ('cmd.exe', full_args, False)
        elif ext == '.ps1':
            # PowerShell scripts
            full_args = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', executable] + args
            return ('powershell.exe', full_args, False)
        elif ext == '.exe':
            # Native executables
            full_args = [executable] + args
            return (executable, full_args, False)
        else:
            # Unknown extension on Windows - try via cmd.exe to be safe
            # This handles edge cases where npm installs scripts without proper extension
            logger.debug(f"Unknown extension '{ext}' on Windows, using cmd.exe wrapper for: {executable}")
            full_args = ['cmd.exe', '/c', executable] + args
            return ('cmd.exe', full_args, False)
    else:
        # Unix-like systems: direct execution
        full_args = [executable] + args
        return (executable, full_args, False)


async def create_subprocess_cross_platform(
    cmd: List[str],
    stdin: Optional[int] = None,
    stdout: Optional[int] = None,
    stderr: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    limit: int = STDIO_BUFFER_LIMIT
) -> asyncio.subprocess.Process:
    """
    Create a subprocess in a cross-platform compatible way.

    This function handles the following platform-specific issues:
    - Windows: .cmd/.bat files cannot be executed directly by CreateProcess
    - Windows: Need to properly escape/quote arguments
    - Windows: Prevent console window popups for background processes
    - Unix: Standard subprocess execution

    Args:
        cmd: Command and arguments as a list. First element is the executable.
        stdin: stdin handling (e.g., asyncio.subprocess.PIPE or None)
        stdout: stdout handling
        stderr: stderr handling
        env: Environment variables dictionary
        cwd: Working directory path
        limit: Buffer limit for stdio pipes

    Returns:
        The created asyncio subprocess.

    Raises:
        OSError: If the subprocess cannot be created.
    """
    if not cmd:
        raise ValueError("Command list cannot be empty")

    executable = cmd[0]
    args = cmd[1:]

    # Build platform-appropriate command
    shell_exec, full_cmd, use_shell = _build_shell_command(executable, args)

    logger.debug(f"Platform: {platform.system()}, Original: {executable}, Final cmd: {full_cmd[:4]}...")

    try:
        if IS_WINDOWS:
            # Windows-specific subprocess creation
            # We use subprocess.Popen kwargs that are passed through
            import subprocess as sp

            # Prepare Windows-specific kwargs
            # Note: asyncio.create_subprocess_exec passes kwargs to subprocess.Popen
            kwargs = {
                'stdin': stdin,
                'stdout': stdout,
                'stderr': stderr,
                'env': env,
                'cwd': cwd,
                'limit': limit,
            }

            # CREATE_NO_WINDOW (0x08000000) prevents console window popup
            # This is crucial for running as a service or background process
            kwargs['creationflags'] = sp.CREATE_NO_WINDOW

            # STARTUPINFO to hide window
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = sp.SW_HIDE
            kwargs['startupinfo'] = startupinfo

            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                **kwargs
            )
        else:
            # Unix-like systems: straightforward execution
            process = await asyncio.create_subprocess_exec(
                *full_cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
                cwd=cwd,
                limit=limit
            )

        logger.debug(f"Subprocess created with PID: {process.pid}")
        return process

    except FileNotFoundError as e:
        logger.error(f"Executable not found: {shell_exec} (full cmd: {full_cmd[:2]})")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied executing: {shell_exec}")
        raise
    except OSError as e:
        # WinError 193 = "%1 is not a valid Win32 application"
        # This happens when trying to run a batch file directly
        if IS_WINDOWS and e.winerror == 193:
            logger.error(
                f"OSError 193: Cannot execute {executable} directly. "
                f"This is typically a batch script that needs cmd.exe wrapper. "
                f"Full command was: {full_cmd}"
            )
        raise


class ClaudeProcess:
    """
    Individual Claude Code Process.

    Manages a Claude CLI subprocess.
    Each instance has a unique session ID and storage path.
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

        # Storage configuration (using Path for cross-platform compatibility)
        self._storage_root = storage_root or DEFAULT_STORAGE_ROOT
        self._storage_path = str(Path(self._storage_root) / session_id)

        # Use storage path as working directory if not specified
        self.working_dir = working_dir or self._storage_path

        # Process state
        self.process: Optional[asyncio.subprocess.Process] = None
        self.status = SessionStatus.STOPPED
        self.error_message: Optional[str] = None
        self.created_at = now_kst()

        # Claude CLI path (set during initialize)
        self._claude_path: Optional[str] = None

        # Current running process (for execute commands)
        self._current_process: Optional[asyncio.subprocess.Process] = None
        self._execution_lock = asyncio.Lock()

    @property
    def storage_path(self) -> str:
        """Session-specific storage path."""
        return self._storage_path

    @property
    def pid(self) -> Optional[int]:
        """Current running process ID."""
        if self._current_process:
            return self._current_process.pid
        return None

    async def initialize(self) -> bool:
        """
        Initialize the session.

        Creates the storage directory and prepares the session.
        Creates .mcp.json file if MCP configuration is provided.

        Returns:
            True if initialization succeeds, False otherwise.
        """
        try:
            self.status = SessionStatus.STARTING
            logger.info(f"[{self.session_id}] Initializing Claude session...")

            # Create storage directory (using Path for cross-platform compatibility)
            Path(self._storage_path).mkdir(parents=True, exist_ok=True)
            logger.info(f"[{self.session_id}] Storage created: {self._storage_path}")

            # Create working_dir if different from storage path
            if self.working_dir != self._storage_path:
                Path(self.working_dir).mkdir(parents=True, exist_ok=True)

            # Create MCP configuration file (.mcp.json)
            if self.mcp_config and self.mcp_config.servers:
                await self._create_mcp_config()

            # Find Claude CLI executable (cross-platform)
            claude_path = find_claude_executable()
            if claude_path is None:
                raise FileNotFoundError(
                    "Claude Code CLI not found. "
                    "Install it with: 'npm install -g @anthropic-ai/claude-code'"
                )

            # Store Claude CLI path for use in execute()
            self._claude_path = claude_path

            # Log the found path with platform info
            logger.info(f"[{self.session_id}] Found claude CLI at: {claude_path}")
            logger.info(f"[{self.session_id}] Platform: {platform.system()} ({platform.machine()})")

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
        Create .mcp.json configuration file.

        Creates MCP configuration file in the session's working_dir.
        Claude Code automatically reads this file to connect to MCP servers.
        """
        if not self.mcp_config:
            return

        mcp_json_path = Path(self.working_dir) / ".mcp.json"
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
        Execute a prompt with Claude.

        Args:
            prompt: The prompt to send to Claude.
            timeout: Execution timeout in seconds.
            skip_permissions: Skip permission prompts (None uses environment variable).
            system_prompt: Additional system prompt (for autonomous mode instructions).
            max_turns: Maximum turns for this execution (None uses session setting).

        Returns:
            Result dictionary with success, output, error, cost_usd, duration_ms.
        """
        async with self._execution_lock:
            if self.status != SessionStatus.RUNNING:
                return {
                    "success": False,
                    "error": f"Session is not running (status: {self.status})"
                }

            start_time = datetime.now()

            try:
                # Prepare environment variables (system + Claude-related + user-specified)
                env = os.environ.copy()
                env.update(get_claude_env_vars())  # Auto-add Claude Code environment variables
                env.update(self.env_vars)  # Session-specific user environment variables

                # Build claude command (use stored full path for cross-platform compatibility)
                claude_cmd = self._claude_path or find_claude_executable() or "claude"
                cmd = [claude_cmd, "--print"]

                # Skip permission prompts option (required for autonomous mode)
                # 1. Function argument takes priority
                # 2. Check CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS environment variable
                should_skip_permissions = skip_permissions
                if should_skip_permissions is None:
                    env_skip = os.environ.get('CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS', 'true').lower()
                    should_skip_permissions = env_skip in ('true', '1', 'yes', 'on')

                if should_skip_permissions:
                    cmd.append("--dangerously-skip-permissions")
                    logger.info(f"[{self.session_id}] 🤖 Autonomous mode: --dangerously-skip-permissions enabled")

                # Specify model
                if self.model:
                    cmd.extend(["--model", self.model])

                # Specify max turns (execution setting > session setting)
                effective_max_turns = max_turns or self.max_turns
                if effective_max_turns:
                    cmd.extend(["--max-turns", str(effective_max_turns)])

                # Add system prompt (autonomous mode instructions)
                if system_prompt:
                    cmd.extend(["--append-system-prompt", system_prompt])
                    logger.info(f"[{self.session_id}] 📝 Custom system prompt applied")

                # Add the prompt - use stdin for long prompts to avoid command line length limits
                # Windows has stricter command line length limits (~8191 chars)
                max_cmd_length = 2000 if IS_WINDOWS else 8000
                use_stdin = len(prompt) > max_cmd_length
                if not use_stdin:
                    cmd.extend(["-p", prompt])

                logger.info(f"[{self.session_id}] Executing: {' '.join(cmd[:5])}...")  # Log partial for security
                logger.info(f"[{self.session_id}] Prompt length: {len(prompt)} chars, use_stdin: {use_stdin}")

                # Execute process using cross-platform helper
                self._current_process = await create_subprocess_cross_platform(
                    cmd,
                    stdin=asyncio.subprocess.PIPE if use_stdin else None,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    limit=STDIO_BUFFER_LIMIT
                )

                # Collect output
                try:
                    if use_stdin:
                        # Send prompt via stdin
                        stdout, stderr = await asyncio.wait_for(
                            self._current_process.communicate(input=prompt.encode('utf-8')),
                            timeout=timeout
                        )
                    else:
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
        """Forcefully terminate the currently running process (cross-platform)."""
        if self._current_process:
            try:
                if IS_WINDOWS:
                    # On Windows, use terminate() first, then kill() if needed
                    # kill() on Windows is equivalent to terminate()
                    self._current_process.terminate()
                    try:
                        await asyncio.wait_for(self._current_process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        # Force kill if graceful termination fails
                        self._current_process.kill()
                        await self._current_process.wait()
                else:
                    # On Unix, try SIGTERM first, then SIGKILL
                    try:
                        self._current_process.terminate()
                        await asyncio.wait_for(self._current_process.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        self._current_process.kill()
                        await self._current_process.wait()
            except ProcessLookupError:
                # Process already terminated
                logger.debug(f"[{self.session_id}] Process already terminated")
            except Exception as e:
                logger.warning(f"[{self.session_id}] Failed to kill process: {e}")

    def list_storage_files(self, subpath: str = "") -> List[Dict]:
        """
        List files in the storage directory.

        Args:
            subpath: Subdirectory path (empty string for root).

        Returns:
            List of file information dictionaries.
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
        Read storage file content.

        Args:
            file_path: File path (relative to storage root).
            encoding: File encoding.

        Returns:
            File content dictionary or None.
        """
        target_path = Path(self._storage_path) / file_path

        # Path validation (prevent directory traversal)
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
        """Stop session and cleanup resources."""
        try:
            logger.info(f"[{self.session_id}] Stopping session...")

            # Terminate currently running process
            await self._kill_current_process()

            self.status = SessionStatus.STOPPED
            logger.info(f"[{self.session_id}] Session stopped")

        except Exception as e:
            logger.error(f"[{self.session_id}] Error stopping session: {e}")
            self.status = SessionStatus.STOPPED

    async def cleanup_storage(self):
        """Delete storage directory."""
        try:
            storage_path = Path(self._storage_path)
            if storage_path.exists():
                shutil.rmtree(storage_path)
                logger.info(f"[{self.session_id}] Storage cleaned up: {self._storage_path}")
        except Exception as e:
            logger.error(f"[{self.session_id}] Failed to cleanup storage: {e}")

    def is_alive(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.RUNNING
