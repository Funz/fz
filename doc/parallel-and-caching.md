# FZ Parallel Execution and Caching

> **Contents**: the reference description comes first; the tutorial-style text that used to live in the README follows in the "Guide" sections below.




## Parallel Execution

### How Parallelization Works

FZ automatically parallelizes calculations when you provide multiple calculators or use environment variables to control worker threads.

**Key principles**:
- Each calculator can run one case at a time (thread-safe locking)
- Cases are distributed round-robin across calculators
- Progress tracking with ETA updates
- Graceful interrupt handling (Ctrl+C)

### Basic Parallel Execution

**Sequential** (1 calculator):
```python
results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300, 400, 500]},  # 5 cases
    model,
    calculators="sh://bash calc.sh",  # 1 worker → sequential
    results_dir="results"
)
# Runs one case at a time
```

**Parallel** (multiple calculators):
```python
results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300, 400, 500]},  # 5 cases
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ],  # 3 workers → parallel
    results_dir="results"
)
# Runs 3 cases concurrently
```

**Concise notation**:
```python
# Create N parallel workers
N = 4
calculators = ["sh://bash calc.sh"] * N

results = fz.fzr("input.txt", variables, model, calculators)
```

### Load Balancing

Cases are distributed round-robin:

```python
# 10 cases, 3 calculators
calculators = ["sh://calc.sh"] * 3

# Distribution:
# Calculator 0: cases 0, 3, 6, 9
# Calculator 1: cases 1, 4, 7
# Calculator 2: cases 2, 5, 8
```

### Controlling Parallelism

**Method 1: Number of calculators**
```python
# 8 parallel workers
calculators = ["sh://bash calc.sh"] * 8
```

**Method 2: Environment variable**
```python
import os
os.environ['FZ_MAX_WORKERS'] = '8'

# Or from shell:
# export FZ_MAX_WORKERS=8
```

**Method 3: Configuration**
```python
from fz import get_config

config = get_config()
config.max_workers = 8
```

### Optimal Number of Workers

**CPU-bound calculations**:
```python
import os

# Use number of CPU cores
num_cores = os.cpu_count()
calculators = ["sh://bash cpu_intensive.sh"] * num_cores
```

**I/O-bound calculations**:
```python
# Can use more workers than cores
calculators = ["sh://bash io_intensive.sh"] * (num_cores * 2)
```

**Memory considerations**:
```python
# Limit workers based on available memory
import psutil

available_memory_gb = psutil.virtual_memory().available / (1024**3)
memory_per_case_gb = 4  # Estimate memory per case
max_workers = int(available_memory_gb / memory_per_case_gb)

calculators = ["sh://bash calc.sh"] * max_workers
```

## Caching Strategies

### Cache Basics

FZ caches results based on SHA-256 hashes of the compiled input files:

**Cache file** (`.fz_hash`, versioned "v2" format):
```
# fz-hash v2
# code_id: telemac@v8p5
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

**Cache matching**:
1. Compute hash of current input files
2. Search cache directories for matching `.fz_hash`
3. If match found, outputs are valid, and the calculator's identity checks out (below) → reuse results
4. If no match → run calculation

Matching is by `.fz_hash` content, not by directory name, so it's unaffected by
`case_naming` (see core-functions.md → "fzr") — a `cache://` calculator still finds
matches whether the cache directory was written with `case_naming="path"`,
`"hash"`, or `"index"`.

The key deliberately does not include the calculator's command or host: the
exact same code can be invoked differently per calculator (a local script vs.
an absolute path over SSH), and requiring the same command would defeat the
point of sharing a cache across calculators. What it *does* check is the
calculator's declared **code identity** — see "Cache identity across
calculators (code_id)" below.

#### Cache identity across calculators (`code_id`)

A calculator alias (`.fz/calculators/<name>.json`, or an inline dict) may
declare an optional `code_id` naming its code installation, e.g.:

```json
{
    "uri": "ssh://user@cluster/bash /opt/telemac/v8p5/run.sh",
    "code_id": "telemac@v8p5"
}
```

- Two calculators declaring the **same** `code_id` share `cache://` results,
  regardless of their command.
- Two calculators declaring **different** `code_id`s never match, even with
  the identical command (different install paths on the same host can be
  different versions).
- With **no** `code_id` declared on either side, a match is still accepted
  (backward compatible) but logs a one-time warning per campaign; set
  `FZ_CACHE_STRICT=1` to refuse such unverifiable matches instead.
- Instead of hardcoding `code_id`, `version_cmd` resolves it by running a
  command on the calculator (once per calculator per session):
  `{"uri": "sh://bash ./run.sh", "version_cmd": "./run.sh --version"}`.
- A `.fz_hash` written by an older `fz` (no `# fz-hash v2` header, MD5) has no
  identity at all; it's ignored by `cache://` unless `FZ_CACHE_ACCEPT_LEGACY=1`.

### Strategy 1: Resume Interrupted Runs

```python
# First run (interrupted with Ctrl+C after 50/100 cases)
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators="sh://bash slow_calc.sh",
    results_dir="run1"
)
print(f"Completed {len(results)} cases")  # e.g., 50

# Resume from cache
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://run1",              # Check cache first
        "sh://bash slow_calc.sh"     # Run remaining 50 cases
    ],
    results_dir="run1_resumed"
)
print(f"Total: {len(results)} cases")  # 100
```

### Strategy 2: Expand Parameter Space

```python
# Initial study: 3×3 = 9 cases
results1 = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300], "pressure": [1, 10, 100]},
    model,
    calculators="sh://bash calc.sh",
    results_dir="study1"
)

# Expanded study: 5×5 = 25 cases (reuses 9, runs 16 new)
results2 = fz.fzr(
    "input.txt",
    {
        "temp": [100, 200, 300, 400, 500],
        "pressure": [1, 10, 100, 1000, 10000]
    },
    model,
    calculators=[
        "cache://study1",
        "sh://bash calc.sh"
    ],
    results_dir="study2"
)
```

### Strategy 3: Compare Multiple Methods

```python
# Method 1: Fast but approximate
fz.fzr("input.txt", variables, model, "sh://fast.sh", "results_fast/")

# Method 2: Slow but accurate (reuses same inputs)
fz.fzr(
    "input.txt",
    variables,
    model,
    "sh://accurate.sh",  # Different calculator, same inputs
    "results_accurate/"
)

# Compare results
import pandas as pd
df_fast = pd.read_csv("results_fast/summary.csv")
df_accurate = pd.read_csv("results_accurate/summary.csv")
comparison = pd.merge(df_fast, df_accurate, on=['temp', 'pressure'])
```

### Strategy 4: Multi-tier Caching

```python
calculators = [
    "cache://latest_run",           # Check most recent
    "cache://archive/2024-*",       # Check this year's archive
    "cache://archive/*/*",          # Check all archives
    "sh://bash calc.sh"             # Last resort: compute
]

results = fz.fzr("input.txt", variables, model, calculators)
```

### Strategy 5: Selective Recalculation

```python
# Run full study
fz.fzr("input.txt", variables, model, "sh://bash calc.sh", "run1/")

# Modify only the calculation script (not inputs)
# edit calc.sh...

# Re-run with different script but same inputs won't use cache
# because cache matches input files, not calculator
fz.fzr("input.txt", variables, model, "sh://bash calc_v2.sh", "run2/")

# To force re-calculation even with same inputs:
# Don't use cache calculator
fz.fzr("input.txt", variables, model, "sh://bash calc.sh", "run3/")
```

## Combining Parallel and Cache

### Pattern 1: Parallel with Cache Fallback

```python
calculators = [
    "cache://previous_run",
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh"
]
# First tries cache
# If cache miss, distributes across 4 parallel workers

results = fz.fzr("input.txt", variables, model, calculators)
```

### Pattern 2: Mixed Remote and Local with Cache

```python
calculators = [
    "cache://archive/*",                      # Try cache
    "ssh://user@fast-cluster/bash fast.sh",  # Fast remote
    "ssh://user@fast-cluster/bash fast.sh",  # Fast remote (parallel)
    "sh://bash local.sh",                     # Local fallback
    "ssh://user@robust-cluster/bash robust.sh"  # Robust remote
]

results = fz.fzr("input.txt", variables, model, calculators)
```

### Pattern 3: Staged Execution

```python
import os

# Stage 1: Quick screening (parallel)
results_quick = fz.fzr(
    "input.txt",
    {"param": list(range(1000))},  # 1000 cases
    model,
    calculators=["sh://bash quick.sh"] * os.cpu_count(),
    results_dir="stage1_quick"
)

# Stage 2: Detailed analysis of interesting cases (with cache)
interesting_params = results_quick[results_quick['result'] > threshold]['param']
results_detailed = fz.fzr(
    "input_detailed.txt",
    {"param": interesting_params.tolist()},
    model,
    calculators=[
        "cache://stage2_previous",  # Check previous detailed runs
        "sh://bash detailed.sh",
        "sh://bash detailed.sh"
    ],
    results_dir="stage2_detailed"
)
```

## Campaign manifest and RO-Crate (traceability)

Each `fzr()` run writes `<results_dir>/manifest.json` (schema `fz-manifest/1`):
fz/Python/platform versions, start/end times (UTC), the model and its SHA-256, the
calculators (credentials in URIs are masked as `user:***@host`), remote hosts, and
per case: path, status, calculator, input values and the SHA-256 of its `.fz_hash`.
`fzd()` writes a campaign-level `<analysis_dir>/manifest.json` (schema
`fz-manifest-fzd/1`: algorithm and options, input variables, output expression,
number of iterations, links to the per-iteration manifests). An RO-Crate 1.1
(`ro-crate-metadata.json`) referencing the manifest is written next to each manifest;
set `FZ_RO_CRATE=0` to disable it. A failure to write either file only logs a warning.

## Retry Mechanism

### Basic Retry

FZ automatically retries failed calculations:

```python
import os
os.environ['FZ_MAX_RETRIES'] = '3'

calculators = [
    "sh://bash may_fail.sh",
    "sh://bash backup.sh"
]

results = fz.fzr("input.txt", variables, model, calculators)
```

**Retry behavior**:
- Attempt 1: Try `may_fail.sh`
- If fails → Attempt 2: Try `backup.sh`
- If fails → Attempt 3: Try `may_fail.sh` again
- If fails → Attempt 4: Try `backup.sh` again
- If fails → Give up, mark as failed

### Retry with Different Methods

```python
calculators = [
    "sh://bash fast_method.sh",      # Fast, may fail
    "sh://bash robust_method.sh",    # Slower, more reliable
    "ssh://user@hpc/bash hpc.sh"     # Expensive, very reliable
]

os.environ['FZ_MAX_RETRIES'] = '5'

results = fz.fzr("input.txt", variables, model, calculators)

# Check retry statistics
print(results[['status', 'calculator', 'error']].value_counts())
```

## Interrupt Handling

### Graceful Shutdown

Press **Ctrl+C** during execution:

```python
results = fz.fzr(
    "input.txt",
    {"param": list(range(1000))},  # Many cases
    model,
    calculators=["sh://bash calc.sh"] * 4,
    results_dir="results"
)
# Press Ctrl+C...
# ⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
# Currently running cases complete
# No new cases start
```

**What happens**:
1. Currently running cases finish
2. No new cases start
3. Partial results are saved
4. Can resume from cache later

### Resume After Interrupt

```python
# First run (interrupted)
try:
    results = fz.fzr(
        "input.txt",
        variables,
        model,
        "sh://bash calc.sh",
        "run1"
    )
except KeyboardInterrupt:
    print("Interrupted, partial results saved")

# Resume
results = fz.fzr(
    "input.txt",
    variables,
    model,
    ["cache://run1", "sh://bash calc.sh"],
    "run1_resumed"
)
```

## Performance Optimization

### 1. Profile to Find Bottlenecks

```python
import os
import time

os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

start = time.time()
results = fz.fzr("input.txt", variables, model, calculators)
elapsed = time.time() - start

print(f"Total time: {elapsed:.2f}s")
print(f"Time per case: {elapsed/len(results):.2f}s")
```

### 2. Optimize Calculator Count

```python
import time

def benchmark_workers(n_workers):
    start = time.time()
    fz.fzr(
        "input.txt",
        {"param": list(range(100))},
        model,
        ["sh://bash calc.sh"] * n_workers,
        f"benchmark_{n_workers}_workers"
    )
    return time.time() - start

# Find optimal number of workers
for n in [1, 2, 4, 8, 16]:
    elapsed = benchmark_workers(n)
    print(f"{n} workers: {elapsed:.2f}s")
```

### 3. Use Fast Calculators First

```python
# Good: fast methods first
calculators = [
    "cache://previous",              # Instant if cache hit
    "sh://bash fast.sh",             # Fast method
    "sh://bash medium.sh",           # Medium speed
    "ssh://user@hpc/bash slow.sh"   # Slow but robust
]

# Bad: slow methods first
calculators = [
    "ssh://user@hpc/bash slow.sh",  # Tries slow method first
    "sh://bash fast.sh"
]
```

### 4. Batch Similar Cases

```python
# Group cases by computational cost
light_cases = {"mesh": [10, 20, 30]}
heavy_cases = {"mesh": [1000, 2000, 3000]}

# Run light cases locally
results_light = fz.fzr(
    "input.txt",
    light_cases,
    model,
    ["sh://bash calc.sh"] * 8,  # Many local workers
    "results_light"
)

# Run heavy cases on HPC
results_heavy = fz.fzr(
    "input.txt",
    heavy_cases,
    model,
    "ssh://user@hpc/sbatch heavy.sh",
    "results_heavy"
)

# Combine results
import pandas as pd
results = pd.concat([results_light, results_heavy])
```

### 5. Clean Old Caches

```bash
# Remove old result directories to save disk space
find results/ -type d -mtime +30 -exec rm -rf {} \;

# Keep only .fz_hash files for cache matching
find results/ -type f ! -name '.fz_hash' -delete
```

## Monitoring Progress

### Built-in Progress Tracking

FZ shows progress automatically:
```
Running calculations... [████████░░░░░░░░] 45/100 (45.0%) - ETA: 2m 30s
```

### Check Results During Execution

```python
# In one terminal: run calculations
results = fz.fzr("input.txt", variables, model, calculators, "results/")

# In another terminal: monitor progress
import os
completed = len([d for d in os.listdir("results/") if os.path.isdir(f"results/{d}")])
print(f"Completed: {completed} cases")
```

### Analyze Partial Results

```python
# While calculations are running, parse completed cases
partial_results = fz.fzo("results/*", model)
print(f"Completed so far: {len(partial_results)} cases")
print(partial_results.head())
```

---

## Guide: Advanced Features



### Parallel Execution

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

### Retry Mechanism

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

### Caching Strategy

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

### Output Type Casting

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

### Vector (array) Outputs

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

### Progress Callbacks

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

---

## Guide: Performance Tips

1. **Use caching**: Reuse previous results when possible
2. **Limit parallelism**: Don't exceed your CPU/memory limits
3. **Optimize calculators**: Fast calculators first in the list
4. **Batch similar cases**: Group cases that use the same calculator
5. **Use SSH keepalive**: For long-running remote calculations
6. **Clean old results**: Remove old result directories to save disk space
