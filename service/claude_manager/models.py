"""
Data models for Claude Control

Data model definitions for Claude Code session management.
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class SessionStatus(str, Enum):
    """Claude session status."""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


# =============================================================================
# MCP (Model Context Protocol) Configuration Models
# =============================================================================

class MCPServerStdio(BaseModel):
    """
    STDIO transport MCP server configuration.

    For MCP servers running as local processes (e.g., npx, python scripts).
    """
    type: Literal["stdio"] = "stdio"
    command: str = Field(..., description="Command to execute (e.g., 'npx', 'python')")
    args: List[str] = Field(default_factory=list, description="Command arguments")
    env: Optional[Dict[str, str]] = Field(default=None, description="Environment variables")


class MCPServerHTTP(BaseModel):
    """
    HTTP transport MCP server configuration.

    For remote HTTP-based MCP servers (e.g., Notion, GitHub).
    """
    type: Literal["http"] = "http"
    url: str = Field(..., description="MCP server URL (e.g., 'https://mcp.notion.com/mcp')")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Authentication headers")


class MCPServerSSE(BaseModel):
    """
    SSE transport MCP server configuration (deprecated, use HTTP instead).
    """
    type: Literal["sse"] = "sse"
    url: str = Field(..., description="SSE server URL")
    headers: Optional[Dict[str, str]] = Field(default=None, description="Authentication headers")


# MCP server configuration Union type
MCPServerConfig = Union[MCPServerStdio, MCPServerHTTP, MCPServerSSE]


class MCPConfig(BaseModel):
    """
    MCP server configuration collection.

    Manages multiple MCP servers by name.
    This configuration is generated as the session's .mcp.json file.

    Example:
        {
            "github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
            "filesystem": {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]}
        }
    """
    servers: Dict[str, MCPServerConfig] = Field(
        default_factory=dict,
        description="MCP server configurations (name -> config)"
    )

    def to_mcp_json(self) -> Dict[str, Any]:
        """
        Convert to .mcp.json file format.

        Returns:
            Dictionary in .mcp.json format recognized by Claude Code.
        """
        mcp_servers = {}
        for name, config in self.servers.items():
            if isinstance(config, MCPServerStdio):
                server_config = {
                    "command": config.command,
                    "args": config.args,
                }
                if config.env:
                    server_config["env"] = config.env
            elif isinstance(config, (MCPServerHTTP, MCPServerSSE)):
                server_config = {
                    "type": config.type,
                    "url": config.url,
                }
                if config.headers:
                    server_config["headers"] = config.headers
            else:
                continue
            mcp_servers[name] = server_config

        return {"mcpServers": mcp_servers}


# =============================================================================
# Session Management Models
# =============================================================================

class CreateSessionRequest(BaseModel):
    """
    Session creation request.

    Creates a new session to run Claude Code.
    Each session has its own independent working directory (storage).
    """
    session_name: Optional[str] = Field(
        default=None,
        description="Session name (for identification)"
    )
    working_dir: Optional[str] = Field(
        default=None,
        description="Working directory (auto-generated if not specified)"
    )
    env_vars: Optional[Dict[str, str]] = Field(
        default=None,
        description="Additional environment variables"
    )
    model: Optional[str] = Field(
        default=None,
        description="Claude model to use (e.g., claude-sonnet-4-20250514)"
    )
    max_turns: Optional[int] = Field(
        default=100,
        description="Maximum conversation turns (need sufficient turns for autonomous mode)"
    )
    timeout: Optional[float] = Field(
        default=1800.0,
        description="Default execution timeout per iteration (seconds)"
    )

    # Autonomous mode settings
    autonomous: Optional[bool] = Field(
        default=True,
        description="Autonomous mode - Claude performs tasks without asking questions"
    )
    autonomous_max_iterations: Optional[int] = Field(
        default=100,
        description="Maximum iterations for autonomous self-managing loop (prevents infinite loops)"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Additional system prompt (appended to default prompt)"
    )
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="List of allowed tools (None allows all tools)"
    )

    # MCP server settings
    mcp_config: Optional[MCPConfig] = Field(
        default=None,
        description="MCP server configuration - MCP tools to use in session"
    )


class SessionInfo(BaseModel):
    """
    Session information response.

    Contains current state and metadata of the session.
    """
    session_id: str
    session_name: Optional[str] = None
    status: SessionStatus
    created_at: datetime
    pid: Optional[int] = None
    error_message: Optional[str] = None

    # Claude-related information
    model: Optional[str] = None

    # Session execution settings (preserved from creation)
    max_turns: Optional[int] = Field(
        default=100,
        description="Maximum conversation turns per execution"
    )
    timeout: Optional[float] = Field(
        default=1800.0,
        description="Execution timeout per iteration (seconds)"
    )
    autonomous: Optional[bool] = Field(
        default=True,
        description="Autonomous mode enabled"
    )
    autonomous_max_iterations: Optional[int] = Field(
        default=100,
        description="Maximum autonomous iterations"
    )

    # Session storage path
    storage_path: Optional[str] = Field(
        default=None,
        description="Session-specific storage path"
    )

    # Pod information for multi-pod routing
    pod_name: Optional[str] = Field(
        default=None,
        description="Pod name where session is running"
    )
    pod_ip: Optional[str] = Field(
        default=None,
        description="Pod IP where session is running"
    )


class ExecuteRequest(BaseModel):
    """
    Claude execution request.

    Sends a prompt to Claude and executes it in the session.
    When autonomous mode is enabled, Claude independently completes tasks.
    """
    prompt: str = Field(
        ...,
        description="Prompt to send to Claude"
    )
    timeout: Optional[float] = Field(
        default=None,
        description="Execution timeout (seconds) - None uses session default (1800s)"
    )
    skip_permissions: Optional[bool] = Field(
        default=True,
        description="Skip permission prompts (required for autonomous mode)"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Additional system prompt for this execution"
    )
    max_turns: Optional[int] = Field(
        default=None,
        description="Maximum turns for this execution (None uses session setting)"
    )


class ExecuteResponse(BaseModel):
    """Claude execution response."""
    success: bool
    session_id: str
    output: Optional[str] = None
    error: Optional[str] = None
    cost_usd: Optional[float] = Field(
        default=None,
        description="API usage cost (USD)"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="Execution time (milliseconds)"
    )
    # Auto-continue fields for self-manager mode
    should_continue: bool = Field(
        default=False,
        description="Whether the task should continue (detected from [CONTINUE: ...] pattern)"
    )
    continue_hint: Optional[str] = Field(
        default=None,
        description="Hint about next step (extracted from [CONTINUE: ...] pattern)"
    )
    # Autonomous mode fields
    is_task_complete: bool = Field(
        default=False,
        description="Whether the task is complete (detected from [TASK_COMPLETE] pattern)"
    )
    iteration_count: Optional[int] = Field(
        default=None,
        description="Current iteration count in autonomous mode"
    )
    total_iterations: Optional[int] = Field(
        default=None,
        description="Total iterations completed in autonomous execution"
    )
    original_request: Optional[str] = Field(
        default=None,
        description="Original user request (for autonomous mode tracking)"
    )


class StorageFile(BaseModel):
    """Storage file information."""
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified_at: Optional[datetime] = None


class StorageListResponse(BaseModel):
    """Storage file list response."""
    session_id: str
    storage_path: str
    files: List[StorageFile]


class StorageFileContent(BaseModel):
    """Storage file content response."""
    session_id: str
    file_path: str
    content: str
    size: int
    encoding: str = "utf-8"


class AutonomousExecuteRequest(BaseModel):
    """
    Autonomous execution request.

    Starts a self-managing autonomous execution loop.
    Claude will continue working on the task until it's complete,
    periodically reminding itself of the original request.
    """
    prompt: str = Field(
        ...,
        description="Initial user request to complete autonomously"
    )
    timeout_per_iteration: Optional[float] = Field(
        default=None,
        description="Timeout for each iteration (seconds) - None uses session default (1800s)"
    )
    max_iterations: Optional[int] = Field(
        default=None,
        description="Maximum number of self-managing iterations - None uses session default (100)"
    )
    skip_permissions: Optional[bool] = Field(
        default=True,
        description="Skip permission prompts (required for autonomous mode)"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Additional system prompt for this execution"
    )
    max_turns: Optional[int] = Field(
        default=None,
        description="Maximum turns per iteration (None uses session setting)"
    )


class AutonomousExecuteResponse(BaseModel):
    """
    Autonomous execution response.

    Contains the final result after all autonomous iterations complete.
    """
    success: bool
    session_id: str
    is_complete: bool = Field(
        description="Whether the task was completed successfully"
    )
    total_iterations: int = Field(
        description="Total number of iterations executed"
    )
    original_request: str = Field(
        description="The original user request"
    )
    final_output: Optional[str] = Field(
        default=None,
        description="Output from the final iteration"
    )
    all_outputs: Optional[List[str]] = Field(
        default=None,
        description="Outputs from all iterations (if requested)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if execution failed"
    )
    total_duration_ms: Optional[int] = Field(
        default=None,
        description="Total execution time across all iterations (milliseconds)"
    )
    total_cost_usd: Optional[float] = Field(
        default=None,
        description="Total API cost across all iterations (USD)"
    )
    stop_reason: str = Field(
        default="unknown",
        description="Reason for stopping: 'complete', 'max_iterations', 'error', 'user_stop'"
    )
