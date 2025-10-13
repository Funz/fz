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

from . import fzi as fzi_func, fzc as fzc_func, fzo as fzo_func, fzr as fzr_func


# Get package version
def get_version():
    """Get the package version"""
    try:
        return version("fz")
    except Exception:
        return "unknown"


# Helper functions used by all CLI commands
def parse_model(model_str):
    """Parse model from JSON file, inline JSON, or alias"""
    if model_str.endswith('.json'):
        with open(model_str) as f:
            return json.load(f)
    elif model_str.startswith('{'):
        return json.loads(model_str)
    else:
        # Assume it's a model alias
        return model_str


def parse_variables(var_str):
    """Parse variables from JSON file or inline JSON"""
    if var_str.endswith('.json'):
        with open(var_str) as f:
            return json.load(f)
    else:
        return json.loads(var_str)


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

        calculators = None
        if args.calculators:
            if args.calculators.endswith('.json'):
                with open(args.calculators) as f:
                    calculators = json.load(f)
            else:
                calculators = json.loads(args.calculators)

        result = fzr_func(args.input_path, variables, model,
                    results_dir=args.results_dir,
                    calculators=calculators)
        print(format_output(result, args.format))
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
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

            calculators = None
            if args.calculators:
                if args.calculators.endswith('.json'):
                    with open(args.calculators) as f:
                        calculators = json.load(f)
                else:
                    calculators = json.loads(args.calculators)

            result = fzr_func(args.input_path, variables, model,
                        results_dir=args.results_dir,
                        calculators=calculators)
            print(format_output(result, args.format))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())