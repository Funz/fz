#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path
from fz import fzr

def simple_test():
    """Minimal test to debug path issues"""

    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_dir)
            print(f"Working in: {temp_dir}")
            print(f"CWD at start: {os.getcwd()}")

            # Create minimal input
            with open("input.txt", "w") as f:
                f.write("x = $(x)\n")

            with open("calc.py", "w") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("with open('output.txt', 'w') as f:\n")
                f.write("    f.write('result = 42\\n')\n")
            os.chmod("calc.py", 0o755)

            print(f"Files created: {os.listdir('.')}")
            print(f"CWD before fzr: {os.getcwd()}")

            # Minimal fzr call with only 2 cases to debug
            result = fzr(
                "input.txt",
                {"varprefix": "$", "delim": "()", "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}},
                {"x": [1, 2]},  # Only 2 cases
                calculators=["python ./calc.py"],
                resultsdir="results"
            )

            print(f"\nCWD after fzr: {os.getcwd()}")
            print(f"Results: {result}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            os.chdir(original_cwd)

if __name__ == "__main__":
    simple_test()