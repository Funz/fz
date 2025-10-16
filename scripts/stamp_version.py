#!/usr/bin/env python3
"""
Stamp version information into fz/_version.py

This script is intended to be run by CI workflows to embed
static version information (commit date, hash) into the package.

Usage:
    python scripts/stamp_version.py
"""

import os
import subprocess
import sys
from pathlib import Path


def get_git_commit_date():
    """Get the date of the last git commit"""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ci'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Could not get git commit date: {e}", file=sys.stderr)
        return "unknown"


def get_git_commit_hash():
    """Get the hash of the last git commit"""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"Warning: Could not get git commit hash: {e}", file=sys.stderr)
        return "unknown"


def get_version_from_init():
    """Extract version from fz/__init__.py"""
    init_file = Path(__file__).parent.parent / 'fz' / '__init__.py'
    try:
        with open(init_file, 'r') as f:
            for line in f:
                if line.startswith('__version__'):
                    # Extract version string
                    return line.split('=')[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"Warning: Could not read version from __init__.py: {e}", file=sys.stderr)
    return "0.0.0"


def stamp_version():
    """Stamp version information into fz/_version.py"""
    version = get_version_from_init()
    commit_date = get_git_commit_date()
    commit_hash = get_git_commit_hash()

    version_file = Path(__file__).parent.parent / 'fz' / '_version.py'

    content = f'''"""
Static version information for fz package

This file is automatically updated by the CI workflow.
DO NOT EDIT MANUALLY - changes will be overwritten.
"""

__version__ = "{version}"
__commit_date__ = "{commit_date}"
__commit_hash__ = "{commit_hash}"
'''

    try:
        with open(version_file, 'w') as f:
            f.write(content)
        print(f"Stamped version information:")
        print(f"  Version: {version}")
        print(f"  Commit date: {commit_date}")
        print(f"  Commit hash: {commit_hash}")
        print(f"  File: {version_file}")
        return 0
    except Exception as e:
        print(f"Error: Could not write to {version_file}: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(stamp_version())
