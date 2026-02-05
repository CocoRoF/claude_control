"""
Claude Manager Package.

Core modules for Claude Code session management, process control, and MCP configuration.

This package provides:
- SessionManager: High-level session lifecycle management with Redis support
- ClaudeProcess: Low-level Claude CLI subprocess management
- Models: Pydantic data models for sessions, execution, and MCP configuration
- MCP Tools Server: LangChain to MCP server wrapper

Example:
    from service.claude_manager import SessionManager, CreateSessionRequest

    manager = SessionManager()
    request = CreateSessionRequest(session_name="my-session")
    session = await manager.create_session(request)
"""
from service.claude_manager.models import (
    SessionStatus,
    SessionInfo,
    CreateSessionRequest,
    ExecuteRequest,
    ExecuteResponse,
    StorageFile,
    StorageListResponse,
    StorageFileContent,
    # MCP config models
    MCPConfig,
    MCPServerStdio,
    MCPServerHTTP,
    MCPServerSSE,
)
from service.claude_manager.session_manager import SessionManager, get_session_manager
from service.claude_manager.process_manager import ClaudeProcess

__all__ = [
    # Models
    'SessionStatus',
    'SessionInfo',
    'CreateSessionRequest',
    'ExecuteRequest',
    'ExecuteResponse',
    'StorageFile',
    'StorageListResponse',
    'StorageFileContent',
    # MCP Models
    'MCPConfig',
    'MCPServerStdio',
    'MCPServerHTTP',
    'MCPServerSSE',
    # Managers
    'SessionManager',
    'get_session_manager',
    'ClaudeProcess',
]
