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
CLAUDE_DEFAULT_TIMEOUT = 1800

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


class ClaudeNodeConfig:
    """
    Configuration for direct Node.js execution of Claude CLI.

    This bypasses cmd.exe/PowerShell entirely on Windows,
    avoiding command line length limits and escaping issues.
    """
    def __init__(self, node_path: str, cli_js_path: str, base_dir: str):
        self.node_path = node_path
        self.cli_js_path = cli_js_path
        self.base_dir = base_dir

    def __repr__(self):
        return f"ClaudeNodeConfig(node='{self.node_path}', cli='{self.cli_js_path}')"


def find_claude_node_config() -> Optional[ClaudeNodeConfig]:
    """
    Find Node.js and Claude CLI JavaScript file paths for direct execution.

    This completely bypasses cmd.exe/PowerShell on Windows by finding:
    1. node.exe path
    2. @anthropic-ai/claude-code/cli.js path

    Returns:
        ClaudeNodeConfig with paths, or None if not found.
    """
    node_path = None
    cli_js_path = None
    base_dir = None

    if IS_WINDOWS:
        # Strategy 1: Find claude.cmd and parse it to get paths
        claude_cmd_paths = []

        # Check common npm global installation paths
        for ext in ['.cmd', '.ps1', '']:
            found = shutil.which(f"claude{ext}")
            if found:
                claude_cmd_paths.append(Path(found))

        # Additional common paths
        appdata = os.environ.get('APPDATA')
        if appdata:
            claude_cmd_paths.append(Path(appdata) / 'npm' / 'claude.cmd')
        claude_cmd_paths.append(Path.home() / 'AppData' / 'Roaming' / 'npm' / 'claude.cmd')

        # nvm4w common paths
        nvm_paths = [
            Path('C:/nvm4w/nodejs'),
            Path('C:/Program Files/nodejs'),
            Path.home() / 'AppData' / 'Local' / 'nvm',
        ]
        for nvm_path in nvm_paths:
            if nvm_path.exists():
                claude_cmd_paths.append(nvm_path / 'claude.cmd')

        # Find the first existing claude.cmd and derive paths
        for cmd_path in claude_cmd_paths:
            if cmd_path.exists():
                base_dir = cmd_path.parent
                potential_node = base_dir / 'node.exe'
                potential_cli = base_dir / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js'

                if potential_cli.exists():
                    # Found cli.js, now find node
                    cli_js_path = str(potential_cli)

                    if potential_node.exists():
                        node_path = str(potential_node)
                    else:
                        # Use node from PATH
                        node_path = shutil.which('node') or shutil.which('node.exe')

                    if node_path and cli_js_path:
                        logger.info(f"Found Claude via cmd wrapper: node={node_path}, cli={cli_js_path}")
                        return ClaudeNodeConfig(node_path, cli_js_path, str(base_dir))

        # Strategy 2: Direct search for cli.js in common npm locations
        npm_module_paths = []
        if appdata:
            npm_module_paths.append(Path(appdata) / 'npm' / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js')

        for nvm_path in nvm_paths:
            npm_module_paths.append(nvm_path / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js')

        for cli_path in npm_module_paths:
            if cli_path.exists():
                cli_js_path = str(cli_path)
                base_dir = str(cli_path.parent.parent.parent.parent)  # up to npm root
                node_path = shutil.which('node') or shutil.which('node.exe')

                if node_path:
                    logger.info(f"Found Claude via direct search: node={node_path}, cli={cli_js_path}")
                    return ClaudeNodeConfig(node_path, cli_js_path, base_dir)

    else:
        # Unix-like systems: find claude binary and derive cli.js path
        claude_path = shutil.which('claude')

        if claude_path:
            # Read the shebang/script to find cli.js
            claude_path = Path(claude_path).resolve()

            # Common cli.js locations relative to claude binary
            possible_cli_paths = [
                claude_path.parent / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js',
                claude_path.parent.parent / 'lib' / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js',
                Path.home() / '.npm-global' / 'lib' / 'node_modules' / '@anthropic-ai' / 'claude-code' / 'cli.js',
                Path('/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js'),
                Path('/usr/lib/node_modules/@anthropic-ai/claude-code/cli.js'),
            ]

            for cli_path in possible_cli_paths:
                if cli_path.exists():
                    cli_js_path = str(cli_path)
                    base_dir = str(cli_path.parent.parent.parent.parent)
                    node_path = shutil.which('node')

                    if node_path:
                        logger.info(f"Found Claude on Unix: node={node_path}, cli={cli_js_path}")
                        return ClaudeNodeConfig(node_path, cli_js_path, base_dir)

        # Fallback: just use 'claude' command directly (for compatibility)
        if claude_path:
            node_path = shutil.which('node')
            if node_path:
                # Return with claude_path as cli.js - will be handled specially
                logger.info(f"Falling back to claude binary: {claude_path}")
                return ClaudeNodeConfig(node_path, str(claude_path), str(claude_path.parent))

    logger.warning("Claude CLI (Node.js configuration) not found")
    return None


# Legacy function for backward compatibility
def find_claude_executable() -> Optional[str]:
    """
    Find the Claude CLI executable path (legacy, for compatibility).

    Use find_claude_node_config() for new code.
    """
    config = find_claude_node_config()
    if config:
        if IS_WINDOWS:
            return config.node_path  # Return node.exe on Windows
        else:
            return shutil.which('claude')  # Return claude binary on Unix
    return None


def _build_direct_node_command(config: ClaudeNodeConfig, args: List[str]) -> List[str]:
    """
    Build command for direct Node.js execution (bypasses cmd.exe/PowerShell entirely).

    Args:
        config: ClaudeNodeConfig with node and cli.js paths.
        args: Claude CLI arguments.

    Returns:
        List of command arguments starting with node.exe.
    """
    # Direct execution: node.exe cli.js [args...]
    # No cmd.exe, no PowerShell, no shell escaping issues
    return [config.node_path, config.cli_js_path] + args


class WindowsProcessWrapper:
    """
    Wrapper class that provides asyncio.subprocess.Process-like interface
    for subprocess.Popen on Windows. This avoids the NotImplementedError
    that occurs when uvicorn uses SelectorEventLoop instead of ProactorEventLoop.
    """

    def __init__(self, popen: 'subprocess.Popen'):
        self._popen = popen

    @property
    def pid(self) -> int:
        return self._popen.pid

    @property
    def returncode(self) -> Optional[int]:
        return self._popen.returncode

    async def communicate(self, input: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Async wrapper around Popen.communicate()"""
        import subprocess as sp

        def _communicate():
            return self._popen.communicate(input=input)

        return await asyncio.to_thread(_communicate)

    async def wait(self) -> int:
        """Async wrapper around Popen.wait()"""
        def _wait():
            return self._popen.wait()

        return await asyncio.to_thread(_wait)

    def terminate(self):
        """Terminate the process"""
        self._popen.terminate()

    def kill(self):
        """Kill the process"""
        self._popen.kill()

    def send_signal(self, sig):
        """Send a signal to the process"""
        self._popen.send_signal(sig)


async def create_subprocess_cross_platform(
    cmd: List[str],
    stdin: Optional[int] = None,
    stdout: Optional[int] = None,
    stderr: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
    cwd: Optional[str] = None,
    limit: int = STDIO_BUFFER_LIMIT
):
    """
    Create a subprocess in a cross-platform compatible way.

    IMPORTANT: On Windows, caller must provide direct executable commands
    (e.g., node.exe with arguments), NOT batch files (.cmd/.bat).
    This function does NOT wrap commands with cmd.exe or PowerShell.

    Args:
        cmd: Command and arguments as a list. First element must be a direct executable.
        stdin: stdin handling (e.g., asyncio.subprocess.PIPE or None)
        stdout: stdout handling
        stderr: stderr handling
        env: Environment variables dictionary
        cwd: Working directory path
        limit: Buffer limit for stdio pipes (only used on Unix)

    Returns:
        The created subprocess (WindowsProcessWrapper on Windows, asyncio.subprocess.Process on Unix).

    Raises:
        OSError: If the subprocess cannot be created.
    """
    import subprocess as sp

    if not cmd:
        raise ValueError("Command list cannot be empty")

    logger.debug(f"Platform: {platform.system()}, Command: {cmd[:4]}...")

    try:
        if IS_WINDOWS:
            # Windows: Use subprocess.Popen directly with node.exe
            # No cmd.exe wrapper - direct execution only

            # Map asyncio.subprocess constants to subprocess constants
            stdin_arg = sp.PIPE if stdin == asyncio.subprocess.PIPE else stdin
            stdout_arg = sp.PIPE if stdout == asyncio.subprocess.PIPE else stdout
            stderr_arg = sp.PIPE if stderr == asyncio.subprocess.PIPE else stderr

            # CREATE_NO_WINDOW (0x08000000) prevents console window popup
            creationflags = sp.CREATE_NO_WINDOW

            # STARTUPINFO to hide window
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = sp.SW_HIDE

            # Create process synchronously (Popen doesn't block)
            popen = sp.Popen(
                cmd,
                stdin=stdin_arg,
                stdout=stdout_arg,
                stderr=stderr_arg,
                env=env,
                cwd=cwd,
                creationflags=creationflags,
                startupinfo=startupinfo
            )

            process = WindowsProcessWrapper(popen)
            logger.debug(f"Windows subprocess created with PID: {process.pid}")
            return process
        else:
            # Unix-like systems: use asyncio subprocess directly
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                env=env,
                cwd=cwd,
                limit=limit
            )
            logger.debug(f"Unix subprocess created with PID: {process.pid}")
            return process

    except FileNotFoundError as e:
        logger.error(f"Executable not found: {cmd[0]}")
        raise
    except PermissionError as e:
        logger.error(f"Permission denied executing: {cmd[0]}")
        raise
    except OSError as e:
        if IS_WINDOWS and hasattr(e, 'winerror') and e.winerror == 193:
            logger.error(
                f"OSError 193: Cannot execute {cmd[0]} directly. "
                f"Ensure you are passing a direct executable (e.g., node.exe), not a script."
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
        mcp_config: Optional[MCPConfig] = None,
        system_prompt: Optional[str] = None
    ):
        self.session_id = session_id
        self.session_name = session_name
        self.model = model
        self.max_turns = max_turns
        self.env_vars = env_vars or {}
        self.mcp_config = mcp_config
        self.system_prompt = system_prompt  # Store system prompt for all executions

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

        # Execution tracking for --resume support
        self._execution_count = 0
        self._conversation_id: Optional[str] = None

        # Claude Node.js configuration (set during initialize)
        self._node_config: Optional[ClaudeNodeConfig] = None

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

            # Find Claude Node.js configuration (direct node.exe + cli.js execution)
            node_config = find_claude_node_config()
            if node_config is None:
                raise FileNotFoundError(
                    "Claude Code CLI not found. "
                    "Install it with: 'npm install -g @anthropic-ai/claude-code'"
                )

            # Store Node.js config for use in execute()
            self._node_config = node_config

            # Log the found paths with platform info
            logger.info(f"[{self.session_id}] Claude CLI config: {node_config}")
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
        max_turns: Optional[int] = None,
        resume: Optional[bool] = None
    ) -> Dict:
        """
        Execute a prompt with Claude using direct Node.js execution.

        On Windows, this bypasses cmd.exe/PowerShell entirely by:
        1. Calling node.exe directly with cli.js
        2. Sending prompts via stdin (no command line length limits)

        Args:
            prompt: The prompt to send to Claude.
            timeout: Execution timeout in seconds.
            skip_permissions: Skip permission prompts (None uses environment variable).
            system_prompt: Additional system prompt (for autonomous mode instructions).
            max_turns: Maximum turns for this execution (None uses session setting).
            resume: Whether to resume previous conversation (None = auto-detect).

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

                # Get or find Node.js config
                node_config = self._node_config or find_claude_node_config()
                if not node_config:
                    return {
                        "success": False,
                        "error": "Claude CLI not found. Install with: npm install -g @anthropic-ai/claude-code"
                    }

                # Build base arguments (without node.exe and cli.js - those are added by _build_direct_node_command)
                args = ["--print", "--verbose"]

                # Resume previous conversation if we have a Claude CLI session ID
                should_resume = resume if resume is not None else (self._execution_count > 0 and self._conversation_id)
                if should_resume and self._conversation_id:
                    args.extend(["--resume", self._conversation_id])
                    logger.info(f"[{self.session_id}] 🔄 Resuming conversation: {self._conversation_id}")

                # Skip permission prompts option (required for autonomous mode)
                should_skip_permissions = skip_permissions
                if should_skip_permissions is None:
                    env_skip = os.environ.get('CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS', 'true').lower()
                    should_skip_permissions = env_skip in ('true', '1', 'yes', 'on')

                if should_skip_permissions:
                    args.append("--dangerously-skip-permissions")
                    logger.info(f"[{self.session_id}] 🤖 Autonomous mode: --dangerously-skip-permissions enabled")

                # Specify model (session model > env default)
                effective_model = self.model or os.environ.get('ANTHROPIC_MODEL')
                if effective_model:
                    args.extend(["--model", effective_model])
                    logger.info(f"[{self.session_id}] 🤖 Using model: {effective_model}")

                # Specify max turns (execution setting > session setting)
                effective_max_turns = max_turns or self.max_turns
                if effective_max_turns:
                    args.extend(["--max-turns", str(effective_max_turns)])

                # Add system prompt (execution param > session default)
                effective_system_prompt = system_prompt or self.system_prompt

                # On Windows with direct node.exe execution, we can safely use stdin
                # No command line length limits or escaping issues

                if effective_system_prompt:
                    args.extend(["--append-system-prompt", effective_system_prompt])
                    logger.info(f"[{self.session_id}] 📝 System prompt applied ({len(effective_system_prompt)} chars)")

                # Build final command: node.exe cli.js [args...]
                # Note: prompt will be sent via stdin, not command line
                cmd = _build_direct_node_command(node_config, args)

                logger.info(f"[{self.session_id}] Executing: node cli.js {' '.join(args[:5])}...")
                logger.info(f"[{self.session_id}] Prompt length: {len(prompt)} chars, using stdin")

                # Execute process using cross-platform helper (direct node.exe execution)
                self._current_process = await create_subprocess_cross_platform(
                    cmd,
                    stdin=asyncio.subprocess.PIPE,  # Use stdin for prompt
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env,
                    cwd=self.working_dir,
                    limit=STDIO_BUFFER_LIMIT
                )

                # Collect output - send prompt via stdin
                try:
                    stdout, stderr = await asyncio.wait_for(
                        self._current_process.communicate(input=prompt.encode('utf-8')),
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
                    self._execution_count += 1
                    logger.info(f"[{self.session_id}] ✅ Execution #{self._execution_count} completed in {duration_ms}ms")

                    # Try to extract Claude CLI session ID from verbose output for --resume
                    # Check both stdout and stderr (verbose output often goes to stderr)
                    import re
                    combined_output = stdout_text + "\n" + stderr_text
                    session_patterns = [
                        r'Session[:\s]+([a-f0-9-]{20,})',
                        r'session_id[:\s]+([a-f0-9-]{20,})',
                        r'conversation[:\s]+([a-f0-9-]{20,})',
                        r'"id":\s*"([a-f0-9-]{20,})"',
                    ]
                    for pattern in session_patterns:
                        match = re.search(pattern, combined_output, re.IGNORECASE)
                        if match:
                            self._conversation_id = match.group(1)
                            logger.info(f"[{self.session_id}] 📝 Captured conversation ID: {self._conversation_id}")
                            break

                    # Save work log
                    await self._append_work_log(prompt, stdout_text, duration_ms, success=True)

                    return {
                        "success": True,
                        "output": stdout_text,
                        "duration_ms": duration_ms,
                        "execution_count": self._execution_count
                    }
                else:
                    logger.error(f"[{self.session_id}] ❌ Execution failed: {stderr_text}")

                    # Save error log
                    await self._append_work_log(prompt, stderr_text, duration_ms, success=False)

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

    async def _append_work_log(
        self,
        prompt: str,
        output: str,
        duration_ms: int,
        success: bool
    ):
        """
        Append execution log to WORK_LOG.md in storage directory.

        This creates a persistent record of all work performed by this session.
        """
        try:
            log_path = Path(self._storage_path) / "WORK_LOG.md"
            timestamp = now_kst().strftime("%Y-%m-%d %H:%M:%S")
            status_emoji = "✅" if success else "❌"

            # Truncate long content for log readability
            prompt_preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
            output_preview = output[:500] + "..." if len(output) > 500 else output

            log_entry = f"""
---

## [{status_emoji}] Execution #{self._execution_count} - {timestamp}

**Duration:** {duration_ms}ms

### Prompt
```
{prompt_preview}
```

### Output
```
{output_preview}
```

"""

            # Create file with header if it doesn't exist
            if not log_path.exists():
                header = f"""# Work Log - Session {self.session_id}

**Session Name:** {self.session_name or 'Unnamed'}
**Created:** {self.created_at.strftime("%Y-%m-%d %H:%M:%S")}
**Model:** {self.model or 'Default'}

This file contains a log of all work performed by this session.

"""
                log_path.write_text(header, encoding='utf-8')

            # Append log entry
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(log_entry)

            logger.debug(f"[{self.session_id}] Work log updated: {log_path}")

        except Exception as e:
            logger.warning(f"[{self.session_id}] Failed to write work log: {e}")

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
        List all files in the storage directory recursively.

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
            # Recursively walk through all files
            for item in target_path.rglob("*"):
                if item.is_file():
                    try:
                        stat = item.stat()
                        rel_path = str(item.relative_to(self._storage_path))
                        # Normalize path separators
                        rel_path = rel_path.replace("\\", "/")
                        files.append({
                            "name": item.name,
                            "path": rel_path,
                            "is_dir": False,
                            "size": stat.st_size,
                            "modified_at": datetime.fromtimestamp(stat.st_mtime)
                        })
                    except (OSError, ValueError) as e:
                        logger.debug(f"[{self.session_id}] Skipping file {item}: {e}")
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
