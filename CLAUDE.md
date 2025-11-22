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

The four core functions are:
1. **`fzi`** - Parse input files to identify variables
2. **`fzc`** - Compile input files by substituting variables
3. **`fzo`** - Parse output files from calculations
4. **`fzr`** - Run complete parametric calculations end-to-end

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

The codebase is organized into functional modules (~5700 lines total):

### Core Modules

- **`fz/core.py`** (913 lines) - Public API functions (`fzi`, `fzc`, `fzo`, `fzr`)
  - Entry points for all parametric computing operations
  - Orchestrates input compilation, calculation execution, and result parsing
  - Handles signal interruption and graceful shutdown

- **`fz/interpreter.py`** (387 lines) - Variable parsing and formula evaluation
  - Variable substitution with `${var}` syntax
  - Formula evaluation with Python or R interpreters
  - Support for default values: `${var~default}`
  - Multi-line function definitions in formulas

- **`fz/runners.py`** (~1800 lines) - Calculator execution engines
  - **Local shell execution** (`sh://`) - runs commands in temporary directories
  - **SSH remote execution** (`ssh://`) - remote HPC/cluster support with file transfer
  - **Funz server execution** (`funz://`) - connects to legacy Java Funz calculator servers via TCP socket protocol
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

- **`fz/cli.py`** (395 lines) - Command-line interface
  - Entry points: `fz`, `fzi`, `fzc`, `fzo`, `fzr`
  - Argument parsing for all commands
  - Output formatting (JSON, table, CSV, markdown, HTML)

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
- Examples: `test_parallel.py`, `test_interrupt_handling.py`, `test_examples_*.py`

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

## Common Development Tasks

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
