# Development

## Running Tests

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_examples_perfectgaz.py -v

# Run with debug output
FZ_LOG_LEVEL=DEBUG python -m pytest tests/test_parallel_simple.py -v

# Run tests matching pattern
python -m pytest tests/ -k "parallel" -v

# Test interrupt handling
python -m pytest tests/test_interrupt_handling.py -v

# Run examples
python example_usage.py
python example_interrupt.py  # Interactive interrupt demo
```

## Project Structure

```
fz/
├── fz/                          # Main package
│   ├── __init__.py              # Public API exports
│   ├── core.py                  # Core functions (fzi, fzc, fzo, fzr, fzd)
│   ├── interpreter.py           # Variable parsing, formula evaluation
│   ├── runners/                 # Calculators, one module per backend (sh, ssh, slurm, funz, cache)
│   ├── helpers.py               # Parallel execution, retry logic
│   ├── io.py                    # File I/O, caching, hashing
│   ├── algorithms.py            # Algorithm framework for fzd
│   ├── shell.py                 # Shell utilities, binary path resolution
│   ├── logging.py               # Logging configuration
│   ├── cli.py                   # Command-line interface
│   └── config.py                # Configuration management
├── examples/                    # Example files
│   └── algorithms/              # Example algorithms for fzd
│       ├── montecarlo_uniform.py  # Monte Carlo sampling
│       ├── randomsampling.py      # Simple random sampling
│       ├── bfgs.py                # BFGS optimization
│       └── brent.py               # Brent's 1D optimization
├── tests/                       # Test suite
│   ├── test_parallel_simple.py  # Parallel execution tests
│   ├── test_interrupt_handling.py  # Interrupt handling tests
│   ├── test_fzd.py              # Design of experiments tests
│   ├── test_examples_*.py       # Example-based tests
│   └── ...
├── doc/                         # Modular user documentation
│   └── fzd_content_format.md    # fzd content format documentation
├── README.md                    # This file
└── pyproject.toml               # Package configuration
```

## Testing Your Own Models

Create a test following this pattern:

```python
import fz
import tempfile
from pathlib import Path

def test_my_model():
    # Create input
    with tempfile.TemporaryDirectory() as tmpdir:
        input_file = Path(tmpdir) / "input.txt"
        input_file.write_text("Parameter: $param\n")

        # Create calculator script
        calc_script = Path(tmpdir) / "calc.sh"
        calc_script.write_text("""#!/bin/bash
source $1
echo "result=$param" > output.txt
""")
        calc_script.chmod(0o755)

        # Define model
        model = {
            "varprefix": "$",
            "output": {
                "result": "grep 'result=' output.txt | cut -d= -f2"
            }
        }

        # Run test
        results = fz.fzr(
            str(input_file),
            {"param": [1, 2, 3]},
            model,
            calculators=f"sh://bash {calc_script}",
            results_dir=str(Path(tmpdir) / "results")
        )

        # Verify
        assert len(results) == 3
        assert list(results['result']) == [1, 2, 3]
        assert all(results['status'] == 'done')

        print("✅ Test passed!")

if __name__ == "__main__":
    test_my_model()
```
