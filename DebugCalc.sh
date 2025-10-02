#!/bin/bash
set -e  # Exit on any error

echo "=== DEBUG: Script starting ===" >&2
echo "PWD: $(pwd)" >&2
echo "Args: $@" >&2
echo "Input file: $1" >&2

# read input file
echo "=== DEBUG: Sourcing input file ===" >&2
source "$1"

echo "=== DEBUG: Variables loaded ===" >&2
echo "T_celsius=$T_celsius" >&2
echo "V_L=$V_L" >&2
echo "n_mol=$n_mol" >&2

echo "=== DEBUG: Starting calculation ===" >&2
sleep 1

echo "=== DEBUG: Calculating pressure ===" >&2
# Calculate pressure using ideal gas law
pressure=$(echo "scale=4; $n_mol * 8.314 * ($T_celsius + 273.15) / ($V_L / 1000)" | bc -l)
echo "Calculated pressure: $pressure" >&2

echo "=== DEBUG: Writing output ===" >&2
echo "pressure = $pressure" > output.txt

echo "=== DEBUG: Syncing files ===" >&2
sync

echo "=== DEBUG: Verifying output file ===" >&2
if [ -f output.txt ]; then
    echo "output.txt exists, content:" >&2
    cat output.txt >&2
else
    echo "ERROR: output.txt does not exist!" >&2
    exit 1
fi

echo "=== DEBUG: Script completed successfully ===" >&2
echo 'Done'
