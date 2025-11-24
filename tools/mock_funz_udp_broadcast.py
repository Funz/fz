#!/usr/bin/env python
"""
Mock Funz Calculator UDP Broadcast

This script simulates the UDP broadcast behavior of a Funz calculator daemon.
Useful for testing the UDP discovery mechanism without running the full Java stack.

The real Funz calculator broadcasts UDP messages periodically containing:
- Protocol version
- TCP port for actual communication
- Available code names

Usage:
    # Broadcast on default port 5555 with TCP port 55555
    python mock_funz_udp_broadcast.py

    # Custom ports
    python mock_funz_udp_broadcast.py --udp-port 5556 --tcp-port 56789

    # Custom codes
    python mock_funz_udp_broadcast.py --codes bash sh python R
"""

import socket
import time
import argparse
import sys


def broadcast_funz_availability(
    udp_port: int = 5555,
    tcp_port: int = 55555,
    codes: list = None,
    interval: float = 5.0,
    version: str = "FUNZ1.0"
):
    """
    Broadcast Funz calculator availability via UDP.

    Args:
        udp_port: UDP port to broadcast on (matches calculator XML HOST port)
        tcp_port: TCP port where calculator would accept connections
        codes: List of available code names (bash, sh, shell, etc.)
        interval: Seconds between broadcasts
        version: Protocol version string
    """
    if codes is None:
        codes = ["bash", "sh", "shell"]

    # Create UDP socket for broadcasting
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Construct broadcast message
    # Format: version\ntcp_port\ncode1\ncode2\n...
    message_parts = [version, str(tcp_port)] + codes
    message = '\n'.join(message_parts)
    message_bytes = message.encode('utf-8')

    print(f"Mock Funz Calculator UDP Broadcast")
    print(f"=" * 70)
    print(f"UDP Broadcast Port: {udp_port}")
    print(f"TCP Port (in message): {tcp_port}")
    print(f"Protocol Version: {version}")
    print(f"Available Codes: {', '.join(codes)}")
    print(f"Broadcast Interval: {interval}s")
    print(f"=" * 70)
    print(f"\nBroadcast Message ({len(message_bytes)} bytes):")
    print("-" * 70)
    print(message)
    print("-" * 70)
    print(f"\nBroadcasting... (Press Ctrl+C to stop)")
    print()

    broadcast_count = 0

    try:
        while True:
            # Broadcast to local subnet
            # Real Funz uses multicast or subnet broadcast
            try:
                # Broadcast to localhost (for testing on same machine)
                sock.sendto(message_bytes, ('127.0.0.1', udp_port))

                # Also try broadcast address (may require elevated privileges)
                try:
                    sock.sendto(message_bytes, ('<broadcast>', udp_port))
                except:
                    pass  # Broadcast may not be allowed

                broadcast_count += 1
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{timestamp}] Broadcast #{broadcast_count} sent to port {udp_port}")

            except Exception as e:
                print(f"❌ Broadcast failed: {e}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n\n✓ Stopped after {broadcast_count} broadcasts")
        sock.close()
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        description="Mock Funz calculator UDP broadcast for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Default settings
  python mock_funz_udp_broadcast.py

  # Custom ports
  python mock_funz_udp_broadcast.py --udp-port 5556 --tcp-port 56789

  # Custom codes
  python mock_funz_udp_broadcast.py --codes bash python R matlab

  # Faster broadcasts for testing
  python mock_funz_udp_broadcast.py --interval 2
        """
    )

    parser.add_argument(
        '--udp-port',
        type=int,
        default=5555,
        help='UDP port to broadcast on (default: 5555)'
    )

    parser.add_argument(
        '--tcp-port',
        type=int,
        default=55555,
        help='TCP port to advertise in message (default: 55555)'
    )

    parser.add_argument(
        '--codes',
        nargs='+',
        default=['bash', 'sh', 'shell'],
        help='Available code names (default: bash sh shell)'
    )

    parser.add_argument(
        '--interval',
        type=float,
        default=5.0,
        help='Seconds between broadcasts (default: 5.0)'
    )

    parser.add_argument(
        '--version',
        default='FUNZ1.0',
        help='Protocol version string (default: FUNZ1.0)'
    )

    args = parser.parse_args()

    # Validate ports
    if not (1 <= args.udp_port <= 65535):
        print(f"❌ Error: UDP port must be between 1 and 65535")
        sys.exit(1)

    if not (1 <= args.tcp_port <= 65535):
        print(f"❌ Error: TCP port must be between 1 and 65535")
        sys.exit(1)

    # Start broadcasting
    try:
        broadcast_funz_availability(
            udp_port=args.udp_port,
            tcp_port=args.tcp_port,
            codes=args.codes,
            interval=args.interval,
            version=args.version
        )
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
