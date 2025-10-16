#!/usr/bin/env python3
"""
Test script to verify the logging system works correctly at different levels
"""
import os
import sys
import platform
from pathlib import Path
import pytest
from fz import fzr, set_log_level
from fz.logging import LogLevel

@pytest.mark.skipif(
    platform.system() == "Windows",
    reason="Test uses bash-specific syntax that doesn't work reliably on Windows"
)
def test_logging_levels():
    """Test the logging system at different verbosity levels"""

    print("=" * 60)
    print("TESTING LOGGING SYSTEM WITH DIFFERENT LEVELS")
    print("=" * 60)

    # Use temp directory from conftest fixture
    temp_dir = Path.cwd()
    print(f"Working in: {temp_dir}")

    # Create input file
    with open("input.txt", "w", newline='\n') as f:
        f.write("x = ${x}\n")

    # Create simple calculator
    with open("calc.sh", "w", newline='\n') as f:
        f.write("#!/bin/bash\necho 'result = success' > output.txt\n")
    os.chmod("calc.sh", 0o755)

    model = {
                "varprefix": "$",
                "delim": "{}",
                "output": {"result": "grep 'result = ' output.txt | cut -d '=' -f2"}
            }

    # Test different logging levels
    levels = [
                (LogLevel.ERROR, "ERROR (only errors)"),
                (LogLevel.WARNING, "WARNING (errors + warnings)"),
                (LogLevel.INFO, "INFO (errors + warnings + info)"),
                (LogLevel.DEBUG, "DEBUG (all messages)")
            ]

    all_successful = True
    for level, description in levels:
        print(f"\n{'='*20} {description} {'='*20}")
        set_log_level(level)

        try:
            result = fzr(
                "input.txt",
                {"x": [1]},  # Single case for cleaner output
                model,
                calculators=["sh://bash ./calc.sh"],
                results_dir=f"results_{level.name.lower()}"
            )

            print(f"Result: {result['result']}")

            # Verify the test succeeded
            if result['status'][0] != 'done':
                all_successful = False

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
            all_successful = False

    # Assert all logging levels work correctly
    assert all_successful, "Not all logging levels produced successful results"

# disable because once python started, the LOG env var is read and changing it has no effect
#def test_environment_variable():
#    """Test setting log level via environment variable"""
#    print(f"\n{'='*60}")
#    print("TESTING ENVIRONMENT VARIABLE CONFIGURATION")
#    print("=" * 60)
#
#    # Test different environment variable values
#    test_cases = ["ERROR", "WARNING", "INFO", "DEBUG", "invalid"]
#
#    valid_levels = []
#    for env_value in test_cases:
#        print(f"\nSetting FZ_LOG_LEVEL={env_value}")
#
#        # Set environment variable
#        os.environ['FZ_LOG_LEVEL'] = env_value
#
#        # Re-import to trigger environment initialization
#        from importlib import reload
#        import fz.logging
#        reload(fz.logging)
#
#        from fz.logging import get_log_level
#        current_level = get_log_level()
#        print(f"Current log level: {current_level.name}")
#
#        # Track valid level settings
#        if env_value != "invalid":
#            valid_levels.append(current_level.name == env_value)
#
#    # Assert environment variable configuration works for valid values
#    assert all(valid_levels), "Environment variable configuration failed for some valid values"

if __name__ == "__main__":
    print("🔍 Testing fz logging system...")
    test_logging_levels()
    #test_environment_variable()
    print(f"\n{'='*60}")
    print("✅ Logging system test completed!")
    print("To control logging in your scripts:")
    print("  1. Set environment: export FZ_LOG_LEVEL=INFO")
    print("  2. Or use in code: from fz import set_log_level, LogLevel; set_log_level(LogLevel.INFO)")
    print("=" * 60)