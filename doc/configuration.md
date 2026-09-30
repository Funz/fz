# Configuration



## Environment Variables

```bash
# Logging level (DEBUG, INFO, WARNING, ERROR)
export FZ_LOG_LEVEL=INFO

# Maximum retry attempts per case
export FZ_MAX_RETRIES=5

# Thread pool size for parallel execution
export FZ_MAX_WORKERS=8

# SSH keepalive interval (seconds)
export FZ_SSH_KEEPALIVE=300

# Auto-accept SSH host keys (use with caution!)
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=0

# Default formula interpreter (python or R)
export FZ_INTERPRETER=python

# Custom shell binary search path (overrides system PATH)
# Windows example: SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\Program Files\Git\usr\bin
# Linux/macOS example: export FZ_SHELL_PATH=/opt/custom/bin:/usr/local/bin
export FZ_SHELL_PATH=/usr/local/bin:/usr/bin

# Run timeout in seconds (default: 3600 = 1 hour; unlimited for ssh:// and slurm:// when unset)
export FZ_RUN_TIMEOUT=1800

# Case directory naming scheme: "path" (var=val,... subdirs, default), "hash"
# (short content hash, avoids filesystem filename length limits with many
# variables), or "index" (case_<i>)
export FZ_CASE_NAMING=path

# Minimum size (bytes) for a variable-free input_path file to trigger a
# one-time warning suggesting input_static instead (default: 1048576 = 1 MiB;
# 0 disables the warning)
export FZ_STATIC_CANDIDATE_MIN_SIZE=1048576

# RO-Crate written next to each campaign's manifest.json (default: 1; 0 disables)
export FZ_RO_CRATE=0

# cache:// identity checks (default: 0 for both): refuse a cache match whose
# calculator code_id can't be verified on both sides, instead of a warning
export FZ_CACHE_STRICT=1
# Consider pre-v2 (MD5, no header, no code_id) cache directories at all;
# ignored by default
export FZ_CACHE_ACCEPT_LEGACY=1

# slurm-array:// (local SLURM job arrays): seconds between sacct/squeue polls (default 2)
# and seconds during which cases are gathered before one sbatch (default 1)
export FZ_SLURM_POLL_INTERVAL=2
export FZ_SLURM_ARRAY_WINDOW=1

# fz-mcp server (see mcp-server.md): workspace root, trusted mode, transport
#   FZ_MCP_ROOT, FZ_MCP_TRUSTED, FZ_MCP_TRANSPORT, FZ_MCP_ALLOW_NETWORK_TRANSPORT
```

## Shell Path Configuration (FZ_SHELL_PATH)

`FZ_SHELL_PATH` lists directories (separated by `;` on Windows, `:` elsewhere) searched **before**
the system `PATH` for the shell tools (grep, awk, sed, ...) used by model `output` commands
and `sh://` calculators. It matters mainly on Windows, where the Unix tools live in MSYS2, Git
Bash, Cygwin or WSL directories (for example `SET FZ_SHELL_PATH=C:\msys64\usr\bin;C:\msys64\mingw64\bin`).
Binary names are resolved to absolute paths (also trying `command.exe` on Windows) and the
results are cached. fz needs `bash` everywhere. Full description, resolution rules and
troubleshooting: [Shell path](shell-path.md) and `examples/shell_path_example.md`.

## Campaign manifest and RO-Crate (traceability)

Each `fzr()` run writes `<results_dir>/manifest.json` (schema `fz-manifest/1`):
fz/Python/platform versions, start/end times (UTC), the model and its SHA-256, the
calculators (credentials in URIs are masked as `user:***@host`), remote hosts, and
per case: path, status, calculator, input values and the SHA-256 of its `.fz_hash`.
`fzd()` writes a campaign-level `<analysis_dir>/manifest.json` (schema
`fz-manifest-fzd/1`: algorithm and options, input variables, output expression,
number of iterations, links to the per-iteration manifests). An RO-Crate 1.1
(`ro-crate-metadata.json`) referencing the manifest is written next to each manifest;
set `FZ_RO_CRATE=0` to disable it. A failure to write either file only logs a warning.

## Timeout Configuration

FZ provides flexible timeout settings for controlling calculation execution time:

### 1. Environment Variable (Global Default)

```bash
# Set default timeout for all calculations (in seconds)
export FZ_RUN_TIMEOUT=1800  # 30 minutes (default: 3600 seconds = 1 hour for sh:// and funz://,
                            # unlimited for ssh:// and slurm://)
```

When `FZ_RUN_TIMEOUT` is not set, `ssh://` and `slurm://` calculations have **no timeout**
(queue waits are unbounded); a warning is logged at launch. Set `FZ_RUN_TIMEOUT`, the
model `timeout` or the `timeout=` argument to bound them. When set explicitly,
`FZ_RUN_TIMEOUT` applies to every calculator type.

### 2. Model Configuration (Per-Model)

```python
model = {
    "varprefix": "$",
    "output": {"result": "cat output.txt"},
    "timeout": 1800  # 30 minutes for this model, regardless of FZ_RUN_TIMEOUT
}

results = fz.fzr("input.txt", input_variables, model, calculators="sh://calc.sh")
```

A model `timeout` of `None`/`null` or `0` disables the timeout entirely for that
model (the calculation may run indefinitely):

```python
model = {"timeout": None, "output": {"result": "cat output.txt"}}
```

`FZ_RUN_TIMEOUT=0` and `timeout=0` do **not** disable the timeout: every case then times
out immediately. Only the model entry disables it.

### 3. `fzr()`/`fzc()` `timeout=` Argument (Per-Call)

```python
# Overrides both the model's timeout and FZ_RUN_TIMEOUT for this call only
results = fz.fzr("input.txt", input_variables, model, calculators="sh://calc.sh", timeout=7200)
```

### Priority Order (highest to lowest)

1. **`timeout=` argument** passed to `fzr()`/`fzc()`
2. **Model configuration** (`model["timeout"]`)
3. **Environment variable** (`FZ_RUN_TIMEOUT`; if unset: 3600 seconds for `sh://`/`funz://`, unlimited for `ssh://`/`slurm://`)

**Timeout Behavior**:
- Calculation terminates after timeout expires
- Marked as "failed" with timeout error
- Retry mechanism may attempt with next calculator
- Partial results preserved for debugging

## Python Configuration

```python
from fz import get_config

# Get current config
config = get_config()
print(f"Max retries: {config.max_retries}")
print(f"Max workers: {config.max_workers}")

# Modify configuration
config.max_retries = 10
config.max_workers = 4
```

## Directory Structure

FZ uses the following directory structure:

```
your_project/
├── input.txt                 # Your input template
├── calculate.sh              # Your calculation script
├── run_study.py             # Your Python script
├── .fz/                     # FZ configuration (optional)
│   ├── models/              # Model aliases
│   │   └── mymodel.json
│   ├── calculators/         # Calculator aliases
│   │   └── mycluster.json
│   ├── algorithms/          # Algorithm plugins
│   │   ├── myalgo.py
│   │   └── myalgo.R
│   └── tmp/                 # Temporary files (auto-created)
│       └── fz_temp_*/       # Per-run temp directories
└── results/                 # Results directory
    ├── case1/               # One directory per case
    │   ├── input.txt        # Compiled input
    │   ├── output.txt       # Calculation output
    │   ├── log.txt          # Execution metadata
    │   ├── out.txt          # Standard output
    │   ├── err.txt          # Standard error
    │   └── .fz_hash         # File checksums (for caching)
    └── case2/
        └── ...
```
