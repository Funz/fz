#!/bin/bash
# Perfect gas pressure calculation
# P = nRT/V
# R = 8.314 J/(mol·K)
echo 'Starting calculation...'
# Get temperature from input file if possible, or use default
T_K=293  # Default to 20°C = 293K
V=1      # 1 L
n=1      # 1 mol
R=8314   # 8.314 J/(mol·K) * 1000 for L·Pa units
P=$((n * R * T_K / V))
echo "pressure = $P Pa" > output.txt
echo 'Calculation completed'
