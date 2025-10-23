# CI Enhancement: List Cygwin Utilities After Installation

## Overview

Added a new CI step to list installed Cygwin utilities immediately after package installation. This provides visibility into what utilities are available and helps debug installation issues.

## Change Summary

### New Step Added

**Step Name**: `List installed Cygwin utilities (Windows)`

**Location**: After Cygwin package installation, before adding to PATH

**Workflows Updated**: 3 Windows jobs
- `.github/workflows/ci.yml` - Main CI workflow
- `.github/workflows/cli-tests.yml` - CLI tests job
- `.github/workflows/cli-tests.yml` - CLI integration tests job

## Step Implementation

```yaml
- name: List installed Cygwin utilities (Windows)
  if: runner.os == 'Windows'
  shell: pwsh
  run: |
    Write-Host "Listing executables in C:\cygwin64\bin..."
    Write-Host ""

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

    Write-Host ""
    Write-Host "Total executables installed: $($binFiles.Count)"
    Write-Host ""
    Write-Host "Sample of other utilities available:"
    $binFiles | Where-Object { $_ -notin $keyUtilities } | Select-Object -First 20 | ForEach-Object { Write-Host "  - $_" }
```

## What This Step Does

### 1. Lists All Executables
Scans `C:\cygwin64\bin` directory for all `.exe` files

### 2. Checks Key Utilities
Verifies presence of 12 essential utilities:
- bash.exe
- grep.exe
- cut.exe
- awk.exe (may be a symlink to gawk)
- gawk.exe
- sed.exe
- tr.exe
- cat.exe
- sort.exe
- uniq.exe
- head.exe
- tail.exe

### 3. Displays Status
Shows ✓ or ✗ for each required utility

### 4. Shows Statistics
- Total count of executables installed
- Sample list of first 20 other available utilities

## Sample Output

```
Listing executables in C:\cygwin64\bin...

Key utilities required by fz:
  ✓ bash.exe
  ✓ grep.exe
  ✓ cut.exe
  ✗ awk.exe (NOT FOUND)
  ✓ gawk.exe
  ✓ sed.exe
  ✓ tr.exe
  ✓ cat.exe
  ✓ sort.exe
  ✓ uniq.exe
  ✓ head.exe
  ✓ tail.exe

Total executables installed: 247

Sample of other utilities available:
  - ls.exe
  - cp.exe
  - mv.exe
  - rm.exe
  - mkdir.exe
  - chmod.exe
  - chown.exe
  - find.exe
  - tar.exe
  - gzip.exe
  - diff.exe
  - patch.exe
  - make.exe
  - wget.exe
  - curl.exe
  - ssh.exe
  - scp.exe
  - git.exe
  - python3.exe
  - perl.exe
```

## Benefits

### 1. Early Detection
See immediately after installation what utilities are available, before tests run

### 2. Debugging Aid
If tests fail due to missing utilities, the listing provides clear evidence

### 3. Documentation
Creates a record of what utilities are installed in each CI run

### 4. Change Tracking
If Cygwin packages change over time, we can see what changed in the CI logs

### 5. Transparency
Makes it clear what's in the environment before verification step runs

## Updated CI Flow

```
┌─────────────────────────────────────────┐
│ 1. Install Cygwin base (Chocolatey)    │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 2. Install packages (setup-x86_64.exe) │
│    - bash, grep, gawk, sed, coreutils  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 3. List installed utilities ← NEW      │
│    - Check 12 key utilities            │
│    - Show total count                  │
│    - Display sample of others          │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 4. Add Cygwin to PATH                  │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 5. Verify Unix utilities               │
│    - Run each utility with --version   │
│    - Fail if any missing               │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 6. Install Python dependencies         │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│ 7. Run tests                           │
└─────────────────────────────────────────┘
```

## Use Cases

### Debugging Missing Utilities
If the verification step fails, check the listing step to see:
- Was the utility installed at all?
- Is it named differently than expected?
- Did the package installation complete successfully?

### Understanding Cygwin Defaults
See what utilities come with the coreutils package

### Tracking Package Changes
If Cygwin updates change what's included, the CI logs will show the difference

### Verifying Package Installation
Confirm that the `Start-Process` command successfully installed packages

## Example Debugging Scenario

**Problem**: Tests fail with "awk: command not found"

**Investigation**:
1. Check "List installed Cygwin utilities" step output
2. Look for `awk.exe` in the key utilities list
3. Possible findings:
   - ✗ `awk.exe (NOT FOUND)` → Package installation failed
   - ✓ `awk.exe` → Package installed, but PATH issue
   - Only `gawk.exe` present → Need to verify awk is symlinked to gawk

**Resolution**: Based on findings, adjust package list or PATH configuration

## Technical Details

### Why Check .exe Files?
On Windows, Cygwin executables have `.exe` extension. Checking for `.exe` files ensures we're looking at actual executables, not shell scripts or symlinks.

### Why Check Both awk.exe and gawk.exe?
- `gawk.exe` is the GNU awk implementation
- `awk.exe` may be a symlink or copy of gawk
- We check both to understand the exact setup

### Why Sample Only First 20 Other Utilities?
- Cygwin typically has 200+ executables
- Showing all would clutter the logs
- First 20 provides representative sample
- Full list available via `Get-ChildItem` if needed

## Files Modified

1. `.github/workflows/ci.yml` - Added listing step at line 75
2. `.github/workflows/cli-tests.yml` - Added listing step at lines 69 and 344
3. `.github/workflows/WINDOWS_CI_SETUP.md` - Updated documentation with new step

## Validation

- ✅ YAML syntax validated
- ✅ All 3 Windows jobs updated
- ✅ Step positioned correctly in workflow
- ✅ Documentation updated

## Future Enhancements

Possible future improvements:
1. Save full utility list to artifact for later inspection
2. Compare utility list across different CI runs
3. Add checks for specific utility versions
4. Create a "known good" baseline and compare against it
