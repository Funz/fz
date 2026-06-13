# FZ Formulas and Interpreters

## Formula Evaluation Overview

FZ supports evaluating formulas in input templates using Python or R interpreters. This allows:

- **Calculated parameters**: Derive values from input variables
- **Unit conversions**: Convert between units automatically
- **Complex expressions**: Use mathematical functions and libraries
- **Statistical computing**: Generate random samples, compute statistics (R)

## Basic Formula Syntax

### Python Formulas (Default)

**Model configuration**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python"  # Default
}
```

**Input template**:
```text
# Variables
temperature=$T_celsius

# Formula
temperature_K=@{$T_celsius + 273.15}
```

**With variables** `{"T_celsius": 25}`, becomes:
```text
temperature=25
temperature_K=298.15
```

### R Formulas

**Model configuration**:
```python
model = {
    "varprefix": "$",
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "R"
}
```

**Input template**:
```text
# Variables
sample_size=$n

# Formula
#@ samples <- rnorm($n, mean=0, sd=1)
sample_mean=@{mean(samples)}
```

**With variables** `{"n": 100}`, becomes:
```text
sample_size=100
sample_mean=0.0234  # Random value from normal distribution
```

## Context Lines

Context lines define code that's available to all formulas in the file.

### Python Context

**Syntax**: `commentline + formulaprefix + code`

```text
#@ import math
#@ import numpy as np
#@ R = 8.314  # Gas constant
#@
#@ def celsius_to_kelvin(t):
#@     return t + 273.15
#@
#@ def pressure_ideal_gas(n, T, V):
#@     return n * R * T / V
```

**What you can include**:
- Import statements: `#@ import math`
- Variable assignments: `#@ R = 8.314`
- Function definitions: `#@ def func(x): ...`
- Multi-line code blocks

### R Context

```text
#@ library(MASS)
#@ set.seed(42)
#@
#@ normalize <- function(x) {
#@     (x - mean(x)) / sd(x)
#@ }
#@
#@ samples <- rnorm(1000, mean=100, sd=15)
```

**What you can include**:
- Library loading: `#@ library(package)`
- Variable assignments: `#@ var <- value`
- Function definitions: `#@ func <- function(x) { ... }`
- Data generation: `#@ samples <- rnorm(...)`

## Complete Examples

### Example 1: Perfect Gas Law (Python)

**Input template**:
```text
# Input variables
n_mol=$n_mol
T_celsius=$T_celsius
V_L=$V_L

# Context: constants and functions
#@ import math
#@ R = 8.314  # J/(mol·K)
#@
#@ def L_to_m3(liters):
#@     return liters / 1000
#@
#@ def celsius_to_kelvin(celsius):
#@     return celsius + 273.15

# Calculated values
T_kelvin=@{celsius_to_kelvin($T_celsius)}
V_m3=@{L_to_m3($V_L)}
P_expected=@{$n_mol * R * celsius_to_kelvin($T_celsius) / L_to_m3($V_L)}
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

**Compiled result**:
```text
n_mol=2
T_celsius=25
V_L=10

T_kelvin=298.15
V_m3=0.01
P_expected=49640.2
```

### Example 2: Statistical Sampling (R)

**Input template**:
```text
# Sampling parameters
sample_size=$n
population_mean=$mu
population_sd=$sigma
confidence=$conf_level

# Context: generate samples and define functions
#@ set.seed(42)  # Reproducible results
#@ samples <- rnorm($n, mean=$mu, sd=$sigma)
#@
#@ confidence_interval <- function(x, conf) {
#@     se <- sd(x) / sqrt(length(x))
#@     margin <- qt((1 + conf)/2, df=length(x)-1) * se
#@     c(mean(x) - margin, mean(x) + margin)
#@ }

# Results
sample_mean=@{mean(samples)}
sample_sd=@{sd(samples)}
sample_median=@{median(samples)}
ci_lower=@{confidence_interval(samples, $conf_level)[1]}
ci_upper=@{confidence_interval(samples, $conf_level)[2]}
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

**Variables**:
```python
{"n": 100, "mu": 100, "sigma": 15, "conf_level": 0.95}
```

**Compiled result**:
```text
sample_size=100
population_mean=100
population_sd=15
confidence=0.95

sample_mean=101.23
sample_sd=14.87
sample_median=100.56
ci_lower=98.35
ci_upper=104.11
```

### Example 3: Geometric Calculations (Python)

**Input template**:
```text
# Geometry parameters
radius=$radius
height=$height

# Context: import math for pi
#@ import math
#@
#@ def cylinder_volume(r, h):
#@     return math.pi * r**2 * h
#@
#@ def cylinder_surface_area(r, h):
#@     return 2 * math.pi * r * (r + h)

# Calculated geometry
volume=@{cylinder_volume($radius, $height)}
surface_area=@{cylinder_surface_area($radius, $height)}
circumference=@{2 * math.pi * $radius}
```

**Variables**:
```python
{"radius": 5, "height": 10}
```

**Compiled result**:
```text
radius=5
height=10

volume=785.398
surface_area=471.239
circumference=31.416
```

### Example 4: Unit Conversions (Python)

**Input template**:
```text
# Input in various units
temp_F=$temp_fahrenheit
pressure_psi=$pressure_psi
length_inch=$length_inches

# Context: conversion functions
#@ def F_to_C(f):
#@     return (f - 32) * 5/9
#@
#@ def F_to_K(f):
#@     return F_to_C(f) + 273.15
#@
#@ def psi_to_Pa(psi):
#@     return psi * 6894.76
#@
#@ def inch_to_m(inch):
#@     return inch * 0.0254

# Converted values
temp_C=@{F_to_C($temp_fahrenheit)}
temp_K=@{F_to_K($temp_fahrenheit)}
pressure_Pa=@{psi_to_Pa($pressure_psi)}
length_m=@{inch_to_m($length_inches)}
```

**Variables**:
```python
{"temp_fahrenheit": 68, "pressure_psi": 14.7, "length_inches": 12}
```

**Compiled result**:
```text
temp_F=68
pressure_psi=14.7
length_inch=12

temp_C=20.0
temp_K=293.15
pressure_Pa=101352.72
length_m=0.3048
```

### Example 5: Array Calculations (Python)

**Input template**:
```text
# Grid parameters
nx=$nx
ny=$ny
nz=$nz

# Context: compute derived quantities
#@ import numpy as np
#@
#@ total_cells = $nx * $ny * $nz
#@ cells_per_dimension = np.array([$nx, $ny, $nz])
#@ max_dimension = max($nx, $ny, $nz)

# Results
total_cells=@{total_cells}
max_dim=@{max_dimension}
aspect_ratio=@{$nx / $nz}
```

**Variables**:
```python
{"nx": 100, "ny": 100, "nz": 50}
```

**Compiled result**:
```text
nx=100
ny=100
nz=50

total_cells=500000
max_dim=100
aspect_ratio=2.0
```

## Python vs R Comparison

### Mathematical Operations

**Python**:
```text
#@ import math
result=@{math.sqrt($x**2 + $y**2)}
angle=@{math.atan2($y, $x)}
```

**R**:
```text
result=@{sqrt($x^2 + $y^2)}
angle=@{atan2($y, $x)}
```

### Statistical Functions

**Python** (requires numpy/scipy):
```text
#@ import numpy as np
mean=@{np.mean([$x, $y, $z])}
std=@{np.std([$x, $y, $z])}
```

**R** (built-in):
```text
#@ values <- c($x, $y, $z)
mean=@{mean(values)}
std=@{sd(values)}
```

### Random Sampling

**Python**:
```text
#@ import random
#@ random.seed(42)
random_value=@{random.gauss($mu, $sigma)}
```

**R**:
```text
#@ set.seed(42)
random_value=@{rnorm(1, mean=$mu, sd=$sigma)}
```

### Array/Vector Operations

**Python**:
```text
#@ import numpy as np
#@ x = np.linspace(0, 10, $n)
#@ y = np.sin(x)
max_y=@{np.max(y)}
```

**R**:
```text
#@ x <- seq(0, 10, length.out=$n)
#@ y <- sin(x)
max_y=@{max(y)}
```

## Advanced Patterns

### Pattern 1: Conditional Logic

**Python**:
```text
#@ def select_method(size):
#@     if size < 100:
#@         return "fast"
#@     elif size < 1000:
#@         return "medium"
#@     else:
#@         return "slow"

method=@{select_method($mesh_size)}
```

**R**:
```text
#@ select_method <- function(size) {
#@     if (size < 100) "fast"
#@     else if (size < 1000) "medium"
#@     else "slow"
#@ }

method=@{select_method($mesh_size)}
```

### Pattern 2: Lookup Tables

**Python**:
```text
#@ coefficients = {
#@     "water": 1000,
#@     "air": 1.225,
#@     "steel": 7850
#@ }

density=@{coefficients.get($material, 0)}
```

**R**:
```text
#@ coefficients <- list(
#@     water = 1000,
#@     air = 1.225,
#@     steel = 7850
#@ )

density=@{coefficients[[$material]]}
```

### Pattern 3: File-based Data

**Python**:
```text
#@ import json
#@ with open('parameters.json') as f:
#@     params = json.load(f)

value=@{params[$key]}
```

**R**:
```text
#@ library(jsonlite)
#@ params <- fromJSON('parameters.json')

value=@{params[[$key]]}
```

### Pattern 4: Complex Calculations

**Python**:
```text
#@ import numpy as np
#@ from scipy import integrate
#@
#@ def integrand(x, a, b):
#@     return a * x**2 + b * x
#@
#@ result, error = integrate.quad(integrand, 0, $upper_limit, args=($a, $b))

integral=@{result}
```

**R**:
```text
#@ integrand <- function(x, a, b) {
#@     a * x^2 + b * x
#@ }
#@
#@ result <- integrate(function(x) integrand(x, $a, $b), 0, $upper_limit)

integral=@{result$value}
```

## Variable Substitution in Formulas

Variables are substituted BEFORE evaluation:

```text
#@ def calculate(n, T):
#@     return n * 8.314 * T

# $n_mol and $T_kelvin are substituted first
result=@{calculate($n_mol, $T_kelvin)}
```

**With** `{"n_mol": 2, "T_kelvin": 300}`, becomes:
```text
result=@{calculate(2, 300)}
```

Then evaluated to:
```text
result=4988.4
```

## Setting Interpreter

### In Model Definition

```python
model = {
    "interpreter": "python",  # or "R"
    # ... other fields
}
```

### Globally

```python
from fz.config import set_interpreter

set_interpreter("R")  # All subsequent operations use R
```

### Via Environment Variable

```bash
export FZ_INTERPRETER=R
```

## Installing R Support

### Requirements

```bash
# Install R
sudo apt-get install r-base r-base-dev  # Ubuntu/Debian
brew install r                           # macOS

# Install Python package with R support
pip install funz-fz[r]
# or
pip install rpy2
```

### Verification

```python
from fz.config import set_interpreter

try:
    set_interpreter("R")
    print("R interpreter available")
except Exception as e:
    print(f"R not available: {e}")
```

## Best Practices

### 1. Keep Context Organized

```text
# Good: organized context
#@ import math
#@ import numpy as np
#@
#@ # Constants
#@ R = 8.314
#@ g = 9.81
#@
#@ # Helper functions
#@ def func1(x):
#@     return x * 2
#@
#@ def func2(x, y):
#@     return x + y
```

### 2. Use Descriptive Function Names

```text
# Good
#@ def celsius_to_kelvin(temp_c):
#@     return temp_c + 273.15

# Bad
#@ def c2k(t):
#@     return t + 273.15
```

### 3. Handle Edge Cases

```text
#@ def safe_divide(a, b):
#@     return a / b if b != 0 else 0

result=@{safe_divide($numerator, $denominator)}
```

### 4. Document Complex Formulas

```text
#@ # Calculate Reynolds number for pipe flow
#@ # Re = (density * velocity * diameter) / viscosity
#@ def reynolds_number(rho, v, d, mu):
#@     return (rho * v * d) / mu

Re=@{reynolds_number($density, $velocity, $diameter, $viscosity)}
```

### 5. Test Formulas Independently

```python
# Test formula evaluation separately
from fz.interpreter import evaluate_formulas_in_content

content = """
#@ def test(x):
#@     return x * 2
result=@{test(5)}
"""

model = {
    "formulaprefix": "@",
    "delim": "{}",
    "commentline": "#",
    "interpreter": "python"
}

result = evaluate_formulas_in_content(content, {}, model)
print(result)
# Output: result=10
```
