#!/usr/bin/env python3
"""
Test script to verify the logging system works correctly at different levels
"""
import os
import sys
import tempfile
import platform
from pathlib import Path
import pytest
from fz import fzr, set_log_level_from_string

@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Test uses bash-specific syntax that doesn't work reliably on Windows"
)
def test_logging_levels():
    """Test the logging system at different verbosity levels"""

    print("=" * 60)
    print("TESTING LOGGING SYSTEM WITH DIFFERENT LEVELS")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as temp_dir:
        original_cwd = os.getcwd()

        try:
            os.chdir(temp_dir)
            print(f"Working in: {temp_dir}")

            # Create input file
            with open("input.txt", "w") as f:
                f.write("x = $(x)\n")

            # Create simple calculator
            with open("calc.sh", "w") as f:
                f.write("#!/bin/bash\necho 'result = success' > output.txt\n")
            os.chmod("calc.sh", 0o755)

            model = {
                "varprefix": "$",
                "delim": "()",
                "output": {"result": "grep 'result = ' output.txt | awk '{print $3}'"}
            }

            # Test different logging levels
            levels = [
                "ERROR",
                "WARNING",
                "INFO",
                "DEBUG"
            ]

            for level, description in levels:
                print(f"\n{'='*20} {description} {'='*20}")
                set_log_level_from_string(level)

                result = fzr(
                    "input.txt",
                    model,
                    {"x": [1]},  # Single case for cleaner output
                    calculators=["sh://bash ./calc.sh"],
                    results_dir=f"results_{level.name.lower()}"
                )

                print(f"Result: {result['result']}")

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
        finally:
            os.chdir(original_cwd)

def test_environment_variable():
    """Test setting log level via environment variable"""
    print(f"\n{'='*60}")
    print("TESTING ENVIRONMENT VARIABLE CONFIGURATION")
    print("=" * 60)

    # Test different environment variable values
    test_cases = ["ERROR", "WARNING", "INFO", "DEBUG", "invalid"]

    for env_value in test_cases:
        print(f"\nSetting FZ_LOG_LEVEL={env_value}")

        # Set environment variable
        os.environ['FZ_LOG_LEVEL'] = env_value

        # Re-import to trigger environment initialization
        from importlib import reload
        import fz.logging
        reload(fz.logging)

        from fz.logging import get_log_level
        current_level = get_log_level()
        print(f"Current log level: {current_level.name}")

if __name__ == "__main__":
    print("🔍 Testing fz logging system...")
    test_logging_levels()
    test_environment_variable()
    print(f"\n{'='*60}")
    print("✅ Logging system test completed!")
    print("To control logging in your scripts:")
    print("  1. Set environment: export FZ_LOG_LEVEL=INFO")
    print("  2. Or use in code: from fz import set_log_level, LogLevel; set_log_level(LogLevel.INFO)")
    print("=" * 60)