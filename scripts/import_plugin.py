#!/usr/bin/env python3
"""
Script to import a Funz plugin repository and create fz model aliases

Usage:
    python scripts/import_plugin.py <plugin-name>

Example:
    python scripts/import_plugin.py moret
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
import subprocess
import re


def parse_ioplugin(ioplugin_path):
    """Parse a Funz .ioplugin file and extract configuration"""
    config = {}

    with open(ioplugin_path, 'r') as f:
        content = f.read()

    # Parse basic configuration
    for line in content.split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()

            if key == 'variableStartSymbol':
                config['varprefix'] = value
            elif key == 'variableLimit':
                # Extract delimiters - the format is like (...)  or {...}
                # The actual delimiters are the outer brackets
                if value.startswith('(') and ')' in value:
                    config['delim'] = '()'
                elif value.startswith('[') and ']' in value:
                    config['delim'] = '[]'
                elif value.startswith('{') and '}' in value:
                    config['delim'] = '{}'
            elif key == 'formulaStartSymbol':
                config['formulaprefix'] = value
            elif key == 'formulaLimit':
                # Extract delimiters
                if value.startswith('{') and '}' in value:
                    config['formula_delim'] = '{}'
                elif value.startswith('(') and ')' in value:
                    config['formula_delim'] = '()'
                elif value.startswith('[') and ']' in value:
                    config['formula_delim'] = '[]'
            elif key == 'commentLineChar':
                config['commentline'] = value
            elif key == 'outputlist':
                config['output_keys'] = value.split()

    # Parse output extraction patterns
    config['outputs'] = {}
    for line in content.split('\n'):
        if line.strip().startswith('output.') and '.get=' in line:
            # Extract output name
            match = re.match(r'output\.(\w+)\.get=(.+)', line.strip())
            if match:
                output_name = match.group(1)
                pattern = match.group(2)
                config['outputs'][output_name] = pattern

    return config


def create_model_alias(plugin_name, config, samples_dir):
    """Create a model alias JSON file"""

    # Build output shell commands from the parsing patterns
    outputs = {}
    for key in config.get('output_keys', []):
        # Convert Funz pattern to shell command
        pattern = config['outputs'].get(key, '')

        # For MORET-specific patterns with FAIBLE/LOWEST SIGMA
        if 'FAIBLE' in pattern or 'LOWEST' in pattern:
            # Create grep command that searches for the pattern
            if 'mean_keff' in key or 'dkeff' in key:
                # Extract value before +/-
                outputs[key] = 'grep -E "(FAIBLE|LOWEST) SIGMA" *.listing | head -1 | sed -E "s/.*SIGMA[[:space:]]+([0-9.E+-]+)[[:space:]]+.*/\\1/"'
            elif 'sigma' in key:
                # Extract value after +/-
                outputs[key] = 'grep -E "(FAIBLE|LOWEST) SIGMA" *.listing | head -1 | sed -E "s/.*\\/\\-[[:space:]]+([0-9.E+-]+).*/\\1/"'
        # For MCNP-specific patterns with "final estimated combined"
        elif 'final estimated combined' in pattern:
            if 'mean_keff' in key:
                # Extract keff value after "keff = "
                outputs[key] = 'grep "final estimated combined" outp | sed -E "s/.*keff = ([0-9.E+-]+).*/\\1/"'
            elif 'sigma' in key:
                # Extract standard deviation value
                outputs[key] = 'grep "final estimated combined" outp | sed -E "s/.*standard deviation of ([0-9.E+-]+).*/\\1/"'
        else:
            # Default: create a TODO placeholder
            outputs[key] = f'echo "TODO: implement extraction for {key}"'

    model = {
        "id": plugin_name.lower(),
        "varprefix": config.get('varprefix', '$'),
        "delim": config.get('delim', '()'),
        "formulaprefix": config.get('formulaprefix', '@'),
        "commentline": config.get('commentline', '#'),
        "output": outputs
    }

    # Add formula_delim if present
    if 'formula_delim' in config:
        model['formula_delim'] = config['formula_delim']

    return model


def import_plugin(plugin_name):
    """Import a Funz plugin and create model alias"""

    print(f"Importing plugin: {plugin_name}")

    # Clone the plugin repository
    plugin_url = f"https://github.com/Funz/plugin-{plugin_name}.git"
    temp_dir = tempfile.mkdtemp()
    plugin_dir = Path(temp_dir) / f"plugin-{plugin_name}"

    print(f"Cloning {plugin_url}...")
    result = subprocess.run(['git', 'clone', plugin_url, str(plugin_dir)],
                          capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Error cloning repository: {result.stderr}")
        sys.exit(1)

    # Find the .ioplugin file
    ioplugin_files = list(plugin_dir.glob('src/main/io/*.ioplugin'))
    if not ioplugin_files:
        print("No .ioplugin file found!")
        sys.exit(1)

    ioplugin_path = ioplugin_files[0]
    print(f"Found ioplugin: {ioplugin_path}")

    # Parse the configuration
    config = parse_ioplugin(ioplugin_path)
    print(f"Configuration: {json.dumps(config, indent=2)}")

    # Find sample files
    samples_dir = plugin_dir / 'src' / 'main' / 'samples'
    sample_files = list(samples_dir.glob('*')) if samples_dir.exists() else []

    # Create model alias
    model = create_model_alias(plugin_name, config, samples_dir)

    # Save model alias
    fz_dir = Path.cwd()
    models_dir = fz_dir / '.fz' / 'models'
    models_dir.mkdir(parents=True, exist_ok=True)

    model_file = models_dir / f'{plugin_name.lower()}.json'
    with open(model_file, 'w') as f:
        json.dump(model, f, indent=2)

    print(f"Created model alias: {model_file}")

    # Copy sample files for testing
    if sample_files:
        examples_dir = fz_dir / 'examples' / plugin_name.lower()
        examples_dir.mkdir(parents=True, exist_ok=True)

        for sample in sample_files:
            if sample.is_file():
                shutil.copy(sample, examples_dir / sample.name)
                print(f"Copied sample: {sample.name}")

    # Cleanup
    shutil.rmtree(temp_dir)

    print(f"\nPlugin '{plugin_name}' imported successfully!")
    print(f"Model alias: {model_file}")
    print(f"Examples: {examples_dir if sample_files else 'None'}")

    return model


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_plugin.py <plugin-name>")
        print("Example: python scripts/import_plugin.py moret")
        sys.exit(1)

    plugin_name = sys.argv[1]
    import_plugin(plugin_name)
