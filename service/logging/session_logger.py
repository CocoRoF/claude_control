"""
Session Logger

Per-session logging system for Claude Control.
Each session gets its own log file in the logs/ directory.
"""
import json
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List
from threading import Lock

from service.utils.utils import now_kst, format_kst

logger = logging.getLogger(__name__)


class LogLevel(str, Enum):
    """Log levels for session logging."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    COMMAND = "COMMAND"
    RESPONSE = "RESPONSE"


class LogEntry:
    """Represents a single log entry."""

    def __init__(
        self,
        level: LogLevel,
        message: str,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.level = level
        self.message = message
        self.timestamp = timestamp or now_kst()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert log entry to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "message": self.message,
            "metadata": self.metadata
        }

    def to_line(self) -> str:
        """Convert log entry to formatted log line."""
        ts = format_kst(self.timestamp)
        meta_str = ""
        if self.metadata:
            meta_str = f" | {json.dumps(self.metadata, ensure_ascii=False)}"
        return f"[{ts}] [{self.level.value:8}] {self.message}{meta_str}\n"


class SessionLogger:
    """
    Per-session logger.

    Each session has its own log file stored in logs/ directory.
    Log files are named: {session_id}.log

    Features:
    - Timestamps for each log entry
    - Command logging (user commands to Claude)
    - Response logging (Claude's responses)
    - Error logging
    - JSON metadata support
    """

    def __init__(
        self,
        session_id: str,
        session_name: Optional[str] = None,
        logs_dir: Optional[str] = None
    ):
        self.session_id = session_id
        self.session_name = session_name or session_id

        # Determine logs directory
        if logs_dir:
            self._logs_dir = Path(logs_dir)
        else:
            # Default to logs/ directory in project root
            self._logs_dir = Path(__file__).parent.parent.parent / "logs"

        # Ensure logs directory exists
        self._logs_dir.mkdir(parents=True, exist_ok=True)

        # Log file path
        self._log_file = self._logs_dir / f"{session_id}.log"

        # Thread safety
        self._lock = Lock()

        # In-memory log cache (for quick retrieval)
        self._log_cache: List[LogEntry] = []
        self._max_cache_size = 1000  # Keep last 1000 entries in memory

        # Write session start entry
        self._write_header()

    def _write_header(self):
        """Write session header to log file."""
        header = (
            f"{'=' * 80}\n"
            f"Session ID: {self.session_id}\n"
            f"Session Name: {self.session_name}\n"
            f"Started: {format_kst(now_kst())}\n"
            f"{'=' * 80}\n\n"
        )
        with self._lock:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(header)

    def _write_entry(self, entry: LogEntry):
        """Write a log entry to file and cache."""
        with self._lock:
            # Write to file
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(entry.to_line())

            # Add to cache
            self._log_cache.append(entry)

            # Trim cache if too large
            if len(self._log_cache) > self._max_cache_size:
                self._log_cache = self._log_cache[-self._max_cache_size:]

    def log(
        self,
        level: LogLevel,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Write a log entry.

        Args:
            level: Log level
            message: Log message
            metadata: Optional metadata dictionary
        """
        entry = LogEntry(level=level, message=message, metadata=metadata)
        self._write_entry(entry)

    def debug(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a debug message."""
        self.log(LogLevel.DEBUG, message, metadata)

    def info(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an info message."""
        self.log(LogLevel.INFO, message, metadata)

    def warning(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log a warning message."""
        self.log(LogLevel.WARNING, message, metadata)

    def error(self, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Log an error message."""
        self.log(LogLevel.ERROR, message, metadata)

    def log_command(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        system_prompt: Optional[str] = None,
        max_turns: Optional[int] = None
    ):
        """
        Log a command sent to Claude.

        Args:
            prompt: The prompt/command sent to Claude
            timeout: Command timeout
            system_prompt: Custom system prompt
            max_turns: Maximum turns for execution
        """
        metadata = {
            "type": "command",
            "timeout": timeout,
            "system_prompt": system_prompt[:100] + "..." if system_prompt and len(system_prompt) > 100 else system_prompt,
            "max_turns": max_turns
        }
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        self.log(LogLevel.COMMAND, f"PROMPT: {prompt[:500]}{'...' if len(prompt) > 500 else ''}", metadata)

    def log_response(
        self,
        success: bool,
        output: Optional[str] = None,
        error: Optional[str] = None,
        duration_ms: Optional[int] = None,
        cost_usd: Optional[float] = None
    ):
        """
        Log a response from Claude.

        Args:
            success: Whether execution was successful
            output: Claude's output
            error: Error message if failed
            duration_ms: Execution duration in milliseconds
            cost_usd: API cost in USD
        """
        metadata = {
            "type": "response",
            "success": success,
            "duration_ms": duration_ms,
            "cost_usd": cost_usd
        }
        # Remove None values
        metadata = {k: v for k, v in metadata.items() if v is not None}

        if success:
            message = f"SUCCESS: {output[:500]}{'...' if output and len(output) > 500 else ''}"
        else:
            message = f"FAILED: {error}"

        self.log(LogLevel.RESPONSE, message, metadata)

    def log_session_event(self, event: str, details: Optional[Dict[str, Any]] = None):
        """
        Log a session lifecycle event.

        Args:
            event: Event type (e.g., "created", "stopped", "error")
            details: Event details
        """
        metadata = {"event": event}
        if details:
            metadata.update(details)
        self.log(LogLevel.INFO, f"SESSION EVENT: {event}", metadata)

    def get_logs(
        self,
        limit: int = 100,
        level: Optional[LogLevel] = None,
        from_cache: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get log entries.

        Args:
            limit: Maximum number of entries to return
            level: Filter by log level
            from_cache: If True, read from cache; if False, read from file

        Returns:
            List of log entries as dictionaries
        """
        if from_cache:
            with self._lock:
                entries = self._log_cache[-limit:]
                if level:
                    entries = [e for e in entries if e.level == level]
                return [e.to_dict() for e in entries]
        else:
            # Read from file
            return self._read_logs_from_file(limit, level)

    def _read_logs_from_file(
        self,
        limit: int = 100,
        level: Optional[LogLevel] = None
    ) -> List[Dict[str, Any]]:
        """Read log entries from file."""
        entries = []
        try:
            with self._lock:
                if not self._log_file.exists():
                    return []

                with open(self._log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for line in lines[-limit * 2:]:  # Read more lines to account for filtering
                    if line.startswith('[') and '] [' in line:
                        try:
                            # Parse log line
                            # Format: [timestamp] [LEVEL   ] message | metadata
                            parts = line.split('] [', 1)
                            if len(parts) >= 2:
                                ts_str = parts[0][1:]
                                rest = parts[1]
                                level_end = rest.find(']')
                                if level_end > 0:
                                    log_level = rest[:level_end].strip()
                                    message_part = rest[level_end + 2:].strip()

                                    # Check level filter
                                    if level and log_level != level.value:
                                        continue

                                    # Parse metadata if present
                                    metadata = {}
                                    if ' | ' in message_part:
                                        msg, meta_str = message_part.rsplit(' | ', 1)
                                        try:
                                            metadata = json.loads(meta_str)
                                        except json.JSONDecodeError:
                                            pass
                                    else:
                                        msg = message_part.rstrip('\n')

                                    entries.append({
                                        "timestamp": ts_str,
                                        "level": log_level,
                                        "message": msg,
                                        "metadata": metadata
                                    })
                        except Exception:
                            continue

                return entries[-limit:]
        except Exception as e:
            logger.error(f"Failed to read logs from file: {e}")
            return []

    def get_log_file_path(self) -> str:
        """Get the path to this session's log file."""
        return str(self._log_file)

    def close(self):
        """Close the logger and write session end marker."""
        footer = (
            f"\n{'=' * 80}\n"
            f"Session Ended: {format_kst(now_kst())}\n"
            f"{'=' * 80}\n"
        )
        with self._lock:
            with open(self._log_file, 'a', encoding='utf-8') as f:
                f.write(footer)


# Session logger registry
_session_loggers: Dict[str, SessionLogger] = {}
_registry_lock = Lock()


def get_session_logger(
    session_id: str,
    session_name: Optional[str] = None,
    create_if_missing: bool = True
) -> Optional[SessionLogger]:
    """
    Get or create a session logger.

    Args:
        session_id: Session ID
        session_name: Session name (used only when creating)
        create_if_missing: If True, create logger if it doesn't exist

    Returns:
        SessionLogger instance or None
    """
    with _registry_lock:
        if session_id in _session_loggers:
            return _session_loggers[session_id]

        if create_if_missing:
            logger_instance = SessionLogger(session_id, session_name)
            _session_loggers[session_id] = logger_instance
            return logger_instance

        return None


def remove_session_logger(session_id: str, delete_file: bool = False):
    """
    Remove session logger from memory.

    By default, log files are preserved for historical reference.
    Only removes from memory registry, not from disk.

    Args:
        session_id: Session ID
        delete_file: If True, also delete the log file (default: False)
    """
    with _registry_lock:
        if session_id in _session_loggers:
            session_logger = _session_loggers[session_id]
            session_logger.close()
            
            # Optionally delete the file (default: keep it)
            if delete_file:
                try:
                    log_path = Path(session_logger.get_log_file_path())
                    if log_path.exists():
                        log_path.unlink()
                        logger.info(f"Deleted log file: {log_path}")
                except Exception as e:
                    logger.warning(f"Failed to delete log file: {e}")
            
            del _session_loggers[session_id]


def list_session_logs() -> List[Dict[str, Any]]:
    """
    List all available session log files.

    Returns:
        List of log file info dictionaries
    """
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    if not logs_dir.exists():
        return []

    log_files = []
    for log_file in logs_dir.glob("*.log"):
        stat = log_file.stat()
        log_files.append({
            "session_id": log_file.stem,
            "file_name": log_file.name,
            "file_path": str(log_file),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })

    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x["modified_at"], reverse=True)
    return log_files


def read_logs_from_file(
    session_id: str,
    limit: int = 100,
    level: Optional[LogLevel] = None
) -> List[Dict[str, Any]]:
    """
    Read log entries directly from a log file.

    This function reads logs from disk without requiring an active session logger.
    Useful for reading historical logs from deleted sessions.

    Args:
        session_id: Session ID (used to find the log file)
        limit: Maximum number of entries to return
        level: Filter by log level

    Returns:
        List of log entries as dictionaries
    """
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    log_file = logs_dir / f"{session_id}.log"

    if not log_file.exists():
        return []

    entries = []
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            if line.startswith('[') and '] [' in line:
                try:
                    # Parse log line
                    # Format: [timestamp] [LEVEL   ] message | metadata
                    parts = line.split('] [', 1)
                    if len(parts) >= 2:
                        ts_str = parts[0][1:]
                        rest = parts[1]
                        level_end = rest.find(']')
                        if level_end > 0:
                            log_level = rest[:level_end].strip()

                            # Check level filter
                            if level and log_level != level.value:
                                continue

                            message_part = rest[level_end + 2:].strip()

                            # Parse metadata if present
                            metadata = {}
                            if ' | ' in message_part:
                                msg, meta_str = message_part.rsplit(' | ', 1)
                                try:
                                    metadata = json.loads(meta_str)
                                except json.JSONDecodeError:
                                    pass
                            else:
                                msg = message_part.rstrip('\n')

                            entries.append({
                                "timestamp": ts_str,
                                "level": log_level,
                                "message": msg,
                                "metadata": metadata
                            })
                except Exception:
                    continue

        return entries[-limit:]
    except Exception as e:
        logger.error(f"Failed to read logs from file {log_file}: {e}")
        return []


def get_log_file_path(session_id: str) -> Optional[str]:
    """
    Get the log file path for a session.

    Args:
        session_id: Session ID

    Returns:
        Path to log file if exists, None otherwise
    """
    logs_dir = Path(__file__).parent.parent.parent / "logs"
    log_file = logs_dir / f"{session_id}.log"
    return str(log_file) if log_file.exists() else None
