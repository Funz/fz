# Funz Calculator UDP Discovery and Integration

This document explains how the Funz calculator discovery mechanism works and how to test it with the Python `fz` library.

## Architecture Overview

The Funz calculator system uses a two-port communication model:

```
┌─────────────────────────────────────────────────────────────┐
│  Funz Calculator Daemon (Java)                              │
│                                                               │
│  1. UDP Broadcast Port (e.g., 5555)                         │
│     - Configured in XML: <HOST port="5555" />               │
│     - Broadcasts availability every ~5 seconds              │
│     - Message format:                                        │
│       Line 1: Protocol version (e.g., "FUNZ1.0")            │
│       Line 2: TCP port number                                │
│       Line 3+: Available codes (bash, sh, shell, etc.)      │
│                                                               │
│  2. TCP Communication Port (dynamic)                         │
│     - Actual calculator communication happens here           │
│     - Port number communicated via UDP broadcast            │
│     - Implements Funz protocol (RESERVE, EXECUTE, etc.)     │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ UDP Broadcast
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Client (Python fz library)                                  │
│                                                               │
│  1. Listen on UDP port 5555                                  │
│  2. Parse TCP port from UDP message                          │
│  3. Connect to TCP port for actual work                      │
│  4. Use funz://:tcp_port/code URI                           │
└─────────────────────────────────────────────────────────────┘
```

## Calculator Configuration

The calculator XML configuration specifies the UDP broadcast port:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<CALCULATOR name="calc-5555" spool="spool-5555">
  <!-- UDP broadcast port -->
  <HOST name="localhost" port="5555" />

  <!-- Available execution codes -->
  <CODE name="bash" command="/bin/bash" />
  <CODE name="sh" command="/bin/sh" />
  <CODE name="shell" command="/bin/bash" />
</CALCULATOR>
```

**Important Notes:**
- The `<HOST port="5555" />` is the **UDP broadcast port**, NOT the TCP port
- The TCP port is dynamically assigned and communicated via UDP broadcasts
- The calculator daemon broadcasts its availability every ~5 seconds

## Discovery Process

### 1. Start the Funz Calculator

Using the CI workflow as reference:

```bash
cd funz-calculator/dist

# Build classpath
LIB=""
for jar in lib/funz-core-*.jar lib/funz-calculator-*.jar lib/commons-*.jar \
           lib/ftpserver-*.jar lib/ftplet-*.jar lib/mina-*.jar \
           lib/sigar-*.jar lib/slf4j-*.jar; do
  if [ -f "$jar" ]; then
    LIB="${LIB}:${jar}"
  fi
done
LIB="${LIB:1}"  # Remove leading colon

# Start calculator daemon
java -Dapp.home=. -classpath "$LIB" \
  org.funz.calculator.Calculator \
  file:calculator-5555.xml > calculator.log 2>&1 &
```

### 2. Discover Calculator via UDP

The test script `test_funz_udp_discovery.py` demonstrates discovery:

```python
def discover_funz_calculator_udp(udp_port: int = 5555, timeout: float = 10.0):
    """Listen to UDP broadcasts and extract TCP port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('', udp_port))
    sock.settimeout(timeout)

    data, addr = sock.recvfrom(4096)
    message = data.decode('utf-8').strip()
    lines = message.split('\n')

    # Parse message
    version = lines[0]      # "FUNZ1.0"
    tcp_port = int(lines[1])  # e.g., "55123"
    codes = lines[2:]       # ["bash", "sh", "shell"]

    return {'tcp_port': tcp_port, 'codes': codes, 'version': version}
```

### 3. Use fzr with Discovered TCP Port

Once you have the TCP port, use it in the `funz://` URI:

```python
import fz

# Discovered TCP port from UDP broadcast
tcp_port = 55123  # Example value from discovery

# Use funz:// with the TCP port
results = fz.fzr(
    "input.txt",
    {"x": [1, 2, 3], "y": [10, 20]},
    model={"output": {"sum": "grep 'sum = ' output.txt | awk '{print $3}'"}},
    calculators=f"funz://:{tcp_port}/bash"
)
```

**URI Format:**
- `funz://:<tcp_port>/<code>` - Local calculator (localhost)
- `funz://hostname:<tcp_port>/<code>` - Remote calculator

## Running the Test Script

### Two Approaches

**Approach 1: Standalone Scripts (Recommended for Local Development)**

Use dedicated shell scripts to manage Funz calculator separately from tests:

```bash
# One-time setup: Install Funz calculator
./tools/setup_funz_calculator.sh

# Start calculator daemon
./tools/start_funz_calculator.sh

# Run tests (reuses running calculator)
python test_funz_udp_discovery.py --no-setup

# Stop calculator when done
./tools/stop_funz_calculator.sh
```

**Benefits:**
- Faster iteration (no re-download/build between test runs)
- Calculator persists across multiple test sessions
- Easier debugging (inspect running calculator)
- See `tools/README.md` for detailed documentation

**Approach 2: Fully Automatic (Good for CI/One-off Testing)**

The test script automatically downloads, builds, and starts everything:

```bash
python test_funz_udp_discovery.py
```

### Prerequisites

**Minimum Requirements:**
- Python 3.7+
- Java 11+ (JDK with `javac`)
- Apache Ant (for building Java projects)
- Git (for cloning repositories)

**Install on Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install -y openjdk-11-jdk ant git

# Install Python dependencies
pip install -e .
pip install pandas  # Optional but recommended
```

**Install on macOS:**
```bash
brew install openjdk@11 ant git

# Install Python dependencies
pip install -e .
pip install pandas
```

### Basic Usage

**Fully Automatic (Recommended):**
```bash
# Downloads Funz components, builds them, starts calculator, runs tests
python test_funz_udp_discovery.py
```

The script will:
1. Download funz-profile, funz-core, funz-calculator to `~/.funz_test/`
2. Build all components with `ant`
3. Create calculator configuration (UDP port 5555)
4. Start calculator daemon
5. Discover calculator via UDP
6. Run fzr integration tests
7. Clean up (stop calculator)

**Skip Re-downloading (if already exists):**
```bash
# Use existing Funz installation in ~/.funz_test
python test_funz_udp_discovery.py --skip-download
```

**Use Existing Calculator (Manual Setup):**
```bash
# Skip automatic setup, use calculator you started manually
python test_funz_udp_discovery.py --no-setup
```

### Advanced Configuration

**Custom Installation Directory:**
```bash
python test_funz_udp_discovery.py --setup-dir /opt/funz_test
```

**Custom UDP Port:**
```bash
python test_funz_udp_discovery.py --udp-port 5556
# Or via environment variable:
FUNZ_UDP_PORT=5556 python test_funz_udp_discovery.py
```

**Longer Discovery Timeout:**
```bash
python test_funz_udp_discovery.py --discovery-timeout 30
# Or via environment variable:
FUNZ_DISCOVERY_TIMEOUT=30 python test_funz_udp_discovery.py
```

**Debug Logging:**
```bash
FZ_LOG_LEVEL=DEBUG python test_funz_udp_discovery.py
```

**Combined Example:**
```bash
# Custom directory, skip download, debug logging
python test_funz_udp_discovery.py \
  --setup-dir ~/my_funz \
  --skip-download \
  --udp-port 5555 \
  --discovery-timeout 20
```

## Expected Output

```
======================================================================
 Funz UDP Discovery and fzr Integration Test
======================================================================

Configuration:
  UDP Port: 5555 (set via FUNZ_UDP_PORT env var)
  Discovery Timeout: 15s (set via FUNZ_DISCOVERY_TIMEOUT env var)

Step 1: UDP Discovery
----------------------------------------------------------------------
🔍 Discovering Funz calculator on UDP port 5555...
   (Timeout: 15.0s)
   Listening for UDP broadcasts on 0.0.0.0:5555...

📡 Received UDP broadcast from 127.0.0.1:49152
   Raw message (45 bytes):
   Line 1: FUNZ1.0
   Line 2: 55123
   Line 3: bash
   Line 4: sh
   Line 5: shell

✅ Funz calculator discovered!
   Host: 127.0.0.1
   TCP Port: 55123
   Version: FUNZ1.0
   Available codes: bash, sh, shell

Step 2: Test fzr with Funz Calculator
----------------------------------------------------------------------
Testing fzr with funz://55123/bash
======================================================================

📁 Working directory: /tmp/funz_test_abc123
✓ Created input template: input.txt
✓ Created calculation script: calculate.sh

🚀 Running fzr with:
   Calculator: funz://:55123/bash
   Parameters: {'x': [1, 2, 3], 'y': [10, 20]}
   Expected cases: 6 (Cartesian product)

======================================================================
✅ fzr completed successfully!
======================================================================

📊 Results:
   x  y  sum  product
0  1 10   11       10
1  1 20   21       20
2  2 10   12       20
3  2 20   22       40
4  3 10   13       30
5  3 20   23       60

✓ Generated 6/6 cases
✓ Output variables parsed correctly
✓ All calculations verified correct

======================================================================
 Test Summary
======================================================================
  UDP Discovery: ✅ Success
  TCP Port: 55123
  fzr Integration: ✅ Success

✅ ALL TESTS PASSED
```

## Troubleshooting

### No UDP broadcasts received

**Symptoms:**
```
❌ No Funz calculator discovered after 15s timeout
```

**Solutions:**
1. **Check calculator is running:**
   ```bash
   ps aux | grep funz.calculator.Calculator
   ```

2. **Verify UDP port in calculator XML:**
   ```bash
   grep '<HOST.*port=' calculator-5555.xml
   # Should show: <HOST name="localhost" port="5555" />
   ```

3. **Check if UDP port is listening:**
   ```bash
   netstat -uln | grep 5555
   # Note: UDP doesn't show as "LISTEN" but broadcasts should be visible with:
   sudo tcpdump -i lo -n port 5555
   ```

4. **Firewall blocking UDP:**
   ```bash
   # Allow UDP on port 5555
   sudo ufw allow 5555/udp
   ```

5. **Calculator not broadcasting yet:**
   - Wait 5-10 seconds after starting calculator
   - Check calculator logs for errors:
     ```bash
     tail -f calculator.log
     ```

### UDP discovered but fzr fails

**Symptoms:**
```
✅ Funz calculator discovered! TCP Port: 55123
❌ fzr failed with error: Connection refused
```

**Solutions:**
1. **Verify TCP port is listening:**
   ```bash
   netstat -tln | grep 55123
   # Should show: tcp  0  0 127.0.0.1:55123  LISTEN
   ```

2. **Test TCP connection directly:**
   ```bash
   telnet localhost 55123
   # Or
   nc -v localhost 55123
   ```

3. **Check calculator logs for errors:**
   ```bash
   tail -50 calculator.log
   ```

4. **Increase fzr timeout:**
   ```python
   results = fz.fzr(..., timeout=300)  # 5 minutes
   ```

### Wrong TCP port in URI

**Symptoms:**
```
❌ Must use TCP port from UDP discovery, not UDP port in URI
```

**Correct Usage:**
```python
# ❌ WRONG - using UDP broadcast port
funz://5555/bash

# ✅ CORRECT - using TCP port from UDP message
funz://55123/bash
```

## Integration with CI/CD

See `.github/workflows/funz-calculator.yml` for a complete CI workflow that:
1. Builds funz-calculator from source
2. Starts 3 calculator instances on different UDP ports
3. Runs UDP discovery tests
4. Executes fzr integration tests
5. Cleans up calculator processes

## References

- **Funz Protocol Tests**: `tests/test_funz_protocol.py`
- **Funz Integration Tests**: `tests/test_funz_integration.py`
- **Funz Runner Implementation**: `fz/runners.py:run_funz_calculation()`
- **CI Workflow**: `.github/workflows/funz-calculator.yml`
