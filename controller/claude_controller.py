"""
Claude Control API Controller

REST API endpoints for Claude session management.
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path, Query

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
            timeout=request.timeout or 600.0,
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

        return ExecuteResponse(
            success=result.get("success", False),
            session_id=session_id,
            output=result.get("output"),
            error=result.get("error"),
            cost_usd=result.get("cost_usd"),
            duration_ms=result.get("duration_ms")
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
