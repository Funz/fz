# R Interpreter Example

This example demonstrates how to use the R interpreter in the fz package using the rpy2 integration.

## Installation

First, install the R interpreter support:

```bash
pip install funz-fz[r]
```

This will install the `rpy2` package which provides the Python-R interface.

## Basic Usage

### Setting the Interpreter

You can set the interpreter to R in several ways:

1. **Environment variable**:
   ```bash
   export FZ_INTERPRETER=R
   ```

2. **Programmatically**:
   ```python
   from fz.config import set_interpreter
   set_interpreter("R")
   ```

3. **In your model definition**:
   ```python
   model = {
       "interpreter": "R",
       # ... other model settings
   }
   ```

### Example 1: Basic R Formulas

Create a file `example.txt` with R formulas:

```
Radius: $radius
Diameter: @{2 * radius}
Area: @{pi * radius^2}
Circumference: @{2 * pi * radius}
```

When processed with `radius=5`, this becomes:

```
Radius: 5
Diameter: 10
Area: 78.53981633974483
Circumference: 31.41592653589793
```

### Example 2: Using R Context (Function Definitions)

You can define R functions using context lines (lines starting with `#@`):

```
#@calculate_stats <- function(x) {
#@  list(mean = mean(x), sd = sd(x), median = median(x))
#@}
#@
#@data <- c($val1, $val2, $val3, $val4, $val5)

Mean: @{mean(data)}
Standard Deviation: @{sd(data)}
Median: @{median(data)}
```

### Example 3: Statistical Analysis

```
#@# Create a normal distribution sample
#@samples <- rnorm($n, mean=$mu, sd=$sigma)

Sample size: $n
Mean (theoretical): $mu
SD (theoretical): $sigma
Mean (sample): @{mean(samples)}
SD (sample): @{sd(samples)}
```

### Example 4: Using R's Built-in Functions

R has many built-in statistical and mathematical functions:

```
#@x <- seq(1, $max_val, by=1)

Sum: @{sum(x)}
Product: @{prod(x)}
Min: @{min(x)}
Max: @{max(x)}
Range: @{diff(range(x))}
Variance: @{var(x)}
```

## Variable Substitution

Variables in the content are replaced using the pattern `$variable` or `${variable}`:

- `$x` - Simple variable reference
- `${x}` - Delimited variable reference (useful when followed by alphanumeric characters)

In formulas, variables are converted from Python to R automatically:
- Numbers (int, float) → R numeric
- Strings → R character
- Lists/tuples → R vectors

## Formula Syntax

Formulas are marked with the formula prefix (default `@`) and delimiters (default `{}`):

- `@{expression}` - Evaluate the R expression and replace with result
- `#@code` - Context line: R code that runs before formula evaluation (useful for functions, data setup)

## Complete Example

```python
from fz import fzi
from fz.config import set_interpreter

# Set interpreter to R
set_interpreter("R")

# Run parametric study
results = fzi(
    input_path="my_r_template.txt",
    input_variables={
        "n_samples": [100, 500, 1000],
        "distribution": ["norm", "unif", "exp"]
    },
    output_expression="Mean: @{mean(samples)}"
)

print(results)
```

## Comparison: Python vs R Interpreter

### Python Interpreter
```
#@import math
Circumference: @{2 * math.pi * $radius}
```

### R Interpreter
```
Circumference: @{2 * pi * $radius}
```

Note: R has `pi` as a built-in constant, while Python requires importing `math.pi`.

## Tips

1. **Use R's vectorized operations**: R is optimized for vector operations
2. **Statistical functions**: Leverage R's extensive statistical library
3. **Error handling**: If a formula fails, the original formula text is preserved
4. **Context lines**: Use `#@` for multi-line function definitions and data setup

## Troubleshooting

If you get an error about rpy2 not being installed:

```
Warning: rpy2 package not installed. Install with: pip install rpy2
```

Make sure to install it:

```bash
pip install rpy2
# or
pip install funz-fz[r]
```

For issues with R installation itself, make sure R is installed on your system:

```bash
# Ubuntu/Debian
sudo apt-get install r-base r-base-dev

# macOS
brew install r

# Windows
# Download from https://cran.r-project.org/bin/windows/base/
```
