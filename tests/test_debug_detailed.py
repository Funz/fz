#!/usr/bin/env python3
"""
Debug path resolution with detailed output
"""
import sys
import shlex
import os
from pathlib import Path

def debug_resolve_paths_in_segment(segment: str, original_cwd: str) -> str:
    """
    Debug version of _resolve_paths_in_segment with detailed output
    """
    import shlex
    import re

    print(f"Processing segment: {segment}")

    # Parse command parts using shlex for proper quote handling
    try:
        command_parts = shlex.split(segment)
    except ValueError:
        # Fallback to simple split if shlex fails
        command_parts = segment.split()

    print(f"Command parts: {command_parts}")

    if not command_parts:
        return segment

    resolved_parts = []

    # File operation patterns that take multiple file arguments
    multi_file_commands = {'cp', 'mv', 'ln', 'tar', 'zip', 'rsync', 'diff', 'cmp'}

    for i, part in enumerate(command_parts):
        should_resolve = False
        original_part = part
        reason = "no reason"

        print(f"\n  [{i}] Processing: '{part}'")

        # Skip if it's clearly not a file path
        if (part.startswith('-') and len(part) > 1 or  # Command flags
            part in ['|', '||', '&&', ';', '>', '>>', '<', '<<'] or  # Shell operators
            part.startswith('$') or  # Variables
            part.startswith('${') or part.endswith('}') or  # Variable expansions
            re.match(r'^[0-9]+$', part) or  # Pure numbers
            part in ['true', 'false', 'null', 'nil'] or  # Literals
            part.startswith('http://') or part.startswith('https://') or  # URLs
            part.startswith('ftp://') or part.startswith('ssh://')):  # URLs
            should_resolve = False
            reason = "skip - special token"

        # Path detection logic (enhanced)
        elif "/" in part and not part.startswith('-'):
            # Contains slash - likely a path
            should_resolve = True
            reason = "contains slash"

        # Check if this follows a redirection operator
        elif i > 0 and command_parts[i-1] in ['>', '>>', '<', '<<']:
            # File after redirection operator
            if command_parts[i-1] in ['<', '<<']:
                # Input redirection - resolve the path
                should_resolve = True
                reason = "input redirection"
            else:
                # Output redirection - only resolve if it has path separators
                should_resolve = "/" in part
                reason = f"output redirection ({'has slash' if '/' in part else 'no slash'})"

        elif part in ['.', '..'] or part.startswith('./') or part.startswith('../'):
            # Relative path references
            should_resolve = True
            reason = "relative path reference"

        elif (part.endswith('.sh') or part.endswith('.py') or part.endswith('.pl') or
              part.endswith('.rb') or part.endswith('.js')):
            # Script files - these should be resolved to absolute paths
            should_resolve = True
            reason = "script file"

        elif (part.endswith('.txt') or part.endswith('.log') or part.endswith('.conf') or
              part.endswith('.cfg') or part.endswith('.ini') or part.endswith('.json') or
              part.endswith('.xml') or part.endswith('.csv') or part.endswith('.dat')):
            # Data/config files - more intelligent resolution
            if "/" in part:  # Contains path separator - always resolve
                should_resolve = True
                reason = "data file with path"
            elif (i > 0 and command_parts[i-1] in ['>', '>>']):  # Output redirection
                should_resolve = False  # Keep output files relative
                reason = "output redirection data file"
            elif (i > 0 and command_parts[i-1] in ['<', '<<']):  # Input redirection
                should_resolve = True  # Resolve input files
                reason = "input redirection data file"
            elif (i > 0 and command_parts[i-1] in {'cat', 'grep', 'awk', 'sed', 'head', 'tail', 'sort', 'uniq', 'wc'}):
                # Input to read-only commands - resolve
                should_resolve = True
                reason = "input to read command"
            elif (i > 0 and command_parts[i-1] in {'-f', '--file', '--input', '--config'}):
                # File flag argument - resolve
                should_resolve = True
                reason = "file flag argument"
            elif (i > 0 and command_parts[i-1] == 'cp' and
                  i == len(command_parts) - 1):  # Last argument to cp (destination)
                should_resolve = False  # Keep destination relative
                reason = f"cp destination (i={i}, len={len(command_parts)})"
            elif (i > 0 and command_parts[i-1] == 'mv' and
                  i == len(command_parts) - 1):  # Last argument to mv (destination)
                should_resolve = False  # Keep destination relative
                reason = f"mv destination (i={i}, len={len(command_parts)})"
            else:
                # For other cases, if it doesn't have a path separator, keep it relative
                should_resolve = False
                reason = "data file - keep relative"

        print(f"      Decision: {should_resolve} - {reason}")

        if should_resolve:
            if os.path.isabs(part):
                # Already absolute
                resolved_parts.append(original_part)
                print(f"      Result: '{original_part}' (already absolute)")
            else:
                # Make it absolute
                abs_path = os.path.abspath(os.path.join(original_cwd, part))
                # Preserve original quoting style if needed
                if " " in abs_path or "'" in abs_path or '"' in abs_path:
                    resolved_parts.append(shlex.quote(abs_path))
                else:
                    resolved_parts.append(abs_path)
                print(f"      Result: '{abs_path}' (resolved)")
        else:
            # Not a file path - preserve as is
            resolved_parts.append(original_part)
            print(f"      Result: '{original_part}' (preserved)")

    # Reconstruct the segment
    resolved_segment = " ".join(resolved_parts)
    print(f"\nFinal result: {resolved_segment}")
    return resolved_segment

def test_detailed_resolution():
    """Test with detailed debug output"""
    # Use project root (parent of tests directory)
    original_cwd = str(Path(__file__).parent.parent.absolute())

    test_segments = [
        "cp test_input.txt copy.txt",
        "echo 'result = 10' > output.txt"
    ]

    print("🔍 Detailed Path Resolution Debug")
    print("=" * 60)

    results = []
    for segment in test_segments:
        print(f"\n{'='*60}")
        result = debug_resolve_paths_in_segment(segment, original_cwd)
        results.append(result is not None)
        print(f"{'='*60}")

    # Assert all segments were processed
    assert all(results), "Some segments failed to process"

if __name__ == "__main__":
    test_detailed_resolution()