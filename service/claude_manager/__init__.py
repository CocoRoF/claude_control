"""
Claude Manager Package

Core modules for Claude Code session management
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
