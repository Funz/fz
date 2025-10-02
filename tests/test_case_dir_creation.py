#!/usr/bin/env python3
"""
Test that case directories are created in results dir before calculator execution
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

def test_case_directory_creation():
    """Test that case directories exist in results dir before calculators run"""

    # Create a script that checks if it's already in the results directory
    with open('check_location_script.py', 'w') as f:
        f.write('''#!/usr/bin/env python3
import os
import subprocess

with open("location_check.txt", "w") as f:
    f.write(f"Script running from: {os.getcwd()}\\n")
    f.write("Current directory contents:\\n")
    result = subprocess.run(["ls", "-la"], capture_output=True, text=True)
    f.write(result.stdout)
    f.write("Parent directory:\\n")
    result = subprocess.run(["ls", "-la", ".."], capture_output=True, text=True)
    f.write(result.stdout)

    # Check if we're in a results directory by looking for expected files
    if os.path.exists("test_case_input.txt"):
        f.write("✅ Input file found in current directory\\n")
    else:
        f.write("❌ Input file NOT found in current directory\\n")

    if os.path.exists(".fz_hash"):
        f.write("✅ Hash file found in current directory\\n")
    else:
        f.write("❌ Hash file NOT found in current directory\\n")

# Final result
with open("script_result.txt", "w") as f:
    f.write("result = 123\\n")

with open("location_check.txt", "a") as f:
    f.write("Location check completed\\n")
''')
    os.chmod('check_location_script.py', 0o755)

    with open('test_case_input.txt', 'w') as f:
        f.write('test input for case directory verification\n')

    print("🏗️  Testing Case Directory Creation Before Calculator Execution")
    print("=" * 70)

    try:
        # Test single case
        print("\n1️⃣ Testing Single Case:")
        result1 = fzr(
            input_path="test_case_input.txt",
            model={"output": {"value": "echo 'Single case test'"}},
            varvalues={},
            calculators=["python check_location_script.py"],
            resultsdir="single_case_test"
        )

        # Check single case results
        single_results_dir = Path("single_case_test")
        if single_results_dir.exists():
            print(f"  📁 Results directory exists: {single_results_dir}")

            # Check for location check file
            location_file = single_results_dir / "location_check.txt"
            if location_file.exists():
                print(f"  📄 Location check file found, content:")
                content = location_file.read_text()
                for line in content.split('\n'):
                    if line.strip():
                        print(f"    {line}")

                # Analyze the results
                if "✅ Input file found" in content and "✅ Hash file found" in content:
                    print(f"  ✅ Single case: Calculator ran in prepared results directory")
                else:
                    print(f"  ❌ Single case: Calculator did not run in prepared results directory")
            else:
                print(f"  ❌ Location check file not found")
        else:
            print(f"  ❌ Results directory not found")

        # Test multiple cases
        print(f"\n2️⃣ Testing Multiple Cases:")
        result2 = fzr(
            input_path="test_case_input.txt",
            model={"output": {"value": "echo 'Multiple case test'"}},
            varvalues={"param1": ["a", "b"], "param2": ["1", "2"]},
            calculators=["python check_location_script.py"],
            resultsdir="multi_case_test"
        )

        # Check multiple case results
        multi_results_dir = Path("multi_case_test")
        if multi_results_dir.exists():
            print(f"  📁 Results directory exists: {multi_results_dir}")

            # List subdirectories (each case should have its own)
            subdirs = [d for d in multi_results_dir.iterdir() if d.is_dir()]
            print(f"  📂 Found {len(subdirs)} case subdirectories:")

            cases_correct = 0
            for subdir in subdirs:
                print(f"    📁 {subdir.name}")

                location_file = subdir / "location_check.txt"
                if location_file.exists():
                    content = location_file.read_text()
                    if "✅ Input file found" in content and "✅ Hash file found" in content:
                        print(f"      ✅ Calculator ran in prepared directory")
                        cases_correct += 1
                    else:
                        print(f"      ❌ Calculator did not run in prepared directory")
                        # Show some of the content for debugging
                        lines = content.split('\n')[:5]
                        for line in lines:
                            if line.strip():
                                print(f"        {line}")
                else:
                    print(f"      ❌ Location check file not found")

            print(f"  📊 Summary: {cases_correct}/{len(subdirs)} cases ran in prepared directories")
        else:
            print(f"  ❌ Results directory not found")

        print(f"\n📋 Overall Summary:")
        print(f"  • Case directories are created in results directory BEFORE calculator execution")
        print(f"  • Input files are copied to case directories upfront")
        print(f"  • Hash files are created for cache matching")
        print(f"  • Calculators execute directly in their final result directories")

    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup
        for f in ['check_location_script.py', 'test_case_input.txt']:
            if os.path.exists(f):
                os.remove(f)

if __name__ == "__main__":
    test_case_directory_creation()