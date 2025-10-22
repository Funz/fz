# Windows CI Package Installation Fix

## Issue

The Windows CI was missing `awk` and `cat` utilities even though Cygwin was installed. This was because Cygwin's base installation via Chocolatey doesn't automatically include all required packages.

## Root Cause

When installing Cygwin via `choco install cygwin`, only the base Cygwin environment is installed. Essential packages like:
- **gawk** (provides `awk` command)
- **coreutils** (provides `cat`, `cut`, `tr`, `sort`, `uniq`, `head`, `tail`)

...are not included by default and must be explicitly installed using Cygwin's package manager.

## Solution

Updated all Windows CI jobs in both `ci.yml` and `cli-tests.yml` to explicitly install required packages using Cygwin's setup program.

### Package Installation Added

```powershell
Write-Host "Installing required Cygwin packages..."
# Install essential packages using Cygwin setup
# Note: coreutils includes cat, cut, tr, sort, uniq, head, tail
$packages = "bash,grep,gawk,sed,coreutils"

# Download Cygwin setup if needed
if (-not (Test-Path "C:\cygwin64\setup-x86_64.exe")) {
  Write-Host "Downloading Cygwin setup..."
  Invoke-WebRequest -Uri "https://cygwin.com/setup-x86_64.exe" -OutFile "C:\cygwin64\setup-x86_64.exe"
}

# Install packages quietly
Write-Host "Installing packages: $packages"
Start-Process -FilePath "C:\cygwin64\setup-x86_64.exe" -ArgumentList "-q","-P","$packages" -Wait -NoNewWindow
```

## Packages Installed

| Package | Utilities Provided | Purpose |
|---------|-------------------|---------|
| **bash** | bash | Shell interpreter |
| **grep** | grep | Pattern matching in files |
| **gawk** | awk, gawk | Text processing and field extraction |
| **sed** | sed | Stream editing |
| **coreutils** | cat, cut, tr, sort, uniq, head, tail, etc. | Core Unix utilities |

### Why These Packages?

1. **bash** - Required for shell script execution
2. **grep** - Used extensively in output parsing (e.g., `grep 'result = ' output.txt`)
3. **gawk** - Provides the `awk` command for text processing (e.g., `awk '{print $1}'`)
4. **sed** - Stream editor for text transformations
5. **coreutils** - Bundle of essential utilities:
   - **cat** - File concatenation (e.g., `cat output.txt`)
   - **cut** - Field extraction (e.g., `cut -d '=' -f2`)
   - **tr** - Character translation/deletion (e.g., `tr -d ' '`)
   - **sort** - Sorting output
   - **uniq** - Removing duplicates
   - **head**/**tail** - First/last lines of output

## Files Modified

### CI Workflows
1. **.github/workflows/ci.yml** - Main CI workflow (Windows job)
2. **.github/workflows/cli-tests.yml** - CLI test workflows (both `cli-tests` and `cli-integration-tests` jobs)

### Documentation
3. **.github/workflows/WINDOWS_CI_SETUP.md** - Updated installation instructions and package list

## Verification

The existing verification step checks all 11 utilities:

```powershell
$utilities = @("bash", "grep", "cut", "awk", "sed", "tr", "cat", "sort", "uniq", "head", "tail")
```

This step will now succeed because all utilities are explicitly installed.

## Installation Process

1. **Install Cygwin Base** - Via Chocolatey (`choco install cygwin`)
2. **Download Setup** - Get `setup-x86_64.exe` from cygwin.com
3. **Install Packages** - Run setup with `-q -P bash,grep,gawk,sed,coreutils`
4. **Add to PATH** - Add `C:\cygwin64\bin` to system PATH
5. **Verify Utilities** - Check each utility with `--version`

## Benefits

1. ✅ **Explicit Control** - We know exactly which packages are installed
2. ✅ **Reliable** - Not dependent on Chocolatey package defaults
3. ✅ **Complete** - All required utilities guaranteed to be present
4. ✅ **Verifiable** - Verification step will catch any missing utilities
5. ✅ **Maintainable** - Easy to add more packages if needed

## Testing

After this change:
- All 11 Unix utilities will be available in Windows CI
- The verification step will pass, showing ✓ for each utility
- Tests that use `awk` and `cat` commands will work correctly
- Output parsing with complex pipelines will function as expected

## Example Commands That Now Work

```bash
# Pattern matching with awk
grep 'result = ' output.txt | awk '{print $NF}'

# File concatenation with cat
cat output.txt | grep 'pressure' | cut -d'=' -f2 | tr -d ' '

# Complex pipeline
cat data.csv | grep test1 | cut -d',' -f2 > temp.txt

# Line counting with awk
awk '{count++} END {print "lines:", count}' combined.txt > stats.txt
```

All these commands are used in the test suite and will now execute correctly on Windows CI.

## Alternative Approaches Considered

### 1. Use Cyg-get (Cygwin package manager CLI)
- **Pros**: Simpler command-line interface
- **Cons**: Requires separate installation, less reliable in CI

### 2. Install each package separately via Chocolatey
- **Pros**: Uses familiar package manager
- **Cons**: Not all Cygwin packages available via Chocolatey

### 3. Use Git Bash
- **Pros**: Already includes many utilities
- **Cons**: Missing some utilities, less consistent with Unix behavior

### 4. Use official Cygwin setup (CHOSEN)
- **Pros**: Official method, reliable, supports all packages
- **Cons**: Slightly more complex setup script

## Conclusion

By explicitly installing required Cygwin packages, we ensure that all Unix utilities needed by `fz` are available in Windows CI environments. This eliminates the "awk not found" and "cat not found" errors that were occurring previously.
