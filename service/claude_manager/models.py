"""
Data models for Claude Control

Claude Code 세션 관리를 위한 데이터 모델 정의
"""
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime


class SessionStatus(str, Enum):
    """Claude 세션 상태"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


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
        default=None,
        description="최대 대화 턴 수"
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
    """
    prompt: str = Field(
        ..., 
        description="Claude에게 전달할 프롬프트"
    )
    timeout: Optional[float] = Field(
        default=300.0,
        description="실행 타임아웃 (초)"
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
