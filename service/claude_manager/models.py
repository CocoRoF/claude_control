"""
Data models for Claude Control

Claude Code 세션 관리를 위한 데이터 모델 정의
"""
from enum import Enum
from typing import Optional, Dict, Any, List, Union, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class SessionStatus(str, Enum):
    """Claude 세션 상태"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


# =============================================================================
# MCP (Model Context Protocol) 설정 모델
# =============================================================================

class MCPServerStdio(BaseModel):
    """
    STDIO 트랜스포트 MCP 서버 설정
    
    로컬 프로세스로 실행되는 MCP 서버 (예: npx, python 스크립트)
    """
    type: Literal["stdio"] = "stdio"
    command: str = Field(..., description="실행할 명령어 (예: 'npx', 'python')")
    args: List[str] = Field(default_factory=list, description="명령어 인자")
    env: Optional[Dict[str, str]] = Field(default=None, description="환경 변수")


class MCPServerHTTP(BaseModel):
    """
    HTTP 트랜스포트 MCP 서버 설정
    
    원격 HTTP 기반 MCP 서버 (예: Notion, GitHub)
    """
    type: Literal["http"] = "http"
    url: str = Field(..., description="MCP 서버 URL (예: 'https://mcp.notion.com/mcp')")
    headers: Optional[Dict[str, str]] = Field(default=None, description="인증 헤더")


class MCPServerSSE(BaseModel):
    """
    SSE 트랜스포트 MCP 서버 설정 (deprecated, HTTP 사용 권장)
    """
    type: Literal["sse"] = "sse"
    url: str = Field(..., description="SSE 서버 URL")
    headers: Optional[Dict[str, str]] = Field(default=None, description="인증 헤더")


# MCP 서버 설정 Union 타입
MCPServerConfig = Union[MCPServerStdio, MCPServerHTTP, MCPServerSSE]


class MCPConfig(BaseModel):
    """
    MCP 서버 설정 컬렉션
    
    여러 MCP 서버를 이름으로 관리합니다.
    이 설정은 세션의 .mcp.json 파일로 생성됩니다.
    
    Example:
        {
            "github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
            "filesystem": {"type": "stdio", "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path"]}
        }
    """
    servers: Dict[str, MCPServerConfig] = Field(
        default_factory=dict,
        description="MCP 서버 설정 (이름 -> 설정)"
    )
    
    def to_mcp_json(self) -> Dict[str, Any]:
        """
        .mcp.json 파일 형식으로 변환
        
        Returns:
            Claude Code가 인식하는 .mcp.json 형식의 딕셔너리
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
# 세션 관리 모델
# =============================================================================

class CreateSessionRequest(BaseModel):
    """
    세션 생성 요청
    
    Claude Code를 실행할 새로운 세션을 생성합니다.
    각 세션은 독립적인 작업 디렉토리(storage)를 가집니다.
    """
    session_name: Optional[str] = Field(
        default=None, 
        description="세션 이름 (식별용)"
    )
    working_dir: Optional[str] = Field(
        default=None, 
        description="작업 디렉토리 (미지정시 자동 생성)"
    )
    env_vars: Optional[Dict[str, str]] = Field(
        default=None, 
        description="추가 환경 변수"
    )
    model: Optional[str] = Field(
        default=None,
        description="사용할 Claude 모델 (예: claude-sonnet-4-20250514)"
    )
    max_turns: Optional[int] = Field(
        default=50,
        description="최대 대화 턴 수 (자율 모드에서 충분한 턴 필요)"
    )
    
    # 자율 모드 설정
    autonomous: Optional[bool] = Field(
        default=True,
        description="자율 모드 - Claude가 질문 없이 스스로 작업 수행"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="추가 시스템 프롬프트 (기본 프롬프트에 추가됨)"
    )
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="허용할 도구 목록 (None이면 모든 도구 허용)"
    )
    
    # MCP 서버 설정
    mcp_config: Optional[MCPConfig] = Field(
        default=None,
        description="MCP 서버 설정 - 세션에서 사용할 MCP 도구들"
    )


class SessionInfo(BaseModel):
    """
    세션 정보 응답
    
    세션의 현재 상태와 메타데이터를 포함합니다.
    """
    session_id: str
    session_name: Optional[str] = None
    status: SessionStatus
    created_at: datetime
    pid: Optional[int] = None
    error_message: Optional[str] = None
    
    # Claude 관련 정보
    model: Optional[str] = None
    
    # 세션 스토리지 경로
    storage_path: Optional[str] = Field(
        default=None, 
        description="세션 전용 스토리지 경로"
    )
    
    # Multi-pod 라우팅을 위한 Pod 정보
    pod_name: Optional[str] = Field(
        default=None, 
        description="세션이 실행 중인 Pod 이름"
    )
    pod_ip: Optional[str] = Field(
        default=None, 
        description="세션이 실행 중인 Pod IP"
    )


class ExecuteRequest(BaseModel):
    """
    Claude 실행 요청
    
    세션에서 Claude에게 프롬프트를 전달하고 실행합니다.
    자율 모드가 활성화되면 Claude가 스스로 판단하여 작업을 완료합니다.
    """
    prompt: str = Field(
        ..., 
        description="Claude에게 전달할 프롬프트"
    )
    timeout: Optional[float] = Field(
        default=600.0,
        description="실행 타임아웃 (초) - 자율 모드에서는 길게 설정 권장"
    )
    skip_permissions: Optional[bool] = Field(
        default=True,
        description="권한 프롬프트 건너뛰기 (자율 모드 필수)"
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="실행별 추가 시스템 프롬프트"
    )
    max_turns: Optional[int] = Field(
        default=None,
        description="이 실행의 최대 턴 수 (None이면 세션 설정 사용)"
    )


class ExecuteResponse(BaseModel):
    """
    Claude 실행 응답
    """
    success: bool
    session_id: str
    output: Optional[str] = None
    error: Optional[str] = None
    cost_usd: Optional[float] = Field(
        default=None,
        description="API 사용 비용 (USD)"
    )
    duration_ms: Optional[int] = Field(
        default=None,
        description="실행 시간 (밀리초)"
    )


class StorageFile(BaseModel):
    """스토리지 파일 정보"""
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified_at: Optional[datetime] = None


class StorageListResponse(BaseModel):
    """스토리지 파일 목록 응답"""
    session_id: str
    storage_path: str
    files: List[StorageFile]


class StorageFileContent(BaseModel):
    """스토리지 파일 내용 응답"""
    session_id: str
    file_path: str
    content: str
    size: int
    encoding: str = "utf-8"
