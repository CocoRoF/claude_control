"""
Test script for Claude Control with large prompts and system prompts.
Tests the new direct Node.js execution (bypassing cmd.exe/PowerShell).
"""
import requests
import json
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api"

# Load system prompt from file
SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "self-manager.md"

def load_system_prompt() -> str:
    """Load the self-manager system prompt."""
    with open(SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
        return f.read()

def create_session(session_name: str, system_prompt: str) -> dict:
    """Create a new session with system prompt."""
    response = requests.post(
        f"{BASE_URL}/sessions",
        json={
            "session_name": session_name,
            "system_prompt": system_prompt
        },
        timeout=30
    )
    response.raise_for_status()
    return response.json()

def execute_prompt(session_id: str, prompt: str, timeout: int = 300) -> dict:
    """Execute a prompt in a session."""
    response = requests.post(
        f"{BASE_URL}/sessions/{session_id}/execute",
        json={"prompt": prompt},
        timeout=timeout
    )
    response.raise_for_status()
    return response.json()

def delete_session(session_id: str):
    """Delete a session."""
    response = requests.delete(
        f"{BASE_URL}/sessions/{session_id}",
        timeout=30
    )
    return response.status_code

def generate_large_prompt(min_chars: int = 8000) -> str:
    """Generate a large prompt (8000+ chars) with a realistic task."""

    task_header = """
# Task: Create a Comprehensive Python Utility Library

## Background
You are tasked with creating a utility library for a Python project. This library should contain various helper functions that are commonly needed across different modules. The code should be well-documented, type-hinted, and follow Python best practices.

## Requirements

### 1. File Operations Module (file_utils.py)
Create a module with the following functions:

- `read_json(path: str) -> dict`: Read and parse a JSON file
- `write_json(path: str, data: dict, indent: int = 2) -> None`: Write data to JSON file
- `read_lines(path: str) -> List[str]`: Read file and return list of lines
- `ensure_dir(path: str) -> Path`: Create directory if it doesn't exist
- `get_file_hash(path: str, algorithm: str = 'sha256') -> str`: Calculate file hash
- `copy_with_backup(src: str, dst: str) -> None`: Copy file, creating backup if dst exists

### 2. String Operations Module (string_utils.py)
Create a module with the following functions:

- `slugify(text: str) -> str`: Convert text to URL-friendly slug
- `truncate(text: str, max_length: int, suffix: str = '...') -> str`: Truncate text with suffix
- `camel_to_snake(text: str) -> str`: Convert camelCase to snake_case
- `snake_to_camel(text: str) -> str`: Convert snake_case to camelCase
- `extract_emails(text: str) -> List[str]`: Extract all email addresses from text
- `extract_urls(text: str) -> List[str]`: Extract all URLs from text
- `mask_sensitive(text: str, patterns: List[str]) -> str`: Mask sensitive data in text

### 3. Date/Time Operations Module (datetime_utils.py)
Create a module with the following functions:

- `now_utc() -> datetime`: Get current UTC time
- `now_local(tz: str = 'Asia/Seoul') -> datetime`: Get current local time
- `parse_datetime(text: str) -> datetime`: Parse datetime from various formats
- `format_relative(dt: datetime) -> str`: Format as "2 hours ago", "3 days ago", etc.
- `get_week_boundaries(dt: datetime) -> Tuple[datetime, datetime]`: Get start/end of week
- `get_month_boundaries(dt: datetime) -> Tuple[datetime, datetime]`: Get start/end of month
- `business_days_between(start: date, end: date) -> int`: Count business days

### 4. Validation Module (validators.py)
Create a module with the following functions:

- `is_valid_email(email: str) -> bool`: Validate email address
- `is_valid_url(url: str) -> bool`: Validate URL
- `is_valid_phone(phone: str, country: str = 'KR') -> bool`: Validate phone number
- `is_valid_credit_card(number: str) -> bool`: Validate credit card (Luhn algorithm)
- `is_valid_json(text: str) -> bool`: Check if text is valid JSON
- `is_valid_uuid(text: str) -> bool`: Check if text is valid UUID

### 5. Data Processing Module (data_utils.py)
Create a module with the following functions:

- `deep_merge(dict1: dict, dict2: dict) -> dict`: Deep merge two dictionaries
- `flatten_dict(d: dict, sep: str = '.') -> dict`: Flatten nested dict with key separator
- `unflatten_dict(d: dict, sep: str = '.') -> dict`: Unflatten dict
- `chunk_list(lst: List, size: int) -> List[List]`: Split list into chunks
- `remove_duplicates(lst: List, key: Callable = None) -> List`: Remove duplicates preserving order
- `safe_get(d: dict, path: str, default: Any = None) -> Any`: Safely get nested dict value

## Directory Structure
Create the following structure:
```
utils/
├── __init__.py
├── file_utils.py
├── string_utils.py
├── datetime_utils.py
├── validators.py
├── data_utils.py
└── tests/
    ├── __init__.py
    ├── test_file_utils.py
    ├── test_string_utils.py
    ├── test_datetime_utils.py
    ├── test_validators.py
    └── test_data_utils.py
```

## Quality Requirements
1. All functions must have docstrings with:
   - Brief description
   - Args with types
   - Returns with type
   - Raises (if applicable)
   - Example usage

2. All functions must have type hints

3. Each module must have at least 3 unit tests per function

4. Follow PEP 8 style guide

5. Handle edge cases gracefully (empty inputs, None values, etc.)

## Additional Context

Here is some example code showing the expected style:

```python
from typing import List, Optional, Any, Callable
from pathlib import Path
import json
import hashlib
import re
from datetime import datetime, date, timedelta
import pytz

def read_json(path: str) -> dict:
    \"\"\"
    Read and parse a JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed JSON data as dictionary.

    Raises:
        FileNotFoundError: If file doesn't exist.
        json.JSONDecodeError: If file contains invalid JSON.

    Example:
        >>> data = read_json('config.json')
        >>> print(data['version'])
    \"\"\"
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
```

Please implement all modules following this style. Start with creating the directory structure, then implement each module one by one, and finally create comprehensive tests.

## Notes on Implementation

1. For `slugify`, use `unicodedata` to handle non-ASCII characters
2. For `parse_datetime`, support ISO 8601, RFC 2822, and common formats
3. For `format_relative`, handle future dates as well ("in 2 hours")
4. For phone validation, at minimum support Korean (+82) and US (+1) formats
5. For `deep_merge`, handle cases where values are lists (concatenate) or dicts (recursive merge)

## Expected Timeline
- Directory structure and __init__.py files: M1
- file_utils.py implementation: M2
- string_utils.py implementation: M3
- datetime_utils.py implementation: M4
- validators.py implementation: M5
- data_utils.py implementation: M6
- All tests implementation: M7
- Final verification: M8

Begin working on this task now. Remember to follow the CPEV cycle for each milestone.
"""

    # Add more context to reach 8000+ chars
    additional_context = """

## Supplementary Technical Specifications

### Error Handling Strategy
All functions should follow a consistent error handling approach:
- Use specific exception types where possible
- Include helpful error messages with context
- Log errors appropriately before raising
- Consider adding retry logic for I/O operations

### Logging Guidelines
- Use Python's built-in logging module
- Create a logger per module: `logger = logging.getLogger(__name__)`
- Use appropriate log levels: DEBUG for detailed info, INFO for normal operations, WARNING for potential issues, ERROR for failures

### Testing Requirements
Each test file should:
- Use pytest as the testing framework
- Include fixtures for common setup
- Test both success cases and error cases
- Use parametrize for testing multiple inputs
- Include integration tests where applicable

### Performance Considerations
- For file operations, consider using generators for large files
- For string operations, compile regex patterns once and reuse
- For data operations, consider memory usage with large datasets
- Profile critical paths and optimize if needed

### Compatibility Requirements
- Python 3.8+ compatible
- Cross-platform (Windows, Linux, macOS)
- No external dependencies except for standard library and common packages (pytz, etc.)

This task requires careful attention to detail and thorough implementation. Please ensure all requirements are met before marking the task as complete.
"""

    full_prompt = task_header + additional_context

    # Ensure we have at least min_chars
    if len(full_prompt) < min_chars:
        padding = "\n\n" + "Additional context: " + "detailed implementation needed. " * 100
        full_prompt += padding[:min_chars - len(full_prompt)]

    return full_prompt

def main():
    print("=" * 60)
    print("Claude Control - Large Prompt Test")
    print("=" * 60)

    # Load system prompt
    print("\n1. Loading system prompt...")
    system_prompt = load_system_prompt()
    print(f"   System prompt length: {len(system_prompt)} chars")

    # Generate large prompt
    print("\n2. Generating large prompt...")
    large_prompt = generate_large_prompt(8000)
    print(f"   Prompt length: {len(large_prompt)} chars")

    # Create session
    print("\n3. Creating session with system prompt...")
    try:
        session = create_session("large-prompt-test", system_prompt)
        session_id = session["session_id"]
        print(f"   Session ID: {session_id}")
        print(f"   Status: {session['status']}")
    except Exception as e:
        print(f"   ERROR creating session: {e}")
        return

    # Execute large prompt
    print("\n4. Executing large prompt...")
    print("   (This may take a while...)")
    start_time = time.time()

    try:
        result = execute_prompt(session_id, large_prompt, timeout=300)
        elapsed = time.time() - start_time

        print(f"\n5. Results:")
        print(f"   Success: {result['success']}")
        print(f"   Duration: {result.get('duration_ms', 0)}ms (server) / {elapsed:.1f}s (total)")
        print(f"   Should Continue: {result.get('should_continue', False)}")

        if result['success']:
            output = result.get('output', '')
            print(f"   Output length: {len(output)} chars")
            print("\n   --- Output Preview (first 1000 chars) ---")
            print(output[:1000])
            if len(output) > 1000:
                print("   ... (truncated)")
            print("   --- End Preview ---")
        else:
            print(f"   Error: {result.get('error', 'Unknown error')}")

    except Exception as e:
        print(f"   ERROR executing prompt: {e}")

    # Clean up
    print("\n6. Cleaning up session...")
    try:
        delete_session(session_id)
        print("   Session deleted.")
    except Exception as e:
        print(f"   Warning: Could not delete session: {e}")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
