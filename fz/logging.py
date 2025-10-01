"""
Global logging system for fz package

Provides configurable logging levels: ERROR, WARNING, INFO, DEBUG
Uses environment variable FZ_LOG_LEVEL or function calls to set verbosity.
"""

import os
from enum import Enum
from typing import Optional


class LogLevel(Enum):
    """Logging levels in order of increasing verbosity"""
    QUIET = -1
    ERROR = 0
    WARNING = 1
    INFO = 2
    DEBUG = 3


# Global logging configuration
_current_log_level = LogLevel.ERROR


def set_log_level(level: LogLevel) -> None:
    """Set the global logging level"""
    global _current_log_level
    _current_log_level = level


def get_log_level() -> LogLevel:
    """Get the current logging level"""
    return _current_log_level


def set_log_level_from_string(level_str: str) -> None:
    """Set logging level from string (case-insensitive)"""
    level_map = {
        'QUIET': LogLevel.QUIET,
        'ERROR': LogLevel.ERROR,
        'WARNING': LogLevel.WARNING,
        'INFO': LogLevel.INFO,
        'DEBUG': LogLevel.DEBUG
    }

    level_str = level_str.upper()
    if level_str in level_map:
        set_log_level(level_map[level_str])
    else:
        raise ValueError(f"Invalid log level: {level_str}. Valid levels: {list(level_map.keys())}")


def init_logging_from_env() -> None:
    """Initialize logging level from FZ_LOG_LEVEL environment variable"""
    from .config import get_config
    config = get_config()
    try:
        set_log_level_from_string(config.log_level)
    except ValueError:
        # Default to ERROR if invalid level provided
        set_log_level(LogLevel.ERROR)


def should_log(level: LogLevel) -> bool:
    """Check if a message at the given level should be logged"""
    return level.value <= _current_log_level.value


def log_error(message: str) -> None:
    """Log an error message (always shown unless completely disabled)"""
    if should_log(LogLevel.ERROR):
        print(message)


def log_warning(message: str) -> None:
    """Log a warning message"""
    if should_log(LogLevel.WARNING):
        print("  " + message)


def log_info(message: str) -> None:
    """Log an info message"""
    if should_log(LogLevel.INFO):
        print("    " + message)


def log_debug(message: str) -> None:
    """Log a debug message"""
    if should_log(LogLevel.DEBUG):
        print("      " + message)


def log_progress(message: str) -> None:
    """Log a progress message (shows at all levels except QUIET)"""
    if _current_log_level != LogLevel.QUIET:
        print(message)


# Initialize from environment on module import
init_logging_from_env()