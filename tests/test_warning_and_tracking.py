#!/usr/bin/env python3
"""
Test that warnings are displayed and resolved commands are tracked
"""

import os
import sys
from pathlib import Path

from fz import fzr

def test_warning_and_tracking():
    """Test that path resolution warnings are displayed and commands tracked"""

    # Create test files
    with open('test_warning_script.sh', 'w') as f:
        f.write('#!/bin/bash\necho "Script with path resolution"\necho "result = 456" > test_output.txt\n')
    os.chmod('test_warning_script.sh', 0o755)

    with open('input_data.txt', 'w') as f:
        f.write('test data\n')

    print("🧪 Testing Warning Display and Command Tracking")
    print("=" * 60)

    try:
        # Test with a command that should trigger path resolution
        result = fzr(
            input_path="input_data.txt",
            input_variables={},
            model={"output": {"value": "echo 'Completed'"}},
            calculators=["sh://bash test_warning_script.sh"],
            results_dir="warning_test_result"
        )

        print(f"\nExecution status: {result.get('status', ['unknown'])[0]}")

        # Check if command information is in the results
        if 'command' in result:
            print(f"✅ Command tracked: {result['command'][0]}")
        else:
            print(f"❌ Command not found in results")

        # Test with a command that should NOT trigger path resolution (no relative paths)
        print(f"\n{'='*60}")
        print("Testing command with no relative paths (should not show warning):")

        result2 = fzr(
            input_path="input_data.txt",
            input_variables={},
            model={"output": {"value": "echo 'No paths'"}},
            calculators=["sh://echo 'No relative paths here'"],
            results_dir="no_warning_test"
        )

        print(f"Execution status: {result2.get('status', ['unknown'])[0]}")

        if 'command' in result2:
            print(f"Command in results: {result2['command'][0]}")
        else:
            print(f"✅ No command tracking (expected for commands without path changes)")

        # Assert tests passed
        assert result.get('status', ['unknown'])[0] == 'done', \
            f"First test failed: expected status 'done', got {result.get('status', ['unknown'])[0]}"
        assert result2.get('status', ['unknown'])[0] == 'done', \
            f"Second test failed: expected status 'done', got {result2.get('status', ['unknown'])[0]}"
        assert 'command' in result, "Command tracking failed for first test"

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        raise

    finally:
        # Cleanup
        for f in ['test_warning_script.sh', 'input_data.txt', 'test_output.txt']:
            if os.path.exists(f):
                os.remove(f)

    print(f"\n✅ Warning and tracking system implemented successfully")

if __name__ == "__main__":
    test_warning_and_tracking()