# FZ Syntax Guide

## Variable Substitution

### Basic Syntax

Variables are marked with a prefix (default `$`) and optionally delimited:

```text
# Without delimiters
Temperature: $temp
Pressure: $pressure

# With delimiters (safer for complex expressions)
Temperature: ${temp}
Pressure: ${pressure}
```

**Model configuration**:
```python
model = {
    "varprefix": "$",     # Variable prefix
    "delim": "{}"         # Optional delimiters (can be empty)
}
```

### Variable Naming Rules

- Alphanumeric and underscores: `$var_name`, `$T_celsius`, `$mesh_size`
- Case-sensitive: `$Temp` ≠ `$temp`
- Cannot start with number: `$1var` is invalid

### Legacy Funz Syntax Compatibility

FZ supports the legacy Java Funz variable syntax for backward compatibility:

```text
# Old Funz syntax (question mark prefix)
Temperature: ?T_celsius
Pressure: ?pressure

# Equivalent to modern FZ syntax
Temperature: $T_celsius
Pressure: $pressure
```

**Automatic detection**: `?var` is automatically converted to `$var` internally.

**Use cases**:
- Migrating from Java Funz to Python FZ
- Reusing existing Funz input templates
- Backward compatibility with legacy projects

See `examples/java_funz_syntax_example.py` for complete examples.

### Default Values

Variables can specify default values using `~` syntax:

```text
# Variable with default value
Host: ${host~localhost}
Port: ${port~8080}
Workers: ${workers~4}
```

**Behavior**:
- If variable is provided: use provided value
- If variable is missing: use default value (warning logged)
- If variable is missing and no default: keep original text

**Example**:
```python
from fz.interpreter import replace_variables_in_content

content = "Server: ${host~localhost}:${port~8080}"
variables = {"host": "example.com"}  # port not provided

result = replace_variables_in_content(content, variables)
# Result: "Server: example.com:8080"
# Warning: Variable 'port' not found, using default '8080'
```

## Formula Evaluation

### Basic Formula Syntax

Formulas compute values using expressions:

```text
# Formula with Python expression
Temperature_K: @{$T_celsius + 273.15}

# Formula with function call
Volume_m3: @{L_to_m3($V_L)}

# Formula with math operations
Circumference: @{2 * 3.14159 * $radius}
```

**Model configuration**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#"
}
```

### Context Lines (Shared Code)

Lines starting with comment + formula prefix define context available to all formulas:

```text
# Python interpreter
#@ import math
#@ R = 8.314  # Gas constant
#@ def celsius_to_kelvin(t):
#@     return t + 273.15

# Now use in formulas
T_kelvin: @{celsius_to_kelvin($T_celsius)}
Pressure: @{$n_mol * R * T_kelvin / $V_m3}
```

```text
# R interpreter
#@ samples <- rnorm(100, mean=$mu, sd=$sigma)
#@ normalize <- function(x) { (x - mean(x)) / sd(x) }

Mean: @{mean(samples)}
Normalized: @{mean(normalize(samples))}
```

### Variable Substitution in Formulas

Variables are substituted BEFORE formula evaluation:

```text
#@ def calculate_pressure(n, T, V):
#@     R = 8.314
#@     return n * R * T / V

# $n_mol, $T_kelvin, $V_m3 are substituted first
Pressure: @{calculate_pressure($n_mol, $T_kelvin, $V_m3)}
```

**With values** `{"n_mol": 2, "T_kelvin": 300, "V_m3": 0.001}`, becomes:
```text
Pressure: @{calculate_pressure(2, 300, 0.001)}
```

## Complete Examples

### Example 1: Simple Variable Substitution

**Input template**:
```text
# Configuration
n_iterations=$iterations
time_step=$dt
mesh_size=$mesh
```

**Model**:
```python
model = {"varprefix": "$"}
```

**Variables**:
```python
{"iterations": 1000, "dt": 0.01, "mesh": 100}
```

**Compiled output**:
```text
# Configuration
n_iterations=1000
time_step=0.01
mesh_size=100
```

### Example 2: Formulas with Python

**Input template**:
```text
# Perfect Gas Law calculation
n_mol=$n_mol
T_celsius=$T_celsius
V_L=$V_L

#@ import math
#@ R = 8.314  # Gas constant J/(mol·K)
#@ def L_to_m3(liters):
#@     return liters / 1000

# Calculated values
T_kelvin=@{$T_celsius + 273.15}
V_m3=@{L_to_m3($V_L)}
P_expected=@{$n_mol * R * $T_celsius / $V_m3}
```

**Model**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python"
}
```

**Variables**:
```python
{"n_mol": 2, "T_celsius": 25, "V_L": 10}
```

**Compiled output**:
```text
# Perfect Gas Law calculation
n_mol=2
T_celsius=25
V_L=10

# Calculated values
T_kelvin=298.15
V_m3=0.01
P_expected=49640.2
```

### Example 3: Formulas with R

**Input template**:
```text
# Statistical analysis
sample_size=$n
population_mean=$mu
population_sd=$sigma

#@ set.seed(42)
#@ samples <- rnorm($n, mean=$mu, sd=$sigma)
#@
#@ confidence_interval <- function(x, conf=0.95) {
#@     se <- sd(x) / sqrt(length(x))
#@     margin <- qt((1 + conf)/2, df=length(x)-1) * se
#@     return(c(mean(x) - margin, mean(x) + margin))
#@ }

# Results
sample_mean=@{mean(samples)}
sample_sd=@{sd(samples)}
ci_lower=@{confidence_interval(samples)[1]}
ci_upper=@{confidence_interval(samples)[2]}
```

**Model**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "R"
}
```

### Example 4: Default Values

**Input template**:
```text
# Server configuration
host=${server_host~localhost}
port=${server_port~8080}
workers=${num_workers~4}
debug=${debug_mode~false}

# Required parameter (no default)
api_key=$api_key
```

**Model**:
```python
model = {"varprefix": "$", "delim": "{}"}
```

**Variables** (partial):
```python
{"server_host": "production.example.com", "api_key": "secret123"}
```

**Compiled output**:
```text
# Server configuration
host=production.example.com
port=8080           # Used default
workers=4            # Used default
debug=false          # Used default

# Required parameter
api_key=secret123
```

## Syntax Patterns Reference

### Variables
```text
$var              # Simple variable
${var}            # Delimited variable (safer)
${var~default}    # Variable with default value
```

### Formulas
```text
@{expression}                  # Formula with delimiters
@{$var1 + $var2}              # Formula with variables
@{function($var)}             # Formula with function call
@{2 * math.pi * $radius}      # Formula with library function
```

### Context (Python)
```text
#@import library              # Import statement
#@var = value                 # Variable assignment
#@def func(x):                # Function definition (multi-line)
#@    return x * 2
```

### Context (R)
```text
#@library(package)            # Load library
#@var <- value                # Variable assignment
#@func <- function(x) {       # Function definition (multi-line)
#@    return(x * 2)
#@}
```

## Common Mistakes

### ❌ Wrong: No delimiter with special characters
```text
value=$temp_celsius
# Problem: underscore is part of variable name
```

### ✅ Correct: Use delimiters
```text
value=${temp}_celsius
# or
value=$temp" celsius"
```

### ❌ Wrong: Variable in comment without formula prefix
```text
# T_kelvin = $T_celsius + 273.15
# This is just a comment, not evaluated
```

### ✅ Correct: Use formula prefix for evaluation
```text
#@ T_kelvin = $T_celsius + 273.15
# This is evaluated as context
```

### ❌ Wrong: Formula without delimiters
```text
Result: @$var + 10
# Parser may not recognize this correctly
```

### ✅ Correct: Use delimiters
```text
Result: @{$var + 10}
```
