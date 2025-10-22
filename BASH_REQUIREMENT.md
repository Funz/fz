# Bash Requirement on Windows

## Overview

On Windows, `fz` requires **bash** to be available in the system PATH. This is necessary because:

1. **Output evaluation** (`fzo()`): Shell commands are used to parse and extract output values from result files
2. **Calculation execution** (`fzr()`, `sh://` calculator): Bash is used as the shell interpreter for running calculations

## Startup Check

When importing `fz` on Windows, the package automatically checks if bash is available in PATH:

```python
import fz  # On Windows: checks for bash and raises error if not found
```

If bash is **not found**, a `RuntimeError` is raised with installation instructions:

```
ERROR: bash is not available in PATH on Windows.

fz requires bash to run shell commands and evaluate output expressions.
Please install one of the following:

1. Cygwin (recommended):
   - Download from: https://www.cygwin.com/
   - During installation, make sure to select 'bash' package
   - Add C:\cygwin64\bin to your PATH environment variable

2. Git for Windows (includes Git Bash):
   - Download from: https://git-scm.com/download/win
   - Ensure 'Git Bash Here' is selected during installation
   - Add Git\bin to your PATH (e.g., C:\Program Files\Git\bin)

3. WSL (Windows Subsystem for Linux):
   - Install from Microsoft Store or use: wsl --install
   - Note: bash.exe should be accessible from Windows PATH

After installation, verify bash is in PATH by running:
   bash --version
```

## Recommended Installation: Cygwin

We recommend **Cygwin** for Windows users because:

- Provides a comprehensive Unix-like environment
- Includes bash and other common Unix utilities
- Well-tested and widely used for Windows development
- Easy to add to PATH

### Installing Cygwin

1. Download the installer from [https://www.cygwin.com/](https://www.cygwin.com/)
2. Run the installer
3. During package selection, ensure **bash** is selected (it usually is by default)
4. Complete the installation
5. Add `C:\cygwin64\bin` to your system PATH:
   - Right-click "This PC" → Properties → Advanced system settings
   - Click "Environment Variables"
   - Under "System variables", find and edit "Path"
   - Add `C:\cygwin64\bin` to the list
   - Click OK to save

6. Verify bash is available:
   ```cmd
   bash --version
   ```

## Alternative: Git for Windows

If you prefer Git Bash:

1. Download from [https://git-scm.com/download/win](https://git-scm.com/download/win)
2. Run the installer
3. Ensure "Git Bash Here" is selected during installation
4. Add Git's bin directory to PATH (usually `C:\Program Files\Git\bin`)
5. Verify:
   ```cmd
   bash --version
   ```

## Alternative: WSL (Windows Subsystem for Linux)

For WSL users:

1. Install WSL from Microsoft Store or run:
   ```powershell
   wsl --install
   ```

2. Ensure `bash.exe` is accessible from Windows PATH
3. Verify:
   ```cmd
   bash --version
   ```

## Implementation Details

### Startup Check

The startup check is implemented in `fz/core.py`:

```python
def check_bash_availability_on_windows():
    """Check if bash is available in PATH on Windows"""
    if platform.system() != "Windows":
        return

    bash_path = shutil.which("bash")
    if bash_path is None:
        raise RuntimeError("ERROR: bash is not available in PATH...")

    log_debug(f"✓ Bash found on Windows: {bash_path}")
```

This function is called automatically when importing `fz` (in `fz/__init__.py`):

```python
from .core import check_bash_availability_on_windows

# Check bash availability on Windows at import time
check_bash_availability_on_windows()
```

### Shell Execution

When executing shell commands on Windows, `fz` uses bash as the interpreter:

```python
# In fzo() and run_local_calculation()
executable = None
if platform.system() == "Windows":
    executable = shutil.which("bash")

subprocess.run(command, shell=True, executable=executable, ...)
```

## Testing

Run the test suite to verify bash checking works correctly:

```bash
python test_bash_check.py
```

Run the demonstration to see the behavior:

```bash
python demo_bash_requirement.py
```

## Non-Windows Platforms

On Linux and macOS, bash is typically available by default, so no check is performed. The package imports normally without requiring any special setup.
