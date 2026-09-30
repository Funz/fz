# Troubleshooting

## Common Issues

**Problem**: Calculations fail with "command not found"
```bash
# Solution: Use absolute paths in calculator URIs
calculators = "sh://bash /full/path/to/script.sh"
```

**Problem**: SSH calculations hang
```bash
# Solution: Increase timeout or check SSH connectivity
calculators = "ssh://user@host/bash script.sh"
# Test manually: ssh user@host "bash script.sh"
```

**Problem**: Cache not working
```bash
# Solution: Check .fz_hash files exist in cache directories
# Enable debug logging to see cache matching process
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'
```

**Problem**: Out of memory with many parallel cases
```bash
# Solution: Limit parallel workers
export FZ_MAX_WORKERS=2
```

## Windows / Cross-Platform

**Problem**: Shell commands fail on Windows
```bash
# Solution: Install MSYS2 and set FZ_SHELL_PATH to point to its binaries
SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin
# See examples/shell_path_example.md for details
```

**Problem**: Line ending issues on Windows
```bash
# Solution: Write input files with Unix line endings (newline='\n')
# FZ templates and shell scripts expect LF, not CRLF
with open("input.txt", "w", newline='\n') as f:
    f.write(content)
```

**Problem**: `chmod` has no effect on Windows
```bash
# This is expected — Windows does not support Unix file permissions.
# Shell scripts run via sh:// do not need chmod on Windows.
```

## Debug Mode

Enable detailed logging:

```python
import os
os.environ['FZ_LOG_LEVEL'] = 'DEBUG'

results = fz.fzr(...)  # Will show detailed execution logs
```

Debug output includes:
- Calculator selection and locking
- File operations
- Command execution
- Cache matching
- Thread pool management
- Temporary directory preservation
