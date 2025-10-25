#!/usr/bin/env python3
"""
Command line interface for fz package
"""
import argparse
import json
import sys
from pathlib import Path

try:
    from importlib.metadata import version
except ImportError:
    from importlib_metadata import version

from . import fzi as fzi_func, fzc as fzc_func, fzo as fzo_func, fzr as fzr_func, fzd as fzd_func


# Get package version
def get_version():
    """Get the package version"""
    try:
        # Try the new package name first
        return version("funz-fz")
    except Exception:
        try:
            # Fallback to old package name for backward compatibility
            return version("fz")
        except Exception:
            return "unknown"


# Helper functions used by all CLI commands
def parse_argument(arg_str, alias_type=None):
    """
    Parse an argument that can be: JSON string, JSON file path, or alias.

    Tries in order:
    1. JSON string (e.g., '{"key": "value"}')
    2. JSON file path (e.g., 'path/to/file.json')
    3. Alias (e.g., 'myalias' -> looks for .fz/<alias_type>/myalias.json)

    Args:
        arg_str: The argument string to parse
        alias_type: Type of alias ('models', 'calculators', 'algorithms', etc.)
                   If provided and string is not JSON/file, treats as alias

    Returns:
        Parsed data (dict/list/string)
    """
    if not arg_str:
        return None

    json_error = None
    file_error = None

    # Try 1: Parse as JSON string (preferred)
    if arg_str.strip().startswith(('{', '[')):
        try:
            return json.loads(arg_str)
        except json.JSONDecodeError as e:
            json_error = str(e)
            # Fall through to next option

    # Try 2: Load as JSON file path
    if arg_str.endswith('.json'):
        try:
            path = Path(arg_str)
            if path.exists():
                with open(path) as f:
                    return json.load(f)
            else:
                file_error = f"File not found: {arg_str}"
        except IOError as e:
            file_error = f"Cannot read file: {e}"
        except json.JSONDecodeError as e:
            file_error = f"Invalid JSON in file {arg_str}: {e}"
        # Fall through to next option

    # Try 3: Load as alias
    if alias_type:
        from .io import load_aliases
        alias_data = load_aliases(arg_str, alias_type)
        if alias_data is not None:
            return alias_data

        # If alias not found, print a warning
        if json_error or file_error:
            # We tried multiple formats and all failed
            print(f"⚠️  Warning: Could not parse argument '{arg_str}':", file=sys.stderr)
            if json_error:
                print(f"    - Invalid JSON: {json_error}", file=sys.stderr)
            if file_error:
                print(f"    - File issue: {file_error}", file=sys.stderr)
            print(f"    - Alias '{arg_str}' not found in .fz/{alias_type}/", file=sys.stderr)
            print(f"    Using raw value: '{arg_str}'", file=sys.stderr)
    elif json_error or file_error:
        # No alias_type, but we had errors parsing
        print(f"⚠️  Warning: Could not parse argument '{arg_str}':", file=sys.stderr)
        if json_error:
            print(f"    - Invalid JSON: {json_error}", file=sys.stderr)
        if file_error:
            print(f"    - File issue: {file_error}", file=sys.stderr)
        print(f"    Using raw value: '{arg_str}'", file=sys.stderr)

    # If alias_type not provided or alias not found, return as-is (might be an alias name)
    # The calling code can decide what to do with it
    return arg_str


def parse_model(model_str):
    """Parse model from JSON string, JSON file, or alias"""
    return parse_argument(model_str, alias_type='models')


def parse_variables(var_str):
    """Parse variables from JSON string or JSON file"""
    return parse_argument(var_str, alias_type=None)


def parse_calculators(calc_str):
    """Parse calculators from JSON string, JSON file, or alias"""
    result = parse_argument(calc_str, alias_type='calculators')

    # Wrap dict in list if it's a single calculator definition
    if isinstance(result, dict):
        result = [result]

    return result


def format_output(data, format_type='markdown'):
    """
    Format output data in various formats

    Args:
        data: Dictionary or list to format
        format_type: One of 'json', 'csv', 'html', 'markdown', 'table'

    Returns:
        Formatted string
    """
    if format_type == 'json':
        return json.dumps(data, indent=2)

    # Convert data to table format
    if isinstance(data, dict):
        # Flatten nested dictionaries for table display
        rows = []
        for key, value in data.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    rows.append({'Key': f"{key}.{subkey}", 'Value': str(subvalue)})
            elif isinstance(value, list):
                rows.append({'Key': key, 'Value': ', '.join(str(v) for v in value)})
            else:
                rows.append({'Key': key, 'Value': str(value)})

        if not rows:
            return "No data"

        headers = ['Key', 'Value']
    elif isinstance(data, list):
        if not data:
            return "No data"
        if isinstance(data[0], dict):
            headers = list(data[0].keys())
            rows = data
        else:
            headers = ['Value']
            rows = [{'Value': str(item)} for item in data]
    else:
        return str(data)

    if format_type == 'csv':
        lines = [','.join(headers)]
        for row in rows:
            values = [str(row.get(h, '')) for h in headers]
            # Escape values containing commas or quotes
            values = [f'"{v}"' if ',' in v or '"' in v else v for v in values]
            lines.append(','.join(values))
        return '\n'.join(lines)

    elif format_type == 'html':
        html = ['<table border="1">', '  <thead>', '    <tr>']
        html.extend([f'      <th>{h}</th>' for h in headers])
        html.extend(['    </tr>', '  </thead>', '  <tbody>'])
        for row in rows:
            html.append('    <tr>')
            for h in headers:
                value = str(row.get(h, ''))
                # Escape HTML special characters
                value = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                html.append(f'      <td>{value}</td>')
            html.append('    </tr>')
        html.extend(['  </tbody>', '</table>'])
        return '\n'.join(html)

    elif format_type == 'markdown':
        lines = ['| ' + ' | '.join(headers) + ' |']
        lines.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
        for row in rows:
            values = [str(row.get(h, '')) for h in headers]
            # Escape pipe characters in markdown
            values = [v.replace('|', '\\|') for v in values]
            lines.append('| ' + ' | '.join(values) + ' |')
        return '\n'.join(lines)

    elif format_type == 'table':
        # ASCII table format
        # Calculate column widths
        col_widths = {h: len(h) for h in headers}
        for row in rows:
            for h in headers:
                col_widths[h] = max(col_widths[h], len(str(row.get(h, ''))))

        # Build table
        lines = []
        # Header
        header_line = '| ' + ' | '.join(h.ljust(col_widths[h]) for h in headers) + ' |'
        separator = '+' + '+'.join('-' * (col_widths[h] + 2) for h in headers) + '+'
        lines.append(separator)
        lines.append(header_line)
        lines.append(separator)
        # Rows
        for row in rows:
            values = [str(row.get(h, '')).ljust(col_widths[h]) for h in headers]
            lines.append('| ' + ' | '.join(values) + ' |')
        lines.append(separator)
        return '\n'.join(lines)

    else:
        raise ValueError(f"Unsupported format: {format_type}")


def fzi_main():
    """Entry point for fzi command"""
    parser = argparse.ArgumentParser(description="fzi - Parse input to find variables")
    parser.add_argument("--version", action="version", version=f"fzi {get_version()}")
    parser.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser.add_argument("--format", "-f", default="markdown",
                        choices=["json", "csv", "html", "markdown", "table"],
                        help="Output format (default: markdown)")

    args = parser.parse_args()

    try:
        model = parse_model(args.model)
        result = fzi_func(args.input_path, model)
        print(format_output(result, args.format))
        return 0
    except TypeError as e:
        # TypeError messages already printed by decorator
        # Just show help and exit
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as e:
        # These error messages already printed by decorator
        # Just exit with error code
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def fzc_main():
    """Entry point for fzc command"""
    parser = argparse.ArgumentParser(description="fzc - Compile input with variable values")
    parser.add_argument("--version", action="version", version=f"fzc {get_version()}")
    parser.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser.add_argument("--input_variables", "-v", required=True, help="Variable values (JSON file or inline JSON)")
    parser.add_argument("--output_dir", "-o", default="output", help="Output directory (default: output)")

    args = parser.parse_args()

    try:
        model = parse_model(args.model)
        variables = parse_variables(args.input_variables)
        fzc_func(args.input_path, variables, model, output_dir=args.output_dir)
        print(f"Compiled input saved to {args.output_dir}")
        return 0
    except TypeError as e:
        # TypeError messages already printed by decorator
        # Just show help and exit
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as e:
        # These error messages already printed by decorator
        # Just exit with error code
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def fzo_main():
    """Entry point for fzo command"""
    parser = argparse.ArgumentParser(description="fzo - Parse output files")
    parser.add_argument("--version", action="version", version=f"fzo {get_version()}")
    parser.add_argument("--output_path", "-o", required=True, help="Output file or directory")
    parser.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser.add_argument("--format", "-f", default="markdown",
                        choices=["json", "csv", "html", "markdown", "table"],
                        help="Output format (default: markdown)")

    args = parser.parse_args()

    try:
        model = parse_model(args.model)
        result = fzo_func(args.output_path, model)
        print(format_output(result, args.format))
        return 0
    except TypeError as e:
        # TypeError messages already printed by decorator
        # Just show help and exit
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as e:
        # These error messages already printed by decorator
        # Just exit with error code
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def fzr_main():
    """Entry point for fzr command"""
    parser = argparse.ArgumentParser(description="fzr - Run full parametric calculations")
    parser.add_argument("--version", action="version", version=f"fzr {get_version()}")
    parser.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser.add_argument("--input_variables", "-v", required=True, help="Variable values (JSON file or inline JSON)")
    parser.add_argument("--results_dir", "-r", default="results", help="Results directory (default: results)")
    parser.add_argument("--calculators", "-c", help="Calculator specifications (JSON file or inline JSON)")
    parser.add_argument("--format", "-f", default="markdown",
                        choices=["json", "csv", "html", "markdown", "table"],
                        help="Output format (default: markdown)")

    args = parser.parse_args()

    try:
        model = parse_model(args.model)
        variables = parse_variables(args.input_variables)
        calculators = parse_calculators(args.calculators) if args.calculators else None

        result = fzr_func(args.input_path, variables, model,
                    results_dir=args.results_dir,
                    calculators=calculators)
        print(format_output(result, args.format))
        return 0
    except TypeError as e:
        # TypeError messages already printed by decorator
        # Just show help and exit
        print(file=sys.stderr)
        parser.print_help(sys.stderr)
        return 1
    except (ValueError, FileNotFoundError) as e:
        # These error messages already printed by decorator
        # Just exit with error code
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def fzd_main():
    """Entry point for fzd command"""
    parser = argparse.ArgumentParser(description="fzd - Iterative design of experiments with algorithms")
    parser.add_argument("--version", action="version", version=f"fzd {get_version()}")
    parser.add_argument("--input_dir", "-i", required=True, help="Input directory path")
    parser.add_argument("--input_vars", "-v", required=True, help="Input variable ranges (JSON file or inline JSON)")
    parser.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser.add_argument("--output_expression", "-e", required=True, help="Output expression to minimize (e.g., 'out1 + out2 * 2')")
    parser.add_argument("--algorithm", "-a", required=True, help="Algorithm name (randomsampling, brent, bfgs, ...)")
    parser.add_argument("--results_dir", "-r", default="results_fzd", help="Results directory (default: results_fzd)")
    parser.add_argument("--calculators", "-c", help="Calculator specifications (JSON file or inline JSON)")
    parser.add_argument("--options", "-o", help="Algorithm options (JSON file or inline JSON)")

    args = parser.parse_args()

    try:
        model = parse_model(args.model)
        variables = parse_variables(args.input_vars)

        calculators = None
        if args.calculators:
            if args.calculators.endswith('.json'):
                with open(args.calculators) as f:
                    calculators = json.load(f)
            else:
                calculators = json.loads(args.calculators)

        # Parse algorithm options
        algo_options = {}
        if args.options:
            if args.options.endswith('.json'):
                with open(args.options) as f:
                    algo_options = json.load(f)
            else:
                algo_options = json.loads(args.options)

        result = fzd_func(
            args.input_dir,
            variables,
            model,
            args.output_expression,
            args.algorithm,
            results_dir=args.results_dir,
            calculators=calculators,
            **algo_options
        )

        # Print summary
        print("\n" + "="*60)
        print(result['summary'])
        print("="*60)

        if 'analysis' in result and 'text' in result['analysis']:
            print(result['analysis']['text'])

        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    """Entry point for 'fz' command with subcommands"""
    parser = argparse.ArgumentParser(description="fz - Parametric scientific computing")
    parser.add_argument("--version", action="version", version=f"fz {get_version()}")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # input command (fzi)
    parser_input = subparsers.add_parser("input", help="Parse input to find variables")
    parser_input.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser_input.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser_input.add_argument("--format", "-f", default="markdown",
                              choices=["json", "csv", "html", "markdown", "table"],
                              help="Output format (default: markdown)")

    # compile command (fzc)
    parser_compile = subparsers.add_parser("compile", help="Compile input with variable values")
    parser_compile.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser_compile.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser_compile.add_argument("--input_variables", "-v", required=True, help="Variable values (JSON file or inline JSON)")
    parser_compile.add_argument("--output_dir", "-o", default="output", help="Output directory (default: output)")

    # output command (fzo)
    parser_output = subparsers.add_parser("output", help="Parse output files")
    parser_output.add_argument("--output_path", "-o", required=True, help="Output file or directory")
    parser_output.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser_output.add_argument("--format", "-f", default="markdown",
                               choices=["json", "csv", "html", "markdown", "table"],
                               help="Output format (default: markdown)")

    # run command (fzr)
    parser_run = subparsers.add_parser("run", help="Run full parametric calculations")
    parser_run.add_argument("--input_path", "-i", required=True, help="Input file or directory")
    parser_run.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser_run.add_argument("--input_variables", "-v", required=True, help="Variable values (JSON file or inline JSON)")
    parser_run.add_argument("--results_dir", "-r", default="results", help="Results directory (default: results)")
    parser_run.add_argument("--calculators", "-c", help="Calculator specifications (JSON file or inline JSON)")
    parser_run.add_argument("--format", "-f", default="markdown",
                            choices=["json", "csv", "html", "markdown", "table"],
                            help="Output format (default: markdown)")

    # design command (fzd)
    parser_design = subparsers.add_parser("design", help="Iterative design of experiments with algorithms")
    parser_design.add_argument("--input_dir", "-i", required=True, help="Input directory path")
    parser_design.add_argument("--input_vars", "-v", required=True, help="Input variable ranges (JSON file or inline JSON)")
    parser_design.add_argument("--model", "-m", required=True, help="Model definition (JSON file, inline JSON, or alias)")
    parser_design.add_argument("--output_expression", "-e", required=True, help="Output expression to minimize (e.g., 'out1 + out2 * 2')")
    parser_design.add_argument("--algorithm", "-a", required=True, help="Algorithm name (randomsampling, brent, bfgs, ...)")
    parser_design.add_argument("--results_dir", "-r", default="results_fzd", help="Results directory (default: results_fzd)")
    parser_design.add_argument("--calculators", "-c", help="Calculator specifications (JSON file or inline JSON)")
    parser_design.add_argument("--options", "-o", help="Algorithm options (JSON file or inline JSON)")

    # install command (supports both models and algorithms)
    parser_install = subparsers.add_parser("install", help="Install a model or algorithm from GitHub or local zip file")
    install_subparsers = parser_install.add_subparsers(dest="install_type", help="Type of resource to install")

    # install model subcommand
    parser_install_model = install_subparsers.add_parser("model", help="Install a model")
    parser_install_model.add_argument("source", help="Model source (GitHub name, URL, or local zip file)")
    parser_install_model.add_argument("--global", dest="global_install", action="store_true",
                                      help="Install to ~/.fz/models/ (default: ./.fz/models/)")

    # install algorithm subcommand
    parser_install_algorithm = install_subparsers.add_parser("algorithm", help="Install an algorithm")
    parser_install_algorithm.add_argument("source", help="Algorithm source (GitHub name, URL, or local zip file)")
    parser_install_algorithm.add_argument("--global", dest="global_install", action="store_true",
                                          help="Install to ~/.fz/algorithms/ (default: ./.fz/algorithms/)")

    # list command (supports both models and algorithms)
    parser_list = subparsers.add_parser("list", help="List installed models or algorithms")
    list_subparsers = parser_list.add_subparsers(dest="list_type", help="Type of resource to list")

    # list models subcommand
    parser_list_models = list_subparsers.add_parser("models", help="List installed models")
    parser_list_models.add_argument("--global", dest="global_list", action="store_true",
                                    help="List models from ~/.fz/models/ (default: ./.fz/models/)")

    # list algorithms subcommand
    parser_list_algorithms = list_subparsers.add_parser("algorithms", help="List installed algorithms")
    parser_list_algorithms.add_argument("--global", dest="global_list", action="store_true",
                                        help="List algorithms from ~/.fz/algorithms/ (default: ./.fz/algorithms/)")

    # uninstall command (supports both models and algorithms)
    parser_uninstall = subparsers.add_parser("uninstall", help="Uninstall a model or algorithm")
    uninstall_subparsers = parser_uninstall.add_subparsers(dest="uninstall_type", help="Type of resource to uninstall")

    # uninstall model subcommand
    parser_uninstall_model = uninstall_subparsers.add_parser("model", help="Uninstall a model")
    parser_uninstall_model.add_argument("name", help="Model name to uninstall")
    parser_uninstall_model.add_argument("--global", dest="global_uninstall", action="store_true",
                                        help="Uninstall from ~/.fz/models/ (default: ./.fz/models/)")

    # uninstall algorithm subcommand
    parser_uninstall_algorithm = uninstall_subparsers.add_parser("algorithm", help="Uninstall an algorithm")
    parser_uninstall_algorithm.add_argument("name", help="Algorithm name to uninstall")
    parser_uninstall_algorithm.add_argument("--global", dest="global_uninstall", action="store_true",
                                            help="Uninstall from ~/.fz/algorithms/ (default: ./.fz/algorithms/)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == "input":
            model = parse_model(args.model)
            result = fzi_func(args.input_path, model)
            print(format_output(result, args.format))

        elif args.command == "compile":
            model = parse_model(args.model)
            variables = parse_variables(args.input_variables)
            fzc_func(args.input_path, variables, model, output_dir=args.output_dir)
            print(f"Compiled input saved to {args.output_dir}")

        elif args.command == "output":
            model = parse_model(args.model)
            result = fzo_func(args.output_path, model)
            print(format_output(result, args.format))

        elif args.command == "run":
            model = parse_model(args.model)
            variables = parse_variables(args.input_variables)
            calculators = parse_calculators(args.calculators) if args.calculators else None

            result = fzr_func(args.input_path, variables, model,
                        results_dir=args.results_dir,
                        calculators=calculators)
            print(format_output(result, args.format))

        elif args.command == "design":
            model = parse_model(args.model)
            variables = parse_variables(args.input_vars)

            calculators = None
            if args.calculators:
                if args.calculators.endswith('.json'):
                    with open(args.calculators) as f:
                        calculators = json.load(f)
                else:
                    calculators = json.loads(args.calculators)

            # Parse algorithm options
            algo_options = {}
            if args.options:
                if args.options.endswith('.json'):
                    with open(args.options) as f:
                        algo_options = json.load(f)
                else:
                    algo_options = json.loads(args.options)

            result = fzd_func(
                args.input_dir,
                variables,
                model,
                args.output_expression,
                args.algorithm,
                results_dir=args.results_dir,
                calculators=calculators,
                **algo_options
            )

            # Print summary
            print("\n" + "="*60)
            print(result['summary'])
            print("="*60)

            if 'analysis' in result and 'text' in result['analysis']:
                print(result['analysis']['text'])

        elif args.command == "install":
            if args.install_type == "model":
                from .installer import install_model
                result = install_model(args.source, global_install=args.global_install)
                print(f"Successfully installed model '{result['model_name']}'")
                if result.get('installed_files'):
                    print(f"  Installed {len(result['installed_files'])} additional files from .fz subdirectories")
            elif args.install_type == "algorithm":
                from .installer import install_algorithm
                result = install_algorithm(args.source, global_install=args.global_install)
                print(f"Successfully installed algorithm '{result['algorithm_name']}'")
                if len(result.get('all_files', [])) > 1:
                    print(f"  Installed {len(result['all_files'])} files")
            else:
                print("Error: Please specify 'model' or 'algorithm' to install")
                print("Usage: fz install model <source>")
                print("       fz install algorithm <source>")
                return 1

        elif args.command == "list":
            if args.list_type == "models":
                from .installer import list_installed_models
                models = list_installed_models(global_list=args.global_list)
                if not models:
                    location = "~/.fz/models/" if args.global_list else "./.fz/models/"
                    print(f"No models installed in {location}")
                else:
                    print(f"Installed models:")
                    for model_name, model_info in models.items():
                        model_id = model_info.get('id', 'N/A')
                        is_global = model_info.get('global', False)
                        location = "[global]" if is_global else "[local]"
                        print(f"  - {model_name} (id: {model_id}) {location}")
            elif args.list_type == "algorithms":
                from .installer import list_installed_algorithms
                algorithms = list_installed_algorithms(global_list=args.global_list)
                if not algorithms:
                    location = "~/.fz/algorithms/" if args.global_list else "./.fz/algorithms/"
                    print(f"No algorithms installed in {location}")
                else:
                    print(f"Installed algorithms:")
                    for algo_name, algo_info in algorithms.items():
                        algo_type = algo_info.get('type', 'N/A')
                        is_global = algo_info.get('global', False)
                        location = "[global]" if is_global else "[local]"
                        print(f"  - {algo_name} ({algo_type}) {location}")
            else:
                print("Error: Please specify 'models' or 'algorithms' to list")
                print("Usage: fz list models")
                print("       fz list algorithms")
                return 1

        elif args.command == "uninstall":
            if args.uninstall_type == "model":
                from .installer import uninstall_model
                success = uninstall_model(args.name, global_uninstall=args.global_uninstall)
                if success:
                    location = "~/.fz/models/" if args.global_uninstall else "./.fz/models/"
                    print(f"Successfully uninstalled model '{args.name}' from {location}")
                else:
                    location = "~/.fz/models/" if args.global_uninstall else "./.fz/models/"
                    print(f"Model '{args.name}' not found in {location}")
                    return 1
            elif args.uninstall_type == "algorithm":
                from .installer import uninstall_algorithm
                success = uninstall_algorithm(args.name, global_uninstall=args.global_uninstall)
                if success:
                    location = "~/.fz/algorithms/" if args.global_uninstall else "./.fz/algorithms/"
                    print(f"Successfully uninstalled algorithm '{args.name}' from {location}")
                else:
                    location = "~/.fz/algorithms/" if args.global_uninstall else "./.fz/algorithms/"
                    print(f"Algorithm '{args.name}' not found in {location}")
                    return 1
            else:
                print("Error: Please specify 'model' or 'algorithm' to uninstall")
                print("Usage: fz uninstall model <name>")
                print("       fz uninstall algorithm <name>")
                return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())