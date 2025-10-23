# Windows CI Setup with MSYS2

## Overview

The Windows CI workflows have been updated to install MSYS2 with bash and essential Unix utilities to meet the `fz` package requirements. The package requires:

- **bash** - Shell interpreter
- **Unix utilities** - grep, cut, awk, sed, tr, cat, sort, uniq, head, tail (for output parsing)

## Changes Made

### Workflows Updated

1. **`.github/workflows/ci.yml`** - Main CI workflow
2. **`.github/workflows/cli-tests.yml`** - CLI testing workflow (both jobs)

### Installation Steps Added

For each Windows job, the following steps have been added:

#### 1. Install MSYS2 with Required Packages
```yaml
- name: Install system dependencies (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Install MSYS2 with bash and essential Unix utilities
    # fz requires bash and Unix tools (grep, cut, awk, sed, tr) for output parsing
    Write-Host "Installing MSYS2 with bash and Unix utilities..."
    choco install msys2 -y --params="/NoUpdate"

    Write-Host "Installing required MSYS2 packages..."
    # Use pacman (MSYS2 package manager) to install packages
    # Note: coreutils includes cat, cut, tr, sort, uniq, head, tail
    $env:MSYSTEM = "MSYS"

    # Update package database
    C:\msys64\usr\bin\bash.exe -lc "pacman -Sy --noconfirm"

    # Install required packages
    C:\msys64\usr\bin\bash.exe -lc "pacman -S --noconfirm bash grep gawk sed bc coreutils"

    Write-Host "✓ MSYS2 installation complete with all required packages"
```

**Packages Installed**:
- **bash** - Shell interpreter
- **grep** - Pattern matching
- **gawk** - GNU awk for text processing (provides `awk` command)
- **sed** - Stream editor
- **coreutils** - Core utilities package including cat, cut, tr, sort, uniq, head, tail

#### 2. List Installed Utilities
```yaml
- name: List installed MSYS2 utilities (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    Write-Host "Listing executables in C:\msys64\usr\bin..."

    # List all .exe files in msys64/usr/bin
    $binFiles = Get-ChildItem -Path "C:\msys64\usr\bin" -Filter "*.exe" | Select-Object -ExpandProperty Name

    # Check for key utilities we need
    $keyUtilities = @("bash.exe", "grep.exe", "cut.exe", "awk.exe", "gawk.exe", "sed.exe", "tr.exe", "cat.exe", "sort.exe", "uniq.exe", "head.exe", "tail.exe")

    Write-Host "Key utilities required by fz:"
    foreach ($util in $keyUtilities) {
      if ($binFiles -contains $util) {
        Write-Host "  ✓ $util"
      } else {
        Write-Host "  ✗ $util (NOT FOUND)"
      }
    }

    Write-Host "Total executables installed: $($binFiles.Count)"
    Write-Host "Sample of other utilities available:"
    $binFiles | Where-Object { $_ -notin $keyUtilities } | Select-Object -First 20 | ForEach-Object { Write-Host "  - $_" }
```

This step provides visibility into what utilities were actually installed, helping to:
- **Debug** package installation issues
- **Verify** all required utilities are present
- **Inspect** what other utilities are available
- **Track** changes in MSYS2 package contents over time

#### 3. Add MSYS2 to PATH
```yaml
- name: Add MSYS2 to PATH (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Add MSYS2 bin directory to PATH for this workflow
    $env:PATH = "C:\msys64\usr\bin;$env:PATH"
    echo "C:\msys64\usr\bin" | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
    Write-Host "✓ MSYS2 added to PATH"
```

#### 4. Verify Unix Utilities
```yaml
- name: Verify Unix utilities (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Verify bash and essential Unix utilities are available
    Write-Host "Verifying Unix utilities..."

    $utilities = @("bash", "grep", "cut", "awk", "sed", "tr",  "sort", "uniq", "head", "tail")
    $allFound = $true

    foreach ($util in $utilities) {
      try {
        & $util --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq $null) {
          Write-Host "  ✓ $util"
        } else {
          Write-Host "  ✗ $util (exit code: $LASTEXITCODE)"
          $allFound = $false
        }
      } catch {
        Write-Host "  ✗ $util (not found)"
        $allFound = $false
      }
    }

    if (-not $allFound) {
      Write-Host "`nERROR: Some Unix utilities are missing"
      exit 1
    }

    Write-Host "`n✓ All Unix utilities are available and working"

    Write-Host "Where is bash?"
    Get-Command bash
    Get-Command C:\msys64\usr\bin\bash.exe
    $env:PATH
```

## Why MSYS2?

We chose MSYS2 as the preferred option over Cygwin, Git Bash, or WSL for the following reasons:

1. **Complete Unix Environment**: MSYS2 provides all required Unix utilities through well-maintained packages
2. **Native Package Manager**: Uses pacman (from Arch Linux), a modern and reliable package management system
3. **Better Performance**: MSYS2 generally offers better performance than Cygwin for file operations
4. **Active Development**: MSYS2 is actively maintained with regular updates and modern tooling
5. **Consistency**: MSYS2's utilities behave identically to their Unix counterparts, ensuring cross-platform compatibility
6. **CI Availability**: MSYS2 is readily available via Chocolatey on GitHub Actions Windows runners
7. **PATH Integration**: Easy to add to PATH and verify installation
8. **Explicit Package Control**: We explicitly install required packages ensuring all utilities are available

**Note**: Cygwin is still supported as an alternative Unix environment. The `fz` package will automatically detect and use either MSYS2 or Cygwin bash if available.

## Installation Location

### MSYS2 (Preferred)
- MSYS2 is installed to: `C:\msys64`
- Bash executable is at: `C:\msys64\usr\bin\bash.exe`
- The bin directory (`C:\msys64\usr\bin`) is added to PATH

### Cygwin (Alternative)
- Cygwin is installed to: `C:\cygwin64`
- Bash executable is at: `C:\cygwin64\bin\bash.exe`
- The bin directory (`C:\cygwin64\bin`) is added to PATH

## Verification

Each workflow includes a verification step that:
1. Runs `bash --version` to ensure bash is executable
2. Checks the exit code to confirm successful execution
3. Fails the workflow if bash is not available

This ensures that tests will not run if bash is not properly installed.

## Testing on Windows

When testing locally on Windows, developers should install MSYS2 (recommended) or Cygwin:

### Option 1: MSYS2 (Recommended)
1. Download from https://www.msys2.org/
2. Run the installer (default location: `C:\msys64`)
3. Open MSYS2 terminal and install required packages:
   ```bash
   pacman -Sy
   pacman -S bash grep gawk sed bc coreutils
   ```
4. Add `C:\msys64\usr\bin` to the system PATH
5. Verify with `bash --version`

### Option 2: Cygwin (Alternative)
1. Download from https://www.cygwin.com/
2. Run the installer and select the `bash`, `grep`, `gawk`, `sed`, and `coreutils` packages
3. Add `C:\cygwin64\bin` to the system PATH
4. Verify with `bash --version`

See `BASH_REQUIREMENT.md` for detailed installation instructions.

## CI Execution Flow

The updated Windows CI workflow now follows this sequence:

1. **Checkout code**
2. **Set up Python**
3. **Install MSYS2** ← New step
4. **Add MSYS2 to PATH** ← New step
5. **Verify bash and Unix utilities** ← New step
6. **Install R and other dependencies**
7. **Install Python dependencies** (including `fz`)
   - At this point, `import fz` will check for bash and should succeed
8. **Run tests**

## Benefits

- **Early Detection**: Bash availability is verified before tests run
- **Clear Errors**: If bash is missing, the workflow fails with a clear message
- **Consistent Environment**: All Windows CI jobs now have bash available
- **Test Coverage**: Windows tests can now run the full test suite, including bash-dependent tests

## Alternative Approaches Considered

### Cygwin (Still Supported)
- **Pros**:
  - Mature and well-tested Unix environment
  - Comprehensive package ecosystem
  - Widely used in enterprise environments
- **Cons**:
  - Slower than MSYS2 for file operations
  - Less active development compared to MSYS2
  - Older package management system

### Git Bash
- **Pros**: Often already installed on developer machines
- **Cons**:
  - May not be in PATH by default
  - Minimal Unix utilities included
  - Different behavior from Unix bash in some cases
  - Harder to verify installation in CI

### WSL
- **Pros**: Most authentic Linux environment on Windows
- **Cons**:
  - More complex to set up in CI
  - Requires WSL-specific invocation syntax
  - May have performance overhead
  - Additional layer of abstraction

### PowerShell Bash Emulation
- **Pros**: No installation needed
- **Cons**:
  - Not a true bash implementation
  - Incompatible with many bash scripts
  - Would require significant code changes

## Maintenance Notes

- The MSYS2 installation uses Chocolatey, which is pre-installed on GitHub Actions Windows runners
- If Chocolatey is updated or MSYS2 packages change, these workflows may need adjustment
- The installation path (`C:\msys64`) is hardcoded and should remain consistent across updates
- If additional Unix tools are needed, they can be installed using `pacman` package manager
- The `fz` package supports both MSYS2 and Cygwin, automatically detecting which is available

## Related Documentation

- `BASH_REQUIREMENT.md` - User documentation on bash requirement
- `tests/test_bash_availability.py` - Tests for bash availability checking
- `tests/test_bash_requirement_demo.py` - Demonstration of bash requirement behavior
