"""
Autonomous Graph - 난이도 기반 LangGraph StateGraph

질문의 난이도에 따라 다른 실행 경로를 제공하는 자율 실행 그래프입니다.

난이도 분류:
- 쉬움 (easy): 바로 답변 진행
- 중간 (medium): 답변 + 검토 수행
- 어려움 (hard): TODO 생성 → 개별 진행 → 전체 검토 → 최종 답변

그래프 구조:
    START
      ↓
    classify_difficulty (난이도 분류)
      ↓ [conditional: easy/medium/hard]

    [easy]
      → direct_answer → END

    [medium]
      → answer → review → [conditional: approved/rejected]
        → approved: END
        → rejected: answer (재시도)

    [hard]
      → create_todos → execute_todo → check_progress
        → [conditional: has_more/complete]
        → has_more: execute_todo (반복)
        → complete: final_review → final_answer → END

사용 예:
    from service.langgraph.autonomous_graph import (
        AutonomousGraph,
        AutonomousState,
        Difficulty,
    )

    # 그래프 생성
    graph = AutonomousGraph(model)
    compiled = graph.compile()

    # 실행
    result = await compiled.ainvoke({"input": "What is 2+2?"})
"""

from logging import getLogger
from enum import Enum
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver

from service.langgraph.claude_cli_model import ClaudeCLIChatModel
from service.logging.session_logger import get_session_logger, SessionLogger

logger = getLogger(__name__)


# ============================================================================
# Enums & Types
# ============================================================================


class Difficulty(str, Enum):
    """질문 난이도"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ReviewResult(str, Enum):
    """검토 결과"""
    APPROVED = "approved"
    REJECTED = "rejected"


class TodoStatus(str, Enum):
    """TODO 항목 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class TodoItem(TypedDict):
    """TODO 항목"""
    id: int
    title: str
    description: str
    status: TodoStatus
    result: Optional[str]


# ============================================================================
# State Reducers
# ============================================================================


def add_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    """메시지 리스트 병합 (reducer 함수)"""
    return left + right


def update_todos(left: List[TodoItem], right: List[TodoItem]) -> List[TodoItem]:
    """TODO 리스트 업데이트 (reducer 함수) - ID 기준 병합"""
    if not right:
        return left

    result = {item["id"]: item for item in left}
    for item in right:
        result[item["id"]] = item

    return list(result.values())


# ============================================================================
# State Definition
# ============================================================================


class AutonomousState(TypedDict):
    """
    Autonomous 그래프의 상태 정의.

    LangGraph StateGraph에서 사용되는 상태 스키마입니다.
    """
    # 원본 입력
    input: str

    # 대화 메시지 히스토리
    messages: Annotated[List[BaseMessage], add_messages]

    # 난이도 분류 결과
    difficulty: Optional[Difficulty]

    # 현재 단계
    current_step: str

    # 답변 내용
    answer: Optional[str]

    # 검토 결과
    review_result: Optional[ReviewResult]
    review_feedback: Optional[str]
    review_count: int

    # TODO 리스트 (어려운 문제용)
    todos: Annotated[List[TodoItem], update_todos]
    current_todo_index: int

    # 최종 결과
    final_answer: Optional[str]

    # 실행 메타데이터
    metadata: Dict[str, Any]

    # 에러 정보
    error: Optional[str]

    # 완료 여부
    is_complete: bool


# ============================================================================
# Autonomous Graph Class
# ============================================================================


class AutonomousGraph:
    """
    난이도 기반 Autonomous 실행 그래프.

    질문의 난이도를 자동으로 판단하고 적절한 실행 경로를 선택합니다.
    """

    # 검토 재시도 최대 횟수
    MAX_REVIEW_RETRIES = 3

    # 난이도 분류 프롬프트
    CLASSIFY_PROMPT = """You are a task difficulty classifier. Analyze the given input and classify its difficulty level.

Classification criteria:
- EASY: Simple questions, factual lookups, basic calculations, straightforward requests
  Examples: "What is 2+2?", "What is the capital of France?", "Hello, how are you?"

- MEDIUM: Moderate complexity, requires some reasoning or multi-step thinking, but can be done in one response
  Examples: "Explain how photosynthesis works", "Compare Python and JavaScript", "Write a simple function"

- HARD: Complex tasks requiring multiple steps, research, planning, or iterative execution
  Examples: "Build a web application", "Debug this complex codebase", "Design a system architecture"

IMPORTANT: Respond with ONLY one of these exact words: easy, medium, hard

Input to classify:
{input}"""

    REVIEW_PROMPT = """You are a quality reviewer. Review the following answer for accuracy and completeness.

Original Question:
{question}

Answer to Review:
{answer}

Review the answer and determine:
1. Is the answer accurate and correct?
2. Does it fully address the question?
3. Is there anything missing or incorrect?

Respond in this exact format:
VERDICT: approved OR rejected
FEEDBACK: (your detailed feedback)"""

    CREATE_TODOS_PROMPT = """You are a task planner. Break down the following complex task into smaller, manageable TODO items.

Task:
{input}

Create a list of TODO items that, when completed in order, will fully accomplish the task.
Each TODO should be:
- Specific and actionable
- Self-contained (can be executed independently)
- Ordered logically (dependencies respected)

Respond in this exact JSON format only (no markdown, no explanation):
[
  {{"id": 1, "title": "Short title", "description": "Detailed description of what to do"}},
  {{"id": 2, "title": "Short title", "description": "Detailed description of what to do"}}
]"""

    EXECUTE_TODO_PROMPT = """You are executing a specific task from a larger plan.

Overall Goal:
{goal}

Current TODO Item:
Title: {title}
Description: {description}

Previous completed items and their results:
{previous_results}

Execute this TODO item now. Provide a complete solution/implementation/answer for this specific item.
Be thorough and ensure this item is fully completed."""

    FINAL_REVIEW_PROMPT = """You are conducting a final review of a completed complex task.

Original Request:
{input}

TODO Items and Results:
{todo_results}

Review the entire work:
1. Was the original request fully addressed?
2. Are all TODO items completed satisfactorily?
3. Is there any integration work needed?
4. Identify any gaps or issues.

Provide your comprehensive review."""

    FINAL_ANSWER_PROMPT = """Based on the completed work and review, provide the final comprehensive answer.

Original Request:
{input}

Completed Work:
{todo_results}

Review Feedback:
{review_feedback}

Now provide the final, polished answer that addresses the original request completely.
Synthesize all the completed work into a coherent, complete response."""

    def __init__(
        self,
        model: ClaudeCLIChatModel,
        session_id: Optional[str] = None,
        enable_checkpointing: bool = False,
        max_review_retries: int = 3,
    ):
        """
        AutonomousGraph 초기화.

        Args:
            model: Claude CLI 모델
            session_id: 세션 ID (로깅용)
            enable_checkpointing: 체크포인팅 활성화
            max_review_retries: 검토 재시도 최대 횟수
        """
        self._model = model
        self._session_id = session_id or (model.session_id if model else "unknown")
        self._enable_checkpointing = enable_checkpointing
        self._max_review_retries = max_review_retries
        self._checkpointer: Optional[MemorySaver] = None
        self._graph: Optional[CompiledStateGraph] = None

        logger.info(f"[{self._session_id}] AutonomousGraph initialized")

    def _get_logger(self) -> Optional[SessionLogger]:
        """세션 로거 가져오기"""
        return get_session_logger(self._session_id, create_if_missing=True)

    # ========================================================================
    # Graph Nodes
    # ========================================================================

    async def _classify_difficulty_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        난이도 분류 노드.

        입력을 분석하여 easy/medium/hard 중 하나로 분류합니다.
        """
        logger.info(f"[{self._session_id}] classify_difficulty: Classifying input difficulty")
        session_logger = self._get_logger()

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="classify_difficulty",
                iteration=0,
                state_summary={"input_length": len(state.get("input", ""))}
            )

        try:
            input_text = state.get("input", "")

            # 난이도 분류 요청
            prompt = self.CLASSIFY_PROMPT.format(input=input_text)
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            response_text = response.content.strip().lower()

            # 응답에서 난이도 추출
            if "easy" in response_text:
                difficulty = Difficulty.EASY
            elif "medium" in response_text:
                difficulty = Difficulty.MEDIUM
            elif "hard" in response_text:
                difficulty = Difficulty.HARD
            else:
                # 기본값: medium
                logger.warning(f"[{self._session_id}] Could not parse difficulty from: {response_text}, defaulting to medium")
                difficulty = Difficulty.MEDIUM

            logger.info(f"[{self._session_id}] classify_difficulty: Classified as {difficulty.value}")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="classify_difficulty",
                    iteration=0,
                    output_preview=f"Difficulty: {difficulty.value}",
                    duration_ms=0,
                    state_changes={"difficulty": difficulty.value}
                )

            return {
                "difficulty": difficulty,
                "current_step": "difficulty_classified",
                "messages": [HumanMessage(content=input_text)],
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in classify_difficulty: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="classify_difficulty",
                    iteration=0,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _direct_answer_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        직접 답변 노드 (쉬운 문제용).

        추가 검토 없이 바로 답변을 생성합니다.
        """
        logger.info(f"[{self._session_id}] direct_answer: Generating direct answer")
        session_logger = self._get_logger()

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="direct_answer",
                iteration=0,
                state_summary={"difficulty": "easy"}
            )

        try:
            input_text = state.get("input", "")

            # 직접 답변 요청
            messages = [HumanMessage(content=input_text)]
            response = await self._model.ainvoke(messages)
            answer = response.content

            logger.info(f"[{self._session_id}] direct_answer: Answer generated ({len(answer)} chars)")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="direct_answer",
                    iteration=0,
                    output_preview=answer[:200] if answer else None,
                    duration_ms=0,
                    state_changes={"answer_generated": True, "is_complete": True}
                )

            return {
                "answer": answer,
                "final_answer": answer,
                "messages": [response],
                "current_step": "direct_answer_complete",
                "is_complete": True,
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in direct_answer: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="direct_answer",
                    iteration=0,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _answer_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        답변 생성 노드 (중간 난이도용).

        답변을 생성하고 검토를 위해 전달합니다.
        """
        logger.info(f"[{self._session_id}] answer: Generating answer for review")
        session_logger = self._get_logger()
        review_count = state.get("review_count", 0)

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="answer",
                iteration=review_count,
                state_summary={
                    "difficulty": "medium",
                    "review_count": review_count,
                    "has_previous_feedback": bool(state.get("review_feedback"))
                }
            )

        try:
            input_text = state.get("input", "")
            previous_feedback = state.get("review_feedback")

            # 피드백이 있으면 포함
            if previous_feedback and review_count > 0:
                prompt = f"""Previous attempt was rejected with this feedback:
{previous_feedback}

Please try again with the following request, addressing the feedback:
{input_text}"""
            else:
                prompt = input_text

            messages = [HumanMessage(content=prompt)]
            response = await self._model.ainvoke(messages)
            answer = response.content

            logger.info(f"[{self._session_id}] answer: Answer generated ({len(answer)} chars)")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="answer",
                    iteration=review_count,
                    output_preview=answer[:200] if answer else None,
                    duration_ms=0,
                    state_changes={"answer_generated": True}
                )

            return {
                "answer": answer,
                "messages": [response],
                "current_step": "answer_generated",
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in answer: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="answer",
                    iteration=review_count,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _review_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        검토 노드 (중간 난이도용).

        생성된 답변을 검토하고 승인/거부를 결정합니다.
        """
        logger.info(f"[{self._session_id}] review: Reviewing answer")
        session_logger = self._get_logger()
        review_count = state.get("review_count", 0) + 1

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="review",
                iteration=review_count,
                state_summary={
                    "review_count": review_count,
                    "answer_length": len(state.get("answer", ""))
                }
            )

        try:
            input_text = state.get("input", "")
            answer = state.get("answer", "")

            # 검토 요청
            prompt = self.REVIEW_PROMPT.format(question=input_text, answer=answer)
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            review_text = response.content

            # 검토 결과 파싱
            review_result = ReviewResult.APPROVED
            feedback = ""

            if "VERDICT:" in review_text:
                lines = review_text.split("\n")
                for line in lines:
                    if line.startswith("VERDICT:"):
                        verdict = line.replace("VERDICT:", "").strip().lower()
                        if "rejected" in verdict:
                            review_result = ReviewResult.REJECTED
                    elif line.startswith("FEEDBACK:"):
                        feedback = line.replace("FEEDBACK:", "").strip()
                        # 나머지 줄도 피드백에 포함
                        idx = lines.index(line)
                        feedback = "\n".join([feedback] + lines[idx + 1:])
                        break
            else:
                # VERDICT 형식이 없으면 approved로 간주
                feedback = review_text

            logger.info(f"[{self._session_id}] review: Result = {review_result.value}")

            # 최대 재시도 횟수 도달 시 강제 승인
            is_complete = False
            if review_result == ReviewResult.REJECTED and review_count >= self._max_review_retries:
                logger.warning(f"[{self._session_id}] review: Max retries reached, forcing approval")
                review_result = ReviewResult.APPROVED
                is_complete = True
            elif review_result == ReviewResult.APPROVED:
                is_complete = True

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="review",
                    iteration=review_count,
                    output_preview=f"Result: {review_result.value}",
                    duration_ms=0,
                    state_changes={
                        "review_result": review_result.value,
                        "review_count": review_count,
                        "is_complete": is_complete
                    }
                )

            result = {
                "review_result": review_result,
                "review_feedback": feedback,
                "review_count": review_count,
                "messages": [response],
                "current_step": "review_complete",
            }

            if is_complete:
                result["final_answer"] = answer
                result["is_complete"] = True

            return result

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in review: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="review",
                    iteration=review_count,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _create_todos_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        TODO 생성 노드 (어려운 문제용).

        복잡한 작업을 분해하여 TODO 리스트를 생성합니다.
        """
        logger.info(f"[{self._session_id}] create_todos: Creating TODO list")
        session_logger = self._get_logger()

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="create_todos",
                iteration=0,
                state_summary={"difficulty": "hard"}
            )

        try:
            input_text = state.get("input", "")

            # TODO 생성 요청
            prompt = self.CREATE_TODOS_PROMPT.format(input=input_text)
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            response_text = response.content.strip()

            # JSON 파싱
            import json

            # 마크다운 코드 블록 제거
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            try:
                todos_raw = json.loads(response_text.strip())
            except json.JSONDecodeError as je:
                logger.warning(f"[{self._session_id}] Failed to parse todos, creating single TODO: {je}")
                todos_raw = [{"id": 1, "title": "Execute task", "description": input_text}]

            # TodoItem 형식으로 변환
            todos: List[TodoItem] = []
            for item in todos_raw:
                todos.append({
                    "id": item.get("id", len(todos) + 1),
                    "title": item.get("title", f"Task {len(todos) + 1}"),
                    "description": item.get("description", ""),
                    "status": TodoStatus.PENDING,
                    "result": None,
                })

            logger.info(f"[{self._session_id}] create_todos: Created {len(todos)} TODO items")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="create_todos",
                    iteration=0,
                    output_preview=f"Created {len(todos)} TODOs",
                    duration_ms=0,
                    state_changes={"todos_created": len(todos)}
                )

            return {
                "todos": todos,
                "current_todo_index": 0,
                "messages": [response],
                "current_step": "todos_created",
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in create_todos: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="create_todos",
                    iteration=0,
                    error_type=type(e).__name__
                )

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _execute_todo_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        TODO 실행 노드 (어려운 문제용).

        현재 인덱스의 TODO 항목을 실행합니다.
        """
        current_index = state.get("current_todo_index", 0)
        todos = state.get("todos", [])

        logger.info(f"[{self._session_id}] execute_todo: Executing TODO {current_index + 1}/{len(todos)}")
        session_logger = self._get_logger()

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="execute_todo",
                iteration=current_index,
                state_summary={
                    "current_index": current_index,
                    "total_todos": len(todos)
                }
            )

        try:
            if current_index >= len(todos):
                logger.warning(f"[{self._session_id}] execute_todo: Index out of range")
                return {
                    "current_step": "todos_complete",
                }

            input_text = state.get("input", "")
            todo = todos[current_index]

            # 이전 결과 수집
            previous_results = ""
            for i, t in enumerate(todos):
                if i < current_index and t.get("result"):
                    previous_results += f"\n[{t['title']}]: {t['result'][:500]}...\n"

            if not previous_results:
                previous_results = "(No previous items completed)"

            # TODO 실행 요청
            prompt = self.EXECUTE_TODO_PROMPT.format(
                goal=input_text,
                title=todo["title"],
                description=todo["description"],
                previous_results=previous_results,
            )
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            result = response.content

            # TODO 상태 업데이트
            updated_todo: TodoItem = {
                **todo,
                "status": TodoStatus.COMPLETED,
                "result": result,
            }

            logger.info(f"[{self._session_id}] execute_todo: TODO {current_index + 1} completed")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="execute_todo",
                    iteration=current_index,
                    output_preview=result[:200] if result else None,
                    duration_ms=0,
                    state_changes={
                        "todo_completed": todo["title"],
                        "new_index": current_index + 1
                    }
                )

            return {
                "todos": [updated_todo],
                "current_todo_index": current_index + 1,
                "messages": [response],
                "current_step": f"todo_{current_index + 1}_complete",
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in execute_todo: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="execute_todo",
                    iteration=current_index,
                    error_type=type(e).__name__
                )

            # 실패한 TODO 업데이트
            if current_index < len(todos):
                failed_todo: TodoItem = {
                    **todos[current_index],
                    "status": TodoStatus.FAILED,
                    "result": f"Error: {str(e)}",
                }
                return {
                    "todos": [failed_todo],
                    "current_todo_index": current_index + 1,
                    "current_step": f"todo_{current_index + 1}_failed",
                }

            return {
                "error": str(e),
                "is_complete": True,
            }

    async def _check_progress_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        진행 상황 확인 노드 (어려운 문제용).

        모든 TODO가 완료되었는지 확인합니다.
        """
        current_index = state.get("current_todo_index", 0)
        todos = state.get("todos", [])

        logger.info(f"[{self._session_id}] check_progress: {current_index}/{len(todos)} completed")
        session_logger = self._get_logger()

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="check_progress",
                iteration=current_index,
                state_summary={
                    "current_index": current_index,
                    "total_todos": len(todos)
                }
            )

        # 완료된 TODO 수 계산
        completed = sum(1 for t in todos if t.get("status") == TodoStatus.COMPLETED)

        if session_logger:
            session_logger.log_graph_node_exit(
                node_name="check_progress",
                iteration=current_index,
                output_preview=f"Progress: {completed}/{len(todos)}",
                duration_ms=0,
                state_changes={"completed_count": completed}
            )

        return {
            "current_step": "progress_checked",
            "metadata": {
                **state.get("metadata", {}),
                "completed_todos": completed,
                "total_todos": len(todos),
            },
        }

    async def _final_review_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        최종 검토 노드 (어려운 문제용).

        모든 TODO 결과를 종합적으로 검토합니다.
        """
        logger.info(f"[{self._session_id}] final_review: Reviewing all completed work")
        session_logger = self._get_logger()
        todos = state.get("todos", [])

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="final_review",
                iteration=0,
                state_summary={"total_todos": len(todos)}
            )

        try:
            input_text = state.get("input", "")

            # TODO 결과 수집
            todo_results = ""
            for todo in todos:
                status = todo.get("status", TodoStatus.PENDING)
                result = todo.get("result", "No result")
                todo_results += f"\n### {todo['title']} [{status}]\n{result}\n"

            # 최종 검토 요청
            prompt = self.FINAL_REVIEW_PROMPT.format(
                input=input_text,
                todo_results=todo_results,
            )
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            review_feedback = response.content

            logger.info(f"[{self._session_id}] final_review: Review completed")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="final_review",
                    iteration=0,
                    output_preview=review_feedback[:200] if review_feedback else None,
                    duration_ms=0,
                    state_changes={"final_review_done": True}
                )

            return {
                "review_feedback": review_feedback,
                "messages": [response],
                "current_step": "final_review_complete",
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in final_review: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="final_review",
                    iteration=0,
                    error_type=type(e).__name__
                )

            return {
                "review_feedback": f"Review failed: {str(e)}",
                "current_step": "final_review_failed",
            }

    async def _final_answer_node(self, state: AutonomousState) -> Dict[str, Any]:
        """
        최종 답변 생성 노드 (어려운 문제용).

        모든 작업 결과를 종합하여 최종 답변을 생성합니다.
        """
        logger.info(f"[{self._session_id}] final_answer: Generating final answer")
        session_logger = self._get_logger()
        todos = state.get("todos", [])

        if session_logger:
            session_logger.log_graph_node_enter(
                node_name="final_answer",
                iteration=0,
                state_summary={"total_todos": len(todos)}
            )

        try:
            input_text = state.get("input", "")
            review_feedback = state.get("review_feedback", "")

            # TODO 결과 수집
            todo_results = ""
            for todo in todos:
                status = todo.get("status", TodoStatus.PENDING)
                result = todo.get("result", "No result")
                todo_results += f"\n### {todo['title']} [{status}]\n{result}\n"

            # 최종 답변 요청
            prompt = self.FINAL_ANSWER_PROMPT.format(
                input=input_text,
                todo_results=todo_results,
                review_feedback=review_feedback,
            )
            messages = [HumanMessage(content=prompt)]

            response = await self._model.ainvoke(messages)
            final_answer = response.content

            logger.info(f"[{self._session_id}] final_answer: Final answer generated ({len(final_answer)} chars)")

            if session_logger:
                session_logger.log_graph_node_exit(
                    node_name="final_answer",
                    iteration=0,
                    output_preview=final_answer[:200] if final_answer else None,
                    duration_ms=0,
                    state_changes={"final_answer_generated": True, "is_complete": True}
                )

            return {
                "final_answer": final_answer,
                "messages": [response],
                "current_step": "complete",
                "is_complete": True,
            }

        except Exception as e:
            logger.exception(f"[{self._session_id}] Error in final_answer: {e}")

            if session_logger:
                session_logger.log_graph_error(
                    error_message=str(e),
                    node_name="final_answer",
                    iteration=0,
                    error_type=type(e).__name__
                )

            # 에러 시 TODO 결과만으로 답변
            todo_results = ""
            for todo in todos:
                if todo.get("result"):
                    todo_results += f"{todo['title']}: {todo['result']}\n"

            return {
                "final_answer": f"Task completed with errors.\n\nResults:\n{todo_results}",
                "error": str(e),
                "is_complete": True,
            }

    # ========================================================================
    # Conditional Edges
    # ========================================================================

    def _route_by_difficulty(self, state: AutonomousState) -> Literal["easy", "medium", "hard"]:
        """난이도에 따른 라우팅"""
        difficulty = state.get("difficulty")

        if difficulty == Difficulty.EASY:
            return "easy"
        elif difficulty == Difficulty.MEDIUM:
            return "medium"
        else:
            return "hard"

    def _route_after_review(self, state: AutonomousState) -> Literal["approved", "retry"]:
        """검토 결과에 따른 라우팅"""
        review_result = state.get("review_result")

        if review_result == ReviewResult.APPROVED:
            return "approved"
        else:
            return "retry"

    def _route_after_progress_check(self, state: AutonomousState) -> Literal["continue", "complete"]:
        """진행 상황에 따른 라우팅"""
        current_index = state.get("current_todo_index", 0)
        todos = state.get("todos", [])

        if current_index >= len(todos):
            return "complete"
        else:
            return "continue"

    # ========================================================================
    # Graph Building
    # ========================================================================

    def build(self) -> CompiledStateGraph:
        """
        그래프 빌드 및 컴파일.

        Returns:
            컴파일된 StateGraph
        """
        logger.info(f"[{self._session_id}] Building AutonomousGraph...")

        # 체크포인터 설정
        if self._enable_checkpointing:
            self._checkpointer = MemorySaver()

        # StateGraph 생성
        graph_builder = StateGraph(AutonomousState)

        # ========== 노드 등록 ==========

        # 공통
        graph_builder.add_node("classify_difficulty", self._classify_difficulty_node)

        # Easy path
        graph_builder.add_node("direct_answer", self._direct_answer_node)

        # Medium path
        graph_builder.add_node("answer", self._answer_node)
        graph_builder.add_node("review", self._review_node)

        # Hard path
        graph_builder.add_node("create_todos", self._create_todos_node)
        graph_builder.add_node("execute_todo", self._execute_todo_node)
        graph_builder.add_node("check_progress", self._check_progress_node)
        graph_builder.add_node("final_review", self._final_review_node)
        graph_builder.add_node("final_answer", self._final_answer_node)

        # ========== 엣지 정의 ==========

        # START -> classify_difficulty
        graph_builder.add_edge(START, "classify_difficulty")

        # classify_difficulty -> [easy/medium/hard]
        graph_builder.add_conditional_edges(
            "classify_difficulty",
            self._route_by_difficulty,
            {
                "easy": "direct_answer",
                "medium": "answer",
                "hard": "create_todos",
            }
        )

        # Easy path: direct_answer -> END
        graph_builder.add_edge("direct_answer", END)

        # Medium path: answer -> review -> [approved/retry]
        graph_builder.add_edge("answer", "review")
        graph_builder.add_conditional_edges(
            "review",
            self._route_after_review,
            {
                "approved": END,
                "retry": "answer",
            }
        )

        # Hard path: create_todos -> execute_todo -> check_progress -> [continue/complete]
        graph_builder.add_edge("create_todos", "execute_todo")
        graph_builder.add_edge("execute_todo", "check_progress")
        graph_builder.add_conditional_edges(
            "check_progress",
            self._route_after_progress_check,
            {
                "continue": "execute_todo",
                "complete": "final_review",
            }
        )
        graph_builder.add_edge("final_review", "final_answer")
        graph_builder.add_edge("final_answer", END)

        # ========== 그래프 컴파일 ==========

        if self._checkpointer:
            self._graph = graph_builder.compile(checkpointer=self._checkpointer)
        else:
            self._graph = graph_builder.compile()

        logger.info(f"[{self._session_id}] ✅ AutonomousGraph built successfully")
        return self._graph

    def compile(self) -> CompiledStateGraph:
        """build()의 별칭"""
        return self.build()

    @property
    def graph(self) -> Optional[CompiledStateGraph]:
        """컴파일된 그래프 반환"""
        return self._graph

    def get_initial_state(self, input_text: str, **kwargs) -> AutonomousState:
        """
        초기 상태 생성.

        Args:
            input_text: 사용자 입력
            **kwargs: 추가 메타데이터

        Returns:
            초기 상태 딕셔너리
        """
        return {
            "input": input_text,
            "messages": [],
            "difficulty": None,
            "current_step": "start",
            "answer": None,
            "review_result": None,
            "review_feedback": None,
            "review_count": 0,
            "todos": [],
            "current_todo_index": 0,
            "final_answer": None,
            "metadata": kwargs,
            "error": None,
            "is_complete": False,
        }

    def visualize(self) -> Optional[bytes]:
        """
        그래프 시각화 (PNG 이미지 반환).

        Returns:
            PNG 이미지 바이트 또는 None
        """
        if not self._graph:
            logger.warning(f"[{self._session_id}] Graph not built yet, building now...")
            self.build()

        try:
            return self._graph.get_graph().draw_mermaid_png()
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not visualize graph: {e}")
            return None

    def get_mermaid_diagram(self) -> Optional[str]:
        """
        Mermaid 다이어그램 문자열 반환.

        Returns:
            Mermaid 다이어그램 문자열 또는 None
        """
        if not self._graph:
            logger.warning(f"[{self._session_id}] Graph not built yet, building now...")
            self.build()

        try:
            return self._graph.get_graph().draw_mermaid()
        except Exception as e:
            logger.warning(f"[{self._session_id}] Could not generate mermaid diagram: {e}")
            return None
