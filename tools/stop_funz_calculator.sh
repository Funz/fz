#!/bin/bash
# Stop Funz calculator daemon
#
# Usage:
#   ./stop_funz_calculator.sh [udp_port] [install_dir]
#
# Arguments:
#   udp_port: UDP port of calculator to stop (default: 5555)
#   install_dir: Funz installation directory (default: ~/.funz_calculator)

set -e  # Exit on error

# Configuration
UDP_PORT="${1:-5555}"
INSTALL_DIR="${2:-$HOME/.funz_calculator}"
CALC_DIR="$INSTALL_DIR/funz-calculator"
DIST_DIR="$CALC_DIR/dist"
PID_FILE="$DIST_DIR/calculator_${UDP_PORT}.pid"
LOG_FILE="$DIST_DIR/calculator_${UDP_PORT}.log"

echo "======================================================================="
echo " Stopping Funz Calculator Daemon"
echo "======================================================================="
echo ""
echo "UDP Port: $UDP_PORT"
echo "PID File: $PID_FILE"
echo ""

# Check if PID file exists
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️  No PID file found at: $PID_FILE"
    echo ""
    echo "Calculator may not be running, or was started differently."
    echo ""

    # Try to find process by name
    echo "Searching for calculator process..."
    PIDS=$(pgrep -f "org.funz.calculator.Calculator.*calculator-${UDP_PORT}.xml" || true)

    if [ -z "$PIDS" ]; then
        echo "✓ No calculator process found for port $UDP_PORT"
        exit 0
    else
        echo "Found calculator process(es): $PIDS"
        echo ""
        read -p "Kill these processes? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Cancelled."
            exit 0
        fi

        for PID in $PIDS; do
            echo "Killing PID: $PID"
            kill $PID || true
        done

        sleep 2

        # Force kill if still running
        for PID in $PIDS; do
            if ps -p $PID > /dev/null 2>&1; then
                echo "Force killing PID: $PID"
                kill -9 $PID || true
            fi
        done

        echo "✓ Process(es) stopped"
        exit 0
    fi
fi

# Read PID
PID=$(cat "$PID_FILE")

# Check if process is running
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "⚠️  Process not running (PID: $PID)"
    rm -f "$PID_FILE"
    echo "✓ Removed stale PID file"
    exit 0
fi

echo "🛑 Stopping calculator (PID: $PID)..."

# Try graceful shutdown (SIGTERM)
kill "$PID" || true

# Wait up to 5 seconds for graceful shutdown
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✓ Calculator stopped gracefully"
        rm -f "$PID_FILE"

        echo ""
        echo "Log file preserved at:"
        echo "  $LOG_FILE"
        echo ""
        exit 0
    fi
    sleep 0.5
done

# Force kill if still running
echo "⚠️  Graceful shutdown timeout, force killing..."
kill -9 "$PID" || true

sleep 1

if ps -p "$PID" > /dev/null 2>&1; then
    echo "❌ Failed to stop calculator (PID: $PID)"
    exit 1
else
    echo "✓ Calculator force stopped"
    rm -f "$PID_FILE"

    echo ""
    echo "Log file preserved at:"
    echo "  $LOG_FILE"
    echo ""
    exit 0
fi
