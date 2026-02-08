"""
Self-Request Manager

Enables sessions to send requests to themselves for continuation,
allowing long-running tasks to be executed without hitting timeout limits.
"""
import asyncio
import logging
import re
from typing import Optional, Callable, Awaitable, Dict, Any
from datetime import datetime

from service.orchestration.models import (
    OrchestrationConfig,
    InterSessionRequest,
    MilestoneStatus,
    TaskStatus
)
from service.orchestration.orchestrator import SessionOrchestrator, get_session_orchestrator

logger = logging.getLogger(__name__)

# Pattern to detect [CONTINUE: ...] in output
CONTINUE_PATTERN = re.compile(r'\[CONTINUE:\s*(.+?)\]', re.IGNORECASE)

# Pattern to detect [TASK_COMPLETE] in output
COMPLETE_PATTERN = re.compile(r'\[TASK_COMPLETE\]', re.IGNORECASE)

# Pattern to detect milestone completion markers
MILESTONE_COMPLETE_PATTERN = re.compile(
    r'\[MILESTONE_COMPLETE:\s*([^\]]+)\]',
    re.IGNORECASE
)


class SelfRequestManager:
    """
    Manages self-request loops for autonomous session execution.

    This enables sessions to work continuously on complex tasks by
    automatically sending follow-up requests when [CONTINUE:] is detected.
    """

    def __init__(
        self,
        orchestrator: Optional[SessionOrchestrator] = None,
        config: Optional[OrchestrationConfig] = None
    ):
        self.orchestrator = orchestrator or get_session_orchestrator()
        self.config = config or OrchestrationConfig()

        # Active self-request loops (session_id -> asyncio.Task)
        self._active_loops: Dict[str, asyncio.Task] = {}

        # Execution function reference (set by the API layer)
        self._execute_func: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None

        logger.info("SelfRequestManager initialized")

    def set_execute_function(
        self,
        func: Callable[..., Awaitable[Dict[str, Any]]]
    ):
        """
        Set the function used to execute prompts.

        This should be the session execution function from the process manager.

        Args:
            func: Async function that takes (session_id, prompt, timeout, system_prompt)
                  and returns execution result dict
        """
        self._execute_func = func
        logger.info("Execute function registered with SelfRequestManager")

    async def start_self_request_loop(
        self,
        session_id: str,
        initial_prompt: str,
        timeout: float = 300.0,
        system_prompt: Optional[str] = None,
        task_id: Optional[str] = None,
        on_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_continue: Optional[Callable[[str, str], None]] = None
    ) -> str:
        """
        Start a self-request loop for autonomous task execution.

        The loop will continue executing until:
        1. [TASK_COMPLETE] is detected
        2. Max auto-continues is reached
        3. An error occurs
        4. The loop is manually stopped

        Args:
            session_id: The session to run the loop in
            initial_prompt: The initial prompt to start with
            timeout: Timeout for each request
            system_prompt: System prompt to use
            task_id: Optional task ID for tracking
            on_complete: Callback when task completes
            on_continue: Callback when continue is detected (hint, output)

        Returns:
            The task ID (auto-generated if not provided)
        """
        if session_id in self._active_loops:
            logger.warning(f"Self-request loop already active for session {session_id}")
            return task_id or ""

        if not self._execute_func:
            raise ValueError("Execute function not set. Call set_execute_function first.")

        task_id = task_id or f"self-request-{session_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        async def _loop():
            continue_count = 0
            current_prompt = initial_prompt
            last_output = ""

            logger.info(f"[{session_id}] Starting self-request loop for task {task_id}")

            while continue_count < self.config.max_auto_continues:
                try:
                    # Execute the current prompt
                    result = await self._execute_func(
                        session_id=session_id,
                        prompt=current_prompt,
                        timeout=timeout,
                        system_prompt=system_prompt
                    )

                    if not result.get("success", False):
                        logger.error(f"[{session_id}] Execution failed: {result.get('error')}")
                        break

                    output = result.get("output", "")
                    last_output = output

                    # Check for task completion
                    if COMPLETE_PATTERN.search(output):
                        logger.info(f"[{session_id}] Task complete detected")
                        if on_complete:
                            on_complete(result)
                        break

                    # Check for milestone completion
                    milestone_match = MILESTONE_COMPLETE_PATTERN.search(output)
                    if milestone_match and task_id:
                        milestone_id = milestone_match.group(1).strip()
                        await self.orchestrator.update_milestone_status(
                            task_id=task_id,
                            milestone_id=milestone_id,
                            status=MilestoneStatus.COMPLETED,
                            output=output
                        )

                    # Check for continue signal
                    continue_match = CONTINUE_PATTERN.search(output)
                    if continue_match:
                        continue_hint = continue_match.group(1).strip()
                        continue_count += 1

                        logger.info(
                            f"[{session_id}] Continue #{continue_count}: {continue_hint}"
                        )

                        if on_continue:
                            on_continue(continue_hint, output)

                        # Build continuation prompt
                        current_prompt = self._build_continuation_prompt(
                            continue_hint,
                            task_id
                        )

                        # Small delay between requests to avoid overwhelming
                        await asyncio.sleep(self.config.continue_delay_ms / 1000.0)
                    else:
                        # No continue signal and no completion - task may be stuck
                        logger.warning(
                            f"[{session_id}] No continue signal detected, stopping loop"
                        )
                        break

                except asyncio.CancelledError:
                    logger.info(f"[{session_id}] Self-request loop cancelled")
                    raise
                except Exception as e:
                    logger.error(f"[{session_id}] Self-request loop error: {e}")
                    break

            logger.info(
                f"[{session_id}] Self-request loop ended after {continue_count} continues"
            )

            # Cleanup
            self._active_loops.pop(session_id, None)

        # Start the loop as a background task
        loop_task = asyncio.create_task(_loop())
        self._active_loops[session_id] = loop_task

        return task_id

    async def stop_self_request_loop(self, session_id: str):
        """Stop an active self-request loop."""
        loop_task = self._active_loops.pop(session_id, None)
        if loop_task:
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
            logger.info(f"[{session_id}] Self-request loop stopped")

    def is_loop_active(self, session_id: str) -> bool:
        """Check if a self-request loop is active for a session."""
        return session_id in self._active_loops

    def _build_continuation_prompt(
        self,
        continue_hint: str,
        task_id: Optional[str] = None
    ) -> str:
        """
        Build a continuation prompt based on the continue hint.

        Args:
            continue_hint: The hint from [CONTINUE: ...]
            task_id: Optional task ID for context

        Returns:
            The continuation prompt
        """
        prompt = f"""Continue with: {continue_hint}

Remember:
- You are continuing the previous task
- Read any TASK_PLAN.md or progress files to understand the current state
- Follow the CPEV cycle (Check, Plan, Execute, Verify)
- Output [CONTINUE: next_action] if more work is needed
- Output [TASK_COMPLETE] when all work is verified complete
- Output [MILESTONE_COMPLETE: milestone_id] when a milestone is finished
"""

        if task_id:
            prompt += f"\n[TASK_ID: {task_id}]"

        return prompt

    async def execute_task_plan(
        self,
        session_id: str,
        task_id: str,
        system_prompt: Optional[str] = None,
        on_milestone_complete: Optional[Callable[[str, Dict], None]] = None
    ):
        """
        Execute a task plan through its milestones using self-requests.

        This method orchestrates the execution of milestones one by one,
        handling retries and dependencies automatically.

        Args:
            session_id: The session to execute in
            task_id: The task plan ID
            system_prompt: System prompt to use
            on_milestone_complete: Callback when a milestone completes
        """
        task = await self.orchestrator.get_task_plan(task_id)
        if not task:
            raise ValueError(f"Task plan {task_id} not found")

        if not self._execute_func:
            raise ValueError("Execute function not set")

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        task.add_progress_log("execution_started")

        while not task.is_complete():
            # Get next milestone
            milestone_info = await self.orchestrator.get_next_milestone_prompt(task_id)
            if not milestone_info:
                logger.warning(f"[{task_id}] No ready milestone found")
                break

            milestone_id = milestone_info["milestone_id"]
            prompt = milestone_info["prompt"]
            timeout = milestone_info["timeout"]

            # Update milestone status
            await self.orchestrator.update_milestone_status(
                task_id=task_id,
                milestone_id=milestone_id,
                status=MilestoneStatus.IN_PROGRESS
            )

            logger.info(f"[{task_id}] Executing milestone: {milestone_id}")

            # Execute milestone with self-request loop for continuation
            try:
                result = await self._execute_func(
                    session_id=session_id,
                    prompt=prompt,
                    timeout=timeout,
                    system_prompt=system_prompt
                )

                if result.get("success"):
                    output = result.get("output", "")

                    # Handle continuation within milestone
                    continue_count = 0
                    while CONTINUE_PATTERN.search(output) and not MILESTONE_COMPLETE_PATTERN.search(output):
                        continue_count += 1
                        if continue_count > 10:  # Max continues per milestone
                            break

                        continue_match = CONTINUE_PATTERN.search(output)
                        continue_hint = continue_match.group(1).strip()

                        continuation_prompt = self._build_continuation_prompt(
                            continue_hint, task_id
                        )

                        await asyncio.sleep(self.config.continue_delay_ms / 1000.0)

                        result = await self._execute_func(
                            session_id=session_id,
                            prompt=continuation_prompt,
                            timeout=timeout,
                            system_prompt=system_prompt
                        )

                        if not result.get("success"):
                            break
                        output = result.get("output", "")

                    # Mark milestone complete
                    await self.orchestrator.update_milestone_status(
                        task_id=task_id,
                        milestone_id=milestone_id,
                        status=MilestoneStatus.COMPLETED,
                        output=output
                    )

                    if on_milestone_complete:
                        on_milestone_complete(milestone_id, result)

                else:
                    # Handle failure with retry
                    task = await self.orchestrator.get_task_plan(task_id)
                    for m in task.milestones:
                        if m.milestone_id == milestone_id:
                            m.retry_count += 1
                            if m.retry_count >= m.max_retries:
                                await self.orchestrator.update_milestone_status(
                                    task_id=task_id,
                                    milestone_id=milestone_id,
                                    status=MilestoneStatus.FAILED,
                                    error=result.get("error")
                                )
                            else:
                                # Reset for retry
                                m.status = MilestoneStatus.NOT_STARTED
                            break

            except Exception as e:
                logger.error(f"[{task_id}] Error executing milestone {milestone_id}: {e}")
                await self.orchestrator.update_milestone_status(
                    task_id=task_id,
                    milestone_id=milestone_id,
                    status=MilestoneStatus.FAILED,
                    error=str(e)
                )

            # Refresh task state
            task = await self.orchestrator.get_task_plan(task_id)

        # Final status update
        if task.is_complete():
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.add_progress_log("task_completed")
            logger.info(f"[{task_id}] Task completed successfully")
        else:
            task.status = TaskStatus.FAILED
            task.add_progress_log("task_failed")
            logger.warning(f"[{task_id}] Task failed to complete")


# Singleton instance
_self_request_manager: Optional[SelfRequestManager] = None


def get_self_request_manager() -> SelfRequestManager:
    """Get the singleton SelfRequestManager instance."""
    global _self_request_manager
    if _self_request_manager is None:
        _self_request_manager = SelfRequestManager()
    return _self_request_manager
