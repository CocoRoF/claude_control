"""
Tools Package.

Package for custom tool definition and auto-loading in Claude sessions.

This package provides:
- BaseTool: Abstract base class for complex tool implementations
- ToolWrapper: Function-to-tool wrapper created by @tool decorator
- @tool decorator: Simple way to convert functions into tools
- Utility functions: is_tool(), get_tool_info() for tool introspection

Example:
    from tools import tool

    @tool
    def search_database(query: str, limit: int = 10) -> str:
        '''Search the database for records'''
        results = db.search(query, limit=limit)
        return json.dumps(results)
"""
from tools.base import BaseTool, ToolWrapper, tool, is_tool, get_tool_info

__all__ = [
    'BaseTool',
    'ToolWrapper',
    'tool',
    'is_tool',
    'get_tool_info'
]
