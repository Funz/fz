# Funz Calculator Tools

Shell scripts for managing Funz calculator infrastructure locally.

## Quick Start

```bash
# 1. Install and build Funz calculator
./tools/setup_funz_calculator.sh

# 2. Start calculator daemon (UDP port 5555)
./tools/start_funz_calculator.sh

# 3. Run tests (uses existing calculator)
python test_funz_udp_discovery.py --no-setup

# 4. Stop calculator when done
./tools/stop_funz_calculator.sh
```

## Scripts

### `setup_funz_calculator.sh`

Downloads and builds the complete Funz calculator infrastructure.

**Usage:**
```bash
./tools/setup_funz_calculator.sh [install_dir]
```

**Arguments:**
- `install_dir`: Installation directory (default: `~/.funz_calculator`)

**What it does:**
1. Checks prerequisites (git, ant, java, javac)
2. Clones repositories:
   - funz-profile
   - funz-core
   - funz-calculator
3. Builds each component with `ant clean dist`
4. Creates environment file: `funz_env.sh`

**Example:**
```bash
# Install to default location (~/.funz_calculator)
./tools/setup_funz_calculator.sh

# Install to custom location
./tools/setup_funz_calculator.sh /opt/funz_calculator
```

**Output:**
```
~/.funz_calculator/
├── funz-profile/         # Profile definitions
├── funz-core/            # Core library
│   └── dist/             # Built JARs
├── funz-calculator/      # Calculator daemon
│   └── dist/             # Calculator executable
└── funz_env.sh           # Environment variables
```

---

### `start_funz_calculator.sh`

Starts the Funz calculator daemon.

**Usage:**
```bash
./tools/start_funz_calculator.sh [udp_port] [install_dir]
```

**Arguments:**
- `udp_port`: UDP port for broadcasts (default: `5555`)
- `install_dir`: Funz installation directory (default: `~/.funz_calculator`)

**What it does:**
1. Creates calculator configuration XML
2. Creates spool directory for calculator state
3. Builds Java classpath
4. Starts `java org.funz.calculator.Calculator`
5. Saves PID to file for later shutdown

**Examples:**
```bash
# Start on default port 5555
./tools/start_funz_calculator.sh

# Start on custom port 5556
./tools/start_funz_calculator.sh 5556

# Use custom installation directory
./tools/start_funz_calculator.sh 5555 /opt/funz_calculator
```

**Calculator Configuration:**

The calculator broadcasts UDP messages on the configured port containing:
- Protocol version (e.g., "FUNZ1.0")
- TCP port number (dynamic)
- Available codes (bash, sh, shell)

Generated XML (`calculator-5555.xml`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<CALCULATOR name="calc-5555" spool="spool-5555">
  <HOST name="localhost" port="5555" />
  <CODE name="bash" command="/bin/bash" />
  <CODE name="sh" command="/bin/sh" />
  <CODE name="shell" command="/bin/bash" />
</CALCULATOR>
```

**Output Files:**
- PID file: `~/.funz_calculator/funz-calculator/dist/calculator_5555.pid`
- Log file: `~/.funz_calculator/funz-calculator/dist/calculator_5555.log`
- Config: `~/.funz_calculator/funz-calculator/dist/calculator-5555.xml`
- Spool: `~/.funz_calculator/funz-calculator/dist/spool-5555/`

**Monitoring:**
```bash
# Watch log file
tail -f ~/.funz_calculator/funz-calculator/dist/calculator_5555.log

# Check if running
ps aux | grep org.funz.calculator.Calculator

# Listen for UDP broadcasts
sudo tcpdump -i lo -n port 5555 -X
```

---

### `stop_funz_calculator.sh`

Stops the Funz calculator daemon gracefully.

**Usage:**
```bash
./tools/stop_funz_calculator.sh [udp_port] [install_dir]
```

**Arguments:**
- `udp_port`: UDP port of calculator to stop (default: `5555`)
- `install_dir`: Funz installation directory (default: `~/.funz_calculator`)

**What it does:**
1. Reads PID from file
2. Sends SIGTERM for graceful shutdown
3. Waits up to 5 seconds
4. Force kills with SIGKILL if needed
5. Removes PID file
6. Preserves log file

**Examples:**
```bash
# Stop calculator on default port 5555
./tools/stop_funz_calculator.sh

# Stop calculator on custom port 5556
./tools/stop_funz_calculator.sh 5556

# Use custom installation directory
./tools/stop_funz_calculator.sh 5555 /opt/funz_calculator
```

---

### `mock_funz_udp_broadcast.py`

Mock UDP broadcaster for testing discovery without Java stack.

**Usage:**
```bash
python tools/mock_funz_udp_broadcast.py [options]
```

**Options:**
- `--udp-port PORT`: UDP port to broadcast on (default: 5555)
- `--tcp-port PORT`: TCP port to advertise (default: 55555)
- `--codes CODE [CODE ...]`: Available code names (default: bash sh shell)
- `--interval SECONDS`: Broadcast interval (default: 5.0)
- `--version VERSION`: Protocol version (default: FUNZ1.0)

**Example:**
```bash
# Start mock broadcaster
python tools/mock_funz_udp_broadcast.py --udp-port 5555 --tcp-port 55555

# In another terminal, test UDP discovery
python test_funz_udp_discovery.py --no-setup --udp-port 5555
```

**Note:** Mock only broadcasts UDP. It won't accept TCP connections, so fzr tests will fail. Useful for debugging UDP discovery logic only.

---

## Complete Workflow Example

### First-time Setup

```bash
# 1. Install Funz calculator (one-time setup)
./tools/setup_funz_calculator.sh

# Output:
# ✅ Setup Complete
# Installation: /home/user/.funz_calculator
```

### Daily Usage

```bash
# 2. Start calculator
./tools/start_funz_calculator.sh

# Output:
# ✅ Calculator daemon running successfully
# PID: 12345
# UDP Port: 5555

# 3. Run tests (with existing calculator)
python test_funz_udp_discovery.py --no-setup

# Or run fzr directly after discovering TCP port
python -c "
from test_funz_udp_discovery import discover_funz_calculator_udp
info = discover_funz_calculator_udp(5555, 10)
print(f'TCP Port: {info[\"tcp_port\"]}')
"

# Then use with fzr
python -c "
import fz
results = fz.fzr('input.txt', {'x': [1,2,3]}, model, calculators='funz://:PORT/bash')
"

# 4. Stop calculator when done
./tools/stop_funz_calculator.sh

# Output:
# ✓ Calculator stopped gracefully
```

### Multiple Calculators

Run multiple calculators on different ports for parallel execution:

```bash
# Start 3 calculators
./tools/start_funz_calculator.sh 5555
./tools/start_funz_calculator.sh 5556
./tools/start_funz_calculator.sh 5557

# Use all three with fzr
python -c "
import fz
results = fz.fzr(
    'input.txt',
    {'x': range(10)},
    model,
    calculators=[
        'funz://:PORT1/bash',  # Discovered from UDP 5555
        'funz://:PORT2/bash',  # Discovered from UDP 5556
        'funz://:PORT3/bash'   # Discovered from UDP 5557
    ]
)
"

# Stop all
./tools/stop_funz_calculator.sh 5555
./tools/stop_funz_calculator.sh 5556
./tools/stop_funz_calculator.sh 5557
```

## Prerequisites

### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y git ant openjdk-11-jdk
```

### macOS
```bash
brew install git ant openjdk@11
```

### Verify Installation
```bash
git --version      # Should show version
ant -version       # Should show version
java -version      # Should show Java 11+
javac -version     # Should show Java 11+
```

## Troubleshooting

### Calculator won't start

**Check log file:**
```bash
cat ~/.funz_calculator/funz-calculator/dist/calculator_5555.log
```

**Common issues:**
- Missing JAR files: Re-run `setup_funz_calculator.sh`
- Port already in use: Choose different UDP port
- Java version too old: Install Java 11+

### Can't discover calculator via UDP

**Check if calculator is running:**
```bash
ps aux | grep org.funz.calculator.Calculator
```

**Listen for UDP broadcasts:**
```bash
# On Linux/macOS
sudo tcpdump -i lo -n port 5555 -X
```

**Check firewall:**
```bash
# Allow UDP port
sudo ufw allow 5555/udp  # Ubuntu
```

### Process won't stop

**Find and kill manually:**
```bash
# Find PID
pgrep -f "org.funz.calculator.Calculator"

# Kill process
kill -9 <PID>

# Remove PID file
rm ~/.funz_calculator/funz-calculator/dist/calculator_*.pid
```

## Environment Variables

Source the environment file for convenient access:

```bash
source ~/.funz_calculator/funz_env.sh
```

This sets:
- `FUNZ_PROFILE_HOME`: Profile directory
- `FUNZ_CORE_HOME`: Core library directory
- `FUNZ_CALCULATOR_HOME`: Calculator directory
- `PATH`: Adds calculator dist to PATH

## Integration with Tests

The test script `test_funz_udp_discovery.py` supports two modes:

**Mode 1: Automatic (downloads and starts everything)**
```bash
python test_funz_udp_discovery.py
```

**Mode 2: Manual (use existing calculator)**
```bash
# Start calculator first
./tools/start_funz_calculator.sh

# Run tests
python test_funz_udp_discovery.py --no-setup

# Stop when done
./tools/stop_funz_calculator.sh
```

**Mode 2 is faster** for repeated testing since it reuses the existing installation.

## See Also

- **Main documentation:** `../FUNZ_UDP_DISCOVERY.md`
- **Test script:** `../test_funz_udp_discovery.py`
- **CI workflow:** `../.github/workflows/funz-calculator.yml`
