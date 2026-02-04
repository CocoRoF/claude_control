# Claude Control

Claude Code 멀티 세션 관리 시스템

## 개요

Claude Control은 여러 Claude Code 세션을 동시에 관리하고 제어할 수 있는 시스템입니다.

### 주요 기능

- **멀티 세션 관리**: 여러 Claude Code 인스턴스를 세션 단위로 생성/관리
- **세션별 독립 스토리지**: 각 세션마다 독립적인 작업 디렉토리 제공
- **Multi-pod 지원**: Kubernetes 환경에서 여러 Pod에 걸친 세션 관리
- **Redis 기반 세션 공유**: Redis를 통한 세션 메타데이터 공유
- **🔌 MCP 자동 로드**: `mcp/` 폴더의 JSON 설정 자동 로드
- **🔧 커스텀 도구**: `tools/` 폴더의 Python 도구 자동 등록

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Control                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [API Layer]                                                    │
│   ├── POST /api/sessions          - 세션 생성                   │
│   ├── GET  /api/sessions          - 세션 목록                   │
│   ├── GET  /api/sessions/{id}     - 세션 조회                   │
│   ├── DELETE /api/sessions/{id}   - 세션 삭제                   │
│   ├── POST /api/sessions/{id}/execute - Claude 실행             │
│   └── GET  /api/sessions/{id}/storage - 스토리지 조회           │
│                                                                  │
│   [Session Manager]                                              │
│   ├── 세션 생명주기 관리                                         │
│   ├── Redis 기반 메타데이터 저장                                 │
│   └── Multi-pod 세션 라우팅                                      │
│                                                                  │
│   [Claude Process]                                               │
│   ├── claude CLI 프로세스 관리                                   │
│   ├── 독립 스토리지 디렉토리                                     │
│   └── 프롬프트 실행 및 응답 수집                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 설치

### 필수 요구사항

- Python 3.11+
- Claude CLI (`npm install -g @anthropic-ai/claude-code`)
- Redis (선택사항, Multi-pod 환경에서 필요)

### 설치 방법

```bash
# 의존성 설치
pip install -r requirements.txt

# 또는 pyproject.toml 사용
pip install -e .
```

## 환경 변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `APP_HOST` | 서버 호스트 | `0.0.0.0` |
| `APP_PORT` | 서버 포트 | `8000` |
| `DEBUG_MODE` | 디버그 모드 | `false` |
| `REDIS_HOST` | Redis 호스트 | `redis` |
| `REDIS_PORT` | Redis 포트 | `6379` |
| `REDIS_PASSWORD` | Redis 비밀번호 | - |
| `CLAUDE_STORAGE_ROOT` | 세션 스토리지 루트 경로 | `/tmp/claude_sessions` |
| `ANTHROPIC_API_KEY` | Anthropic API 키 (필수) | - |
| `CLAUDE_DANGEROUSLY_SKIP_PERMISSIONS` | 자율 모드 - 권한 프롬프트 건너뛰기 | `true` |

## 실행

```bash
# 개발 모드 (hot reload)
DEBUG_MODE=true python main.py

# 프로덕션 모드
python main.py
```

## API 사용 예시

### 세션 생성

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "my-session",
    "model": "claude-sonnet-4-20250514"
  }'
```

### Claude 실행 (기본)

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, Claude!"
  }'
```

### 🤖 자율 모드 실행 예시

자율 모드를 사용하면 Claude가 질문 없이 스스로 작업을 완료합니다.

#### Next.js 프로젝트 생성 및 Git Push

```bash
# 세션 생성 (자율 모드가 기본 활성화)
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "nextjs-project",
    "max_turns": 100,
    "autonomous": true
  }'

# 자율적으로 Next.js 프로젝트 생성 및 Git Push 수행
curl -X POST http://localhost:8000/api/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Create a complete Next.js 14 project with: 1) App Router, 2) Tailwind CSS, 3) TypeScript, 4) A modern landing page with hero section, features section, and footer. 5) Initialize git, make initial commit, and push to https://github.com/user/my-nextjs-project.git",
    "timeout": 1800,
    "skip_permissions": true,
    "system_prompt": "You are an autonomous AI agent. Complete all tasks without asking for confirmation. Create files, run commands, and push to git independently. Do not ask questions - make reasonable decisions and proceed."
  }'
```

#### 자동 코드 리팩토링

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze all files in this project. Refactor for better code quality: add TypeScript types, improve naming conventions, add JSDoc comments, and fix any bugs. Commit changes with descriptive messages.",
    "system_prompt": "Work autonomously without asking questions. Make all necessary changes directly.",
    "max_turns": 50
  }'
```

#### 테스트 작성 자동화

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write comprehensive unit tests for all components and utilities in this project using Jest and React Testing Library. Aim for 80%+ coverage. Run tests and fix any failures.",
    "timeout": 1200
  }'
```

### 세션 삭제

```bash
curl -X DELETE http://localhost:8000/api/sessions/{session_id}
```

## 프로젝트 구조

```
claude_control/
├── main.py                         # FastAPI 앱 진입점
├── controller/
│   └── claude_controller.py        # API 엔드포인트
├── service/
│   ├── claude_manager/             # 핵심 세션 관리
│   │   ├── models.py               # 데이터 모델
│   │   ├── process_manager.py      # Claude 프로세스 관리
│   │   ├── session_manager.py      # 세션 생명주기
│   │   └── mcp_tools_server.py     # LangChain → MCP 래퍼
│   ├── redis/
│   │   └── redis_client.py         # Redis 클라이언트
│   ├── pod/
│   │   └── pod_info.py             # Pod 정보 (Multi-pod)
│   ├── middleware/
│   │   └── session_router.py       # 세션 라우팅 미들웨어
│   ├── proxy/
│   │   └── internal_proxy.py       # Pod 간 프록시
│   ├── utils/
│   │   └── utils.py                # 유틸리티
│   └── mcp_loader.py               # MCP/도구 자동 로더
├── mcp/                            # 📁 MCP 서버 설정 (자동 로드)
│   ├── README.md                   # 사용 가이드
│   └── *.json                      # MCP 서버 설정 파일
├── tools/                          # 📁 커스텀 도구 (자동 로드)
│   ├── README.md                   # 사용 가이드
│   ├── base.py                     # BaseTool, @tool 데코레이터
│   └── *_tool.py                   # 커스텀 도구 파일
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 📁 MCP/Tools 자동 로드

### mcp/ 폴더 (MCP 서버 자동 등록)

`mcp/` 폴더에 `.json` 파일을 추가하면 **모든 세션에서 자동으로 사용 가능**합니다.

```bash
# 예: mcp/github.json
{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp/",
  "description": "GitHub MCP 서버"
}

# 예: mcp/database.json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@bytebase/dbhub", "--dsn", "${DATABASE_URL}"],
  "description": "PostgreSQL MCP 서버"
}
```

👉 자세한 내용: [mcp/README.md](mcp/README.md)

### tools/ 폴더 (커스텀 도구 자동 등록)

`tools/` 폴더에 `*_tool.py` 파일을 추가하면 **모든 세션에서 자동으로 사용 가능**합니다.

```python
# 예: tools/my_tool.py
from tools.base import tool

@tool
def search_database(query: str) -> str:
    """Search the database for records"""
    return f"Results for: {query}"

TOOLS = [search_database]
```

👉 자세한 내용: [tools/README.md](tools/README.md)

## 🔌 MCP 서버 설정 (API)

Claude Code 세션에 MCP 서버를 연결하여 외부 도구와 데이터에 접근할 수 있습니다.

### MCP 서버 설정 예시

```bash
# GitHub, 파일시스템, PostgreSQL MCP 서버 연결
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "full-stack-session",
    "mcp_config": {
      "servers": {
        "github": {
          "type": "http",
          "url": "https://api.githubcopilot.com/mcp/"
        },
        "filesystem": {
          "type": "stdio",
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace"]
        },
        "database": {
          "type": "stdio",
          "command": "npx",
          "args": ["-y", "@bytebase/dbhub", "--dsn", "postgresql://user:pass@localhost:5432/mydb"]
        }
      }
    }
  }'
```

### 지원 MCP 트랜스포트

| 타입 | 설명 | 사용 예 |
|------|------|---------|
| `stdio` | 로컬 프로세스 | npx, python 스크립트 |
| `http` | 원격 HTTP 서버 | GitHub, Notion, Sentry |
| `sse` | Server-Sent Events (deprecated) | 레거시 서버 |

### 인기 MCP 서버

```json
{
  "servers": {
    "github": {"type": "http", "url": "https://api.githubcopilot.com/mcp/"},
    "notion": {"type": "http", "url": "https://mcp.notion.com/mcp"},
    "sentry": {"type": "http", "url": "https://mcp.sentry.dev/mcp"},
    "slack": {"type": "http", "url": "https://mcp.slack.com/mcp"}
  }
}
```

## 🔧 LangChain 도구 통합

LangChain 도구를 MCP 서버로 래핑하여 Claude Code 세션에서 사용할 수 있습니다.

### LangChain 도구를 MCP 서버로 변환

```python
from langchain_core.tools import tool
from service.claude_manager.mcp_tools_server import MCPToolsServer

# LangChain 도구 정의
@tool
def search_web(query: str) -> str:
    """Search the web for information"""
    return f"Search results for: {query}"

@tool
def analyze_code(code: str, language: str = "python") -> str:
    """Analyze code for potential issues"""
    return f"Analysis of {language} code: No issues found"

# MCP 서버 생성 및 실행
server = MCPToolsServer(
    name="custom-tools",
    tools=[search_web, analyze_code]
)

# stdio 트랜스포트로 실행
server.run(transport="stdio")

# 또는 HTTP 서버로 실행
# server.run(transport="http", port=8080)
```

### LangChain MCP 서버를 세션에 연결

```bash
# LangChain 도구 MCP 서버를 세션에 연결
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "session_name": "langchain-session",
    "mcp_config": {
      "servers": {
        "custom-tools": {
          "type": "stdio",
          "command": "python",
          "args": ["/path/to/my_tools_server.py"]
        }
      }
    }
  }'
```

### 편의 함수로 MCP 설정 생성

```python
from service.claude_manager.mcp_tools_server import (
    create_filesystem_mcp_config,
    create_github_mcp_config,
    create_postgres_mcp_config,
    create_custom_mcp_config
)

# 파일시스템 접근
fs_config = create_filesystem_mcp_config(["/workspace", "/data"])

# GitHub 연결
github_config = create_github_mcp_config()

# PostgreSQL 연결
db_config = create_postgres_mcp_config("postgresql://user:pass@localhost:5432/mydb")

# 커스텀 서버
custom_config = create_custom_mcp_config(
    server_type="stdio",
    command="python",
    args=["my_server.py"],
    env={"API_KEY": "xxx"}
)
```

## 라이선스

MIT License

