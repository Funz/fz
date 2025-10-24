"""
Configuration system for fz package

Provides environment variable-based configuration for default settings.
"""

import os
from typing import Optional, Union
from enum import Enum


def _get_version() -> str:
    """Get package version from static version file"""
    try:
        from fz._version import __version__
        return __version__
    except ImportError:
        # Fallback to __init__.py if _version.py not found
        try:
            from fz import __version__
            return __version__
        except ImportError:
            return "unknown"


def _get_last_commit_date() -> str:
    """Get date of last git commit from static version file"""
    try:
        from fz._version import __commit_date__
        return __commit_date__
    except ImportError:
        return "unknown"


def _get_commit_hash() -> str:
    """Get git commit hash from static version file"""
    try:
        from fz._version import __commit_hash__
        return __commit_hash__
    except ImportError:
        return "unknown"


class Interpreter(Enum):
    """Available formula interpreters"""
    PYTHON = "python"
    R = "R"
    JAVASCRIPT = "javascript"
    AUTO = "auto"


class Config:
    """Global configuration for fz package"""

    def __init__(self):
        self._load_from_environment()

    def _load_from_environment(self):
        """Load configuration from environment variables"""

        # Logging configuration
        self.log_level = os.getenv('FZ_LOG_LEVEL', 'ERROR').upper()

        # Calculator retry configuration
        self.max_retries = int(os.getenv('FZ_MAX_RETRIES', '5'))

        # Default formula interpreter
        interpreter_str = os.getenv('FZ_INTERPRETER', 'python').lower()
        try:
            self.interpreter = Interpreter(interpreter_str)
        except ValueError:
            self.interpreter = Interpreter.PYTHON

        # Parallel execution configuration
        self.max_workers = self._parse_int_env('FZ_MAX_WORKERS', None)

        # SSH configuration
        self.ssh_auto_accept_hostkeys = self._parse_bool_env('FZ_SSH_AUTO_ACCEPT_HOSTKEYS', False)
        self.ssh_keepalive = self._parse_int_env('FZ_SSH_KEEPALIVE', 300)  # 5 minutes default

        # Shell path configuration (overrides system PATH for binary resolution)
        self.shell_path = os.getenv('FZ_SHELL_PATH', None)

    def _parse_int_env(self, key: str, default: Optional[int]) -> Optional[int]:
        """Parse integer environment variable"""
        value = os.getenv(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def _parse_bool_env(self, key: str, default: bool) -> bool:
        """Parse boolean environment variable"""
        value = os.getenv(key, '').lower()
        if value in ('true', '1', 'yes', 'on'):
            return True
        elif value in ('false', '0', 'no', 'off'):
            return False
        else:
            return default

    def reload(self):
        """Reload configuration from environment variables and sync with logging"""
        self._load_from_environment()

        # Sync with logging module
        from .logging import set_log_level
        set_log_level(self.log_level)

    def get_summary(self) -> dict:
        """Get a summary of current configuration"""
        # Get actual current log level from logging module
        from .logging import get_log_level_string
        current_log_level = get_log_level_string()

        return {
            'version': _get_version(),
            'commit_date': _get_last_commit_date(),
            'commit_hash': _get_commit_hash(),
            'log_level': current_log_level,
            'max_retries': self.max_retries,
            'interpreter': self.interpreter.value,
            'max_workers': self.max_workers,
            'ssh_auto_accept_hostkeys': self.ssh_auto_accept_hostkeys,
            'ssh_keepalive': self.ssh_keepalive,
            'shell_path': self.shell_path
        }


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance"""
    return config


def reload_config():
    """Reload configuration from environment variables"""
    config.reload()


# Global formula interpreter
_interpreter: Optional[str] = None


def set_interpreter(interpreter: str):
    """
    Set the global formula interpreter

    Args:
        interpreter: Interpreter name ("python", "R", "javascript", "auto")

    Raises:
        ValueError: If interpreter name is not valid
    """
    global _interpreter

    # Validate interpreter name
    valid_interpreters = [i.value for i in Interpreter]
    if interpreter.lower() not in valid_interpreters:
        raise ValueError(f"Invalid interpreter '{interpreter}'. Must be one of: {valid_interpreters}")

    _interpreter = interpreter.lower()


def get_interpreter() -> str:
    """
    Get the current global formula interpreter

    Returns:
        Interpreter name (defaults to FZ_INTERPRETER env var or "python")
    """
    # If interpreter was explicitly set, use that
    if _interpreter is not None:
        return _interpreter

    # Otherwise use the configured default from environment variable
    return config.interpreter.value


def print_config():
    """Print current configuration in a readable format"""
    print("=" * 60)
    print("FZ PACKAGE CONFIGURATION")
    print("=" * 60)

    summary = config.get_summary()

    print(f"Version: {summary['version']}")
    print(f"Commit: {summary['commit_hash']} ({summary['commit_date']})")

    print("\n🔧 LOGGING:")
    print(f"  FZ_LOG_LEVEL = {summary['log_level']}")

    print("\n🔄 CALCULATION:")
    print(f"  FZ_MAX_RETRIES = {summary['max_retries']}")
    print(f"  FZ_INTERPRETER = {summary['interpreter']}")
    print(f"  Current interpreter = {get_interpreter()}")

    print("\n⚡ PERFORMANCE:")
    print(f"  FZ_MAX_WORKERS = {summary['max_workers'] or 'auto'}")

    print("\n🌐 SSH:")
    print(f"  FZ_SSH_AUTO_ACCEPT_HOSTKEYS = {summary['ssh_auto_accept_hostkeys']}")
    print(f"  FZ_SSH_KEEPALIVE = {summary['ssh_keepalive']}s")

    print("\n🔍 SHELL PATH:")
    print(f"  FZ_SHELL_PATH = {summary['shell_path'] or '(not set, use system PATH)'}")

    print("\n" + "=" * 60)
    print("Set environment variables to customize these defaults")
    print("Example: export FZ_LOG_LEVEL=INFO FZ_MAX_RETRIES=3")
    print("=" * 60)