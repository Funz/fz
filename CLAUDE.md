# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**FZ** is a parametric scientific computing framework that automates:
- Parsing input files with variables and formulas
- Compiling input templates with parameter values
- Running calculations (locally or remotely via SSH) with parallel execution
- Graceful interrupt handling (Ctrl+C)
- Reading and parsing output results
- Smart caching and retry mechanisms

The five core functions are:
1. **`fzi`** - Parse input files to identify variables
2. **`fzc`** - Compile input files by substituting variables
3. **`fzo`** - Parse output files from calculations
4. **`fzr`** - Run complete parametric calculations end-to-end
5. **`fzd`** - Run iterative design of experiments with adaptive algorithms

## Development Setup

### Installation

```bash
# Clone and enter the repository
git clone https://github.com/Funz/fz.git
cd fz

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
pip install pandas  # Optional but recommended
```

### Common Commands

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_cli_commands.py -v

# Run tests matching pattern
python -m pytest tests/ -k "parallel" -v

# Run with debug output
FZ_LOG_LEVEL=DEBUG python -m pytest tests/ -v

# Check code style
flake8 fz/ --max-line-length=127

# Format code with black
black fz/ tests/

# Run single test
python -m pytest tests/test_cli_commands.py::test_fzi_parse_variables -v
```

## Architecture

The codebase is organized into functional modules (~7300 lines total):

### Core Modules

- **`fz/core.py`** (1277 lines) - Public API functions (`fzi`, `fzc`, `fzo`, `fzr`, `fzd`)
  - Entry points for all parametric computing operations
  - Orchestrates input compilation, calculation execution, and result parsing
  - Implements iterative design of experiments (`fzd`) with algorithm integration
  - Handles signal interruption and graceful shutdown

- **`fz/interpreter.py`** (387 lines) - Variable parsing and formula evaluation
  - Variable substitution with `${var}` syntax
  - Formula evaluation with Python or R interpreters
  - Support for default values: `${var~default}`
  - Multi-line function definitions in formulas

- **`fz/runners.py`** (1345 lines) - Calculator execution engines
  - **Local shell execution** (`sh://`) - runs commands in temporary directories
  - **SSH remote execution** (`ssh://`) - remote HPC/cluster support with file transfer
  - **Cache calculator** (`cache://`) - reuses previous results by input hash matching
  - Host key validation, authentication handling, timeout management

- **`fz/helpers.py`** (1405 lines) - Parallel execution and orchestration
  - Parallel case execution with thread pool management
  - Retry mechanism with fallback calculators
  - Case directory management and result organization
  - Windows bash detection and configuration
  - Temperature directory handling with preservation in DEBUG mode

- **`fz/io.py`** (238 lines) - File I/O and caching
  - Model and calculator alias loading from `.fz/models/` and `.fz/calculators/`
  - Hash-based cache matching (MD5 checksums in `.fz_hash` files)
  - Result directory parsing with automatic variable extraction
  - Output type casting (JSON → Python literals → numeric types)

- **`fz/config.py`** (209 lines) - Configuration management
  - Environment variable handling (`FZ_LOG_LEVEL`, `FZ_MAX_WORKERS`, `FZ_MAX_RETRIES`)
  - Interpreter selection (Python or R)
  - Default configuration values

- **`fz/logging.py`** (113 lines) - Logging setup
  - Structured logging with levels (DEBUG, INFO, WARNING, ERROR)
  - UTF-8 encoding handling for Windows

- **`fz/cli.py`** (509 lines) - Command-line interface
  - Entry points: `fz`, `fzi`, `fzc`, `fzo`, `fzr`, `fzd`
  - Argument parsing for all commands
  - Output formatting (JSON, table, CSV, markdown, HTML)

- **`fz/algorithms.py`** (513 lines) - Algorithm framework for design of experiments
  - Base interface for iterative algorithms used by `fzd`
  - Algorithm loading from Python files with dynamic import
  - Support for initial design, adaptive sampling, and result analysis
  - Automatic dependency checking (e.g., numpy, scipy)
  - Content detection for analysis results (HTML, JSON, Markdown, key-value)

- **`fz/shell.py`** (505 lines) - Shell utilities and binary path resolution
  - Cross-platform shell command execution with Windows bash detection
  - Binary path resolution with `FZ_SHELL_PATH` support
  - Caching of binary locations for performance
  - Windows .exe extension handling
  - Short path conversion for Windows paths with spaces

### Supporting Modules

- **`fz/spinner.py`** (225 lines) - Progress indication for long-running operations
- **`fz/installer.py`** (354 lines) - Model installation from GitHub/URL/zip

## Key Design Patterns

### 1. Signal-Safe Interrupt Handling
- Global `_shutdown_event` and `_original_sigint_handler` manage Ctrl+C gracefully
- Currently running calculations complete; no new ones start
- Partial results are preserved and saved
- `try_calculators_with_retry()` in helpers.py respects shutdown events

### 2. Model-Based Configuration
- Models define input parsing and output extraction as dictionaries:
  ```python
  model = {
      "varprefix": "$",
      "formulaprefix": "@",
      "delim": "{}",
      "commentline": "#",
      "interpreter": "python",  # or "R"
      "output": {
          "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
      }
  }
  ```
- Models can be stored as JSON in `.fz/models/` and referenced by name

### 3. Calculator Chaining
- Multiple calculators provide fallback and parallel execution
- Order matters: `["cache://prev_run", "sh://fast.sh", "sh://robust.sh"]`
- Each calculator is locked to one case at a time (thread-safe)
- Retry mechanism automatically tries next calculator on failure

### 4. Cartesian Product of Parameters
- Input variables with lists create all combinations: `{"a": [1, 2], "b": [3, 4]}` → 4 cases
- Results organized in directories: `a=1,b=3/`, `a=1,b=4/`, etc.
- Automatic parsing of variable values from directory names

### 5. Caching Strategy
- Input files hashed with MD5, stored in `.fz_hash` file
- Cache hit when input hash matches and outputs are not None
- Prevents redundant computation when resuming interrupted runs
- Glob patterns supported: `cache://archive/*/results`

### 6. Algorithm-Based Design of Experiments (fzd)
- **Iterative adaptive sampling**: Algorithms decide what points to evaluate next based on previous results
- **Algorithm interface**: Each algorithm class implements:
  - `get_initial_design()`: Returns initial design points
  - `get_next_design()`: Returns next points to evaluate (empty list when done)
  - `get_analysis()`: Returns final analysis results
  - `get_analysis_tmp()`: [Optional] Returns intermediate progress at each iteration
- **Flexible analysis output**: Algorithms can return text, HTML, JSON, Markdown, or key-value pairs
- **Content detection**: Automatically processes analysis results based on content type
- **Examples**: Monte Carlo sampling, BFGS optimization, Brent's method, random sampling
- **Requires pandas**: fzd returns results as pandas DataFrames

## Windows-Specific Considerations

### Bash Availability
- FZ requires bash for shell execution (`sh://` calculator)
- On Windows, checks for: Git Bash, MSYS2, WSL, Cygwin
- `get_windows_bash_executable()` in helpers.py locates bash
- Warns user at import time if no bash found
- See `BASH_REQUIREMENT.md` for detailed Windows bash setup

### UTF-8 Encoding
- Core.py monkey-patches `open()` for UTF-8 by default on Windows
- Reconfigures stdout/stderr to handle emoji output correctly

## Testing Strategy

### Test Organization
- All tests in `tests/` directory following pytest conventions
- Test files prefixed with `test_` (e.g., `test_cli_commands.py`)
- Use pytest fixtures in `conftest.py` for common setup
- Examples: `test_parallel.py`, `test_interrupt_handling.py`, `test_fzd.py`, `test_examples_*.py`

### Test Patterns
1. Create temporary directory with `tempfile.TemporaryDirectory()`
2. Write input template file
3. Define model dictionary
4. Call appropriate fz function (`fzi`, `fzc`, `fzo`, or `fzr`)
5. Assert results match expected behavior
6. Cleanup is automatic via context manager

### Running Tests
```bash
# Full test suite
python -m pytest tests/ -v

# Specific file
python -m pytest tests/test_parallel.py -v

# With coverage
pytest tests/ --cov=fz --cov-report=html
```

## Important Files & Patterns

### Model Definition Files
- Location: `.fz/models/` (project-level) or `~/.fz/models/` (global)
- Format: JSON files named `modelname.json`
- Example: `.fz/models/perfectgas.json`

### Calculator Aliases
- Location: `.fz/calculators/` or `~/.fz/calculators/`
- Format: JSON with `uri` and `models` properties
- Enables short names like `"local"` instead of `"sh://bash calc.sh"`

### Result Structure
Each case creates a directory with:
- `input.txt` - Compiled input file
- `output.txt` - Calculation output file
- `log.txt` - Execution metadata (command, exit code, timing, environment)
- `out.txt` - Standard output
- `err.txt` - Standard error
- `.fz_hash` - Input file MD5 hashes (for cache matching)

### Example Algorithms
- Location: `examples/algorithms/` directory
- Available algorithms:
  - **`montecarlo_uniform.py`** - Uniform random sampling for Monte Carlo integration
  - **`randomsampling.py`** - Simple random sampling with configurable iterations
  - **`bfgs.py`** - BFGS optimization algorithm (requires scipy)
  - **`brent.py`** - Brent's method for 1D optimization (requires scipy)
- Each algorithm demonstrates the standard interface and can serve as a template
- Algorithms can be referenced by file path: `algorithm="examples/algorithms/montecarlo_uniform.py"`

## Environment Variables

```bash
FZ_LOG_LEVEL=DEBUG|INFO|WARNING|ERROR    # Logging level
FZ_MAX_WORKERS=N                          # Parallel worker threads
FZ_MAX_RETRIES=N                          # Retry attempts per case
FZ_SSH_KEEPALIVE=seconds                  # SSH keepalive interval
FZ_SSH_AUTO_ACCEPT_HOSTKEYS=0|1           # Auto-accept SSH keys (use with caution)
FZ_INTERPRETER=python|R                   # Default formula interpreter
FZ_SHELL_PATH=path1:path2:...             # Custom shell binary search path (overrides system PATH)
```

### Shell Path Configuration (FZ_SHELL_PATH)

The `FZ_SHELL_PATH` environment variable allows you to override the system `PATH` for binary resolution in FZ operations. This is particularly useful on Windows where:

1. **Binary resolution in model output expressions** - Commands like `grep`, `awk`, `sed` in model output definitions are resolved using `FZ_SHELL_PATH`
2. **Binary resolution in shell calculators** - Commands in `sh://` calculator scripts are resolved using `FZ_SHELL_PATH`
3. **Windows .exe handling** - Automatically handles .exe extensions on Windows (e.g., `grep` resolves to `C:\msys64\usr\bin\grep.exe`)

#### Usage Examples

**On Windows with MSYS2:**
```bash
# Use semicolon separator on Windows
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin

# Now model output expressions will use MSYS2 binaries:
# Model: {"output": {"pressure": "grep 'pressure' output.txt | awk '{print $3}'"}}
# Will execute: C:\msys64\usr\bin\grep.exe 'pressure' output.txt | C:\msys64\usr\bin\awk.exe '{print $3}'
```

**On Windows with Git Bash:**
```bash
SET FZ_SHELL_PATH=C:\Program Files\Git\usr\bin;C:\Program Files\Git\bin
```

**On Unix/Linux (use colon separator):**
```bash
export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin
```

#### How It Works

1. **Configuration Loading**: `FZ_SHELL_PATH` is read from environment variables in `config.py`
2. **Binary Discovery**: The `ShellPathResolver` class in `shell_path.py` manages binary resolution with caching
3. **Command Resolution**: Commands in model output dicts and `sh://` calculators are automatically resolved to absolute paths
4. **Fallback Behavior**: If `FZ_SHELL_PATH` is not set, uses system `PATH` environment variable

#### Implementation Details

- **Module**: `fz/shell_path.py` - Provides `ShellPathResolver` class and global functions
- **Config Integration**: `config.py` loads `FZ_SHELL_PATH` environment variable
- **Core Integration**:
  - `core.py` (fzo function): Applies shell path resolution to model output commands
  - `runners.py` (run_local_calculation): Applies shell path resolution to sh:// commands
- **Caching**: Binary paths are cached after first resolution for performance
- **Windows Support**: Automatically tries both `command` and `command.exe` on Windows

#### Performance Considerations

- Binary paths are cached after first resolution
- Cache is cleared when config is reloaded with `reinitialize_resolver()`
- Use `FZ_SHELL_PATH` to prioritize specific tool versions or custom installations

## Code Style & Standards

### Style Guide
- **Max line length**: 127 characters (configured in flake8, pyproject.toml)
- **Black formatter**: Line length 88 (see pyproject.toml)
- **Docstring format**: Google-style with Args, Returns, Raises sections
- **Type hints**: Use throughout for clarity

### Required Docstrings
All public functions and methods must have docstrings with:
- Brief one-line description
- Longer description if needed
- Args and Returns sections
- Raises section for exceptions
- Example section if non-obvious

## Key Implementation Details

### Temporary Directory Management
- Created with `fz_temporary_directory()` context manager in helpers.py
- Each run gets unique directory: `.fz/tmp/fz_temp_<uuid>/`
- Preserved in DEBUG mode for inspection; otherwise cleaned up
- Prevents conflicts when running multiple cases in parallel

### Parallel Execution
- `run_cases_parallel()` in helpers.py uses `ThreadPoolExecutor`
- Round-robin distribution: case N goes to calculator N % num_calculators
- Thread-safe locking per calculator prevents concurrent use by same thread
- Progress tracking with ETA updates

### Formula Evaluation
- Python: Uses `exec()` with sandboxed namespace (functions, imported modules, variables)
- R: Uses rpy2 (optional dependency) for R interpreter
- Context (imports, functions, assignments) evaluated first
- Formulas evaluated with context namespace plus variable substitution

### SSH Execution
- Paramiko-based implementation in runners.py
- Automatic SFTP file transfer before and after execution
- Supports key-based or password authentication
- Host key validation with interactive fingerprint checking
- Timeout and keepalive configurable via environment

### Algorithm Loading and Execution (fzd)
- **Dynamic import**: Algorithms loaded from Python files using `importlib.machinery`
- **Dependency checking**: `__require__` list checked at load time; warns if missing
- **Fixed vs variable inputs**: Separates fixed values from ranges for optimization
  - Fixed: `{"x": "5.0"}` → always x=5.0
  - Variable: `{"y": "[0;10]"}` → y varies between 0 and 10
  - Algorithm only controls variable inputs; fixed values merged automatically
- **Analysis content processing**: Detects and processes multiple content types:
  - HTML: Saved to `analysis.html` and `iteration_N.html`
  - JSON: Parsed and made available as structured data
  - Markdown: Saved to `analysis.md` files
  - Key-value pairs: Parsed into dictionaries
- **Progress tracking**: Progress bar shows iteration count, evaluations, and ETA
- **Result structure**: Returns dict with:
  - `XY`: pandas DataFrame with all input and output values
  - `analysis`: Processed analysis results (HTML, plots, metrics, etc.) - excludes internal `_raw` data
  - `algorithm`: Algorithm path
  - `iterations`: Number of iterations completed
  - `total_evaluations`: Total number of function evaluations
  - `summary`: Human-readable summary text

## Common Development Tasks

### Adding a New Algorithm for fzd
1. Create a new Python file in `examples/algorithms/` or any directory
2. Implement a class with required methods:
   - `__init__(self, **options)` - Accept algorithm-specific options
   - `get_initial_design(self, input_vars, output_vars)` - Return initial design points
   - `get_next_design(self, previous_input_vars, previous_output_values)` - Return next points (or empty list when done)
   - `get_analysis(self, input_vars, output_values)` - Return final analysis results
   - `get_analysis_tmp(self, input_vars, output_values)` [Optional] - Return intermediate results
3. Add optional `__require__` list for dependencies (e.g., `["numpy", "scipy"]`)
4. Test with `fzd()` function
5. See `examples/algorithms/` for reference implementations

### Adding a New Calculator Type
1. Add runner function to `runners.py` following `_run_*_calculator()` pattern
2. Register in calculator resolution logic
3. Add tests in `tests/test_*.py`
4. Update README with usage examples

### Adding a New Interpreter
1. Implement in `interpreter.py` alongside Python evaluator
2. Update model schema to accept interpreter choice
3. Add tests for formula evaluation
4. Document in README

### Fixing Windows-Specific Issues
1. Check `BASH_REQUIREMENT.md` for bash availability
2. Test both direct bash and WSL paths
3. Handle path separators (`/` vs `\`)
4. Consider UTF-8 encoding edge cases

### Improving Performance
1. Profile with `FZ_LOG_LEVEL=DEBUG` to identify bottlenecks
2. Check `helpers.py` for thread pool sizing (FZ_MAX_WORKERS)
3. Optimize hash computation in `io.py` if handling many large files
4. Consider caching frequently accessed model/calculator configs

## Related Documentation

- **README.md** - User-facing documentation with examples
- **CONTRIBUTING.md** - Contributing guidelines and PR process
- **BASH_REQUIREMENT.md** - Windows bash setup requirements
- **WINDOWS_INTERRUPT_GUIDE.md** - Interrupt handling on Windows
- **examples/** - Example templates and usage scripts
