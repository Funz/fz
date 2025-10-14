#!/usr/bin/env python3
"""
Test script for enhanced logging functionality
"""
import os
import tempfile
import time
from pathlib import Path
import sys

import fz

def test_local_enhanced_logging():
    """Test that local calculations create enhanced log files"""
    print("Testing enhanced logging for local calculations...")

    test_model = {
        "varprefix": "$",
        "delim": "{}",
        "output": {"result": "cat result.txt 2>/dev/null || echo 'no result'"}
    }

    # Create temporary input file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("# Test input for enhanced logging\ntest_param = 42\n")
        temp_input = f.name

    try:
        # Run calculation that creates result file
        results = fz.fzr(
            temp_input,
            test_model,
            {"param": 1},
            results_dir="test_enhanced_logs",
            calculators=["sh://echo 'test result' > result.txt && sleep 0.1"]
        )

        print(f"Calculation results: {results}")

        # Check that results directory was created
        results_dir = Path("test_enhanced_logs")
        assert results_dir.exists(), "Results directory should exist"

        # Check for enhanced log file
        log_file = results_dir / "log.txt"
        assert log_file.exists(), "Log file should exist"

        # Read and verify log content
        log_content = log_file.read_text()
        print(f"\nLog file contents:\n{log_content}")

        # Verify required log entries are present
        required_fields = [
            "Command:",
            "Exit code:",
            "Time start:",
            "Time end:",
            "Execution time:",
            "User:",
            "Hostname:",
            "Operating system:",
            "Platform:",
            "Working directory:",
            "Original directory:",
            "Timestamp:"
        ]

        missing_fields = []
        for field in required_fields:
            if field not in log_content:
                missing_fields.append(field)

        # Assert all required fields are present
        assert not missing_fields, f"Missing fields in log: {missing_fields}"

        print("✓ Enhanced logging test PASSED")

    except Exception as e:
        print(f"✗ Enhanced logging test FAILED: {e}")
        raise

    finally:
        try:
            os.unlink(temp_input)
            import shutil
            if Path("test_enhanced_logs").exists():
                shutil.rmtree("test_enhanced_logs")
        except:
            pass

def test_environment_info_function():
    """Test the get_environment_info function directly"""
    print("\nTesting get_environment_info function...")

    try:
        from fz.runners import get_environment_info

        env_info = get_environment_info()
        print(f"Environment info: {env_info}")

        # Check that all expected fields are present
        expected_fields = [
            'user', 'hostname', 'operating_system',
            'platform', 'working_dir', 'python_version'
        ]

        missing_fields = []
        for field in expected_fields:
            if field not in env_info:
                missing_fields.append(field)

        # Assert all expected fields are present
        assert not missing_fields, f"Missing fields in environment info: {missing_fields}"

        # Check that values are not empty or 'unknown'
        for field, value in env_info.items():
            if not value or value == 'unknown':
                print(f"Warning: Field '{field}' has empty or unknown value: '{value}'")

        print("✓ Environment info function test PASSED")

    except Exception as e:
        print(f"✗ Environment info function test FAILED: {e}")
        raise

if __name__ == "__main__":
    print("Testing FZ enhanced logging functionality")
    print("=" * 50)

    try:
        test_environment_info_function()
        test_local_enhanced_logging()

        print("\n" + "=" * 50)
        print("Tests completed: 2/2 passed")
        print("🎉 All logging tests PASSED!")
        exit(0)
    except Exception as e:
        print("\n" + "=" * 50)
        print("❌ Some logging tests FAILED!")
        print(f"Error: {e}")
        exit(1)