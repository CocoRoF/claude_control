"""
Orchestration API Controller

REST API endpoints for inter-session communication, task orchestration,
and self-request management.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field

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
from service.orchestration.orchestrator import get_session_orchestrator
from service.orchestration.self_request import get_self_request_manager
from service.claude_manager.session_manager import get_session_manager

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

# Get managers
orchestrator = get_session_orchestrator()
self_request_manager = get_self_request_manager()
session_manager = get_session_manager()


# =============================================================================
# Request/Response Models
# =============================================================================

class SetRoleRequest(BaseModel):
    """Request to set a session's role."""
    role: SessionRole
    manager_session_id: Optional[str] = None


class SendRequestPayload(BaseModel):
    """Payload for sending an inter-session request."""
    prompt: str = Field(..., description="Prompt to execute")
    timeout: float = Field(default=1800.0, description="Execution timeout")
    system_prompt: Optional[str] = Field(default=None)
    max_turns: Optional[int] = Field(default=None)
    task_id: Optional[str] = Field(default=None)
    milestone_id: Optional[str] = Field(default=None)
    priority: int = Field(default=0)


class CreateTaskPlanRequest(BaseModel):
    """Request to create a task plan."""
    name: str = Field(..., description="Task name")
    original_prompt: str = Field(..., description="Original user prompt")
    milestones: List[Dict[str, Any]] = Field(..., description="Milestone definitions")
    success_criteria: Optional[List[str]] = Field(default=None)
    manager_session_id: Optional[str] = Field(default=None)


class StartSelfRequestLoopRequest(BaseModel):
    """Request to start a self-request loop."""
    initial_prompt: str = Field(..., description="Initial prompt")
    timeout: float = Field(default=1800.0, description="Timeout per request")
    system_prompt: Optional[str] = Field(default=None)
    task_id: Optional[str] = Field(default=None)


class ExecuteTaskPlanRequest(BaseModel):
    """Request to execute a task plan."""
    task_id: str = Field(..., description="Task plan ID to execute")
    system_prompt: Optional[str] = Field(default=None)


class ConfigUpdateRequest(BaseModel):
    """Request to update orchestration config."""
    enable_self_request: Optional[bool] = None
    default_milestone_timeout: Optional[float] = None
    max_milestone_timeout: Optional[float] = None
    auto_continue_on_signal: Optional[bool] = None
    max_auto_continues: Optional[int] = None
    continue_delay_ms: Optional[int] = None
    enable_inter_session: Optional[bool] = None
    inter_session_timeout: Optional[float] = None


# =============================================================================
# Session Role Management
# =============================================================================

@router.post("/sessions/{session_id}/role")
async def set_session_role(
    session_id: str = Path(..., description="Session ID"),
    request: SetRoleRequest = Body(...)
):
    """
    Set the orchestration role for a session.

    Roles:
    - MANAGER: Can control worker sessions, distribute tasks
    - WORKER: Executes tasks assigned by a manager
    - STANDALONE: Independent session (default)
    """
    try:
        # Verify session exists
        session = session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        # Validate manager if setting as worker
        if request.role == SessionRole.WORKER and request.manager_session_id:
            manager_session = session_manager.get_session_info(request.manager_session_id)
            if not manager_session:
                raise HTTPException(
                    status_code=404,
                    detail=f"Manager session not found: {request.manager_session_id}"
                )

        orchestrator.set_session_role(
            session_id=session_id,
            role=request.role,
            manager_session_id=request.manager_session_id
        )

        state = orchestrator.get_session_state(session_id)
        return {
            "success": True,
            "session_id": session_id,
            "role": request.role.value,
            "state": state.model_dump() if state else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set session role: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/state")
async def get_session_state(
    session_id: str = Path(..., description="Session ID")
):
    """Get the orchestration state for a session."""
    state = orchestrator.get_session_state(session_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"Session not registered with orchestrator: {session_id}"
        )
    return state.model_dump()


@router.get("/sessions/{session_id}/workers")
async def get_worker_statuses(
    session_id: str = Path(..., description="Manager session ID")
):
    """Get status of all workers for a manager session."""
    state = orchestrator.get_session_state(session_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if state.role != SessionRole.MANAGER:
        raise HTTPException(
            status_code=400,
            detail=f"Session {session_id} is not a manager"
        )

    return orchestrator.get_worker_statuses(session_id)


# =============================================================================
# Inter-Session Communication
# =============================================================================

@router.post("/sessions/{source_id}/send/{target_id}")
async def send_inter_session_request(
    source_id: str = Path(..., description="Source session ID"),
    target_id: str = Path(..., description="Target session ID"),
    payload: SendRequestPayload = Body(...)
):
    """
    Send a request from one session to another.

    This enables manager sessions to delegate tasks to workers,
    or allows peer-to-peer communication between sessions.
    """
    try:
        # Verify both sessions exist
        source_session = session_manager.get_session_info(source_id)
        if not source_session:
            raise HTTPException(status_code=404, detail=f"Source session not found: {source_id}")

        target_session = session_manager.get_session_info(target_id)
        if not target_session:
            raise HTTPException(status_code=404, detail=f"Target session not found: {target_id}")

        # Register sessions if not already registered
        if not orchestrator.get_session_state(source_id):
            orchestrator.register_session(source_id)
        if not orchestrator.get_session_state(target_id):
            orchestrator.register_session(target_id)

        request = await orchestrator.send_request(
            source_session_id=source_id,
            target_session_id=target_id,
            prompt=payload.prompt,
            timeout=payload.timeout,
            system_prompt=payload.system_prompt,
            max_turns=payload.max_turns,
            task_id=payload.task_id,
            milestone_id=payload.milestone_id
        )

        return {
            "success": True,
            "request_id": request.request_id,
            "source_session_id": source_id,
            "target_session_id": target_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send inter-session request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/self-request")
async def send_self_request(
    session_id: str = Path(..., description="Session ID"),
    payload: SendRequestPayload = Body(...)
):
    """
    Send a request from a session to itself.

    This enables continuation of long-running tasks by queueing
    follow-up requests that will be executed after the current one.
    """
    try:
        session = session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        if not orchestrator.get_session_state(session_id):
            orchestrator.register_session(session_id)

        request = await orchestrator.send_self_request(
            session_id=session_id,
            prompt=payload.prompt,
            timeout=payload.timeout,
            system_prompt=payload.system_prompt,
            task_id=payload.task_id,
            milestone_id=payload.milestone_id
        )

        return {
            "success": True,
            "request_id": request.request_id,
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send self-request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/pending")
async def get_pending_requests(
    session_id: str = Path(..., description="Session ID")
):
    """Get pending requests for a session."""
    request = await orchestrator.get_pending_request(session_id)
    if request:
        return {
            "has_pending": True,
            "request": request.model_dump()
        }
    return {"has_pending": False, "request": None}


@router.post("/sessions/{manager_id}/broadcast")
async def broadcast_to_workers(
    manager_id: str = Path(..., description="Manager session ID"),
    payload: SendRequestPayload = Body(...)
):
    """
    Broadcast a request to all worker sessions.

    Only available for manager sessions.
    """
    try:
        state = orchestrator.get_session_state(manager_id)
        if not state or state.role != SessionRole.MANAGER:
            raise HTTPException(
                status_code=400,
                detail=f"Session {manager_id} is not a manager"
            )

        requests = await orchestrator.broadcast_to_workers(
            manager_session_id=manager_id,
            prompt=payload.prompt,
            timeout=payload.timeout,
            system_prompt=payload.system_prompt
        )

        return {
            "success": True,
            "manager_session_id": manager_id,
            "requests_sent": len(requests),
            "request_ids": [r.request_id for r in requests]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to broadcast: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Task Planning
# =============================================================================

@router.post("/sessions/{session_id}/tasks")
async def create_task_plan(
    session_id: str = Path(..., description="Session ID"),
    request: CreateTaskPlanRequest = Body(...)
):
    """
    Create a task plan with milestones.

    Task plans enable long-running tasks to be executed as a series
    of smaller operations, avoiding timeout issues.
    """
    try:
        session = session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        if not orchestrator.get_session_state(session_id):
            orchestrator.register_session(session_id)

        task = await orchestrator.create_task_plan(
            session_id=session_id,
            name=request.name,
            original_prompt=request.original_prompt,
            milestones=request.milestones,
            success_criteria=request.success_criteria,
            manager_session_id=request.manager_session_id
        )

        return {
            "success": True,
            "task_id": task.task_id,
            "name": task.name,
            "milestones_count": len(task.milestones),
            "status": task.status.value
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create task plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}")
async def get_task_plan(
    task_id: str = Path(..., description="Task ID")
):
    """Get a task plan by ID."""
    task = await orchestrator.get_task_plan(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task.model_dump()


@router.patch("/tasks/{task_id}/milestones/{milestone_id}")
async def update_milestone(
    task_id: str = Path(..., description="Task ID"),
    milestone_id: str = Path(..., description="Milestone ID"),
    status: MilestoneStatus = Query(..., description="New status"),
    output: Optional[str] = Body(default=None),
    error: Optional[str] = Body(default=None)
):
    """Update the status of a milestone."""
    try:
        await orchestrator.update_milestone_status(
            task_id=task_id,
            milestone_id=milestone_id,
            status=status,
            output=output,
            error=error
        )
        return {"success": True, "task_id": task_id, "milestone_id": milestone_id, "status": status.value}
    except Exception as e:
        logger.error(f"Failed to update milestone: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/next-milestone")
async def get_next_milestone(
    task_id: str = Path(..., description="Task ID")
):
    """Get the next milestone prompt for execution."""
    milestone_info = await orchestrator.get_next_milestone_prompt(task_id)
    if not milestone_info:
        return {"has_next": False, "milestone": None}
    return {"has_next": True, "milestone": milestone_info}


# =============================================================================
# Self-Request Loop Management
# =============================================================================

@router.post("/sessions/{session_id}/loop/start")
async def start_self_request_loop(
    session_id: str = Path(..., description="Session ID"),
    request: StartSelfRequestLoopRequest = Body(...)
):
    """
    Start a self-request loop for autonomous task execution.

    The loop will continue executing requests until [TASK_COMPLETE]
    is detected or max continues is reached.
    """
    try:
        session = session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        # Set up execute function if not already set
        if not self_request_manager._execute_func:
            async def execute_func(session_id: str, prompt: str, timeout: float, system_prompt: Optional[str] = None):
                process = session_manager.get_process(session_id)
                if not process:
                    return {"success": False, "error": "Session process not found"}
                return await process.execute(
                    prompt=prompt,
                    timeout=timeout,
                    system_prompt=system_prompt
                )
            self_request_manager.set_execute_function(execute_func)

        task_id = await self_request_manager.start_self_request_loop(
            session_id=session_id,
            initial_prompt=request.initial_prompt,
            timeout=request.timeout,
            system_prompt=request.system_prompt,
            task_id=request.task_id
        )

        return {
            "success": True,
            "session_id": session_id,
            "task_id": task_id,
            "message": "Self-request loop started"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start self-request loop: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/loop/stop")
async def stop_self_request_loop(
    session_id: str = Path(..., description="Session ID")
):
    """Stop an active self-request loop."""
    try:
        await self_request_manager.stop_self_request_loop(session_id)
        return {
            "success": True,
            "session_id": session_id,
            "message": "Self-request loop stopped"
        }
    except Exception as e:
        logger.error(f"Failed to stop self-request loop: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/loop/status")
async def get_loop_status(
    session_id: str = Path(..., description="Session ID")
):
    """Check if a self-request loop is active."""
    is_active = self_request_manager.is_loop_active(session_id)
    return {
        "session_id": session_id,
        "is_active": is_active
    }


@router.post("/sessions/{session_id}/execute-task-plan")
async def execute_task_plan(
    session_id: str = Path(..., description="Session ID"),
    request: ExecuteTaskPlanRequest = Body(...)
):
    """
    Execute a task plan through its milestones.

    This will automatically execute each milestone in order,
    handling retries and dependencies.
    """
    try:
        session = session_manager.get_session_info(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        task = await orchestrator.get_task_plan(request.task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task not found: {request.task_id}")

        # Set up execute function if not already set
        if not self_request_manager._execute_func:
            async def execute_func(session_id: str, prompt: str, timeout: float, system_prompt: Optional[str] = None):
                process = session_manager.get_process(session_id)
                if not process:
                    return {"success": False, "error": "Session process not found"}
                return await process.execute(
                    prompt=prompt,
                    timeout=timeout,
                    system_prompt=system_prompt
                )
            self_request_manager.set_execute_function(execute_func)

        # Start execution in background
        import asyncio
        asyncio.create_task(
            self_request_manager.execute_task_plan(
                session_id=session_id,
                task_id=request.task_id,
                system_prompt=request.system_prompt
            )
        )

        return {
            "success": True,
            "session_id": session_id,
            "task_id": request.task_id,
            "message": "Task plan execution started"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to execute task plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Configuration
# =============================================================================

@router.get("/config")
async def get_orchestration_config():
    """Get current orchestration configuration."""
    return orchestrator.config.model_dump()


@router.patch("/config")
async def update_orchestration_config(
    request: ConfigUpdateRequest = Body(...)
):
    """Update orchestration configuration."""
    try:
        config = orchestrator.config
        update_data = request.model_dump(exclude_unset=True)

        for key, value in update_data.items():
            if value is not None:
                setattr(config, key, value)

        return {
            "success": True,
            "config": config.model_dump()
        }
    except Exception as e:
        logger.error(f"Failed to update config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
