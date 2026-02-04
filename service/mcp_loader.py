"""
MCP Loader

mcp/ 폴더의 JSON 설정과 tools/ 폴더의 도구들을 자동으로 로드하여
모든 Claude Code 세션에서 사용할 수 있는 글로벌 MCP 설정을 생성합니다.

Usage:
    from service.mcp_loader import MCPLoader, get_global_mcp_config
    
    # 로더 초기화 및 로드
    loader = MCPLoader()
    loader.load_all()
    
    # 글로벌 MCP 설정 가져오기
    config = get_global_mcp_config()
"""
import asyncio
import importlib.util
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

from service.claude_manager.models import (
    MCPConfig,
    MCPServerStdio,
    MCPServerHTTP,
    MCPServerSSE,
    MCPServerConfig
)

logger = logging.getLogger(__name__)

# 글로벌 MCP 설정 저장소
_global_mcp_config: Optional[MCPConfig] = None

# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent


def get_global_mcp_config() -> Optional[MCPConfig]:
    """
    글로벌 MCP 설정 반환
    
    Returns:
        로드된 글로벌 MCP 설정 또는 None
    """
    return _global_mcp_config


def set_global_mcp_config(config: MCPConfig) -> None:
    """
    글로벌 MCP 설정 설정
    
    Args:
        config: 설정할 MCP 설정
    """
    global _global_mcp_config
    _global_mcp_config = config


class MCPLoader:
    """
    MCP 설정 및 도구 자동 로더
    
    mcp/ 폴더의 JSON 파일과 tools/ 폴더의 Python 도구를 로드하여
    통합된 MCP 설정을 생성합니다.
    """
    
    def __init__(
        self,
        mcp_dir: Optional[Path] = None,
        tools_dir: Optional[Path] = None
    ):
        """
        Args:
            mcp_dir: MCP JSON 설정 폴더 경로 (기본: 프로젝트루트/mcp)
            tools_dir: 도구 폴더 경로 (기본: 프로젝트루트/tools)
        """
        self.mcp_dir = mcp_dir or PROJECT_ROOT / "mcp"
        self.tools_dir = tools_dir or PROJECT_ROOT / "tools"
        self.servers: Dict[str, MCPServerConfig] = {}
        self.tools: List[Any] = []
        self._tools_mcp_process = None
    
    def load_all(self) -> MCPConfig:
        """
        모든 MCP 설정과 도구 로드
        
        Returns:
            통합된 MCP 설정
        """
        logger.info("=" * 60)
        logger.info("🔌 MCP Loader: Starting...")
        
        # 1. mcp/ 폴더의 JSON 설정 로드
        self._load_mcp_configs()
        
        # 2. tools/ 폴더의 도구 로드
        self._load_tools()
        
        # 3. 도구를 MCP 서버로 변환
        if self.tools:
            self._register_tools_as_mcp()
        
        # 4. 글로벌 설정 생성
        config = MCPConfig(servers=self.servers)
        set_global_mcp_config(config)
        
        logger.info(f"🔌 MCP Loader: Loaded {len(self.servers)} MCP servers")
        logger.info("=" * 60)
        
        return config
    
    def _load_mcp_configs(self) -> None:
        """mcp/ 폴더의 JSON 설정 파일 로드"""
        if not self.mcp_dir.exists():
            logger.info(f"📁 MCP config directory not found: {self.mcp_dir}")
            return
        
        json_files = list(self.mcp_dir.glob("*.json"))
        if not json_files:
            logger.info(f"📁 No JSON files in: {self.mcp_dir}")
            return
        
        logger.info(f"📁 Loading MCP configs from: {self.mcp_dir}")
        
        for json_file in json_files:
            try:
                server_name = json_file.stem  # 파일명 (확장자 제외)
                
                with open(json_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 환경 변수 확장
                config_data = self._expand_env_vars(config_data)
                
                # 서버 설정 생성
                server_config = self._create_server_config(config_data)
                
                if server_config:
                    self.servers[server_name] = server_config
                    desc = config_data.get('description', '')
                    logger.info(f"   ✅ {server_name}: {desc[:50]}..." if len(desc) > 50 else f"   ✅ {server_name}: {desc}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"   ⚠️ Invalid JSON in {json_file.name}: {e}")
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to load {json_file.name}: {e}")
    
    def _expand_env_vars(self, data: Any) -> Any:
        """
        설정 내 환경 변수 확장 (${VAR} 또는 ${VAR:-default} 형식)
        """
        if isinstance(data, str):
            # ${VAR} 또는 ${VAR:-default} 패턴 찾기
            pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
            
            def replace_env(match):
                var_name = match.group(1)
                default = match.group(2)
                value = os.environ.get(var_name)
                if value is None:
                    if default is not None:
                        return default
                    return match.group(0)  # 환경 변수 없으면 원본 유지
                return value
            
            return re.sub(pattern, replace_env, data)
        
        elif isinstance(data, dict):
            return {k: self._expand_env_vars(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            return [self._expand_env_vars(item) for item in data]
        
        return data
    
    def _create_server_config(self, data: Dict[str, Any]) -> Optional[MCPServerConfig]:
        """JSON 데이터에서 MCP 서버 설정 생성"""
        server_type = data.get('type', 'stdio')
        
        if server_type == 'stdio':
            command = data.get('command')
            if not command:
                return None
            return MCPServerStdio(
                command=command,
                args=data.get('args', []),
                env=data.get('env')
            )
        
        elif server_type == 'http':
            url = data.get('url')
            if not url:
                return None
            return MCPServerHTTP(
                url=url,
                headers=data.get('headers')
            )
        
        elif server_type == 'sse':
            url = data.get('url')
            if not url:
                return None
            return MCPServerSSE(
                url=url,
                headers=data.get('headers')
            )
        
        return None
    
    def _load_tools(self) -> None:
        """tools/ 폴더의 도구 파일 로드"""
        if not self.tools_dir.exists():
            logger.info(f"📁 Tools directory not found: {self.tools_dir}")
            return
        
        # *_tool.py 또는 *_tools.py 파일 찾기
        tool_files = list(self.tools_dir.glob("*_tool.py")) + list(self.tools_dir.glob("*_tools.py"))
        
        if not tool_files:
            logger.info(f"📁 No tool files in: {self.tools_dir}")
            return
        
        logger.info(f"📁 Loading tools from: {self.tools_dir}")
        
        # tools 패키지를 sys.path에 추가
        if str(PROJECT_ROOT) not in sys.path:
            sys.path.insert(0, str(PROJECT_ROOT))
        
        for tool_file in tool_files:
            try:
                tools = self._load_tools_from_file(tool_file)
                if tools:
                    self.tools.extend(tools)
                    logger.info(f"   ✅ {tool_file.name}: {len(tools)} tools")
                    for t in tools:
                        name = getattr(t, 'name', t.__name__ if hasattr(t, '__name__') else str(t))
                        logger.info(f"      - {name}")
                        
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to load {tool_file.name}: {e}")
    
    def _load_tools_from_file(self, file_path: Path) -> List[Any]:
        """파일에서 도구 로드"""
        # 모듈 동적 로드
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            return []
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[file_path.stem] = module
        spec.loader.exec_module(module)
        
        # TOOLS 리스트가 정의되어 있으면 사용
        if hasattr(module, 'TOOLS'):
            return list(module.TOOLS)
        
        # 아니면 자동 수집
        tools = []
        from tools.base import is_tool
        
        for name in dir(module):
            if name.startswith('_'):
                continue
            obj = getattr(module, name)
            if is_tool(obj):
                tools.append(obj)
        
        return tools
    
    def _register_tools_as_mcp(self) -> None:
        """로드된 도구를 내장 MCP 서버로 등록"""
        if not self.tools:
            return
        
        # 도구 MCP 서버 스크립트 경로 생성
        tools_server_script = self._create_tools_server_script()
        
        if tools_server_script:
            # Python 실행 경로
            python_exe = sys.executable
            
            self.servers["_builtin_tools"] = MCPServerStdio(
                command=python_exe,
                args=[str(tools_server_script)],
                env=None
            )
            
            logger.info(f"   🔧 Registered {len(self.tools)} tools as MCP server: _builtin_tools")
    
    def _create_tools_server_script(self) -> Optional[Path]:
        """
        도구를 MCP 서버로 실행하는 스크립트 생성
        """
        # 도구 파일 목록 수집
        tool_files = list(self.tools_dir.glob("*_tool.py")) + list(self.tools_dir.glob("*_tools.py"))
        
        if not tool_files:
            return None
        
        # 스크립트 생성
        script_path = self.tools_dir / "_mcp_server.py"
        
        imports = []
        tool_names = []
        
        for tool_file in tool_files:
            module_name = tool_file.stem
            
            # 해당 모듈의 도구 이름 수집
            spec = importlib.util.spec_from_file_location(module_name, tool_file)
            if spec is None or spec.loader is None:
                continue
            
            module = importlib.util.module_from_spec(spec)
            try:
                spec.loader.exec_module(module)
            except Exception:
                continue
            
            if hasattr(module, 'TOOLS'):
                imports.append(f"from tools.{module_name} import TOOLS as {module_name}_TOOLS")
                tool_names.append(f"*{module_name}_TOOLS")
        
        if not imports:
            return None
        
        script_content = f'''#!/usr/bin/env python3
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
{chr(10).join(imports)}

# MCP 서버 생성
mcp = FastMCP("builtin-tools")

# 모든 도구 수집
all_tools = []
{chr(10).join(f"all_tools.extend({name.replace('*', '')})" for name in tool_names)}

# 각 도구를 MCP에 등록
for tool_obj in all_tools:
    name = getattr(tool_obj, 'name', None)
    if not name and hasattr(tool_obj, '__name__'):
        name = tool_obj.__name__
    if not name:
        continue
    
    description = getattr(tool_obj, 'description', '') or getattr(tool_obj, '__doc__', '') or f"Tool: {{name}}"
    
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
'''
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        logger.info(f"   📝 Generated MCP server script: {script_path}")
        
        return script_path
    
    def get_server_count(self) -> int:
        """로드된 서버 수 반환"""
        return len(self.servers)
    
    def get_tool_count(self) -> int:
        """로드된 도구 수 반환"""
        return len(self.tools)
    
    def get_config(self) -> MCPConfig:
        """현재 MCP 설정 반환"""
        return MCPConfig(servers=self.servers)


def merge_mcp_configs(base: Optional[MCPConfig], override: Optional[MCPConfig]) -> Optional[MCPConfig]:
    """
    두 MCP 설정 병합
    
    override의 설정이 base보다 우선합니다.
    
    Args:
        base: 기본 설정 (글로벌)
        override: 우선 설정 (세션별)
        
    Returns:
        병합된 설정
    """
    if not base and not override:
        return None
    
    if not base:
        return override
    
    if not override:
        return base
    
    # 서버 병합 (override가 우선)
    merged_servers = {**base.servers, **override.servers}
    
    return MCPConfig(servers=merged_servers)
