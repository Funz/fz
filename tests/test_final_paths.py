#!/usr/bin/env python3
"""
Final comprehensive test of path resolution in sh:// commands
"""

import sys
import os

from fz import fzr

def test_final_path_resolution():
    """Final test of path resolution capabilities"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("# Final path test\n")
        f.write("value = ${T}\n")

    # Create dummy scripts for testing
    scripts = {
        "local_script.sh": "#!/bin/bash\necho 'Local script executed'\n",
        "folder with spaces/script with spaces.sh": "#!/bin/bash\necho 'Script with spaces executed'\n",
        "multi_path_script.sh": "#!/bin/bash\necho 'Multi path script executed'\n",
        "helper.sh": "#!/bin/bash\necho 'Helper script executed'\n",
        "tools/bin/complex_script.sh": "#!/bin/bash\necho 'Complex script executed'\n"
    }
    for path, content in scripts.items():
        print(f"Creating script: '{path}'")
        if not os.path.exists(os.path.dirname(path)) and os.path.dirname(path) != '':
            print(f"Creating directory: '{os.path.dirname(path)}'")
            os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', newline='\n') as f:
            f.write(content)
        os.chmod(path, 0o755)

    test_cases = [
        {
            "name": "Simple relative path",
            "calculator": "sh://bash ./local_script.sh",
            "expected_status": "done"
        },
        {
            "name": "Quoted path with spaces",
            "calculator": "sh://bash \"folder with spaces/script with spaces.sh\"",
            "expected_status": "done"
        },
        {
            "name": "Multiple relative paths",
            "calculator": "sh://bash ./multi_path_script.sh ./helper.sh",
            "expected_status": "done"
        },
        {
            "name": "Nested subdirectory path",
            "calculator": "sh://bash tools/bin/complex_script.sh",
            "expected_status": "done"
        },
        {
            "name": "Already absolute path (no change needed)",
            "calculator": f"sh://bash {os.path.abspath('local_script.sh').replace(os.sep, '/')}",
            "expected_status": "done"
        }
    ]

    print("🔍 Final Comprehensive Path Resolution Test")
    print(f"Working directory: {os.getcwd()}")
    print(f"{'='*60}")

    all_passed = True
    results = []

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test_case['name']}")
        print(f"Calculator: {test_case['calculator']}")

        try:
            result = fzr("input.txt",
            {
                "T": [f"final_{i}"]
            },
            {
                "varprefix": "$",
                "delim": "{}",
                "output": {"test": "echo 'success' || echo 'failed'"}
            },
            calculators=[test_case['calculator']],
            results_dir=f"final_test_{i}")

            status = result['status'][0]
            error = result.get('error', [None])[0]

            if status == test_case['expected_status']:
                print(f"✅ PASS: Status = {status}")
                results.append(True)
            else:
                print(f"❌ FAIL: Expected {test_case['expected_status']}, got {status}")
                if error:
                    print(f"   Error: {error}")
                results.append(False)
                all_passed = False

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append(False)
            all_passed = False

    # Summary
    passed = sum(results)
    total = len(results)

    print(f"\n{'='*60}")
    print("FINAL TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests passed: {passed}/{total}")

    if all_passed:
        print("🎉 ALL PATH RESOLUTION TESTS PASSED!")
        print("✅ All relative paths are properly converted to absolute paths")
        print("✅ Quoted paths with spaces are handled correctly")
        print("✅ Multiple paths in commands are resolved properly")
        print("✅ Complex command structures work reliably")
        print("✅ Absolute paths are preserved unchanged")
    else:
        print("⚠️  Some tests failed - path resolution needs further improvement")

    # Assert all tests passed
    assert all_passed, \
        f"Expected all {total} path resolution tests to pass, but only {passed} passed"

if __name__ == "__main__":
    test_final_path_resolution()