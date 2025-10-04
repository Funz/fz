# FZ - Parametric Scientific Computing Framework

[![CI](https://github.com/Funz/fz/workflows/CI/badge.svg)](https://github.com/Funz/fz/actions/workflows/ci.yml)
<!--
[![Python Version](https://img.shields.io/pypi/pyversions/funz.svg)](https://pypi.org/project/funz/)
-->
[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)
[![Version](https://img.shields.io/badge/version-0.8.0-blue.svg)](https://github.com/Funz/fz/releases)

A powerful Python package for parametric simulations and computational experiments. FZ wraps your simulation codes to automatically run parametric studies, manage input/output files, handle parallel execution, and collect results in structured DataFrames.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Functions](#core-functions)
- [Model Definition](#model-definition)
- [Calculator Types](#calculator-types)
- [Advanced Features](#advanced-features)
- [Complete Examples](#complete-examples)
- [Configuration](#configuration)
- [Interrupt Handling](#interrupt-handling)
- [Development](#development)

## Features

### Core Capabilities

- **🔄 Parametric Studies**: Automatically generate and run all combinations of parameter values (Cartesian product)
- **⚡ Parallel Execution**: Run multiple cases concurrently across multiple calculators with automatic load balancing
- **💾 Smart Caching**: Reuse previous calculation results based on input file hashes to avoid redundant computations
- **🔁 Retry Mechanism**: Automatically retry failed calculations with alternative calculators
- **🌐 Remote Execution**: Execute calculations on remote servers via SSH with automatic file transfer
- **📊 DataFrame Output**: Results returned as pandas DataFrames with automatic type casting and variable extraction
- **🛑 Interrupt Handling**: Gracefully stop long-running calculations with Ctrl+C while preserving partial results
- **🔍 Formula Evaluation**: Support for calculated parameters using Python or R expressions
- **📁 Directory Management**: Automatic organization of inputs, outputs, and logs for each case

### Four Core Functions

1. **`fzi`** - Parse **I**nput files to identify variables
2. **`fzc`** - **C**ompile input files by substituting variable values
3. **`fzo`** - Read and parse **O**utput files from calculations
4. **`fzr`** - **R**un complete parametric calculations end-to-end

## Installation

### From Source

```bash
git clone https://github.com/Funz/fz.git
cd fz
pip install -e .
```

### Dependencies

```bash
# Optional dependencies:

# for SSH support
pip install paramiko

# for DataFrame support
pip install pandas
```

## Quick Start

Here's a complete example for a simple parametric study:

### 1. Create an Input Template

Create `input.txt`:
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@($T_celsius + 273.15)
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@(L_to_m3($V_L))
```

### 2. Create a Calculation Script

Create `PerfectGazPressure.sh`:
```bash
#!/bin/bash

# read input file
source $1

sleep 5 # simulate a calculation time

echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt

echo 'Done'
```

Make it executable:
```bash
chmod +x PerfectGazPressure.sh
```

### 3. Run Parametric Study

Create `run_study.py`:
```python
import fz

# Define the model
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

# Define parameter values
input_variables = {
    "T_celsius": [10, 20, 30, 40],  # 4 temperatures
    "V_L": [1, 2, 5],                # 3 volumes
    "n_mol": 1.0                     # fixed amount
}

# Run all combinations (4 × 3 = 12 cases)
results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="results"
)

# Display results
print(results)
print(f"\nCompleted {len(results)} calculations")
```

Run it:
```bash
python run_study.py
```

Expected output:
```
   T_celsius  V_L  n_mol     pressure status calculator       error command
0         10  1.0    1.0  235358.1200   done     sh://        None    bash...
1         10  2.0    1.0  117679.0600   done     sh://        None    bash...
2         10  5.0    1.0   47071.6240   done     sh://        None    bash...
3         20  1.0    1.0  243730.2200   done     sh://        None    bash...
...

Completed 12 calculations
```

## Core Functions

### fzi - Parse Input Variables

Identify all variables in an input file or directory:

```python
import fz

model = {
    "varprefix": "$",
    "delim": "()"
}

# Parse single file
variables = fz.fzi("input.txt", model)
# Returns: {'T_celsius': None, 'V_L': None, 'n_mol': None}

# Parse directory (scans all files)
variables = fz.fzi("input_dir/", model)
```

**Returns**: Dictionary with variable names as keys (values are None)

### fzc - Compile Input Files

Substitute variable values and evaluate formulas:

```python
import fz

model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#"
}

input_variables = {
    "T_celsius": 25,
    "V_L": 10,
    "n_mol": 2
}

# Compile single file
fz.fzc(
    "input.txt",
    input_variables,
    model,
    output_dir="compiled"
)

# Compile with multiple value sets (creates subdirectories)
fz.fzc(
    "input.txt",
    {
        "T_celsius": [20, 30],  # 2 values
        "V_L": [5, 10],         # 2 values
        "n_mol": 1              # fixed
    },
    model,
    output_dir="compiled_grid"
)
# Creates: compiled_grid/T_celsius=20,V_L=5/, T_celsius=20,V_L=10/, etc.
```

**Parameters**:
- `input_path`: Path to input file or directory
- `input_variables`: Dictionary of variable values (scalar or list)
- `model`: Model definition (dict or alias name)
- `engine`: Expression evaluator (`"python"` or `"R"`, default: `"python"`)
- `output_dir`: Output directory path

### fzo - Read Output Files

Parse calculation results from output directory:

```python
import fz

model = {
    "output": {
        "pressure": "grep 'Pressure:' output.txt | awk '{print $2}'",
        "temperature": "grep 'Temperature:' output.txt | awk '{print $2}'"
    }
}

# Read from single directory
output = fz.fzo("results/case1", model)
# Returns: DataFrame with 1 row

# Read from directory with subdirectories
output = fz.fzo("results", model)
# Returns: DataFrame with 1 row per subdirectory
```

**Automatic Path Parsing**: If subdirectory names follow the pattern `key1=val1,key2=val2,...`, variables are automatically extracted as columns:

```python
# Directory structure:
# results/
#   ├── T_celsius=20,V_L=1/output.txt
#   ├── T_celsius=20,V_L=2/output.txt
#   └── T_celsius=30,V_L=1/output.txt

output = fz.fzo("results", model)
print(output)
#                          path  pressure  T_celsius  V_L
# 0  T_celsius=20,V_L=1  2437.30       20.0  1.0
# 1  T_celsius=20,V_L=2  1218.65       20.0  2.0
# 2  T_celsius=30,V_L=1  2520.74       30.0  1.0
```

### fzr - Run Parametric Calculations

Execute complete parametric study with automatic parallelization:

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "result": "cat output.txt"
    }
}

results = fz.fzr(
    input_path="input.txt",
    input_variables={
        "temperature": [100, 200, 300],
        "pressure": [1, 10, 100],
        "concentration": 0.5
    },
    model=model,
    calculators=["sh://bash calculate.sh"],
    results_dir="results"
)

# Results DataFrame includes:
# - All variable columns
# - All output columns
# - Metadata: status, calculator, error, command
print(results)
```

**Parameters**:
- `input_path`: Input file or directory path
- `input_variables`: Variable values (creates Cartesian product of lists)
- `model`: Model definition (dict or alias)
- `engine`: Expression evaluator (default: `"python"`)
- `calculators`: Calculator URI(s) - string or list
- `results_dir`: Results directory path

**Returns**: pandas DataFrame with all results

## Model Definition

A model defines how to parse inputs and extract outputs:

```python
model = {
    # Input parsing
    "varprefix": "$",           # Variable marker (e.g., $temp)
    "formulaprefix": "@",       # Formula marker (e.g., @pressure)
    "delim": "()",              # Formula delimiters
    "commentline": "#",         # Comment character

    # Output extraction (shell commands)
    "output": {
        "pressure": "grep 'P =' out.txt | awk '{print $3}'",
        "temperature": "cat temp.txt",
        "energy": "python extract.py"
    },

    # Optional: model identifier
    "id": "perfectgas"
}
```

### Model Aliases

Store reusable models in `.fz/models/`:

**`.fz/models/perfectgas.json`**:
```json
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    },
    "id": "perfectgas"
}
```

Use by name:
```python
results = fz.fzr("input.txt", input_variables, "perfectgas")
```

### Formula Evaluation

Formulas in input files are evaluated during compilation:

```text
# Input template with formulas
Temperature: $T_celsius C
Volume: $V_L L

# Context (available in all formulas)
#@R = 8.314
#@def celsius_to_kelvin(t):
#@    return t + 273.15

# Calculated value
#@T_kelvin = celsius_to_kelvin($T_celsius)
#@pressure = $n_mol * R * T_kelvin / ($V_L / 1000)

Result: @(pressure) Pa
```

**Features**:
- Python or R expression evaluation
- Multi-line function definitions
- Variable substitution in formulas
- Nested formula evaluation

## Calculator Types

### Local Shell Execution

Execute calculations locally:

```python
# Basic shell command
calculators = "sh://bash script.sh"

# With multiple arguments
calculators = "sh://python calculate.py --verbose"

# Multiple calculators (tries in order, parallel execution)
calculators = [
    "sh://bash method1.sh",
    "sh://bash method2.sh",
    "sh://python method3.py"
]
```

**How it works**:
1. Input files copied to temporary directory
2. Command executed in that directory with input files as arguments
3. Outputs parsed from result directory
4. Temporary files cleaned up (preserved in DEBUG mode)

### SSH Remote Execution

Execute calculations on remote servers:

```python
# SSH with password
calculators = "ssh://user:password@server.com:22/bash /absolutepath/to/calc.sh"

# SSH with key-based auth (recommended)
calculators = "ssh://user@server.com/bash /absolutepath/to/calc.sh"

# SSH with custom port
calculators = "ssh://user@server.com:2222/bash /absolutepath/to/calc.sh"
```

**Features**:
- Automatic file transfer (SFTP)
- Remote execution with timeout
- Result retrieval
- SSH key-based or password authentication
- Host key verification

**Security**:
- Interactive host key acceptance
- Warning for password-based auth
- Environment variable for auto-accepting host keys: `FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1`

### Cache Calculator

Reuse previous calculation results:

```python
# Check single cache directory
calculators = "cache://previous_results"

# Check multiple cache locations
calculators = [
    "cache://run1",
    "cache://run2/results",
    "sh://bash calculate.sh"  # Fallback to actual calculation
]

# Use glob patterns
calculators = "cache://archive/*/results"
```

**Cache Matching**:
- Based on MD5 hash of input files (`.fz_hash`)
- Validates outputs are not None
- Falls through to next calculator on miss
- No recalculation if cache hit

### Calculator Aliases

Store calculator configurations in `.fz/calculators/`:

**`.fz/calculators/cluster.json`**:
```json
{
    "uri": "ssh://user@cluster.university.edu",
    "models": {
        "perfectgas": "bash /home/user/codes/perfectgas/run.sh",
        "navier-stokes": "bash /home/user/codes/cfd/run.sh"
    }
}
```

Use by name:
```python
results = fz.fzr("input.txt", input_variables, "perfectgas", calculators="cluster")
```

## Advanced Features

### Parallel Execution

FZ automatically parallelizes when you have multiple cases and calculators:

```python
# Sequential: 1 calculator, 10 cases → runs one at a time
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators="sh://bash calc.sh"
)

# Parallel: 3 calculators, 10 cases → 3 concurrent
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ]
)

# Control parallelism with environment variable
import os
os.environ['FZ_MAX_WORKERS'] = '4'

# Or use duplicate calculator URIs
calculators = ["sh://bash calc.sh"] * 4  # 4 parallel workers
```

**Load Balancing**:
- Round-robin distribution of cases to calculators
- Thread-safe calculator locking
- Automatic retry on failures
- Progress tracking with ETA

### Retry Mechanism

Automatic retry on calculation failures:

```python
import os
os.environ['FZ_MAX_RETRIES'] = '3'  # Try each case up to 3 times

results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators=[
        "sh://unreliable_calc.sh",  # Might fail
        "sh://backup_calc.sh"        # Backup method
    ]
)
```

**Retry Strategy**:
1. Try first available calculator
2. On failure, try next calculator
3. Repeat up to `FZ_MAX_RETRIES` times
4. Report all attempts in logs

### Caching Strategy

Intelligent result reuse:

```python
# First run
results1 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30]},
    model,
    calculators="sh://expensive_calc.sh",
    results_dir="run1"
)

# Add more cases - reuse previous results
results2 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30, 40, 50]},  # 2 new cases
    model,
    calculators=[
        "cache://run1",              # Check cache first
        "sh://expensive_calc.sh"     # Only run new cases
    ],
    results_dir="run2"
)
# Only runs calculations for temp=40 and temp=50
```

### Output Type Casting

Automatic type conversion:

```python
model = {
    "output": {
        "scalar_int": "echo 42",
        "scalar_float": "echo 3.14159",
        "array": "echo '[1, 2, 3, 4, 5]'",
        "single_array": "echo '[42]'",  # → 42 (simplified)
        "json_object": "echo '{\"key\": \"value\"}'",
        "string": "echo 'hello world'"
    }
}

results = fz.fzo("output_dir", model)
# Values automatically cast to int, float, list, dict, or str
```

**Casting Rules**:
1. Try JSON parsing
2. Try Python literal evaluation
3. Try numeric conversion (int/float)
4. Keep as string
5. Single-element arrays → scalar

## Complete Examples

### Example 1: Perfect Gas Pressure Study

**Input file (`input.txt`)**:
```text
# input file for Perfect Gaz Pressure, with variables n_mol, T_celsius, V_L
n_mol=$n_mol
T_kelvin=@($T_celsius + 273.15)
#@ def L_to_m3(L):
#@     return(L / 1000)
V_m3=@(L_to_m3($V_L))
```

**Calculation script (`PerfectGazPressure.sh`)**:
```bash
#!/bin/bash

# read input file
source $1

sleep 5 # simulate a calculation time

echo 'pressure = '`echo "scale=4;$n_mol*8.314*$T_kelvin/$V_m3" | bc` > output.txt

echo 'Done'
```

**Python script (`run_perfectgas.py`)**:
```python
import fz
import matplotlib.pyplot as plt

# Define model
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "()",
    "commentline": "#",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

# Parametric study
results = fz.fzr(
    "input.txt",
    {
        "n_mol": [1, 2, 3],
        "T_celsius": [10, 20, 30],
        "V_L": [5, 10]
    },
    model,
    calculators="sh://bash PerfectGazPressure.sh",
    results_dir="perfectgas_results"
)

print(results)

# Plot results: pressure vs temperature for different volumes
for volume in results['V_L'].unique():
    for n in results['n_mol'].unique():
        data = results[(results['V_L'] == volume) & (results['n_mol'] == n)]
        plt.plot(data['T_celsius'], data['pressure'],
                 marker='o', label=f'n={n} mol, V={volume} L')

plt.xlabel('Temperature (°C)')
plt.ylabel('Pressure (Pa)')
plt.title('Ideal Gas: Pressure vs Temperature')
plt.legend()
plt.grid(True)
plt.savefig('perfectgas_results.png')
print("Plot saved to perfectgas_results.png")
```

### Example 2: Remote HPC Calculation

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "energy": "grep 'Total Energy' output.log | awk '{print $4}'",
        "time": "grep 'CPU time' output.log | awk '{print $4}'"
    }
}

# Run on HPC cluster
results = fz.fzr(
    "simulation_input/",
    {
        "mesh_size": [100, 200, 400, 800],
        "timestep": [0.001, 0.01, 0.1],
        "iterations": 1000
    },
    model,
    calculators=[
        "cache://previous_runs/*",  # Check cache first
        "ssh://user@hpc.university.edu/sbatch /path/to/submit.sh"
    ],
    results_dir="hpc_results"
)

# Analyze convergence
import pandas as pd
summary = results.groupby('mesh_size').agg({
    'energy': ['mean', 'std'],
    'time': 'sum'
})
print(summary)
```

### Example 3: Multi-Calculator with Failover

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat result.txt"}
}

results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://previous_results",           # 1. Check cache
        "sh://bash fast_but_unstable.sh",    # 2. Try fast method
        "sh://bash robust_method.sh",        # 3. Fallback to robust
        "ssh://user@server/bash remote.sh"   # 4. Last resort: remote
    ],
    results_dir="results"
)

# Check which calculator was used for each case
print(results[['param', 'calculator', 'status']].head(10))
```

## Configuration

### Environment Variables

```bash
# Logging level (DEBUG, INFO, WARNING, ERROR)
export FZ_LOG_LEVEL=INFO

# Maximum retry attempts per case
export FZ_MAX_RETRIES=5

# Thread pool size for parallel execution
export FZ_MAX_WORKERS=8

# SSH keepalive interval (seconds)
export FZ_SSH_KEEPALIVE=300

# Auto-accept SSH host keys (use with caution!)
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=0

# Default formula interpreter
export FZ_INTERPRETER=python
```

### Python Configuration

```python
from fz import get_config

# Get current config
config = get_config()
print(f"Max retries: {config.max_retries}")
print(f"Max workers: {config.max_workers}")

# Modify configuration
config.max_retries = 10
config.max_workers = 4
```

### Directory Structure

FZ uses the following directory structure:

```
your_project/
├── input.txt                 # Your input template
├── calculate.sh              # Your calculation script
├── run_study.py             # Your Python script
├── .fz/                     # FZ configuration (optional)
│   ├── models/              # Model aliases
│   │   └── mymodel.json
│   ├── calculators/         # Calculator aliases
│   │   └── mycluster.json
│   └── tmp/                 # Temporary files (auto-created)
│       └── fz_temp_*/       # Per-run temp directories
└── results/                 # Results directory
    ├── case1/               # One directory per case
    │   ├── input.txt        # Compiled input
    │   ├── output.txt       # Calculation output
    │   ├── log.txt          # Execution metadata
    │   ├── out.txt          # Standard output
    │   ├── err.txt          # Standard error
    │   └── .fz_hash         # File checksums (for caching)
    └── case2/
        └── ...
```

## Interrupt Handling

FZ supports graceful interrupt handling for long-running calculations:

### How to Interrupt

Press **Ctrl+C** during execution:

```bash
python run_study.py
# ... calculations running ...
# Press Ctrl+C
⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
⚠️  Press Ctrl+C again to force quit (not recommended)
```

### What Happens

1. **First Ctrl+C**:
   - Currently running calculations complete
   - No new calculations start
   - Partial results are saved
   - Resources are cleaned up
   - Signal handlers restored

2. **Second Ctrl+C** (not recommended):
   - Immediate termination
   - May leave resources in inconsistent state

### Resuming After Interrupt

Use caching to resume from where you left off:

```python
# First run (interrupted after 50/100 cases)
results1 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
print(f"Completed {len(results1)} cases before interrupt")

# Resume using cache
results2 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://results",      # Reuse completed cases
        "sh://bash calc.sh"     # Run remaining cases
    ],
    results_dir="results_resumed"
)
print(f"Total completed: {len(results2)} cases")
```

### Example with Interrupt Handling

```python
import fz
import signal
import sys

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

def main():
    try:
        results = fz.fzr(
            "input.txt",
            {"param": list(range(1000))},  # Many cases
            model,
            calculators="sh://bash slow_calculation.sh",
            results_dir="results"
        )

        print(f"\n✅ Completed {len(results)} calculations")
        return results

    except KeyboardInterrupt:
        # This should rarely happen (graceful shutdown handles it)
        print("\n❌ Forcefully terminated")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## Output File Structure

Each case creates a directory with complete execution metadata:

### `log.txt` - Execution Metadata
```
Command: bash calculate.sh input.txt
Exit code: 0
Time start: 2024-03-15T10:30:45.123456
Time end: 2024-03-15T10:32:12.654321
Execution time: 87.531 seconds
User: john_doe
Hostname: compute-01
Operating system: Linux
Platform: Linux-5.15.0-x86_64
Working directory: /tmp/fz_temp_abc123/case1
Original directory: /home/john/project
```

### `.fz_hash` - Input File Checksums
```
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

Used for cache matching.

## Development

### Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_examples_perfectgaz.py -v

# Run with debug output
FZ_LOG_LEVEL=DEBUG python -m pytest tests/test_parallel.py -v

# Run tests matching pattern
python -m pytest tests/ -k "parallel" -v

# Test interrupt handling
python -m pytest tests/test_interrupt_handling.py -v

# Run examples
python example_usage.py
python example_interrupt.py  # Interactive interrupt demo
```

### Project Structure

```
fz/
├── fz/                          # Main package
│   ├── __init__.py              # Public API exports
│   ├── core.py                  # Core functions (fzi, fzc, fzo, fzr)
│   ├── engine.py                # Variable parsing, formula evaluation
│   ├── runners.py               # Calculation execution (sh, ssh)
│   ├── helpers.py               # Parallel execution, retry logic
│   ├── io.py                    # File I/O, caching, hashing
│   ├── logging.py               # Logging configuration
│   └── config.py                # Configuration management
├── tests/                       # Test suite
│   ├── test_parallel.py         # Parallel execution tests
│   ├── test_interrupt_handling.py  # Interrupt handling tests
│   ├── test_examples_*.py       # Example-based tests
│   └── ...
├── README.md                    # This file
└── setup.py                     # Package configuration
```

### Testing Your Own Models

Create a test following this pattern:

```python
import fz
import tempfile
from pathlib import Path

def test_my_model():
    # Create input
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("Parameter: $param\n")

        # Create calculator script
        calc_script = Path(tmpdir) / "calc.sh"
        calc_script.write_text("""#!/bin/bash
source $1
echo "result=$param" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "output": {
                "result": "grep 'result=' output.txt | cut -d= -f2"
            }
        }

        # Run test
        results = fz.fzr(
            str(input_file),
            {"param": [1, 2, 3]},
            model,
            calculators=f"sh://bash {calc_script}",
            results_dir=str(Path(tmpdir) / "results")
        )

        # Verify
        assert len(results) == 3
        assert list(results['result']) == [1, 2, 3]
        assert all(results['status'] == 'done')

        print("✅ Test passed!")

if __name__ == "__main__":
    test_my_model()
```

## Troubleshooting

### Common Issues

**Problem**: Calculations fail with "command not found"
```bash
# Solution: Use absolute paths in calculator URIs
calculators = "sh://bash /full/path/to/script.sh"
```

**Problem**: SSH calculations hang
```bash
# Solution: Increase timeout or check SSH connectivity
calculators = "ssh://user@host/bash script.sh"
# Test manually: ssh user@host "bash script.sh"
```

**Problem**: Cache not working
```bash
# Solution: Check .fz_hash files exist in cache directories
# Enable debug logging to see cache matching process
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'
```

**Problem**: Out of memory with many parallel cases
```bash
# Solution: Limit parallel workers
export FZ_MAX_WORKERS=2
```

### Debug Mode

Enable detailed logging:

```python
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

results = fz.fzr(...)  # Will show detailed execution logs
```

Debug output includes:
- Calculator selection and locking
- File operations
- Command execution
- Cache matching
- Thread pool management
- Temporary directory preservation

## Performance Tips

1. **Use caching**: Reuse previous results when possible
2. **Limit parallelism**: Don't exceed your CPU/memory limits
3. **Optimize calculators**: Fast calculators first in the list
4. **Batch similar cases**: Group cases that use the same calculator
5. **Use SSH keepalive**: For long-running remote calculations
6. **Clean old results**: Remove old result directories to save disk space

## License

BSD 3-Clause License. See `LICENSE` file for details.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## Citation

If you use FZ in your research, please cite:

```bibtex
@software{fz,
  title = {FZ: Parametric Scientific Computing Framework},
  designers = {[Yann Richet]},
  authors = {[Claude Sonnet, Yann Richet]},
  year = {2025},
  url = {https://github.com/Funz/fz}
}
```

## Support

- **Issues**: https://github.com/Funz/fz/issues
- **Documentation**: https://fz.github.io
- **Examples**: See `tests/test_examples_*.py` for working examples
