# Shell Path Configuration (FZ_SHELL_PATH)

## Overview

The `FZ_SHELL_PATH` environment variable allows you to specify custom locations for shell binaries (grep, awk, sed, cut, tr, etc.) used in model output expressions and calculator commands. This is essential for cross-platform compatibility, especially on Windows where Unix-like tools may be installed in non-standard locations.

## Why FZ_SHELL_PATH?

### Problems It Solves

1. **Windows Compatibility**: Unix tools on Windows are often in custom locations (MSYS2, Git Bash, Cygwin, WSL)
2. **Consistency**: Ensures all team members use the same tool versions
3. **Portability**: Scripts work across different environments without PATH dependencies
4. **Priority Control**: Override system PATH to use specific tool versions
5. **Performance**: Binary paths are cached after first resolution

### Without FZ_SHELL_PATH

```python
# Model with shell commands - may fail on Windows
model = {
    "output": {
        "pressure": "grep 'pressure' output.txt | awk '{print $2}'"
    }
}

# ❌ Problem: Where is grep? Where is awk?
# - Windows: C:\Program Files\Git\usr\bin\grep.exe?
# - Windows: C:\msys64\usr\bin\grep.exe?
# - Linux: /usr/bin/grep?
```

### With FZ_SHELL_PATH

```bash
# Windows
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin

# Linux/macOS
export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin
```

Now FZ knows exactly where to find tools!

## Usage

### Environment Variable Setup

**Windows Command Prompt:**
```cmd
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
```

**Windows PowerShell:**
```powershell
$env:FZ_SHELL_PATH = "C:\msys64\usr\bin;C:\msys64\mingw64\bin"
```

**Linux/macOS Bash:**
```bash
export FZ_SHELL_PATH=/opt/tools/bin:/usr/local/bin:/usr/bin
```

**Python:**
```python
import os
os.environ['FZ_SHELL_PATH'] = '/opt/custom/bin:/usr/local/bin'
```

### Path Separators

- **Windows**: Semicolon (`;`)
- **Unix/Linux/macOS**: Colon (`:`)

FZ automatically detects the platform and uses the correct separator.

### Priority Order

Paths are searched **left to right**. Earlier paths have higher priority:

```bash
# Linux example
export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin:/usr/bin

# Search order:
# 1. /opt/custom/bin/grep
# 2. /usr/local/bin/grep
# 3. /usr/bin/grep
```

## How It Works

### 1. Command Resolution

When FZ encounters a shell command, it:

1. Parses the command string to identify binary names
2. Searches `FZ_SHELL_PATH` directories for each binary
3. Replaces binary names with absolute paths
4. Caches resolved paths for performance

### 2. Example Transformation

**Before (input):**
```python
model = {
    "output": {
        "value": "grep 'result' output.txt | awk '{print $2}' | tr -d '\\n'"
    }
}
```

**After (with FZ_SHELL_PATH=C:\msys64\usr\bin):**
```python
# Executed command:
"C:\\msys64\\usr\\bin\\grep.exe 'result' output.txt | C:\\msys64\\usr\\bin\\awk.exe '{print $2}' | C:\\msys64\\usr\\bin\\tr.exe -d '\\n'"
```

### 3. Integration Points

**Model Output Commands** (`fzo` function):
```python
model = {
    "output": {
        "pressure": "grep 'P=' out.txt | awk '{print $2}'"
    }
}

results = fz.fzo("results/", model)
# Shell commands are resolved using FZ_SHELL_PATH
```

**Calculator Commands** (`sh://` URIs):
```python
calculators = "sh://grep 'done' status.txt && bash process.sh"
# Commands in calculator URIs are resolved using FZ_SHELL_PATH
```

## Common Configurations

### Windows with MSYS2

```cmd
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
```

**Provides**: grep, awk, sed, cut, tr, bash, python3, etc.

### Windows with Git Bash

```cmd
SET FZ_SHELL_PATH=C:\Program Files\Git\usr\bin;C:\Program Files\Git\bin
```

**Provides**: Unix tools bundled with Git for Windows

### macOS with Homebrew

```bash
export FZ_SHELL_PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin
```

**Provides**: Homebrew-installed tools with priority over system tools

### Linux Custom Installation

```bash
export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin:/usr/bin
```

**Provides**: Custom compiled tools with fallback to system

## Platform-Specific Features

### Windows: .exe Extension Handling

FZ automatically tries both `command` and `command.exe` on Windows:

```python
# Looking for "grep"
# Tries: grep, grep.exe
# Found: C:\msys64\usr\bin\grep.exe ✓
```

### Windows: Short Path (8.3) Format

For paths with spaces, FZ can use Windows short paths:

```cmd
# Long path: C:\Program Files\Git\usr\bin\grep.exe
# Short path: C:\PROGRA~1\Git\usr\bin\grep.exe
```

### Unix: Executable Permission

FZ checks that binaries have execute permission:

```bash
# Must be executable
$ ls -l /usr/bin/grep
-rwxr-xr-x 1 root root 220K /usr/bin/grep
```

## Programmatic Usage

### Checking Configuration

```python
from fz import get_config

config = get_config()
print(f"Shell path: {config.shell_path}")
```

### Resolving Commands Manually

```python
from fz.shell_path import resolve_command, replace_commands_in_string

# Resolve single command
grep_path = resolve_command("grep")
print(f"grep found at: {grep_path}")

# Replace all commands in a string
original = "grep 'pattern' file.txt | awk '{print $2}'"
resolved = replace_commands_in_string(original)
print(f"Resolved: {resolved}")
```

### Listing Available Binaries

```python
from fz.shell_path import get_resolver

resolver = get_resolver()
binaries = resolver.list_available_binaries()
print(f"Available binaries: {binaries}")
```

### Reloading Configuration

```python
import os
from fz.shell_path import reinitialize_resolver

# Change shell path
os.environ['FZ_SHELL_PATH'] = '/new/path/bin'

# Reinitialize resolver to pick up new path
reinitialize_resolver()
```

## Troubleshooting

### Command Not Found

**Problem**: FZ can't find a required binary

**Solution**:
```bash
# 1. Check FZ_SHELL_PATH is set
echo $FZ_SHELL_PATH  # Linux/macOS
echo %FZ_SHELL_PATH%  # Windows

# 2. Verify binary exists in path
ls $FZ_SHELL_PATH | grep grep  # Linux/macOS
dir %FZ_SHELL_PATH% | findstr grep  # Windows

# 3. Add missing directory to FZ_SHELL_PATH
export FZ_SHELL_PATH=/missing/dir:$FZ_SHELL_PATH
```

### Wrong Tool Version

**Problem**: System tool is used instead of custom tool

**Solution**: Put custom path **first** in FZ_SHELL_PATH
```bash
# ❌ Wrong order - system tool used
export FZ_SHELL_PATH=/usr/bin:/opt/custom/bin

# ✅ Correct order - custom tool used
export FZ_SHELL_PATH=/opt/custom/bin:/usr/bin
```

### Windows Path with Spaces

**Problem**: Paths containing spaces cause issues

**Solutions**:
```cmd
# Option 1: Use short path (8.3 format)
SET FZ_SHELL_PATH=C:\PROGRA~1\Git\usr\bin

# Option 2: Use forward slashes
SET FZ_SHELL_PATH=C:/Program Files/Git/usr/bin

# Option 3: Install tools in path without spaces
SET FZ_SHELL_PATH=C:\msys64\usr\bin
```

## Performance

### Caching

FZ caches resolved binary paths for performance:

```python
# First call - resolves and caches
grep = resolve_command("grep")  # ~1ms (file system lookup)

# Subsequent calls - uses cache
grep = resolve_command("grep")  # ~0.001ms (memory lookup)
```

Cache is cleared when:
- `reinitialize_resolver()` is called
- Process restarts

### Optimization Tips

1. **Use absolute paths** in `FZ_SHELL_PATH` (not relative)
2. **Put frequently used directories first** (reduces search time)
3. **Avoid very long path lists** (each directory is scanned)

## Implementation Details

### ShellPathResolver Class

Located in `fz/shell_path.py`:

```python
class ShellPathResolver:
    def __init__(self, custom_shell_path: Optional[str]):
        """Initialize with custom path or None (uses system PATH)"""

    def resolve_command(self, command: str) -> Optional[str]:
        """Resolve command name to absolute path (cached)"""

    def replace_commands_in_string(self, cmd_string: str) -> str:
        """Replace all command names with absolute paths"""

    def list_available_binaries(self) -> List[str]:
        """List all binaries in search paths"""
```

### Global Functions

```python
# Get singleton resolver instance
from fz.shell_path import get_resolver
resolver = get_resolver()

# Convenience functions
from fz.shell_path import resolve_command, replace_commands_in_string
path = resolve_command("grep")
resolved_cmd = replace_commands_in_string("grep file.txt")
```

## Best Practices

### 1. Document Requirements

```python
# requirements.txt or README
"""
Windows users: Install MSYS2 and set:
    SET FZ_SHELL_PATH=C:\msys64\usr\bin

Linux/macOS users:
    export FZ_SHELL_PATH=/usr/local/bin:/usr/bin
"""
```

### 2. Validate in Setup Scripts

```bash
#!/bin/bash
# setup.sh

if [ -z "$FZ_SHELL_PATH" ]; then
    echo "Warning: FZ_SHELL_PATH not set"
    echo "Using system PATH - may cause issues"
fi

# Test required commands
for cmd in grep awk sed; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done
```

### 3. Team Configuration File

```bash
# .fzrc
export FZ_SHELL_PATH=/opt/project/tools/bin:/usr/local/bin
export FZ_LOG_LEVEL=INFO

# Usage:
source .fzrc
python run_study.py
```

### 4. CI/CD Integration

```yaml
# .github/workflows/ci.yml
jobs:
  test:
    steps:
      - name: Set FZ_SHELL_PATH
        run: echo "FZ_SHELL_PATH=/usr/bin" >> $GITHUB_ENV

      - name: Run tests
        run: pytest tests/
```

## See Also

- **Shell path example**: `examples/shell_path_example.md`
- **Configuration guide**: `context/overview.md`
- **Calculator types**: `context/calculators.md`
- **Source code**: `fz/shell_path.py`
- **Tests**: `tests/test_shell_path.py`
