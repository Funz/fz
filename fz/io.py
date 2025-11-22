"""
IO utilities for fz package: cache, directory/file tools, and configuration loading
"""
import os
import re
import glob
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING

from .logging import log_info, log_warning
from datetime import datetime

if TYPE_CHECKING:
    import pandas

# Check if pandas is available for dict flattening
try:
    import pandas as pd
except ImportError:
    pd = None


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

    log_info(f"No cache match found in {cache_base_path} or its subdirectories")
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


def detect_content_type(text: str) -> str:
    """
    Detect the type of content in a text string.

    Returns: 'html', 'json', 'keyvalue', 'markdown', or 'plain'
    """
    if not text or not isinstance(text, str):
        return 'plain'

    text_stripped = text.strip()

    # Check for HTML tags
    if re.search(r'<(html|div|p|h1|h2|h3|img|table|body|head)', text_stripped, re.IGNORECASE):
        return 'html'

    # Check for JSON (starts with { or [)
    if text_stripped.startswith(('{', '[')):
        try:
            json.loads(text_stripped)
            return 'json'
        except (json.JSONDecodeError, ValueError):
            pass

    # Check for markdown (has markdown syntax like #, ##, *, -, ```, etc.)
    markdown_patterns = [
        r'^#{1,6}\s+.+$',  # Headers
        r'^\*\*.+\*\*$',   # Bold
        r'^_.+_$',         # Italic
        r'^\[.+\]\(.+\)$', # Links
        r'^```',           # Code blocks
        r'^\* .+$',        # Unordered lists
        r'^\d+\. .+$',     # Ordered lists
    ]
    for pattern in markdown_patterns:
        if re.search(pattern, text_stripped, re.MULTILINE):
            return 'markdown'

    # Check for key=value format (at least 2 lines with = signs)
    lines = text_stripped.split('\n')
    kv_lines = [l for l in lines if '=' in l and not l.strip().startswith('#')]
    if len(kv_lines) >= 2:
        # Verify they look like key=value pairs
        if all(len(l.split('=', 1)) == 2 for l in kv_lines[:3]):
            return 'keyvalue'

    return 'plain'


def parse_keyvalue_text(text: str) -> Dict[str, str]:
    """Parse key=value text into a dictionary."""
    result = {}
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, value = line.split('=', 1)
            result[key.strip()] = value.strip()
    return result


def process_analysis_content(
    analysis_dict: Dict[str, Any],
    iteration: int,
    results_dir: Path
) -> Dict[str, Any]:
    """
    Process get_analysis() output, detecting content types and saving to files.

    Args:
        analysis_dict: The dict returned by get_analysis()
        iteration: Current iteration number
        results_dir: Directory to save files

    Returns:
        Processed dict with file references instead of raw content
    """
    processed = {'data': analysis_dict.get('data', {})}

    # Process 'html' field if present
    if 'html' in analysis_dict:
        html_content = analysis_dict['html']
        html_file = results_dir / f"analysis_{iteration}.html"
        with open(html_file, 'w') as f:
            f.write(html_content)
        processed['html_file'] = str(html_file.name)
        log_info(f"  💾 Saved HTML to {html_file.name}")

    # Process 'text' field if present
    if 'text' in analysis_dict:
        text_content = analysis_dict['text']
        content_type = detect_content_type(text_content)

        if content_type == 'html':
            # Save as HTML file
            html_file = results_dir / f"analysis_{iteration}.html"
            with open(html_file, 'w') as f:
                f.write(text_content)
            processed['html_file'] = str(html_file.name)
            log_info(f"  💾 Detected HTML in text, saved to {html_file.name}")

        elif content_type == 'json':
            # Parse JSON and save to file
            json_file = results_dir / f"analysis_{iteration}.json"
            try:
                parsed_json = json.loads(text_content)
                with open(json_file, 'w') as f:
                    json.dump(parsed_json, f, indent=2)
                processed['json_data'] = parsed_json
                processed['json_file'] = str(json_file.name)
                log_info(f"  💾 Detected JSON, parsed and saved to {json_file.name}")
            except Exception as e:
                log_warning(f"⚠️  Failed to parse JSON: {e}")
                processed['text'] = text_content

        elif content_type == 'keyvalue':
            # Parse key=value format and save to file
            txt_file = results_dir / f"analysis_{iteration}.txt"
            with open(txt_file, 'w') as f:
                f.write(text_content)
            try:
                parsed_kv = parse_keyvalue_text(text_content)
                processed['keyvalue_data'] = parsed_kv
                processed['txt_file'] = str(txt_file.name)
                log_info(f"  💾 Detected key=value format, parsed and saved to {txt_file.name}")
            except Exception as e:
                log_warning(f"⚠️  Failed to parse key=value: {e}")
                processed['text'] = text_content

        elif content_type == 'markdown':
            # Save as markdown file
            md_file = results_dir / f"analysis_{iteration}.md"
            with open(md_file, 'w') as f:
                f.write(text_content)
            processed['md_file'] = str(md_file.name)
            log_info(f"  💾 Detected markdown, saved to {md_file.name}")

        else:
            # Keep as plain text
            processed['text'] = text_content

    return processed


def flatten_dict_recursive(d: dict, parent_key: str = '', sep: str = '_') -> dict:
    """
    Recursively flatten a nested dictionary.

    Args:
        d: Dictionary to flatten
        parent_key: Parent key prefix for nested keys
        sep: Separator to use between nested keys

    Returns:
        Flattened dictionary with keys joined by separator
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            # Recursively flatten nested dict
            items.extend(flatten_dict_recursive(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def flatten_dict_columns(df: "pandas.DataFrame") -> "pandas.DataFrame":
    """
    Recursively flatten dictionary-valued columns into separate columns.

    For each column containing dict values, creates new columns with the dict keys.
    Nested dicts are flattened recursively with keys joined by '_'.
    For example, {"stats": {"basic": {"min": 1, "max": 4}}} becomes:
    - stats_basic_min: 1
    - stats_basic_max: 4

    The original dict column is removed.

    Args:
        df: DataFrame potentially containing dict-valued columns

    Returns:
        DataFrame with dict columns recursively flattened
    """
    
    if df.empty:
        return df

    # Keep flattening until no more dict columns remain
    max_iterations = 10  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1

        # Track which columns contain dicts and need to be flattened
        dict_columns = []

        for col in df.columns:
            # Check if this column contains dict values
            # Sample first non-None value to check type
            sample_value = None
            for val in df[col]:
                if val is not None:
                    sample_value = val
                    break

            if isinstance(sample_value, dict):
                dict_columns.append(col)

        if not dict_columns:
            break  # No more dict columns to flatten

        # Flatten each dict column
        new_columns = {}

        for col in dict_columns:
            # Process each row in this column
            for row_idx, val in enumerate(df[col]):
                if isinstance(val, dict):
                    # Recursively flatten this dict
                    flattened = flatten_dict_recursive(val, parent_key=col, sep='_')

                    # Add flattened keys to new_columns
                    for flat_key, flat_val in flattened.items():
                        if flat_key not in new_columns:
                            # Initialize column with None for all rows
                            new_columns[flat_key] = [None] * len(df)
                        new_columns[flat_key][row_idx] = flat_val

        # Create new DataFrame with original columns plus flattened dict columns
        df = df.copy()

        # Add new columns
        for col_name, values in new_columns.items():
            df[col_name] = values

        # Drop original dict columns
        df = df.drop(columns=dict_columns)

    return df


def get_and_process_analysis(
    algo_instance,
    all_input_vars: List[Dict[str, float]],
    all_output_values: List[float],
    iteration: int,
    results_dir: Path,
    method_name: str = 'get_analysis'
) -> Optional[Dict[str, Any]]:
    """
    Helper to call algorithm's analysis method and process the results.

    Args:
        algo_instance: Algorithm instance
        all_input_vars: All evaluated input combinations
        all_output_values: All corresponding output values
        iteration: Current iteration number
        results_dir: Directory to save processed results
        method_name: Name of the display method ('get_analysis' or 'get_analysis_tmp')

    Returns:
        Processed analysis dict or None if method doesn't exist or fails
    """
    if not hasattr(algo_instance, method_name):
        return None

    try:
        analysis_method = getattr(algo_instance, method_name)
        analysis_dict = analysis_method(all_input_vars, all_output_values)

        if analysis_dict:
            # Process and save content intelligently
            processed = process_analysis_content(analysis_dict, iteration, results_dir)
            # Also keep the original text/html for backward compatibility
            processed['_raw'] = analysis_dict
            return processed
        return None

    except Exception as e:
        log_warning(f"⚠️  {method_name} failed: {e}")
        return None


def get_analysis(
    algo_instance,
    all_input_vars: List[Dict[str, float]],
    all_output_values: List[float],
    output_expression: str,
    algorithm: str,
    iteration: int,
    results_dir: Path
) -> Dict[str, Any]:
    """
    Create final analysis results with analysis information and DataFrame.

    Args:
        algo_instance: Algorithm instance
        all_input_vars: All evaluated input combinations
        all_output_values: All corresponding output values
        output_expression: Expression for output column name
        algorithm: Algorithm path/name
        iteration: Final iteration number
        results_dir: Directory for saving results

    Returns:
        Dict with analysis results including XY DataFrame and analysis info
    """
    # Display final results
    log_info("\n" + "="*60)
    log_info("📈 Final Results")
    log_info("="*60)

    # Get and process final analysis results
    processed_final_analysis = get_and_process_analysis(
        algo_instance, all_input_vars, all_output_values,
        iteration, results_dir, 'get_analysis'
    )

    if processed_final_analysis and '_raw' in processed_final_analysis:
        if 'text' in processed_final_analysis['_raw']:
            log_info(processed_final_analysis['_raw']['text'])
        # Remove _raw from returned dict - it's only for internal use
        del processed_final_analysis['_raw']

    # If processed_final_analysis is None, create empty dict for backward compatibility
    if processed_final_analysis is None:
        processed_final_analysis = {}

    # Create DataFrame with all input and output values
    df_data = []
    for inp_dict, out_val in zip(all_input_vars, all_output_values):
        row = inp_dict.copy()
        row[output_expression] = out_val  # Use output_expression as column name
        df_data.append(row)

    data_df = pd.DataFrame(df_data)

    # Prepare return value
    result = {
        'XY': data_df,  # DataFrame with all X and Y values
        'analysis': processed_final_analysis,  # Use processed analysis instead of raw
        'algorithm': algorithm,
        'iterations': iteration,
        'total_evaluations': len(all_input_vars),
    }

    # Add summary
    valid_count = sum(1 for v in all_output_values if v is not None)
    summary = f"{algorithm} completed: {iteration} iterations, {len(all_input_vars)} evaluations ({valid_count} valid)"
    result['summary'] = summary

    return result