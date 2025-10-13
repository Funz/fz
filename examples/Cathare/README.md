# Cathare Example

This example demonstrates how to use FZ with a simulated nuclear reactor thermal-hydraulics code (Cathare-like). It showcases the pattern of:
1. Running a simulation that generates CSV output files
2. Parsing those CSV files using pandas to extract time-series results

## Structure

```
Cathare/
├── cathare_input.dat          # Input file with parametric variables
├── .fz/
│   ├── calculators/
│   │   ├── Cathare.sh         # Shell script that runs simulation and generates CSVs
│   │   └── Localhost_Cathare.json  # Calculator alias configuration
│   └── models/
│       └── Cathare.json       # Model definition with pandas-based CSV parsing
└── README.md
```

## Key Features

### Cathare.sh
- Accepts a `.dat` input file with parameters (pressure, temperature, flow_rate)
- Simulates a thermal-hydraulics calculation
- Generates three CSV files:
  - `temperature_evolution.csv` - Temperature at different measurement points over time
  - `pressure_evolution.csv` - Pressure at different measurement points over time
  - `flow_evolution.csv` - Flow rate at different measurement points over time

### Cathare.json
- Uses pandas to parse the generated CSV files
- Converts CSV data to JSON dictionaries for easy manipulation
- Demonstrates the pattern: **compute in shell script, parse with pandas**

## Usage

### Basic variable extraction

```python
import fz

# Find variables in input file
variables = fz.fzi('cathare_input.dat', 'Cathare')
print(variables)  # {'pressure': None, 'temperature': None, 'flow_rate': None}
```

### Single case calculation

```python
import fz

results = fz.fzr(
    'cathare_input.dat',
    {
        'pressure': 100000,    # Pa
        'temperature': 300,    # K
        'flow_rate': 10        # kg/s
    },
    'Cathare',
    calculators='sh://bash .fz/calculators/Cathare.sh',
    results_dir='results'
)

print(results)
# Returns DataFrame with input parameters and output time series
```

### Parametric study

```python
import fz

results = fz.fzr(
    'cathare_input.dat',
    {
        'pressure': [100000, 150000, 200000],  # 3 values
        'temperature': [300, 350],              # 2 values
        'flow_rate': 10                         # 1 value
    },
    'Cathare',
    calculators='sh://bash .fz/calculators/Cathare.sh',
    results_dir='results'
)

print(results.shape)  # (6, 11) - 6 cases (3×2×1)
# Access specific output
print(results['temperature_evolution'].iloc[0])
```

### Using calculator alias

```python
import fz

# Uses configuration from .fz/calculators/Localhost_Cathare.json
results = fz.fzr(
    'cathare_input.dat',
    {'pressure': 100000, 'temperature': 300, 'flow_rate': 10},
    'Cathare',
    calculators='*',
    results_dir='results'
)
```

### Parse existing results

```python
import fz

# Parse output from a previous run without re-running calculation
results = fz.fzo('results', 'Cathare')
print(results)
```

## Design Pattern

This example follows a clean separation of concerns:

1. **Computation** (Cathare.sh): 
   - Runs the actual simulation
   - Generates CSV files with raw results
   - Pure shell script, no complex Python embedding

2. **Parsing** (Cathare.json):
   - Uses pandas one-liners to parse CSV files
   - Converts tabular data to structured JSON
   - Easy to maintain and understand

This pattern is recommended for integrating any simulation code that can generate CSV outputs.

## Comparison with Telemac Example

The Cathare example is similar to the Telemac example but with a simpler structure:
- **Telemac**: Embeds Python code in the shell script for post-processing
- **Cathare**: Keeps shell script simple, uses pandas for parsing in model definition

Both approaches work, but Cathare's approach is cleaner for cases where CSV output is sufficient.
