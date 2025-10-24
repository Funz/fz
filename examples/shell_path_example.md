# FZ_SHELL_PATH Example

The `FZ_SHELL_PATH` environment variable allows you to customize where FZ looks for binaries (grep, awk, sed, etc.) used in:
1. Model output expressions
2. Local shell calculator (`sh://`) commands

This is especially useful on Windows where you might have multiple bash environments (MSYS2, Git Bash, WSL, Cygwin) installed.

## Use Case: Ensure consistent tool versions across your team

**Problem:** Different team members have different Unix tool installations:
- Some use MSYS2
- Some use Git Bash
- Some use custom-built tools in `/opt/tools`

**Solution:** Set `FZ_SHELL_PATH` to ensure everyone uses the same binaries.

### Windows Example with MSYS2

```bash
# On Windows Command Prompt:
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
python -m fz input.txt -m mymodel

# Or on PowerShell:
$env:FZ_SHELL_PATH = "C:\msys64\usr\bin;C:\msys64\mingw64\bin"
python -m fz input.txt -m mymodel
```

### Unix/Linux Example

```bash
# Use colon separator on Unix
export FZ_SHELL_PATH=/opt/team-tools/bin:/usr/local/bin:/usr/bin

# Now when a model uses:
# {"output": {"value": "grep 'result' output.txt | awk '{print $2}'"}}
#
# FZ will resolve:
# /opt/team-tools/bin/grep 'result' output.txt | /opt/team-tools/bin/awk '{print $2}'
```

## How It Works

1. **Configuration**: `FZ_SHELL_PATH` is loaded from environment when FZ starts
2. **Resolution**: When executing model output commands or `sh://` commands, each binary name is looked up in the configured paths
3. **Caching**: Once a binary is resolved, the path is cached for performance
4. **Fallback**: If `FZ_SHELL_PATH` is not set, FZ uses the system `PATH` environment variable

## Example Model with Custom Tools

```python
import fz

# Define model with output expressions that use external tools
model = {
    "varprefix": "$",
    "delim": "{}",
    "output": {
        # These commands will be resolved using FZ_SHELL_PATH
        "temperature": "grep 'T=' output.txt | awk '{print $2}'",
        "pressure": "grep 'P=' output.txt | cut -d'=' -f2",
        "iterations": "tail -1 output.txt | awk '{print NF}'"
    }
}

# Run FZ (with FZ_SHELL_PATH set to your custom paths)
results = fz.fzr(
    "input.txt",
    variables={"param": [1, 2, 3]},
    model=model,
    calculators=["sh://bash calc.sh"],
    results_dir="results"
)

# Parse results
output = fz.fzo("results/*", model)
print(output)
```

## Advantages

1. **Consistency**: Ensure everyone in your team uses the same tool versions
2. **Portability**: Move Unix tools to specific locations without relying on system PATH
3. **Isolation**: Avoid conflicts with system-wide bash installations
4. **Windows Support**: Automatically handles `.exe` extensions on Windows (grep → grep.exe)
5. **Performance**: Caches binary paths for faster execution

## Troubleshooting

**Q: Why isn't my custom grep being used?**

A: Make sure:
1. The directory containing grep is in `FZ_SHELL_PATH`
2. Use semicolons (;) on Windows, colons (:) on Unix
3. The path is absolute, not relative
4. The binary has executable permissions

```bash
# Verify your setup:
echo %FZ_SHELL_PATH%  # On Windows
echo $FZ_SHELL_PATH   # On Unix

# Test that grep is found:
python -c "from fz.shell_path import get_resolver; print(get_resolver().resolve_command('grep'))"
```

**Q: Can I use relative paths in FZ_SHELL_PATH?**

A: It's recommended to use absolute paths for clarity and to avoid issues when working directories change. Relative paths are not recommended.

**Q: How do I list all available binaries in my FZ_SHELL_PATH?**

A: Use Python:

```python
from fz.shell_path import get_resolver

resolver = get_resolver()
binaries = resolver.list_available_binaries()
for binary in binaries:
    print(binary)
```
