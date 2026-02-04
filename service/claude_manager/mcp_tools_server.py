"""
LangChain Tools to MCP Server Wrapper

LangChain의 BaseTool을 MCP 서버로 래핑하여 Claude Code 세션에서 사용할 수 있게 합니다.

사용 방법:
    1. LangChain 도구 정의
    2. MCPToolsServer로 래핑
    3. 서버 실행 또는 Claude Control 세션에 연결

Example:
    ```python
    from langchain_core.tools import tool
    from service.claude_manager.mcp_tools_server import MCPToolsServer
    
    @tool
    def search_web(query: str) -> str:
        '''Search the web for information'''
        return f"Results for: {query}"
    
    @tool  
    def calculate(expression: str) -> str:
        '''Calculate a math expression'''
        return str(eval(expression))
    
    # MCP 서버로 실행
    server = MCPToolsServer(
        name="custom-tools",
        tools=[search_web, calculate]
    )
    server.run(transport="stdio")
    ```
"""
import asyncio
import json
import logging
from typing import List, Optional, Dict, Any, Callable, Union
from pathlib import Path

logger = logging.getLogger(__name__)

# MCP SDK가 설치되어 있는지 확인
try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Install with: pip install mcp")

# LangChain이 설치되어 있는지 확인
try:
    from langchain_core.tools import BaseTool, StructuredTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain not installed. Install with: pip install langchain-core")


class MCPToolsServer:
    """
    LangChain 도구를 MCP 서버로 래핑
    
    LangChain의 BaseTool 또는 @tool 데코레이터로 정의된 도구들을
    MCP 서버로 변환하여 Claude Code에서 사용할 수 있게 합니다.
    
    Attributes:
        name: MCP 서버 이름
        tools: LangChain 도구 리스트
        mcp: FastMCP 인스턴스
    """
    
    def __init__(
        self,
        name: str = "langchain-tools",
        tools: Optional[List[Any]] = None,
        description: Optional[str] = None
    ):
        """
        Args:
            name: MCP 서버 이름
            tools: LangChain BaseTool 리스트
            description: 서버 설명
        """
        if not MCP_AVAILABLE:
            raise ImportError(
                "MCP SDK가 설치되어 있지 않습니다. "
                "'pip install mcp' 명령으로 설치하세요."
            )
        
        self.name = name
        self._tools: List[Any] = []
        self._description = description or f"LangChain tools wrapped as MCP server: {name}"
        
        # FastMCP 인스턴스 생성
        self.mcp = FastMCP(name)
        
        # 도구 등록
        if tools:
            for tool in tools:
                self.add_tool(tool)
    
    def add_tool(self, tool: Any) -> None:
        """
        LangChain 도구 추가
        
        Args:
            tool: LangChain BaseTool 또는 @tool 데코레이터로 정의된 함수
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError(
                "LangChain이 설치되어 있지 않습니다. "
                "'pip install langchain-core' 명령으로 설치하세요."
            )
        
        self._tools.append(tool)
        self._register_mcp_tool(tool)
    
    def _register_mcp_tool(self, tool: Any) -> None:
        """
        LangChain 도구를 MCP 도구로 등록
        
        Args:
            tool: LangChain 도구
        """
        # 도구 이름과 설명 추출
        if hasattr(tool, 'name'):
            tool_name = tool.name
        elif hasattr(tool, '__name__'):
            tool_name = tool.__name__
        else:
            tool_name = str(tool)
        
        if hasattr(tool, 'description'):
            tool_description = tool.description
        elif hasattr(tool, '__doc__') and tool.__doc__:
            tool_description = tool.__doc__
        else:
            tool_description = f"LangChain tool: {tool_name}"
        
        # 도구 함수 생성
        async def mcp_tool_wrapper(**kwargs) -> str:
            """MCP 도구 래퍼"""
            try:
                # LangChain 도구 실행
                if hasattr(tool, 'ainvoke'):
                    result = await tool.ainvoke(kwargs)
                elif hasattr(tool, 'invoke'):
                    result = tool.invoke(kwargs)
                elif hasattr(tool, 'run'):
                    result = tool.run(**kwargs) if kwargs else tool.run()
                elif callable(tool):
                    result = tool(**kwargs)
                else:
                    result = str(tool)
                
                # 결과를 문자열로 변환
                if isinstance(result, str):
                    return result
                elif isinstance(result, (dict, list)):
                    return json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    return str(result)
                    
            except Exception as e:
                logger.error(f"Tool execution error ({tool_name}): {e}")
                return f"Error: {str(e)}"
        
        # 함수 메타데이터 설정
        mcp_tool_wrapper.__name__ = tool_name
        mcp_tool_wrapper.__doc__ = tool_description
        
        # MCP 도구로 등록
        self.mcp.tool()(mcp_tool_wrapper)
        logger.info(f"Registered MCP tool: {tool_name}")
    
    def add_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> None:
        """
        일반 Python 함수를 MCP 도구로 추가
        
        Args:
            func: Python 함수
            name: 도구 이름 (기본값: 함수 이름)
            description: 도구 설명 (기본값: docstring)
        """
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or f"Function: {tool_name}"
        
        # 함수 메타데이터 설정
        wrapper = func
        wrapper.__name__ = tool_name
        wrapper.__doc__ = tool_description
        
        # MCP 도구로 등록
        self.mcp.tool()(wrapper)
        logger.info(f"Registered MCP function: {tool_name}")
    
    def run(self, transport: str = "stdio", host: str = "0.0.0.0", port: int = 8080) -> None:
        """
        MCP 서버 실행
        
        Args:
            transport: 트랜스포트 타입 ("stdio" 또는 "http")
            host: HTTP 서버 호스트 (transport="http"일 때)
            port: HTTP 서버 포트 (transport="http"일 때)
        """
        logger.info(f"Starting MCP server '{self.name}' with {len(self._tools)} tools")
        logger.info(f"Transport: {transport}")
        
        if transport == "http":
            self.mcp.run(transport="http", host=host, port=port)
        else:
            self.mcp.run(transport="stdio")
    
    def get_tool_list(self) -> List[Dict[str, str]]:
        """
        등록된 도구 목록 반환
        
        Returns:
            도구 정보 리스트
        """
        tools = []
        for tool in self._tools:
            if hasattr(tool, 'name'):
                name = tool.name
            elif hasattr(tool, '__name__'):
                name = tool.__name__
            else:
                name = str(tool)
            
            if hasattr(tool, 'description'):
                desc = tool.description
            elif hasattr(tool, '__doc__'):
                desc = tool.__doc__ or ""
            else:
                desc = ""
            
            tools.append({"name": name, "description": desc})
        
        return tools


def create_mcp_server_script(
    tools_module_path: str,
    tool_names: List[str],
    server_name: str = "custom-tools",
    output_path: Optional[str] = None
) -> str:
    """
    LangChain 도구를 MCP 서버로 실행하는 스크립트 생성
    
    Args:
        tools_module_path: 도구가 정의된 모듈 경로
        tool_names: 사용할 도구 이름 리스트
        server_name: MCP 서버 이름
        output_path: 출력 스크립트 경로 (None이면 문자열 반환)
        
    Returns:
        생성된 스크립트 내용
    """
    script = f'''#!/usr/bin/env python3
"""
Auto-generated MCP Server Script
Server Name: {server_name}
Tools: {", ".join(tool_names)}
"""
import sys
sys.path.insert(0, ".")

from {tools_module_path} import {", ".join(tool_names)}
from service.claude_manager.mcp_tools_server import MCPToolsServer

if __name__ == "__main__":
    server = MCPToolsServer(
        name="{server_name}",
        tools=[{", ".join(tool_names)}]
    )
    server.run(transport="stdio")
'''
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(script)
        logger.info(f"MCP server script created: {output_path}")
    
    return script


# =============================================================================
# 편의 함수: 자주 사용되는 MCP 서버 설정 생성
# =============================================================================

def create_filesystem_mcp_config(paths: List[str]) -> Dict[str, Any]:
    """
    파일시스템 MCP 서버 설정 생성
    
    Args:
        paths: 접근 허용할 경로 리스트
        
    Returns:
        MCP 서버 설정 딕셔너리
    """
    return {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"] + paths
    }


def create_github_mcp_config() -> Dict[str, Any]:
    """
    GitHub MCP 서버 설정 생성
    
    Returns:
        MCP 서버 설정 딕셔너리
    """
    return {
        "type": "http",
        "url": "https://api.githubcopilot.com/mcp/"
    }


def create_postgres_mcp_config(dsn: str) -> Dict[str, Any]:
    """
    PostgreSQL MCP 서버 설정 생성
    
    Args:
        dsn: PostgreSQL 연결 문자열
        
    Returns:
        MCP 서버 설정 딕셔너리
    """
    return {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@bytebase/dbhub", "--dsn", dsn]
    }


def create_custom_mcp_config(
    server_type: str,
    command: Optional[str] = None,
    args: Optional[List[str]] = None,
    url: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    커스텀 MCP 서버 설정 생성
    
    Args:
        server_type: 서버 타입 ("stdio", "http", "sse")
        command: 실행 명령어 (stdio용)
        args: 명령어 인자 (stdio용)
        url: 서버 URL (http/sse용)
        env: 환경 변수
        headers: HTTP 헤더
        
    Returns:
        MCP 서버 설정 딕셔너리
    """
    config: Dict[str, Any] = {"type": server_type}
    
    if server_type == "stdio":
        if command:
            config["command"] = command
        if args:
            config["args"] = args
        if env:
            config["env"] = env
    else:  # http or sse
        if url:
            config["url"] = url
        if headers:
            config["headers"] = headers
    
    return config
