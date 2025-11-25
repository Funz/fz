#!/bin/bash
# Start Funz calculator daemon
#
# Usage:
#   ./start_funz_calculator.sh [udp_port] [install_dir]
#
# Arguments:
#   udp_port: UDP port for broadcasts (default: 5555)
#   install_dir: Funz installation directory (default: ~/.funz_calculator)
#
# The calculator will:
#   - Broadcast UDP messages on the specified port
#   - Listen for TCP connections (port communicated via UDP)
#   - Execute calculations with configured codes (bash, sh, shell)

set -e  # Exit on error

# Configuration
UDP_PORT="${1:-5555}"
INSTALL_DIR="${2:-$HOME/.funz_calculator}"
CALC_DIR="$INSTALL_DIR/funz-calculator"
DIST_DIR="$CALC_DIR/dist"
PID_FILE="$DIST_DIR/calculator_${UDP_PORT}.pid"
LOG_FILE="$DIST_DIR/calculator_${UDP_PORT}.log"
CONFIG_FILE="$DIST_DIR/calculator-${UDP_PORT}.xml"
SPOOL_DIR="$DIST_DIR/spool-${UDP_PORT}"

echo "======================================================================="
echo " Starting Funz Calculator Daemon"
echo "======================================================================="
echo ""
echo "Configuration:"
echo "  UDP Port: $UDP_PORT"
echo "  Install Dir: $INSTALL_DIR"
echo "  PID File: $PID_FILE"
echo "  Log File: $LOG_FILE"
echo ""

# Check if calculator is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "❌ Calculator already running (PID: $OLD_PID)"
        echo "   Stop it first: tools/stop_funz_calculator.sh $UDP_PORT"
        exit 1
    else
        echo "⚠️  Stale PID file found, removing..."
        rm "$PID_FILE"
    fi
fi

# Check installation
if [ ! -d "$DIST_DIR" ]; then
    echo "❌ Funz calculator not found at: $DIST_DIR"
    echo ""
    echo "Run setup first:"
    echo "  tools/setup_funz_calculator.sh"
    exit 1
fi

cd "$DIST_DIR"

# Create calculator configuration if not exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "📝 Creating calculator configuration..."
    cat > "$CONFIG_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<CALCULATOR name="calc-${UDP_PORT}" spool="spool-${UDP_PORT}">
  <HOST name="localhost" port="${UDP_PORT}" />
  <CODE name="bash" command="/bin/bash" />
  <CODE name="sh" command="/bin/sh" />
  <CODE name="shell" command="/bin/bash" />
</CALCULATOR>
EOF
    echo "✓ Created: $CONFIG_FILE"
fi

# Create spool directory
if [ ! -d "$SPOOL_DIR" ]; then
    mkdir -p "$SPOOL_DIR"
    echo "✓ Created spool directory: $SPOOL_DIR"
fi

# Build classpath
echo "Building classpath..."
LIB=""
for jar in lib/funz-core-*.jar \
           lib/funz-calculator-*.jar \
           lib/commons-*.jar \
           lib/ftpserver-*.jar \
           lib/ftplet-*.jar \
           lib/mina-*.jar \
           lib/sigar-*.jar \
           lib/slf4j-*.jar; do
    if [ -f "$jar" ]; then
        LIB="${LIB}:${jar}"
    fi
done

# Remove leading colon
LIB="${LIB:1}"

if [ -z "$LIB" ]; then
    echo "❌ No JAR files found in lib/"
    exit 1
fi

echo "✓ Classpath built"

# Start calculator daemon
MAIN="org.funz.calculator.Calculator"

echo ""
echo "🚀 Starting calculator daemon..."
echo "   Command: java -Dapp.home=. -classpath ... $MAIN file:$CONFIG_FILE"
echo ""

nohup java -Dapp.home=. -classpath "$LIB" $MAIN "file:$(basename $CONFIG_FILE)" \
    > "$LOG_FILE" 2>&1 &

PID=$!
echo $PID > "$PID_FILE"

echo "✓ Calculator started (PID: $PID)"
echo ""

# Wait a moment and check if still running
sleep 2

if ! ps -p $PID > /dev/null 2>&1; then
    echo "❌ Calculator process exited prematurely"
    echo ""
    echo "Log output:"
    echo "-------------------------------------------------------------------"
    cat "$LOG_FILE"
    echo "-------------------------------------------------------------------"
    rm -f "$PID_FILE"
    exit 1
fi

echo "✅ Calculator daemon running successfully"
echo ""
echo "Details:"
echo "  PID: $PID"
echo "  UDP Port: $UDP_PORT (broadcasts every ~5s)"
echo "  TCP Port: (check UDP broadcast messages)"
echo "  Config: $CONFIG_FILE"
echo "  Log: $LOG_FILE"
echo "  Spool: $SPOOL_DIR"
echo ""
echo "Monitor log:"
echo "  tail -f $LOG_FILE"
echo ""
echo "Stop calculator:"
echo "  tools/stop_funz_calculator.sh $UDP_PORT"
echo ""
echo "Test UDP discovery:"
echo "  python test_funz_udp_discovery.py --no-setup --udp-port $UDP_PORT"
echo ""
