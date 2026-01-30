# FZ Calculators

## What is a Calculator?

A calculator is an execution backend that runs your computational code. FZ supports three types:

1. **`sh://`** - Local shell execution
2. **`ssh://`** - Remote SSH execution
3. **`cache://`** - Reuse cached results

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

**Key-based (recommended)**:
```python
# Uses SSH keys from ~/.ssh/
calculators = "ssh://user@host/bash script.sh"
```

**Password-based** (not recommended):
```python
# Password in URI (insecure, avoid in production)
calculators = "ssh://user:password@host/bash script.sh"
```

**Interactive**:
```python
# FZ will prompt for password if needed
calculators = "ssh://user@host/bash script.sh"
# Prompt: "Enter password for user@host:"
```

### Host Key Verification

First-time connection to a new host:
```
WARNING: Host key verification for host.edu
Fingerprint: SHA256:abc123def456...
Do you want to accept this host key? (yes/no):
```

**Auto-accept** (use with caution):
```bash
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1
```

### SSH Configuration

**Environment variables**:
```bash
export FZ_SSH_KEEPALIVE=300           # Keepalive interval (seconds)
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=1  # Auto-accept host keys
```

**Python**:
```python
import os
os.environ['FZ_SSH_KEEPALIVE'] = '300'
os.environ['FZ_SSH_AUTO_ACCEPT_HOSTKEYS'] = '0'
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

### Configuration

**Environment variables**:
```bash
export FZ_RUN_TIMEOUT=3600    # Timeout in seconds (default: 600 = 10 minutes)
export FZ_SSH_KEEPALIVE=300   # For remote SLURM
```

**Python**:
```python
import os
os.environ['FZ_RUN_TIMEOUT'] = '7200'  # 2 hours
```

## Funz Server Calculator (`funz://`)

Execute calculations using legacy Java Funz calculator servers via TCP socket protocol.

### Basic Syntax

```python
# Local Funz server
calculators = "funz://:port/code"

# Remote Funz server
calculators = "funz://host:port/code"
```

**URI Format**: `funz://[host]:<port>/<code>`
- `host`: Server hostname (default: localhost)
- `port`: Server port (required)
- `code`: Calculator code/model name (e.g., "R", "Python", "Modelica", "bash")

### Examples

**Example 1: Connect to local Funz server**

```python
calculators = "funz://:5555/R"
```

**Example 2: Connect to remote Funz server**

```python
calculators = "funz://server.example.com:5555/Python"
```

**Example 3: Multiple Funz servers for parallel execution**

```python
calculators = [
    "funz://:5555/R",
    "funz://:5556/R",
    "funz://:5557/R"
]
```

**Example 4: Complete parametric study**

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
    calculators="funz://:5555/bash"
)
```

### How it Works

1. **Calculator reservation**: Connects to Funz server and reserves calculator
2. **File upload**: Transfers input files to server
3. **Remote execution**: Executes calculation via Funz protocol
4. **Result download**: Retrieves output files
5. **Unreservation**: Releases calculator and cleans up

### Funz Protocol

The Funz calculator uses a text-based TCP socket communication protocol:

- **RESERVE**: Request calculator reservation with authentication
- **EXECUTE**: Submit calculation job
- **STATUS**: Check job status
- **DOWNLOAD**: Retrieve result files
- **UNRESERVE**: Release calculator

### UDP Discovery

Funz calculators broadcast their availability via UDP:

```
Port 5555 (UDP): Broadcasts availability every ~5 seconds
  Message format:
    Line 1: Protocol version (e.g., "FUNZ1.0")
    Line 2: TCP port number
    Line 3+: Available codes (bash, R, Python, etc.)

Port <TCP> (dynamic): Actual calculator communication
```

See `funz-protocol.md` for detailed protocol documentation.

### Features

- **Compatible with legacy Java Funz servers**
- **Automatic file upload/download**
- **TCP socket communication**
- **Calculator reservation system**
- **Interrupt handling support**
- **Authentication support**

### Requirements

- Funz calculator server running (Java-based)
- Network access to server port
- No Python dependencies beyond standard library

### Starting a Funz Calculator

See `tools/start_funz_calculator.sh` and `tools/setup_funz_calculator.sh` for helper scripts.

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

1. **Compute input hash**: MD5 hash of all input files
2. **Search cache**: Look for matching `.fz_hash` file
3. **Validate outputs**: Check that outputs are not None
4. **Copy results**: If match found, reuse cached results
5. **Skip calculation**: No execution needed

### Cache Matching

**`.fz_hash` file format**:
```
a1b2c3d4e5f6...  input.txt
f6e5d4c3b2a1...  config.dat
```

**Matching criteria**:
- All input file hashes must match
- All output values must be non-None
- If match: reuse results (no calculation)
- If mismatch: fall through to next calculator

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
fz.fzr("input.txt", variables, model, "sh://bash calc.sh", "run1/")

# Resume from cache
fz.fzr(
    "input.txt",
    variables,
    model,
    ["cache://run1", "sh://bash calc.sh"],  # Cache + fallback
    "run2/"
)
```

**Expand parameter space**:
```python
# Original run: 10 cases
fz.fzr("input.txt", {"temp": range(10)}, model, "sh://bash calc.sh", "run1/")

# Expanded run: 20 cases (reuses first 10)
fz.fzr(
    "input.txt",
    {"temp": range(20)},  # 10 new cases
    model,
    ["cache://run1", "sh://bash calc.sh"],
    "run2/"
)
```

**Compare methods using same inputs**:
```python
# Method 1
fz.fzr("input.txt", variables, model, "sh://method1.sh", "results_m1/")

# Method 2 (reuses inputs, different calculator)
fz.fzr("input.txt", variables, model, "sh://method2.sh", "results_m2/")
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

results = fz.fzr("input.txt", variables, model, calculators)
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

```bash
# Maximum retry attempts per case
export FZ_MAX_RETRIES=5

# Thread pool size (parallel execution)
export FZ_MAX_WORKERS=8

# SSH-specific
export FZ_SSH_KEEPALIVE=300
export FZ_SSH_AUTO_ACCEPT_HOSTKEYS=0
```

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
results = fz.fzr("input.txt", variables, model, calculators, "results/")

# Check which calculator was used
print(results[['calculator', 'status', 'error']].value_counts())
```
