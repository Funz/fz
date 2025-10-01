"""
Configuration system for fz package

Provides environment variable-based configuration for default settings.
"""

import os
from typing import Optional, Union
from enum import Enum


class DefaultFormulaEngine(Enum):
    """Available formula evaluation engines"""
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

        # Default formula evaluation engine
        formula_engine_str = os.getenv('FZ_DEFAULT_FORMULA_ENGINE', 'python').lower()
        try:
            self.default_formula_engine = DefaultFormulaEngine(formula_engine_str)
        except ValueError:
            self.default_formula_engine = DefaultFormulaEngine.PYTHON

        # Parallel execution configuration
        self.max_workers = self._parse_int_env('FZ_MAX_WORKERS', None)

        # SSH configuration
        self.ssh_auto_accept_hostkeys = self._parse_bool_env('FZ_SSH_AUTO_ACCEPT_HOSTKEYS', False)
        self.ssh_keepalive = self._parse_int_env('FZ_SSH_KEEPALIVE', 300)  # 5 minutes default

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
        """Reload configuration from environment variables"""
        self._load_from_environment()

    def get_summary(self) -> dict:
        """Get a summary of current configuration"""
        return {
            'log_level': self.log_level,
            'max_retries': self.max_retries,
            'default_formula_engine': self.default_formula_engine.value,
            'max_workers': self.max_workers,
            'ssh_auto_accept_hostkeys': self.ssh_auto_accept_hostkeys,
            'ssh_keepalive': self.ssh_keepalive
        }


# Global configuration instance
config = Config()


def get_config() -> Config:
    """Get the global configuration instance"""
    return config


def reload_config():
    """Reload configuration from environment variables"""
    config.reload()


def print_config():
    """Print current configuration in a readable format"""
    print("=" * 60)
    print("FZ PACKAGE CONFIGURATION")
    print("=" * 60)

    summary = config.get_summary()

    print("🔧 LOGGING:")
    print(f"  FZ_LOG_LEVEL = {summary['log_level']}")

    print("\n🔄 CALCULATION:")
    print(f"  FZ_MAX_RETRIES = {summary['max_retries']}")
    print(f"  FZ_DEFAULT_FORMULA_ENGINE = {summary['default_formula_engine']}")

    print("\n⚡ PERFORMANCE:")
    print(f"  FZ_MAX_WORKERS = {summary['max_workers'] or 'auto'}")

    print("\n🌐 SSH:")
    print(f"  FZ_SSH_AUTO_ACCEPT_HOSTKEYS = {summary['ssh_auto_accept_hostkeys']}")
    print(f"  FZ_SSH_KEEPALIVE = {summary['ssh_keepalive']}s")

    print("\n" + "=" * 60)
    print("Set environment variables to customize these defaults")
    print("Example: export FZ_LOG_LEVEL=INFO FZ_MAX_RETRIES=3")
    print("=" * 60)