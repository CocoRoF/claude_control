# Claude Control 업데이트 내역

## 버전: UI 대시보드 개선

이 업데이트는 Claude Control에 세션 로깅 시스템, 중앙 명령 시스템, 웹 UI 대시보드를 추가합니다.

---

## 1. 세션 로깅 시스템 (Session Logging System)

### 새로운 파일
- `service/logging/__init__.py`
- `service/logging/session_logger.py`
- `logs/` 디렉토리 (로그 파일 저장 위치)

### 주요 기능
- **세션별 로그 파일**: 각 세션은 `logs/{session_id}.log` 형태의 고유한 로그 파일을 갖습니다.
- **타임스탬프 기록**: 모든 로그 항목에 KST(한국 표준시) 타임스탬프가 포함됩니다.
- **로그 레벨 지원**:
  - `DEBUG`: 디버그 정보
  - `INFO`: 일반 정보
  - `WARNING`: 경고
  - `ERROR`: 오류
  - `COMMAND`: Claude로 전송된 명령
  - `RESPONSE`: Claude의 응답

### 사용 예시
```python
from service.logging.session_logger import get_session_logger

# 세션 로거 가져오기
logger = get_session_logger(session_id, session_name)

# 명령 로깅
logger.log_command(prompt="Hello Claude", timeout=600)

# 응답 로깅
logger.log_response(success=True, output="Hello!", duration_ms=1500)

# 일반 로깅
logger.info("Session started")
logger.error("Connection failed")
```

---

## 2. 중앙 명령 시스템 (Central Command System)

### 새로운 파일
- `controller/command_controller.py`

### API 엔드포인트

#### 배치 명령 실행
```
POST /api/command/batch
```
여러 세션에 동시에 명령을 실행합니다.

**요청 본문:**
```json
{
  "session_ids": ["session-1", "session-2"],
  "prompt": "Hello Claude!",
  "timeout": 600,
  "skip_permissions": true,
  "parallel": true
}
```

**응답:**
```json
{
  "total_sessions": 2,
  "successful": 2,
  "failed": 0,
  "results": [...],
  "total_duration_ms": 1500
}
```

#### 브로드캐스트 명령
```
POST /api/command/broadcast?prompt=Hello&timeout=600
```
모든 활성 세션에 명령을 브로드캐스트합니다.

#### 세션 모니터링
```
GET /api/command/monitor
GET /api/command/monitor/{session_id}
```
세션 상태 및 최근 로그를 포함한 모니터링 정보를 조회합니다.

#### 로그 조회
```
GET /api/command/logs
GET /api/command/logs/{session_id}?limit=100&level=ERROR
```
세션 로그를 조회합니다. 로그 레벨로 필터링이 가능합니다.

#### 통계
```
GET /api/command/stats
```
전체 명령 실행 통계를 조회합니다.

---

## 3. 웹 UI 대시보드 (Web UI Dashboard)

### 새로운 파일
- `static/index.html` - 대시보드 HTML
- `static/style.css` - 스타일시트
- `static/app.js` - JavaScript 애플리케이션

### 접속 방법
```
http://localhost:8000/dashboard
```

### 주요 기능

#### 세션 관리
- **세션 목록**: 좌측 사이드바에서 모든 세션 확인
- **상태 표시**: 실행 중(녹색), 중지됨(회색), 시작 중(노란색), 오류(빨간색)
- **세션 생성**: "New" 버튼으로 새 세션 생성
- **세션 삭제**: 세션 항목의 삭제 버튼 사용

#### 명령 탭 (Command)
- 선택한 세션에 명령 전송
- 타임아웃 및 최대 턴 설정
- 실행 결과 실시간 표시

#### 로그 탭 (Logs)
- 세션별 로그 조회
- 로그 레벨 필터링
- 실시간 새로고침

#### 배치 탭 (Batch)
- 여러 세션 선택
- 일괄 명령 실행
- 병렬/순차 실행 선택
- 결과 요약 및 상세 보기

### 단축키
- `Ctrl/Cmd + Enter`: 명령 실행
- `Escape`: 모달 닫기

---

## 4. main.py 변경사항

### 추가된 임포트
```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from controller.command_controller import router as command_router
```

### 추가된 라우터
```python
app.include_router(command_router)
```

### 정적 파일 마운트
```python
app.mount("/static", StaticFiles(directory="static"), name="static")
```

### 대시보드 엔드포인트
```python
@app.get("/dashboard")
async def dashboard():
    return FileResponse("static/index.html")
```

---

## 설치 및 실행

### 요구사항
기존 요구사항과 동일합니다. 추가 의존성은 없습니다.

### 실행
```bash
# 개발 모드
DEBUG_MODE=true python main.py

# 프로덕션 모드
python main.py
```

### 대시보드 접속
브라우저에서 `http://localhost:8000/dashboard`로 접속합니다.

---

## 프로젝트 구조

```
claude_control/
├── main.py                           # FastAPI 앱 (업데이트됨)
├── controller/
│   ├── claude_controller.py          # 기존 API 컨트롤러
│   └── command_controller.py         # 🆕 중앙 명령 컨트롤러
├── service/
│   ├── logging/                      # 🆕 로깅 서비스
│   │   ├── __init__.py
│   │   └── session_logger.py
│   └── ...
├── static/                           # 🆕 웹 UI 대시보드
│   ├── index.html
│   ├── style.css
│   └── app.js
├── logs/                             # 🆕 세션 로그 디렉토리
└── update.md                         # 🆕 이 문서
```

---

## 참고사항

1. **로그 파일 관리**: 로그 파일은 자동으로 삭제되지 않습니다. 필요에 따라 수동으로 정리하거나 로그 로테이션을 구성하세요.

2. **보안**: 프로덕션 환경에서는 대시보드에 대한 인증을 추가하는 것을 권장합니다.

3. **성능**: 배치 명령 실행 시 병렬 모드(`parallel: true`)를 사용하면 더 빠른 실행이 가능합니다.

4. **브라우저 호환성**: 대시보드는 최신 웹 브라우저(Chrome, Firefox, Safari, Edge)에서 테스트되었습니다.
