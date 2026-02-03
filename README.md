# Claude Control

Claude Code 멀티 세션 관리 시스템

## 개요

Claude Control은 여러 Claude Code 세션을 동시에 관리하고 제어할 수 있는 시스템입니다.

### 주요 기능

- **멀티 세션 관리**: 여러 Claude Code 인스턴스를 세션 단위로 생성/관리
- **세션별 독립 스토리지**: 각 세션마다 독립적인 작업 디렉토리 제공
- **Multi-pod 지원**: Kubernetes 환경에서 여러 Pod에 걸친 세션 관리
- **Redis 기반 세션 공유**: Redis를 통한 세션 메타데이터 공유

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

### Claude 실행

```bash
curl -X POST http://localhost:8000/api/sessions/{session_id}/execute \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Hello, Claude!"
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
│   │   └── session_manager.py      # 세션 생명주기
│   ├── redis/
│   │   └── redis_client.py         # Redis 클라이언트
│   ├── pod/
│   │   └── pod_info.py             # Pod 정보 (Multi-pod)
│   ├── middleware/
│   │   └── session_router.py       # 세션 라우팅 미들웨어
│   ├── proxy/
│   │   └── internal_proxy.py       # Pod 간 프록시
│   └── utils/
│       └── utils.py                # 유틸리티
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 라이선스

MIT License
