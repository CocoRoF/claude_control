"""
Claude Control API Controller

REST API endpoints for Claude session management.
"""
import re
import logging
from typing import List
from fastapi import APIRouter, HTTPException, Path, Query

# Pattern to detect auto-continue signal from self-manager
CONTINUE_PATTERN = re.compile(r'\[CONTINUE:\s*(.+?)\]', re.IGNORECASE)
COMPLETE_PATTERN = re.compile(r'\[TASK_COMPLETE\]', re.IGNORECASE)

from service.claude_manager.models import (
    CreateSessionRequest,
    SessionInfo,
    ExecuteRequest,
    ExecuteResponse,
    StorageFile,
    StorageListResponse,
    StorageFileContent,
    AutonomousExecuteRequest,
    AutonomousExecuteResponse
)
from service.claude_manager.session_manager import get_session_manager
from service.logging.session_logger import get_session_logger

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Singleton session manager
session_manager = get_session_manager()


# ========== Session Management API ==========

@router.post("", response_model=SessionInfo)
async def create_session(request: CreateSessionRequest):
    """
    Create a new Claude session.

    Creates a new session to run Claude Code.
    Each session has its own independent storage directory.
    """
    try:
        session = await session_manager.create_session(request)
        logger.info(f"✅ Session created: {session.session_id}")
        return session
    except Exception as e:
        logger.error(f"❌ Failed to create session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[SessionInfo])
async def list_sessions():
    """
    List all sessions.

    In multi-pod environments, returns sessions from all pods.
    """
    return session_manager.list_sessions()


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get specific session information.
    """
    session = session_manager.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str = Path(..., description="Session ID"),
    cleanup_storage: bool = Query(True, description="Also delete storage")
):
    """
    Delete session.

    Terminates the session and cleans up related resources.
    """
    success = await session_manager.delete_session(session_id, cleanup_storage)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    logger.info(f"✅ Session deleted: {session_id}")
    return {"success": True, "session_id": session_id}


# ========== Claude Execution API ==========

@router.post("/{session_id}/execute", response_model=ExecuteResponse)
async def execute_prompt(
    session_id: str = Path(..., description="Session ID"),
    request: ExecuteRequest = ...
):
    """
    Execute prompt with Claude.

    Sends a prompt to Claude in the session and returns the result.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Session is not running (status: {process.status})"
        )

    # Get session logger
    session_logger = get_session_logger(session_id, create_if_missing=False)

    try:
        # Log the command
        if session_logger:
            session_logger.log_command(
                prompt=request.prompt,
                timeout=request.timeout,
                system_prompt=request.system_prompt,
                max_turns=request.max_turns
            )

        result = await process.execute(
            prompt=request.prompt,
            timeout=request.timeout or process.timeout,  # Use session default if not specified
            skip_permissions=request.skip_permissions,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns or process.max_turns  # Use session default if not specified
        )

        # Log the response
        if session_logger:
            session_logger.log_response(
                success=result.get("success", False),
                output=result.get("output"),
                error=result.get("error"),
                duration_ms=result.get("duration_ms"),
                cost_usd=result.get("cost_usd")
            )

        # Detect CONTINUE pattern for auto-continue mode
        output = result.get("output") or ""
        should_continue = False
        continue_hint = None
        is_task_complete = False

        continue_match = CONTINUE_PATTERN.search(output)
        if continue_match and result.get("success", False):
            should_continue = True
            continue_hint = continue_match.group(1).strip()
            logger.info(f"[{session_id}] 🔄 Auto-continue detected: {continue_hint}")

        # Detect TASK_COMPLETE pattern
        if COMPLETE_PATTERN.search(output) and result.get("success", False):
            is_task_complete = True
            should_continue = False
            logger.info(f"[{session_id}] ✅ Task complete detected")

        return ExecuteResponse(
            success=result.get("success", False),
            session_id=session_id,
            output=output,
            error=result.get("error"),
            cost_usd=result.get("cost_usd"),
            duration_ms=result.get("duration_ms"),
            should_continue=should_continue,
            continue_hint=continue_hint,
            is_task_complete=is_task_complete
        )
    except Exception as e:
        logger.error(f"❌ Execution failed: {e}", exc_info=True)
        if session_logger:
            session_logger.error(f"Execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ========== Autonomous Execution API ==========

@router.post("/{session_id}/execute/autonomous", response_model=AutonomousExecuteResponse)
async def execute_autonomous(
    session_id: str = Path(..., description="Session ID"),
    request: AutonomousExecuteRequest = ...
):
    """
    Execute a task autonomously with self-managing loop.

    This endpoint starts an autonomous execution loop where Claude will:
    1. Work on the user's request
    2. Continue automatically until the task is complete
    3. Periodically remind itself of the original request
    4. Self-verify completion before stopping

    The loop continues until:
    - Claude outputs [TASK_COMPLETE]
    - Maximum iterations are reached
    - An error occurs
    - The user stops it via /execute/autonomous/stop

    This is a blocking call that returns when the autonomous execution completes.
    For long-running tasks, consider using a longer timeout or monitoring via
    /execute/autonomous/status endpoint.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Session is not running (status: {process.status})"
        )

    # Check if autonomous execution is already running
    if process.autonomous_state.get("is_running"):
        raise HTTPException(
            status_code=409,
            detail="Autonomous execution already in progress"
        )

    session_logger = get_session_logger(session_id, create_if_missing=False)

    try:
        if session_logger:
            session_logger.log_command(
                prompt=f"[AUTONOMOUS] {request.prompt}",
                timeout=request.timeout_per_iteration,
                system_prompt=request.system_prompt,
                max_turns=request.max_turns
            )

        logger.info(f"[{session_id}] 🚀 Starting autonomous execution...")

        result = await process.execute_autonomous(
            prompt=request.prompt,
            timeout_per_iteration=request.timeout_per_iteration or process.timeout,  # Use session default
            max_iterations=request.max_iterations or process.autonomous_max_iterations,  # Use session default
            skip_permissions=request.skip_permissions,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns or process.max_turns  # Use session default
        )

        if session_logger:
            session_logger.log_response(
                success=result.get("success", False),
                output=f"[Autonomous: {result.get('total_iterations', 0)} iterations] {result.get('final_output', '')[:500]}",
                error=None if result.get("success") else result.get("stop_reason"),
                duration_ms=result.get("total_duration_ms")
            )

        return AutonomousExecuteResponse(
            success=result.get("success", False),
            session_id=session_id,
            is_complete=result.get("is_complete", False),
            total_iterations=result.get("total_iterations", 0),
            original_request=result.get("original_request", request.prompt),
            final_output=result.get("final_output"),
            all_outputs=result.get("all_outputs"),
            error=None if result.get("success") else result.get("stop_reason"),
            total_duration_ms=result.get("total_duration_ms"),
            stop_reason=result.get("stop_reason", "unknown")
        )

    except Exception as e:
        logger.error(f"❌ Autonomous execution failed: {e}", exc_info=True)
        if session_logger:
            session_logger.error(f"Autonomous execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{session_id}/execute/autonomous/stop")
async def stop_autonomous_execution(
    session_id: str = Path(..., description="Session ID")
):
    """
    Stop the autonomous execution loop.

    Gracefully stops the autonomous execution after the current iteration completes.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not process.autonomous_state.get("is_running"):
        raise HTTPException(
            status_code=400,
            detail="No autonomous execution in progress"
        )

    process.stop_autonomous()
    logger.info(f"[{session_id}] 🛑 Autonomous execution stop requested")

    return {
        "success": True,
        "message": "Autonomous execution will stop after current iteration",
        "current_iteration": process.autonomous_state.get("iteration", 0)
    }


@router.get("/{session_id}/execute/autonomous/status")
async def get_autonomous_status(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get the current autonomous execution status.

    Returns the current state of autonomous execution including:
    - Whether it's running
    - Current iteration count
    - Original request
    - Whether stop was requested
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    state = process.autonomous_state
    return {
        "session_id": session_id,
        "is_running": state.get("is_running", False),
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 100),
        "original_request": state.get("original_request"),
        "stop_requested": state.get("stop_requested", False)
    }


# ========== Storage API ==========

@router.get("/{session_id}/storage", response_model=StorageListResponse)
async def list_storage_files(
    session_id: str = Path(..., description="Session ID"),
    path: str = Query("", description="Subdirectory path")
):
    """
    List session storage files.

    Returns file list from session-specific storage.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    files_data = process.list_storage_files(path)
    files = [StorageFile(**f) for f in files_data]

    return StorageListResponse(
        session_id=session_id,
        storage_path=process.storage_path,
        files=files
    )


@router.get("/{session_id}/storage/{file_path:path}", response_model=StorageFileContent)
async def read_storage_file(
    session_id: str = Path(..., description="Session ID"),
    file_path: str = Path(..., description="File path"),
    encoding: str = Query("utf-8", description="File encoding")
):
    """
    Read storage file content.

    Returns content of a specific file from session storage.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    file_content = process.read_storage_file(file_path, encoding)
    if not file_content:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    return StorageFileContent(
        session_id=session_id,
        **file_content
    )
