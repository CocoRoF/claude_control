"""
Example Tools

예시 도구 파일입니다. 이 파일을 참고하여 커스텀 도구를 만드세요.
파일명이 *_tool.py 또는 *_tools.py 형식이면 자동으로 로드됩니다.
"""
from tools.base import tool, BaseTool


# =============================================================================
# 방법 1: @tool 데코레이터 사용 (간단하고 권장)
# =============================================================================

@tool
def add_numbers(a: int, b: int) -> str:
    """
    Add two numbers together.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Sum of the two numbers
    """
    return str(a + b)


@tool
def multiply_numbers(a: int, b: int) -> str:
    """
    Multiply two numbers.
    
    Args:
        a: First number
        b: Second number
        
    Returns:
        Product of the two numbers
    """
    return str(a * b)


@tool
def reverse_string(text: str) -> str:
    """
    Reverse a string.
    
    Args:
        text: The string to reverse
        
    Returns:
        The reversed string
    """
    return text[::-1]


@tool
def count_words(text: str) -> str:
    """
    Count the number of words in a text.
    
    Args:
        text: The text to count words in
        
    Returns:
        Word count
    """
    words = text.split()
    return f"Word count: {len(words)}"


# =============================================================================
# 방법 2: BaseTool 클래스 상속 (복잡한 로직용)
# =============================================================================

class EchoTool(BaseTool):
    """Simple echo tool for testing."""
    
    name = "echo"
    description = "Echo back the input message"
    
    def run(self, message: str) -> str:
        return f"Echo: {message}"


class CalculatorTool(BaseTool):
    """Safe calculator that evaluates expressions."""
    
    name = "calculator"
    description = "Safely evaluate a mathematical expression"
    
    # 허용된 연산자와 함수
    ALLOWED_NAMES = {
        'abs': abs,
        'round': round,
        'min': min,
        'max': max,
        'sum': sum,
        'pow': pow,
    }
    
    def run(self, expression: str) -> str:
        """
        Evaluate a math expression safely.
        
        Args:
            expression: Mathematical expression (e.g., "2 + 3 * 4")
        """
        try:
            # 안전한 평가를 위해 허용된 이름만 사용
            result = eval(expression, {"__builtins__": {}}, self.ALLOWED_NAMES)
            return str(result)
        except Exception as e:
            return f"Error: {e}"


# =============================================================================
# 내보낼 도구 목록 (선택사항)
# 정의하지 않으면 파일 내 모든 도구가 자동 수집됨
# =============================================================================

TOOLS = [
    add_numbers,
    multiply_numbers,
    reverse_string,
    count_words,
    EchoTool(),
    CalculatorTool(),
]
