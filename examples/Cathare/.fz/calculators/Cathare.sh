#!/bin/bash

# Cathare simulator wrapper
# This script runs a simplified Cathare simulation and generates CSV output files

# If directory as input, cd into it
if [ -d "$1" ]; then
  cd "$1"
  INPUT_FILE=`ls *.dat | head -n 1`
  shift
# If $* are files, find the .dat file
elif [ $# -gt 1 ]; then
  INPUT_FILE=""
  for f in "$@"; do
    if [ `echo $f | grep -c '\.dat$'` -eq 1 ]; then
      INPUT_FILE="$f"
      break
    fi
  done
  if [ -z "$INPUT_FILE" ]; then
    echo "No .dat file found in input files. Exiting."
    exit 1
  fi
  shift $#
else
  echo "Usage: $0 <case.dat or case_directory>"
  exit 2
fi

# Source the input file to get parameters
source "$INPUT_FILE"

# Simulate Cathare calculation
# In a real scenario, this would call the actual Cathare code
echo "Running Cathare simulation with parameters:"
echo "  Pressure: $pressure Pa"
echo "  Temperature: $temperature K"
echo "  Flow rate: $flow_rate kg/s"

# Simulate some computation time
sleep 2

# Generate output CSV files for different variables
# Temperature evolution over time
cat > temperature_evolution.csv << EOF
time,T1,T2,T3
0.0,${temperature},${temperature},${temperature}
1.0,$((temperature + 10)),$((temperature + 5)),$((temperature + 2))
2.0,$((temperature + 15)),$((temperature + 8)),$((temperature + 4))
3.0,$((temperature + 18)),$((temperature + 10)),$((temperature + 5))
4.0,$((temperature + 20)),$((temperature + 11)),$((temperature + 6))
5.0,$((temperature + 21)),$((temperature + 12)),$((temperature + 6))
EOF

# Pressure evolution over time
cat > pressure_evolution.csv << EOF
time,P1,P2,P3
0.0,${pressure},${pressure},${pressure}
1.0,$((pressure + 1000)),$((pressure + 500)),$((pressure + 200))
2.0,$((pressure + 1500)),$((pressure + 800)),$((pressure + 400))
3.0,$((pressure + 1800)),$((pressure + 1000)),$((pressure + 500))
4.0,$((pressure + 2000)),$((pressure + 1100)),$((pressure + 600))
5.0,$((pressure + 2100)),$((pressure + 1200)),$((pressure + 600))
EOF

# Flow rate evolution over time  
cat > flow_evolution.csv << EOF
time,F1,F2,F3
0.0,${flow_rate},${flow_rate},${flow_rate}
1.0,$(echo "scale=2; ${flow_rate} * 1.1" | bc),$(echo "scale=2; ${flow_rate} * 1.05" | bc),$(echo "scale=2; ${flow_rate} * 1.02" | bc)
2.0,$(echo "scale=2; ${flow_rate} * 1.15" | bc),$(echo "scale=2; ${flow_rate} * 1.08" | bc),$(echo "scale=2; ${flow_rate} * 1.04" | bc)
3.0,$(echo "scale=2; ${flow_rate} * 1.18" | bc),$(echo "scale=2; ${flow_rate} * 1.10" | bc),$(echo "scale=2; ${flow_rate} * 1.05" | bc)
4.0,$(echo "scale=2; ${flow_rate} * 1.20" | bc),$(echo "scale=2; ${flow_rate} * 1.11" | bc),$(echo "scale=2; ${flow_rate} * 1.06" | bc)
5.0,$(echo "scale=2; ${flow_rate} * 1.21" | bc),$(echo "scale=2; ${flow_rate} * 1.12" | bc),$(echo "scale=2; ${flow_rate} * 1.06" | bc)
EOF

echo "Simulation completed successfully"
echo "Generated CSV files:"
echo "  - temperature_evolution.csv"
echo "  - pressure_evolution.csv"
echo "  - flow_evolution.csv"
