# Bash and Unix Utilities Requirement on Windows

## Overview

On Windows, `fz` requires **bash** and **essential Unix utilities** to be available in the system PATH. This is necessary because:

1. **Output evaluation** (`fzo()`): Shell commands using Unix utilities (grep, cut, awk, tr, etc.) are used to parse and extract output values from result files
2. **Calculation execution** (`fzr()`, `sh://` calculator): Bash is used as the shell interpreter for running calculations

## Required Utilities

The following Unix utilities must be available:

- **bash** - Shell interpreter
- **grep** - Pattern matching (heavily used for output parsing)
- **cut** - Field extraction (e.g., `cut -d '=' -f2`)
- **awk** - Text processing and field extraction
- **sed** - Stream editing
- **tr** - Character translation/deletion
- **cat** - File concatenation
- **sort**, **uniq**, **head**, **tail** - Text processing utilities

## Startup Check

When importing `fz` on Windows, the package automatically checks if bash is available in PATH:

```python
import fz  # On Windows: checks for bash and raises error if not found
```

If bash is **not found**, a `RuntimeError` is raised with installation instructions:

```
ERROR: bash is not available in PATH on Windows.

fz requires bash and Unix utilities (grep, cut, awk, sed, tr, cat) to run shell
commands and evaluate output expressions.
Please install one of the following:

1. MSYS2 (recommended):
   - Download from: https://www.msys2.org/
   - Or install via Chocolatey: choco install msys2
   - After installation, run: pacman -S bash grep gawk sed coreutils
   - Add C:\msys64\usr\bin to your PATH environment variable

2. Git for Windows (includes Git Bash):
   - Download from: https://git-scm.com/download/win
   - Ensure 'Git Bash Here' is selected during installation
   - Add Git\bin to your PATH (e.g., C:\Program Files\Git\bin)

3. WSL (Windows Subsystem for Linux):
   - Install from Microsoft Store or use: wsl --install
   - Note: bash.exe should be accessible from Windows PATH

4. Cygwin (alternative):
   - Download from: https://www.cygwin.com/
   - During installation, select 'bash', 'grep', 'gawk', 'sed', and 'coreutils' packages
   - Add C:\cygwin64\bin to your PATH environment variable

After installation, verify bash is in PATH by running:
   bash --version
```

## Recommended Installation: MSYS2

We recommend **MSYS2** for Windows users because:

- Provides a comprehensive Unix-like environment on Windows
- Modern package manager (pacman) similar to Arch Linux
- Actively maintained with regular updates
- Includes all required Unix utilities (grep, cut, awk, sed, tr, cat, sort, uniq, head, tail)
- Easy to install additional packages
- All utilities work consistently with Unix versions
- Available via Chocolatey for easy installation

### Installing MSYS2

1. Download the installer from [https://www.msys2.org/](https://www.msys2.org/)
2. Run the installer (or use Chocolatey: `choco install msys2`)
3. After installation, open MSYS2 terminal and update the package database:
   ```bash
   pacman -Syu
   ```
4. Install required packages:
   ```bash
   pacman -S bash grep gawk sed coreutils
   ```
5. Add `C:\msys64\usr\bin` to your system PATH:
   - Right-click "This PC" → Properties → Advanced system settings
   - Click "Environment Variables"
   - Under "System variables", find and edit "Path"
   - Add `C:\msys64\usr\bin` to the list
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
