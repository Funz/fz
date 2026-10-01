# FZ Calculators

## What is a Calculator?

A calculator is an execution backend that runs your computational code. FZ supports six types:

1. **`sh://`** - Local shell execution
2. **`ssh://`** - Remote SSH execution (files transferred by SFTP)
3. **`slurm://`** - SLURM via `srun` (local, or remote through SSH)
4. **`slurm-array://`** - Local SLURM, all cases batched into one `sbatch --array` job
5. **`funz://`** - Legacy Java Funz calculator server (TCP)
6. **`cache://`** - Reuse results of previous runs (no computation)

Each non-cache calculator entry runs **one case at a time**: the number of parallel cases
equals the number of calculator entries (see [Multiple Calculators](#multiple-calculators)).
See [limitations.md](limitations.md) for the constraints that apply to all calculators.

## Calculator URI Format

Calculators are specified as URI strings:

```
protocol://[auth@]host[:port]/command [args]
```

**Examples**:
```
sh://bash script.sh
ssh://user@server.com/bash /path/to/script.sh
cache://previous_results/
```

## Local Shell Calculator (`sh://`)

Execute calculations locally using shell commands.

### Basic Syntax

```python
calculators = "sh://command [arguments]"
```

### Examples

**Example 1: Bash script**

```python
calculators = "sh://bash calculate.sh"
```

**Example 2: Python script**

```python
calculators = "sh://python3 simulate.py --verbose"
```

**Example 3: Compiled executable**

```python
calculators = "sh://./run_simulation"
```

**Example 4: With multiple arguments**

```python
calculators = "sh://bash run.sh --method=fast --tolerance=1e-6"
```

### How it Works

1. **Create temporary directory**: FZ creates a unique temp directory
2. **Copy input files**: All compiled input files are copied to temp directory
3. **Execute command**: Command is run with input files as arguments
4. **Parse outputs**: Results are extracted using model's output commands
5. **Cleanup**: Temp directory is cleaned (preserved in DEBUG mode)

**Command receives**:
```bash
# If input.txt is your input file:
bash calculate.sh input.txt

# Multiple input files:
bash calculate.sh file1.txt file2.dat config.ini
```

**Files named in the command** (`sh://cat in.txt > res.txt`): a bare word such as `script.sh`
or `data.txt` is turned into an absolute path in the *launch* directory only if it exists
there **and** does not exist in the case directory (the compiled input files win). Targets
of `>`, `>>` and `2>` redirections are never rewritten, so outputs stay in the case
directory. Each rewritten word is logged at info level. A helper script that lives only next
to the caller (`sh://bash calc.sh`) therefore works, while per-case files must be referred to
by bare name. Earlier versions rewrote every file-looking word, which could make a command
read the un-substituted template and write outside the case directory (see `NEWS.md`).

The input file names are appended to the end of the **whole** command line, after any
pipe or redirection: `sh://cat input.txt > res.txt` runs
`cat input.txt > res.txt input.txt`, so `res.txt` holds the input twice. Put anything
beyond a single command in a script (`sh://bash run.sh`), where `$1`, `$2`, ... are the
compiled input files.

### Example Calculator Script

**`calculate.sh`**:
```bash
#!/bin/bash

# Input file is passed as first argument
INPUT_FILE=$1

# Read input variables
source $INPUT_FILE

# Run calculation
echo "Running with temp=$temp, pressure=$pressure"
result=$(echo "scale=2; $temp * $pressure / 100" | bc)

# Write output
echo "result=$result" > output.txt
echo "Done"
```

### Parallel Execution

Use multiple `sh://` calculators for parallel execution:

```python
# 4 parallel workers
calculators = [
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh"
]

# Or more concisely:
calculators = ["sh://bash calc.sh"] * 4
```

## Remote SSH Calculator (`ssh://`)

Execute calculations on remote servers via SSH.

### Basic Syntax

```python
# With password (not recommended)
calculators = "ssh://user:password@host:port/command"

# With key authentication (recommended)
calculators = "ssh://user@host/command"
```

### Examples

**Example 1: Basic SSH**

```python
calculators = "ssh://john@compute-server.edu/bash /home/john/run.sh"
```

**Example 2: Custom port**

```python
calculators = "ssh://john@server.edu:2222/bash /path/to/script.sh"
```

**Example 3: HPC cluster**

```python
calculators = "ssh://user@hpc.university.edu/sbatch /scratch/user/submit.sh"
```

**Example 4: Multiple remote calculators**

```python
calculators = [
    "ssh://user@node1.cluster.edu/bash /path/to/run.sh",
    "ssh://user@node2.cluster.edu/bash /path/to/run.sh",
    "ssh://user@node3.cluster.edu/bash /path/to/run.sh"
]
```

### How it Works

1. **Connect via SSH**: Establish SSH connection (key or password auth)
2. **Create remote directory**: Create temporary directory on remote host
3. **Transfer input files**: SFTP upload all input files
4. **Execute command**: Run command on remote host
5. **Transfer outputs**: SFTP download result files
6. **Cleanup**: Remove remote temp directory

### Authentication

- **SSH key / agent** (recommended): `ssh://user@host/...`; keys from `~/.ssh/` and the
  SSH agent are used.
- **Password in URI**: `ssh://user:password@host/...`; keys and agent are then not
  tried. The password is masked in results, logs and manifests (a warning is logged once
  per host) but stays in your scripts.
- There is **no interactive password prompt**. Without `user@`, the user name is
  `$SSH_USER`, else the local user name.

### Host Key Verification

Behavior for a host absent from `~/.ssh/known_hosts`:

| Authentication | Behavior |
|----------------|----------|
| SSH key (no password in URI) | Host key added automatically (paramiko `AutoAddPolicy`, no fingerprint check) |
| Password in URI | Interactive prompt on stdin: `Accept this host key? [y/N/fingerprint]` (blocks unattended runs) |
| `FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1` | Host key added automatically, whatever the authentication |

When host identity matters, populate `~/.ssh/known_hosts` beforehand
(`ssh-keyscan host >> ~/.ssh/known_hosts`, then check the fingerprint).

### SSH Configuration

**Environment variables**:
```bash
export FZ_SSH_KEEPALIVE=300           # Keepalive interval (seconds)
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1  # Auto-accept host keys
```

**Python** (environment variables are read at `import fz`; reload after changing them):
```python
import os, fz
os.environ['FZ_SSH_KEEPALIVE'] = '300'
os.environ['FZ_SSH_AUTO_ACCEPT_HOSTKEYS'] = '0'
fz.reload_config()
```

### Remote Script Example

**Remote script** (`/home/user/run.sh` on server):
```bash
#!/bin/bash

# Input files are in current directory
source input.txt

# Load modules on HPC
module load gcc/11.2
module load openmpi/4.1

# Run simulation
mpirun -np 16 ./simulation input.txt

# Results written to output.txt
```

## SLURM Workload Manager (`slurm://`)

Execute calculations on SLURM clusters (local or remote).

### Basic Syntax

```python
# Local SLURM
calculators = "slurm://:partition/command"

# Remote SLURM via SSH
calculators = "slurm://user@host:partition/command"
calculators = "slurm://user@host:port:partition/command"  # with custom SSH port
```

**Note**: For local execution, the partition must be prefixed with a colon (`:partition`).

### Examples

**Example 1: Local SLURM execution**

```python
calculators = "slurm://:compute/bash script.sh"
```

**Example 2: Remote SLURM on HPC cluster**

```python
calculators = "slurm://user@cluster.edu:gpu/bash simulation.sh"
```

**Example 3: Remote SLURM with custom SSH port**

```python
calculators = "slurm://user@hpc.university.edu:2222:compute/bash run.sh"
```

**Example 4: Multiple SLURM partitions for parallel execution**

```python
calculators = [
    "slurm://user@cluster:compute/bash calc.sh",
    "slurm://user@cluster:gpu/bash calc.sh",
    "slurm://user@cluster:highmem/bash calc.sh"
]
```

### How it Works

**Local execution**:
1. Uses `srun --partition=<partition> <command>` directly
2. Automatically handles SLURM partition scheduling
3. Supports interrupt handling (Ctrl+C terminates SLURM jobs)

**Remote execution**:
1. Connects via SSH to remote cluster
2. Transfers input files via SFTP
3. Executes `srun` on remote cluster
4. Retrieves results via SFTP

### Features

- **Partition specification**: Control which SLURM partition to use
- **Automatic file transfer**: For remote execution
- **Timeout handling**: Configurable execution timeouts
- **Interrupt support**: Graceful job termination with Ctrl+C
- **Compatible with all SLURM schedulers**

### Requirements

- **Local**: SLURM installed (`srun` command available)
- **Remote**: SSH access to SLURM cluster + `paramiko` library

## SLURM Job Arrays (`slurm-array://`, local only)

Asynchronous twin of `slurm://`. Cases submitted within a short window are batched
into **one** `sbatch --array` job — a single calculator URI runs all N cases
concurrently, and is not locked per case — instead of one blocking `srun` per case.
A single shared monitor thread follows every task with one `sacct` call per poll
(falling back to `squeue` when accounting is disabled).

```python
calculators = "slurm-array://:compute/bash script.sh?cores=4&mem=8G&time=01:00:00&maxrunning=20"
```

**Resources** (URI query string, for both `slurm://` and `slurm-array://`): `cores`
(`--cpus-per-task`), `mem`, `time`, `nodes`, `ntasks`, `gres`, `account`, `qos`, plus
`maxrunning` (array throttle, `--array=0-N%M`; `slurm-array://` only). Values are
validated against a whitelist.

**Environment variables**:
```bash
export FZ_SLURM_POLL_INTERVAL=2      # seconds between sacct/squeue polls (default: 2)
export FZ_SLURM_ARRAY_WINDOW=1       # seconds cases are gathered before one sbatch (default: 1)
```

`slurm-array://` supports local SLURM only; remote SLURM stays on `slurm://`.

### Configuration

**Environment variables**:
```bash
export FZ_RUN_TIMEOUT=3600    # Timeout in seconds (default: 3600 = 1 hour for sh://, funz://;
                               # unlimited for ssh://, slurm:// when unset); a model's own
                               # "timeout" entry (int, or None/0 to disable) overrides this
export FZ_SSH_KEEPALIVE=300   # For remote SLURM
```

**Python**:
```python
import os, fz
os.environ['FZ_RUN_TIMEOUT'] = '7200'  # 2 hours
fz.reload_config()                     # FZ_* variables are read at import
```

## Funz Server Calculator (`funz://`)

Execute calculations on legacy Java Funz calculator servers (TCP protocol), located by
UDP discovery. Full protocol description: [funz-protocol.md](funz-protocol.md).

### Basic Syntax

```python
calculators = "funz://:19001/R"                     # listen on UDP port 19001, code "R"
calculators = "funz://server.example.com:19001/R"   # TCP connection to that host
```

**URI Format**: `funz://[host]:<udp_port>/<code>`
- `host`: host to open the TCP connection to (default: `localhost`)
- `udp_port`: **UDP port on which calculators broadcast their availability** (required);
  the TCP port is read from the broadcast, not from the URI
- `code`: code name the calculator must offer (e.g. `R`, `Python`, `Modelica`, `bash`)

### Examples

```python
import fz

model = {"output": {"pressure": "grep 'pressure = ' output.txt | awk '{print $3}'"}}

results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300]},
    model,
    calculators=["funz://:19001/bash"] * 3,   # up to 3 calculators in parallel
    results_dir="results",
)
```

### How it Works

1. **Discovery**: listen on the UDP port (up to 10 s) for calculator broadcasts; prefer an
   idle calculator offering `code`, then any calculator offering it, then the first seen.
2. **Reservation**: connect to the advertised TCP port and reserve the calculator.
3. **Upload / execute / download** through the Funz text protocol.
4. **Unreservation**: release the calculator.

Discovery can also be called directly:

```python
from fz import discover_funz_servers
servers = discover_funz_servers(19001, listen_duration=10)
# [{'host': ..., 'tcp_port': 5555, 'name': 'calc1', 'os': ..., 'activity': 'idle',
#   'idle': True, 'codes': ['R', 'Python']}, ...]
```

### UDP broadcast format

Newline-separated, as built by the Java calculator: name, TCP port, start timestamp,
operating system, activity (`idle` when free), number of codes, then one code per line.

### Requirements

- A running Java Funz calculator (see `tools/setup_funz_calculator.sh` and
  `tools/start_funz_calculator.sh`)
- UDP broadcasts from the calculator must reach the machine running fz, and its TCP
  port must be reachable
- Default timeout: 3600 s (like `sh://`)

## Cache Calculator (`cache://`)

Reuse results from previous calculations based on input file hashes.

### Basic Syntax

```python
calculators = "cache://path/to/results"
```

### Examples

**Example 1: Single cache directory**

```python
calculators = "cache://previous_run"
```

**Example 2: Multiple cache locations**

```python
calculators = [
    "cache://run1",
    "cache://run2",
    "cache://archive/results"
]
```

**Example 3: Glob patterns**

```python
# Check all subdirectories
calculators = "cache://archive/*/"

# Check specific pattern
calculators = "cache://runs/2024-*/results"
```

**Example 4: Cache with fallback**

```python
calculators = [
    "cache://previous_results",  # Try cache first
    "sh://bash calculate.sh"      # Run if cache miss
]
```

### How it Works

1. **Compute input hash**: SHA-256 hash of all compiled input files
2. **Search cache**: Look for matching `.fz_hash` file
3. **Check code identity**: verify the calculator's declared `code_id` (below)
4. **Validate outputs**: Check that outputs are not None
5. **Copy results**: If match found, reuse cached results
6. **Skip calculation**: No execution needed

### Cache Matching

**`.fz_hash` file format** (versioned "v2", SHA-256; `# code_id:` is only
written once the calculator that produced these results is known - and only
when that calculator declares one):
```
# fz-hash v2
# code_id: telemac@v8p5
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

**Matching criteria**:
- All input file hashes must match
- All output values must be non-None
- The candidate's `code_id` must be compatible with the calculators available
  to this run (see "Cache identity (`code_id`)" below) - **not** its command
  or host, which routinely differ for the exact same code
- If match: reuse results (no calculation)
- If mismatch: fall through to next calculator

### Reusing the same results directory (`cache://_`)

An existing `results_dir` is renamed with a timestamp suffix before a run. The special
entry `cache://_` points to that renamed copy, so a study can be resumed or extended in
place:

```python
fz.fzr("input.txt", variables, model,
       calculators=["cache://_", "sh://bash calc.sh"], results_dir="results")
```

`cache://results` with `results_dir="results"` finds nothing: it designates the new,
empty directory.

### Cache Identity (`code_id`)

The command is deliberately excluded from the cache key: the same code can be
invoked as `bash run.sh` locally and `/opt/telemac/v8p5/run.sh` over SSH, and
keying on the command would defeat cache sharing across calculators. Instead,
a calculator alias may declare the identity of its code installation:

```json
{
    "uri": "ssh://user@cluster/bash /opt/telemac/v8p5/run.sh",
    "code_id": "telemac@v8p5"
}
```

- Same `code_id` on both sides → match, whatever the command.
- Different `code_id` → never matches, even with an identical command.
- No `code_id` declared on either side → still matches (backward compatible),
  with a one-time warning per campaign; `FZ_CACHE_STRICT=1` refuses instead.
- `version_cmd` resolves `code_id` by running a command on the calculator
  (once per calculator per session) instead of hardcoding it:
  `{"uri": "sh://bash ./run.sh", "version_cmd": "./run.sh --version"}`.
- A cache directory written by an older `fz` (no `# fz-hash v2` header) has no
  identity at all and is ignored unless `FZ_CACHE_ACCEPT_LEGACY=1`.

### Cache Directory Structure

```
previous_run/
├── case1/
│   ├── input.txt
│   ├── output.txt
│   ├── .fz_hash        # Hash file for cache matching
│   └── log.txt
├── case2/
│   ├── input.txt
│   ├── output.txt
│   ├── .fz_hash
│   └── log.txt
└── case3/
    └── ...
```

### Use Cases for Cache

**Resume interrupted runs**:
```python
# First run (interrupted with Ctrl+C)
fz.fzr("input.txt", variables, model, calculators="sh://bash calc.sh", results_dir="run1/")

# Resume from cache
fz.fzr(
    "input.txt",
    variables,
    model,
    calculators=["cache://run1", "sh://bash calc.sh"],  # Cache + fallback
    results_dir="run2/"
)
```

**Expand parameter space**:
```python
# Original run: 10 cases
fz.fzr("input.txt", {"temp": range(10)}, model, calculators="sh://bash calc.sh", results_dir="run1/")

# Expanded run: 20 cases (reuses first 10)
fz.fzr(
    "input.txt",
    {"temp": range(20)},  # 10 new cases
    model,
    calculators=["cache://run1", "sh://bash calc.sh"],
    results_dir="run2/"
)
```

**Compare methods using same inputs**:
```python
# Method 1
fz.fzr("input.txt", variables, model, calculators="sh://method1.sh", results_dir="results_m1/")

# Method 2 (reuses inputs, different calculator)
fz.fzr("input.txt", variables, model, calculators="sh://method2.sh", results_dir="results_m2/")
```

## Multiple Calculators

### Parallel Execution

Multiple calculators run cases in parallel:

```python
calculators = [
    "sh://bash calc.sh",
    "sh://bash calc.sh",
    "sh://bash calc.sh"
]
# 3 cases run concurrently
```

**Load balancing**: Round-robin distribution
- Case 0 → Calculator 0
- Case 1 → Calculator 1
- Case 2 → Calculator 2
- Case 3 → Calculator 0
- etc.

### Fallback Chain

Calculators tried in order until one succeeds:

```python
calculators = [
    "cache://previous_run",       # 1. Try cache
    "sh://bash fast_method.sh",   # 2. Try fast method
    "sh://bash robust_method.sh", # 3. Fallback to robust
    "ssh://user@hpc/bash slow_but_reliable.sh"  # 4. Last resort
]
```

**Retry mechanism**:
- Each case tries calculators in order
- Stops at first success
- Controlled by `FZ_MAX_RETRIES` environment variable

### Mixed Calculator Types

Combine local, remote, and cache:

```python
calculators = [
    "cache://archive/*",                      # Check archive
    "sh://bash quick_calc.sh",                # Local quick method
    "sh://bash intensive_calc.sh",            # Local intensive method
    "ssh://user@cluster/bash hpc_calc.sh"    # Remote HPC
]
```

## Calculator Aliases

Store calculator configurations in `.fz/calculators/` directory.

### Creating Calculator Alias

**`.fz/calculators/cluster.json`**:
```json
{
    "uri": "ssh://user@hpc.university.edu",
    "models": {
        "perfectgas": "bash /home/user/codes/perfectgas/run.sh",
        "cfd": "bash /home/user/codes/cfd/run.sh",
        "md": "bash /home/user/codes/md/run.sh"
    }
}
```

### Using Calculator Aliases

```python
# Use calculator alias instead of full URI
results = fz.fzr(
    "input.txt",
    variables,
    "perfectgas",      # Model alias
    calculators="cluster",  # Calculator alias
    results_dir="results"
)

# FZ resolves to: ssh://user@hpc.university.edu/bash /home/user/codes/perfectgas/run.sh
```

### Calculator Search Path

FZ searches for calculators in:
1. Current directory: `./.fz/calculators/`
2. Home directory: `~/.fz/calculators/`

### Calculator-Model Compatibility

An alias's `models` table maps each model id to the command to run for it. When a campaign
uses an alias with model `perfectgas`, fz takes the command from `models["perfectgas"]`
and appends it to the alias `uri`.

- If the calculators are **auto-discovered** (`calculators="*"`),
  aliases whose `models` table does not list the model are skipped.
- If an alias is named explicitly and its `models` table has **no entry** for the model,
  no command is added: the bare `uri` is used. For `sh://` this leaves nothing to run, and
  the case fails (typically with a "Permission denied when executing './input.txt'"
  error, since fz tries to execute the input file itself).
- Direct URIs (`sh://bash any_script.sh`) are never checked: you are responsible for the
  compatibility between the command and the model.

Use `fz list --check` (`fzl`) to validate installed models and calculators; its output
lists the calculators that support each model (see [Core functions](core-functions.md)).

## Advanced Patterns

### Pattern 1: Multi-tier Execution

```python
calculators = [
    "cache://archive/*/*",           # Check deep archive
    "sh://bash fast.sh",              # Quick local method
    "ssh://fast@cluster/bash fast.sh", # Fast remote
    "ssh://robust@cluster/bash robust.sh"  # Robust remote
]
```

### Pattern 2: Geographic Distribution

```python
calculators = [
    "ssh://user@us-east.cluster/bash run.sh",
    "ssh://user@us-west.cluster/bash run.sh",
    "ssh://user@eu.cluster/bash run.sh",
    "ssh://user@asia.cluster/bash run.sh"
]
```

### Pattern 3: Resource-based Selection

```python
# Assign heavy calculations to HPC, light ones to local
if is_heavy_calculation(variables):
    calculators = "ssh://user@hpc/sbatch heavy.sh"
else:
    calculators = "sh://bash light.sh"

results = fz.fzr("input.txt", variables, model, calculators=calculators)
```

### Pattern 4: Development vs Production

```python
import os

if os.getenv('ENVIRONMENT') == 'production':
    calculators = "ssh://user@production-cluster/bash run.sh"
else:
    calculators = "sh://bash run_local.sh"  # Fast local testing
```

## Environment Variables

The variables that affect calculators (`FZ_MAX_RETRIES`, `FZ_MAX_WORKERS`, `FZ_RUN_TIMEOUT`,
`FZ_SSH_KEEPALIVE`, `FZ_SSH_AUTO_ACCEPT_HOSTKEYS`, `FZ_CACHE_STRICT`, `FZ_CACHE_ACCEPT_LEGACY`,
`FZ_SLURM_POLL_INTERVAL`, `FZ_SLURM_ARRAY_WINDOW`, ...) are listed, with their defaults, in
[Configuration](configuration.md); `cache://` identity checks are described in "Cache Calculator" above.

## Best Practices

### 1. Use Absolute Paths for Remote Calculators

```python
# Good
calculators = "ssh://user@host/bash /absolute/path/to/script.sh"

# Bad (may not work)
calculators = "ssh://user@host/bash script.sh"
```

### 2. Test Calculators Manually First

```bash
# Test local
bash calculate.sh input.txt

# Test remote
ssh user@host "bash /path/to/script.sh /path/to/input.txt"
```

### 3. Use Cache for Expensive Calculations

```python
# Always put cache first
calculators = [
    "cache://previous_runs",
    "sh://bash expensive_calculation.sh"
]
```

### 4. Handle Calculator Failures

```python
# Provide fallback calculators
calculators = [
    "sh://bash may_fail.sh",
    "sh://bash reliable_backup.sh"
]
```

### 5. Monitor Calculator Usage

```python
results = fz.fzr("input.txt", variables, model, calculators=calculators, results_dir="results/")

# Check which calculator was used
print(results[['calculator', 'status', 'error']].value_counts())
```
