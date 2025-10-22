# Windows CI Setup with Cygwin

## Overview

The Windows CI workflows have been updated to install Cygwin with bash and essential Unix utilities to meet the `fz` package requirements. The package requires:

- **bash** - Shell interpreter
- **Unix utilities** - grep, cut, awk, sed, tr, cat, sort, uniq, head, tail (for output parsing)

## Changes Made

### Workflows Updated

1. **`.github/workflows/ci.yml`** - Main CI workflow
2. **`.github/workflows/cli-tests.yml`** - CLI testing workflow (both jobs)

### Installation Steps Added

For each Windows job, the following steps have been added:

#### 1. Install Cygwin with Required Packages
```yaml
- name: Install system dependencies (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Install Cygwin with bash and essential Unix utilities
    # fz requires bash and Unix tools (grep, cut, awk, sed, tr) for output parsing
    Write-Host "Installing Cygwin with bash and Unix utilities..."
    choco install cygwin -y --params "/InstallDir:C:\cygwin64"

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

    Write-Host "✓ Cygwin installation complete with all required packages"
```

**Packages Installed**:
- **bash** - Shell interpreter
- **grep** - Pattern matching
- **gawk** - GNU awk for text processing (provides `awk` command)
- **sed** - Stream editor
- **coreutils** - Core utilities package including cat, cut, tr, sort, uniq, head, tail

#### 2. List Installed Utilities
```yaml
- name: List installed Cygwin utilities (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    Write-Host "Listing executables in C:\cygwin64\bin..."

    # List all .exe files in cygwin64/bin
    $binFiles = Get-ChildItem -Path "C:\cygwin64\bin" -Filter "*.exe" | Select-Object -ExpandProperty Name

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
- **Track** changes in Cygwin package contents over time

#### 3. Add Cygwin to PATH
```yaml
- name: Add Cygwin to PATH (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Add Cygwin bin directory to PATH for this workflow
    $env:PATH = "C:\cygwin64\bin;$env:PATH"
    echo "C:\cygwin64\bin" | Out-File -FilePath $env:GITHUB_PATH -Encoding utf8 -Append
    Write-Host "✓ Cygwin added to PATH"
```

#### 4. Verify Unix Utilities
```yaml
- name: Verify Unix utilities (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    # Verify bash and essential Unix utilities are available
    Write-Host "Verifying Unix utilities..."

    $utilities = @("bash", "grep", "cut", "awk", "sed", "tr", "cat", "sort", "uniq", "head", "tail")
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
```

## Why Cygwin?

We chose Cygwin over Git Bash or WSL for the following reasons:

1. **Complete Unix Environment**: Cygwin provides all required Unix utilities through well-maintained packages
2. **Reliability**: Cygwin is specifically designed to provide a comprehensive Unix-like environment on Windows
3. **Package Management**: Easy to install specific packages (bash, grep, gawk, sed, coreutils) via setup program
4. **Consistency**: Cygwin's utilities behave identically to their Unix counterparts, ensuring cross-platform compatibility
5. **CI Availability**: Cygwin is readily available via Chocolatey on GitHub Actions Windows runners
6. **PATH Integration**: Easy to add to PATH and verify installation
7. **Explicit Package Control**: We explicitly install required packages ensuring all utilities are available

## Installation Location

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

When testing locally on Windows, developers should install Cygwin by:

1. Downloading from https://www.cygwin.com/
2. Running the installer and selecting the `bash` package
3. Adding `C:\cygwin64\bin` to the system PATH
4. Verifying with `bash --version`

See `BASH_REQUIREMENT.md` for detailed installation instructions.

## CI Execution Flow

The updated Windows CI workflow now follows this sequence:

1. **Checkout code**
2. **Set up Python**
3. **Install Cygwin** ← New step
4. **Add Cygwin to PATH** ← New step
5. **Verify bash** ← New step
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

### Git Bash
- **Pros**: Often already installed on developer machines
- **Cons**:
  - May not be in PATH by default
  - Different behavior from Unix bash in some cases
  - Harder to verify installation in CI

### WSL
- **Pros**: Most authentic Linux environment on Windows
- **Cons**:
  - More complex to set up in CI
  - Requires WSL-specific invocation syntax
  - May have performance overhead

### PowerShell Bash Emulation
- **Pros**: No installation needed
- **Cons**:
  - Not a true bash implementation
  - Incompatible with many bash scripts
  - Would require significant code changes

## Maintenance Notes

- The Cygwin installation uses Chocolatey, which is pre-installed on GitHub Actions Windows runners
- If Chocolatey is updated or Cygwin packages change, these workflows may need adjustment
- The installation path (`C:\cygwin64`) is hardcoded and should remain consistent across updates
- If additional Unix tools are needed, they can be installed using `cyg-get`

## Related Documentation

- `BASH_REQUIREMENT.md` - User documentation on bash requirement
- `tests/test_bash_availability.py` - Tests for bash availability checking
- `tests/test_bash_requirement_demo.py` - Demonstration of bash requirement behavior
