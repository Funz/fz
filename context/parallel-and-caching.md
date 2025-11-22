# FZ Parallel Execution and Caching

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

FZ caches results based on MD5 hashes of input files:

**Cache file** (`.fz_hash`):
```
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

**Cache matching**:
1. Compute hash of current input files
2. Search cache directories for matching `.fz_hash`
3. If match found and outputs are valid → reuse results
4. If no match → run calculation

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
