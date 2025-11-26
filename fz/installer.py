"""
Model installation functionality for fz package

Supports installation from:
- GitHub model names (e.g., "moret" → "https://github.com/Funz/fz-moret")
- Full GitHub URLs (e.g., "https://github.com/Funz/fz-moret")
- Local zip files (e.g., "fz-moret.zip")
"""

import os
import shutil
import tempfile
import zipfile
import json
from pathlib import Path
from typing import Optional, Dict
from urllib.request import urlretrieve
from urllib.parse import urlparse

from .logging import log_info, log_error, log_warning, log_debug


def normalize_github_url(source: str) -> Optional[str]:
    """
    Normalize a model source to a GitHub archive URL

    Args:
        source: Model source (GitHub name, full URL, or local file)

    Returns:
        GitHub archive URL or None if it's a local file
    """
    # Check if it's a local file path
    if os.path.exists(source) or source.endswith('.zip'):
        return None

    # If it's already a full GitHub URL
    if source.startswith('http://') or source.startswith('https://'):
        parsed = urlparse(source)
        if 'github.com' in parsed.netloc:
            # Convert to archive URL if it's not already
            # e.g., https://github.com/Funz/fz-moret → https://github.com/Funz/fz-moret/archive/refs/heads/main.zip
            path = parsed.path.rstrip('/')
            if not path.endswith('.zip'):
                return f"https://github.com{path}/archive/refs/heads/main.zip"
            return source
        return source

    # Assume it's a short GitHub model name like "moret"
    # Convention: fz-{model} under Funz organization
    model_name = source
    if not model_name.startswith('fz-'):
        model_name = f'fz-{model_name}'

    return f"https://github.com/Funz/{model_name}/archive/refs/heads/main.zip"


def download_model(source: str, dest_dir: Path) -> Path:
    """
    Download model from URL or use local file

    Args:
        source: Model source (URL or local file path)
        dest_dir: Destination directory for the downloaded file

    Returns:
        Path to the downloaded/local zip file

    Raises:
        Exception: If download fails
    """
    # If it's a local file, just return its path
    if os.path.exists(source):
        local_path = Path(source).resolve()
        log_info(f"Using local file: {local_path}")
        return local_path

    # Download from URL
    url = normalize_github_url(source)
    if url is None:
        raise ValueError(f"Invalid source: {source}")

    log_info(f"Downloading from: {url}")

    # Generate a temporary filename
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path) or 'model.zip'
    dest_file = dest_dir / filename

    try:
        urlretrieve(url, dest_file)
        log_info(f"Downloaded to: {dest_file}")
        return dest_file
    except Exception as e:
        raise Exception(f"Failed to download from {url}: {e}")


def extract_model_files(zip_path: Path, extract_dir: Path) -> Dict[str, Path]:
    """
    Extract model files from a zip archive

    The expected structure of a model zip is:
    - fz-model-name-main/
      - model.json (model definition)
      - README.md (optional)
      - examples/ (optional)

    Args:
        zip_path: Path to the zip file
        extract_dir: Directory to extract to

    Returns:
        Dict with 'model_json' key pointing to the model definition file,
        and 'model_name' key with the model name

    Raises:
        Exception: If extraction fails or model.json not found
    """
    log_info(f"Extracting: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            log_debug(f"Extracted files: {zip_ref.namelist()[:10]}")  # Show first 10 files
    except Exception as e:
        raise Exception(f"Failed to extract {zip_path}: {e}")

    # Find the model definition file
    # Look in two places:
    # 1. model.json in the root (simple case)
    # 2. .fz/models/*.json (fz repository structure)

    log_debug(f"Searching for model definition in: {extract_dir}")

    # First try: look for model.json in root
    model_json_paths = list(extract_dir.rglob('model.json'))

    # Second try: look for .fz/models/*.json
    if not model_json_paths:
        model_json_paths = list(extract_dir.glob('*/.fz/models/*.json'))
        log_debug(f"Looking in .fz/models/: found {len(model_json_paths)} files")

    log_debug(f"Found {len(model_json_paths)} model definition files")

    if not model_json_paths:
        # List what we did find to help debugging
        all_files = list(extract_dir.rglob('*'))
        log_debug(f"Files found in extraction: {[str(f.relative_to(extract_dir)) for f in all_files[:20]]}")
        raise Exception(f"No model definition found in extracted archive. Extracted to: {extract_dir}")

    # Use the first model definition found
    model_json = model_json_paths[0]
    log_info(f"Found model definition: {model_json}")

    # Extract model name from the JSON file
    try:
        with open(model_json, 'r') as f:
            model_def = json.load(f)
            model_name = model_def.get('id')
            if not model_name:
                raise ValueError("Model definition must have an 'id' field")
    except Exception as e:
        raise Exception(f"Failed to read model definition: {e}")

    # Find the .fz directory that contains the model
    # The model_json is at: extracted/fz-model-main/.fz/models/Model.json
    # So the .fz directory is at: extracted/fz-model-main/.fz/
    fz_dir = model_json.parent.parent

    if not fz_dir.name == '.fz':
        # Try alternative location: look for .fz in the root extract directory
        root_extract_dir = list(extract_dir.glob('*'))[0] if list(extract_dir.glob('*')) else extract_dir
        fz_dir = root_extract_dir / '.fz'

    log_debug(f"Looking for .fz directory at: {fz_dir}")

    return {
        'model_json': model_json,
        'model_name': model_name,
        'extract_dir': model_json.parent,
        'fz_dir': fz_dir if fz_dir.exists() else None
    }


def install_model(source: str, global_install: bool = False) -> Dict[str, str]:
    """
    Install a model from a source (GitHub name, URL, or local zip file)

    Args:
        source: Model source to install from
        global_install: If True, install to ~/.fz/models/, else to ./.fz/models/

    Returns:
        Dict with 'model_name' and 'install_path' keys

    Raises:
        Exception: If installation fails
    """
    # Determine installation directory
    if global_install:
        install_base = Path.home() / '.fz' / 'models'
    else:
        install_base = Path.cwd() / '.fz' / 'models'

    install_base.mkdir(parents=True, exist_ok=True)

    # Create a temporary directory for download and extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Download the model
            zip_path = download_model(source, temp_path)

            # Extract the model files
            extract_path = temp_path / 'extract'
            extract_path.mkdir(exist_ok=True)
            model_info = extract_model_files(zip_path, extract_path)

            model_name = model_info['model_name']
            model_json = model_info['model_json']
            fz_dir = model_info.get('fz_dir')

            # Install the model definition
            dest_json = install_base / f"{model_name}.json"
            shutil.copy2(model_json, dest_json)
            log_info(f"Installed model '{model_name}' to: {dest_json}")

            # Install all other .fz subdirectories (calculators, algorithms, etc.)
            installed_files = []
            if fz_dir and fz_dir.exists():
                # Determine base installation directory
                if global_install:
                    install_root = Path.home() / '.fz'
                else:
                    install_root = Path.cwd() / '.fz'

                # Copy all subdirectories except 'models' (already handled)
                for subdir in fz_dir.iterdir():
                    if subdir.is_dir() and subdir.name != 'models':
                        dest_subdir = install_root / subdir.name

                        # Use copytree to recursively copy the entire directory structure
                        # dirs_exist_ok=True allows merging with existing directories
                        log_info(f"Installing {subdir.name}/ directory...")
                        shutil.copytree(subdir, dest_subdir, dirs_exist_ok=True)

                        # Make all shell scripts executable
                        for script_file in dest_subdir.rglob('*'):
                            if script_file.is_file():
                                installed_files.append(str(script_file.relative_to(install_root)))
                                if script_file.suffix in ['.sh', '.bash', '.zsh']:
                                    script_file.chmod(0o755)
                                    log_debug(f"Made executable: {script_file.name}")

                        log_info(f"Installed {subdir.name}/ to: {dest_subdir}")

                if installed_files:
                    log_info(f"Installed {len(installed_files)} total files from .fz subdirectories")
                else:
                    log_debug(f"No additional .fz subdirectories found for model '{model_name}'")
            else:
                log_debug(f"No .fz directory found for model '{model_name}'")

            return {
                'model_name': model_name,
                'install_path': str(dest_json),
                'installed_files': installed_files
            }

        except Exception as e:
            log_error(f"Installation failed: {e}")
            raise


def uninstall_model(model_name: str, global_uninstall: bool = False) -> bool:
    """
    Uninstall a model

    Args:
        model_name: Name of the model to uninstall
        global_uninstall: If True, uninstall from ~/.fz/models/, else from ./.fz/models/

    Returns:
        True if successful, False otherwise
    """
    if global_uninstall:
        install_base = Path.home() / '.fz' / 'models'
    else:
        install_base = Path.cwd() / '.fz' / 'models'

    model_path = install_base / f"{model_name}.json"

    if not model_path.exists():
        log_warning(f"Model '{model_name}' not found at: {model_path}")
        return False

    try:
        model_path.unlink()
        log_info(f"Uninstalled model '{model_name}'")
        return True
    except Exception as e:
        log_error(f"Failed to uninstall model '{model_name}': {e}")
        return False


def list_installed_models(global_list: bool = False) -> Dict[str, Dict]:
    """
    List installed models

    Args:
        global_list: If True, list from ~/.fz/models/, else from ./.fz/models/
                     If False, lists from both locations and marks each with 'global' property

    Returns:
        Dict mapping model names to their definitions (with 'global' property added)
    """
    models = {}

    if global_list:
        # Only list global models
        install_base = Path.home() / '.fz' / 'models'
        if install_base.exists():
            for model_file in install_base.glob('*.json'):
                try:
                    with open(model_file, 'r') as f:
                        model_def = json.load(f)
                        model_name = model_file.stem
                        model_def['global'] = True
                        models[model_name] = model_def
                except Exception as e:
                    log_warning(f"Failed to load model {model_file}: {e}")
    else:
        # List from both local and global, marking each
        # First, check local models
        local_base = Path.cwd() / '.fz' / 'models'
        if local_base.exists():
            for model_file in local_base.glob('*.json'):
                try:
                    with open(model_file, 'r') as f:
                        model_def = json.load(f)
                        model_name = model_file.stem
                        model_def['global'] = False
                        models[model_name] = model_def
                except Exception as e:
                    log_warning(f"Failed to load model {model_file}: {e}")

        # Then check global models (but don't override local ones)
        global_base = Path.home() / '.fz' / 'models'
        if global_base.exists():
            for model_file in global_base.glob('*.json'):
                try:
                    model_name = model_file.stem
                    # Only add if not already present (local takes precedence)
                    if model_name not in models:
                        with open(model_file, 'r') as f:
                            model_def = json.load(f)
                            model_def['global'] = True
                            models[model_name] = model_def
                except Exception as e:
                    log_warning(f"Failed to load model {model_file}: {e}")

    return models


# ============================================================================
# Algorithm Installation Functions
# ============================================================================


def extract_algorithm_files(zip_path: Path, extract_dir: Path) -> Dict[str, Path]:
    """
    Extract algorithm files from a zip archive

    The expected structure of an algorithm zip is:
    - fz-algorithm-name-main/
      - algorithm.py or algorithm.R (algorithm implementation)
      - README.md (optional)
      - examples/ (optional)

    Args:
        zip_path: Path to the zip file
        extract_dir: Directory to extract to

    Returns:
        Dict with 'algorithm_files' key pointing to list of algorithm files (.py or .R),
        and 'algorithm_name' key with the algorithm name

    Raises:
        Exception: If extraction fails or no algorithm files found
    """
    log_info(f"Extracting: {zip_path}")

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            log_debug(f"Extracted files: {zip_ref.namelist()[:10]}")  # Show first 10 files
    except Exception as e:
        raise Exception(f"Failed to extract {zip_path}: {e}")

    # Find algorithm files (.py or .R)
    # Look in two places:
    # 1. Algorithm files in the root (simple case)
    # 2. .fz/algorithms/*.py or *.R (fz repository structure)

    log_debug(f"Searching for algorithm files in: {extract_dir}")

    # First try: look for .py/.R files in root
    py_files = list(extract_dir.rglob('*.py'))
    r_files = list(extract_dir.rglob('*.R'))

    # Filter out test files, setup files, etc.
    def is_algorithm_file(path: Path) -> bool:
        """Check if file is likely an algorithm implementation"""
        name_lower = path.name.lower()
        # Exclude common non-algorithm files
        exclude_patterns = ['setup.py', 'test_', '_test.', 'conftest.py', '__init__.py']
        return not any(pattern in name_lower for pattern in exclude_patterns)

    py_files = [f for f in py_files if is_algorithm_file(f)]
    r_files = [f for f in r_files if is_algorithm_file(f)]

    # Second try: specifically look for .fz/algorithms/*.py or *.R
    fz_algo_py = list(extract_dir.glob('*/.fz/algorithms/*.py'))
    fz_algo_r = list(extract_dir.glob('*/.fz/algorithms/*.R'))

    # Combine and prioritize .fz/algorithms/ files if they exist
    if fz_algo_py or fz_algo_r:
        algorithm_files = fz_algo_py + fz_algo_r
        log_debug(f"Found {len(algorithm_files)} algorithm files in .fz/algorithms/")
    else:
        algorithm_files = py_files + r_files
        log_debug(f"Found {len(algorithm_files)} algorithm files in root")

    if not algorithm_files:
        # List what we did find to help debugging
        all_files = list(extract_dir.rglob('*'))
        log_debug(f"Files found in extraction: {[str(f.relative_to(extract_dir)) for f in all_files[:20]]}")
        raise Exception(f"No algorithm files (.py or .R) found in extracted archive. Extracted to: {extract_dir}")

    # Extract algorithm name from first file
    # For fz-algorithm repositories, the file is typically named after the algorithm
    algorithm_file = algorithm_files[0]
    algorithm_name = algorithm_file.stem
    log_info(f"Found algorithm file: {algorithm_file}")

    return {
        'algorithm_files': algorithm_files,
        'algorithm_name': algorithm_name,
        'extract_dir': algorithm_file.parent
    }


def install_algorithm(source: str, global_install: bool = False) -> Dict[str, str]:
    """
    Install an algorithm from a source (GitHub name, URL, or local zip file)

    Args:
        source: Algorithm source to install from
                - GitHub name: "montecarlo" → "https://github.com/Funz/fz-montecarlo"
                - Full URL: "https://github.com/user/fz-myalgo"
                - Local zip: "fz-myalgo.zip"
        global_install: If True, install to ~/.fz/algorithms/, else to ./.fz/algorithms/

    Returns:
        Dict with 'algorithm_name' and 'install_path' keys

    Raises:
        Exception: If installation fails
    """
    # Determine installation directory
    if global_install:
        install_base = Path.home() / '.fz' / 'algorithms'
    else:
        install_base = Path.cwd() / '.fz' / 'algorithms'

    install_base.mkdir(parents=True, exist_ok=True)

    # Create a temporary directory for download and extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # Download the algorithm (reuse download_model function)
            zip_path = download_model(source, temp_path)

            # Extract the algorithm files
            extract_path = temp_path / 'extract'
            extract_path.mkdir(exist_ok=True)
            algo_info = extract_algorithm_files(zip_path, extract_path)

            algorithm_name = algo_info['algorithm_name']
            algorithm_files = algo_info['algorithm_files']

            # Install the algorithm file(s)
            installed_files = []
            for algo_file in algorithm_files:
                # Use the original filename for installation
                dest_file = install_base / algo_file.name
                shutil.copy2(algo_file, dest_file)
                installed_files.append(str(dest_file))
                log_info(f"Installed algorithm '{algo_file.name}' to: {dest_file}")

            return {
                'algorithm_name': algorithm_name,
                'install_path': str(installed_files[0]),
                'all_files': installed_files
            }

        except Exception as e:
            log_error(f"Algorithm installation failed: {e}")
            raise


def uninstall_algorithm(algorithm_name: str, global_uninstall: bool = False) -> bool:
    """
    Uninstall an algorithm

    Args:
        algorithm_name: Name of the algorithm to uninstall (without extension)
        global_uninstall: If True, uninstall from ~/.fz/algorithms/, else from ./.fz/algorithms/

    Returns:
        True if successful, False otherwise
    """
    if global_uninstall:
        install_base = Path.home() / '.fz' / 'algorithms'
    else:
        install_base = Path.cwd() / '.fz' / 'algorithms'

    # Try both .py and .R extensions
    removed_any = False
    for ext in ['.py', '.R']:
        algo_path = install_base / f"{algorithm_name}{ext}"
        if algo_path.exists():
            try:
                algo_path.unlink()
                log_info(f"Uninstalled algorithm '{algorithm_name}{ext}'")
                removed_any = True
            except Exception as e:
                log_error(f"Failed to uninstall algorithm '{algorithm_name}{ext}': {e}")
                return False

    if not removed_any:
        log_warning(f"Algorithm '{algorithm_name}' not found at: {install_base}")
        return False

    return True


def list_installed_algorithms(global_list: bool = False) -> Dict[str, Dict]:
    """
    List installed algorithms

    Args:
        global_list: If True, list from ~/.fz/algorithms/, else from ./.fz/algorithms/
                     If False, lists from both locations and marks each with 'global' property

    Returns:
        Dict mapping algorithm names to their info (with 'global' property added)
    """
    algorithms = {}

    if global_list:
        # Only list global algorithms
        install_base = Path.home() / '.fz' / 'algorithms'
        if install_base.exists():
            for algo_file in install_base.glob('*'):
                if algo_file.suffix in ['.py', '.R'] and algo_file.is_file():
                    algo_name = algo_file.stem
                    algorithms[algo_name] = {
                        'name': algo_name,
                        'file': str(algo_file),
                        'type': 'Python' if algo_file.suffix == '.py' else 'R',
                        'global': True
                    }
    else:
        # List from both local and global, marking each
        # First, check local algorithms
        local_base = Path.cwd() / '.fz' / 'algorithms'
        if local_base.exists():
            for algo_file in local_base.glob('*'):
                if algo_file.suffix in ['.py', '.R'] and algo_file.is_file():
                    algo_name = algo_file.stem
                    algorithms[algo_name] = {
                        'name': algo_name,
                        'file': str(algo_file),
                        'type': 'Python' if algo_file.suffix == '.py' else 'R',
                        'global': False
                    }

        # Then check global algorithms (but don't override local ones)
        global_base = Path.home() / '.fz' / 'algorithms'
        if global_base.exists():
            for algo_file in global_base.glob('*'):
                if algo_file.suffix in ['.py', '.R'] and algo_file.is_file():
                    algo_name = algo_file.stem
                    # Only add if not already present (local takes precedence)
                    if algo_name not in algorithms:
                        algorithms[algo_name] = {
                            'name': algo_name,
                            'file': str(algo_file),
                            'type': 'Python' if algo_file.suffix == '.py' else 'R',
                            'global': True
                        }

    return algorithms
