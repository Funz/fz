# Funz Server Protocol and UDP Discovery

## Overview

The Funz protocol enables FZ to communicate with legacy Java Funz calculator servers via TCP socket communication. It provides:

- **TCP Protocol**: Text-based socket communication for calculator operations
- **UDP Discovery**: Automatic server detection via broadcast messages
- **Compatibility**: Full compatibility with existing Java Funz infrastructure
- **Reservation System**: Calculator locking with automatic timeout handling

## URI Format

```
funz://[host]:<port>/<code>
```

**Components:**
- `host`: Server hostname (default: `localhost` if omitted)
- `port`: UDP discovery port (required)
- `code`: Calculator/model code (e.g., "R", "Python", "Modelica")

**Examples:**
```python
# Local server on port 19001, code "R"
calculators = "funz://:19001/R"

# Remote server
calculators = "funz://server.example.com:19001/Python"

# Multiple servers for parallel execution
calculators = [
    "funz://:19001/R",
    "funz://:19002/R",
    "funz://:19003/R"
]
```

## UDP Discovery

### How It Works

1. **Client listens** on specified UDP port
2. **Server broadcasts** UDP messages periodically
3. **Client receives** broadcast containing TCP port and available codes
4. **Client connects** to TCP port for actual calculations

### UDP Broadcast Format

The server broadcasts a newline-separated message:

```
Line 0: Calculator name
Line 1: TCP port
Line 2: Secret code (authentication)
Line 3: Operating system
Line 4: Status
Line 5: (reserved)
Line 6+: Available codes (one per line)
```

**Example broadcast:**
```
MyCalculator
5555
secret123
Linux
available

R
Python
Modelica
shell
```

### Discovery in Python

#### Automatic Discovery

```python
import fz

# Using UDP discovery (port in URI)
results = fz.fzr(
    "input.txt",
    {"x": [1, 2, 3]},
    model,
    calculators="funz://:19001/R"  # Discovers TCP port automatically
)
```

#### Manual Discovery

```python
from fz.runners import discover_funz_servers

# Discover all servers on port 19001
servers = discover_funz_servers(udp_port=19001, timeout=5)

# Returns:
# [
#   {'host': '192.168.1.100', 'port': 5555, 'code': 'R', 'name': 'calc1'},
#   {'host': '192.168.1.101', 'port': 5555, 'code': 'Python', 'name': 'calc2'},
#   ...
# ]

# Use discovered servers
calculators = [f"funz://{s['host']}:{s['port']}/{s['code']}" for s in servers]
results = fz.fzr("input.txt", input_variables, model, calculators=calculators)
```

### Discovery Process

```
Client                          Server
  |                               |
  |  (1) Bind UDP port 19001      |
  |  (2) Listen for broadcast     |
  |                               |
  |  <----- UDP Broadcast -----   |  (Periodic, e.g., every 10s)
  |  (name=calc1, tcp=5555,       |
  |   codes=[R, Python])          |
  |                               |
  |  (3) Parse broadcast          |
  |  (4) Verify code "R" avail    |
  |  (5) Connect TCP port 5555 ----> |
  |                               |
```

### UDP Port Configuration

**Default Funz Port**: 19001 (commonly used)

**Custom Ports**:
```python
# Server 1 on port 19001
calculators = "funz://:19001/R"

# Server 2 on port 19002
calculators = "funz://:19002/Python"
```

### Timeout Handling

```python
# UDP discovery timeout: 10 seconds (hardcoded)
# If no broadcast received within 10s, discovery fails

# Example error:
# "Failed to discover calculator via UDP: timeout"
```

## TCP Protocol

### Connection Workflow

```
1. RESERVE    - Lock calculator for exclusive use
2. NEWCASE    - Create new calculation case
3. PUTFILE    - Upload input files (multiple files)
4. EXECUTE    - Run calculation
5. GETFILE    - Download results archive
6. UNRESERVE  - Release calculator
```

### Protocol Commands

#### 1. RESERVE

Lock calculator for exclusive use:

**Request:**
```
RESERVE
<code>
/
```

**Response:**
```
Y
<secret_code>
<calculator_name>
```

**Example:**
```python
# Client sends:
RESERVE
R
/

# Server responds:
Y
abc123secret
MyCalculator
```

#### 2. NEWCASE

Create a new calculation case:

**Request:**
```
NEWCASE
<secret_code>
<case_name>
<variable_count>
<variable1>=<value1>
<variable2>=<value2>
...
/
```

**Response:**
```
Y
<case_directory>
```

**Example:**
```python
# Client sends:
NEWCASE
abc123secret
case_001
2
USERNAME=john
TIMESTAMP=2024-01-30
/

# Server responds:
Y
/tmp/funz/case_001
```

#### 3. PUTFILE

Upload input files:

**Request:**
```
PUTFILE
<secret_code>
<filename>
<file_size_bytes>
<file_content_bytes>
/
```

**Response:**
```
Y
```

**Example:**
```python
# Client sends:
PUTFILE
abc123secret
input.txt
25
n_mol=1.0
T_celsius=25
/

# Server responds:
Y
```

#### 4. EXECUTE

Run the calculation:

**Request:**
```
EXECUTE
<secret_code>
/
```

**Response (periodic heartbeats):**
```
H    # Heartbeat - calculation still running
H
H
Y    # Success - calculation complete
<output_summary>
```

**Example:**
```python
# Client sends:
EXECUTE
abc123secret
/

# Server responds (periodic):
H
H
H
Y
Calculation completed successfully
```

#### 5. GETFILE (ARCHIVE)

Download results archive:

**Request:**
```
ARCHIVE
<secret_code>
/
```

**Response:**
```
Y
<archive_size_bytes>
<archive_content_bytes>
```

**Example:**
```python
# Client sends:
ARCHIVE
abc123secret
/

# Server responds:
Y
1024
<binary ZIP content>
```

#### 6. UNRESERVE

Release calculator:

**Request:**
```
UNRESERVE
<secret_code>
/
```

**Response:**
```
Y
```

### Response Codes

- `Y` - Success
- `N` - Failure (followed by error message)
- `E` - Error (followed by error message)
- `I` - Info (followed by information)
- `H` - Heartbeat (calculation in progress)
- `S` - Sync (synchronization message)

### Request Terminator

All requests end with `/` (forward slash) on its own line.

## Python Implementation

### Basic Usage

```python
import fz

model = {
    "varprefix": "$",
    "output": {
        "result": "cat output.txt"
    }
}

# Connect to Funz server
results = fz.fzr(
    "input.txt",
    {"temp": [100, 200, 300]},
    model,
    calculators="funz://:19001/R",
    results_dir="results"
)
```

### Error Handling

```python
try:
    results = fz.fzr(..., calculators="funz://:19001/R")
except Exception as e:
    if "UDP" in str(e):
        print("UDP discovery failed - check server is running")
    elif "RESERVE" in str(e):
        print("Calculator already reserved - try again later")
    elif "timeout" in str(e):
        print("Calculation timed out - increase timeout")
```

### Timeout Configuration

```python
# Model-level timeout
model = {
    "timeout": 3600,  # 1 hour
    "output": {"result": "cat output.txt"}
}

# Calculator-level timeout
calculators = "funz://:19001/R?timeout=7200"  # 2 hours

# Environment variable (default)
import os
os.environ['FZ_RUN_TIMEOUT'] = '3600'
```

### Multiple Servers

```python
# Parallel execution across multiple Funz servers
calculators = [
    "funz://server1.local:19001/R",
    "funz://server2.local:19001/R",
    "funz://server3.local:19001/R"
]

# FZ distributes cases across servers
results = fz.fzr(
    "input.txt",
    {"param": list(range(100))},  # 100 cases
    model,
    calculators=calculators  # ~33 cases per server
)
```

## Server Setup

### Java Funz Calculator Server

The FZ client is compatible with existing Java Funz calculator servers.

**Starting a server:**
```bash
java -jar funz-calculator.jar -port 5555 -udp 19001 -code R
```

**Parameters:**
- `-port`: TCP port for calculations
- `-udp`: UDP broadcast port for discovery
- `-code`: Calculator code (R, Python, shell, etc.)

### Python Mock Server (Testing)

For testing, use the mock server from tests:

```python
# tests/test_funz_protocol.py
from tests.test_funz_protocol import MockFunzServer

# Start mock server
server = MockFunzServer(tcp_port=5555, udp_port=19001, code="shell")
server.start()

try:
    # Run calculations
    results = fz.fzr(..., calculators="funz://:19001/shell")
finally:
    server.stop()
```

## Network Configuration

### Firewall Rules

**UDP Port** (for discovery):
```bash
# Allow incoming UDP on port 19001
ufw allow 19001/udp
```

**TCP Port** (for calculations):
```bash
# Allow incoming TCP on port 5555
ufw allow 5555/tcp
```

### Docker Deployment

```dockerfile
FROM java:11
COPY funz-calculator.jar /app/
EXPOSE 5555/tcp 19001/udp
CMD ["java", "-jar", "/app/funz-calculator.jar", "-port", "5555", "-udp", "19001"]
```

```bash
docker run -p 5555:5555/tcp -p 19001:19001/udp funz-calculator
```

## Troubleshooting

### UDP Discovery Fails

**Problem**: "Failed to discover calculator via UDP"

**Solutions:**
1. Check server is running and broadcasting
2. Verify firewall allows UDP port
3. Increase discovery timeout (hardcoded 10s)
4. Check UDP port is correct

**Debug:**
```bash
# Listen for UDP broadcasts
nc -u -l 19001

# Should see periodic broadcasts from server
```

### Calculator Always Reserved

**Problem**: "Calculator is already reserved"

**Solutions:**
1. Wait 60 seconds for automatic timeout
2. Restart calculator server
3. Check for hung processes

### Connection Timeout

**Problem**: TCP connection times out

**Solutions:**
1. Verify TCP port is accessible
2. Check firewall rules
3. Increase FZ_RUN_TIMEOUT
4. Check server logs

### Code Not Available

**Problem**: "Code 'X' not available on calculator"

**Solutions:**
1. Check UDP broadcast includes your code
2. Verify server supports the code
3. Check spelling of code name

## Advanced Usage

### Custom Discovery Function

```python
def discover_servers_on_network(base_port=19001, num_ports=10):
    """Discover all Funz servers on network."""
    from fz.runners import discover_funz_servers

    servers = []
    for port in range(base_port, base_port + num_ports):
        try:
            found = discover_funz_servers(udp_port=port, timeout=2)
            servers.extend(found)
        except:
            pass

    return servers

# Use in FZ
servers = discover_servers_on_network()
calculators = [f"funz://{s['host']}:{s['port']}/{s['code']}" for s in servers]
```

### Load Balancing

```python
from collections import defaultdict

def group_calculators_by_code(servers):
    """Group servers by calculator code."""
    by_code = defaultdict(list)
    for s in servers:
        by_code[s['code']].append(f"funz://{s['host']}:{s['port']}/{s['code']}")
    return dict(by_code)

servers = discover_funz_servers(udp_port=19001)
by_code = group_calculators_by_code(servers)

# Use all R servers
results = fz.fzr(..., calculators=by_code['R'])
```

### Health Checking

```python
def check_server_health(funz_uri, timeout=5):
    """Check if Funz server is responsive."""
    import socket

    try:
        # Try UDP discovery
        # (implementation details in fz/runners.py)
        return True
    except:
        return False

# Filter healthy servers
servers = discover_funz_servers(udp_port=19001)
healthy = [s for s in servers if check_server_health(f"funz://{s['host']}:{s['port']}/{s['code']}")]
```

## Protocol Sequence Diagram

```
Client                          Funz Server
  |                               |
  |  UDP Discovery                |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (TCP port: 5555)             |
  |                               |
  |  TCP Connect :5555            |
  |  ==========================>  |
  |                               |
  |  RESERVE "R"                  |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (secret: abc123)             |
  |                               |
  |  NEWCASE                      |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (case: /tmp/case_001)        |
  |                               |
  |  PUTFILE "input.txt"          |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (Y)                          |
  |                               |
  |  EXECUTE                      |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (H H H... Y)                 |
  |                               |
  |  ARCHIVE                      |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (results.zip)                |
  |                               |
  |  UNRESERVE                    |
  |  --------------------------->  |
  |  <---------------------------  |
  |  (Y)                          |
  |                               |
  |  TCP Close                    |
  |  ==========================>  |
  |                               |
```

## See Also

- **Funz protocol tests**: `tests/test_funz_protocol.py`
- **Integration tests**: `tests/test_funz_integration.py`
- **Calculator types**: `context/calculators.md`
- **Implementation**: `fz/runners.py` (run_funz_calculation function)
- **Java Funz**: https://github.com/Funz/funz-calculator
