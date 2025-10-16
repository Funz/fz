# Windows Interrupt Handling Guide

This guide explains how Ctrl+C interrupt handling works on Windows and how to troubleshoot issues.

## Quick Test

Run the test script to verify interrupt handling works on your system:

```bash
python test_windows_interrupt.py
```

Press Ctrl+C when prompted. You should see:
```
⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
⚠️  Press Ctrl+C again to force quit (not recommended)
```

## How It Works

### Signal Handling on Windows

Windows handles Ctrl+C differently from Unix systems:

| Aspect | Unix/Linux | Windows |
|--------|-----------|---------|
| Signal | SIGINT (signal 2) | CTRL_C_EVENT |
| Handler | Always works | May not work in all contexts |
| Subprocess | Interrupted automatically | Requires special flags |
| Blocking calls | Get interrupted | Do NOT get interrupted |

### Our Implementation

FZ uses a **polling-based approach** that works on both platforms:

1. **Signal Handler** (`fz/core.py`)
   - Catches Ctrl+C and sets a global flag
   - Flushes output on Windows for immediate feedback
   - Allows graceful shutdown on first Ctrl+C
   - Forces quit on second Ctrl+C

2. **Polling Loop** (`fz/runners.py`)
   - Checks process status every 500ms
   - Checks interrupt flag between polls
   - Terminates process when interrupt detected
   - Works even when signal handler fails

3. **Windows-Specific Subprocess Creation** (`fz/runners.py`)
   - Uses `CREATE_NEW_PROCESS_GROUP` flag
   - Allows child processes to receive Ctrl+C
   - Essential for proper interrupt propagation

## Interrupt Keys on Windows

### Primary Method: Ctrl+C

```
First Ctrl+C:  Graceful shutdown (recommended)
Second Ctrl+C: Force quit
```

**What happens:**
1. Signal handler sets interrupt flag
2. Polling loop detects flag within 500ms
3. Running processes are terminated gracefully
4. Partial results are saved
5. Resources are cleaned up

### Alternative: Ctrl+Break

```
Ctrl+Break: Immediate termination (emergency only)
```

**Use when:**
- Ctrl+C doesn't work
- Process is completely frozen
- Emergency stop needed

**Caution:** Skips cleanup, may leave orphaned processes

## Terminal Compatibility

### ✅ Fully Supported

- **Command Prompt (cmd.exe)** - Full support
- **PowerShell** - Full support
- **Windows Terminal** - Full support
- **Git Bash / MSYS2** - Full support (Unix-like behavior)
- **Cmder** - Full support
- **ConEmu** - Full support

### ⚠️ Limited Support

- **IDE Integrated Terminals** - Varies by IDE
  - VS Code: ✅ Works
  - PyCharm: ✅ Works (may need configuration)
  - Jupyter: ❌ Doesn't work (use kernel interrupt instead)
  - Spyder: ⚠️ May not work

- **Windows Services** - ❌ No console, can't receive Ctrl+C

## Troubleshooting

### Problem: Ctrl+C does nothing

**Symptoms:**
- Press Ctrl+C but calculations continue
- No interrupt message appears
- Have to close terminal to stop

**Solutions:**

1. **Check your terminal**
   ```bash
   # Test basic interrupt:
   python -c "import time; time.sleep(60)"
   # Press Ctrl+C - should exit immediately
   ```

2. **Run from command line**
   ```bash
   # Instead of running from IDE, open cmd.exe:
   cd path\to\project
   python run_study.py
   ```

3. **Use absolute paths**
   ```bash
   # Ensure Python is in PATH or use full path:
   C:\Python39\python.exe run_study.py
   ```

4. **Check for background processes**
   ```bash
   # If running as service/background, Ctrl+C won't work
   # Stop service or use Task Manager
   ```

### Problem: "Process didn't terminate, killing..."

**Symptoms:**
- See interrupt message
- Process doesn't stop gracefully
- See "killing..." message

**Explanation:**
- Normal on Windows for some processes
- FZ tries graceful termination first
- Falls back to force kill after 5 seconds

**No action needed** - this is expected behavior for stuck processes.

### Problem: Calculations don't stop immediately

**Symptoms:**
- Press Ctrl+C
- Calculations continue for several seconds
- Eventually stops

**Explanation:**
- This is **normal** behavior
- Polling loop checks every 500ms
- Current case finishes before stopping
- Ensures no corrupted results

**Expected delay:**
- Minimum: 0-500ms (until next poll)
- Maximum: Current case duration + 500ms

### Problem: Running in IDE doesn't work

**Solution 1: Configure IDE**

**VS Code:**
```json
// settings.json
{
  "terminal.integrated.shellArgs.windows": ["-NoExit", "-Command"]
}
```

**PyCharm:**
- Settings → Tools → Terminal
- Check "Run as a login shell"

**Solution 2: Use external terminal**
```bash
# Create run_external.bat:
start cmd /k "python run_study.py"
```

## Examples

### Basic Usage

```python
# run_study.py
import fz

model = {"varprefix": "$", "output": {"result": "cat output.txt"}}

results = fz.fzr(
    "input.txt",
    {"x": range(100)},  # 100 cases
    model,
    calculators="sh://bash calc.sh"
)
```

**Run and interrupt:**
```bash
C:\project> python run_study.py
# Press Ctrl+C after a few cases
⚠️  Interrupt received (Ctrl+C). Gracefully shutting down...
⚠️  Execution was interrupted. Partial results may be available.
```

### Resume After Interrupt

```python
# First run (interrupted)
results1 = fz.fzr(
    "input.txt",
    {"x": range(100)},
    model,
    calculators="sh://bash calc.sh",
    results_dir="run1"
)
print(f"Completed {len(results1)} before interrupt")

# Resume using cache
results2 = fz.fzr(
    "input.txt",
    {"x": range(100)},
    model,
    calculators=[
        "cache://run1",        # Reuse completed
        "sh://bash calc.sh"    # Run remaining
    ],
    results_dir="run2"
)
print(f"Total: {len(results2)} cases")
```

### Parallel Execution

```python
# Multiple calculators for parallel execution
results = fz.fzr(
    "input.txt",
    {"x": range(100)},
    model,
    calculators=[
        "sh://bash calc.sh",
        "sh://bash calc.sh",
        "sh://bash calc.sh"
    ],  # 3 parallel workers
    results_dir="results"
)
```

**Interrupt behavior:**
- All 3 workers stop on Ctrl+C
- Currently running cases finish
- Remaining cases skipped

## Advanced: Programmatic Interrupt Check

You can check for interrupts in your own code:

```python
from fz.core import is_interrupted

def my_long_calculation():
    for i in range(1000):
        if is_interrupted():
            print("Calculation interrupted!")
            break

        # Do work...
        process_case(i)

    print("Done!")
```

## Technical Details

### Signal Handler Installation

```python
# From fz/core.py
def _install_signal_handler():
    """Install custom SIGINT handler"""
    global _original_sigint_handler

    if platform.system() == "Windows":
        try:
            _original_sigint_handler = signal.signal(signal.SIGINT, _signal_handler)
            # Windows-specific: ensure output is flushed
        except (ValueError, OSError) as e:
            log_warning(f"Could not install handler: {e}")
    else:
        _original_sigint_handler = signal.signal(signal.SIGINT, _signal_handler)
```

### Polling Loop

```python
# From fz/runners.py
while process.poll() is None:
    # Check interrupt flag (works even if signal handler fails)
    if is_interrupted():
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()  # Force kill if termination fails
            process.wait()
        raise KeyboardInterrupt()

    time.sleep(0.5)  # Poll every 500ms
```

### Windows Subprocess Creation

```python
# From fz/runners.py
if platform.system() == "Windows":
    # Use CREATE_NEW_PROCESS_GROUP for Ctrl+C propagation
    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        command,
        shell=True,
        stdout=out_file,
        stderr=err_file,
        cwd=working_dir,
        creationflags=creationflags  # Essential for Windows
    )
```

## Reporting Issues

If interrupt handling still doesn't work after following this guide:

1. Run the test script:
   ```bash
   python test_windows_interrupt.py
   ```

2. Collect information:
   - Windows version
   - Python version
   - Terminal being used
   - Test script output

3. Report at: https://github.com/Funz/fz/issues

Include this information:
```
Platform: Windows 10/11
Python: 3.x.x
Terminal: cmd.exe / PowerShell / Git Bash / Other
Test result: [output from test_windows_interrupt.py]
```

## See Also

- [Main README](README.md) - General documentation
- [Interrupt Handling](README.md#interrupt-handling) - Cross-platform guide
- [Configuration](README.md#configuration) - Environment variables
