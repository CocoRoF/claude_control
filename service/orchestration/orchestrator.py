"""
Session Orchestrator

Manages inter-session communication and task orchestration.
Enables manager sessions to coordinate worker sessions for complex tasks.
"""
import asyncio
import logging
import uuid
from typing import Dict, Optional, List, Callable, Any
from datetime import datetime

from service.orchestration.models import (
    SessionRole,
    TaskStatus,
    MilestoneStatus,
    InterSessionRequest,
    InterSessionResponse,
    TaskPlan,
    Milestone,
    OrchestrationConfig,
    SessionOrchestrationState
)

logger = logging.getLogger(__name__)


class SessionOrchestrator:
    """
    Orchestrates communication and task distribution between sessions.

    Key capabilities:
    1. Inter-session communication: Sessions can send requests to each other
    2. Manager-worker hierarchy: Manager sessions can control worker sessions
    3. Task planning: Break complex tasks into milestones for timeout-resilient execution
    4. Self-request: Sessions can queue requests to themselves for continuation
    """

    def __init__(self, config: Optional[OrchestrationConfig] = None):
        self.config = config or OrchestrationConfig()

        # Session states
        self._session_states: Dict[str, SessionOrchestrationState] = {}

        # Request queues (session_id -> list of requests)
        self._request_queues: Dict[str, List[InterSessionRequest]] = {}

        # Active tasks (task_id -> TaskPlan)
        self._active_tasks: Dict[str, TaskPlan] = {}

        # Response callbacks (request_id -> callback)
        self._response_callbacks: Dict[str, Callable[[InterSessionResponse], None]] = {}

        # Locks for thread-safe operations
        self._queue_locks: Dict[str, asyncio.Lock] = {}
        self._task_lock = asyncio.Lock()

        logger.info("SessionOrchestrator initialized")

    # =============================================================================
    # Session State Management
    # =============================================================================

    def register_session(
        self,
        session_id: str,
        role: SessionRole = SessionRole.STANDALONE,
        manager_session_id: Optional[str] = None
    ) -> SessionOrchestrationState:
        """
        Register a session with the orchestrator.

        Args:
            session_id: The session ID to register
            role: The session's role in orchestration
            manager_session_id: ID of the manager session (for workers)

        Returns:
            The created SessionOrchestrationState
        """
        if session_id in self._session_states:
            logger.warning(f"Session {session_id} already registered, updating state")

        state = SessionOrchestrationState(
            session_id=session_id,
            role=role,
            manager_session_id=manager_session_id,
            last_activity=datetime.now()
        )

        self._session_states[session_id] = state
        self._request_queues[session_id] = []
        self._queue_locks[session_id] = asyncio.Lock()

        # If this is a worker, register with the manager
        if role == SessionRole.WORKER and manager_session_id:
            manager_state = self._session_states.get(manager_session_id)
            if manager_state and session_id not in manager_state.worker_session_ids:
                manager_state.worker_session_ids.append(session_id)

        logger.info(f"Registered session {session_id} with role {role.value}")
        return state

    def unregister_session(self, session_id: str):
        """Unregister a session from the orchestrator."""
        state = self._session_states.pop(session_id, None)
        self._request_queues.pop(session_id, None)
        self._queue_locks.pop(session_id, None)

        if state:
            # Remove from manager's worker list
            if state.manager_session_id:
                manager_state = self._session_states.get(state.manager_session_id)
                if manager_state and session_id in manager_state.worker_session_ids:
                    manager_state.worker_session_ids.remove(session_id)

            # Remove workers if this was a manager
            for worker_id in state.worker_session_ids:
                worker_state = self._session_states.get(worker_id)
                if worker_state:
                    worker_state.manager_session_id = None
                    worker_state.role = SessionRole.STANDALONE

        logger.info(f"Unregistered session {session_id}")

    def get_session_state(self, session_id: str) -> Optional[SessionOrchestrationState]:
        """Get the orchestration state for a session."""
        return self._session_states.get(session_id)

    def set_session_role(
        self,
        session_id: str,
        role: SessionRole,
        manager_session_id: Optional[str] = None
    ):
        """
        Change a session's role.

        Args:
            session_id: The session to modify
            role: The new role
            manager_session_id: Manager session ID (required if role is WORKER)
        """
        state = self._session_states.get(session_id)
        if not state:
            state = self.register_session(session_id, role, manager_session_id)
            return

        # Update old manager if changing
        if state.manager_session_id and state.manager_session_id != manager_session_id:
            old_manager = self._session_states.get(state.manager_session_id)
            if old_manager and session_id in old_manager.worker_session_ids:
                old_manager.worker_session_ids.remove(session_id)

        state.role = role
        state.manager_session_id = manager_session_id

        # Register with new manager
        if role == SessionRole.WORKER and manager_session_id:
            manager_state = self._session_states.get(manager_session_id)
            if manager_state and session_id not in manager_state.worker_session_ids:
                manager_state.worker_session_ids.append(session_id)

        logger.info(f"Session {session_id} role changed to {role.value}")

    # =============================================================================
    # Inter-Session Communication
    # =============================================================================

    async def send_request(
        self,
        source_session_id: str,
        target_session_id: str,
        prompt: str,
        timeout: float = 600.0,
        system_prompt: Optional[str] = None,
        max_turns: Optional[int] = None,
        task_id: Optional[str] = None,
        milestone_id: Optional[str] = None,
        callback: Optional[Callable[[InterSessionResponse], None]] = None
    ) -> InterSessionRequest:
        """
        Send a request from one session to another.

        Args:
            source_session_id: The requesting session
            target_session_id: The target session to execute the request
            prompt: The prompt to execute
            timeout: Execution timeout
            system_prompt: Optional system prompt override
            max_turns: Optional max turns
            task_id: Parent task ID (for orchestration)
            milestone_id: Associated milestone ID
            callback: Optional callback for when response is received

        Returns:
            The created InterSessionRequest
        """
        if not self.config.enable_inter_session and source_session_id != target_session_id:
            raise ValueError("Inter-session communication is disabled")

        # Ensure target session is registered
        if target_session_id not in self._session_states:
            self.register_session(target_session_id)

        request = InterSessionRequest(
            request_id=str(uuid.uuid4()),
            source_session_id=source_session_id,
            target_session_id=target_session_id,
            prompt=prompt,
            system_prompt=system_prompt,
            timeout=timeout,
            max_turns=max_turns,
            task_id=task_id,
            milestone_id=milestone_id
        )

        # Store callback if provided
        if callback:
            self._response_callbacks[request.request_id] = callback

        # Add to target's queue
        lock = self._queue_locks.get(target_session_id)
        if lock:
            async with lock:
                queue = self._request_queues.get(target_session_id, [])
                if len(queue) >= self.config.max_queue_size:
                    raise ValueError(f"Request queue full for session {target_session_id}")
                queue.append(request)
                self._request_queues[target_session_id] = queue

        logger.info(
            f"Request {request.request_id[:8]} queued: "
            f"{source_session_id[:8]} -> {target_session_id[:8]}"
        )
        return request

    async def send_self_request(
        self,
        session_id: str,
        prompt: str,
        timeout: float = 300.0,
        system_prompt: Optional[str] = None,
        task_id: Optional[str] = None,
        milestone_id: Optional[str] = None
    ) -> InterSessionRequest:
        """
        Send a request from a session to itself (for continuation).

        This enables timeout-resilient long-running tasks by breaking them
        into smaller requests that each fit within timeout limits.

        Args:
            session_id: The session sending the self-request
            prompt: The continuation prompt
            timeout: Execution timeout for this request
            system_prompt: Optional system prompt
            task_id: Parent task ID
            milestone_id: Associated milestone ID

        Returns:
            The created InterSessionRequest
        """
        if not self.config.enable_self_request:
            raise ValueError("Self-request is disabled")

        return await self.send_request(
            source_session_id=session_id,
            target_session_id=session_id,
            prompt=prompt,
            timeout=timeout,
            system_prompt=system_prompt,
            task_id=task_id,
            milestone_id=milestone_id
        )

    async def get_pending_request(
        self,
        session_id: str
    ) -> Optional[InterSessionRequest]:
        """
        Get the next pending request for a session.

        Returns the highest priority pending request, or None if queue is empty.
        """
        lock = self._queue_locks.get(session_id)
        if not lock:
            return None

        async with lock:
            queue = self._request_queues.get(session_id, [])
            if not queue:
                return None

            # Sort by priority (descending) and created_at (ascending)
            queue.sort(key=lambda r: (-r.priority, r.created_at))
            return queue.pop(0)

    async def submit_response(
        self,
        request_id: str,
        source_session_id: str,
        target_session_id: str,
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        should_continue: bool = False,
        continue_hint: Optional[str] = None,
        duration_ms: Optional[int] = None
    ):
        """
        Submit a response for a completed request.

        Args:
            request_id: The original request ID
            source_session_id: The session that made the request
            target_session_id: The session that executed the request
            success: Whether execution succeeded
            output: Execution output
            error: Error message if failed
            should_continue: Whether [CONTINUE:] was detected
            continue_hint: The continue hint extracted from output
            duration_ms: Execution duration
        """
        response = InterSessionResponse(
            request_id=request_id,
            source_session_id=source_session_id,
            target_session_id=target_session_id,
            success=success,
            output=output,
            error=error,
            should_continue=should_continue,
            continue_hint=continue_hint,
            duration_ms=duration_ms
        )

        # Update session state
        state = self._session_states.get(target_session_id)
        if state:
            state.is_busy = False
            state.last_activity = datetime.now()
            if should_continue:
                state.continue_count += 1
                state.last_continue_hint = continue_hint

        # Invoke callback if registered
        callback = self._response_callbacks.pop(request_id, None)
        if callback:
            try:
                callback(response)
            except Exception as e:
                logger.error(f"Error in response callback: {e}")

        logger.info(
            f"Response for {request_id[:8]}: success={success}, "
            f"continue={should_continue}"
        )

        return response

    # =============================================================================
    # Task Planning
    # =============================================================================

    async def create_task_plan(
        self,
        session_id: str,
        name: str,
        original_prompt: str,
        milestones: List[Dict[str, Any]],
        success_criteria: Optional[List[str]] = None,
        manager_session_id: Optional[str] = None
    ) -> TaskPlan:
        """
        Create a task plan with milestones.

        Args:
            session_id: The session that will execute the task
            name: Task name
            original_prompt: The original user prompt
            milestones: List of milestone definitions
            success_criteria: List of success criteria
            manager_session_id: Optional manager session ID

        Returns:
            The created TaskPlan
        """
        task_id = str(uuid.uuid4())

        milestone_objects = []
        for i, m in enumerate(milestones):
            milestone = Milestone(
                milestone_id=m.get("id") or f"M{i+1}",
                name=m.get("name", f"Milestone {i+1}"),
                description=m.get("description", ""),
                prompt_template=m.get("prompt_template", ""),
                timeout=min(
                    m.get("timeout", self.config.default_milestone_timeout),
                    self.config.max_milestone_timeout
                ),
                max_retries=m.get("max_retries", self.config.default_max_retries),
                depends_on=m.get("depends_on", [])
            )
            milestone_objects.append(milestone)

        task = TaskPlan(
            task_id=task_id,
            name=name,
            original_prompt=original_prompt,
            session_id=session_id,
            manager_session_id=manager_session_id,
            milestones=milestone_objects,
            success_criteria=success_criteria or [],
            criteria_met=[False] * len(success_criteria or [])
        )
        task.add_progress_log("task_created", {"milestones": len(milestone_objects)})

        async with self._task_lock:
            self._active_tasks[task_id] = task

        # Update session state
        state = self._session_states.get(session_id)
        if state:
            state.active_task_id = task_id

        logger.info(f"Created task plan {task_id[:8]} with {len(milestone_objects)} milestones")
        return task

    async def get_task_plan(self, task_id: str) -> Optional[TaskPlan]:
        """Get a task plan by ID."""
        return self._active_tasks.get(task_id)

    async def update_milestone_status(
        self,
        task_id: str,
        milestone_id: str,
        status: MilestoneStatus,
        output: Optional[str] = None,
        error: Optional[str] = None
    ):
        """Update the status of a milestone."""
        task = self._active_tasks.get(task_id)
        if not task:
            logger.warning(f"Task {task_id} not found")
            return

        for milestone in task.milestones:
            if milestone.milestone_id == milestone_id:
                milestone.status = status
                if status == MilestoneStatus.IN_PROGRESS:
                    milestone.started_at = datetime.now()
                elif status in (MilestoneStatus.COMPLETED, MilestoneStatus.FAILED):
                    milestone.completed_at = datetime.now()
                if output:
                    milestone.output = output
                if error:
                    milestone.error = error
                break

        task.add_progress_log(
            f"milestone_{status.value}",
            {"milestone_id": milestone_id}
        )

        # Check if task is complete
        if task.is_complete():
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.add_progress_log("task_completed")

        logger.info(f"Milestone {milestone_id} status: {status.value}")

    async def get_next_milestone_prompt(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the prompt for the next milestone to execute.

        Returns:
            Dict with milestone_id, prompt, and timeout, or None if no milestone is ready
        """
        task = self._active_tasks.get(task_id)
        if not task:
            return None

        next_milestone = task.get_next_milestone()
        if not next_milestone:
            return None

        # Build the prompt with context
        prompt = f"""[MILESTONE: {next_milestone.name}]
[MILESTONE_ID: {next_milestone.milestone_id}]
[TASK_ID: {task_id}]

{next_milestone.prompt_template}

---
Task Context:
- Task: {task.name}
- Completed milestones: {task.get_completed_milestone_ids()}
- Progress: {len(task.get_completed_milestone_ids())}/{len(task.milestones)}
"""

        return {
            "milestone_id": next_milestone.milestone_id,
            "prompt": prompt,
            "timeout": next_milestone.timeout
        }

    # =============================================================================
    # Manager Session Operations
    # =============================================================================

    async def assign_task_to_worker(
        self,
        manager_session_id: str,
        worker_session_id: str,
        prompt: str,
        timeout: float = 600.0,
        system_prompt: Optional[str] = None
    ) -> InterSessionRequest:
        """
        Assign a task from a manager to a worker session.

        Args:
            manager_session_id: The manager session
            worker_session_id: The worker session to assign to
            prompt: The task prompt
            timeout: Execution timeout
            system_prompt: Optional system prompt

        Returns:
            The created request
        """
        manager_state = self._session_states.get(manager_session_id)
        if not manager_state or manager_state.role != SessionRole.MANAGER:
            raise ValueError(f"Session {manager_session_id} is not a manager")

        worker_state = self._session_states.get(worker_session_id)
        if not worker_state:
            # Auto-register as worker
            self.register_session(
                worker_session_id,
                SessionRole.WORKER,
                manager_session_id
            )
        elif worker_state.manager_session_id != manager_session_id:
            raise ValueError(
                f"Worker {worker_session_id} is assigned to another manager"
            )

        return await self.send_request(
            source_session_id=manager_session_id,
            target_session_id=worker_session_id,
            prompt=prompt,
            timeout=timeout,
            system_prompt=system_prompt
        )

    async def broadcast_to_workers(
        self,
        manager_session_id: str,
        prompt: str,
        timeout: float = 600.0,
        system_prompt: Optional[str] = None
    ) -> List[InterSessionRequest]:
        """
        Send the same request to all worker sessions.

        Args:
            manager_session_id: The manager session
            prompt: The prompt to broadcast
            timeout: Execution timeout
            system_prompt: Optional system prompt

        Returns:
            List of created requests
        """
        manager_state = self._session_states.get(manager_session_id)
        if not manager_state or manager_state.role != SessionRole.MANAGER:
            raise ValueError(f"Session {manager_session_id} is not a manager")

        requests = []
        for worker_id in manager_state.worker_session_ids:
            try:
                req = await self.send_request(
                    source_session_id=manager_session_id,
                    target_session_id=worker_id,
                    prompt=prompt,
                    timeout=timeout,
                    system_prompt=system_prompt
                )
                requests.append(req)
            except Exception as e:
                logger.error(f"Failed to send to worker {worker_id}: {e}")

        return requests

    def get_worker_statuses(self, manager_session_id: str) -> Dict[str, Dict[str, Any]]:
        """Get status of all workers for a manager session."""
        manager_state = self._session_states.get(manager_session_id)
        if not manager_state:
            return {}

        statuses = {}
        for worker_id in manager_state.worker_session_ids:
            worker_state = self._session_states.get(worker_id)
            if worker_state:
                statuses[worker_id] = {
                    "is_busy": worker_state.is_busy,
                    "active_task_id": worker_state.active_task_id,
                    "pending_requests": len(self._request_queues.get(worker_id, [])),
                    "continue_count": worker_state.continue_count,
                    "last_activity": worker_state.last_activity.isoformat() if worker_state.last_activity else None
                }
        return statuses


# Singleton instance
_orchestrator: Optional[SessionOrchestrator] = None


def get_session_orchestrator() -> SessionOrchestrator:
    """Get the singleton SessionOrchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = SessionOrchestrator()
    return _orchestrator
