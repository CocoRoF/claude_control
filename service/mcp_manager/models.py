"""
Data models for MCP Station
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class MCPServerType(str, Enum):
    """MCP 서버 타입"""
    PYTHON = "python"
    NODE = "node"


class MCPServerStatus(str, Enum):
    """MCP 서버 상태"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class CreateSessionRequest(BaseModel):
    """세션 생성 요청"""
    server_type: MCPServerType
    server_command: str = Field(..., description="실행할 MCP 서버 명령어 (예: python server.py, node server.js)")
    server_args: Optional[List[str]] = Field(default=None, description="추가 인자")
    env_vars: Optional[Dict[str, str]] = Field(default=None, description="환경 변수")
    working_dir: Optional[str] = Field(default=None, description="작업 디렉토리")
    session_name: Optional[str] = Field(default=None, description="세션 이름 (식별용)")
    additional_commands: Optional[List[str]] = Field(default=None, description="MCP 서버 실행 후 순차 실행할 추가 명령어 (예: ['npx playwright install chrome'])")


class SessionInfo(BaseModel):
    """세션 정보"""
    session_id: str
    session_name: Optional[str] = None
    server_type: MCPServerType
    status: MCPServerStatus
    created_at: datetime
    pid: Optional[int] = None
    error_message: Optional[str] = None
    server_command: Optional[str] = None
    server_args: Optional[List[str]] = None
    additional_commands: Optional[List[str]] = None
    mcp_initialized: bool = Field(default=False, description="MCP 프로토콜 초기화 완료 여부")
    # Multi-pod 라우팅을 위한 Pod 정보
    pod_name: Optional[str] = Field(default=None, description="세션이 실행 중인 Pod 이름")
    pod_ip: Optional[str] = Field(default=None, description="세션이 실행 중인 Pod IP")


class MCPRequest(BaseModel):
    """MCP 서버로의 요청"""
    session_id: str
    method: str = Field(..., description="MCP 메서드 (예: tools/list, tools/call)")
    params: Optional[Dict[str, Any]] = Field(default=None, description="메서드 파라미터")


class MCPResponse(BaseModel):
    """MCP 서버로부터의 응답"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
