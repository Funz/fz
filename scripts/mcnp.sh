#!/bin/bash
# MCNP calculator wrapper
# Assumes MCNP6 is installed at /Applications/MCNP6 or in PATH

# Default installation path (adjust as needed)
MCNP_PATH="${MCNP_PATH:-/Applications/MCNP6}"
export DATAPATH="$MCNP_PATH/MCNP_DATA"

ulimit -s unlimited 2>/dev/null

# Track process IDs for cleanup
echo $$ >> PID

if [ -f "$MCNP_PATH/MCNP_CODE/bin/mcnp6" ]; then
    $MCNP_PATH/MCNP_CODE/bin/mcnp6 inp="$@" &
    PID_MCNP=$!
    echo $PID_MCNP >> PID
    wait $PID_MCNP
elif command -v mcnp6 &> /dev/null; then
    mcnp6 inp="$@" &
    PID_MCNP=$!
    echo $PID_MCNP >> PID
    wait $PID_MCNP
else
    echo "ERROR: MCNP6 not found. Please install MCNP6 or set MCNP_PATH environment variable."
    rm -f PID
    exit 1
fi

# Cleanup
if [ -f "PID" ]; then
    rm -f "PID"
fi
