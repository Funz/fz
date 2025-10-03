#!/usr/bin/env python3
"""
Test that path resolution uses current working directory correctly
"""

import os
import sys
import tempfile
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_current_dir_fix():
    """Test that path resolution uses current working directory, not case directory"""

    # Create a temporary directory to work from
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create test files in the temporary directory
        script_file = temp_path / "test_script.sh"
        input_file = temp_path / "test_input.txt"

        with open(script_file, 'w') as f:
            f.write('#!/bin/bash\necho "Test executed from: $(pwd)"\necho "result = 777" > test_result.txt\n')
        os.chmod(script_file, 0o755)

        with open(input_file, 'w') as f:
            f.write('test data for current dir fix\n')

        # Change to the temporary directory
        original_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            print("🔧 Testing Current Directory Path Resolution Fix")
            print("=" * 60)
            print(f"Working directory: {os.getcwd()}")
            print(f"Script file: {script_file.name} (should be resolved relative to this dir)")

            # Run fzr with a relative path to the script
            result = fzr(
                input_path="test_input.txt",
                model={"output": {"value": "echo 'Test completed'"}},
                varvalues={},
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

            if resolved_cmd and expected_path in resolved_cmd:
                print(f"✅ Path resolution CORRECT: Uses current working directory")
                print(f"   Expected: {expected_path}")
                print(f"   Got:      {resolved_cmd}")
            else:
                print(f"❌ Path resolution INCORRECT")
                print(f"   Expected path: {expected_path}")
                print(f"   Resolved command: {resolved_cmd}")

        finally:
            # Restore original working directory
            os.chdir(original_cwd)

if __name__ == "__main__":
    test_current_dir_fix()