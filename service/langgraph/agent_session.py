"""
AgentSession - CompiledStateGraph 기반 세션 관리

기존 CLI 세션(ClaudeProcess)을 내부에 보유하면서
LangGraph의 CompiledStateGraph로 래핑하여 상태 관리 기능을 제공합니다.

새 세션 생성 과정:
1. CLI 세션 생성 (ClaudeProcess via ClaudeCLIChatModel)
2. CompiledStateGraph 생성 (AgentSession)

이렇게 생성된 AgentSession이 실제 에이전트 세션으로 사용됩니다.

사용 예:
    from service.langgraph import AgentSession, AgentState

    # 새 에이전트 세션 생성
    agent = await AgentSession.create(
        working_dir="/path/to/project",
        model_name="claude-sonnet-4-20250514",
        session_name="my-agent"
    )

    # 실행
    result = await agent.invoke("Hello, what can you help me with?")

    # 스트리밍 실행
    async for event in agent.astream("Build a web app"):
        print(event)

    # 정리
    await agent.cleanup()
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import (
    Annotated,
    Any,
    AsyncIterator,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    Sequence,
    TypedDict,
    Union,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field, PrivateAttr

from service.claude_manager.models import (
    MCPConfig,
    SessionInfo,
    SessionRole,
    SessionStatus,
)
from service.claude_manager.process_manager import ClaudeProcess
from service.langgraph.claude_cli_model import ClaudeCLIChatModel
from service.logging.session_logger import get_session_logger, SessionLogger

# Lazy import to avoid circular dependency
_autonomous_graph_module = None

def _get_autonomous_graph_class():
    """Lazy import of AutonomousGraph to avoid circular imports."""
    global _autonomous_graph_module
    if _autonomous_graph_module is None:
        from service.langgraph import autonomous_graph as ag
        _autonomous_graph_module = ag
    return _autonomous_graph_module.AutonomousGraph

logger = logging.getLogger(__name__)


# ============================================================================
# State Definition
# ============================================================================


def add_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    """메시지 리스트 병합 (reducer 함수)"""
    return left + right


class AgentState(TypedDict):
    """
    AgentSession의 상태 정의.

    LangGraph StateGraph에서 사용되는 상태 스키마입니다.
    """
    # 대화 메시지 히스토리 (reducer로 누적)
    messages: Annotated[List[BaseMessage], add_messages]

    # 현재 실행 단계
    current_step: str

    # 마지막 에이전트 출력
    last_output: Optional[str]

    # 실행 메타데이터
    metadata: Dict[str, Any]

    # 에러 정보
    error: Optional[str]

    # 실행 완료 여부
    is_complete: bool


# ============================================================================
# AgentSession Class
# ============================================================================


class AgentSession:
    """
    CompiledStateGraph 기반 에이전트 세션.

    기존 ClaudeProcess의 CLI 세션을 내부에 보유하면서
    LangGraph의 상태 관리 기능을 통합합니다.

    핵심 구조:
    - ClaudeCLIChatModel: ClaudeProcess를 래핑한 LangChain 모델
    - CompiledStateGraph: LangGraph 그래프 (노드: agent, router)
    - MemorySaver: 체크포인팅 지원 (옵션)

    기존 SessionInfo와 호환:
    - session_id, session_name, status 등 동일 필드 제공
    - get_session_info() 메서드로 SessionInfo 객체 반환
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        session_name: Optional[str] = None,
        working_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        max_turns: int = 100,
        timeout: float = 1800.0,
        system_prompt: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        mcp_config: Optional[MCPConfig] = None,
        autonomous: bool = True,
        autonomous_max_iterations: int = 100,
        role: SessionRole = SessionRole.WORKER,
        manager_id: Optional[str] = None,
        enable_checkpointing: bool = False,
    ):
        """
        AgentSession 초기화.

        Args:
            session_id: 세션 ID (미제공시 자동 생성)
            session_name: 세션 이름
            working_dir: CLI 작업 디렉토리
            model_name: Claude 모델명
            max_turns: 최대 턴 수
            timeout: 실행 타임아웃 (초)
            system_prompt: 시스템 프롬프트
            env_vars: 환경 변수
            mcp_config: MCP 설정
            autonomous: 자율 모드 여부
            autonomous_max_iterations: 자율 실행 최대 반복 횟수
            role: 세션 역할 (MANAGER/WORKER)
            manager_id: 매니저 세션 ID (WORKER인 경우)
            enable_checkpointing: 체크포인팅 활성화 여부
        """
        # 세션 식별 정보
        self._session_id = session_id or str(uuid.uuid4())
        self._session_name = session_name
        self._created_at = datetime.now()

        # 실행 설정 (working_dir=None이면 ClaudeProcess에서 storage_path 사용)
        self._working_dir = working_dir  # None allowed - ClaudeProcess will use storage_path
        self._model_name = model_name
        self._max_turns = max_turns
        self._timeout = timeout
        self._system_prompt = system_prompt
        self._env_vars = env_vars or {}
        self._mcp_config = mcp_config
        self._autonomous = autonomous
        self._autonomous_max_iterations = autonomous_max_iterations

        # 역할 설정
        self._role = role
        self._manager_id = manager_id

        # 내부 컴포넌트
        self._model: Optional[ClaudeCLIChatModel] = None
        self._graph: Optional[CompiledStateGraph] = None
        self._checkpointer: Optional[MemorySaver] = None
        self._enable_checkpointing = enable_checkpointing

        # 실행 상태
        self._initialized = False
        self._error_message: Optional[str] = None
        self._current_thread_id: str = "default"
        self._current_iteration: int = 0
        self._execution_start_time: Optional[datetime] = None

        # Autonomous 그래프 (autonomous 모드일 때 사용)
        self._autonomous_graph: Optional[CompiledStateGraph] = None

        # 초기 상태 설정 (STARTING 사용)
        self._status = SessionStatus.STARTING

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    async def create(
        cls,
        working_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        session_name: Optional[str] = None,
        session_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        mcp_config: Optional[MCPConfig] = None,
        role: SessionRole = SessionRole.WORKER,
        enable_checkpointing: bool = False,
        **kwargs,
    ) -> "AgentSession":
        """
        새 AgentSession을 생성하고 초기화.

        Args:
            working_dir: 작업 디렉토리
            model_name: Claude 모델명
            session_name: 세션 이름
            session_id: 세션 ID
            system_prompt: 시스템 프롬프트
            mcp_config: MCP 설정
            role: 세션 역할
            enable_checkpointing: 체크포인팅 활성화
            **kwargs: 추가 설정

        Returns:
            초기화된 AgentSession 인스턴스
        """
        agent = cls(
            session_id=session_id,
            session_name=session_name,
            working_dir=working_dir,
            model_name=model_name,
            system_prompt=system_prompt,
            mcp_config=mcp_config,
            role=role,
            enable_checkpointing=enable_checkpointing,
            **kwargs,
        )

        success = await agent.initialize()
        if not success:
            raise RuntimeError(f"Failed to initialize AgentSession: {agent.error_message}")

        return agent

    @classmethod
    def from_process(cls, process: ClaudeProcess, enable_checkpointing: bool = False) -> "AgentSession":
        """
        기존 ClaudeProcess를 사용하여 AgentSession 생성.

        Args:
            process: 초기화된 ClaudeProcess 인스턴스
            enable_checkpointing: 체크포인팅 활성화

        Returns:
            AgentSession 인스턴스
        """
        agent = cls(
            session_id=process.session_id,
            session_name=process.session_name,
            working_dir=process.working_dir,
            model_name=process.model,
            max_turns=process.max_turns,
            timeout=process.timeout,
            system_prompt=process.system_prompt,
            env_vars=process.env_vars or {},
            mcp_config=process.mcp_config,
            autonomous=process.autonomous,
            autonomous_max_iterations=process.autonomous_max_iterations,
            role=SessionRole(process.role) if process.role else SessionRole.WORKER,
            manager_id=process.manager_id,
            enable_checkpointing=enable_checkpointing,
        )

        # ClaudeProcess를 사용하여 모델 생성
        agent._model = ClaudeCLIChatModel.from_process(process)
        agent._build_graph()
        agent._initialized = True
        agent._status = SessionStatus.RUNNING

        logger.info(f"[{agent.session_id}] AgentSession created from existing process")
        return agent

    @classmethod
    def from_model(cls, model: ClaudeCLIChatModel, enable_checkpointing: bool = False) -> "AgentSession":
        """
        기존 ClaudeCLIChatModel을 사용하여 AgentSession 생성.

        Args:
            model: 초기화된 ClaudeCLIChatModel 인스턴스
            enable_checkpointing: 체크포인팅 활성화

        Returns:
            AgentSession 인스턴스
        """
        if not model.is_initialized:
            raise ValueError("ClaudeCLIChatModel must be initialized before creating AgentSession")

        agent = cls(
            session_id=model.session_id,
            session_name=model.session_name,
            working_dir=model.working_dir,
            model_name=model.model_name,
            max_turns=model.max_turns,
            timeout=model.timeout,
            system_prompt=model.system_prompt,
            env_vars=model.env_vars,
            mcp_config=model.mcp_config,
            autonomous=model.autonomous,
            enable_checkpointing=enable_checkpointing,
        )

        agent._model = model
        agent._build_graph()
        agent._initialized = True
        agent._status = SessionStatus.RUNNING

        logger.info(f"[{agent.session_id}] AgentSession created from existing model")
        return agent

    # ========================================================================
    # Properties (SessionInfo 호환)
    # ========================================================================

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def session_name(self) -> Optional[str]:
        return self._session_name

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def pid(self) -> Optional[int]:
        """프로세스 ID (ClaudeProcess에서 가져옴)"""
        if self._model and self._model.process:
            return self._model.process.pid
        return None

    @property
    def error_message(self) -> Optional[str]:
        return self._error_message

    @property
    def model_name(self) -> Optional[str]:
        return self._model_name

    @property
    def max_turns(self) -> int:
        return self._max_turns

    @property
    def timeout(self) -> float:
        return self._timeout

    @property
    def autonomous(self) -> bool:
        return self._autonomous

    @property
    def autonomous_max_iterations(self) -> int:
        return self._autonomous_max_iterations

    @property
    def role(self) -> SessionRole:
        return self._role

    @property
    def manager_id(self) -> Optional[str]:
        return self._manager_id

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def graph(self) -> Optional[CompiledStateGraph]:
        """내부 CompiledStateGraph 반환"""
        return self._graph

    @property
    def model(self) -> Optional[ClaudeCLIChatModel]:
        """내부 ClaudeCLIChatModel 반환"""
        return self._model

    @property
    def process(self) -> Optional[ClaudeProcess]:
        """내부 ClaudeProcess 반환"""
        if self._model:
            return self._model.process
        return None

    @property
    def storage_path(self) -> Optional[str]:
        """세션 저장 경로"""
        if self._model and self._model.process:
            return self._model.process.storage_path
        return None

    def _get_logger(self) -> Optional[SessionLogger]:
        """세션 로거 가져오기 (lazy)"""
        return get_session_logger(self._session_id, create_if_missing=True)

    def _get_state_summary(self, state: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """현재 상태 요약 생성 (로깅용)"""
        if not state:
            return None
        return {
            "messages_count": len(state.get("messages", [])),
            "current_step": state.get("current_step"),
            "is_complete": state.get("is_complete", False),
            "has_error": bool(state.get("error")),
            "iteration": state.get("metadata", {}).get("iteration", 0),
        }
    # ========================================================================
    # Core Methods
    # ========================================================================

    async def initialize(self) -> bool:
        """
        AgentSession 초기화.

        1. ClaudeCLIChatModel 생성 및 초기화
        2. LangGraph StateGraph 빌드

        Returns:
            초기화 성공 여부
        """
        if self._initialized:
            logger.info(f"[{self._session_id}] AgentSession already initialized")
            return True

        logger.info(f"[{self._session_id}] Initializing AgentSession...")

        try:
            # 1. ClaudeCLIChatModel 생성
            self._model = ClaudeCLIChatModel(
                session_id=self._session_id,
                session_name=self._session_name,
                working_dir=self._working_dir,
                model_name=self._model_name,
                max_turns=self._max_turns,
                timeout=self._timeout,
                system_prompt=self._system_prompt,
                env_vars=self._env_vars,
                mcp_config=self._mcp_config,
                autonomous=self._autonomous,
            )

            # 2. ClaudeCLIChatModel 초기화 (ClaudeProcess 생성)
            success = await self._model.initialize()
            if not success:
                self._error_message = self._model.process.error_message if self._model.process else "Unknown error"
                self._status = SessionStatus.ERROR
                logger.error(f"[{self._session_id}] Failed to initialize model: {self._error_message}")
                return False

            # 3. StateGraph 빌드
            self._build_graph()

            self._initialized = True
            self._status = SessionStatus.RUNNING
            logger.info(f"[{self._session_id}] ✅ AgentSession initialized successfully")
            return True

        except Exception as e:
            self._error_message = str(e)
            self._status = SessionStatus.ERROR
            logger.exception(f"[{self._session_id}] Exception during initialization: {e}")
            return False

    def _build_graph(self):
        """
        LangGraph StateGraph 빌드.

        autonomous 모드일 경우: 난이도 기반 AutonomousGraph 사용
        non-autonomous 모드: 단순 agent -> process_output 그래프 사용
        """
        # 체크포인터 설정
        if self._enable_checkpointing:
            self._checkpointer = MemorySaver()

        # Autonomous 모드일 때는 AutonomousGraph 사용
        if self._autonomous:
            self._build_autonomous_graph()
        else:
            self._build_simple_graph()

        logger.debug(f"[{self._session_id}] StateGraph built successfully (autonomous={self._autonomous})")

    def _build_autonomous_graph(self):
        """
        Autonomous 모드용 그래프 빌드.

        난이도 기반 AutonomousGraph 사용:
        - Easy: 바로 답변
        - Medium: 답변 + 검토
        - Hard: TODO 생성 -> 개별 실행 -> 검토 -> 최종 답변
        """
        AutonomousGraph = _get_autonomous_graph_class()
        
        autonomous_graph_builder = AutonomousGraph(
            model=self._model,
            session_id=self._session_id,
            enable_checkpointing=self._enable_checkpointing,
            max_review_retries=3,
        )
        
        self._autonomous_graph = autonomous_graph_builder.build()
        
        # 기본 그래프도 빌드 (호환성)
        self._build_simple_graph()
        
        logger.info(f"[{self._session_id}] AutonomousGraph built for autonomous execution")

    def _build_simple_graph(self):
        """
        Non-autonomous 모드용 단순 그래프 빌드.

        그래프 구조:
        START -> agent -> process_output -> END or agent (반복)
        """
        # StateGraph 생성
        graph_builder = StateGraph(AgentState)

        # 노드 등록
        graph_builder.add_node("agent", self._agent_node)
        graph_builder.add_node("process_output", self._process_output_node)

        # 엣지 정의
        graph_builder.add_edge(START, "agent")
        graph_builder.add_edge("agent", "process_output")
        graph_builder.add_conditional_edges(
            "process_output",
            self._should_continue,
            {
                "continue": "agent",
                "end": END,
            }
        )

        # 그래프 컴파일
        if self._checkpointer:
            self._graph = graph_builder.compile(checkpointer=self._checkpointer)
        else:
            self._graph = graph_builder.compile()

    async def _agent_node(self, state: AgentState) -> Dict[str, Any]:
        """
        에이전트 노드: Claude CLI 호출.

        현재 상태의 메시지를 기반으로 Claude에게 요청하고
        응답을 상태에 추가합니다.
        """
        import time
        start_time = time.time()
        iteration = state.get("metadata", {}).get("iteration", 0)

        # 로깅: 노드 진입
        session_logger = self._get_logger()
        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="agent",
                iteration=iteration,
                state_summary=self._get_state_summary(state)
            )

        try:
            messages = state.get("messages", [])
            if not messages:
                error_result = {
                    "error": "No messages in state",
                    "is_complete": True,
                }
                if session_logger:
                    session_logger.log_graph_error(
                        error_message="No messages in state",
                        node_name="agent",
                        iteration=iteration
                    )
                return error_result

            # Claude CLI 호출
            response = await self._model.ainvoke(messages)
            duration_ms = int((time.time() - start_time) * 1000)

            output_content = response.content if hasattr(response, 'content') else str(response)

            # 로깅: 노드 완료
            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="agent",
                    iteration=iteration,
                    output_preview=output_content,
                    duration_ms=duration_ms,
                    state_changes={"messages_added": 1, "last_output_updated": True}
                )

            # 응답 메시지 추가
            return {
                "messages": [response],
                "last_output": output_content,
                "current_step": "agent_responded",
                "error": None,
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"[{self._session_id}] Error in agent node: {e}")

            # 로깅: 에러
            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="agent",
                    iteration=iteration,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _process_output_node(self, state: AgentState) -> Dict[str, Any]:
        """
        출력 처리 노드.

        에이전트 응답을 처리하고 다음 상태를 결정합니다.
        """
        metadata = state.get("metadata", {})
        iteration = metadata.get("iteration", 0) + 1
        max_iterations = metadata.get("max_iterations", self._autonomous_max_iterations)

        # 현재 반복 횟수 업데이트
        self._current_iteration = iteration

        # 로깅: 노드 진입/완료 (처리 노드는 간단하므로 한번에)
        session_logger = self._get_logger()
        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="process_output",
                iteration=iteration,
                state_summary=self._get_state_summary(state)
            )
            session_logger.log_graph_state_update(
                update_type="iteration_increment",
                changes={"iteration": iteration, "max_iterations": max_iterations},
                iteration=iteration
            )

        return {
            "metadata": {**metadata, "iteration": iteration},
            "current_step": "output_processed",
        }

    def _should_continue(self, state: AgentState) -> Literal["continue", "end"]:
        """
        조건부 엣지: 계속 실행 여부 결정.

        종료 조건:
        1. is_complete가 True
        2. error가 있음
        3. max_iterations 도달
        """
        metadata = state.get("metadata", {})
        iteration = metadata.get("iteration", 0)
        max_iterations = metadata.get("max_iterations", self._autonomous_max_iterations)
        session_logger = self._get_logger()

        decision = "continue"
        reason = None

        if state.get("is_complete", False):
            decision = "end"
            reason = "is_complete flag set"
        elif state.get("error"):
            decision = "end"
            reason = f"error: {state.get('error')[:50]}"
        elif not self._autonomous or max_iterations <= 1:
            # 단일 실행 모드 (반복 없음)
            decision = "end"
            reason = "single execution mode"
        elif iteration >= max_iterations:
            # 최대 반복 도달
            decision = "end"
            reason = f"max_iterations reached ({iteration}/{max_iterations})"
        else:
            # 마지막 응답 확인 (완료 신호 검출)
            last_output = state.get("last_output", "")
            if self._is_task_complete(last_output):
                decision = "end"
                reason = "task completion signal detected"

        # 로깅: 엣지 결정
        if session_logger:
            session_logger.log_graph_edge_decision(
                from_node="process_output",
                decision=decision,
                reason=reason,
                iteration=iteration
            )

        return decision

    def _is_task_complete(self, output: str) -> bool:
        """
        작업 완료 여부 판단.

        CLI 출력에서 완료 신호를 감지합니다.
        """
        if not output:
            return False

        completion_signals = [
            "작업이 완료되었습니다",
            "Task completed",
            "완료되었습니다",
            "Done.",
            "Finished.",
        ]

        for signal in completion_signals:
            if signal.lower() in output.lower():
                return True

        return False

    # ========================================================================
    # Execution Methods
    # ========================================================================

    async def invoke(
        self,
        input_text: str,
        thread_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        **kwargs,
    ) -> str:
        """
        동기식 실행 (결과 반환).

        autonomous 모드일 경우 난이도 기반 AutonomousGraph 사용:
        - Easy: 바로 답변
        - Medium: 답변 + 검토
        - Hard: TODO 생성 -> 개별 실행 -> 검토 -> 최종 답변

        Args:
            input_text: 사용자 입력 텍스트
            thread_id: 스레드 ID (체크포인팅용)
            max_iterations: 최대 반복 횟수 (None이면 기본값 사용)
            **kwargs: 추가 설정

        Returns:
            에이전트 응답 텍스트
        """
        import time
        start_time = time.time()

        if not self._initialized or not self._graph:
            raise RuntimeError("AgentSession not initialized. Call initialize() first.")

        self._status = SessionStatus.RUNNING
        self._current_iteration = 0
        self._execution_start_time = datetime.now()
        thread_id = thread_id or self._current_thread_id
        effective_max_iterations = max_iterations or self._autonomous_max_iterations

        session_logger = self._get_logger()

        # 로깅: 그래프 실행 시작
        if session_logger:
            session_logger.log_graph_execution_start(
                input_text=input_text,
                thread_id=thread_id,
                max_iterations=effective_max_iterations,
                execution_mode="invoke_autonomous" if self._autonomous else "invoke"
            )

        try:
            config = {"configurable": {"thread_id": thread_id}}

            # Autonomous 모드: 난이도 기반 AutonomousGraph 사용
            if self._autonomous and self._autonomous_graph:
                result = await self._invoke_autonomous(input_text, config, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)
                
                final_output = result.get("final_answer", "") or result.get("answer", "")
                has_error = bool(result.get("error"))
                
                # 로깅: 그래프 실행 완료
                if session_logger:
                    session_logger.log_graph_execution_complete(
                        success=not has_error,
                        total_iterations=result.get("metadata", {}).get("completed_todos", 0),
                        final_output=final_output[:500] if final_output else None,
                        total_duration_ms=duration_ms,
                        stop_reason="completed" if not has_error else result.get("error")
                    )
                
                if has_error:
                    self._error_message = result["error"]
                    return f"Error: {result['error']}"
                
                return final_output
            
            # Non-autonomous 모드: 기존 simple graph 사용
            initial_state: AgentState = {
                "messages": [HumanMessage(content=input_text)],
                "current_step": "start",
                "last_output": None,
                "metadata": {
                    "iteration": 0,
                    "max_iterations": effective_max_iterations,
                    **kwargs,
                },
                "error": None,
                "is_complete": False,
            }

            result = await self._graph.ainvoke(initial_state, config)
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = SessionStatus.RUNNING

            # 결과 추출
            final_output = result.get("last_output", "")
            has_error = bool(result.get("error"))
            total_iterations = result.get("metadata", {}).get("iteration", 0)

            # 로깅: 그래프 실행 완료
            if session_logger:
                session_logger.log_graph_execution_complete(
                    success=not has_error,
                    total_iterations=total_iterations,
                    final_output=final_output,
                    total_duration_ms=duration_ms,
                    stop_reason="completed" if not has_error else result.get("error")
                )

            if has_error:
                self._error_message = result["error"]
                return f"Error: {result['error']}"

            return final_output

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self._status = SessionStatus.RUNNING
            self._error_message = str(e)
            logger.exception(f"[{self._session_id}] Error during invoke: {e}")

            # 로깅: 에러
            if session_logger:
                session_logger.log_graph_execution_complete(
                    success=False,
                    total_iterations=self._current_iteration,
                    final_output=None,
                    total_duration_ms=duration_ms,
                    stop_reason=f"exception: {type(e).__name__}"
                )

            raise

    async def _invoke_autonomous(
        self,
        input_text: str,
        config: Dict[str, Any],
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Autonomous 그래프 실행 (난이도 기반).

        Args:
            input_text: 사용자 입력
            config: 실행 설정
            **kwargs: 추가 메타데이터

        Returns:
            실행 결과 딕셔너리
        """
        if not self._autonomous_graph:
            raise RuntimeError("AutonomousGraph not built")

        # AutonomousGraph 초기 상태 생성
        AutonomousGraph = _get_autonomous_graph_class()
        autonomous_graph_builder = AutonomousGraph(
            model=self._model,
            session_id=self._session_id,
        )
        initial_state = autonomous_graph_builder.get_initial_state(input_text, **kwargs)

        # 그래프 실행
        result = await self._autonomous_graph.ainvoke(initial_state, config)
        
        self._status = SessionStatus.RUNNING
        
        return result

    async def _astream_autonomous(
        self,
        input_text: str,
        config: Dict[str, Any],
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Autonomous 그래프 스트리밍 실행.

        Args:
            input_text: 사용자 입력
            config: 실행 설정
            **kwargs: 추가 메타데이터

        Yields:
            각 노드 실행 결과
        """
        if not self._autonomous_graph:
            raise RuntimeError("AutonomousGraph not built")

        # AutonomousGraph 초기 상태 생성
        AutonomousGraph = _get_autonomous_graph_class()
        autonomous_graph_builder = AutonomousGraph(
            model=self._model,
            session_id=self._session_id,
        )
        initial_state = autonomous_graph_builder.get_initial_state(input_text, **kwargs)

        # 그래프 스트리밍 실행
        async for event in self._autonomous_graph.astream(initial_state, config):
            yield event

    async def astream(
        self,
        input_text: str,
        thread_id: Optional[str] = None,
        max_iterations: Optional[int] = None,
        **kwargs,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        스트리밍 실행.

        autonomous 모드일 경우 난이도 기반 AutonomousGraph 사용.

        Args:
            input_text: 사용자 입력 텍스트
            thread_id: 스레드 ID
            max_iterations: 최대 반복 횟수

        Yields:
            각 노드 실행 결과
        """
        if not self._initialized or not self._graph:
            raise RuntimeError("AgentSession not initialized. Call initialize() first.")

        self._status = SessionStatus.RUNNING
        thread_id = thread_id or self._current_thread_id

        # 그래프 실행 로깅 초기화
        session_logger = self._get_logger()
        start_time = time.time()
        self._current_iteration = 0
        self._execution_start_time = start_time
        effective_max_iterations = max_iterations or self._autonomous_max_iterations
        event_count = 0
        last_event = None

        # 그래프 실행 시작 로깅
        if session_logger:
            session_logger.log_graph_execution_start(
                input_text=input_text,
                thread_id=thread_id,
                max_iterations=effective_max_iterations,
                execution_mode="astream_autonomous" if self._autonomous else "astream",
            )

        try:
            config = {"configurable": {"thread_id": thread_id}}

            # Autonomous 모드: AutonomousGraph 사용
            if self._autonomous and self._autonomous_graph:
                async for event in self._astream_autonomous(input_text, config, **kwargs):
                    event_count += 1
                    last_event = event

                    # 스트림 이벤트 로깅
                    if session_logger:
                        event_keys = list(event.keys()) if isinstance(event, dict) else []
                        session_logger.log_graph_event(
                            event_type="stream_event",
                            message=f"AUTONOMOUS_STREAM event_{event_count}",
                            data={
                                "event_number": event_count,
                                "event_keys": event_keys,
                                "elapsed_ms": int((time.time() - start_time) * 1000),
                            },
                        )

                    yield event
            else:
                # Non-autonomous 모드: 기존 simple graph
                initial_state: AgentState = {
                    "messages": [HumanMessage(content=input_text)],
                    "current_step": "start",
                    "last_output": None,
                    "metadata": {
                        "iteration": 0,
                        "max_iterations": effective_max_iterations,
                        **kwargs,
                    },
                    "error": None,
                    "is_complete": False,
                }

                async for event in self._graph.astream(initial_state, config):
                    event_count += 1
                    last_event = event

                    # 스트림 이벤트 로깅
                    if session_logger:
                        event_keys = list(event.keys()) if isinstance(event, dict) else []
                        session_logger.log_graph_event(
                            event_type="stream_event",
                            message=f"STREAM event_{event_count}",
                            data={
                                "event_number": event_count,
                                "event_keys": event_keys,
                                "elapsed_ms": int((time.time() - start_time) * 1000),
                            },
                        )

                    yield event

            self._status = SessionStatus.RUNNING

            # 스트리밍 완료 로깅
            duration_ms = int((time.time() - start_time) * 1000)
            if session_logger:
                # 마지막 이벤트에서 출력 추출 시도
                final_output = None
                if last_event and isinstance(last_event, dict):
                    # Autonomous 그래프용 키
                    for key in ["final_answer", "direct_answer", "answer", "process_output", "agent", "__end__"]:
                        if key in last_event:
                            node_result = last_event[key]
                            if isinstance(node_result, dict):
                                final_output = node_result.get("final_answer") or node_result.get("answer") or node_result.get("last_output")
                                if final_output:
                                    break

                session_logger.log_graph_execution_complete(
                    success=True,
                    total_iterations=self._current_iteration,
                    final_output=final_output[:500] if final_output else None,
                    total_duration_ms=duration_ms,
                    stop_reason="stream_complete",
                )

        except Exception as e:
            self._status = SessionStatus.RUNNING
            self._error_message = str(e)
            logger.exception(f"[{self._session_id}] Error during astream: {e}")

            # 에러 로깅
            duration_ms = int((time.time() - start_time) * 1000)
            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="astream",
                    iteration=self._current_iteration,
                    error_type=type(e).__name__,
                )
                session_logger.log_graph_execution_complete(
                    success=False,
                    total_iterations=self._current_iteration,
                    final_output=None,
                    total_duration_ms=duration_ms,
                    stop_reason=f"exception: {type(e).__name__}",
                )

            raise

    async def execute(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        skip_permissions: bool = True,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        기존 ClaudeProcess.execute()와 호환되는 실행 메서드.

        Controller에서 기존 방식대로 호출할 수 있습니다.

        Args:
            prompt: 실행할 프롬프트
            timeout: 타임아웃 (초)
            skip_permissions: 권한 프롬프트 스킵 여부
            **kwargs: 추가 설정

        Returns:
            실행 결과 딕셔너리 (output, cost_usd, duration_ms 등)
        """
        if not self._initialized or not self._model or not self._model.process:
            raise RuntimeError("AgentSession not initialized")

        self._status = SessionStatus.RUNNING

        try:
            # 직접 ClaudeProcess.execute() 호출 (기존 호환성)
            result = await self._model.process.execute(
                prompt=prompt,
                timeout=timeout or self._timeout,
                skip_permissions=skip_permissions,
                **kwargs,
            )

            self._status = SessionStatus.RUNNING
            return result

        except Exception as e:
            self._status = SessionStatus.RUNNING
            self._error_message = str(e)
            logger.exception(f"[{self._session_id}] Error during execute: {e}")
            raise

    # ========================================================================
    # Lifecycle Methods
    # ========================================================================

    async def cleanup(self):
        """
        AgentSession 정리.

        ClaudeCLIChatModel과 관련 리소스를 정리합니다.
        """
        logger.info(f"[{self._session_id}] Cleaning up AgentSession...")

        if self._model:
            await self._model.cleanup()
            self._model = None

        self._graph = None
        self._checkpointer = None
        self._initialized = False
        self._status = SessionStatus.STOPPED

        logger.info(f"[{self._session_id}] ✅ AgentSession cleaned up")

    async def stop(self):
        """세션 중지 (cleanup의 별칭)"""
        await self.cleanup()

    def is_alive(self) -> bool:
        """프로세스가 살아있는지 확인"""
        if self._model and self._model.process:
            return self._model.process.is_alive()
        return False

    # ========================================================================
    # SessionInfo Compatibility
    # ========================================================================

    def get_session_info(self, pod_name: Optional[str] = None, pod_ip: Optional[str] = None) -> SessionInfo:
        """
        SessionInfo 객체 반환.

        기존 SessionManager와의 호환성을 위해 제공합니다.

        Args:
            pod_name: Pod 이름 (선택)
            pod_ip: Pod IP (선택)

        Returns:
            SessionInfo 인스턴스
        """
        return SessionInfo(
            session_id=self._session_id,
            session_name=self._session_name,
            status=self._status,
            created_at=self._created_at,
            pid=self.pid,
            error_message=self._error_message,
            model=self._model_name,
            max_turns=self._max_turns,
            timeout=self._timeout,
            autonomous=self._autonomous,
            autonomous_max_iterations=self._autonomous_max_iterations,
            storage_path=self.storage_path,
            pod_name=pod_name,
            pod_ip=pod_ip,
            role=self._role,
            manager_id=self._manager_id,
        )

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def get_state(self, thread_id: Optional[str] = None) -> Optional[AgentState]:
        """
        현재 그래프 상태 조회 (체크포인팅 필요).

        Args:
            thread_id: 스레드 ID

        Returns:
            현재 상태 또는 None
        """
        if not self._enable_checkpointing or not self._graph:
            return None

        config = {"configurable": {"thread_id": thread_id or self._current_thread_id}}
        try:
            state_snapshot = self._graph.get_state(config)
            return state_snapshot.values if state_snapshot else None
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not get state: {e}")
            return None

    def get_history(self, thread_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        실행 히스토리 조회 (체크포인팅 필요).

        Args:
            thread_id: 스레드 ID

        Returns:
            히스토리 리스트
        """
        if not self._enable_checkpointing or not self._graph:
            return []

        config = {"configurable": {"thread_id": thread_id or self._current_thread_id}}
        try:
            history = list(self._graph.get_state_history(config))
            return [{"config": h.config, "values": h.values} for h in history]
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not get history: {e}")
            return []

    def visualize(self, autonomous: bool = True) -> Optional[bytes]:
        """
        그래프 시각화 (PNG 이미지 반환).

        Args:
            autonomous: True이면 AutonomousGraph, False이면 기본 그래프

        Returns:
            PNG 이미지 바이트 또는 None
        """
        graph_to_visualize = None
        
        if autonomous and self._autonomous_graph:
            graph_to_visualize = self._autonomous_graph
        elif self._graph:
            graph_to_visualize = self._graph
        
        if not graph_to_visualize:
            return None

        try:
            return graph_to_visualize.get_graph().draw_mermaid_png()
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not visualize graph: {e}")
            return None

    def get_mermaid_diagram(self, autonomous: bool = True) -> Optional[str]:
        """
        Mermaid 다이어그램 문자열 반환.

        Args:
            autonomous: True이면 AutonomousGraph, False이면 기본 그래프

        Returns:
            Mermaid 다이어그램 문자열 또는 None
        """
        graph_to_visualize = None
        
        if autonomous and self._autonomous_graph:
            graph_to_visualize = self._autonomous_graph
        elif self._graph:
            graph_to_visualize = self._graph
        
        if not graph_to_visualize:
            return None

        try:
            return graph_to_visualize.get_graph().draw_mermaid()
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not generate mermaid diagram: {e}")
            return None

    def __repr__(self) -> str:
        return (
            f"AgentSession("
            f"session_id={self._session_id!r}, "
            f"status={self._status.value}, "
            f"initialized={self._initialized})"
        )
