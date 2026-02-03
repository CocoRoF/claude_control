"""
MCP Controller - MCP 세션 및 요청 관리 라우터
"""
import logging
from fastapi import APIRouter, HTTPException, status
from service.mcp_manager.session_manager import SessionManager
from service.mcp_manager.router import MCPRouter
from service.mcp_manager.models import (
    CreateSessionRequest,
    SessionInfo,
    MCPRequest,
    MCPResponse
)

logger = logging.getLogger(__name__)

# 전역 매니저
session_manager = SessionManager()
mcp_router = MCPRouter(session_manager)

# 라우터 정의
router = APIRouter(prefix="/api/mcp", tags=["MCP"])

@router.get("/")
async def root():
    """헬스체크"""
    return {
        "service": "MCP Station",
        "status": "running",
        "sessions_count": len(session_manager.sessions)
    }

@router.post("/sessions", response_model=SessionInfo, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest):
    """
    새로운 MCP 서버 세션 생성

    - **server_type**: python 또는 node
    - **server_command**: 실행할 스크립트 경로
    - **server_args**: 추가 명령줄 인자 (선택)
    - **env_vars**: 환경 변수 (선택)
    - **working_dir**: 작업 디렉토리 (선택)
    """
    try:
        session_info = await session_manager.create_session(request)
        logger.info(f"Session created: {session_info.session_id}")
        return session_info
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions():
    """모든 활성 세션 목록 조회"""
    await session_manager.cleanup_dead_sessions()
    return session_manager.list_sessions()


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session(session_id: str):
    """특정 세션 정보 조회"""
    # 먼저 Redis에서 세션 메타데이터 조회 시도
    session_info = session_manager.get_session_info(session_id)
    
    if session_info:
        return session_info
    
    # 로컬 프로세스에서 조회 (하위 호환성)
    process = session_manager.get_session(session_id)

    if not process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )

    from service.pod.pod_info import get_pod_info
    pod_info = get_pod_info()
    
    return SessionInfo(
        session_id=session_id,
        session_name=process.session_name,
        server_type=process.server_type,
        status=process.status,
        created_at=process.created_at,
        pid=process.pid,
        error_message=process.error_message,
        server_command=process.command,
        server_args=process.args,
        additional_commands=process.additional_commands,
        mcp_initialized=getattr(process, '_initialized', False),
        pod_name=pod_info.pod_name,
        pod_ip=pod_info.pod_ip
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str):
    """세션 삭제 및 프로세스 종료"""
    success = await session_manager.delete_session(session_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}"
        )


@router.get("/sessions/{session_id}/tools")
async def get_session_tools(session_id: str):
    """
    특정 세션의 MCP 도구 목록 조회

    LangChain 등 외부에서 도구 정보를 가져올 때 사용
    """
    # tools/list 메서드 호출
    request = MCPRequest(
        session_id=session_id,
        method="tools/list",
        params={}
    )

    response = await mcp_router.route_request(request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tools: {response.error}"
        )

    return response.data


@router.post("/mcp-request", response_model=MCPResponse)
async def mcp_request(request: MCPRequest):
    """
    MCP 서버로 요청 라우팅

    - **session_id**: 대상 세션 ID
    - **method**: MCP 메서드 (예: tools/list, tools/call, prompts/list 등)
    - **params**: 메서드 파라미터
    """
    response = await mcp_router.route_request(request)

    if not response.success:
        # MCP 에러는 200으로 반환하되, success=false로 표시
        # 클라이언트가 처리 방식을 선택할 수 있도록
        return response

    return response
