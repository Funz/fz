#!/usr/bin/env python3
"""
Test edge cases for path resolution in sh:// commands
"""

import sys
import os
sys.path.insert(0, '/home/richet/Sync/Open/Funz/fz')

from fz import fzr

def create_edge_case_scripts():
    """Create scripts for edge case testing"""

    # Create input file
    with open("input.txt", 'w') as f:
        f.write("# Edge case test input\n")
        f.write("test = $(T)\n")

    # Script with spaces in path - use Python for cross-platform compatibility
    os.makedirs("folder with spaces", exist_ok=True)
    with open("folder with spaces/script with spaces.py", 'w') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("print('Script with spaces in path')\n")
        f.write("with open('output.txt', 'w') as out:\n")
        f.write("    out.write('result = 123\\n')\n")
    os.chmod("folder with spaces/script with spaces.py", 0o755)

    # Script with multiple path arguments - use Python for cross-platform compatibility
    with open("multi_path_script.py", 'w') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("import sys\n")
        f.write("print('Multi-path script executed')\n")
        f.write("print('Args:', sys.argv)\n")
        f.write("with open('output.txt', 'w') as out:\n")
        f.write("    out.write('result = 456\\n')\n")
    os.chmod("multi_path_script.py", 0o755)

    # Helper script - use Python for cross-platform compatibility
    with open("helper.py", 'w') as f:
        f.write("#!/usr/bin/env python3\n")
        f.write("print('Helper script')\n")
    os.chmod("helper.py", 0o755)

def test_edge_cases():
    """Test edge cases for path resolution"""

    test_cases = [
        {
            "name": "Multiple relative paths in command",
            "calculator": "python ./multi_path_script.py ./helper.py",
            "expected_result": 456
        },
        {
            "name": "Path with spaces (quoted)",
            "calculator": "python \"folder with spaces/script with spaces.py\"",
            "expected_result": 123
        },
        {
            "name": "Relative path with ../ parent directory",
            "calculator": f"python {os.path.join('.', 'multi_path_script.py')}",
            "expected_result": 456
        },
        {
            "name": "Simple relative path",
            "calculator": "python ./multi_path_script.py",
            "expected_result": 456
        }
    ]

    print("🧪 Testing Edge Cases for Path Resolution")
    print(f"Current working directory: {os.getcwd()}\n")

    results = []

    for i, test_case in enumerate(test_cases):
        print(f"{'='*60}")
        print(f"EDGE CASE {i+1}: {test_case['name']}")
        print(f"Calculator: {test_case['calculator']}")
        print(f"{'='*60}")

        try:
            result = fzr("input.txt",
            {
                "varprefix": "$",
                "delim": "()",
                "output": {"result": "grep 'result = ' output.txt | awk '{print $3}' || echo 'none'"}
            },
            {
                "T": [f"edge_{i+1}"]
            },
            engine="python",
            calculators=[test_case['calculator']],
            resultsdir=f"edge_test_{i+1}")

            test_result = {
                "test_name": test_case['name'],
                "status": result['status'][0],
                "result_value": result['result'][0],
                "expected": test_case['expected_result'],
                "error": result.get('error', [None])[0]
            }

            if test_result['status'] == 'done':
                print(f"✅ SUCCESS: Status={test_result['status']}, Result={test_result['result_value']}")
            else:
                print(f"❌ FAILED: Status={test_result['status']}, Error={test_result['error']}")

            results.append(test_result)

        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            results.append({
                "test_name": test_case['name'],
                "status": "exception",
                "error": str(e),
                "expected": test_case['expected_result']
            })

    # Summary
    print(f"\n{'='*60}")
    print("EDGE CASE TEST SUMMARY")
    print(f"{'='*60}")

    successful = sum(1 for r in results if r['status'] == 'done')
    total = len(results)

    for i, result in enumerate(results, 1):
        status_icon = "✅" if result['status'] == 'done' else "❌"
        print(f"  {i}. {status_icon} {result['test_name']}")
        if result['status'] != 'done':
            print(f"     Error: {result.get('error', 'Unknown error')}")

    print(f"\nResults: {successful}/{total} edge cases passed")

    return results

if __name__ == "__main__":
    create_edge_case_scripts()
    test_edge_cases()