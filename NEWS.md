# FZ Release Notes

## Version 0.9.1 (2026-01-25)

### New Features

#### `fzl` Command - List and Validate Models/Calculators
- **New CLI command**: `fzl` (or `fz list`) for listing and validating installed models and calculators
- Supports glob patterns for filtering: `fzl --models "perfect*" --calculators "ssh*"`
- Validation mode with `--check` flag to verify model/calculator integrity
- Multiple output formats: JSON, Markdown (default), Table
- Shows supported calculators for each model
- Example usage:
  ```bash
  fzl --models "*" --calculators "*" --check --format markdown
  ```

#### Enhanced Calculator Support

**SLURM Workload Manager Integration**
- New calculator type: `slurm://[user@host[:port]]:partition/script`
- Supports both local and remote SLURM execution
- Local: `slurm://:compute/bash script.sh`
- Remote: `slurm://user@cluster.edu:gpu/bash script.sh`
- Automatic partition scheduling and job management
- Interrupt handling (Ctrl+C terminates SLURM jobs)

**Funz Server Protocol Support**
- New calculator type: `funz://[host]:<port>/<code>`
- Compatible with legacy Java Funz calculator servers
- TCP socket-based communication with reservation/unreservation
- Automatic file upload/download
- UDP discovery support for automatic server detection
- Example: `funz://:5555/R` or `funz://server.example.com:5555/Python`
- See `FUNZ_UDP_DISCOVERY.md` for detailed protocol documentation

#### Shell Path Configuration (FZ_SHELL_PATH)
- **New environment variable**: `FZ_SHELL_PATH` for custom binary resolution
- Overrides system PATH for shell commands in models and calculators
- Essential for Windows users with MSYS2, Git Bash, or custom tool locations
- Format: Semicolon-separated on Windows, colon-separated on Unix/Linux
- Example: `SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin`
- Automatic `.exe` extension handling on Windows
- Binary path caching for performance
- See `SHELL_PATH_IMPLEMENTATION.md` for implementation details

#### R Interpreter Support
- **Formula evaluation with R**: Set interpreter to "R" for statistical computing
- Configure via `model["interpreter"] = "R"` or `set_interpreter("R")`
- Supports R statistical functions: `mean()`, `sd()`, `median()`, `rnorm()`, etc.
- Multi-line R function definitions in formula context
- Requires `rpy2` package and R system installation
- Example:
  ```text
  #@ samples <- rnorm($n, mean=$mu, sd=$sigma)
  Mean: @{mean(samples)}
  ```
- See `examples/r_interpreter_example.md` for installation guide

#### Variable Default Values
- **New syntax**: `${var~default}` for specifying default values
- Falls back to default when variable not provided in `input_variables`
- Useful for configuration templates with sensible defaults
- Example: `${host~localhost}`, `${port~8080}`
- Warning issued when default value is used
- See `examples/variable_substitution.md` for comprehensive documentation

#### Old Funz Syntax Compatibility
- Support for legacy Java Funz variable syntax: `?var` (equivalent to `$var`)
- Backward compatibility for existing Funz users migrating to Python
- Automatic detection and replacement
- Example: `Temperature: ?T_celsius` → `Temperature: 25`

#### Progress Callbacks
- **New callback system** for monitoring execution progress
- Callback functions receive events: `case_start`, `case_complete`, `case_failed`
- Real-time progress tracking for long-running calculations
- Custom progress bars, logging, or UI updates
- Example:
  ```python
  def progress_callback(event_type, case_info):
      if event_type == "case_complete":
          print(f"✓ Case {case_info['case_name']} done")
  
  fzr(..., callbacks=[progress_callback])
  ```

### Improvements

#### Enhanced Argument Parsing
- CLI arguments now support three formats:
  1. **Inline JSON**: `--model '{"varprefix": "$"}'`
  2. **JSON file**: `--model model.json`
  3. **Alias**: `--model perfectgas` (loads from `.fz/models/perfectgas.json`)
- Automatic detection with fallback and helpful error messages
- Better type validation with detailed warnings
- Consistent behavior across all CLI commands

#### Calculator-Model Compatibility
- Automatic validation that calculators support specified models
- Prevents incompatible calculator/model combinations
- Clear error messages when model not supported by calculator
- Alias resolution for both models and calculators

#### Timeout Configuration
- Flexible timeout settings at multiple levels:
  - Environment variable: `FZ_EXECUTION_TIMEOUT`
  - Model configuration: `model["timeout"]`
  - Calculator URI: `sh://script.sh?timeout=300`
- Per-calculator timeout overrides
- Default timeout handling for long-running calculations

#### Better Error Handling
- Comprehensive error messages with context
- Automatic help display on TypeError (missing/wrong arguments)
- Detailed warnings for argument parsing failures
- Stack trace preservation for debugging

#### Code Quality & Sanitization
- Extensive code cleanup and refactoring
- Improved type hints and docstrings
- Better separation of concerns
- Enhanced test coverage (100+ new tests)
- Fixed unsafe bash command replacement vulnerabilities

### Testing & CI

#### New Test Suites
- `test_funz_protocol.py` - Comprehensive Funz protocol tests (TCP/UDP)
- `test_funz_integration.py` - End-to-end Funz server integration
- `test_slurm_runner.py` - SLURM workload manager tests
- `test_shell_path.py` - Shell path resolution tests
- `test_interpreter_r.py` - R interpreter tests
- `test_interpreter_default_values.py` - Default value substitution tests
- `test_calculator_discovery.py` - Calculator/model discovery tests
- `test_callbacks.py` - Progress callback tests
- `test_no_*.py` - Edge case tests (no models, no calculators, no formulas, etc.)

#### CI/CD Enhancements
- GitHub Actions workflow for SLURM testing
- Funz calculator integration CI workflow
- Windows CI improvements with better error handling
- More robust test fixtures and cleanup

### Documentation

#### New Documentation Files
- `FUNZ_UDP_DISCOVERY.md` - Funz protocol and UDP discovery guide
- `SHELL_PATH_IMPLEMENTATION.md` - Shell path configuration details
- `CLAUDE.md` - LLM-friendly codebase documentation
- `context/` directory - Modular documentation for different aspects:
  - `INDEX.md` - Documentation overview
  - `core-functions.md` - API reference for fzi, fzc, fzo, fzr
  - `calculators.md` - Calculator types and configuration
  - `model-definition.md` - Model structure and aliases
  - `formulas-and-interpreters.md` - Formula evaluation guide
  - `parallel-and-caching.md` - Performance optimization
  - `quick-examples.md` - Common usage patterns
  - `syntax-guide.md` - Input template syntax reference

#### Updated Documentation
- README.md - Added sections for:
  - FZ_SHELL_PATH configuration
  - R interpreter support
  - Variable default values
  - SLURM calculator usage
  - Funz server integration
  - Progress callbacks
  - Old Funz syntax compatibility
- Examples:
  - `examples/r_interpreter_example.md` - R setup and usage
  - `examples/variable_substitution.md` - Default values guide
  - `examples/shell_path_example.md` - Shell path configuration
  - `examples/java_funz_syntax_example.py` - Legacy syntax examples
  - `examples/fzi_formulas_example.py` - Formula evaluation examples
  - `examples/fzi_static_objects_example.py` - Static object examples

### Bug Fixes

- Fixed Windows path separator handling in file operations
- Fixed unsafe bash command string replacement (security issue)
- Fixed PATH environment variable not respecting FZ_SHELL_PATH priority
- Fixed SLURM URI parsing for local execution (`:partition` prefix required)
- Fixed scalar value result extraction in various contexts
- Fixed calculator XML configuration for Funz integration
- Fixed missing JSON files during model/plugin installation
- Fixed OSError handling in Windows script execution
- Fixed R interpreter initialization and expression evaluation
- Fixed cache matching when outputs are None
- Fixed directory structure creation when no input variables specified

### Breaking Changes

- **fzr directory structure**: Now creates subdirectories in `results_dir` as long as any `input_variable` is set up
  - No subdirectories only when `input_variables={}`
  - More consistent with user expectations
  - Better organization for parametric studies

### Deprecations

None in this release.

---

## Version 0.9.0 (Initial Release)

### Core Features

- Four core functions: `fzi`, `fzc`, `fzo`, `fzr`
- Command-line interface with dedicated commands
- Parametric study automation with Cartesian product
- Parallel execution with thread pool
- Smart caching based on input file hashes
- Retry mechanism with calculator fallback
- Remote execution via SSH
- Interrupt handling (Ctrl+C) with graceful shutdown
- DataFrame output with automatic type casting
- Formula evaluation with Python interpreter
- Model and calculator aliases
- Comprehensive test suite
- BSD 3-Clause License

### Calculator Types

- Local shell execution (`sh://`)
- SSH remote execution (`ssh://`)
- Cache calculator (`cache://`)

### Model Definition

- Variable substitution with `$var` syntax
- Formula evaluation with `@{expression}` syntax
- Comment-based formula context
- Output command specification
- Model aliasing with JSON files

### Installation

- PyPI package: `funz-fz`
- pipx support for CLI tools
- Optional dependencies: `paramiko`, `pandas`

---

For detailed information, see:
- README.md - User guide and examples
- CLAUDE.md - Developer documentation
- context/ - Modular documentation by topic
