# MCP Station

MCP (Model Context Protocol) 서버 관리 및 라우팅 시스템

## 아키텍처 개요
```
┌─────────────────┐
│ polarag_backend │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────────────────────────────┐
│         MCP Station (FastAPI)           │
│  ┌────────────────────────────────────┐ │
│  │      Session Manager               │ │
│  │  ┌──────────┬──────────┬────────┐ │ │
│  │  │Session 1 │Session 2 │Session N│ │ │
│  │  └──────────┴──────────┴────────┘ │ │
│  └────────────────────────────────────┘ │
│  ┌────────────────────────────────────┐ │
│  │      Process Manager               │ │
│  │  ┌──────────┬──────────┬────────┐ │ │
│  │  │Python    │Node.js   │Python  │ │ │
│  │  │MCP Server│MCP Server│MCP Srv │ │ │
│  │  │(PID 123) │(PID 456) │(PID 789│ │ │
│  │  └──────────┴──────────┴────────┘ │ │
│  └────────────────────────────────────┘ │
│  ┌────────────────────────────────────┐ │
│  │           Router                   │ │
│  │  (JSON-RPC over stdio)             │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## 핵심 컴포넌트

### 1. Session Manager (`session_manager.py`)
- MCP 서버 세션의 생명주기 관리
- 세션 생성, 조회, 삭제
- 죽은 세션 자동 정리

### 2. Process Manager (`process_manager.py`)
- 개별 MCP 서버를 서브프로세스로 실행
- Python 및 Node.js 기반 MCP 서버 지원
- stdio를 통한 JSON-RPC 통신
- 프로세스 상태 모니터링

### 3. Router (`router.py`)
- 요청을 적절한 세션으로 라우팅
- JSON-RPC 2.0 프로토콜 지원
- 에러 핸들링 및 타임아웃 관리

### 4. FastAPI Application (`main.py`)
- RESTful API 엔드포인트 제공
- 세션 관리 API
- MCP 요청 프록시 API

## API 엔드포인트

### 세션 관리

#### POST `/sessions` - 세션 생성
```json
{
  "server_type": "python",
  "server_command": "/path/to/mcp_server.py",
  "server_args": ["--port", "8080"],
  "env_vars": {
    "API_KEY": "secret"
  },
  "working_dir": "/app/servers"
}
```

**응답:**
```json
{
  "session_id": "uuid-here",
  "server_type": "python",
  "status": "running",
  "created_at": "2025-09-29T...",
  "pid": 12345
}
```

#### GET `/sessions` - 세션 목록
모든 활성 세션 조회

#### GET `/sessions/{session_id}` - 세션 정보
특정 세션의 상태 조회

#### DELETE `/sessions/{session_id}` - 세션 삭제
세션 종료 및 프로세스 정리

### MCP 요청

#### POST `/mcp/request` - MCP 요청 라우팅
```json
{
  "session_id": "uuid-here",
  "method": "tools/list",
  "params": {}
}
```

**응답:**
```json
{
  "success": true,
  "data": {
    "tools": [...]
  }
}
```

## Docker Compose 네트워크 통신

### Backend에서 MCP Station 호출 예시:

```python
import httpx

# 세션 생성
async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://mcp_station:20100/sessions",
        json={
            "server_type": "python",
            "server_command": "/app/my_mcp_server.py"
        }
    )
    session_info = response.json()
    session_id = session_info["session_id"]

    # MCP 요청
    response = await client.post(
        "http://mcp_station:20100/mcp/request",
        json={
            "session_id": session_id,
            "method": "tools/list",
            "params": {}
        }
    )
    result = response.json()
```

## 실행 방법

### 로컬 개발
```bash
pip install -r requirements.txt
python main.py
```

### Docker Compose
```yaml
mcp_station:
  build: ./mcp_station/.
  container_name: mcp_station
  restart: unless-stopped
  ports:
    - 20100:20100
```

## 환경 변수

현재는 하드코딩된 포트를 사용하지만, 필요시 `.env` 파일로 설정 가능:

```env
MCP_STATION_PORT=20100
LOG_LEVEL=INFO
```

## 향후 개선 사항

1. **인증/인가**: API 키 또는 JWT 기반 인증
2. **영속성**: 세션 정보를 DB에 저장
3. **모니터링**: Prometheus 메트릭 추가
4. **Rate Limiting**: 요청 제한
5. **WebSocket 지원**: 실시간 양방향 통신
6. **Health Check 개선**: 프로세스 상태 상세 모니터링
