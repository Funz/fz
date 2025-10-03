#!/usr/bin/env python3
"""
Command line interface for fz package
"""
import argparse
import json
import sys
from pathlib import Path

from . import fzi, fzc, fzo, fzr


def main():
    parser = argparse.ArgumentParser(description="fz - Parametric scientific computing")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fzi command
    parser_fzi = subparsers.add_parser("fzi", help="Parse input to find variables")
    parser_fzi.add_argument("input", help="Input file or directory")
    parser_fzi.add_argument("model", help="Model definition (JSON file or inline JSON)")

    # fzc command
    parser_fzc = subparsers.add_parser("fzc", help="Compile input with variable values")
    parser_fzc.add_argument("input", help="Input file or directory")
    parser_fzc.add_argument("model", help="Model definition (JSON file or inline JSON)")
    parser_fzc.add_argument("variables", help="Variable values (JSON)")
    parser_fzc.add_argument("--engine", default="python", help="Formula evaluation engine")
    parser_fzc.add_argument("--output", default="output", help="Output directory")

    # fzo command
    parser_fzo = subparsers.add_parser("fzo", help="Parse output files")
    parser_fzo.add_argument("output", help="Output file or directory")
    parser_fzo.add_argument("model", help="Model definition (JSON file or inline JSON)")

    # fzr command
    parser_fzr = subparsers.add_parser("fzr", help="Run full parametric calculations")
    parser_fzr.add_argument("input", help="Input file or directory")
    parser_fzr.add_argument("model", help="Model definition (JSON file or inline JSON)")
    parser_fzr.add_argument("variables", help="Variable values (JSON)")
    parser_fzr.add_argument("--engine", default="python", help="Formula evaluation engine")
    parser_fzr.add_argument("--results", default="results", help="Results directory")
    parser_fzr.add_argument("--calculators", help="Calculator specifications (JSON)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Helper function to parse model
    def parse_model(model_str):
        if model_str.endswith('.json'):
            with open(model_str) as f:
                return json.load(f)
        elif model_str.startswith('{'):
            return json.loads(model_str)
        else:
            # Assume it's a model alias
            return model_str

    # Helper function to parse variables
    def parse_variables(var_str):
        if var_str.endswith('.json'):
            with open(var_str) as f:
                return json.load(f)
        else:
            return json.loads(var_str)

    try:
        if args.command == "fzi":
            model = parse_model(args.model)
            result = fzi(args.input, model)
            print(json.dumps(result, indent=2))

        elif args.command == "fzc":
            model = parse_model(args.model)
            variables = parse_variables(args.variables)
            fzc(args.input, model, variables, engine=args.engine, output_dir=args.output)
            print(f"Compiled input saved to {args.output}")

        elif args.command == "fzo":
            model = parse_model(args.model)
            result = fzo(args.output, model)
            print(json.dumps(result, indent=2))

        elif args.command == "fzr":
            model = parse_model(args.model)
            variables = parse_variables(args.variables)

            calculators = None
            if args.calculators:
                if args.calculators.endswith('.json'):
                    with open(args.calculators) as f:
                        calculators = json.load(f)
                else:
                    calculators = json.loads(args.calculators)

            result = fzr(args.input, model, variables,
                        engine=args.engine, results_dir=args.results,
                        calculators=calculators)
            print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())