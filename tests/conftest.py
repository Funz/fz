"""
Pytest configuration for fz tests.
All tests automatically run in a temporary directory.
"""
import os
import tempfile
import pytest
from pathlib import Path


@pytest.fixture(autouse=True)
def temp_test_dir(tmp_path, monkeypatch):
    """
    Automatically run all tests in a temporary directory.

    This fixture:
    - Creates a temporary directory for each test
    - Changes the working directory to that temp directory
    - Restores the original directory after the test completes
    - Cleans up the temp directory automatically

    Args:
        tmp_path: pytest's built-in fixture for temporary directories
        monkeypatch: pytest's fixture for modifying environment
    """
    # Store original directory
    original_dir = os.getcwd()

    # Change to temp directory
    monkeypatch.chdir(tmp_path)

    # Yield to run the test
    yield tmp_path

    # Cleanup: change back to original directory
    # (monkeypatch automatically restores, but being explicit)
    os.chdir(original_dir)
