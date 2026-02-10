"""
Agent Session Controller

REST API endpoints for AgentSession (LangGraph + Claude CLI) management.

AgentSession(CompiledStateGraph) 기반 세션을 관리합니다.

AgentSession API:   /api/agents (primary)
Legacy Session API: /api/sessions (deprecated, backward compatibility)
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from service.claude_manager.models import (
    CreateSessionRequest,
    SessionInfo,
    SessionRole,
    ExecuteRequest,
    ExecuteResponse,
    AutonomousExecuteRequest,
    AutonomousExecuteResponse,
    DelegateTaskRequest,
    DelegateTaskResponse,
    StorageFile,
    StorageListResponse,
    StorageFileContent,
    ManagerEvent,
    ManagerEventType,
    ManagerDashboard,
    WorkerStatus,
)
from service.langgraph import (
    get_agent_session_manager,
    AgentSession,
)
from service.logging.session_logger import get_session_logger

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/agents", tags=["agents"])

# AgentSessionManager 싱글톤
agent_manager = get_agent_session_manager()


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateAgentRequest(CreateSessionRequest):
    """
    AgentSession 생성 요청.

    CreateSessionRequest를 상속하며 추가 옵션 제공.
    """
    enable_checkpointing: bool = Field(
        default=False,
        description="Enable state checkpointing for replay/resume"
    )


class AgentInvokeRequest(BaseModel):
    """
    AgentSession invoke 요청.

    LangGraph 상태 기반 실행.
    """
    input_text: str = Field(
        ...,
        description="Input text for the agent"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for checkpointing (optional)"
    )
    max_iterations: Optional[int] = Field(
        default=None,
        description="Maximum iterations for autonomous execution"
    )


class AgentInvokeResponse(BaseModel):
    """
    AgentSession invoke 응답.
    """
    success: bool
    session_id: str
    output: Optional[str] = None
    error: Optional[str] = None
    thread_id: Optional[str] = None


class AgentStateResponse(BaseModel):
    """
    AgentSession 상태 조회 응답.
    """
    session_id: str
    current_step: Optional[str] = None
    last_output: Optional[str] = None
    iteration: Optional[int] = None
    error: Optional[str] = None
    is_complete: bool = False


class UpgradeToAgentRequest(BaseModel):
    """
    기존 세션을 AgentSession으로 업그레이드 요청.
    """
    enable_checkpointing: bool = Field(
        default=False,
        description="Enable state checkpointing"
    )


# ============================================================================
# Agent Session Management API
# ============================================================================


@router.post("", response_model=SessionInfo)
async def create_agent_session(request: CreateAgentRequest):
    """
    Create a new AgentSession.

    AgentSession은 CompiledStateGraph 기반으로 동작하며,
    LangGraph의 상태 관리 기능을 제공합니다.
    """
    try:
        agent = await agent_manager.create_agent_session(
            request=request,
            enable_checkpointing=request.enable_checkpointing,
        )

        session_info = agent.get_session_info()
        logger.info(f"✅ AgentSession created: {agent.session_id}")
        return session_info

    except Exception as e:
        logger.error(f"❌ Failed to create AgentSession: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[SessionInfo])
async def list_agent_sessions():
    """
    List all AgentSessions.

    Returns only AgentSession instances (not regular sessions).
    """
    agents = agent_manager.list_agents()
    return [agent.get_session_info() for agent in agents]


@router.get("/{session_id}", response_model=SessionInfo)
async def get_agent_session(
    session_id: str = Path(..., description="Session ID")
):
    """
    Get specific AgentSession information.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        # 기존 세션에서 조회 시도
        session_info = agent_manager.get_session_info(session_id)
        if session_info:
            raise HTTPException(
                status_code=400,
                detail=f"Session {session_id} is not an AgentSession. Use /api/agents/{session_id}/upgrade to convert it."
            )
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    return agent.get_session_info()


@router.delete("/{session_id}")
async def delete_agent_session(
    session_id: str = Path(..., description="Session ID"),
    cleanup_storage: bool = Query(True, description="Also delete storage")
):
    """
    Delete AgentSession.
    """
    success = await agent_manager.delete_session(session_id, cleanup_storage)
    if not success:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    logger.info(f"✅ AgentSession deleted: {session_id}")
    return {"success": True, "session_id": session_id}


# ============================================================================
# Agent Graph Execution API
# ============================================================================


@router.post("/{session_id}/invoke", response_model=AgentInvokeResponse)
async def invoke_agent(
    session_id: str = Path(..., description="Session ID"),
    request: AgentInvokeRequest = ...
):
    """
    Invoke AgentSession with LangGraph state execution.

    상태 기반 그래프 실행을 수행합니다.
    체크포인팅이 활성화된 경우 thread_id로 상태를 복원/저장합니다.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    if not agent.is_initialized:
        raise HTTPException(
            status_code=400,
            detail=f"AgentSession is not initialized"
        )

    # 세션 로거
    session_logger = get_session_logger(session_id, create_if_missing=False)

    try:
        # 입력 로깅
        if session_logger:
            session_logger.log_command(
                prompt=request.input_text,
                max_turns=request.max_iterations,
            )

        # LangGraph 그래프 실행
        output = await agent.invoke(
            input_text=request.input_text,
            thread_id=request.thread_id,
            max_iterations=request.max_iterations,
        )

        # 응답 로깅
        if session_logger:
            session_logger.log_response(
                success=True,
                output=output,
            )

        return AgentInvokeResponse(
            success=True,
            session_id=session_id,
            output=output,
            thread_id=request.thread_id,
        )

    except Exception as e:
        logger.error(f"❌ Agent invoke failed: {e}", exc_info=True)

        if session_logger:
            session_logger.log_response(
                success=False,
                error=str(e),
            )

        return AgentInvokeResponse(
            success=False,
            session_id=session_id,
            error=str(e),
            thread_id=request.thread_id,
        )


@router.post("/{session_id}/execute", response_model=ExecuteResponse)
async def execute_agent_prompt(
    session_id: str = Path(..., description="Session ID"),
    request: ExecuteRequest = ...
):
    """
    Execute prompt with AgentSession (기존 방식 호환).

    기존 claude_controller의 execute와 동일한 인터페이스를 제공합니다.
    내부적으로 ClaudeProcess.execute()를 직접 호출합니다.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    if not agent.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"AgentSession is not running (status: {agent.status})"
        )

    # 세션 로거
    session_logger = get_session_logger(session_id, create_if_missing=False)

    try:
        # 입력 로깅
        if session_logger:
            session_logger.log_command(
                prompt=request.prompt,
                timeout=request.timeout,
                system_prompt=request.system_prompt,
                max_turns=request.max_turns,
            )

        # 기존 방식으로 실행 (ClaudeProcess.execute 호출)
        result = await agent.execute(
            prompt=request.prompt,
            timeout=request.timeout or agent.timeout,
            skip_permissions=request.skip_permissions,
        )

        # 응답 로깅
        if session_logger:
            session_logger.log_response(
                success=result.get("success", False),
                output=result.get("output"),
                error=result.get("error"),
                duration_ms=result.get("duration_ms"),
                cost_usd=result.get("cost_usd"),
            )

        return ExecuteResponse(
            success=result.get("success", False),
            session_id=session_id,
            output=result.get("output"),
            error=result.get("error"),
            cost_usd=result.get("cost_usd"),
            duration_ms=result.get("duration_ms"),
        )

    except Exception as e:
        logger.error(f"❌ Agent execute failed: {e}", exc_info=True)

        if session_logger:
            session_logger.log_response(
                success=False,
                error=str(e),
            )

        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Agent State API
# ============================================================================


@router.get("/{session_id}/state", response_model=AgentStateResponse)
async def get_agent_state(
    session_id: str = Path(..., description="Session ID"),
    thread_id: Optional[str] = Query(None, description="Thread ID")
):
    """
    Get current AgentSession state.

    체크포인팅이 활성화된 경우에만 상태를 조회할 수 있습니다.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    state = agent.get_state(thread_id=thread_id)

    if state is None:
        return AgentStateResponse(
            session_id=session_id,
            error="State not available (checkpointing disabled or no execution yet)",
        )

    metadata = state.get("metadata", {})

    return AgentStateResponse(
        session_id=session_id,
        current_step=state.get("current_step"),
        last_output=state.get("last_output"),
        iteration=metadata.get("iteration"),
        error=state.get("error"),
        is_complete=state.get("is_complete", False),
    )


@router.get("/{session_id}/history")
async def get_agent_history(
    session_id: str = Path(..., description="Session ID"),
    thread_id: Optional[str] = Query(None, description="Thread ID")
):
    """
    Get AgentSession execution history.

    체크포인팅이 활성화된 경우에만 히스토리를 조회할 수 있습니다.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    history = agent.get_history(thread_id=thread_id)

    return {
        "session_id": session_id,
        "thread_id": thread_id,
        "history": history,
    }


# ============================================================================
# Agent Upgrade API
# ============================================================================


@router.post("/{session_id}/upgrade", response_model=SessionInfo)
async def upgrade_to_agent_session(
    session_id: str = Path(..., description="Session ID"),
    request: UpgradeToAgentRequest = UpgradeToAgentRequest()
):
    """
    Upgrade existing ClaudeProcess session to AgentSession.

    기존 세션의 ClaudeProcess를 유지하면서 AgentSession으로 래핑합니다.
    """
    # 이미 AgentSession인지 확인
    if agent_manager.has_agent(session_id):
        agent = agent_manager.get_agent(session_id)
        logger.info(f"Session {session_id} is already an AgentSession")
        return agent.get_session_info()

    # 업그레이드 시도
    agent = agent_manager.upgrade_to_agent(
        session_id=session_id,
        enable_checkpointing=request.enable_checkpointing,
    )

    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found or cannot be upgraded: {session_id}"
        )

    logger.info(f"✅ Session upgraded to AgentSession: {session_id}")
    return agent.get_session_info()


# ============================================================================
# Manager/Worker API
# ============================================================================


@router.get("/managers", response_model=List[SessionInfo])
async def list_agent_managers():
    """
    Get all AgentSession managers.
    """
    managers = agent_manager.get_agent_managers()
    return [m.get_session_info() for m in managers]


@router.get("/{manager_id}/workers", response_model=List[SessionInfo])
async def get_agent_workers(
    manager_id: str = Path(..., description="Manager session ID")
):
    """
    Get workers under a manager AgentSession.
    """
    workers = agent_manager.get_agent_workers_by_manager(manager_id)
    return [w.get_session_info() for w in workers]


# ============================================================================
# Autonomous Execution API
# ============================================================================


@router.post("/{session_id}/execute/autonomous")
async def execute_autonomous(
    session_id: str = Path(..., description="Session ID"),
    request: AutonomousExecuteRequest = ...
):
    """
    Execute a task autonomously with self-managing loop.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    process = agent.process
    if not process:
        raise HTTPException(status_code=400, detail="AgentSession process not available")

    if not process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Session is not running (status: {process.status})"
        )

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
            timeout_per_iteration=request.timeout_per_iteration or process.timeout,
            max_iterations=request.max_iterations or process.autonomous_max_iterations,
            skip_permissions=request.skip_permissions,
            system_prompt=request.system_prompt,
            max_turns=request.max_turns or process.max_turns
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
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    process = agent.process
    if not process:
        raise HTTPException(status_code=400, detail="AgentSession process not available")

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
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    process = agent.process
    if not process:
        raise HTTPException(status_code=400, detail="AgentSession process not available")

    state = process.autonomous_state
    return {
        "session_id": session_id,
        "is_running": state.get("is_running", False),
        "iteration": state.get("iteration", 0),
        "max_iterations": state.get("max_iterations", 100),
        "original_request": state.get("original_request"),
        "stop_requested": state.get("stop_requested", False)
    }


# ============================================================================
# Storage API
# ============================================================================


@router.get("/{session_id}/storage")
async def list_storage_files(
    session_id: str = Path(..., description="Session ID"),
    path: str = Query("", description="Subdirectory path")
):
    """
    List session storage files.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    process = agent.process
    if not process:
        raise HTTPException(status_code=400, detail="AgentSession process not available")

    files_data = process.list_storage_files(path)
    files = [StorageFile(**f) for f in files_data]

    return StorageListResponse(
        session_id=session_id,
        storage_path=process.storage_path,
        files=files
    )


@router.get("/{session_id}/storage/{file_path:path}")
async def read_storage_file(
    session_id: str = Path(..., description="Session ID"),
    file_path: str = Path(..., description="File path"),
    encoding: str = Query("utf-8", description="File encoding")
):
    """
    Read storage file content.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    process = agent.process
    if not process:
        raise HTTPException(status_code=400, detail="AgentSession process not available")

    file_content = process.read_storage_file(file_path, encoding)
    if not file_content:
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    return StorageFileContent(
        session_id=session_id,
        **file_content
    )


# ============================================================================
# Manager Dashboard API
# ============================================================================


@router.post("/{session_id}/delegate")
async def delegate_task(
    session_id: str = Path(..., description="Manager session ID"),
    request: DelegateTaskRequest = ...
):
    """
    Delegate a task from manager to worker.
    """
    import uuid
    from datetime import datetime

    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Manager AgentSession not found: {session_id}")

    if agent.role != SessionRole.MANAGER:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not a manager (role: {agent.role})"
        )

    # Get worker
    worker = agent_manager.get_agent(request.worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail=f"Worker AgentSession not found: {request.worker_id}")

    if worker.manager_id != session_id:
        raise HTTPException(
            status_code=400,
            detail=f"Worker {request.worker_id} is not managed by this manager"
        )

    worker_process = worker.process
    if not worker_process or not worker_process.is_alive():
        raise HTTPException(
            status_code=400,
            detail=f"Worker session is not running"
        )

    manager_logger = get_session_logger(session_id, create_if_missing=True)
    delegation_id = str(uuid.uuid4())[:8]

    try:
        if manager_logger:
            manager_logger.log_task_delegated(
                worker_id=request.worker_id,
                worker_name=worker.session_name,
                task_prompt=request.prompt,
                context=request.context
            )

        worker_process.is_busy = True
        worker_process.current_task = request.prompt[:100]
        worker_process.last_activity = datetime.now()

        if worker.autonomous:
            result = await worker_process.execute_autonomous(
                prompt=request.prompt,
                timeout_per_iteration=request.timeout or worker.timeout,
                max_iterations=worker.autonomous_max_iterations,
                skip_permissions=request.skip_permissions
            )
            output = result.get("final_output")
            success = result.get("success", False)
        else:
            result = await worker_process.execute(
                prompt=request.prompt,
                timeout=request.timeout or worker.timeout,
                skip_permissions=request.skip_permissions
            )
            output = result.get("output")
            success = result.get("success", False)

        worker_process.is_busy = False
        worker_process.last_output = output[:500] if output else None
        worker_process.last_activity = datetime.now()

        if manager_logger:
            manager_logger.log_worker_completed(
                worker_id=request.worker_id,
                worker_name=worker.session_name,
                success=success,
                output_preview=output[:200] if output else None,
                duration_ms=result.get("duration_ms") or result.get("total_duration_ms"),
                cost_usd=result.get("cost_usd") or result.get("total_cost_usd")
            )

        return DelegateTaskResponse(
            success=success,
            manager_id=session_id,
            worker_id=request.worker_id,
            delegation_id=delegation_id,
            status="completed" if success else "error",
            output=output,
            error=result.get("error") or result.get("stop_reason") if not success else None
        )

    except Exception as e:
        worker_process.is_busy = False
        worker_process.last_activity = datetime.now()
        logger.error(f"❌ Task delegation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/events")
async def get_manager_events(
    session_id: str = Path(..., description="Manager session ID"),
    limit: int = Query(50, description="Maximum number of events to return")
):
    """
    Get manager event log.
    """
    import uuid
    from datetime import datetime

    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    if agent.role != SessionRole.MANAGER:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not a manager (role: {agent.role})"
        )

    session_logger = get_session_logger(session_id, create_if_missing=False)
    if not session_logger:
        return []

    raw_events = session_logger.get_manager_events(limit=limit)

    events = []
    for raw in raw_events:
        metadata = raw.get("metadata", {})
        events.append(ManagerEvent(
            event_id=metadata.get("event_id", str(uuid.uuid4())[:8]),
            event_type=ManagerEventType(metadata.get("event_type", "status_check")),
            timestamp=datetime.fromisoformat(raw.get("timestamp")) if raw.get("timestamp") else datetime.now(),
            manager_id=session_id,
            worker_id=metadata.get("worker_id"),
            message=raw.get("message", ""),
            data=metadata.get("data")
        ))

    return events


@router.get("/{session_id}/dashboard")
async def get_manager_dashboard(
    session_id: str = Path(..., description="Manager session ID")
):
    """
    Get manager dashboard data.
    """
    agent = agent_manager.get_agent(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"AgentSession not found: {session_id}")

    if agent.role != SessionRole.MANAGER:
        raise HTTPException(
            status_code=400,
            detail=f"Session is not a manager (role: {agent.role})"
        )

    workers = agent_manager.get_agent_workers_by_manager(session_id)
    worker_statuses = []

    for worker in workers:
        process = worker.process

        worker_status = WorkerStatus(
            worker_id=worker.session_id,
            worker_name=worker.session_name,
            status=worker.status,
            is_busy=process.is_busy if process else False,
            current_task=process.current_task if process else None,
            last_output=process.last_output if process else None,
            last_activity=process.last_activity if process else None
        )
        worker_statuses.append(worker_status)

    events_response = await get_manager_events(session_id, limit=20)

    active_delegations = sum(1 for w in worker_statuses if w.is_busy)
    completed_delegations = sum(
        1 for e in events_response
        if e.event_type in [ManagerEventType.WORKER_COMPLETED, ManagerEventType.WORKER_ERROR]
    )

    return ManagerDashboard(
        manager_id=session_id,
        manager_name=agent.session_name,
        workers=worker_statuses,
        recent_events=events_response,
        active_delegations=active_delegations,
        completed_delegations=completed_delegations
    )
