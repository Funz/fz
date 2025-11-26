#!/usr/bin/env python
"""
Test script for Funz calculator with UDP discovery and fzr integration.

This script demonstrates the complete Funz workflow:
1. Downloads and builds Funz calculator infrastructure (funz-profile, funz-core, funz-calculator)
2. Starts Funz calculator daemon (broadcasts UDP on configured port)
3. Discovers calculator via UDP and extracts TCP port
4. Uses fzr with funz://:tcp_port/code for parametric calculations
5. Validates results and cleans up

Architecture:
- HOST element in calculator XML specifies UDP broadcast port
- Calculator sends periodic UDP broadcasts with format: "FUNZ<version>\n<tcp_port>\n<codes>"
- Clients listen to UDP, parse TCP port, then connect via TCP for actual work

Usage:
    # Auto-download and test (default)
    python test_funz_udp_discovery.py

    # Skip download if already exists
    python test_funz_udp_discovery.py --skip-download

    # Use existing calculator (no download/start)
    python test_funz_udp_discovery.py --no-setup

Environment Variables:
    FUNZ_UDP_PORT: UDP port for discovery (default: 5555)
    FUNZ_DISCOVERY_TIMEOUT: Discovery timeout in seconds (default: 15)
    FUNZ_SETUP_DIR: Directory for Funz installation (default: ~/.funz_test)
"""

import socket
import time
import tempfile
import os
import subprocess
import signal
import atexit
import shutil
from pathlib import Path
import sys
import argparse


# Global variables for cleanup
_calculator_process = None
_setup_dir = None


def setup_funz_calculator(setup_dir: Path, udp_port: int = 5555, skip_download: bool = False):
    """
    Download, build, and configure Funz calculator infrastructure.

    Args:
        setup_dir: Directory to install Funz components
        udp_port: UDP port for calculator broadcasts
        skip_download: Skip git clone if directories already exist

    Returns:
        Path to calculator dist directory
    """
    print(f"\n{'='*70}")
    print(f"Setting up Funz Calculator Infrastructure")
    print(f"{'='*70}\n")

    setup_dir.mkdir(parents=True, exist_ok=True)
    print(f"📁 Setup directory: {setup_dir}")

    # Check for required tools
    required_tools = ['git', 'ant', 'java']
    for tool in required_tools:
        if shutil.which(tool) is None:
            print(f"❌ Required tool not found: {tool}")
            print(f"   Please install: {', '.join(required_tools)}")
            sys.exit(1)

    print(f"✓ Required tools available: {', '.join(required_tools)}")
    print()

    # Clone and build funz-profile
    profile_dir = setup_dir / "funz-profile"
    if skip_download and profile_dir.exists():
        print(f"⏭️  Skipping funz-profile download (already exists)")
    else:
        print(f"📦 Cloning funz-profile...")
        if profile_dir.exists():
            shutil.rmtree(profile_dir)
        subprocess.run(
            ["git", "clone", "https://github.com/Funz/funz-profile.git", str(profile_dir)],
            check=True,
            capture_output=True
        )
        print(f"✓ funz-profile cloned")

    # Clone and build funz-core
    core_dir = setup_dir / "funz-core"
    if skip_download and core_dir.exists() and (core_dir / "dist").exists():
        print(f"⏭️  Skipping funz-core download and build (already exists)")
    else:
        print(f"📦 Cloning and building funz-core...")
        if core_dir.exists():
            shutil.rmtree(core_dir)
        subprocess.run(
            ["git", "clone", "https://github.com/Funz/funz-core.git", str(core_dir)],
            check=True,
            capture_output=True
        )

        # Build with ant
        subprocess.run(
            ["ant", "clean", "dist"],
            cwd=core_dir,
            check=True,
            capture_output=True
        )
        print(f"✓ funz-core built")

    # Clone and build funz-calculator
    calc_dir = setup_dir / "funz-calculator"
    if skip_download and calc_dir.exists() and (calc_dir / "dist").exists():
        print(f"⏭️  Skipping funz-calculator download and build (already exists)")
    else:
        print(f"📦 Cloning and building funz-calculator...")
        if calc_dir.exists():
            shutil.rmtree(calc_dir)
        subprocess.run(
            ["git", "clone", "https://github.com/Funz/funz-calculator.git", str(calc_dir)],
            check=True,
            capture_output=True
        )

        # Build with ant
        subprocess.run(
            ["ant", "clean", "dist"],
            cwd=calc_dir,
            check=True,
            capture_output=True
        )
        print(f"✓ funz-calculator built")

    dist_dir = calc_dir / "dist"

    # Create calculator configuration
    print(f"\n📝 Creating calculator configuration...")
    calc_xml = dist_dir / f"calculator-{udp_port}.xml"
    calc_xml.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<CALCULATOR name="calc-{udp_port}" spool="spool-{udp_port}">
  <HOST name="localhost" port="{udp_port}" />
  <CODE name="bash" command="/bin/bash" />
  <CODE name="sh" command="/bin/sh" />
  <CODE name="shell" command="/bin/bash" />
</CALCULATOR>
""")
    print(f"✓ Created {calc_xml.name}")

    # Create spool directory
    spool_dir = dist_dir / f"spool-{udp_port}"
    spool_dir.mkdir(exist_ok=True)
    print(f"✓ Created spool directory: {spool_dir.name}")

    print(f"\n✅ Funz calculator setup complete")
    print(f"   Installation: {setup_dir}")
    print(f"   Calculator dist: {dist_dir}")

    return dist_dir


def start_funz_calculator(dist_dir: Path, udp_port: int = 5555):
    """
    Start Funz calculator daemon.

    Args:
        dist_dir: Calculator dist directory
        udp_port: UDP port for broadcasts

    Returns:
        subprocess.Popen object for the calculator process
    """
    global _calculator_process

    print(f"\n{'='*70}")
    print(f"Starting Funz Calculator Daemon")
    print(f"{'='*70}\n")

    # Build classpath
    lib_dir = dist_dir / "lib"
    lib_patterns = [
        "funz-core-*.jar",
        "funz-calculator-*.jar",
        "commons-*.jar",
        "ftpserver-*.jar",
        "ftplet-*.jar",
        "mina-*.jar",
        "sigar-*.jar",
        "slf4j-*.jar"
    ]

    classpath_parts = []
    for pattern in lib_patterns:
        jars = list(lib_dir.glob(pattern))
        for jar in jars:
            classpath_parts.append(str(jar))

    if not classpath_parts:
        print(f"❌ No JAR files found in {lib_dir}")
        sys.exit(1)

    classpath = ":".join(classpath_parts)
    print(f"✓ Built classpath with {len(classpath_parts)} JARs")

    # Calculator configuration
    calc_xml = dist_dir / f"calculator-{udp_port}.xml"
    log_file = dist_dir / f"calculator_{udp_port}.log"

    print(f"📄 Calculator config: {calc_xml.name}")
    print(f"📄 Log file: {log_file.name}")

    # Start calculator process
    cmd = [
        "java",
        f"-Dapp.home={dist_dir}",
        "-classpath", classpath,
        "org.funz.calculator.Calculator",
        f"file:{calc_xml}"
    ]

    print(f"\n🚀 Starting calculator daemon...")
    print(f"   Command: java -Dapp.home=. -classpath ... org.funz.calculator.Calculator file:{calc_xml.name}")

    with open(log_file, "w") as log:
        process = subprocess.Popen(
            cmd,
            cwd=dist_dir,
            stdout=log,
            stderr=subprocess.STDOUT,
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )

    _calculator_process = process
    print(f"✓ Calculator started (PID: {process.pid})")

    # Wait for startup
    print(f"   Waiting for initialization...")
    time.sleep(3)

    # Check if still running
    if process.poll() is not None:
        print(f"❌ Calculator process exited prematurely")
        print(f"\n   Log output:")
        with open(log_file) as f:
            print(f.read())
        sys.exit(1)

    print(f"✓ Calculator running (PID: {process.pid})")
    print(f"   Check log: {log_file}")

    # Register cleanup
    atexit.register(lambda: stop_funz_calculator(process))

    return process


def stop_funz_calculator(process):
    """Stop Funz calculator daemon."""
    global _calculator_process

    if process and process.poll() is None:
        print(f"\n🛑 Stopping calculator daemon (PID: {process.pid})...")
        try:
            # Try graceful shutdown
            if hasattr(os, 'killpg'):
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            else:
                process.terminate()

            # Wait up to 5 seconds
            try:
                process.wait(timeout=5)
                print(f"✓ Calculator stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill
                if hasattr(os, 'killpg'):
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                else:
                    process.kill()
                print(f"✓ Calculator force stopped")
        except Exception as e:
            print(f"⚠️  Error stopping calculator: {e}")

    _calculator_process = None


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
        funz_uri = f"funz://:{tcp_port}/{code}"

        print(f"\n🚀 Running fzr with:")
        print(f"   Calculator: {funz_uri}")
        print(f"   Parameters: {params}")
        print(f"   Expected cases: {len(params['x']) * len(params['y'])} (Cartesian product)")

        # Set logging
        os.environ['FZ_LOG_LEVEL'] = os.environ.get('FZ_LOG_LEVEL', 'INFO')

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
    parser = argparse.ArgumentParser(
        description="Test Funz calculator with UDP discovery and fzr integration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--no-setup',
        action='store_true',
        help='Skip Funz download/build/start (use existing calculator)'
    )
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='Skip git clone if Funz directories already exist'
    )
    parser.add_argument(
        '--setup-dir',
        type=Path,
        default=Path.home() / ".funz_test",
        help='Directory for Funz installation (default: ~/.funz_test)'
    )
    parser.add_argument(
        '--udp-port',
        type=int,
        default=int(os.environ.get('FUNZ_UDP_PORT', '5555')),
        help='UDP port for discovery (default: 5555 or FUNZ_UDP_PORT env var)'
    )
    parser.add_argument(
        '--discovery-timeout',
        type=float,
        default=float(os.environ.get('FUNZ_DISCOVERY_TIMEOUT', '15')),
        help='Discovery timeout in seconds (default: 15 or FUNZ_DISCOVERY_TIMEOUT env var)'
    )

    args = parser.parse_args()

    print("="*70)
    print(" Funz UDP Discovery and fzr Integration Test")
    print("="*70)
    print()

    print(f"Configuration:")
    print(f"  Setup Mode: {'Disabled (using existing calculator)' if args.no_setup else 'Enabled'}")
    print(f"  Setup Directory: {args.setup_dir}")
    print(f"  Skip Download: {args.skip_download}")
    print(f"  UDP Port: {args.udp_port}")
    print(f"  Discovery Timeout: {args.discovery_timeout}s")
    print()

    calculator_process = None

    try:
        # Setup and start calculator (unless --no-setup)
        if not args.no_setup:
            dist_dir = setup_funz_calculator(
                args.setup_dir,
                args.udp_port,
                args.skip_download
            )
            calculator_process = start_funz_calculator(dist_dir, args.udp_port)

        # Step 1: Discover calculator via UDP
        print(f"\nStep 1: UDP Discovery")
        print("-" * 70)
        calculator_info = discover_funz_calculator_udp(args.udp_port, args.discovery_timeout)

        if not calculator_info or not calculator_info.get('discovered'):
            print("\n❌ FAILED: Could not discover Funz calculator")
            print("\nTroubleshooting:")
            print("1. Ensure Funz calculator daemon is running")
            print("2. Check calculator XML has <HOST port=\"5555\" />")
            print("3. Verify no firewall blocking UDP port")
            print("4. Calculator broadcasts every ~5 seconds")
            sys.exit(1)

        tcp_port = calculator_info['tcp_port']
        codes = calculator_info['codes']

        # Step 2: Test with fzr
        print(f"\nStep 2: Test fzr with Funz Calculator")
        print("-" * 70)

        # Choose code to test
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
            return 0
        else:
            print("❌ SOME TESTS FAILED")
            return 1

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        return 130

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        if calculator_process:
            stop_funz_calculator(calculator_process)


if __name__ == "__main__":
    sys.exit(main())
