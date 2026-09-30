# Calculator Types

## Local Shell Execution

Execute calculations locally:

```python
# Basic shell command
calculators = "sh://bash script.sh"

# With multiple arguments
calculators = "sh://python calculate.py --verbose"

# Multiple calculators (tries in order, parallel execution)
calculators = [
    "sh://bash method1.sh",
    "sh://bash method2.sh",
    "sh://python method3.py"
]
```

**How it works**:
1. Input files copied to temporary directory
2. Command executed in that directory with input files as arguments
3. Outputs parsed from result directory
4. Temporary files cleaned up (preserved in DEBUG mode)

## SSH Remote Execution

Execute calculations on remote servers:

```python
# SSH with password
calculators = "ssh://user:password@server.com:22/bash /absolutepath/to/calc.sh"

# SSH with key-based auth (recommended)
calculators = "ssh://user@server.com/bash /absolutepath/to/calc.sh"

# SSH with custom port
calculators = "ssh://user@server.com:2222/bash /absolutepath/to/calc.sh"
```

**Features**:
- Automatic file transfer (SFTP)
- Remote execution with timeout
- Result retrieval
- SSH key-based or password authentication
- Host key verification

**Security**:
- Interactive host key acceptance
- Warning for password-based auth
- Environment variable for auto-accepting host keys: `FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1`

## SLURM Workload Manager

Execute calculations on SLURM clusters (local or remote):

```python
# Local SLURM execution
calculators = "slurm://:compute/bash script.sh"

# Remote SLURM execution via SSH
calculators = "slurm://user@cluster.edu:gpu/bash script.sh"

# With custom SSH port
calculators = "slurm://user@cluster.edu:2222:gpu/bash script.sh"

# Multiple partitions for parallel execution
calculators = [
    "slurm://user@hpc.edu:compute/bash calc.sh",
    "slurm://user@hpc.edu:gpu/bash calc.sh"
]
```

**URI Format**: `slurm://[user@host[:port]]:partition/script`

Note: For local execution, the partition must be prefixed with a colon (`:partition`), e.g., `slurm://:compute/script.sh`

**How it works**:
1. Local execution: Uses `srun --partition=<partition> <script>` directly
2. Remote execution: Connects via SSH, transfers files, runs `srun` on remote cluster
3. Automatically handles SLURM partition scheduling
4. Supports interrupt handling (Ctrl+C terminates SLURM jobs)

**Features**:
- Local or remote SLURM execution
- Automatic file transfer for remote execution (via SFTP)
- SLURM partition specification
- Timeout and interrupt handling
- Compatible with all SLURM schedulers

**Requirements**:
- Local: SLURM installed (`srun` command available)
- Remote: SSH access to SLURM cluster + `paramiko` library

**Job arrays (`slurm-array://`, local SLURM)**: the asynchronous twin of `slurm://`.
Cases submitted within a short window are batched into **one** `sbatch --array` job (a
single calculator URI runs all N cases; it is not locked per case), and a single shared
monitor thread follows every task with one `sacct` call per poll (falling back to
`squeue` when accounting is disabled), instead of one blocking `srun` per case.

```python
calculators = "slurm-array://:compute/bash script.sh?cores=4&mem=8G&time=01:00:00&maxrunning=20"
```

Resources go in the URI query string, for both `slurm://` and `slurm-array://`.
Allowed keys: `cores` (`--cpus-per-task`), `mem`, `time`, `nodes`, `ntasks`, `gres`,
`account`, `qos`, plus `maxrunning` (array throttle, `--array=0-N%M`; `slurm-array://`
only). Env vars: `FZ_SLURM_POLL_INTERVAL` (seconds between polls, default 2) and
`FZ_SLURM_ARRAY_WINDOW` (seconds cases are gathered before submitting, default 1).
`slurm-array://` supports local SLURM only (remote SSH SLURM stays on `slurm://`).

## Funz Server Execution

Execute calculations using the Funz server protocol (compatible with legacy Java Funz servers):

```python
# Connect to local Funz server
calculators = "funz://:5555/R"

# Connect to remote Funz server
calculators = "funz://server.example.com:5555/Python"

# Multiple Funz servers for parallel execution
calculators = [
    "funz://:5555/R",
    "funz://:5556/R",
    "funz://:5557/R"
]
```

**Features**:
- Compatible with legacy Java Funz calculator servers
- Automatic file upload to server
- Remote execution with the Funz protocol
- Result download and extraction
- Support for interrupt handling
- UDP discovery for automatic server detection

**UDP Discovery**:

FZ supports automatic Funz server discovery via UDP broadcast:

```python
from fz import discover_funz_servers

# Listen on UDP port 19001 for 10s and collect every distinct calculator seen
servers = discover_funz_servers(udp_port=19001, listen_duration=10)

# Returns list of discovered servers:
# [
#   {'host': '192.168.1.100', 'tcp_port': 5555, 'name': 'calc1',
#    'os': 'Linux 6.1', 'activity': 'idle', 'idle': True, 'codes': ['R']},
#   {'host': '192.168.1.101', 'tcp_port': 5555, 'name': 'calc2',
#    'os': 'Linux 6.1', 'activity': 'idle', 'idle': True, 'codes': ['Python']},
#   ...
# ]

# Use idle servers offering "R"
calculators = [
    f"funz://{s['host']}:{s['tcp_port']}/R"
    for s in servers if s["idle"] and "R" in s["codes"]
]
results = fz.fzr("input.txt", input_variables, model, calculators=calculators)
```

**Discovery Protocol**:
- Broadcasts UDP message on port 19001
- Servers respond with their host, port, and supported codes
- Useful for dynamic calculator allocation in cluster environments
- See `doc/funz-protocol.md` for detailed protocol documentation

**Protocol**:
- Text-based TCP socket communication
- Calculator reservation with authentication
- Automatic cleanup and unreservation

**URI Format**: `funz://[host]:<port>/<code>`
- `host`: Server hostname (default: localhost)
- `port`: Server port (required)
- `code`: Calculator code/model name (e.g., "R", "Python", "Modelica")

**Example**:
```python
import fz

model = {
    "output": {
        "pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"
    }
}

results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300]},
    model,
    calculators="funz://:5555/R"
)
```

## Cache Calculator

Reuse previous calculation results:

```python
# Check single cache directory
calculators = "cache://previous_results"

# Check multiple cache locations
calculators = [
    "cache://run1",
    "cache://run2/results",
    "sh://bash calculate.sh"  # Fallback to actual calculation
]

# Use glob patterns
calculators = "cache://archive/*/results"
```

**Cache Matching**:
- Based on a SHA-256 hash of the compiled input files (`.fz_hash`, versioned "v2" format)
- Validates outputs are not None
- Falls through to next calculator on miss
- No recalculation if cache hit
- Checks the calculator's declared **code identity** (`code_id`, see Calculator
  Aliases below), not its command or host: two calculators with different
  commands but the same `code_id` share the cache; different `code_id` never
  matches, even with the same command. Without a `code_id` declared on either
  side, a match is still accepted (with a one-time warning) unless
  `FZ_CACHE_STRICT=1`. A pre-v2 cache directory (written by an older `fz`) is
  ignored unless `FZ_CACHE_ACCEPT_LEGACY=1`.

## Calculator Aliases

Store calculator configurations in `.fz/calculators/`:

**`.fz/calculators/cluster.json`**:
```json
{
    "uri": "ssh://user@cluster.university.edu",
    "models": {
        "perfectgas": "bash /home/user/codes/perfectgas/run.sh",
        "navier-stokes": "bash /home/user/codes/cfd/run.sh"
    }
}
```

Use by name:
```python
results = fz.fzr("input.txt", input_variables, "perfectgas", calculators="cluster")
```

**Code identity for `cache://`**: a calculator alias may declare an optional
`code_id` - the identity of its code installation, not its command or host
(e.g. two calculators can run the exact same code via a different command:
`bash run.sh` locally vs. `/opt/telemac/v8p5/run.sh` over SSH). Calculators
that declare the same `code_id` share `cache://` results with each other;
declaring a different one refuses the match even if the command is
identical. `version_cmd` resolves `code_id` by running a command on the
calculator instead of hardcoding it (once per calculator per session); if it
exits with a non-zero status, the calculator is treated as having no `code_id`:

```json
{
    "uri": "ssh://user@cluster.university.edu/bash /opt/telemac/v8p5/run.sh",
    "code_id": "telemac@v8p5"
}
```
```json
{
    "uri": "sh://bash ./run.sh",
    "version_cmd": "./run.sh --version"
}
```

## Calculator-Model Compatibility

FZ automatically validates that calculators support the specified model to prevent incompatible combinations:

```python
# .fz/calculators/cluster.json
{
    "uri": "ssh://user@cluster.edu",
    "models": {
        "perfectgas": "bash /path/to/perfectgas.sh",
        "cfd": "bash /path/to/cfd.sh"
    }
}
```

**Validation**:

```python
# This works - perfectgas is supported
results = fz.fzr("input.txt", input_variables, "perfectgas", calculators="cluster")

# This fails with clear error - unsupported_model not in calculator's models
results = fz.fzr("input.txt", input_variables, "unsupported_model", calculators="cluster")
# Error: Calculator 'cluster' does not support model 'unsupported_model'
#        Supported models: perfectgas, cfd
```

**Automatic Resolution**:
- Model and calculator aliases are resolved from `.fz/` directories
- Compatibility check happens before execution
- Clear error messages indicate which models are supported
- Prevents wasted computation on incompatible setups

**Direct URIs (No Validation)**:

When using direct calculator URIs (not aliases), no validation occurs:

```python
# No validation - you're responsible for compatibility
results = fz.fzr(
    "input.txt",
    input_variables,
    "anymodel",
    calculators="sh://bash any_script.sh"
)
```

**Best Practice**:
- Use calculator aliases for complex setups
- Document model compatibility in calculator JSON files
- Use `fzl --check` to validate configurations
