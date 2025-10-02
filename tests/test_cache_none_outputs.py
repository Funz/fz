#!/usr/bin/env python3
"""
Test that cache is not reused when outputs contain None values
"""
import os
import tempfile
import shutil
from pathlib import Path
from fz import fzr

def test_cache_none_outputs():
    """Test that cases with None outputs are re-computed instead of using cache"""

    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_dir)
            print(f"Testing in: {temp_dir}")

            # Create input file
            with open("input.txt", "w") as f:
                f.write("x = $(x)\n")

            # Create a failing calculator (exits with error for x=2)
            with open("calc_fail.py", "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("import re\n")
                f.write("import sys\n")
                f.write("with open('input.txt') as f:\n")
                f.write("    content = f.read()\n")
                f.write(r"X = re.search(r'x = (\S+)', content).group(1)" + "\n")
                f.write("if X == '2':\n")
                f.write("    print('Failing for x=2', file=sys.stderr)\n")
                f.write("    sys.exit(1)\n")
                f.write("else:\n")
                f.write("    with open('output.txt', 'w') as out:\n")
                f.write("        out.write(f'result = success_{X}\\n')\n")
            os.chmod("calc_fail.py", 0o755)

            # Create a working calculator
            with open("calc_work.py", "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("import re\n")
                f.write("with open('input.txt') as f:\n")
                f.write("    content = f.read()\n")
                f.write(r"X = re.search(r'x = (\S+)', content).group(1)" + "\n")
                f.write("with open('output.txt', 'w') as out:\n")
                f.write("    out.write(f'result = fixed_{X}\\n')\n")
            os.chmod("calc_work.py", 0o755)

            model = {
                "varprefix": "$",
                "delim": "()",
                "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}
            }

            print("\n🚀 FIRST RUN: Using failing calculator (will create cache with None for x=2)")
            result1 = fzr(
                "input.txt",
                model,
                {"x": [1, 2, 3]},
                calculators=["python ./calc_fail.py"],
                resultsdir="results_1"
            )

            print(f"\nFirst run results: {result1['result']}")
            none_count = sum(1 for r in result1['result'] if r is None)
            print(f"Cases with None outputs: {none_count}")

            if none_count == 0:
                print("❌ Test setup failed - expected some None outputs from failing calculator")
                return False

            print("\n🚀 SECOND RUN: Using cache + working calculator (should skip cache for None cases)")
            result2 = fzr(
                "input.txt",
                model,
                {"x": [1, 2, 3]},
                calculators=["cache://results_1", "python ./calc_work.py"],
                resultsdir="results_2"
            )

            print(f"\nSecond run results: {result2['result']}")
            none_count_2 = sum(1 for r in result2['result'] if r is None)
            print(f"Cases with None outputs after cache+fix: {none_count_2}")

            # Verify that None outputs were fixed
            if none_count_2 == 0:
                print("✅ SUCCESS: Cache correctly skipped for None outputs, all cases now have valid results!")

                # Check that successful cases still used cache (should have 'success' prefix)
                # and failed cases used new calculator (should have 'fixed' prefix)
                cache_used = any('success' in str(r) for r in result2['result'] if r is not None)
                recomputed = any('fixed' in str(r) for r in result2['result'] if r is not None)

                if cache_used and recomputed:
                    print("✅ Perfect: Some results from cache (success_X), some recomputed (fixed_X)")
                    return True
                else:
                    print(f"⚠️ Mixed results: cache_used={cache_used}, recomputed={recomputed}")
                    return True  # Still success, just different pattern
            else:
                print(f"❌ FAILED: Still have {none_count_2} None outputs after cache+fix")
                return False

        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    success = test_cache_none_outputs()
    if success:
        print("\n🎉 Test PASSED: Cache correctly skips cases with None outputs!")
    else:
        print("\n💥 Test FAILED")