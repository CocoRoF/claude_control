"""
Claude Control API Controller

REST API endpoints for Claude session management.
"""
import re
import logging
import asyncio
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path, Query, Body
from pydantic import BaseModel, Field

# Pattern to detect auto-continue signal from self-manager
CONTINUE_PATTERN = re.compile(r'\[CONTINUE:\s*(.+?)\]', re.IGNORECASE)
# Pattern to detect task completion
COMPLETE_PATTERN = re.compile(r'\[TASK_COMPLETE\]', re.IGNORECASE)

from service.claude_manager.models import (
    CreateSessionRequest,
    SessionInfo,
    ExecuteRequest,
    ExecuteResponse,
    StorageFile,
    StorageListResponse,
    StorageFileContent
)
from service.claude_manager.session_manager import SessionManager, get_session_manager
from service.logging.session_logger import get_session_logger
from service.orchestration.orchestrator import get_session_orchestrator
from service.orchestration.self_request import get_self_request_manager

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
            timeout=request.timeout or 1800.0,
            skip_permissions=request.skip_permissions,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns
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

        continue_match = CONTINUE_PATTERN.search(output)
        if continue_match and result.get("success", False):
            should_continue = True
            continue_hint = continue_match.group(1).strip()
            logger.info(f"[{session_id}] 🔄 Auto-continue detected: {continue_hint}")

        return ExecuteResponse(
            success=result.get("success", False),
            session_id=session_id,
            output=output,
            error=result.get("error"),
            cost_usd=result.get("cost_usd"),
            duration_ms=result.get("duration_ms"),
            should_continue=should_continue,
            continue_hint=continue_hint
        )
    except Exception as e:
        logger.error(f"❌ Execution failed: {e}", exc_info=True)
        if session_logger:
            session_logger.error(f"Execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


# =============================================================================
# Extended Execution API with Auto-Continue Support
# =============================================================================

class ExecuteWithContinueRequest(BaseModel):
    """Execute request with auto-continue support."""
    prompt: str = Field(..., description="Prompt to execute")
    timeout: float = Field(default=300.0, description="Timeout per execution (not total)")
    system_prompt: Optional[str] = Field(default=None)
    max_turns: Optional[int] = Field(default=None)
    skip_permissions: bool = Field(default=True)
    auto_continue: bool = Field(default=True, description="Automatically continue on [CONTINUE:]")
    max_continues: int = Field(default=50, description="Maximum number of auto-continues")
    continue_delay_ms: int = Field(default=100, description="Delay between continues (ms)")


class ExecuteWithContinueResponse(BaseModel):
    """Response from execute with auto-continue."""
    success: bool
    session_id: str
    final_output: str = Field(..., description="Final output after all continues")
    total_outputs: List[str] = Field(default_factory=list, description="All outputs in order")
    continue_count: int = Field(default=0, description="Number of continues executed")
    total_duration_ms: int = Field(default=0)
    task_completed: bool = Field(default=False, description="Whether [TASK_COMPLETE] was detected")
    error: Optional[str] = None


@router.post("/{session_id}/execute-continuous", response_model=ExecuteWithContinueResponse)
async def execute_with_auto_continue(
    session_id: str = Path(..., description="Session ID"),
    request: ExecuteWithContinueRequest = Body(...)
):
    """
    Execute prompt with automatic continuation.

    This endpoint automatically continues execution when [CONTINUE:] is detected,
    until [TASK_COMPLETE] is found or max_continues is reached.

    This solves the timeout problem by:
    1. Breaking long tasks into smaller chunks (each within timeout)
    2. Automatically sending continuation requests based on [CONTINUE:] signals
    3. Accumulating all outputs for a complete result

    Use this for self-managing agents that need to work autonomously for
    extended periods without manual intervention.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Session is not running (status: {process.status})"
        )

    all_outputs = []
    continue_count = 0
    total_duration_ms = 0
    task_completed = False
    current_prompt = request.prompt

    try:
        while continue_count <= request.max_continues:
            # Execute current prompt
            result = await process.execute(
                prompt=current_prompt,
                timeout=request.timeout,
                skip_permissions=request.skip_permissions,
                system_prompt=request.system_prompt,
                max_turns=request.max_turns
            )

            duration = result.get("duration_ms", 0)
            total_duration_ms += duration
            output = result.get("output", "")
            all_outputs.append(output)

            if not result.get("success", False):
                return ExecuteWithContinueResponse(
                    success=False,
                    session_id=session_id,
                    final_output=output,
                    total_outputs=all_outputs,
                    continue_count=continue_count,
                    total_duration_ms=total_duration_ms,
                    task_completed=False,
                    error=result.get("error")
                )

            # Check for task completion
            if COMPLETE_PATTERN.search(output):
                task_completed = True
                logger.info(f"[{session_id}] 🎉 Task completed after {continue_count} continues")
                break

            # Check for continue signal
            if not request.auto_continue:
                break

            continue_match = CONTINUE_PATTERN.search(output)
            if not continue_match:
                # No continue signal - task may be stuck or naturally ended
                logger.info(f"[{session_id}] No continue signal detected, stopping")
                break

            continue_hint = continue_match.group(1).strip()
            continue_count += 1

            logger.info(f"[{session_id}] 🔄 Auto-continue #{continue_count}: {continue_hint}")

            # Build continuation prompt
            current_prompt = f"""Continue with: {continue_hint}

Remember:
- Continue from where you left off
- Follow the CPEV cycle (Check, Plan, Execute, Verify)
- Output [CONTINUE: next_action] if more work is needed
- Output [TASK_COMPLETE] when all work is verified complete
"""

            # Small delay between requests
            await asyncio.sleep(request.continue_delay_ms / 1000.0)

        # Combine outputs
        final_output = "\n\n---\n\n".join(all_outputs)

        return ExecuteWithContinueResponse(
            success=True,
            session_id=session_id,
            final_output=final_output,
            total_outputs=all_outputs,
            continue_count=continue_count,
            total_duration_ms=total_duration_ms,
            task_completed=task_completed
        )

    except Exception as e:
        logger.error(f"[{session_id}] Execute-continuous error: {e}", exc_info=True)
        return ExecuteWithContinueResponse(
            success=False,
            session_id=session_id,
            final_output="\n\n".join(all_outputs) if all_outputs else "",
            total_outputs=all_outputs,
            continue_count=continue_count,
            total_duration_ms=total_duration_ms,
            task_completed=False,
            error=str(e)
        )


# =============================================================================
# Process Pending Requests (for inter-session communication)
# =============================================================================

@router.post("/{session_id}/process-pending")
async def process_pending_requests(
    session_id: str = Path(..., description="Session ID"),
    max_requests: int = Query(default=1, description="Max requests to process")
):
    """
    Process pending inter-session requests.

    This endpoint checks for and executes pending requests
    that have been sent to this session from other sessions.
    """
    orchestrator = get_session_orchestrator()

    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if not process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Session is not running (status: {process.status})"
        )

    results = []
    for _ in range(max_requests):
        # Get next pending request
        request = await orchestrator.get_pending_request(session_id)
        if not request:
            break

        logger.info(f"[{session_id}] Processing request {request.request_id[:8]} from {request.source_session_id[:8]}")

        # Execute the request
        result = await process.execute(
            prompt=request.prompt,
            timeout=request.timeout,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns
        )

        output = result.get("output", "")

        # Check for continue signal
        should_continue = False
        continue_hint = None
        continue_match = CONTINUE_PATTERN.search(output)
        if continue_match and result.get("success", False):
            should_continue = True
            continue_hint = continue_match.group(1).strip()

        # Submit response
        await orchestrator.submit_response(
            request_id=request.request_id,
            source_session_id=request.source_session_id,
            target_session_id=session_id,
            success=result.get("success", False),
            output=output,
            error=result.get("error"),
            should_continue=should_continue,
            continue_hint=continue_hint,
            duration_ms=result.get("duration_ms")
        )

        results.append({
            "request_id": request.request_id,
            "success": result.get("success", False),
            "should_continue": should_continue
        })

    return {
        "session_id": session_id,
        "processed_count": len(results),
        "results": results
    }
