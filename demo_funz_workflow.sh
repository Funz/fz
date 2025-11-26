#!/bin/bash
# Demo script showing complete Funz workflow with UDP discovery
# This demonstrates the two-step process:
# 1. UDP discovery to find TCP port
# 2. fzr execution using discovered TCP port

set -e  # Exit on error

echo "======================================================================="
echo " Funz Calculator UDP Discovery + fzr Demo"
echo "======================================================================="
echo ""

# Configuration
UDP_PORT=${FUNZ_UDP_PORT:-5555}
DISCOVERY_TIMEOUT=${FUNZ_DISCOVERY_TIMEOUT:-15}

echo "Configuration:"
echo "  UDP Port: $UDP_PORT"
echo "  Discovery Timeout: ${DISCOVERY_TIMEOUT}s"
echo ""

# Check if mock or real calculator should be used
USE_MOCK=${USE_MOCK:-0}

if [ "$USE_MOCK" = "1" ]; then
    echo "=========================================================================="
    echo " Option 1: Using Mock Calculator (for testing without Java)"
    echo "=========================================================================="
    echo ""
    echo "Starting mock UDP broadcast in background..."
    python tools/mock_funz_udp_broadcast.py --udp-port $UDP_PORT --tcp-port 55555 &
    MOCK_PID=$!
    echo "Mock broadcast PID: $MOCK_PID"
    echo ""

    # Give it a moment to start
    sleep 2

    echo "Note: Mock only broadcasts UDP messages. It won't accept TCP connections."
    echo "This demonstrates UDP discovery but will fail at fzr step."
    echo ""
else
    echo "=========================================================================="
    echo " Option 2: Using Real Java Funz Calculator"
    echo "=========================================================================="
    echo ""
    echo "Prerequisites:"
    echo "  1. Funz calculator must be built and running"
    echo "  2. See .github/workflows/funz-calculator.yml for setup"
    echo "  3. Calculator should broadcast on UDP port $UDP_PORT"
    echo ""
    echo "Quick start (from funz-calculator/dist):"
    echo "  java -Dapp.home=. -classpath \"\$LIB\" \\"
    echo "       org.funz.calculator.Calculator \\"
    echo "       file:calculator-$UDP_PORT.xml"
    echo ""
fi

echo "=========================================================================="
echo " Running UDP Discovery and fzr Test"
echo "=========================================================================="
echo ""

# Run the test script
if [ "$USE_MOCK" = "1" ]; then
    # With mock, expect UDP discovery to work but fzr to fail
    echo "Running with mock calculator (UDP only)..."
    FUNZ_UDP_PORT=$UDP_PORT FUNZ_DISCOVERY_TIMEOUT=$DISCOVERY_TIMEOUT \
        python test_funz_udp_discovery.py || true

    # Cleanup mock
    echo ""
    echo "Stopping mock calculator..."
    kill $MOCK_PID 2>/dev/null || true
    wait $MOCK_PID 2>/dev/null || true
else
    # With real calculator, expect full success
    echo "Running with real Java Funz calculator..."
    FUNZ_UDP_PORT=$UDP_PORT FUNZ_DISCOVERY_TIMEOUT=$DISCOVERY_TIMEOUT \
        python test_funz_udp_discovery.py
fi

echo ""
echo "=========================================================================="
echo " Demo Complete"
echo "=========================================================================="
echo ""

if [ "$USE_MOCK" = "1" ]; then
    echo "Next steps:"
    echo "  1. Build and start real Java Funz calculator"
    echo "  2. Run: ./demo_funz_workflow.sh"
    echo "  3. See FUNZ_UDP_DISCOVERY.md for detailed setup"
else
    echo "For testing without Java calculator:"
    echo "  USE_MOCK=1 ./demo_funz_workflow.sh"
fi

echo ""
