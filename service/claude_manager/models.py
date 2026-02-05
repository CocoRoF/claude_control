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
        default=50,
        description="Maximum conversation turns (need sufficient turns for autonomous mode)"
    )

    # Autonomous mode settings
    autonomous: Optional[bool] = Field(
        default=True,
        description="Autonomous mode - Claude performs tasks without asking questions"
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
        default=600.0,
        description="Execution timeout (seconds) - recommend longer timeout for autonomous mode"
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
