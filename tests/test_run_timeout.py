#!/usr/bin/env python3
"""
Tests for run timeout resolution: config default, per-model override, and
explicit argument precedence.
"""

import pytest

from fz.config import Config, get_config
from fz.runners import resolve_timeout, run_local_calculation


class TestResolveTimeout:
    """Unit tests for resolve_timeout() precedence rules."""

    def test_default_is_config_run_timeout(self):
        assert resolve_timeout({}) == get_config().run_timeout

    def test_default_run_timeout_is_one_hour(self, monkeypatch):
        """FZ_RUN_TIMEOUT's built-in default is 3600s (1h), not the old 600s (10min)."""
        monkeypatch.delenv("FZ_RUN_TIMEOUT", raising=False)
        assert Config().run_timeout == 3600

    def test_explicit_argument_wins_over_model(self):
        model = {"timeout": 1800}
        assert resolve_timeout(model, timeout=60) == 60

    def test_model_timeout_overrides_config_default(self):
        model = {"timeout": 120}
        assert resolve_timeout(model) == 120

    def test_model_timeout_none_disables_timeout(self):
        model = {"timeout": None}
        assert resolve_timeout(model) is None

    def test_model_timeout_zero_disables_timeout(self):
        model = {"timeout": 0}
        assert resolve_timeout(model) is None

    def test_explicit_argument_wins_even_when_model_disables(self):
        model = {"timeout": None}
        assert resolve_timeout(model, timeout=30) == 30

    def test_model_without_timeout_key_uses_config_default(self):
        model = {"varprefix": "$"}
        assert resolve_timeout(model) == get_config().run_timeout

    def test_non_dict_model_uses_config_default(self):
        assert resolve_timeout(None) == get_config().run_timeout


class TestRunLocalCalculationTimeoutBehavior:
    """End-to-end: a small model timeout actually aborts a long-running command."""

    @pytest.fixture
    def slow_input_dir(self, tmp_path):
        work = tmp_path / "case_work"
        work.mkdir()
        (work / "input.txt").write_text("value = 42\n")
        (work / ".fz_hash").write_text("abc123 input.txt\n")
        script = work / "slow.sh"
        script.write_text("#!/bin/bash\nsleep 5\n")
        script.chmod(0o755)
        return work

    def test_model_timeout_triggers_timeout_status(self, slow_input_dir):
        model = {"output": {"result": "echo 42"}, "timeout": 1}
        result = run_local_calculation(
            working_dir=slow_input_dir,
            command=str(slow_input_dir / "slow.sh"),
            model=model,
            timeout=None,  # force resolution through the model's own timeout
            original_cwd=str(slow_input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "timeout"

    def test_explicit_timeout_argument_overrides_model_timeout(self, slow_input_dir):
        """A generous explicit timeout beats a very small model timeout."""
        model = {"output": {"result": "echo 42"}, "timeout": 1}
        result = run_local_calculation(
            working_dir=slow_input_dir,
            command="echo hi",
            model=model,
            timeout=30,
            original_cwd=str(slow_input_dir),
            input_files_list=["input.txt"],
        )
        assert result["status"] == "done"
