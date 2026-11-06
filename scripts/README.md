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

`.github/workflows/release.yml` runs the script before building the wheels and the
sdist, so published packages carry the commit date and hash of the released commit.
No other workflow runs it: in a source checkout, `fz/_version.py` may hold older
commit metadata.

The version number itself has a single source, `fz/__init__.py` (read by
`pyproject.toml`, `fz --version`, `fz.config` and `manifest.json`); the
`__version__` copied into `fz/_version.py` is informative only.

### Version File Structure

The generated `fz/_version.py` file contains:

```python
__version__ = "1.3"             # From fz/__init__.py
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
