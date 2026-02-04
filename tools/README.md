# Tools 폴더

이 폴더에 **Python 도구 파일**을 추가하면 자동으로 MCP 서버로 변환되어 **모든 Claude Code 세션에서 사용 가능**합니다.

## 사용 방법

### 1. 도구 파일 생성

`{이름}_tool.py` 또는 `{이름}_tools.py` 형식으로 파일을 생성합니다.

### 2. 도구 정의

#### 방법 1: `@tool` 데코레이터 사용 (권장)

```python
# my_tool.py
from tools.base import tool

@tool
def search_web(query: str) -> str:
    """
    Search the web for information.
    
    Args:
        query: The search query string
        
    Returns:
        Search results as text
    """
    # 실제 구현
    return f"Search results for: {query}"

@tool
def calculate(expression: str) -> str:
    """
    Calculate a mathematical expression.
    
    Args:
        expression: Math expression to evaluate (e.g., "2 + 3 * 4")
        
    Returns:
        Calculation result
    """
    try:
        result = eval(expression)
        return str(result)
    except Exception as e:
        return f"Error: {e}"
```

#### 방법 2: `BaseTool` 클래스 상속

```python
# advanced_tool.py
from tools.base import BaseTool

class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web for information"
    
    def run(self, query: str) -> str:
        # 실제 구현
        return f"Results for: {query}"

class DatabaseQueryTool(BaseTool):
    name = "query_database"
    description = "Execute SQL query on the database"
    
    def run(self, sql: str, database: str = "main") -> str:
        # 실제 구현
        return f"Query result from {database}"
```

### 3. 도구 내보내기

파일 끝에 `TOOLS` 리스트를 정의하여 내보낼 도구를 명시합니다:

```python
# 데코레이터 방식
TOOLS = [search_web, calculate]

# 또는 클래스 방식
TOOLS = [WebSearchTool(), DatabaseQueryTool()]
```

`TOOLS`가 정의되지 않으면 파일 내 모든 `@tool` 함수와 `BaseTool` 인스턴스가 자동 수집됩니다.

## 전체 예시

```python
# api_tools.py
"""
외부 API 연동 도구들
"""
import httpx
from tools.base import tool

@tool
def get_weather(city: str) -> str:
    """
    Get current weather for a city.
    
    Args:
        city: City name (e.g., "Seoul", "New York")
        
    Returns:
        Current weather information
    """
    # 실제로는 API 호출
    return f"Weather in {city}: Sunny, 22°C"

@tool
def translate_text(text: str, target_lang: str = "en") -> str:
    """
    Translate text to target language.
    
    Args:
        text: Text to translate
        target_lang: Target language code (default: "en")
        
    Returns:
        Translated text
    """
    # 실제로는 번역 API 호출
    return f"[{target_lang}] {text}"

@tool
async def fetch_url(url: str) -> str:
    """
    Fetch content from a URL.
    
    Args:
        url: URL to fetch
        
    Returns:
        Response content
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text[:1000]  # 처음 1000자만

# 내보낼 도구 목록
TOOLS = [get_weather, translate_text, fetch_url]
```

## 자동 로드

1. `main.py` 실행 시 `tools/` 폴더의 모든 `*_tool.py`, `*_tools.py` 파일 스캔
2. 각 파일의 도구들을 수집하여 MCP 서버로 래핑
3. 래핑된 MCP 서버가 **모든 세션에서 기본으로 사용 가능**

## 파일 구조

```
tools/
├── README.md           # 이 파일
├── base.py             # BaseTool 인터페이스, @tool 데코레이터
├── __init__.py         # 패키지 초기화
├── example_tool.py     # 예시 도구 (복사해서 사용)
└── my_custom_tool.py   # 사용자 정의 도구
```

## 주의사항

1. **파일명**: `*_tool.py` 또는 `*_tools.py` 형식만 자동 로드
2. **docstring 필수**: 도구의 `description`으로 사용됨
3. **타입 힌트 권장**: 파라미터 스키마 자동 생성에 활용
4. **비동기 지원**: `async def` 함수도 지원
5. **에러 처리**: 예외 발생 시 에러 메시지가 반환됨

## 디버깅

도구가 제대로 로드되었는지 확인:

```bash
# 서버 시작 시 로그 확인
python main.py

# 출력 예시:
# [MCP Loader] Loaded tools from: api_tools.py
# [MCP Loader]   - get_weather
# [MCP Loader]   - translate_text
# [MCP Loader]   - fetch_url
```
