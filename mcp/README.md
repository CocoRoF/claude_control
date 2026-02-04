# MCP 서버 설정 폴더

이 폴더에 `.json` 파일을 추가하면 **모든 Claude Code 세션에서 자동으로 MCP 서버를 사용**할 수 있습니다.

## 사용 방법

### 1. JSON 파일 생성

이 폴더에 `{이름}.json` 파일을 생성합니다. 파일 이름이 MCP 서버 이름이 됩니다.

### 2. JSON 스키마

```json
{
  "type": "stdio | http | sse",
  "command": "실행 명령어 (stdio용)",
  "args": ["인자1", "인자2"],
  "env": {"환경변수": "값"},
  "url": "서버 URL (http/sse용)",
  "headers": {"헤더명": "값"},
  "description": "서버 설명 (선택사항)"
}
```

### 3. 예시

#### GitHub MCP 서버 (`github.json`)
```json
{
  "type": "http",
  "url": "https://api.githubcopilot.com/mcp/",
  "description": "GitHub 연동 - PR, Issue 관리"
}
```

#### 파일시스템 MCP 서버 (`filesystem.json`)
```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "/workspace", "/data"],
  "description": "파일시스템 접근"
}
```

#### PostgreSQL MCP 서버 (`database.json`)
```json
{
  "type": "stdio",
  "command": "npx",
  "args": ["-y", "@bytebase/dbhub", "--dsn", "${DATABASE_URL}"],
  "env": {
    "DATABASE_URL": "postgresql://user:pass@localhost:5432/mydb"
  },
  "description": "PostgreSQL 데이터베이스 접근"
}
```

#### Notion MCP 서버 (`notion.json`)
```json
{
  "type": "http",
  "url": "https://mcp.notion.com/mcp",
  "description": "Notion 페이지 및 데이터베이스 접근"
}
```

#### Sentry MCP 서버 (`sentry.json`)
```json
{
  "type": "http",
  "url": "https://mcp.sentry.dev/mcp",
  "description": "Sentry 에러 모니터링"
}
```

#### 커스텀 Python MCP 서버 (`custom.json`)
```json
{
  "type": "stdio",
  "command": "python",
  "args": ["tools/my_custom_server.py"],
  "env": {
    "API_KEY": "${MY_API_KEY}"
  },
  "description": "커스텀 도구 서버"
}
```

## 환경 변수 사용

JSON 파일 내에서 `${환경변수명}` 형식으로 환경 변수를 참조할 수 있습니다:

```json
{
  "type": "http",
  "url": "${API_BASE_URL}/mcp",
  "headers": {
    "Authorization": "Bearer ${API_TOKEN}"
  }
}
```

## 자동 로드

- `main.py` 실행 시 이 폴더의 모든 `.json` 파일이 자동으로 로드됩니다
- 로드된 MCP 서버는 **모든 세션에서 기본으로 사용 가능**합니다
- 세션 생성 시 추가 MCP 설정을 전달하면 **병합**됩니다

## 주의사항

1. **파일명 = 서버 이름**: `github.json` → MCP 서버 이름 `github`
2. **중복 방지**: 같은 이름의 서버가 세션 설정에 있으면 세션 설정이 우선
3. **검증**: 잘못된 JSON은 로드 시 경고 출력 후 건너뜀
4. **보안**: API 키는 환경 변수로 관리 권장

## 인기 MCP 서버 목록

| 서버 | URL | 설명 |
|------|-----|------|
| GitHub | `https://api.githubcopilot.com/mcp/` | GitHub 연동 |
| Notion | `https://mcp.notion.com/mcp` | Notion 연동 |
| Sentry | `https://mcp.sentry.dev/mcp` | 에러 모니터링 |
| Slack | `https://mcp.slack.com/mcp` | Slack 연동 |
| Linear | `https://mcp.linear.app/mcp` | 이슈 트래커 |

더 많은 MCP 서버: https://github.com/modelcontextprotocol/servers
