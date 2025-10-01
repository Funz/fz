"""
IO utilities for fz package: cache, directory/file tools, and configuration loading
"""
import os
import re
import glob
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional

from .logging import log_info
from datetime import datetime


def ensure_unique_directory(directory_path: Path) -> tuple[Path, Optional[Path]]:
    """
    Ensure directory is unique by renaming existing ones with timestamp suffix

    Args:
        directory_path: Desired directory path

    Returns:
        Tuple of (directory_to_use, renamed_directory_path)
        - directory_to_use: Path to use for new operations (same as input)
        - renamed_directory_path: Path where existing directory was moved (None if no existing directory)
    """
    if not directory_path.exists():
        return directory_path, None

    # Generate timestamp suffix in YYYY-MM-DD_HH-MM-SS format
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    # Rename existing directory
    existing_name = directory_path.name
    parent = directory_path.parent
    new_name = f"{existing_name}_{timestamp}"
    new_path = parent / new_name

    # Rename the existing directory
    directory_path.rename(new_path)
    log_info(f"Existing directory renamed: {directory_path} → {new_path}")

    # Return original path which is now available and the renamed path
    return directory_path, new_path


def create_hash_file(directory: Path, input_files_order: List[str] = None) -> None:
    """
    Create .fz_hash file containing MD5 checksums of all files in the directory
    The input files are listed first in the order they were provided

    Args:
        directory: Directory to hash all files in
        input_files_order: Optional list of input file names in the order they should appear
    """
    hash_file = directory / ".fz_hash"

    # Get all files in directory (excluding .fz_hash itself and subdirectories)
    all_files = [f for f in directory.iterdir() if f.is_file() and f.name != ".fz_hash"]

    hash_content = []

    # If input_files_order is provided, process those files first in order
    processed_files = set()
    if input_files_order:
        for rel_path_str in input_files_order:
            file_path = directory / rel_path_str
            if file_path.exists() and file_path.is_file():
                try:
                    # Calculate MD5 hash of file content
                    hasher = hashlib.md5()
                    with open(file_path, 'rb') as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hasher.update(chunk)

                    file_hash = hasher.hexdigest()
                    hash_content.append(f"{file_hash}  {rel_path_str}")
                    processed_files.add(file_path)

                except Exception as e:
                    # Skip files that can't be read, but log the issue
                    print(f"Warning: Could not hash file {file_path}: {e}")

    # Process remaining files in alphabetical order
    remaining_files = [f for f in all_files if f not in processed_files]
    remaining_files.sort()

    for file_path in remaining_files:
        try:
            # Calculate MD5 hash of file content
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)

            file_hash = hasher.hexdigest()
            # Use relative path for consistent hashes across different locations
            rel_path = file_path.name
            hash_content.append(f"{file_hash}  {rel_path}")

        except Exception as e:
            # Skip files that can't be read, but log the issue
            print(f"Warning: Could not hash file {file_path}: {e}")

    # Write hash file
    with open(hash_file, 'w') as f:
        f.write('\n'.join(hash_content) + '\n')

    log_info(f"Created hash file: {hash_file}")


def resolve_cache_paths(cache_pattern: str) -> List[Path]:
    """
    Resolve cache pattern to list of actual cache directories

    Args:
        cache_pattern: Cache path pattern (may contain regex or glob patterns)

    Returns:
        List of Path objects for directories that match the pattern
    """
    cache_path = Path(cache_pattern)

    # If it's a simple path that exists, return it as-is
    if cache_path.exists() and cache_path.is_dir():
        return [cache_path]

    # Check if pattern contains regex/glob characters
    pattern_chars = {'*', '?', '[', ']', '{', '}', '^', '$', '.', '+', '(', ')'}
    if any(char in cache_pattern for char in pattern_chars):
        # Try glob pattern first (more common and intuitive)
        try:
            glob_matches = glob.glob(cache_pattern)
            glob_paths = [Path(p) for p in glob_matches if Path(p).is_dir()]
            if glob_paths:
                print(f"Cache pattern '{cache_pattern}' matched {len(glob_paths)} directories via glob")
                return sorted(glob_paths)
        except Exception as e:
            print(f"Glob pattern matching failed: {e}")

        # Try regex pattern on directory names in parent directory
        try:
            if '/' in cache_pattern:
                parent_dir = Path(cache_pattern).parent
                pattern_name = Path(cache_pattern).name
            else:
                parent_dir = Path('.')
                pattern_name = cache_pattern

            if parent_dir.exists():
                regex_pattern = re.compile(pattern_name)
                regex_matches = []
                for item in parent_dir.iterdir():
                    if item.is_dir() and regex_pattern.match(item.name):
                        regex_matches.append(item)

                if regex_matches:
                    print(f"Cache pattern '{cache_pattern}' matched {len(regex_matches)} directories via regex")
                    return sorted(regex_matches)
        except Exception as e:
            print(f"Regex pattern matching failed: {e}")

    # If no pattern matches found, return empty list
    print(f"Cache pattern '{cache_pattern}' did not match any directories")
    return []


def find_cache_match(cache_base_path: Path, current_hash_file: Path) -> Optional[Path]:
    """
    Find a cache subdirectory with matching .fz_hash file

    Args:
        cache_base_path: Base cache directory to search in
        current_hash_file: Hash file of current case to match against

    Returns:
        Path to matching cache subdirectory, or None if no match found
    """
    if not current_hash_file.exists():
        print(f"Current hash file not found: {current_hash_file}")
        return None

    try:
        current_hash = current_hash_file.read_text().strip()
    except Exception as e:
        print(f"Could not read current hash file: {e}")
        return None

    if not cache_base_path.exists() or not cache_base_path.is_dir():
        print(f"Cache base path does not exist or is not a directory: {cache_base_path}")
        return None

    # First check the base path itself for .fz_hash file
    base_hash_file = cache_base_path / ".fz_hash"
    if base_hash_file.exists():
        try:
            cache_hash = base_hash_file.read_text().strip()
            if cache_hash == current_hash:
                print(f"Cache match found in base path: {cache_base_path}")
                return cache_base_path
        except Exception as e:
            print(f"Could not read cache hash file {base_hash_file}: {e}")

    # Then search through all subdirectories in cache
    for cache_subdir in cache_base_path.iterdir():
        if not cache_subdir.is_dir():
            continue

        cache_hash_file = cache_subdir / ".fz_hash"
        if not cache_hash_file.exists():
            continue

        try:
            cache_hash = cache_hash_file.read_text().strip()
            if cache_hash == current_hash:
                print(f"Cache match found in subdirectory: {cache_subdir}")
                return cache_subdir
        except Exception as e:
            print(f"Could not read cache hash file {cache_hash_file}: {e}")
            continue

    print(f"No cache match found in {cache_base_path} or its subdirectories")
    return None


def load_aliases(name: str, alias_type: str = "models") -> Optional[Dict]:
    """Load model or calculator aliases from .fz directories"""
    search_dirs = [Path.cwd() / ".fz", Path.home() / ".fz"]

    for base_dir in search_dirs:
        alias_path = base_dir / alias_type / f"{name}.json"
        if alias_path.exists():
            try:
                with open(alias_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
    return None