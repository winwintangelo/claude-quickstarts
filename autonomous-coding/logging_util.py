"""
Logging Utilities
=================

Provides dual logging to both stdout and a log file for easier debugging.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, TextIO


class DualLogger:
    """
    Logger that writes to both stdout and a log file simultaneously.
    """
    
    def __init__(self, log_file: Optional[Path] = None):
        """
        Initialize the dual logger.
        
        Args:
            log_file: Path to the log file. If None, only writes to stdout.
        """
        self._log_file: Optional[TextIO] = None
        self._log_path: Optional[Path] = None
        
        if log_file:
            self.set_log_file(log_file)
    
    def set_log_file(self, log_file: Path) -> None:
        """Set or change the log file path."""
        # Close existing log file if open
        if self._log_file:
            self._log_file.close()
        
        self._log_path = log_file
        # Create parent directories if needed
        log_file.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode
        self._log_file = open(log_file, "a", encoding="utf-8")
        
        # Write session start marker
        self._log_file.write(f"\n{'='*70}\n")
        self._log_file.write(f"Session started: {datetime.now().isoformat()}\n")
        self._log_file.write(f"{'='*70}\n\n")
        self._log_file.flush()
    
    def write(self, message: str, end: str = "\n", flush: bool = False) -> None:
        """
        Write a message to both stdout and the log file.
        
        Args:
            message: The message to write
            end: String appended after the message (default: newline)
            flush: Whether to flush the output immediately
        """
        # Write to stdout
        print(message, end=end, flush=flush)
        
        # Write to log file if available
        if self._log_file:
            self._log_file.write(message + end)
            if flush:
                self._log_file.flush()
    
    def log(self, message: str, timestamp: bool = False) -> None:
        """
        Log a message with optional timestamp.
        
        Args:
            message: The message to log
            timestamp: Whether to prepend a timestamp
        """
        if timestamp:
            ts = datetime.now().strftime("%H:%M:%S")
            message = f"[{ts}] {message}"
        self.write(message)
    
    def flush(self) -> None:
        """Flush both stdout and the log file."""
        sys.stdout.flush()
        if self._log_file:
            self._log_file.flush()
    
    def close(self) -> None:
        """Close the log file."""
        if self._log_file:
            self._log_file.write(f"\nSession ended: {datetime.now().isoformat()}\n")
            self._log_file.close()
            self._log_file = None
    
    @property
    def log_path(self) -> Optional[Path]:
        """Get the current log file path."""
        return self._log_path
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Global logger instance
_logger: Optional[DualLogger] = None


def get_logger() -> DualLogger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = DualLogger()
    return _logger


def init_logger(project_dir: Path) -> DualLogger:
    """
    Initialize the global logger with a log file in the project directory.
    
    Args:
        project_dir: Project directory where logs will be stored
        
    Returns:
        The initialized logger
    """
    global _logger
    
    # Create log file path with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = project_dir / "logs" / f"agent_session_{timestamp}.log"
    
    _logger = DualLogger(log_file)
    return _logger


def log(message: str, end: str = "\n", flush: bool = False) -> None:
    """
    Convenience function to log a message.
    
    Args:
        message: The message to log
        end: String appended after the message
        flush: Whether to flush immediately
    """
    get_logger().write(message, end=end, flush=flush)


def log_tool_call(tool_name: str, arguments: dict, result: str, duration_ms: float, is_error: bool = False) -> None:
    """
    Log a tool call with formatted output.
    
    Args:
        tool_name: Name of the tool
        arguments: Tool arguments
        result: Tool result (truncated for display)
        duration_ms: Execution duration in milliseconds
        is_error: Whether the result is an error
    """
    logger = get_logger()
    
    logger.write(f"\n[Tool: {tool_name}]", flush=True)
    
    if arguments:
        args_str = str(arguments)
        if len(args_str) > 200:
            logger.write(f"   Input: {args_str[:200]}...", flush=True)
        else:
            logger.write(f"   Input: {args_str}", flush=True)
    
    if is_error:
        logger.write(f"   [Error] {result[:200]} ({duration_ms:.0f}ms)", flush=True)
    else:
        logger.write(f"   [Done] ({duration_ms:.0f}ms)", flush=True)


def close_logger() -> None:
    """Close the global logger."""
    global _logger
    if _logger:
        _logger.close()
        _logger = None

