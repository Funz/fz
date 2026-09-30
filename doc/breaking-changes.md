# Breaking Changes

## Version 0.9.1

### fzr Directory Structure Change

**Previous behavior** (< 0.9.1):
- `fzr` created subdirectories only when multiple values were provided for variables
- Single values resulted in flat directory structure

**New behavior** (>= 0.9.1):
- `fzr` creates subdirectories in `results_dir` as long as **any** `input_variable` is provided
- No subdirectories only when `input_variables={}` (empty dict)
- More consistent and predictable behavior

**Example**:

```python
import fz

model = {"output": {"result": "cat output.txt"}}

# Single value - OLD: flat directory, NEW: subdirectory
results = fz.fzr(
    "input.txt",
    {"temp": 25},  # Single value
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)

# OLD (< 0.9.1):
#   results/input.txt, results/output.txt, ...
#
# NEW (>= 0.9.1):
#   results/temp=25/input.txt, results/temp=25/output.txt, ...

# Only flat when explicitly empty
results = fz.fzr(
    "input.txt",
    {},  # Empty - no variables
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
# Both versions: results/input.txt, results/output.txt, ... (flat)
```

**Migration**:
- Update scripts expecting flat directory structure for single-value cases
- Use path parsing from `fzo` to handle subdirectory names
- Benefits: Better organization, consistent with parametric study expectations
