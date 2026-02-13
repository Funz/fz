#!/usr/bin/env python3
"""
Test that path resolution uses current working directory correctly
"""

import os
import sys
from pathlib import Path

from fz import fzr

def test_current_dir_fix():
    """Test that path resolution uses current working directory, not case directory"""

    # Use the temp directory provided by conftest fixture
    temp_path = Path.cwd()

    # Create test files in the temporary directory
    script_file = temp_path / "test_script.sh"
    input_file = temp_path / "test_input.txt"

    with open(script_file, 'w') as f:
        f.write('#!/bin/bash\necho "Test executed from: ${pwd}"\necho "result = 777" > test_result.txt\n')
    os.chmod(script_file, 0o755)

    with open(input_file, 'w') as f:
        f.write('test data for current dir fix\n')

    print("🔧 Testing Current Directory Path Resolution Fix")
    print("=" * 60)
    print(f"Working directory: {os.getcwd()}")
    print(f"Script file: {script_file.name} (should be resolved relative to this dir)")

    # Run fzr with a relative path to the script
    result = fzr(
        input_path="test_input.txt",
        model={"output": {"value": "echo 'Test completed'"}},
        input_variables={},
        calculators=["sh://bash test_script.sh"],
        results_dir="current_dir_test"
    )

    print(f"\n📊 Results:")
    # Handle both DataFrame and dict return types
    if hasattr(result, 'to_dict'):
        result_dict = result.to_dict('list')
    else:
        result_dict = result
    print(f"Status: {result_dict.get('status', ['unknown'])[0]}")
    print(f"Command: {result_dict.get('command', ['None'])[0]}")

    # Check if the command uses the correct absolute path
    resolved_cmd = result_dict.get('command', [''])[0]
    expected_path = str(script_file)

    # Normalize paths for cross-platform comparison (Windows uses backslashes, bash uses forward slashes)
    expected_path_normalized = expected_path.replace('\\', '/')
    resolved_cmd_normalized = resolved_cmd.replace('\\', '/') if resolved_cmd else ''

    if resolved_cmd_normalized and expected_path_normalized in resolved_cmd_normalized:
        print(f"✅ Path resolution CORRECT: Uses current working directory")
        print(f"   Expected: {expected_path_normalized}")
        print(f"   Got:      {resolved_cmd_normalized}")
    else:
        print(f"❌ Path resolution INCORRECT")
        print(f"   Expected path: {expected_path_normalized}")
        print(f"   Resolved command: {resolved_cmd_normalized}")

    # Assert path resolution is correct
    assert result_dict.get('status', ['unknown'])[0] == 'done', \
        f"Expected status 'done', got: {result_dict.get('status', ['unknown'])[0]}"
    assert resolved_cmd_normalized and expected_path_normalized in resolved_cmd_normalized, \
        f"Path resolution incorrect: expected '{expected_path_normalized}' in command '{resolved_cmd_normalized}'"

if __name__ == "__main__":
    test_current_dir_fix()
