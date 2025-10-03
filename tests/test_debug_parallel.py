#!/usr/bin/env python3
"""
Debug script to understand parallel execution issues
"""
import os
import tempfile
import time
from pathlib import Path
from datetime import datetime

# Add fz package to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

import fz

def test_debug_parallel_execution():
    """Debug the parallel execution to see what's happening"""
    print("Debugging parallel execution behavior...")

    test_model = {
        "varprefix": "$",
        "delim": "()",
        "output": {"result": "cat result.txt 2>/dev/null || echo 'no result'"}
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input\nparam = 42\n")
        temp_input = f.name

    try:
        print("Testing calculators and cache behavior...")

        # Test with different calculator combinations
        test_cases = [
            {
                "name": "No cache - 2 calculators",
                "calculators": [
                    "sh://sleep 1 && echo 'fast result' > result.txt",
                    "sh://sleep 2 && echo 'slow result' > result.txt"
                ]
            },
            {
                "name": "With cache - 2 non-cache calculators",
                "calculators": [
                    "cache://results",
                    "sh://sleep 1 && echo 'fast result' > result.txt",
                    "sh://sleep 2 && echo 'slow result' > result.txt"
                ]
            },
        ]

        for i, test_case in enumerate(test_cases):
            print(f"\n--- Test {i+1}: {test_case['name']} ---")
            start_time = datetime.now()

            results = fz.fzr(
                temp_input,
                test_model,
                {"value": 1},
                results_dir=f"debug_results_{i}",
                calculators=test_case['calculators']
            )

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            print(f"Execution time: {execution_time:.2f} seconds")
            print(f"Calculator used: {results.get('calculator', ['unknown'])[0]}")
            print(f"Status: {results.get('status', ['unknown'])[0]}")

            if execution_time < 1.5:
                print("✓ FAST execution (likely parallel or cache)")
            elif execution_time < 2.5:
                print("→ MEDIUM execution (likely sequential or fast calculator)")
            else:
                print("⚠ SLOW execution (likely sequential)")

    except Exception as e:
        print(f"✗ Debug test FAILED: {e}")
        import traceback
        traceback.print_exc()

    finally:
        try:
            os.unlink(temp_input)
            import shutil
            for i in range(2):
                if Path(f"debug_results_{i}").exists():
                    shutil.rmtree(f"debug_results_{i}")
        except:
            pass

if __name__ == "__main__":
    test_debug_parallel_execution()