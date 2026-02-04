"""
Claude Control API Controller

Claude 세션 관리를 위한 REST API 엔드포인트
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

logger = logging.getLogger(__name__)

# 라우터 생성
router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# 싱글톤 세션 매니저
session_manager = get_session_manager()


# ========== 세션 관리 API ==========

@router.post("", response_model=SessionInfo)
async def create_session(request: CreateSessionRequest):
    """
    새로운 Claude 세션 생성
    
    Claude Code를 실행할 새로운 세션을 생성합니다.
    각 세션은 독립적인 스토리지 디렉토리를 가집니다.
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
    모든 세션 목록 조회
    
    Multi-pod 환경에서는 모든 Pod의 세션을 반환합니다.
    """
    return session_manager.list_sessions()


@router.get("/{session_id}", response_model=SessionInfo)
async def get_session(
    session_id: str = Path(..., description="세션 ID")
):
    """
    특정 세션 정보 조회
    """
    session = session_manager.get_session_info(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str = Path(..., description="세션 ID"),
    cleanup_storage: bool = Query(True, description="스토리지도 함께 삭제")
):
    """
    세션 삭제
    
    세션을 종료하고 관련 리소스를 정리합니다.
    """
    success = await session_manager.delete_session(session_id, cleanup_storage)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    logger.info(f"✅ Session deleted: {session_id}")
    return {"success": True, "session_id": session_id}


# ========== Claude 실행 API ==========

@router.post("/{session_id}/execute", response_model=ExecuteResponse)
async def execute_prompt(
    session_id: str = Path(..., description="세션 ID"),
    request: ExecuteRequest = ...
):
    """
    Claude에게 프롬프트 실행
    
    세션에서 Claude에게 프롬프트를 전달하고 결과를 반환합니다.
    """
    process = session_manager.get_process(session_id)
    if not process:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    
    if not process.is_alive():
        raise HTTPException(
            status_code=400, 
            detail=f"Session is not running (status: {process.status})"
        )
    
    try:
        result = await process.execute(
            prompt=request.prompt,
            timeout=request.timeout or 600.0,
            skip_permissions=request.skip_permissions,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns
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
        raise HTTPException(status_code=500, detail=str(e))


# ========== 스토리지 API ==========

@router.get("/{session_id}/storage", response_model=StorageListResponse)
async def list_storage_files(
    session_id: str = Path(..., description="세션 ID"),
    path: str = Query("", description="하위 경로")
):
    """
    세션 스토리지 파일 목록 조회
    
    세션 전용 스토리지의 파일 목록을 반환합니다.
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
    session_id: str = Path(..., description="세션 ID"),
    file_path: str = Path(..., description="파일 경로"),
    encoding: str = Query("utf-8", description="파일 인코딩")
):
    """
    스토리지 파일 내용 읽기
    
    세션 스토리지의 특정 파일 내용을 반환합니다.
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
