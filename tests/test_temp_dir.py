"""
Simple test to verify that tests run in a temporary directory.
"""
import os
from pathlib import Path


def test_runs_in_temp_directory():
    """Verify that the test is running in a temporary directory."""
    cwd = os.getcwd()
    print(f"Current working directory: {cwd}")

    # Check that we're in a temp directory
    assert "/tmp" in cwd or "temp" in cwd.lower(), f"Not in temp directory: {cwd}"

    # Verify we can create files
    test_file = Path("test_file.txt")
    test_file.write_text("test content")
    assert test_file.exists()
    assert test_file.read_text() == "test content"

    print("✓ Test is running in temporary directory")
    print("✓ Files can be created and read")
