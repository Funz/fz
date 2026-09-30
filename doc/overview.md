# FZ Framework Overview

## What is FZ?

FZ is a parametric scientific computing framework that automates running computational experiments with different parameter combinations. It wraps simulation codes to handle:

- **Parametric studies**: Automatically generate and run all combinations of parameter values (factorial designs: a dict, Cartesian product) or explicit non-factorial designs (a DataFrame with specific cases)
- **Parallel execution**: Run multiple cases concurrently across multiple calculators with automatic load balancing
- **Smart caching**: Reuse previous results, based on input file hashes, to avoid redundant computation
- **Retry mechanism**: Automatically retry failed calculations with alternative calculators
- **Remote execution**: Run calculations on remote servers via SSH (automatic file transfer), SLURM or a Funz server
- **Result management**: Organize and parse results into structured DataFrames (DataFrame input and output, automatic type casting and variable extraction), with an automatic directory per case for inputs, outputs and logs
- **Formula evaluation**: Calculated parameters using Python or R expressions
- **Adaptive algorithms**: Iterative design of experiments with intelligent sampling strategies (`fzd`)
- **Interrupt handling**: Gracefully stop long-running calculations with Ctrl+C while preserving partial results
- **Error reporting**: Protocol-specific error classification, with descriptive messages recorded in the results
- **Cross-platform**: Linux, macOS and Windows (MSYS2/Git Bash) with configurable shell paths

## What's New in 1.0

- **fzd batch deduplication**: duplicate design points in a batch are evaluated once and results reused
- **fzd cross-iteration caching**: points from previous iterations are never re-evaluated
- **fzd re-run resume**: existing `analysis_dir` renamed with timestamp; its cache still consulted
- **Formula variable prefix fix**: configurable `varprefix` now correctly applied inside `@{...}` formulas
- **Variable defaults**: `${var~default}` syntax for default values
- **Progress callbacks**: Real-time monitoring of calculation progress
- **Old Funz syntax**: Backward compatibility with `?var` syntax

See `NEWS.md` for complete release notes.

## When to Use FZ

Use FZ when you need to:

1. **Run parametric sweeps**: Test multiple parameter combinations (e.g., temperature × pressure × concentration)
2. **Automate simulations**: Wrap existing calculation scripts without modifying them
3. **Manage computational experiments**: Track inputs, outputs, and execution metadata
4. **Scale calculations**: Execute on local machines, HPC clusters, or both
5. **Resume interrupted runs**: Gracefully handle Ctrl+C and resume using cache

## Core Functions

fz exposes six core functions, each with a CLI twin of the same name:

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

# 5. fzl - List and validate installed models / calculators
fz.fzl()

# 6. fzd - Adaptive design of experiments (optimization, sampling, inverse problems)
results = fz.fzd("input.txt", {"x": "[0;10]"}, model, "result",
                 algorithm="brent", calculators="sh://bash calc.sh")
```

See [Core functions](core-functions.md) for full signatures, and
[Installing models and algorithms](installing-models.md) to obtain ready-made wrappers
and `fzd` algorithms.

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

Each case creates a directory (named `var1=val1,var2=val2,...` by default; see `case_naming` in
[Core functions](core-functions.md)):

```
results/
├── manifest.json            # campaign manifest (fz/Python versions, model hash, calculators
│                            #   with credentials masked, hosts, dates, per-case hash)
├── ro-crate-metadata.json   # RO-Crate description (FZ_RO_CRATE=0 disables it)
├── temp=100,pressure=1/
│   ├── input.txt            # Compiled input
│   ├── output.txt           # Files written by the calculation
│   ├── out.txt, err.txt     # Captured stdout and stderr
│   ├── log.txt              # Execution metadata
│   ├── info.txt, history.txt  # Case variables (original values) and execution history
│   └── .fz_hash             # Input file checksums (for caching)
└── temp=100,pressure=2/
    └── ...
```

With `case_naming="hash"` or `"index"`, a `cases.csv` at the root maps each case directory to
its variables.

### `log.txt` - execution metadata

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

### `.fz_hash` - input file checksums

Used for `cache://` matching. Versioned format (`# fz-hash v2`): one SHA-256 per input file,
plus an optional `# code_id: ...` line naming the calculator's code identity (see
[Calculators](calculators.md), "Cache Calculator"):

```
# fz-hash v2
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
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
