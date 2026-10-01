# Interrupt Handling

FZ supports graceful interrupt handling for long-running calculations:

## How to Interrupt

Press **Ctrl+C** during execution:

```bash
python run_study.py
# ... calculations running ...
# Press Ctrl+C
⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
⚠️  Press Ctrl+C again to force quit (not recommended)
```

## What Happens

1. **First Ctrl+C**:
   - No new calculations start
   - Running local processes are terminated (killed after 5 s); remote and SLURM jobs
     are cancelled
   - Interrupted cases get `status="interrupted"`
   - `fzr` **returns** the DataFrame of partial results (no exception); the manifest
     records `interrupted: true`
   - Signal handlers restored

2. **Second Ctrl+C** (not recommended):
   - `KeyboardInterrupt` is raised immediately
   - May leave resources in inconsistent state

## Resuming After Interrupt

Use caching to resume from where you left off. To resume **into the same**
`results_dir`, use the special entry `cache://_` (the previous content of `results_dir`,
renamed with a timestamp before the run); `cache://results` with `results_dir="results"`
points to the new, empty directory and never hits.

```python
# First run (interrupted after 50/100 cases)
results1 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators="sh://bash calc.sh",
    results_dir="results"
)
print(f"Completed {len(results1)} cases before interrupt")

# Resume using cache
results2 = fz.fzr(
    "input.txt",
    {"param": list(range(100))},
    model,
    calculators=[
        "cache://results",      # Reuse completed cases
        "sh://bash calc.sh"     # Run remaining cases
    ],
    results_dir="results_resumed"
)
print(f"Total completed: {len(results2)} cases")
```

## Example with Interrupt Handling

```python
import fz
import signal
import sys

model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"}
}

def main():
    try:
        results = fz.fzr(
            "input.txt",
            {"param": list(range(1000))},  # Many cases
            model,
            calculators="sh://bash slow_calculation.sh",
            results_dir="results"
        )

        print(f"\n✅ Completed {len(results)} calculations")
        return results

    except KeyboardInterrupt:
        # This should rarely happen (graceful shutdown handles it)
        print("\n❌ Forcefully terminated")
        sys.exit(1)

if __name__ == "__main__":
    main()
```
