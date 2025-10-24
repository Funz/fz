# FZ_SHELL_PATH Implementation Summary

## Overview

Implemented a comprehensive shell path configuration system for FZ that allows users to override the system `PATH` environment variable for binary resolution. This is particularly useful on Windows where Unix-like tools (grep, awk, sed, etc.) need to be found in custom locations like MSYS2, Git Bash, or user-defined paths.

## Key Features

### 1. Configuration Management
- **New environment variable**: `FZ_SHELL_PATH` - allows users to specify custom binary search paths
- **Path format**: Semicolon-separated on Windows (`;`), colon-separated on Unix/Linux (`:`)
- **Fallback**: If not set, uses system `PATH` environment variable
- **Integration**: Fully integrated into `fz/config.py` with proper configuration loading

### 2. Binary Resolution System
- **New module**: `fz/shell_path.py` - Implements `ShellPathResolver` class
- **Features**:
  - Resolves command names to absolute paths
  - Caches resolved paths for performance
  - Windows .exe extension handling (automatically tries both `cmd` and `cmd.exe`)
  - Lists available binaries in configured paths
  - Replaces command names in shell command strings with absolute paths

### 3. Integration Points

#### Model Output Expressions (fzo function)
- **File**: `fz/core.py`
- **Integration**: Output commands in model definitions are automatically resolved
- **Example**:
  ```python
  model = {"output": {"value": "grep 'pattern' output.txt | awk '{print $2}'"}}
  # With FZ_SHELL_PATH=/msys64/usr/bin, executes:
  # /msys64/usr/bin/grep.exe 'pattern' output.txt | /msys64/usr/bin/awk.exe '{print $2}'
  ```

#### Shell Calculator Commands (sh://)
- **File**: `fz/runners.py`
- **Integration**: Commands in `sh://` calculator URIs are resolved
- **Example**:
  ```python
  calculators=["sh://grep 'result' data.txt | awk '{print $2}'"]
  # Commands are resolved using FZ_SHELL_PATH
  ```

### 4. Testing
- **Test file**: `tests/test_shell_path.py`
- **Coverage**:
  - ShellPathResolver initialization and caching
  - Path resolution on Windows and Unix
  - Windows .exe extension handling
  - Command string replacement
  - Configuration integration
  - Global resolver instance management
- **Test count**: 20 passed, 1 skipped
- **All core tests pass**: Verified with `test_cli_commands.py` and `test_examples_advanced.py`

### 5. Documentation
- **CLAUDE.md**: Updated with comprehensive FZ_SHELL_PATH documentation
  - Usage examples for MSYS2, Git Bash, and Unix/Linux
  - How the system works
  - Implementation details
  - Performance considerations
- **Examples**: New `examples/shell_path_example.md` with practical use cases

## Files Modified

1. **fz/config.py**
   - Added `shell_path` attribute to Config class
   - Load `FZ_SHELL_PATH` from environment
   - Include in config summary display

2. **fz/shell_path.py** (NEW)
   - `ShellPathResolver` class with full functionality
   - Global resolver instance management
   - Binary discovery and caching

3. **fz/core.py**
   - Import shell path resolution module
   - Apply command resolution in fzo() function (both with and without subdirectories)
   - Two locations: subdirectory case (line 556) and single directory case (line 592)

4. **fz/runners.py**
   - Import shell path resolution module
   - Apply command resolution in run_local_calculation() function (line 665)

5. **CLAUDE.md**
   - New "Shell Path Configuration" section (lines 234-285)
   - Usage examples and implementation details
   - Windows-specific guidance

6. **tests/test_shell_path.py** (NEW)
   - Comprehensive test suite for shell path functionality
   - Tests for Windows and Unix platforms
   - Configuration integration tests

7. **examples/shell_path_example.md** (NEW)
   - Practical usage examples
   - Troubleshooting guide
   - Common use cases

## Implementation Details

### ShellPathResolver Class

```python
class ShellPathResolver:
    def __init__(self, custom_shell_path: Optional[str]):
        # Initialize with custom path or None

    def get_search_paths(self) -> List[str]:
        # Returns list of directories to search

    def resolve_command(self, command: str) -> Optional[str]:
        # Resolves command name to absolute path with caching

    def list_available_binaries(self) -> List[str]:
        # Lists all available binaries in search paths

    def replace_commands_in_string(self, command_string: str) -> str:
        # Replaces command names with absolute paths in shell commands
```

### Global Functions

- `get_resolver()` - Get global resolver instance
- `resolve_command(command)` - Resolve single command
- `replace_commands_in_string(command_string)` - Replace commands in string
- `reinitialize_resolver()` - Reset resolver after config reload

### Platform Support

- **Windows**:
  - Semicolon-separated paths
  - Automatic .exe extension handling
  - Short path (8.3) format support for paths with spaces

- **Unix/Linux**:
  - Colon-separated paths
  - Standard executable permission checking

## Usage

### Setting FZ_SHELL_PATH

**Windows Command Prompt:**
```cmd
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
fz input.txt -m mymodel
```

**Windows PowerShell:**
```powershell
$env:FZ_SHELL_PATH = "C:\msys64\usr\bin;C:\msys64\mingw64\bin"
fz input.txt -m mymodel
```

**Unix/Linux Bash:**
```bash
export FZ_SHELL_PATH=/opt/tools/bin:/usr/local/bin
fz input.txt -m mymodel
```

### Programmatic Usage

```python
from fz import fzr
from fz.config import Config
from fz.shell_path import reinitialize_resolver

# Set custom shell path
import os
os.environ['FZ_SHELL_PATH'] = '/opt/custom/bin'

# Reinitialize resolver to pick up new path
reinitialize_resolver()

# Now use fz functions with custom paths
results = fzr("input.txt", variables, model, calculators)
```

## Benefits

1. **Consistency**: Ensure all team members use the same tool versions
2. **Portability**: Don't rely on system PATH which varies across machines
3. **Windows Compatibility**: Seamlessly handle multiple bash environments on Windows
4. **Performance**: Binary paths are cached after first lookup
5. **Flexibility**: Can prioritize custom tool installations over system tools
6. **Backward Compatible**: Works alongside existing code without breaking changes

## Testing Results

```
tests/test_shell_path.py::TestShellPathResolver - 12 tests PASSED
tests/test_shell_path.py::TestGlobalResolver - 3 tests PASSED
tests/test_shell_path.py::TestConfigIntegration - 3 tests PASSED
tests/test_shell_path.py::TestWindowsPathResolution - 2 tests PASSED
tests/test_cli_commands.py - 46 tests PASSED, 3 SKIPPED
tests/test_examples_advanced.py - All tests PASSED
```

## Future Enhancements (Optional)

1. Add Windows registry scanning for tool installations
2. Support for tool version detection and selection
3. Per-calculator shell path configuration
4. Binary aliasing (e.g., gawk → awk)
5. Shell path validation utility command

## Backward Compatibility

✅ **Fully backward compatible**
- Existing code works unchanged
- `FZ_SHELL_PATH` is optional
- Falls back to system `PATH` if not set
- No changes to public APIs beyond new functions in `shell_path` module

## Documentation Status

✅ Complete
- Code comments and docstrings throughout
- CLAUDE.md documentation with examples
- Example file with use cases
- Inline comments for complex logic
- Type hints on all functions
