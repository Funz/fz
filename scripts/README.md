# Version Stamping Scripts

## Overview

This directory contains scripts for managing version information in the fz package.

## stamp_version.py

This script stamps static version information into `fz/_version.py` from git metadata.

### What it does

1. Reads the version number from `fz/__init__.py`
2. Extracts the last git commit date
3. Extracts the last git commit hash (short format)
4. Writes these values into `fz/_version.py` as static fields

### Usage

#### Manual execution

```bash
python scripts/stamp_version.py
```

#### CI/CD Integration

The script is automatically run by GitHub Actions workflows:
- `.github/workflows/ci.yml` - Stamps version before running tests and building packages
- `.github/workflows/stamp-version.yml` - Dedicated workflow for version stamping

### CI Workflow Integration

All CI workflows that build or test the package have been updated to:

1. Checkout with full git history (`fetch-depth: 0`)
2. Run the stamp script early in the workflow
3. Proceed with building/testing using the stamped version

This ensures that:
- All built packages contain accurate version information
- Tests run with the correct version metadata
- The version information matches the exact git commit being built

### Version File Structure

The generated `fz/_version.py` file contains:

```python
__version__ = "0.9.0"           # From fz/__init__.py
__commit_date__ = "2025-10-..."  # From git log
__commit_hash__ = "42d1e24"      # From git rev-parse
```

### Fallback Behavior

If git is not available or fails:
- `__commit_date__` defaults to "unknown"
- `__commit_hash__` defaults to "unknown"
- `__version__` is still extracted from `fz/__init__.py`

### Why Static Stamping?

Static stamping (vs. dynamic git queries at runtime) provides:
- ✓ Works in installed packages without git history
- ✓ No subprocess overhead at runtime
- ✓ Reliable and consistent version information
- ✓ No dependency on git being installed in production
