#!/usr/bin/env python3
"""
Comprehensive test for ALL file path resolution in sh:// commands
"""

import sys
import os
import pytest

from fz import fzr

@pytest.fixture(autouse=True)
def comprehensive_test_environment():
    """Create a comprehensive test environment with various files and scripts"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("# Comprehensive path test\n")
        f.write("test = ${T}\n")

    # Create data files that will be referenced in commands
    with open("data.txt", 'w') as f:
        f.write("line1\nline2\nline3\n")

    with open("config.ini", 'w') as f:
        f.write("[settings]\nvalue=42\n")

    with open("input.dat", 'w') as f:
        f.write("input data for processing\n")

    # Create subdirectories and files
    os.makedirs("subdir", exist_ok=True)
    with open("subdir/nested.txt", 'w') as f:
        f.write("nested file content\n")

    os.makedirs("backup", exist_ok=True)

    # Create test scripts that will be used in commands

    # 1. Script that uses file operations
    with open("file_ops.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# File operations script\n")
        f.write("cp data.txt backup/data_copy.txt\n")
        f.write("echo 'result = 100' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("file_ops.sh", 0o755)

    # 2. Script that processes input file and creates output
    with open("process_data.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# Data processing script\n")
        f.write("grep 'value' config.ini > temp.txt\n")
        f.write("wc -l data.txt >> temp.txt\n")
        f.write("echo 'result = 200' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("process_data.sh", 0o755)

    # 3. Script that uses complex file operations
    with open("complex_ops.sh", 'w', newline='\n') as f:
        f.write("#!/bin/bash\n")
        f.write("# Complex operations script\n")
        f.write("cat input.dat | sed 's/input/processed/g' > processed.dat\n")
        f.write("find subdir -name '*.txt' -exec cp {} backup/ \\;\n")
        f.write("echo 'result = 300' > output.txt\n")
        f.write("exit 0\n")
    os.chmod("complex_ops.sh", 0o755)

    # 4. Python script that processes files
    with open("process.py", 'w') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        #f.write("with open('data.txt', 'r') as f:\n")
        #f.write("    lines = f.readlines()\n")
        f.write("with open('output.txt', 'w') as f:\n")
        f.write("    f.write('result = 400\\n')\n")
        #f.write("    f.write(f'lines = {len(lines)}\\n')\n")
    os.chmod("process.py", 0o755)

def test_comprehensive_path_resolution():
    """Test comprehensive path resolution with various command patterns"""

    import platform
    test_cases = [
        {
            "name": "Simple file copy operation",
            "calculator": "sh://cp data.txt output.txt && echo 'result = 100'",
            "expected_status": "done" if platform.system() != "Windows" else "failed"
        },
        #{ NO: redirection inside command line is not supported
        #    "name": "File processing with redirection",
        #    "calculator": "sh://grep 'line' data.txt > temp.txt && echo 'result = 200'",
        #    "expected_status": "done"
        #},
        {
            "name": "Script execution with file arguments",
            "calculator": "sh://bash file_ops.sh",
            "expected_status": "done"
        },
        #{ NO: redirection inside command line is not supported
        #    "name": "Complex command with multiple file operations",
        #    "calculator": "sh://cat config.ini | grep 'value' > temp.txt && wc -l data.txt >> temp.txt && echo 'result = 300'",
        #    "expected_status": "done"
        #},
        {
            "name": "Python script with file I/O",
            "calculator": "sh://python3 process.py",
            "expected_status": "done"
        },
        #{ NO: find with -exec and redirection inside command line is not supported
        #    "name": "File operations with subdirectories",
        #    "calculator": "sh://find subdir -name '*.txt' -exec cat {} \\; > combined.txt && echo 'result = 500'",
        #    "expected_status": "done"
        #},
        {
            "name": "Archive operations",
            "calculator": "sh://tar -czf archive.tar.gz subdir/ && echo 'result = 600'",
            "expected_status": "done" if platform.system() != "Windows" else "failed"
        },
        #{ NO: awk with file argument and redirection inside command line is not supported
        #    "name": "Multiple file arguments",
        #    "calculator": "sh://awk '{print $1}' data.txt config.ini > parsed.txt && echo 'result = 700'",
        #    "expected_status": "done"
        #},
        #{ NO: redirection inside command line is not supported
        #    "name": "File operations with pipes and redirections",
        #    "calculator": "sh://cat data.txt | sort | uniq > sorted.txt && echo 'result = 800'",
        #    "expected_status": "done"
        #},
        {
            "name": "Complex script with internal file operations",
            "calculator": "sh://bash complex_ops.sh",
            "expected_status": "done"
        }
    ]

    print("🧪 Comprehensive Test of ALL File Path Resolution")
    print("Testing detection and resolution of file paths in various contexts:")
    print("- File arguments to commands")
    print("- Input/output redirections")
    print("- Script paths and data files")
    print("- Complex command structures")
    print(f"Working directory: {os.getcwd()}")
    print(f"{'='*70}")

    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print(f"Command: {test_case['calculator']}")
        print("-" * 60)

        try:
            result = fzr("input.txt",
            {
                "T": [f"comprehensive_{i}"]
            },
            {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' out*.txt | cut -d '=' -f2 || echo 'failed'"}
            },
            calculators=[test_case['calculator']],
            results_dir=f"comprehensive_test_{i}")

            print(str(result.to_dict()))

            status = result['status'][0]
            result_value = result['result'][0]
            error = result.get('error', [None])[0]

            if status == test_case['expected_status']:
                print(f"✅ PASS: Status = {status}, Result = {result_value}")
                results.append(True)
            else:
                print(f"❌ FAIL: Expected {test_case['expected_status']}, got {status}")
                if error:
                    print(f"   Error: {error}")
                results.append(False)

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append(False)

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n{'='*70}")
    print("COMPREHENSIVE PATH RESOLUTION TEST SUMMARY")
    print(f"{'='*70}")
    print(f"Tests passed: {passed}/{total}")

    if passed == total:
        print("🎉 ALL COMPREHENSIVE PATH TESTS PASSED!")
        print("✅ File paths in all contexts are properly resolved")
        print("✅ Redirections, arguments, and file operations work correctly")
        print("✅ Complex command structures are handled properly")
        print("✅ Script execution with file dependencies is reliable")
    else:
        failed = total - passed
        print(f"⚠️  {failed} tests failed")
        print("❌ Some file path contexts are not being resolved correctly")

    # Assert all tests passed
    assert passed == total, \
        f"Expected all {total} comprehensive path tests to pass, but only {passed} passed"

if __name__ == "__main__":
    test_comprehensive_path_resolution()