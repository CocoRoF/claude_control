"""
Orchestration module for Claude Control

Provides inter-session communication, manager sessions, and self-request mechanisms.
"""
from service.orchestration.orchestrator import (
    SessionOrchestrator,
    get_session_orchestrator
)
from service.orchestration.models import (
    SessionRole,
    TaskStatus,
    MilestoneStatus,
    InterSessionRequest,
    InterSessionResponse,
    Milestone,
    TaskPlan,
    OrchestrationConfig
)
from service.orchestration.self_request import (
    SelfRequestManager,
    get_self_request_manager
)

__all__ = [
    # Orchestrator
    "SessionOrchestrator",
    "get_session_orchestrator",
    # Models
    "SessionRole",
    "TaskStatus",
    "MilestoneStatus",
    "InterSessionRequest",
    "InterSessionResponse",
    "Milestone",
    "TaskPlan",
    "OrchestrationConfig",
    # Self-request
    "SelfRequestManager",
    "get_self_request_manager",
]
