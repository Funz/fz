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
   - Currently running calculations complete
   - No new calculations start
   - Partial results are saved
   - Resources are cleaned up
   - Signal handlers restored

2. **Second Ctrl+C** (not recommended):
   - Immediate termination
   - May leave resources in inconsistent state

## Resuming After Interrupt

Use caching to resume from where you left off:

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
