"""
Tools Base Module

도구 정의를 위한 기본 인터페이스와 데코레이터를 제공합니다.

Usage:
    # 방법 1: @tool 데코레이터 (간단한 도구)
    from tools.base import tool
    
    @tool
    def my_function(param: str) -> str:
        '''Tool description here'''
        return result
    
    # 방법 2: BaseTool 클래스 상속 (복잡한 도구)
    from tools.base import BaseTool
    
    class MyTool(BaseTool):
        name = "my_tool"
        description = "Tool description"
        
        def run(self, param: str) -> str:
            return result
"""
import functools
import inspect
import json
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Union, get_type_hints


class BaseTool(ABC):
    """
    도구 기본 클래스
    
    모든 커스텀 도구는 이 클래스를 상속받아 구현합니다.
    
    Attributes:
        name: 도구 이름 (고유해야 함)
        description: 도구 설명 (Claude가 도구 선택에 사용)
        parameters: 파라미터 스키마 (자동 생성 가능)
    
    Example:
        class MyTool(BaseTool):
            name = "my_tool"
            description = "Does something useful"
            
            def run(self, query: str, limit: int = 10) -> str:
                return f"Results for {query}, limit {limit}"
    """
    
    name: str = ""
    description: str = ""
    parameters: Optional[Dict[str, Any]] = None
    
    def __init__(self):
        if not self.name:
            self.name = self.__class__.__name__.lower().replace('tool', '')
        if not self.description:
            self.description = self.__doc__ or f"Tool: {self.name}"
        if self.parameters is None:
            self.parameters = self._generate_parameters_schema()
    
    def _generate_parameters_schema(self) -> Dict[str, Any]:
        """run 메서드의 시그니처에서 파라미터 스키마 생성"""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        try:
            sig = inspect.signature(self.run)
            hints = get_type_hints(self.run) if hasattr(self.run, '__annotations__') else {}
            
            for param_name, param in sig.parameters.items():
                if param_name == 'self':
                    continue
                
                # 타입 추론
                param_type = hints.get(param_name, str)
                json_type = self._python_type_to_json(param_type)
                
                schema["properties"][param_name] = {
                    "type": json_type,
                    "description": f"Parameter: {param_name}"
                }
                
                # 필수 파라미터 확인
                if param.default == inspect.Parameter.empty:
                    schema["required"].append(param_name)
                else:
                    schema["properties"][param_name]["default"] = param.default
                    
        except Exception:
            pass
        
        return schema
    
    @staticmethod
    def _python_type_to_json(python_type: type) -> str:
        """Python 타입을 JSON 스키마 타입으로 변환"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
            type(None): "null"
        }
        
        # Optional, Union 등 처리
        origin = getattr(python_type, '__origin__', None)
        if origin is Union:
            args = getattr(python_type, '__args__', ())
            for arg in args:
                if arg is not type(None):
                    return type_map.get(arg, "string")
        
        return type_map.get(python_type, "string")
    
    @abstractmethod
    def run(self, **kwargs) -> str:
        """
        도구 실행
        
        Args:
            **kwargs: 도구 파라미터
            
        Returns:
            실행 결과 문자열
        """
        pass
    
    async def arun(self, **kwargs) -> str:
        """
        비동기 도구 실행 (기본: 동기 실행)
        
        Override하여 비동기 구현 가능
        """
        return self.run(**kwargs)
    
    def __call__(self, **kwargs) -> str:
        """도구를 함수처럼 호출"""
        return self.run(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """도구 정보를 딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


class ToolWrapper:
    """
    @tool 데코레이터로 생성된 함수 래퍼
    
    일반 함수를 BaseTool과 호환되는 형태로 래핑합니다.
    """
    
    def __init__(self, func: Callable, name: Optional[str] = None, description: Optional[str] = None):
        self.func = func
        self.name = name or func.__name__
        self.description = description or func.__doc__ or f"Tool: {self.name}"
        self.parameters = self._generate_parameters_schema()
        self.is_async = inspect.iscoroutinefunction(func)
        
        # 함수 메타데이터 복사
        functools.update_wrapper(self, func)
    
    def _generate_parameters_schema(self) -> Dict[str, Any]:
        """함수 시그니처에서 파라미터 스키마 생성"""
        schema = {
            "type": "object",
            "properties": {},
            "required": []
        }
        
        try:
            sig = inspect.signature(self.func)
            hints = get_type_hints(self.func) if hasattr(self.func, '__annotations__') else {}
            
            for param_name, param in sig.parameters.items():
                param_type = hints.get(param_name, str)
                json_type = BaseTool._python_type_to_json(param_type)
                
                # docstring에서 파라미터 설명 추출 시도
                param_desc = f"Parameter: {param_name}"
                if self.func.__doc__:
                    # Args: 섹션에서 파라미터 설명 찾기
                    import re
                    match = re.search(rf'{param_name}:\s*(.+?)(?:\n|$)', self.func.__doc__)
                    if match:
                        param_desc = match.group(1).strip()
                
                schema["properties"][param_name] = {
                    "type": json_type,
                    "description": param_desc
                }
                
                if param.default == inspect.Parameter.empty:
                    schema["required"].append(param_name)
                else:
                    if param.default is not None:
                        schema["properties"][param_name]["default"] = param.default
                        
        except Exception:
            pass
        
        return schema
    
    def run(self, **kwargs) -> str:
        """동기 실행"""
        result = self.func(**kwargs)
        return self._format_result(result)
    
    async def arun(self, **kwargs) -> str:
        """비동기 실행"""
        if self.is_async:
            result = await self.func(**kwargs)
        else:
            result = self.func(**kwargs)
        return self._format_result(result)
    
    def _format_result(self, result: Any) -> str:
        """결과를 문자열로 변환"""
        if isinstance(result, str):
            return result
        elif isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return str(result)
    
    def __call__(self, *args, **kwargs):
        """원래 함수처럼 호출 가능"""
        return self.func(*args, **kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """도구 정보를 딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


def tool(
    func: Optional[Callable] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None
) -> Union[ToolWrapper, Callable[[Callable], ToolWrapper]]:
    """
    함수를 도구로 변환하는 데코레이터
    
    Args:
        func: 변환할 함수
        name: 도구 이름 (기본: 함수 이름)
        description: 도구 설명 (기본: docstring)
    
    Usage:
        @tool
        def my_func(param: str) -> str:
            '''Description here'''
            return result
        
        @tool(name="custom_name", description="Custom description")
        def another_func(param: str) -> str:
            return result
    """
    def decorator(f: Callable) -> ToolWrapper:
        return ToolWrapper(f, name=name, description=description)
    
    if func is not None:
        # @tool 형식으로 사용
        return decorator(func)
    else:
        # @tool(...) 형식으로 사용
        return decorator


def is_tool(obj: Any) -> bool:
    """객체가 도구인지 확인"""
    return isinstance(obj, (BaseTool, ToolWrapper))


def get_tool_info(obj: Any) -> Optional[Dict[str, Any]]:
    """도구 정보 추출"""
    if isinstance(obj, (BaseTool, ToolWrapper)):
        return obj.to_dict()
    return None
