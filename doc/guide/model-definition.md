# Model Definition

<!-- counterpart-note -->
> Guide page (from the former README). Reference counterpart in `doc/`: [`model-definition.md`](../model-definition.md), [`syntax-guide.md`](../syntax-guide.md), [`formulas-and-interpreters.md`](../formulas-and-interpreters.md). When behaviour changes, update both.


A model defines how to parse inputs and extract outputs:

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

## Model Aliases

Store reusable models in `.fz/models/`:

**`.fz/models/perfectgas.json`**:
```json
{
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
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

## Formula Evaluation

Formulas in input files are evaluated during compilation using Python or R interpreters.

### Python Interpreter (Default)

```text
# Input template with formulas
Temperature: $T_celsius C
Volume: $V_L L

# Context (available in all formulas)
#@import math
#@R = 8.314
#@def celsius_to_kelvin(t):
#@    return t + 273.15

# Calculated value
#@T_kelvin = celsius_to_kelvin($T_celsius)
#@pressure = $n_mol * R * T_kelvin / ($V_L / 1000)

Result: @{pressure} Pa
Circumference: @{2 * math.pi * $radius}
```

### R Interpreter

For statistical computing, you can use R for formula evaluation:

```python
from fz import fzi
from fz.config import set_interpreter

# Set interpreter to R
set_interpreter("R")

# Or specify in model
model = {"interpreter": "R", "formulaprefix": "@", "delim": "{}", "commentline": "#"}
```

**R template example**:
```text
# Input template with R formulas
Sample size: $n
Mean: $mu
SD: $sigma

# R context (available in all formulas)
#@samples <- rnorm($n, mean=$mu, sd=$sigma)

Mean (sample): @{mean(samples)}
SD (sample): @{sd(samples)}
Median: @{median(samples)}
```

**Installation requirements**: R must be installed along with system libraries. See `examples/r_interpreter_example.md` for detailed installation instructions.

```bash
# Install with R support
pip install funz-fz[r]
```

**Key differences**:
- Python requires `import math` for `math.pi`, R has `pi` built-in
- R excels at statistical functions: `mean()`, `sd()`, `median()`, `rnorm()`, etc.
- R uses `<-` for assignment in context lines
- R is vectorized by default

### Variable Default Values

Variables can specify default values using the `${var~default}` syntax:

```text
# Configuration template
Host: ${host~localhost}
Port: ${port~8080}
Debug: ${debug~false}
Workers: ${workers~4}
```

**Behavior**:
- If variable is provided in `input_variables`, its value is used
- If variable is NOT provided but has default, default is used (with warning)
- If variable is NOT provided and has NO default, it remains unchanged

**Example**:
```python
from fz.interpreter import replace_variables_in_content

content = "Server: ${host~localhost}:${port~8080}"
input_variables = {"host": "example.com"}  # port not provided

result = replace_variables_in_content(content, input_variables)
# Result: "Server: example.com:8080"
# Warning: Variable 'port' not found in input_variables, using default value: '8080'
```

**Use cases**:
- Configuration templates with sensible defaults
- Environment-specific deployments
- Optional parameters in parametric studies

See `doc/syntax-guide.md` for comprehensive documentation.

### Old Funz Syntax Compatibility

For backward compatibility with legacy Java Funz users, FZ supports the old `?var` variable syntax:

```text
# Legacy Funz syntax (still supported)
Temperature: ?T_celsius
Pressure: ?P_bar

# Equivalent modern FZ syntax
Temperature: $T_celsius
Pressure: $P_bar
```

**Behavior**:
- `?variable` is automatically converted to `$variable`
- No configuration needed - works transparently
- Useful for migrating existing Funz projects to Python
- Can mix both syntaxes in the same file

**Example**:
```python
import fz

# Input file with old Funz syntax
content = """
n_mol=?n_mol
T_celsius=?T_celsius
"""

model = {"varprefix": "$"}  # Standard FZ configuration

# Works automatically - ?n_mol treated as $n_mol
variables = fz.fzi("input.txt", model)
# Returns: {'n_mol': None, 'T_celsius': None}
```

See `examples/java_funz_syntax_example.py` for more examples.

**Features**:
- Python or R expression evaluation
- Multi-line function definitions
- Variable substitution in formulas
- Default values for variables
- Nested formula evaluation
