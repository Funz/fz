# Advanced Features

## Parallel Execution

FZ automatically parallelizes when you have multiple cases and calculators:

```python
# Sequential: 1 calculator, 10 cases → runs one at a time
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators="sh://bash calc.sh"
)

# Parallel: 3 calculators, 10 cases → 3 concurrent
results = fz.fzr(
    "input.txt",
    {"temp": list(range(10))},
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ]
)

# Control parallelism with environment variable
import os
os.environ['FZ_MAX_WORKERS'] = '4'

# Or use duplicate calculator URIs
calculators = ["sh://bash calc.sh"] * 4  # 4 parallel workers
```

**Load Balancing**:
- Round-robin distribution of cases to calculators
- Thread-safe calculator locking
- Automatic retry on failures
- Progress tracking with ETA

## Retry Mechanism

Automatic retry on calculation failures:

```python
import os
os.environ['FZ_MAX_RETRIES'] = '3'  # Try each case up to 3 times

results = fz.fzr(
    "input.txt",
    input_variables,
    model,
    calculators=[
        "sh://unreliable_calc.sh",  # Might fail
        "sh://backup_calc.sh"        # Backup method
    ]
)
```

**Retry Strategy**:
1. Try first available calculator
2. On failure, try next calculator
3. Repeat up to `FZ_MAX_RETRIES` times
4. Report all attempts in logs

## Caching Strategy

Intelligent result reuse:

```python
# First run
results1 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30]},
    model,
    calculators="sh://expensive_calc.sh",
    results_dir="run1"
)

# Add more cases - reuse previous results
results2 = fz.fzr(
    "input.txt",
    {"temp": [10, 20, 30, 40, 50]},  # 2 new cases
    model,
    calculators=[
        "cache://run1",              # Check cache first
        "sh://expensive_calc.sh"     # Only run new cases
    ],
    results_dir="run2"
)
# Only runs calculations for temp=40 and temp=50
```

## Output Type Casting

Automatic type conversion:

```python
model = {
    "output": {
        "scalar_int": "echo 42",
        "scalar_float": "echo 3.14159",
        "array": "echo '[1, 2, 3, 4, 5]'",
        "single_array": "echo '[42]'",  # → 42 (simplified)
        "json_object": "echo '{\"key\": \"value\"}'",
        "string": "echo 'hello world'"
    }
}

results = fz.fzo("output_dir", model)
# Values automatically cast to int, float, list, dict, or str
```

**Casting Rules**:
1. Try JSON parsing
2. Try Python literal evaluation
3. Try numeric conversion (int/float)
4. Keep as string
5. Single-element arrays → scalar

## Vector (array) Outputs

An output entry does not have to be a single number: `python://`, `jq://`,
`yq://` and plain shell commands can all return a full list (a time series, a
per-node profile, a spectrum...), which lands in the results DataFrame as one
Python list per case — `fzr`/`fzo` never flatten, truncate or pad vector
outputs, and cases are free to produce vectors of different lengths:

```python
model = {
    "output": {
        # whole JSON array file -> plain Python list
        "T_series": "python://json_file('series.json')",
        # every regex match -> list
        "T_series_grep": "python://grep(r'T=(\S+)', 'log.txt', all=True)",
        # jq/yq filter selecting an array
        "T_series_jq": "jq://.temperatures results.json",
        # xpath:// returns a list too when the expression matches more
        # than one XML node (e.g. several <value> siblings)
        "T_series_xpath": "xpath://'//value/text()' output.xml",
    }
}
```

Note the single-element-array simplification above (rule 5) only applies to
the legacy plain-shell-command form; it does not apply to `python://`,
`jq://`, `yq://` or `xpath://` outputs, so a length-1 vector stays a
one-element list with those forms. See `examples/vector_outputs_example.md`
and `doc/model-definition.md` ("output" → "Vector / array outputs") for more.

## Progress Callbacks

Monitor execution progress in real-time with custom callback functions:

```python
import fz

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

# Define callback function
def progress_callback(event_type, case_info):
    """
    Called during execution for each case event.

    Args:
        event_type: One of "case_start", "case_complete", "case_failed"
        case_info: Dict with case details (case_name, calculator, etc.)
    """
    if event_type == "case_start":
        print(f"⏳ Starting: {case_info['case_name']}")
    elif event_type == "case_complete":
        print(f"✅ Completed: {case_info['case_name']}")
    elif event_type == "case_failed":
        print(f"❌ Failed: {case_info['case_name']} - {case_info.get('error', 'Unknown error')}")

# Run with callback
results = fz.fzr(
    "input.txt",
    {"param": [1, 2, 3, 4, 5]},
    model,
    calculators="sh://bash calc.sh",
    results_dir="results",
    callbacks=[progress_callback]
)
```

**Use Cases**:
- Custom progress bars
- Real-time logging and monitoring
- Integration with external monitoring systems
- UI updates for long-running calculations
- Performance profiling

**Multiple Callbacks**:
```python
def logger_callback(event_type, case_info):
    # Log to file
    with open("execution.log", "a") as f:
        f.write(f"{event_type}: {case_info}\n")

def metrics_callback(event_type, case_info):
    # Send to monitoring system
    send_to_prometheus(event_type, case_info)

results = fz.fzr(..., callbacks=[logger_callback, metrics_callback])
```
