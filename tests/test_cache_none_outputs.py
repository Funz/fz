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
        f.write("    exit 123\n")  # Fail for x=2
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
                {"x": [1, 2, 3]},
                model,
                calculators=["sh://bash ./calc_fail.sh"],
        results_dir="results_1"
            )
    
    print(f"\nFirst run: "+str(result1.to_dict()))

    # check status (should have error for case x=2)
    assert all(result1['status'] == ['done', 'failed', 'done']), f"Unexpected statuses: {result1['status']}"

    # check no 'result' for x=2 case
    assert result1['result'][1] is None, f"Expected None result for x=2 case, got: {result1['result'][1]}"

    # check error message for x=2 case
    assert 'exit code 123' in result1.get('error', [''])[1], f"Expected error message for x=2 case, got: {result1.get('error', [''])[1]}"

    print("\n🚀 SECOND RUN: Using cache + working calculator (should skip cache for None cases)")
    result2 = fzr(
                "input.txt",
                {"x": [1, 2, 3]},
                model,
                calculators=["cache://results_1", "sh://bash ./calc_work.sh"],
        results_dir="results_2"
            )

    print(f"\nSecond run: "+str(result2.to_dict()))

    print(f"\nSecond run results: {result2['result']}")
    none_count_2 = sum(1 for r in result2['result'] if r is None)
    print(f"Cases with None outputs after cache+fix: {none_count_2}")

    assert all(result2['status'] == ['done', 'done', 'done']), f"Unexpected statuses in second run: {result2['status']}"
    assert none_count_2 == 0, f"Expected no None results in second run, got {none_count_2} None results"


if __name__ == "__main__":
    test_cache_none_outputs()