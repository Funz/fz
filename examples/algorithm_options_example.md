# Algorithm Options - Multiple Format Support

This example demonstrates how to pass algorithm options in different formats to `fzd()`.

## Supported Formats

### 1. Dict (Direct)
```python
import fz

result = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",
    algorithm_options={"batch_size": 20, "max_iterations": 10, "seed": 42}
)
```

### 2. JSON String
```python
import fz

result = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",
    algorithm_options='{"batch_size": 20, "max_iterations": 10, "seed": 42}'
)
```

### 3. JSON File Path
```python
import fz

# Create options file
# File: algo_config.json
# {
#   "batch_size": 20,
#   "max_iterations": 10,
#   "seed": 42
# }

result = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="montecarlo",
    algorithm_options="algo_config.json"
)
```

## Benefits

### 1. **Reusability**
Store algorithm configurations in JSON files and reuse them across multiple runs:

```python
# Development config
fz.fzd(..., algorithm_options="dev_config.json")

# Production config with more iterations
fz.fzd(..., algorithm_options="prod_config.json")
```

### 2. **Version Control**
Track algorithm configurations separately from code:

```bash
git add configs/montecarlo_fast.json
git add configs/montecarlo_accurate.json
git commit -m "Add algorithm configurations"
```

### 3. **CLI Integration**
The CLI already supports all three formats via `--options`:

```bash
# Dict as JSON string
fzd input.txt --algorithm montecarlo \\
  --options '{"batch_size": 20, "max_iterations": 10}'

# JSON file
fzd input.txt --algorithm montecarlo \\
  --options algo_config.json
```

## Complex Options

JSON files support nested structures and complex data types:

```json
{
  "batch_size": 20,
  "max_iterations": 100,
  "tolerance": 1e-6,
  "bounds": {
    "x": [0, 10],
    "y": [0, 5]
  },
  "constraints": [
    {"type": "eq", "fun": "x + y - 10"}
  ],
  "verbose": true
}
```

```python
result = fz.fzd(
    input_path="input.txt",
    input_variables={"x": "[0;10]", "y": "[0;5]"},
    model="mymodel",
    output_expression="result",
    algorithm="optimization",
    algorithm_options="complex_config.json"
)
```

## Error Handling

The system provides clear error messages:

```python
# Invalid JSON string
algorithm_options='{"batch_size": 10, "max_iter": }'
# ❌ Error: Could not parse algorithm_options
#     - Invalid JSON: Expecting value: line 1 column 32

# Non-existent file
algorithm_options="missing.json"
# ❌ Error: Could not parse algorithm_options
#     - File issue: File not found: missing.json

# Wrong type (must be dict)
algorithm_options='[1, 2, 3]'
# TypeError: Algorithm options must be a dict
```

## Best Practices

1. **Use dicts for simple options**:
   ```python
   algorithm_options={"batch_size": 10, "seed": 42}
   ```

2. **Use JSON files for complex configurations**:
   ```python
   algorithm_options="configs/optimization_settings.json"
   ```

3. **Use JSON strings for CLI or dynamic generation**:
   ```python
   opts = json.dumps({"batch_size": batch, "seed": seed})
   algorithm_options=opts
   ```

4. **Version control your config files**:
   ```
   configs/
     ├── montecarlo_quick.json
     ├── montecarlo_accurate.json
     └── optimization_default.json
   ```
