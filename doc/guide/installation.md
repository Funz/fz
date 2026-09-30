# Installation

## Using pip

```bash
pip install funz-fz
```

## Using pipx (recommended for CLI tools)

```bash
pipx install funz-fz
```

[pipx](https://pypa.github.io/pipx/) installs the package in an isolated environment while making the CLI commands (`fz`, `fzi`, `fzc`, `fzo`, `fzr`, `fzl`, `fzd`) available globally.

## From Source

```bash
git clone https://github.com/Funz/fz.git
cd fz
pip install -e .
```

Or straight from GitHub via pip:

```bash
pip install --break-system-packages --upgrade --force-reinstall "git+https://github.com/Funz/fz.git"
```

* '--upgrade --force-reinstall' option to force update of possible previous installation
* '--break-system-packages' option to enable user-wide installation (ie. not in dedicated venv)

## Dependencies

```bash
# Installed automatically with fz (required dependencies):
#   paramiko (SSH support), pandas (DataFrame I/O, fzd), charset-normalizer

# Optional dependencies:

# for R interpreter support
pip install funz-fz[r]
# OR
pip install rpy2
# Note: Requires R installed with system libraries - see examples/r_interpreter_example.md

# for optimization algorithms (scipy-based algorithms in examples/)
pip install scipy numpy
```
