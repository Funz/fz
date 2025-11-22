# FZ Framework Overview

## What is FZ?

FZ is a parametric scientific computing framework that automates running computational experiments with different parameter combinations. It wraps simulation codes to handle:

- **Parametric studies**: Automatically generate and run all combinations of parameter values
- **Parallel execution**: Run multiple cases concurrently
- **Smart caching**: Reuse previous results to avoid redundant computation
- **Remote execution**: Run calculations on remote servers via SSH
- **Result management**: Organize and parse results into structured DataFrames

## When to Use FZ

Use FZ when you need to:

1. **Run parametric sweeps**: Test multiple parameter combinations (e.g., temperature × pressure × concentration)
2. **Automate simulations**: Wrap existing calculation scripts without modifying them
3. **Manage computational experiments**: Track inputs, outputs, and execution metadata
4. **Scale calculations**: Execute on local machines, HPC clusters, or both
5. **Resume interrupted runs**: Gracefully handle Ctrl+C and resume using cache

## Four Core Functions

```python
import fz

# 1. fzi - Parse input files to identify variables
variables = fz.fzi("input.txt", model)
# Returns: {"temp": None, "pressure": None, "volume": None}

# 2. fzc - Compile input files by substituting variable values
fz.fzc("input.txt", {"temp": 25, "pressure": 101}, model, "output/")

# 3. fzo - Parse output files from calculations
results = fz.fzo("results/", model)
# Returns: DataFrame with parsed outputs

# 4. fzr - Run complete parametric calculations end-to-end
results = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30], "pressure": [1, 10, 100]},  # 3×3 = 9 cases
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
# Returns: DataFrame with all results
```

## Quick Example

**Input template** (`input.txt`):
```text
Temperature: $temp
Pressure: $pressure
```

**Calculation script** (`calc.sh`):
```bash
#!/bin/bash
source $1
echo "result=$((temp * pressure))" > output.txt
```

**Python script**:
```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "grep result= output.txt | cut -d= -f2"}
}

results = fz.fzr(
    "input.txt",
    {"temp": [100, 200], "pressure": [1, 2]},  # 4 cases
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)

print(results)
#    temp  pressure  result  status
# 0   100         1     100    done
# 1   100         2     200    done
# 2   200         1     200    done
# 3   200         2     400    done
```

## Key Concepts

### Cartesian Product
Lists of parameters automatically create all combinations:
```python
{"a": [1, 2], "b": [3, 4]}  # → 4 cases: (1,3), (1,4), (2,3), (2,4)
```

### Model Definition
Models define how to parse inputs and extract outputs:
```python
model = {
    "varprefix": "$",           # Variables marked with $
    "formulaprefix": "@",       # Formulas marked with @
    "delim": "{}",              # Formula delimiters
    "commentline": "#",         # Comment character
    "output": {                 # Shell commands to extract results
        "result": "grep 'Result:' output.txt | awk '{print $2}'"
    }
}
```

### Calculator Types
- `sh://bash script.sh` - Local shell execution
- `ssh://user@host/bash script.sh` - Remote SSH execution
- `cache://previous_results/` - Reuse cached results

### Parallel Execution
Multiple calculators run cases in parallel:
```python
calculators = [
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh"
]  # 3 parallel workers
```

## Typical Workflow

1. **Create input template** with variable placeholders (`$var`)
2. **Create calculation script** that reads input and produces output
3. **Define model** specifying how to parse inputs/outputs
4. **Run parametric study** with `fzr()`
5. **Analyze results** from returned DataFrame

## Output Structure

Each case creates a directory:
```
results/
├── temp=100,pressure=1/
│   ├── input.txt        # Compiled input
│   ├── output.txt       # Calculation output
│   ├── log.txt          # Execution metadata
│   └── .fz_hash         # File checksums (for caching)
└── temp=100,pressure=2/
    └── ...
```

## Common Patterns

### Pattern 1: Simple Parametric Study
```python
results = fz.fzr(
    "input.txt",
    {"param": [1, 2, 3, 4, 5]},
    model,
    calculators="sh://bash calc.sh"
)
```

### Pattern 2: Parallel Execution
```python
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=["sh://bash calc.sh"] * 4  # 4 parallel workers
)
```

### Pattern 3: Cache and Resume
```python
# First run (may be interrupted)
fz.fzr("input.txt", vars, model, "sh://bash calc.sh", "run1/")

# Resume from cache
fz.fzr(
    "input.txt",
    vars,
    model,
    ["cache://run1", "sh://bash calc.sh"],  # Try cache first
    "run2/"
)
```

### Pattern 4: Remote HPC
```python
results = fz.fzr(
    "input.txt",
    {"mesh_size": [100, 200, 400]},
    model,
    calculators="ssh://user@cluster.edu/bash /path/to/submit.sh"
)
```
