#!/usr/bin/env python3
"""
Auto-generated MCP Server for tools/
This file is auto-generated. Do not edit manually.
"""
import sys
from pathlib import Path

# 프로젝트 루트를 path에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("Error: MCP SDK not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

# 도구 임포트
from tools.example_tool import TOOLS as example_tool_TOOLS

# MCP 서버 생성
mcp = FastMCP("builtin-tools")

# 모든 도구 수집
all_tools = []
all_tools.extend(example_tool_TOOLS)

# 각 도구를 MCP에 등록
for tool_obj in all_tools:
    name = getattr(tool_obj, 'name', None)
    if not name and hasattr(tool_obj, '__name__'):
        name = tool_obj.__name__
    if not name:
        continue
    
    description = getattr(tool_obj, 'description', '') or getattr(tool_obj, '__doc__', '') or f"Tool: {name}"
    
    # run 또는 arun 메서드 찾기
    if hasattr(tool_obj, 'arun'):
        func = tool_obj.arun
    elif hasattr(tool_obj, 'run'):
        func = tool_obj.run
    elif callable(tool_obj):
        func = tool_obj
    else:
        continue
    
    # MCP 도구로 등록
    wrapper = mcp.tool()(func)
    wrapper.__name__ = name
    wrapper.__doc__ = description

if __name__ == "__main__":
    mcp.run(transport="stdio")
