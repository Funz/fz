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

    # Create execution script and calculator alias
    scripts_dir = plugin_dir / 'src' / 'main' / 'scripts'
    if scripts_dir.exists():
        # Try both lowercase and capitalized plugin name
        script_files = list(scripts_dir.glob(f'{plugin_name}.*'))
        if not script_files:
            script_files = list(scripts_dir.glob(f'{plugin_name.capitalize()}.*'))
        if not script_files:
            script_files = list(scripts_dir.glob(f'{plugin_name.upper()}.*'))

        if script_files:
            # Create calculators directory
            calc_dir = fz_dir / '.fz' / 'calculators'
            calc_dir.mkdir(parents=True, exist_ok=True)

            # Read the original script to understand the structure
            original_script = None
            for script_file in script_files:
                if script_file.suffix == '.sh':
                    with open(script_file, 'r') as f:
                        original_script = f.read()
                    break

            # Create simplified wrapper script
            script_name = f'{plugin_name.lower()}.sh'
            wrapper_script = fz_dir / 'scripts' / script_name

            if plugin_name.lower() == 'moret':
                script_content = """#!/bin/bash
# MORET calculator wrapper
# Assumes MORET is installed at /opt/MORET or in PATH

if [ -f "/opt/MORET/scripts/moret.py" ]; then
    /opt/MORET/scripts/moret.py "$@"
elif command -v moret &> /dev/null; then
    moret "$@"
else
    echo "ERROR: MORET not found. Please install MORET or set the path in this script."
    exit 1
fi
"""
            elif plugin_name.lower() == 'mcnp':
                script_content = """#!/bin/bash
# MCNP calculator wrapper
# Assumes MCNP6 is installed at /Applications/MCNP6 or in PATH

# Default installation path (adjust as needed)
MCNP_PATH="${MCNP_PATH:-/Applications/MCNP6}"
export DATAPATH="$MCNP_PATH/MCNP_DATA"

ulimit -s unlimited 2>/dev/null

# Track process IDs for cleanup
echo $$ >> PID

if [ -f "$MCNP_PATH/MCNP_CODE/bin/mcnp6" ]; then
    $MCNP_PATH/MCNP_CODE/bin/mcnp6 inp="$@" &
    PID_MCNP=$!
    echo $PID_MCNP >> PID
    wait $PID_MCNP
elif command -v mcnp6 &> /dev/null; then
    mcnp6 inp="$@" &
    PID_MCNP=$!
    echo $PID_MCNP >> PID
    wait $PID_MCNP
else
    echo "ERROR: MCNP6 not found. Please install MCNP6 or set MCNP_PATH environment variable."
    rm -f PID
    exit 1
fi

# Cleanup
if [ -f "PID" ]; then
    rm -f "PID"
fi
"""
            else:
                # Generic wrapper for other plugins
                script_content = f"""#!/bin/bash
# {plugin_name.upper()} calculator wrapper
# TODO: Configure the path to {plugin_name.upper()} executable

echo "ERROR: {plugin_name.upper()} calculator not configured yet."
echo "Please edit this script to set the correct path to {plugin_name.upper()}."
exit 1
"""

            with open(wrapper_script, 'w') as f:
                f.write(script_content)
            wrapper_script.chmod(0o755)
            print(f"Created wrapper script: {script_name}")

            # Create calculator alias
            calculator_alias = {
                "id": plugin_name.lower(),
                "command": f"sh://bash {script_name}",
                "description": f"{plugin_name.upper()} calculator (assumes local installation)"
            }

            calc_file = calc_dir / f'{plugin_name.lower()}.json'
            with open(calc_file, 'w') as f:
                json.dump(calculator_alias, f, indent=2)

            print(f"Created calculator alias: {calc_file}")

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
