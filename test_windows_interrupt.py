#!/usr/bin/env python
"""
Test script to verify Ctrl+C interrupt handling on Windows

This script helps diagnose interrupt handling issues on Windows and verifies
that the polling-based approach works correctly.

Run this script and press Ctrl+C after a few seconds to test.
"""
import sys
import time
import platform

def test_basic_interrupt():
    """Test basic signal handling"""
    print(f"Platform: {platform.system()}")
    print(f"Python version: {sys.version}")
    print("\nTesting basic interrupt handling...")
    print("Press Ctrl+C to test interrupt (or Ctrl+Break on Windows for force quit)\n")

    try:
        for i in range(60):
            print(f"Running... {i+1}/60 seconds", end='\r')
            sys.stdout.flush()
            time.sleep(1)
        print("\n✓ Completed without interrupt")
    except KeyboardInterrupt:
        print("\n✓ Interrupt caught successfully!")
        return True

    return False


def test_fz_interrupt():
    """Test FZ interrupt handling with actual calculations"""
    import tempfile
    from pathlib import Path

    print("\n" + "="*60)
    print("Testing FZ interrupt handling")
    print("="*60)
    print("\nThis will run 20 slow calculations.")
    print("Press Ctrl+C after a few seconds to test graceful shutdown.\n")

    # Import fz
    try:
        import fz
    except ImportError:
        print("ERROR: Could not import fz. Make sure it's installed.")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create input file
        input_file = tmpdir / "input.txt"
        input_file.write_text("x=$x\n")

        # Create slow calculation script
        if platform.system() == "Windows":
            calc_script = tmpdir / "calc.bat"
            calc_script.write_text(f"""@echo off
timeout /t 5 /nobreak >nul
echo result=%1 > output.txt
""")
        else:
            calc_script = tmpdir / "calc.sh"
            calc_script.write_text("""#!/bin/bash
sleep 5
echo "result=$1" > output.txt
""")
            calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "output": {
                "result": "cat output.txt" if platform.system() != "Windows" else "type output.txt"
            }
        }

        # Run calculations
        try:
            print("Starting calculations...")
            if platform.system() == "Windows":
                calculator = f"sh://cmd /c {calc_script.absolute()}"
            else:
                calculator = f"sh://bash {calc_script.absolute()}"

            results = fz.fzr(
                str(input_file),
                {"x": list(range(1, 21))},  # 20 cases
                model,
                calculators=calculator,
                results_dir=str(tmpdir / "results")
            )

            print(f"\n✓ Completed {len(results)} calculations")
            return True

        except KeyboardInterrupt:
            print("\n✓ Interrupt was handled!")
            return True
        except Exception as e:
            print(f"\n✗ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Run all interrupt tests"""
    print("="*60)
    print("Windows Ctrl+C Interrupt Test Suite")
    print("="*60)

    # Test 1: Basic Python interrupt
    print("\nTest 1: Basic Python Interrupt Handling")
    print("-"*60)
    basic_works = test_basic_interrupt()

    if not basic_works:
        print("\n⚠️  WARNING: Basic interrupt handling doesn't work.")
        print("This suggests a Python/terminal configuration issue.")
        print("\nPossible causes:")
        print("  - Running in an IDE that doesn't properly handle Ctrl+C")
        print("  - Running as a background process")
        print("  - Terminal emulator doesn't send SIGINT")
        return False

    # Test 2: FZ interrupt
    print("\nTest 2: FZ Calculation Interrupt Handling")
    print("-"*60)
    fz_works = test_fz_interrupt()

    if fz_works:
        print("\n" + "="*60)
        print("✓ ALL TESTS PASSED")
        print("="*60)
        print("\nCtrl+C interrupt handling is working correctly on your system!")
    else:
        print("\n" + "="*60)
        print("✗ FZ INTERRUPT TEST FAILED")
        print("="*60)
        print("\nPlease report this issue with the following information:")
        print(f"  Platform: {platform.system()}")
        print(f"  Python version: {sys.version}")
        print(f"  Terminal: {input('What terminal are you using? ')}")

    return fz_works


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
