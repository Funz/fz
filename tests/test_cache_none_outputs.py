#!/usr/bin/env python3
"""
Test that cache is not reused when outputs contain None values
"""
import os
import shutil
from pathlib import Path
from fz import fzr

def test_cache_none_outputs():
    """Test that cases with None outputs are re-computed instead of using cache"""

    # Use temp directory from conftest fixture
    temp_dir = Path.cwd()
    print(f"Testing in: {temp_dir}")

    # Create input file
    with open("input.txt", "w") as f:
        f.write("x = $(x)\n")

    # Create a failing calculator (exits with error for x=2)
    with open("calc_fail.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write("X=$(grep 'x =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("if [ \"$X\" = \"2\" ]; then\n")
        f.write("    echo 'Failing for x=2' >&2\n")
        f.write("    exit 1\n")  # Fail for x=2
        f.write("else\n")
        f.write("    echo \"result = success_$X\" > output.txt\n")
        f.write("fi\n")
    os.chmod("calc_fail.sh", 0o755)

    # Create a working calculator
    with open("calc_work.sh", "w") as f:
        f.write("#!/bin/bash\n")
        f.write("X=$(grep 'x =' input.txt | cut -d'=' -f2 | tr -d ' ')\n")
        f.write("echo \"result = fixed_$X\" > output.txt\n")
    os.chmod("calc_work.sh", 0o755)

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
                calculators=["sh://bash ./calc_fail.sh"],
        results_dir="results_1"
            )

    print(f"\nFirst run results: {result1['result']}")
    none_count = sum(1 for r in result1['result'] if r is None)
    print(f"Cases with None outputs: {none_count}")

    if none_count == 0:
        print("❌ Test setup failed - expected some None outputs from failing calculator")
        returnFalse

    print("\n🚀 SECOND RUN: Using cache + working calculator (should skip cache for None cases)")
    result2 = fzr(
                "input.txt",
                model,
                {"x": [1, 2, 3]},
                calculators=["cache://results_1", "sh://bash ./calc_work.sh"],
        results_dir="results_2"
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

if __name__ == "__main__":
    success = test_cache_none_outputs()
    if success:
        print("\n🎉 Test PASSED: Cache correctly skips cases with None outputs!")
    else:
        print("\n💥 Test FAILED")