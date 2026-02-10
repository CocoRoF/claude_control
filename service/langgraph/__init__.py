"""
LangGraph Integration Module

Claude CLI와 LangGraph를 통합하여 상태 관리 기능과 CLI의 파일 관리/MCP 기능을
동시에 활용합니다.

핵심 컴포넌트:
- ClaudeCLIChatModel: ClaudeProcess를 래핑한 LangChain ChatModel
- AgentSession: CompiledStateGraph 기반 에이전트 세션
- AgentSessionManager: AgentSession 관리자

사용 예:
    # 방법 1: AgentSession 직접 생성
    from service.langgraph import AgentSession

    agent = await AgentSession.create(
        working_dir="/path/to/project",
        model_name="claude-sonnet-4-20250514",
    )
    result = await agent.invoke("Hello")

    # 방법 2: AgentSessionManager 사용
    from service.langgraph import get_agent_session_manager

    manager = get_agent_session_manager()
    agent = await manager.create_agent_session(request)
    result = await agent.invoke("Hello")
"""

from service.langgraph.claude_cli_model import ClaudeCLIChatModel
from service.langgraph.agent_session import AgentSession, AgentState
from service.langgraph.agent_session_manager import (
    AgentSessionManager,
    get_agent_session_manager,
    reset_agent_session_manager,
)

__all__ = [
    # Model
    "ClaudeCLIChatModel",
    # Session
    "AgentSession",
    "AgentState",
    # Manager
    "AgentSessionManager",
    "get_agent_session_manager",
    "reset_agent_session_manager",
]
