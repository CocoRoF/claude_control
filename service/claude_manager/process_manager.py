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
import tempfile
from pathlib import Path
from typing import Optional, Dict, List, Any, TYPE_CHECKING
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

# Default storage root path (cross-platform)
def _get_default_storage_root() -> str:
    """Get platform-appropriate default storage root."""
    env_storage = os.environ.get('CLAUDE_STORAGE_ROOT')
    if env_storage:
        return env_storage

    # Use platform-appropriate temp directory
    if platform.system() == 'Windows':
        # On Windows, use LOCALAPPDATA or TEMP
        base = os.environ.get('LOCALAPPDATA') or tempfile.gettempdir()
        return str(Path(base) / 'claude_sessions')
    else:
        # On Unix-like systems, use /tmp
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

    On Windows, searches for 'claude.cmd' or 'claude.exe' in addition to 'claude'.
    On Unix-like systems, searches for 'claude'.

    Returns:
        Full path to Claude CLI executable, or None if not found.
    """
    # Try the basic 'claude' command first
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # On Windows, try additional extensions
    if platform.system() == 'Windows':
        for ext in ['.cmd', '.exe', '.bat']:
            claude_path = shutil.which(f"claude{ext}")
            if claude_path:
                return claude_path

    return None


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
                    "Claude Code is not installed. "
                    "Install it with: 'npm install -g @anthropic-ai/claude-code'"
                )

            # Store Claude CLI path for use in execute()
            self._claude_path = claude_path

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
                # WARNING: Default is 'false' for security - must explicitly opt-in
                should_skip_permissions = skip_permissions
                if should_skip_permissions is None:
                    env_skip = os.environ.get('CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS', 'false').lower()
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

                # Add the prompt
                cmd.extend(["-p", prompt])

                logger.info(f"[{self.session_id}] Executing: {' '.join(cmd[:5])}...")  # Log partial for security

                # Execute process
                self._current_process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    limit=STDIO_BUFFER_LIMIT
                )

                # Collect output
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
        """Forcefully terminate the currently running process."""
        if self._current_process:
            try:
                self._current_process.kill()
                await self._current_process.wait()
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
