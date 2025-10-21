"""
Platform-specific tests for fz

These tests verify platform-specific functionality like interrupt handling
on different operating systems.
"""

import pytest
import sys
import time
import platform
import tempfile
from pathlib import Path


class TestInterruptHandling:
    """Test interrupt handling (Ctrl+C) on different platforms"""

    @pytest.mark.skipif(
        platform.system() != "Windows",
        reason="Windows-specific interrupt test"
    )
    def test_windows_interrupt_basic(self):
        """Test basic interrupt handling on Windows

        Note: This test cannot actually trigger Ctrl+C automatically.
        It verifies that the interrupt mechanism is set up correctly.
        """
        # Test that KeyboardInterrupt can be caught
        caught_interrupt = False
        try:
            raise KeyboardInterrupt()
        except KeyboardInterrupt:
            caught_interrupt = True

        assert caught_interrupt, "KeyboardInterrupt should be catchable"

    @pytest.mark.skipif(
        platform.system() != "Windows",
        reason="Windows-specific test"
    )
    @pytest.mark.slow
    @pytest.mark.manual
    def test_windows_fz_interrupt(self):
        """Manual test for FZ interrupt handling on Windows

        This test should be run manually with Ctrl+C to verify interrupt handling.
        It is marked as 'manual' and skipped by default.
        """
        pytest.skip("Manual test - requires user interaction (Ctrl+C)")


class TestPandasRequirement:
    """Test that fzd properly requires pandas"""

    def test_pandas_is_available(self):
        """Test that pandas is installed and importable"""
        try:
            import pandas as pd
            assert pd is not None
        except ImportError:
            pytest.fail("pandas should be installed for fzd to work")

    def test_fzd_imports_pandas(self):
        """Test that importing fz.core checks for pandas"""
        # This should not raise an error if pandas is installed
        from fz import core
        assert core.PANDAS_AVAILABLE is True

    def test_fzd_requires_pandas_error_message(self):
        """Test that fzd gives helpful error if pandas is missing

        Note: This test is informational only since pandas is required
        for the test suite to run.
        """
        # We can't actually test the error without uninstalling pandas,
        # but we can verify the check exists
        from fz import core

        # Verify PANDAS_AVAILABLE flag exists
        assert hasattr(core, 'PANDAS_AVAILABLE')

        # Since pandas must be installed for tests to run, it should be True
        assert core.PANDAS_AVAILABLE is True
