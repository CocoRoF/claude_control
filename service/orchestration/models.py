"""
Orchestration Data Models

Models for inter-session communication, milestone-based task orchestration,
and self-managing agent coordination.
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class SessionRole(str, Enum):
    """Role of a session in the orchestration hierarchy."""
    MANAGER = "manager"      # Controls other sessions, orchestrates tasks
    WORKER = "worker"        # Executes tasks assigned by manager
    STANDALONE = "standalone"  # Independent session (default)


class TaskStatus(str, Enum):
    """Status of an orchestrated task."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MilestoneStatus(str, Enum):
    """Status of a milestone."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class InterSessionRequest(BaseModel):
    """
    Request from one session to another.

    Enables manager sessions to delegate tasks to worker sessions,
    and supports peer-to-peer communication between sessions.
    """
    request_id: str = Field(..., description="Unique request identifier")
    source_session_id: str = Field(..., description="Session ID of the requester")
    target_session_id: str = Field(..., description="Session ID of the target")

    # Request content
    prompt: str = Field(..., description="Prompt/command to execute")
    system_prompt: Optional[str] = Field(default=None, description="Override system prompt")

    # Execution parameters
    timeout: float = Field(default=600.0, description="Execution timeout (seconds)")
    max_turns: Optional[int] = Field(default=None, description="Max turns for execution")
    priority: int = Field(default=0, description="Priority (higher = more urgent)")

    # Orchestration metadata
    task_id: Optional[str] = Field(default=None, description="Parent task ID")
    milestone_id: Optional[str] = Field(default=None, description="Associated milestone ID")

    # Callback configuration
    callback_on_complete: bool = Field(default=True, description="Notify source on completion")
    callback_on_continue: bool = Field(default=True, description="Notify source on [CONTINUE:]")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class InterSessionResponse(BaseModel):
    """Response to an inter-session request."""
    request_id: str = Field(..., description="Original request ID")
    source_session_id: str = Field(..., description="Session that made the request")
    target_session_id: str = Field(..., description="Session that executed the request")

    # Execution result
    success: bool = Field(..., description="Whether execution succeeded")
    output: Optional[str] = Field(default=None, description="Execution output")
    error: Optional[str] = Field(default=None, description="Error message if failed")

    # Self-manager continuation
    should_continue: bool = Field(default=False, description="Whether [CONTINUE:] was detected")
    continue_hint: Optional[str] = Field(default=None, description="Continue hint from output")

    # Execution metrics
    duration_ms: Optional[int] = Field(default=None, description="Execution duration")

    # Timestamps
    completed_at: datetime = Field(default_factory=datetime.now)


class Milestone(BaseModel):
    """
    A milestone in a task plan.

    Milestones break down complex tasks into manageable chunks,
    enabling timeout-resilient execution through multi-request patterns.
    """
    milestone_id: str = Field(..., description="Unique milestone identifier")
    name: str = Field(..., description="Milestone name")
    description: str = Field(default="", description="Detailed description")

    # Status tracking
    status: MilestoneStatus = Field(default=MilestoneStatus.NOT_STARTED)

    # Execution configuration
    prompt_template: str = Field(..., description="Prompt template for this milestone")
    timeout: float = Field(default=300.0, description="Timeout for this milestone")
    max_retries: int = Field(default=2, description="Max retry attempts")
    retry_count: int = Field(default=0, description="Current retry count")

    # Dependencies
    depends_on: List[str] = Field(default_factory=list, description="Milestone IDs this depends on")

    # Results
    output: Optional[str] = Field(default=None, description="Execution output")
    error: Optional[str] = Field(default=None, description="Error if failed")

    # Timestamps
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    def is_ready(self, completed_milestones: List[str]) -> bool:
        """Check if all dependencies are met."""
        return all(dep in completed_milestones for dep in self.depends_on)


class TaskPlan(BaseModel):
    """
    A complete task plan with milestones.

    TaskPlans enable long-running tasks to be executed as a series of
    smaller, timeout-safe operations through self-request mechanisms.
    """
    task_id: str = Field(..., description="Unique task identifier")
    name: str = Field(..., description="Task name")
    description: str = Field(default="", description="Task description")

    # Original request
    original_prompt: str = Field(..., description="Original user prompt")

    # Session assignment
    session_id: str = Field(..., description="Session executing this task")
    manager_session_id: Optional[str] = Field(default=None, description="Manager session if any")

    # Milestones
    milestones: List[Milestone] = Field(default_factory=list)
    current_milestone_index: int = Field(default=0)

    # Status
    status: TaskStatus = Field(default=TaskStatus.PENDING)

    # Success criteria
    success_criteria: List[str] = Field(default_factory=list)
    criteria_met: List[bool] = Field(default_factory=list)

    # Progress log
    progress_log: List[Dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    def get_current_milestone(self) -> Optional[Milestone]:
        """Get the current milestone."""
        if 0 <= self.current_milestone_index < len(self.milestones):
            return self.milestones[self.current_milestone_index]
        return None

    def get_completed_milestone_ids(self) -> List[str]:
        """Get IDs of completed milestones."""
        return [m.milestone_id for m in self.milestones if m.status == MilestoneStatus.COMPLETED]

    def get_next_milestone(self) -> Optional[Milestone]:
        """Get the next milestone that is ready to execute."""
        completed = self.get_completed_milestone_ids()
        for m in self.milestones:
            if m.status == MilestoneStatus.NOT_STARTED and m.is_ready(completed):
                return m
        return None

    def add_progress_log(self, event: str, details: Dict[str, Any] = None):
        """Add an entry to the progress log."""
        self.progress_log.append({
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "details": details or {}
        })

    def is_complete(self) -> bool:
        """Check if all milestones are completed."""
        return all(
            m.status in (MilestoneStatus.COMPLETED, MilestoneStatus.SKIPPED)
            for m in self.milestones
        )


class OrchestrationConfig(BaseModel):
    """
    Configuration for session orchestration.

    Controls how sessions interact and manage long-running tasks.
    """
    # Self-request configuration
    enable_self_request: bool = Field(
        default=True,
        description="Allow sessions to send requests to themselves for continuation"
    )

    # Timeout management
    default_milestone_timeout: float = Field(
        default=300.0,
        description="Default timeout for each milestone (seconds)"
    )
    max_milestone_timeout: float = Field(
        default=600.0,
        description="Maximum timeout for any single milestone"
    )

    # Auto-continue behavior
    auto_continue_on_signal: bool = Field(
        default=True,
        description="Automatically continue when [CONTINUE:] is detected"
    )
    max_auto_continues: int = Field(
        default=50,
        description="Maximum number of auto-continues per task"
    )
    continue_delay_ms: int = Field(
        default=100,
        description="Delay between continues (milliseconds)"
    )

    # Inter-session communication
    enable_inter_session: bool = Field(
        default=True,
        description="Allow sessions to send requests to each other"
    )
    inter_session_timeout: float = Field(
        default=30.0,
        description="Timeout for inter-session request delivery"
    )

    # Manager session settings
    manager_can_cancel: bool = Field(
        default=True,
        description="Manager sessions can cancel worker tasks"
    )
    manager_can_reassign: bool = Field(
        default=True,
        description="Manager sessions can reassign tasks between workers"
    )

    # Queue settings
    max_queue_size: int = Field(
        default=100,
        description="Maximum pending requests per session"
    )

    # Retry configuration
    default_max_retries: int = Field(
        default=2,
        description="Default max retries for failed milestones"
    )


class SessionOrchestrationState(BaseModel):
    """
    Orchestration state for a single session.

    Tracks the session's role, active tasks, and communication status.
    """
    session_id: str
    role: SessionRole = Field(default=SessionRole.STANDALONE)

    # Manager relationship
    manager_session_id: Optional[str] = Field(
        default=None,
        description="ID of the manager session (if this is a worker)"
    )
    worker_session_ids: List[str] = Field(
        default_factory=list,
        description="IDs of worker sessions (if this is a manager)"
    )

    # Active tasks
    active_task_id: Optional[str] = Field(default=None, description="Currently executing task")
    pending_requests: List[str] = Field(default_factory=list, description="Pending request IDs")

    # Auto-continue tracking
    continue_count: int = Field(default=0, description="Number of continues in current task")
    last_continue_hint: Optional[str] = Field(default=None)

    # Status
    is_busy: bool = Field(default=False, description="Whether session is currently executing")
    last_activity: Optional[datetime] = Field(default=None)
