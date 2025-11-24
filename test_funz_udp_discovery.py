#!/usr/bin/env python
"""
Test script for Funz calculator with UDP discovery and fzr integration.

This script demonstrates the complete Funz workflow:
1. Funz calculator daemon broadcasts UDP messages on a configured port (e.g., 5555)
2. UDP messages contain the TCP port for actual calculator communication
3. Python code discovers calculators via UDP and extracts TCP port
4. fzr uses funz://:tcp_port/code to communicate with the calculator

Architecture:
- HOST element in calculator XML specifies UDP broadcast port
- Calculator sends periodic UDP broadcasts with format: "FUNZ<version>\n<tcp_port>\n<codes>"
- Clients listen to UDP, parse TCP port, then connect via TCP for actual work

Usage:
    # Start Funz calculator first (see .github/workflows/funz-calculator.yml)
    python test_funz_udp_discovery.py
"""

import socket
import time
import tempfile
import os
from pathlib import Path
import sys


def discover_funz_calculator_udp(udp_port: int = 5555, timeout: float = 10.0) -> dict:
    """
    Discover Funz calculator by listening to UDP broadcasts.

    The Funz calculator daemon broadcasts messages on UDP port containing:
    - Line 1: Protocol version (e.g., "FUNZ1.0")
    - Line 2: TCP port number for calculator communication
    - Line 3+: Available code names (bash, sh, shell, etc.)

    Args:
        udp_port: UDP port to listen on (matches HOST port in calculator XML)
        timeout: Maximum time to wait for discovery (seconds)

    Returns:
        Dict with keys: tcp_port, codes, version, discovered
        Returns None if no calculator discovered
    """
    print(f"🔍 Discovering Funz calculator on UDP port {udp_port}...")
    print(f"   (Timeout: {timeout}s)")

    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        # Bind to UDP port to receive broadcasts
        sock.bind(('', udp_port))
        sock.settimeout(timeout)

        print(f"   Listening for UDP broadcasts on 0.0.0.0:{udp_port}...")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                # Receive UDP broadcast
                data, addr = sock.recvfrom(4096)

                # Parse the message
                message = data.decode('utf-8').strip()
                lines = message.split('\n')

                print(f"\n📡 Received UDP broadcast from {addr[0]}:{addr[1]}")
                print(f"   Raw message ({len(data)} bytes):")
                for i, line in enumerate(lines, 1):
                    print(f"   Line {i}: {line}")

                # Parse Funz protocol message
                if len(lines) >= 2:
                    version = lines[0]  # e.g., "FUNZ1.0"
                    tcp_port_str = lines[1]
                    codes = lines[2:] if len(lines) > 2 else []

                    # Validate and parse TCP port
                    try:
                        tcp_port = int(tcp_port_str)

                        result = {
                            'tcp_port': tcp_port,
                            'codes': codes,
                            'version': version,
                            'host': addr[0],
                            'discovered': True
                        }

                        print(f"\n✅ Funz calculator discovered!")
                        print(f"   Host: {result['host']}")
                        print(f"   TCP Port: {result['tcp_port']}")
                        print(f"   Version: {result['version']}")
                        print(f"   Available codes: {', '.join(result['codes']) if result['codes'] else 'none listed'}")

                        return result

                    except ValueError:
                        print(f"⚠️  Invalid TCP port in UDP message: {tcp_port_str}")
                        continue

            except socket.timeout:
                elapsed = time.time() - start_time
                remaining = timeout - elapsed
                if remaining > 0:
                    print(f"   Still waiting... ({elapsed:.1f}s elapsed, {remaining:.1f}s remaining)")
                continue

    finally:
        sock.close()

    print(f"\n❌ No Funz calculator discovered after {timeout}s timeout")
    return None


def test_funz_with_fzr(tcp_port: int, code: str = "bash"):
    """
    Test Funz calculator using fzr with the discovered TCP port.

    Args:
        tcp_port: TCP port for Funz calculator (from UDP discovery)
        code: Code name to execute (bash, sh, shell, etc.)
    """
    print(f"\n{'='*70}")
    print(f"Testing fzr with funz://{tcp_port}/{code}")
    print(f"{'='*70}\n")

    # Import fz
    try:
        import fz
    except ImportError:
        print("❌ Could not import fz. Install with: pip install -e .")
        return False

    # Create temporary directory for test
    with tempfile.TemporaryDirectory(prefix="funz_test_") as tmpdir:
        tmpdir = Path(tmpdir)
        print(f"📁 Working directory: {tmpdir}")

        # Create input template
        input_file = tmpdir / "input.txt"
        input_file.write_text("""# Test input for Funz calculator
x = ${x}
y = ${y}
sum = ${x} + ${y}
""")
        print(f"✓ Created input template: {input_file.name}")

        # Create calculation script
        calc_script = tmpdir / "calculate.sh"
        calc_script.write_text("""#!/bin/bash
# Extract values from input
x=$(grep "^x = " input.txt | awk '{print $3}')
y=$(grep "^y = " input.txt | awk '{print $3}')

# Calculate
sum=$((x + y))
product=$((x * y))

# Write results
echo "sum = $sum" > output.txt
echo "product = $product" >> output.txt
echo "Calculation complete: $x + $y = $sum, $x * $y = $product"
""")
        calc_script.chmod(0o755)
        print(f"✓ Created calculation script: {calc_script.name}")

        # Define model with output parsing
        model = {
            "output": {
                "sum": "grep '^sum = ' output.txt | awk '{print $3}'",
                "product": "grep '^product = ' output.txt | awk '{print $3}'"
            }
        }

        # Define parameters
        params = {
            "x": [1, 2, 3],
            "y": [10, 20]
        }

        # Construct funz:// URI
        # Format: funz://[host]:<tcp_port>/<code>
        # Since we're testing locally, host is implicit (localhost)
        funz_uri = f"funz://:{tcp_port}/{code}"

        print(f"\n🚀 Running fzr with:")
        print(f"   Calculator: {funz_uri}")
        print(f"   Parameters: {params}")
        print(f"   Expected cases: {len(params['x']) * len(params['y'])} (Cartesian product)")

        # Set debug logging
        os.environ['FZ_LOG_LEVEL'] = 'INFO'

        try:
            # Run fzr
            results = fz.fzr(
                input_file,
                params,
                model,
                calculators=funz_uri,
                results_dir=tmpdir / "results"
            )

            print(f"\n{'='*70}")
            print(f"✅ fzr completed successfully!")
            print(f"{'='*70}\n")

            # Display results
            if results is not None:
                print("📊 Results:")
                print(results)
                print()

                # Verify results
                if hasattr(results, 'shape'):
                    expected_cases = len(params['x']) * len(params['y'])
                    actual_cases = len(results)
                    print(f"✓ Generated {actual_cases}/{expected_cases} cases")

                    # Check if all results are present
                    if 'sum' in results.columns and 'product' in results.columns:
                        print(f"✓ Output variables parsed correctly")

                        # Verify calculations
                        all_correct = True
                        for idx, row in results.iterrows():
                            x_val = row.get('x')
                            y_val = row.get('y')
                            sum_val = row.get('sum')
                            product_val = row.get('product')

                            expected_sum = x_val + y_val
                            expected_product = x_val * y_val

                            if sum_val != expected_sum or product_val != expected_product:
                                print(f"  ✗ Case x={x_val}, y={y_val}: sum={sum_val} (expected {expected_sum}), product={product_val} (expected {expected_product})")
                                all_correct = False

                        if all_correct:
                            print(f"✓ All calculations verified correct")
                    else:
                        print(f"⚠️  Missing expected output columns")
                else:
                    print("⚠️  Results format unexpected")

                return True
            else:
                print("⚠️  No results returned")
                return False

        except Exception as e:
            print(f"\n❌ fzr failed with error:")
            print(f"   {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main test workflow."""
    print("="*70)
    print(" Funz UDP Discovery and fzr Integration Test")
    print("="*70)
    print()

    # Configuration
    udp_port = int(os.environ.get('FUNZ_UDP_PORT', '5555'))
    discovery_timeout = float(os.environ.get('FUNZ_DISCOVERY_TIMEOUT', '15'))

    print(f"Configuration:")
    print(f"  UDP Port: {udp_port} (set via FUNZ_UDP_PORT env var)")
    print(f"  Discovery Timeout: {discovery_timeout}s (set via FUNZ_DISCOVERY_TIMEOUT env var)")
    print()

    # Step 1: Discover calculator via UDP
    print("Step 1: UDP Discovery")
    print("-" * 70)
    calculator_info = discover_funz_calculator_udp(udp_port, discovery_timeout)

    if not calculator_info or not calculator_info.get('discovered'):
        print("\n❌ FAILED: Could not discover Funz calculator")
        print("\nTroubleshooting:")
        print("1. Ensure Funz calculator daemon is running")
        print("2. Check calculator XML has <HOST port=\"5555\" />")
        print("3. Verify no firewall blocking UDP port")
        print("4. Calculator should broadcast every ~5 seconds")
        sys.exit(1)

    tcp_port = calculator_info['tcp_port']
    codes = calculator_info['codes']

    # Step 2: Test with fzr
    print(f"\nStep 2: Test fzr with Funz Calculator")
    print("-" * 70)

    # Choose code to test (prefer bash, fallback to first available)
    test_code = 'bash' if 'bash' in codes else (codes[0] if codes else 'bash')

    success = test_funz_with_fzr(tcp_port, test_code)

    # Summary
    print("\n" + "="*70)
    print(" Test Summary")
    print("="*70)
    print(f"  UDP Discovery: ✅ Success")
    print(f"  TCP Port: {tcp_port}")
    print(f"  fzr Integration: {'✅ Success' if success else '❌ Failed'}")
    print()

    if success:
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
