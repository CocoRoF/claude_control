"""
Claude Code Process Manager

Manages Claude CLI as subprocess instances.
Each session has its own independent process and storage directory.
"""
import asyncio
import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime

from service.claude_manager.models import SessionStatus, MCPConfig
from service.claude_manager.constants import CLAUDE_DEFAULT_TIMEOUT, STDIO_BUFFER_LIMIT
from service.claude_manager.platform_utils import (
    IS_WINDOWS,
    DEFAULT_STORAGE_ROOT,
    get_claude_env_vars,
    create_subprocess_cross_platform,
)
from service.claude_manager.cli_discovery import (
    ClaudeNodeConfig,
    find_claude_node_config,
    build_direct_node_command,
)
from service.claude_manager.storage_utils import (
    list_storage_files as _list_storage_files,
    read_storage_file as _read_storage_file,
)
from service.utils.utils import now_kst

logger = logging.getLogger(__name__)


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
        timeout: Optional[float] = None,
        storage_root: Optional[str] = None,
        mcp_config: Optional[MCPConfig] = None,
        system_prompt: Optional[str] = None,
        autonomous: Optional[bool] = True,
        autonomous_max_iterations: Optional[int] = 100,
        role: Optional[str] = "worker",
        manager_id: Optional[str] = None
    ):
        self.session_id = session_id
        self.session_name = session_name
        self.model = model
        self.max_turns = max_turns or 100
        self.timeout = timeout or 1800.0  # Default 30 minutes
        self.env_vars = env_vars or {}
        self.mcp_config = mcp_config
        self.system_prompt = system_prompt  # Store system prompt for all executions

        # Autonomous mode settings
        self.autonomous = autonomous if autonomous is not None else True
        self.autonomous_max_iterations = autonomous_max_iterations or 100

        # Role settings for hierarchical management
        self.role = role or "worker"
        self.manager_id = manager_id

        # Autonomous execution state
        self._original_request: Optional[str] = None
        self._autonomous_iteration: int = 0
        self._autonomous_running: bool = False
        self._autonomous_stop_requested: bool = False

        # Worker execution state (for manager tracking)
        self._is_busy: bool = False
        self._current_task: Optional[str] = None
        self._last_output: Optional[str] = None
        self._last_activity: Optional[datetime] = None

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

    # Worker state properties for manager tracking
    @property
    def is_busy(self) -> bool:
        """Whether worker is currently executing a task."""
        return self._is_busy

    @is_busy.setter
    def is_busy(self, value: bool):
        self._is_busy = value

    @property
    def current_task(self) -> Optional[str]:
        """Current task description (for workers)."""
        return self._current_task

    @current_task.setter
    def current_task(self, value: Optional[str]):
        self._current_task = value

    @property
    def last_output(self) -> Optional[str]:
        """Last execution output (for workers)."""
        return self._last_output

    @last_output.setter
    def last_output(self, value: Optional[str]):
        self._last_output = value

    @property
    def last_activity(self) -> Optional[datetime]:
        """Last activity timestamp (for workers)."""
        return self._last_activity

    @last_activity.setter
    def last_activity(self, value: Optional[datetime]):
        self._last_activity = value

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
            import platform
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

                # Build base arguments (without node.exe and cli.js - those are added by build_direct_node_command)
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
                cmd = build_direct_node_command(node_config, args)

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

        Files matching .gitignore patterns and default ignore patterns
        (node_modules, .venv, etc.) are automatically excluded.

        Args:
            subpath: Subdirectory path (empty string for root).

        Returns:
            List of file information dictionaries.
        """
        return _list_storage_files(
            storage_path=self._storage_path,
            subpath=subpath,
            session_id=self.session_id,
            include_gitignore=True
        )

    def read_storage_file(self, file_path: str, encoding: str = "utf-8") -> Optional[Dict]:
        """
        Read storage file content.

        Args:
            file_path: File path (relative to storage root).
            encoding: File encoding.

        Returns:
            File content dictionary or None.
        """
        return _read_storage_file(
            storage_path=self._storage_path,
            file_path=file_path,
            encoding=encoding,
            session_id=self.session_id
        )

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

    # ========== Autonomous Mode Methods ==========

    def stop_autonomous(self):
        """Request to stop the autonomous execution loop."""
        self._autonomous_stop_requested = True
        logger.info(f"[{self.session_id}] 🛑 Autonomous stop requested")

    @property
    def autonomous_state(self) -> Dict[str, Any]:
        """Get current autonomous execution state."""
        return {
            "is_running": self._autonomous_running,
            "iteration": self._autonomous_iteration,
            "original_request": self._original_request,
            "stop_requested": self._autonomous_stop_requested,
            "max_iterations": self.autonomous_max_iterations
        }

    async def execute_autonomous(
        self,
        prompt: str,
        timeout_per_iteration: float = 600.0,
        max_iterations: Optional[int] = None,
        skip_permissions: Optional[bool] = True,
        system_prompt: Optional[str] = None,
        max_turns: Optional[int] = None,
        on_iteration_complete: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Execute a task autonomously with self-managing loop.

        This method implements the core autonomous/worker mode:
        1. Stores the original user request
        2. Executes Claude with the request
        3. Checks for [CONTINUE: ...] or [TASK_COMPLETE] patterns
        4. If continue: reminds Claude of original request and continues
        5. If complete: returns final result
        6. Repeats until complete or max_iterations reached

        Args:
            prompt: The original user request to complete.
            timeout_per_iteration: Timeout for each iteration (seconds).
            max_iterations: Maximum iterations (None uses session setting).
            skip_permissions: Skip permission prompts.
            system_prompt: Additional system prompt.
            max_turns: Maximum turns per iteration.
            on_iteration_complete: Callback called after each iteration
                                   with (iteration, result, is_complete).

        Returns:
            Dict with:
                - success: Whether execution completed successfully
                - is_complete: Whether the task was fully completed
                - total_iterations: Number of iterations executed
                - original_request: The original user request
                - final_output: Output from the final iteration
                - all_outputs: List of all iteration outputs
                - stop_reason: 'complete', 'max_iterations', 'error', 'user_stop'
                - total_duration_ms: Total execution time
        """
        # Patterns for detecting continuation and completion
        CONTINUE_PATTERN = re.compile(r'\[CONTINUE:\s*(.+?)\]', re.IGNORECASE)
        COMPLETE_PATTERN = re.compile(r'\[TASK_COMPLETE\]', re.IGNORECASE)

        # Initialize autonomous state
        self._original_request = prompt
        self._autonomous_iteration = 0
        self._autonomous_running = True
        self._autonomous_stop_requested = False

        effective_max_iterations = max_iterations or self.autonomous_max_iterations
        all_outputs: List[str] = []
        total_duration_ms = 0
        stop_reason = "unknown"
        final_output = ""
        is_complete = False

        logger.info(f"[{self.session_id}] 🚀 Starting autonomous execution (max {effective_max_iterations} iterations)")
        logger.info(f"[{self.session_id}] 📝 Original request: {prompt[:200]}{'...' if len(prompt) > 200 else ''}")

        try:
            # Build reminder prefix for subsequent iterations
            reminder_template = """
## ⚠️ REMINDER: Original User Request ⚠️
You are working on the following task. Continue until fully complete.

### Original Request:
{original_request}

### Current Status:
This is iteration #{iteration}. Your previous response indicated more work is needed.
Continue from where you left off. Remember to output [CONTINUE: next_action] if more work remains, or [TASK_COMPLETE] when done.

### Previous Hint:
{previous_hint}

---

Continue working on the task:
"""

            current_prompt = prompt
            previous_hint = "Starting task"

            while self._autonomous_iteration < effective_max_iterations:
                # Check for stop request
                if self._autonomous_stop_requested:
                    stop_reason = "user_stop"
                    logger.info(f"[{self.session_id}] 🛑 Autonomous execution stopped by user")
                    break

                self._autonomous_iteration += 1
                logger.info(f"[{self.session_id}] 🔄 Autonomous iteration #{self._autonomous_iteration}")

                # Execute single iteration
                result = await self.execute(
                    prompt=current_prompt,
                    timeout=timeout_per_iteration,
                    skip_permissions=skip_permissions,
                    system_prompt=system_prompt,
                    max_turns=max_turns,
                    resume=True if self._autonomous_iteration > 1 else None
                )

                output = result.get("output", "")
                all_outputs.append(output)
                final_output = output
                total_duration_ms += result.get("duration_ms", 0)

                # Call iteration callback if provided
                if on_iteration_complete:
                    try:
                        await on_iteration_complete(self._autonomous_iteration, result, False)
                    except Exception as e:
                        logger.warning(f"[{self.session_id}] Callback error: {e}")

                # Check for errors
                if not result.get("success", False):
                    error = result.get("error", "Unknown error")
                    logger.error(f"[{self.session_id}] ❌ Iteration #{self._autonomous_iteration} failed: {error}")
                    stop_reason = "error"
                    break

                # Check for task completion
                if COMPLETE_PATTERN.search(output):
                    is_complete = True
                    stop_reason = "complete"
                    logger.info(f"[{self.session_id}] ✅ Task complete! (iteration #{self._autonomous_iteration})")
                    break

                # Check for continue pattern
                continue_match = CONTINUE_PATTERN.search(output)
                if continue_match:
                    previous_hint = continue_match.group(1).strip()
                    logger.info(f"[{self.session_id}] 🔄 Continue detected: {previous_hint}")

                    # Build reminder prompt for next iteration
                    current_prompt = reminder_template.format(
                        original_request=self._original_request,
                        iteration=self._autonomous_iteration + 1,
                        previous_hint=previous_hint
                    )
                else:
                    # No continue pattern - Claude may have finished or is confused
                    # Check if output looks like completion (no clear next steps mentioned)
                    if self._looks_like_completion(output):
                        is_complete = True
                        stop_reason = "complete"
                        logger.info(f"[{self.session_id}] ✅ Task appears complete (no continue signal)")
                        break
                    else:
                        # Continue with a generic reminder
                        previous_hint = "Continue from where you left off"
                        current_prompt = reminder_template.format(
                            original_request=self._original_request,
                            iteration=self._autonomous_iteration + 1,
                            previous_hint=previous_hint
                        )
                        logger.info(f"[{self.session_id}] ⚠️ No continue pattern, prompting to continue")

            else:
                # Loop completed without break - max iterations reached
                stop_reason = "max_iterations"
                logger.warning(f"[{self.session_id}] ⚠️ Max iterations ({effective_max_iterations}) reached")

        except Exception as e:
            logger.error(f"[{self.session_id}] ❌ Autonomous execution error: {e}", exc_info=True)
            stop_reason = "error"
            final_output = str(e)

        finally:
            self._autonomous_running = False

        # Build final result
        result = {
            "success": stop_reason in ["complete", "max_iterations"],
            "is_complete": is_complete,
            "total_iterations": self._autonomous_iteration,
            "original_request": self._original_request,
            "final_output": final_output,
            "all_outputs": all_outputs,
            "stop_reason": stop_reason,
            "total_duration_ms": total_duration_ms
        }

        logger.info(f"[{self.session_id}] 🏁 Autonomous execution finished: {stop_reason} after {self._autonomous_iteration} iterations")
        return result

    def _looks_like_completion(self, output: str) -> bool:
        """
        Heuristic check if output looks like task completion.

        Checks for patterns that suggest the task is done even without
        explicit [TASK_COMPLETE] marker.
        """
        completion_indicators = [
            "successfully completed",
            "all done",
            "task is complete",
            "finished implementing",
            "implementation is complete",
            "all criteria met",
            "all requirements fulfilled",
            "work is done",
        ]

        output_lower = output.lower()
        for indicator in completion_indicators:
            if indicator in output_lower:
                return True

        # If output is very short and doesn't mention more work, might be done
        if len(output) < 500 and "continue" not in output_lower and "next" not in output_lower:
            return False  # Actually, short response without clear completion isn't reliable

        return False

    def is_alive(self) -> bool:
        """Check if session is active."""
        return self.status == SessionStatus.RUNNING
