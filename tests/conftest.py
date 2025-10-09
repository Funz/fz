"""
Pytest configuration for fz tests.
All tests automatically run in a temporary directory.
"""
import os
import tempfile
import pytest
import socket
import subprocess
import getpass
import shutil
from pathlib import Path


@pytest.fixture(autouse=True)
def temp_test_dir(request, monkeypatch):
    """
    Automatically run all tests in a temporary directory under ./tmp.

    This fixture:
    - Creates a temporary directory for each test in ./tmp
    - Changes the working directory to that temp directory
    - Restores the original directory after the test completes
    - Cleans up the temp directory automatically

    Args:
        request: pytest's request fixture for test information
        monkeypatch: pytest's fixture for modifying environment
    """
    # Store original directory
    original_dir = os.getcwd()

    # Create ./tmp directory if it doesn't exist
    tmp_base = Path(original_dir) / "tmp"
    tmp_base.mkdir(exist_ok=True)

    # Create a unique subdirectory for this test
    test_name = request.node.name
    # Sanitize test name for filesystem
    safe_test_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in test_name)
    test_dir = tmp_base / safe_test_name

    # If directory exists, remove it first to ensure clean state
    if test_dir.exists():
        shutil.rmtree(test_dir)

    test_dir.mkdir(parents=True, exist_ok=True)

    # Change to temp directory
    monkeypatch.chdir(test_dir)

    # Yield to run the test
    yield test_dir

    # Cleanup: change back to original directory
    # (monkeypatch automatically restores, but being explicit)
    os.chdir(original_dir)

    # Clean up test directory after test completes
    try:
        shutil.rmtree(test_dir)
    except Exception:
        pass  # Best effort cleanup


def is_ssh_server_available():
    """
    Check if SSH server is available on localhost.

    Returns:
        bool: True if SSH server is listening on port 22, False otherwise
    """
    try:
        # First, check if port 22 is open
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 22))
        sock.close()

        if result != 0:
            return False

        # Port is open, now verify it's actually an SSH server
        # Try a simple SSH command with a very short timeout
        result = subprocess.run(
            [
                "ssh",
                "-o", "ConnectTimeout=2",
                "-o", "BatchMode=yes",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",
                f"{getpass.getuser()}@localhost",
                "exit 0"
            ],
            capture_output=True,
            timeout=3
        )

        # Exit code 0 means connection was successful
        # Exit code 255 typically means SSH refused connection or auth failed
        # We only care if we can connect at all (server is running)
        return result.returncode in [0, 255]

    except (socket.error, subprocess.TimeoutExpired, FileNotFoundError):
        return False


# Create a pytest marker for SSH availability
SSH_AVAILABLE = is_ssh_server_available()


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "requires_ssh: mark test as requiring SSH server on localhost"
    )
    config.addinivalue_line(
        "markers", "requires_paramiko: mark test as requiring paramiko library for SSH"
    )
