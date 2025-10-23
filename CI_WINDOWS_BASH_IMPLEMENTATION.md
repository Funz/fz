# Windows CI Bash and Unix Utilities Implementation - Summary

## Overview

This document summarizes the complete implementation of bash and Unix utilities availability checking, and Cygwin installation for Windows in the `fz` package.

## Problem Statement

The `fz` package requires bash and Unix utilities to be available on Windows for:

1. **Output evaluation** (`fzo()`): Shell commands using Unix utilities (grep, cut, awk, tr, sed, cat, etc.) are used to parse and extract output values from result files
2. **Calculation execution** (`fzr()`, `sh://` calculator): Bash is used as the shell interpreter for running calculations

### Required Utilities

- **bash** - Shell interpreter
- **grep** - Pattern matching (heavily used for output parsing)
- **cut** - Field extraction (e.g., `cut -d '=' -f2`)
- **awk** - Text processing and field extraction
- **sed** - Stream editing
- **tr** - Character translation/deletion (e.g., `tr -d ' '`)
- **cat** - File concatenation
- **sort**, **uniq**, **head**, **tail** - Additional text processing

Previously, the package would fail with cryptic errors on Windows when these utilities were not available.

## Solution Components

### 1. Code Changes

#### A. Startup Check (`fz/core.py`)
- Added `check_bash_availability_on_windows()` function
- Checks if bash is in PATH on Windows at import time
- Raises `RuntimeError` with helpful installation instructions if bash is not found
- Only runs on Windows (no-op on Linux/macOS)

**Lines**: 107-148

#### B. Import-Time Check (`fz/__init__.py`)
- Calls `check_bash_availability_on_windows()` when fz is imported
- Ensures users get immediate feedback if bash is missing
- Prevents confusing errors later during execution

**Lines**: 13-17

#### C. Shell Execution Updates (`fz/core.py`)
- Updated `fzo()` to use bash as shell interpreter on Windows
- Added `executable` parameter to `subprocess.run()` calls
- Two locations updated: subdirectory processing and single-file processing

**Lines**: 542-557, 581-596

### 2. Test Coverage

#### A. Main Test Suite (`tests/test_bash_availability.py`)
Comprehensive pytest test suite with 12 tests:
- Bash check on non-Windows platforms (no-op)
- Bash check on Windows without bash (raises error)
- Bash check on Windows with bash (succeeds)
- Error message format and content validation
- Logging when bash is found
- Various bash installation paths (Cygwin, Git Bash, WSL, etc.)
- Platform-specific behavior (Linux, macOS, Windows)

**Test count**: 12 tests, all passing

#### B. Demonstration Tests (`tests/test_bash_requirement_demo.py`)
Demonstration tests that serve as both tests and documentation:
- Demo of error message on Windows without bash
- Demo of successful import with Cygwin, Git Bash, WSL
- Error message readability verification
- Current platform compatibility test
- Actual Windows bash availability test (skipped on non-Windows)

**Test count**: 8 tests (7 passing, 1 skipped on non-Windows)

### 3. CI/CD Changes

#### A. Main CI Workflow (`.github/workflows/ci.yml`)

**Changes**:
- Replaced Git Bash installation with Cygwin
- Added three new steps for Windows jobs:
  1. Install Cygwin with bash and bc
  2. Add Cygwin to PATH
  3. Verify bash availability

**Impact**:
- All Windows test jobs (Python 3.10, 3.11, 3.12, 3.13) now have bash available
- Tests can run the full suite without bash-related failures
- Early failure if bash is not available (before tests run)

#### B. CLI Tests Workflow (`.github/workflows/cli-tests.yml`)

**Changes**:
- Updated both `cli-tests` and `cli-integration-tests` jobs
- Same three-step installation process as main CI
- Ensures CLI tests can execute shell commands properly

**Jobs Updated**:
- `cli-tests` job
- `cli-integration-tests` job

### 4. Documentation

#### A. User Documentation (`BASH_REQUIREMENT.md`)
Complete guide for users covering:
- Why bash is required
- Startup check behavior
- Installation instructions for Cygwin, Git Bash, and WSL
- Implementation details
- Testing instructions
- Platform-specific information

#### B. CI Documentation (`.github/workflows/WINDOWS_CI_SETUP.md`)
Technical documentation for maintainers covering:
- Workflows updated
- Installation steps with code examples
- Why Cygwin was chosen
- Installation location and PATH setup
- Verification process
- Testing on Windows
- CI execution flow
- Alternative approaches considered
- Maintenance notes

#### C. This Summary (`CI_WINDOWS_BASH_IMPLEMENTATION.md`)
Complete overview of all changes made

## Files Modified

### Code Files
1. `fz/core.py` - Added bash checking function and updated shell execution
2. `fz/__init__.py` - Added startup check call

### Test Files
1. `tests/test_bash_availability.py` - Comprehensive test suite (new)
2. `tests/test_bash_requirement_demo.py` - Demonstration tests (new)

### CI/CD Files
1. `.github/workflows/ci.yml` - Updated Windows system dependencies
2. `.github/workflows/cli-tests.yml` - Updated Windows system dependencies (2 jobs)

### Documentation Files
1. `BASH_REQUIREMENT.md` - User-facing documentation (new)
2. `.github/workflows/WINDOWS_CI_SETUP.md` - CI documentation (new)
3. `CI_WINDOWS_BASH_IMPLEMENTATION.md` - This summary (new)

## Test Results

### Local Tests
```
tests/test_bash_availability.py ............                    [12 passed]
tests/test_bash_requirement_demo.py .......s                    [7 passed, 1 skipped]
```

### Existing Tests
- All existing tests continue to pass
- No regressions introduced
- Example: `test_fzo_fzr_coherence.py` passes successfully

## Verification Checklist

- [x] Bash check function implemented in `fz/core.py`
- [x] Startup check added to `fz/__init__.py`
- [x] Shell execution updated to use bash on Windows
- [x] Comprehensive test suite created
- [x] Demonstration tests created
- [x] Main CI workflow updated for Windows
- [x] CLI tests workflow updated for Windows
- [x] User documentation created
- [x] CI documentation created
- [x] All tests passing
- [x] No regressions in existing tests
- [x] YAML syntax validated for all workflows

## Installation Instructions for Users

### Windows Users

1. **Install Cygwin** (recommended):
   ```
   Download from: https://www.cygwin.com/
   Ensure 'bash' package is selected during installation
   Add C:\cygwin64\bin to PATH
   ```

2. **Or install Git for Windows**:
   ```
   Download from: https://git-scm.com/download/win
   Add Git\bin to PATH
   ```

3. **Or use WSL**:
   ```
   wsl --install
   Ensure bash.exe is in Windows PATH
   ```

4. **Verify installation**:
   ```cmd
   bash --version
   ```

### Linux/macOS Users

No action required - bash is typically available by default.

## CI Execution Example

When a Windows CI job runs:

1. Checkout code
2. Set up Python
3. **Install Cygwin** ← New
4. **Add Cygwin to PATH** ← New
5. **Verify bash** ← New
6. Install R and dependencies
7. Install Python dependencies
   - `import fz` checks for bash ← Will succeed
8. Run tests ← Will use bash for shell commands

## Error Messages

### Without bash on Windows:
```
RuntimeError: ERROR: bash is not available in PATH on Windows.

fz requires bash to run shell commands and evaluate output expressions.
Please install one of the following:

1. Cygwin (recommended):
   - Download from: https://www.cygwin.com/
   ...
```

### CI verification failure:
```
ERROR: bash is not available in PATH
Exit code: 1
```

## Benefits

1. **User Experience**:
   - Clear, actionable error messages
   - Immediate feedback at import time
   - Multiple installation options provided

2. **CI/CD**:
   - Consistent test environment across all platforms
   - Early failure detection
   - Automated verification

3. **Code Quality**:
   - Comprehensive test coverage
   - Well-documented implementation
   - No regressions in existing functionality

4. **Maintenance**:
   - Clear documentation for future maintainers
   - Modular implementation
   - Easy to extend or modify

## Future Considerations

1. **Alternative shells**: If needed, the framework could be extended to support other shells
2. **Portable bash**: Could bundle a minimal bash distribution with the package
3. **Shell abstraction**: Could create a shell abstraction layer to support multiple shells
4. **Windows-native commands**: Could provide Windows-native alternatives for common shell operations

## Conclusion

The implementation successfully addresses the bash requirement on Windows through:
- Clear error messages at startup
- Proper shell configuration in code
- Automated CI setup with verification
- Comprehensive documentation and testing

Windows users will now get helpful guidance on installing bash, and the CI environment ensures all tests run reliably on Windows with proper bash support.
