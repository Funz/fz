# fzd - Iterative Design of Experiments with Algorithms

`fzd` is a powerful extension to the `fz` framework that enables **iterative design of experiments** using optimization and sampling algorithms. Unlike `fzr` which evaluates a predefined grid of parameter combinations, `fzd` intelligently selects which points to evaluate based on previous results.

## Requirements

**`fzd` requires pandas to be installed:**

```bash
pip install pandas
```

Or install fz with pandas support:

```bash
pip install funz-fz[pandas]
```

## Overview

The `fzd` function combines:
- **Input parameter ranges**: Define search spaces as `{"var": "[min;max]"}`
- **Model execution**: Run simulations using the existing fz model framework
- **Output expressions**: Combine multiple outputs into a single objective
- **Algorithms**: Use built-in or custom algorithms to guide the search

## Basic Usage

### Python API

```python
import fz

analysis = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]", "y": "[-5;5]"},
    model="mymodel",
    output_expression="output1 + output2 * 2",
    algorithm="algorithms/bfgs.py",
    algorithm_options={"max_iter": 100, "tol": 1e-6},
    analysis_dir="fzd_analysis"
)
```

### Command Line

```bash
# Using random sampling algorithm
fzd -i ./input -v '{"x":"[0;1]","y":"[-5;5]"}' \
    -m mymodel -e "output1 + output2 * 2" \
    -a algorithms/randomsampling.py -o '{"nvalues":20}'

# Using BFGS optimization algorithm
fzd -i ./input -v '{"x":"[0;1]"}' \
    -m mymodel -e "result" \
    -a algorithms/bfgs.py -o '{"max_iter":50}'

# Using as a subcommand of fz
fz design -i ./input -v '{"x":"[0;1]"}' \
    -m mymodel -e "result" -a algorithms/brent.py
```

## Parameters

### Required Parameters

- **`input_file`**: Path to input file or directory
- **`input_variables`**: Dict of variable ranges, e.g., `{"x": "[0;1]", "y": "[-5;5]"}`
- **`model`**: Model definition (JSON file, inline JSON, or alias)
- **`output_expression`**: Mathematical expression to minimize, e.g., `"out1 + out2 * 2"`
- **`algorithm`**: Path to algorithm Python file, e.g., `"algorithms/montecarlo_uniform.py"`

### Optional Parameters

- **`calculators`**: Calculator specifications, e.g., `["sh://bash ./script.sh"]` (default: `["sh://"]`)
- **`algorithm_options`**: Dict of algorithm-specific options, e.g., `{"batch_size": 10, "max_iter": 100}`
- **`analysis_dir`**: Analysis results directory (default: `"results_fzd"`)

## Algorithms

`fzd` requires an algorithm file that implements the optimization or sampling strategy. The algorithm is specified as a path to a Python file containing an algorithm class.

**No built-in algorithms** - you must provide an algorithm file. See the `examples/` directory for algorithm implementations you can use or adapt.

## Output Expression

The `output_expression` parameter allows you to combine multiple output variables into a single objective to minimize.

**Supported Operations:**
- Arithmetic: `+`, `-`, `*`, `/`, `**` (power)
- Functions: `sqrt`, `exp`, `log`, `log10`, `sin`, `cos`, `tan`, `abs`, `min`, `max`
- Constants: `pi`, `e`

**Examples:**
```python
# Simple: minimize a single output
output_expression = "error"

# Weighted sum: combine multiple outputs
output_expression = "error1 + error2 * 2"

# Root mean square
output_expression = "sqrt(error1**2 + error2**2)"

# With math functions
output_expression = "abs(target - result) + 0.1 * sqrt(variance)"
```

## Creating Algorithms

### Basic Usage

Algorithms are Python files that define a class with specific methods. You provide the path to the algorithm file:

```python
analysis = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]", "y": "[0;1]"},
    model="mymodel",
    output_expression="result",
    algorithm="algorithms/my_algorithm.py",
    algorithm_options={"custom_option": 42}
)
```

**Supported path formats:**
- Relative paths: `"algorithm.py"`, `"algorithms/my_algo.py"`
- Absolute paths: `"/path/to/algorithm.py"`

### Algorithm File with Metadata

Algorithm files can include metadata comments at the top to document options and requirements:

```python
#title: My Custom Algorithm
#author: Your Name
#type: optimization
#options: max_iter=100;tol=1e-6;batch_size=10
#require: numpy;scipy

class MyAlgorithm:
    def __init__(self, **options):
        # Options from #options metadata are used as defaults
        # but can be overridden by explicitly passed options
        self.max_iter = int(options.get('max_iter', 100))
        self.tol = float(options.get('tol', 1e-6))
        # ...
```

**Metadata fields:**
- `#title:` - Human-readable algorithm title
- `#author:` - Algorithm author
- `#type:` - Algorithm type (optimization, sampling, etc.)
- `#options:` - Default options as `key=value` pairs separated by semicolons
- `#require:` - Required Python packages separated by semicolons (automatically installed if missing)

The `#options` metadata provides default values that are automatically used when loading the algorithm. These can be overridden by passing explicit options to `fzd()`.

**Automatic Package Installation:**

When an algorithm specifies required packages via the `#require:` header, `fzd` will:
1. Check if each package is already installed
2. Automatically install any missing packages using `pip`
3. Verify the installation was successful

For example, if your algorithm requires numpy and scipy:
```python
#require: numpy;scipy
```

These packages will be automatically installed the first time you load the algorithm if they're not already present. This ensures your algorithms can run without manual dependency management.

### Algorithm Interface

Each algorithm must be a class with these methods:

```python
class Myalgorithm:
    """Custom algorithm"""

    def __init__(self, **options):
        """Initialize with algorithm-specific options"""
        self.max_iter = options.get('max_iter', 100)
        # ... store options ...

    def get_initial_design(self, input_vars, output_vars):
        """
        Generate initial design of experiments

        Args:
            input_vars: Dict[str, Tuple[float, float]] - {var: (min, max)}
            output_vars: List[str] - Output variable names

        Returns:
            List[Dict[str, float]] - Initial points to evaluate
        """
        # Return list of dicts, e.g.:
        return [
            {"x": 0.0, "y": 0.0},
            {"x": 0.5, "y": 0.5},
            {"x": 1.0, "y": 1.0}
        ]

    def get_next_design(self, previous_input_vars, previous_output_values):
        """
        Generate next design based on previous results

        Args:
            previous_input_vars: List[Dict[str, float]] - All previous inputs
                                 e.g., [{"x": 0.5, "y": 0.3}, {"x": 0.7, "y": 0.2}]
            previous_output_values: List[float] - Corresponding outputs (may contain None)
                                    e.g., [1.5, 2.3, None, 0.8]

        Returns:
            List[Dict[str, float]] - Next points to evaluate
            Return empty list [] when finished

        Note: While the interface uses Python lists, you can convert to numpy arrays
              for numerical computation:
              ```python
              import numpy as np
              # Filter out None values and convert to numpy
              Y_valid = np.array([y for y in previous_output_values if y is not None])
              # For X, you may want to extract specific variables
              x_vals = np.array([inp['x'] for inp in previous_input_vars])
              ```
        """
        # Analyze previous results and return next points
        # Return [] when algorithm is done
        if self.converged():
            return []

        return [{"x": next_x, "y": next_y}]

    def get_analysis(self, input_vars, output_values):
        """
        Format results for display

        Args:
            input_vars: List[Dict[str, float]] - All evaluated inputs
                       e.g., [{"x": 0.5, "y": 0.3}, {"x": 0.7, "y": 0.2}]
            output_values: List[float] - All outputs (may contain None)
                          e.g., [1.5, 2.3, None, 0.8]

        Returns:
            Dict with 'text' and 'data' keys

        Note: Can convert to numpy arrays for statistical analysis:
              ```python
              import numpy as np
              valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                              if out is not None]
              ```
        """
        # Filter out None values
        valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                        if out is not None]

        if not valid_results:
            return {'text': 'No valid results', 'data': {}}

        best_input, best_output = min(valid_results, key=lambda x: x[1])

        return {
            'text': f"Best: {best_input} = {best_output}",
            'data': {
                'best_input': best_input,
                'best_output': best_output
            }
        }

    def get_analysis_tmp(self, input_vars, output_values):
        """
        (OPTIONAL) Display intermediate results at each iteration

        This method is called after each iteration if it exists.
        Use it to show progress during the optimization/sampling process.

        Args:
            input_vars: List[Dict[str, float]] - All evaluated inputs so far
            output_values: List[float] - All outputs so far (may contain None)

        Returns:
            Dict with 'text' and optionally 'data' keys

        Example:
            def get_analysis_tmp(self, input_vars, output_values):
                valid_results = [(inp, out) for inp, out in zip(input_vars, output_values)
                                if out is not None]

                if not valid_results:
                    return {'text': 'No valid results yet', 'data': {}}

                best_input, best_output = min(valid_results, key=lambda x: x[1])

                return {
                    'text': f"Current best: {best_input} = {best_output:.6f} "
                           f"({len(valid_results)} valid samples)",
                    'data': {'current_best': best_output}
                }
        """
        # Optional method - only implement if you want intermediate progress reports
        pass
```

### Using Algorithms

```python
# Save your algorithm to a file, e.g., algorithms/myalgo.py

analysis = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]"},
    model="mymodel",
    output_expression="result",
    algorithm="algorithms/myalgo.py",
    algorithm_options={"custom_option": 42}
)
```

## Return Value

The `fzd` function returns a dictionary with:

```python
{
    'XY': DataFrame,            # Pandas DataFrame with all X (inputs) and Y (output) values
    'algorithm': 'bfgs',        # Algorithm name
    'iterations': 15,           # Number of iterations
    'total_evaluations': 45,    # Total function evaluations
    'summary': '...',           # Summary text
    'display': {                # Display info from algorithm (processed)
        'text': '...',          # Plain text (if any)
        'data': {...},          # Data dict
        'html_file': '...',     # HTML file path (if HTML detected)
        'json_data': {...},     # Parsed JSON (if JSON detected)
        'json_file': '...',     # JSON file path (if JSON detected)
        'keyvalue_data': {...}, # Parsed key=value (if detected)
        'txt_file': '...',      # Text file path (if key=value detected)
        'md_file': '...'        # Markdown file path (if markdown detected)
    }
}
```

### XY DataFrame

The `XY` DataFrame provides convenient access to all input and output values:

```python
result = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]", "y": "[0;1]"},
    model=model,
    output_expression="result",  # This becomes the output column name
    algorithm="algorithms/optimizer.py"
)

# Access the XY DataFrame
df = result['XY']

# DataFrame columns:
# - All input variables (e.g., 'x', 'y', 'z')
# - Output column named with output_expression (e.g., 'result')

# Example with output_expression="result":
#          x         y    result
# 0  0.639427  0.025011   1.2345
# 1  0.275029  0.223211   2.4567
# 2  0.736471  0.676699   0.9876

# Easy filtering and analysis
valid_df = df[df['result'].notna()]  # Filter out failed evaluations
best_row = df.loc[df['result'].idxmin()]  # Find minimum
print(f"Best input: x={best_row['x']}, y={best_row['y']}")
print(f"Best output: {best_row['result']}")

# Use pandas functions
mean_output = df['result'].mean()
std_output = df['result'].std()

# Plot results
import matplotlib.pyplot as plt
df.plot.scatter(x='x', y='result')
plt.show()
```

## Examples

### Example 1: Optimize a Simple Function

```python
import fz
import tempfile
from pathlib import Path

# Create input directory
input_dir = Path(tempfile.mkdtemp()) / "input"
input_dir.mkdir()

# Create input file
(input_dir / "input.txt").write_text("x = $x\n")

# Define model that computes (x - 0.7)^2
model = {
    "varprefix": "$",
    "delim": "()",
    "run": "bash -c 'source input.txt && result=$(echo \"scale=6; ($x - 0.7) * ($x - 0.7)\" | bc) && echo \"result = $result\" > output.txt'",
    "output": {
        "result": "grep 'result = ' output.txt | cut -d '=' -f2"
    }
}

# Find minimum using Brent's method
analysis = fz.fzd(
    input_file=str(input_dir),
    input_variables={"x": "[0;2]"},
    model=model,
    output_expression="result",
    algorithm="algorithms/brent.py",
    algorithm_options={"max_iter": 20}
)

# Get best result
best_idx = min(range(len(analysis['output_values'])),
               key=lambda i: analysis['output_values'][i])
print(f"Optimal x: {analysis['input_vars'][best_idx]['x']}")  # Should be near 0.7
```

### Example 2: Multi-objective Optimization

```python
# Model that outputs two values
model = {
    "varprefix": "$",
    "delim": "()",
    "run": "bash -c 'source input.txt && ...'",
    "output": {
        "error": "...",
        "variance": "..."
    }
}

# Minimize weighted combination using BFGS
analysis = fz.fzd(
    input_file="./input",
    input_variables={"param1": "[0;10]", "param2": "[-5;5]"},
    model=model,
    output_expression="error + 0.1 * variance",
    algorithm="algorithms/bfgs.py",
    algorithm_options={"max_iter": 100}
)
```

### Example 3: Using a Custom Algorithm from File

```python
# Create custom algorithm file: my_algorithm.py
"""
#title: Simple Grid Search
#author: Me
#type: sampling
#options: grid_points=5

class GridSearch:
    def __init__(self, **options):
        self.grid_points = int(options.get('grid_points', 5))
        self.variables = {}

    def get_initial_design(self, input_vars, output_vars):
        self.variables = input_vars
        import numpy as np
        points = []
        for v, (min_val, max_val) in input_vars.items():
            grid = np.linspace(min_val, max_val, self.grid_points)
            # Generate all combinations
            if not points:
                points = [{v: x} for x in grid]
            else:
                new_points = []
                for point in points:
                    for x in grid:
                        new_point = point.copy()
                        new_point[v] = x
                        new_points.append(new_point)
                points = new_points
        return points

    def get_next_design(self, X, Y):
        return []  # One-shot algorithm

    def get_analysis(self, X, Y):
        best_idx = min(range(len(Y)), key=lambda i: Y[i])
        return {
            'text': f"Best: {X[best_idx]} = {Y[best_idx]}",
            'data': {'best_input': X[best_idx], 'best_output': Y[best_idx]}
        }
"""

# Use the custom algorithm
analysis = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]", "y": "[0;1]"},
    model="mymodel",
    output_expression="result",
    algorithm="my_algorithm.py",
    algorithm_options={"grid_points": 10}
)
```

### Example 4: Using with Remote Calculators

```python
analysis = fz.fzd(
    input_file="./input",
    input_variables={"x": "[0;1]", "y": "[0;1]"},
    model="mymodel",
    output_expression="result",
    algorithm="algorithms/bfgs.py",
    calculators=["ssh://user@server1", "ssh://user@server2"],
    algorithm_options={"max_iter": 50}
)
```

## Comparison: fzd vs fzr

| Feature | fzr | fzd |
|---------|-----|-----|
| **Use Case** | Evaluate predefined grid | Iterative optimization/sampling |
| **Input** | Specific values or lists | Ranges `[min;max]` |
| **Evaluation** | All combinations | Algorithm-guided selection |
| **Output** | DataFrame with all results | Best results + full history |
| **When to use** | Parameter sweep, sensitivity analysis | Optimization, adaptive sampling |

**Use `fzr` when:**
- You want to evaluate all combinations of specific parameter values
- You need complete coverage of a parameter space
- You're doing sensitivity analysis or creating response surfaces

**Use `fzd` when:**
- You want to find optimal parameter values
- The parameter space is large and full evaluation is expensive
- You want intelligent, adaptive sampling

## Advanced Features

### Interrupt Handling

Like `fzr`, `fzd` supports graceful interrupt handling:

```python
try:
    result = fz.fzd(...)  # Press Ctrl+C to interrupt
except KeyboardInterrupt:
    print("Interrupted, partial results may be available")
```

### Progress Bar with Total Time

When running multiple cases, `fzd` displays a visual progress bar showing:

**During execution:**
```
[■■■□□□□] ETA: 2m 15s
```

**After completion:**
```
[■■■■■■■] Total time: 3m 42s
```

Features:
- **Real-time progress**: Shows status of each case (■ = done, □ = failed)
- **Dynamic ETA**: Estimates remaining time based on completed cases
- **Total time display**: After completion, the bar **stays visible** showing total execution time
- **Per-batch tracking**: Each batch in fzd shows its own progress and total time

The progress bar is automatically shown for multiple cases and adapts to your terminal. It provides immediate visual feedback on:
- Number of cases completed vs total
- Approximate time remaining (ETA)
- Final execution time (Total time)
- Success/failure status of each case

Example output from an fzd run with 3 iterations:
```
Iteration 1:
[■■■■■] Total time: 1m 23s

Iteration 2:
[■■■■■■■] Total time: 2m 15s

Iteration 3:
[■■■■■■■■■] Total time: 3m 08s
```

This helps you track performance across iterations and identify slow cases.

### Result Directories

Results are organized by iteration:
```
results_fzd/
├── iter001/
│   ├── case_x=0.5,y=0.3/
│   └── ...
├── iter002/
│   ├── case_x=0.7,y=0.2/
│   └── ...
├── X_1.csv              # Input variables after iteration 1
├── Y_1.csv              # Output values after iteration 1
├── results_1.html       # HTML report with plots and statistics for iteration 1
├── X_2.csv              # Input variables after iteration 2
├── Y_2.csv              # Output values after iteration 2
├── results_2.html       # HTML report for iteration 2
└── ...
```

**Iteration Results Files:**

At each iteration, `fzd` automatically saves:

1. **`X_<iteration>.csv`** - CSV file with all input variable values evaluated so far
   - Columns: variable names (e.g., `x`, `y`)
   - Rows: each evaluated point

2. **`Y_<iteration>.csv`** - CSV file with all output values so far
   - Column: `output`
   - Rows: corresponding output values (or `NA` for failed evaluations)

3. **`results_<iteration>.html`** - HTML report with:
   - Summary (total samples, valid samples, iteration number)
   - Intermediate progress from `get_analysis_tmp()` (if available)
   - Current results from `get_analysis()`
   - Plots and visualizations (if algorithm provides HTML output)

These files allow you to:
- Track algorithm progress over time
- Analyze intermediate results
- Create custom visualizations
- Resume interrupted analyses

#### Intelligent Content Detection

`fzd` automatically detects the type of content returned by your algorithm's `get_analysis()` method and processes it accordingly:

**Supported Content Types:**

1. **HTML Content** - Saved to `analysis_<iteration>.html`
   ```python
   def get_analysis(self, X, Y):
       return {
           'html': '<div><h1>Results</h1><p>Mean: 1.23</p></div>',
           'data': {}
       }
   # Result dict will contain: {'html_file': 'analysis_1.html', 'data': {...}}
   ```

2. **JSON Content** - Parsed and saved to `analysis_<iteration>.json`
   ```python
   def get_analysis(self, X, Y):
       return {
           'text': '{"mean": 1.23, "std": 0.45, "samples": 100}',
           'data': {}
       }
   # Result dict will contain: {'json_data': {...}, 'json_file': 'analysis_1.json', ...}
   ```

3. **Key=Value Content** - Parsed and saved to `analysis_<iteration>.txt`
   ```python
   def get_analysis(self, X, Y):
       return {
           'text': 'mean = 1.23\nstd = 0.45\nsamples = 100',
           'data': {}
       }
   # Result dict will contain: {'keyvalue_data': {...}, 'txt_file': 'analysis_1.txt', ...}
   ```

4. **Markdown Content** - Saved to `analysis_<iteration>.md`
   ```python
   def get_analysis(self, X, Y):
       return {
           'text': '# Results\n\n* Mean: 1.23\n* Std: 0.45',
           'data': {}
       }
   # Result dict will contain: {'md_file': 'analysis_1.md', 'data': {...}}
   ```

5. **Plain Text** - Kept in the result dictionary as-is
   ```python
   def get_analysis(self, X, Y):
       return {
           'text': 'Simple text results',
           'data': {}
       }
   # Result dict will contain: {'text': 'Simple text results', 'data': {...}}
   ```

**Benefits:**
- Reduces memory usage by saving large HTML/Markdown to files
- Automatically parses structured data (JSON, key=value) into Python objects
- Makes results easier to process programmatically
- Maintains compatibility with existing code

**Accessing Results:**
```python
result = fz.fzd(...)

# Access processed display content
display = result['display']

if 'json_data' in display:
    mean = display['json_data']['mean']  # Directly use parsed JSON

if 'keyvalue_data' in display:
    samples = display['keyvalue_data']['samples']  # Access parsed key=value

if 'html_file' in display:
    # Read HTML file if needed
    with open(f"results_fzd/{display['html_file']}") as f:
        html_content = f.read()
```

### Caching

Like `fzr`, you can use caching to avoid re-evaluation:

```python
result = fz.fzd(
    ...,
    calculators=["cache://_", "sh://"]  # Check cache first
)
```

## Tips and Best Practices

1. **Create or reuse algorithm files** - Check the `examples/` directory for algorithm implementations
2. **Start with random sampling** to understand the problem before using optimization
3. **Choose appropriate algorithms**: Use 1D optimization for single variables, multi-dimensional for multiple variables
4. **Tune convergence tolerances** based on your problem's requirements
5. **Monitor iterations** to ensure convergence
6. **Use output expressions** to combine multiple objectives
7. **Use metadata in algorithm files** to document default options
8. **Leverage calculators** for parallel/remote execution

## See Also

- [fzr Documentation](README.md#fzr) - For grid-based parameter sweeps
- [fzo Documentation](README.md#fzo) - For output parsing
- [Model Documentation](README.md#models) - For model creation
