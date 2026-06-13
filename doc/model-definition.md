# FZ Model Definition

## What is a Model?

A model defines how FZ parses input files and extracts output results. It specifies:

- **Input parsing rules**: How to identify variables and formulas
- **Output extraction**: Shell commands to extract results from output files
- **Interpreter**: Which language to use for formula evaluation (Python or R)

## Basic Model Structure

```python
model = {
    # Input parsing
    "varprefix": "$",           # Variable marker (e.g., $temp)
    "formulaprefix": "@",       # Formula marker (e.g., @pressure)
    "delim": "{}",              # Formula delimiters
    "commentline": "#",         # Comment character

    # Optional: formula interpreter
    "interpreter": "python",    # "python" (default) or "R"

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

## Model Fields

### varprefix (required for fzi, fzc, fzr)

Prefix that marks variables in input files.

**Common values**:
- `"$"` - Shell-style: `$variable`
- `"@"` - At-style: `@variable`
- `"%"` - Percent-style: `%variable`

**Example**:
```python
model = {"varprefix": "$"}
# Matches: $temp, $pressure, ${volume}
```

### delim (optional)

Delimiters for variables and formulas. Empty string means no delimiters required.

**Common values**:
- `"{}"` - Curly braces: `${var}`, `@{formula}`
- `"()"` - Parentheses: `$(var)`, `@(formula)`
- `"[]"` - Square brackets: `$[var]`, `@[formula]`
- `""` - No delimiters: `$var`, `@formula`

**When to use delimiters**:
```python
# Without delimiters - ambiguous
content = "$temp_celsius"  # Is variable "temp" or "temp_celsius"?

# With delimiters - clear
content = "${temp}_celsius"  # Variable is "temp", followed by "_celsius"
```

### formulaprefix (required for formulas)

Prefix that marks formulas in input files.

**Common values**:
- `"@"` - At-style: `@{expression}`
- `"="` - Equals-style: `={expression}`
- `"$"` - Can be same as varprefix if using delimiters

**Example**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}"
}
# Variables: ${var}
# Formulas: @{expression}
```

### commentline (required for formulas)

Character that marks comment lines. Context lines use `commentline + formulaprefix`.

**Example**:
```python
model = {"commentline": "#", "formulaprefix": "@"}

# In input file:
# #@ import math          # Context line (evaluated)
# # This is a comment     # Regular comment (ignored)
```

### interpreter (optional)

Which language to use for formula evaluation.

**Values**:
- `"python"` - Python interpreter (default)
- `"R"` - R interpreter (requires rpy2 and R installation)

**Example**:
```python
# Python formulas
model = {
    "interpreter": "python",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}

# R formulas
model = {
    "interpreter": "R",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}
```

### output (required for fzo, fzr)

Dictionary mapping output variable names to shell commands that extract values.

**Example**:
```python
model = {
    "output": {
        "pressure": "grep 'Pressure:' output.txt | awk '{print $2}'",
        "max_temp": "python -c \"import numpy as np; print(np.max(np.loadtxt('temps.dat')))\"",
        "converged": "grep -q 'CONVERGED' log.txt && echo 1 || echo 0",
        "result_array": "cat results.json"
    }
}
```

**Command execution**:
- Commands run in the result directory
- Standard shell commands: `grep`, `awk`, `sed`, `cat`, `head`, `tail`
- Custom scripts: `python extract.py`, `bash parse.sh`
- Pipes and redirection supported: `grep ... | awk ...`

### id (optional)

Unique identifier for the model, useful for documentation and logging.

```python
model = {"id": "perfectgas", ...}
```

## Complete Examples

### Example 1: Perfect Gas Model

```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    },
    "id": "perfectgas"
}
```

**Input template**:
```text
# Perfect Gas Law
n_mol=$n_mol
T_celsius=$T_celsius
V_L=$V_L

#@ def L_to_m3(L):
#@     return L / 1000

T_kelvin=@{$T_celsius + 273.15}
V_m3=@{L_to_m3($V_L)}
```

### Example 2: CFD Simulation Model

```python
model = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        "max_velocity": "grep 'Max velocity' log.txt | tail -1 | awk '{print $3}'",
        "drag_coefficient": "python extract_drag.py output.vtu",
        "residuals": "grep 'Final residual' log.txt | awk '{print $4}'",
        "cpu_time": "grep 'CPU time' log.txt | awk '{print $4}'",
        "converged": "grep -q 'CONVERGED' log.txt && echo 1 || echo 0"
    },
    "id": "cfd_simulation"
}
```

### Example 3: Machine Learning Model

```python
model = {
    "varprefix": "%",
    "delim": "()",
    "output": {
        "accuracy": "python -c \"import json; print(json.load(open('metrics.json'))['accuracy'])\"",
        "loss": "python -c \"import json; print(json.load(open('metrics.json'))['loss'])\"",
        "precision": "jq '.precision' metrics.json",
        "recall": "jq '.recall' metrics.json"
    },
    "id": "ml_experiment"
}
```

**Input template**:
```text
learning_rate=%(lr)
batch_size=%(batch_size)
epochs=%(epochs)
optimizer=%(optimizer)
```

### Example 4: Statistical Analysis with R

```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "R",
    "output": {
        "mean": "Rscript -e 'cat(mean(read.table(\"output.txt\")$V1))'",
        "median": "Rscript -e 'cat(median(read.table(\"output.txt\")$V1))'",
        "sd": "Rscript -e 'cat(sd(read.table(\"output.txt\")$V1))'"
    },
    "id": "statistical_analysis"
}
```

**Input template**:
```text
sample_size=$n
population_mean=$mu
population_sd=$sigma

#@ set.seed(42)
#@ samples <- rnorm($n, mean=$mu, sd=$sigma)

n_samples=@{length(samples)}
sample_mean=@{mean(samples)}
sample_sd=@{sd(samples)}
```

## Model Aliases

Store reusable models in `.fz/models/` directory as JSON files.

### Creating a Model Alias

**`.fz/models/perfectgas.json`**:
```json
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python",
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    },
    "id": "perfectgas"
}
```

### Using Model Aliases

```python
import fz

# Use model by name instead of defining dict
results = fz.fzr(
    "input.txt",
    {"T_celsius": [10, 20, 30], "V_L": [1, 2], "n_mol": 1},
    "perfectgas",  # Model alias
    calculators="sh://bash PerfectGazPressure.sh"
)
```

### Model Search Path

FZ searches for models in:
1. Current directory: `./.fz/models/`
2. Home directory: `~/.fz/models/`

**Organization**:
```
.fz/models/
├── perfectgas.json
├── cfd_simulation.json
├── molecular_dynamics.json
└── optimization.json
```

## Advanced Output Extraction

### Multi-line Commands

Use Python scripts or shell heredocs for complex extraction:

```python
model = {
    "output": {
        "results": """python3 << 'EOF'
import numpy as np
import json

data = np.loadtxt('output.dat')
results = {
    'mean': float(np.mean(data)),
    'std': float(np.std(data)),
    'max': float(np.max(data))
}
print(json.dumps(results))
EOF"""
    }
}
```

### Extracting Arrays

```python
model = {
    "output": {
        "temperature_profile": "cat temperatures.txt",  # Returns array
        "pressure_values": "jq '.pressures' results.json"  # JSON array
    }
}
```

**Output**:
```python
# Result DataFrame will have:
# temperature_profile: [300, 310, 320, 330]  # List type
# pressure_values: [101, 102, 103]           # List type
```

### Conditional Extraction

```python
model = {
    "output": {
        "best_result": "if [ -f best.txt ]; then cat best.txt; else echo 'N/A'; fi",
        "error_count": "grep -c 'ERROR' log.txt || echo 0"
    }
}
```

## Model Validation

### Minimal Model for fzi

```python
# Just need variable parsing
model = {
    "varprefix": "$"
}

variables = fz.fzi("input.txt", model)
```

### Minimal Model for fzc

```python
# Need variable parsing and optionally formulas
model = {
    "varprefix": "$",
    "formulaprefix": "@",  # If using formulas
    "delim": "{}",         # If using formulas
    "commentline": "#"     # If using formulas
}

fz.fzc("input.txt", variables, model, "output/")
```

### Minimal Model for fzo

```python
# Just need output extraction
model = {
    "output": {
        "result": "cat output.txt"
    }
}

results = fz.fzo("results/", model)
```

### Complete Model for fzr

```python
# Need everything
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python",
    "output": {
        "result": "cat output.txt"
    }
}

results = fz.fzr("input.txt", variables, model, calculators)
```

## Best Practices

### 1. Use Delimiters

Always use delimiters for clarity and to avoid ambiguity:

```python
# Good
model = {"varprefix": "$", "delim": "{}"}
content = "Temperature: ${temp} C"

# Risky
model = {"varprefix": "$", "delim": ""}
content = "Temperature: $temp C"  # Works, but ${temp}C would fail
```

### 2. Robust Output Commands

Handle missing files and errors gracefully:

```python
model = {
    "output": {
        # Bad: fails if file doesn't exist
        "result": "cat output.txt",

        # Good: provides default value
        "result": "cat output.txt 2>/dev/null || echo 'N/A'"
    }
}
```

### 3. Type-Safe Output

Extract numeric values explicitly:

```python
model = {
    "output": {
        # Returns string (may not cast correctly)
        "pressure": "grep Pressure output.txt",

        # Returns number (explicit extraction)
        "pressure": "grep Pressure output.txt | awk '{print $2}'"
    }
}
```

### 4. Consistent Naming

Use clear, descriptive names:

```python
# Good
model = {
    "output": {
        "max_velocity": "...",
        "mean_pressure": "...",
        "total_energy": "..."
    }
}

# Confusing
model = {
    "output": {
        "v": "...",
        "p": "...",
        "e": "..."
    }
}
```

### 5. Document Complex Models

```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python",
    "output": {
        # Extract maximum velocity from VTU file using ParaView's pvpython
        "max_velocity": "pvpython extract_velocity.py output.vtu",

        # Compute drag coefficient from force data
        "drag_coefficient": "python -c \"import numpy as np; forces=np.loadtxt('forces.dat'); print(np.mean(forces[:,0]))\"",

        # Check convergence status
        "converged": "grep -q 'CONVERGED' log.txt && echo 1 || echo 0"
    },
    "id": "cfd_simulation"
}
```
