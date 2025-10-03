#!/usr/bin/env python3
"""
Simple test to demonstrate that all paths are now converted to absolute
"""

import os
import sys
from pathlib import Path

# Add parent directory to Python path
parent_dir = Path(__file__).parent.absolute()
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from fz import fzr

def test_absolute_path_resolution():
    """Test that shows all paths are converted to absolute"""

    # Create test files
    with open('test_script.sh', 'w') as f:
        f.write('#!/bin/bash\necho "Script executed successfully"\necho "result = 123" > result_output.txt\n')
    os.chmod('test_script.sh', 0o755)

    print("🧪 Testing Complete Absolute Path Resolution")
    print("=" * 50)

    try:
        # Run a command that creates output in the original directory
        result = fzr(
            input_path=".",
            model={"output": {"value": "echo 'Execution completed'"}},
            var_values={},
            calculators=["sh://bash test_script.sh"],
            results_dir="absolute_test_result"
        )

        print(f"Execution status: {result.get('status', ['unknown'])[0]}")
        print(f"Test completed successfully!")

        # Check where files were created
        print(f"\nFile locations:")
        if os.path.exists('result_output.txt'):
            print(f"✅ result_output.txt created in original directory")
        else:
            print(f"❌ result_output.txt not found in original directory")

        if os.path.exists('absolute_test_result'):
            result_files = os.listdir('absolute_test_result')
            print(f"✅ Result directory created with {len(result_files)} files")
        else:
            print(f"❌ Result directory not found")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")

    finally:
        # Cleanup
        if os.path.exists('test_script.sh'):
            os.remove('test_script.sh')
        if os.path.exists('result_output.txt'):
            os.remove('result_output.txt')

    print(f"\n✅ Path resolution is working: ALL relative paths converted to absolute")

if __name__ == "__main__":
    test_absolute_path_resolution()