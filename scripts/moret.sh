#!/bin/bash
# MORET calculator wrapper
# Assumes MORET is installed at /opt/MORET or in PATH

if [ -f "/opt/MORET/scripts/moret.py" ]; then
    /opt/MORET/scripts/moret.py "$@"
elif command -v moret &> /dev/null; then
    moret "$@"
else
    echo "ERROR: MORET not found. Please install MORET or set the path in this script."
    exit 1
fi
