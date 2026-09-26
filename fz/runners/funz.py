"""Funz server calculator (UDP discovery and TCP protocol)."""

import time
import socket
import getpass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable

from .base import Calculator
from ..logging import log_error, log_warning, log_info, log_debug
from .manager import resolve_timeout, get_environment_info


def _parse_funz_broadcast(data: bytes) -> Optional[Dict[str, Any]]:
    """
    Parse a Funz calculator UDP broadcast message.

    Format (newline-separated), per the actual Java source
    (org.funz.calculator.network.Host.buildPacket()):

        0: calculator name
        1: TCP port
        2: start timestamp ("since", unused here)
        3: operating system
        4: activity - "idle" if free (org.funz.Protocol.IDLE_STATE),
           "unavailable" or "already reserved ..." otherwise
        5: number of codes that follow
        6+: one calculator code per line

    Returns None if the message is too short/malformed to be a valid
    Funz broadcast.
    """
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        return None
    lines = text.strip("\r\n").split("\n")
    if len(lines) < 6:
        return None
    try:
        tcp_port = int(lines[1].strip())
    except ValueError:
        return None
    try:
        ncodes = int(lines[5].strip())
    except ValueError:
        return None
    codes = [line.strip() for line in lines[6 : 6 + ncodes] if line.strip()]
    activity = lines[4].strip()
    return {
        "name": lines[0].strip(),
        "tcp_port": tcp_port,
        "os": lines[3].strip(),
        "activity": activity,
        "idle": activity.lower().startswith("idle"),
        "codes": codes,
    }


def discover_funz_servers(
    udp_port: int,
    listen_duration: float = 10.0,
    stop_when: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> List[Dict[str, Any]]:
    """
    Discover Funz calculator servers broadcasting on a UDP port.

    Binds to `udp_port` and listens for up to `listen_duration` seconds,
    collecting every distinct calculator seen during that window (a
    calculator broadcasts periodically, e.g. every ~10s, so a single
    receive is not enough to reliably see all servers on the network).
    Servers are deduplicated by (host, tcp_port), keeping their most
    recent broadcast.

    Args:
        udp_port: UDP port to listen on for calculator broadcasts.
        listen_duration: how long to listen, in seconds. Should cover at
            least one full broadcast cycle (default 10s); increase it if
            calculators/the network broadcast more slowly.
        stop_when: optional predicate called with each newly discovered
            server dict; if it returns True, discovery returns immediately
            instead of waiting out the full window (e.g. to stop as soon
            as a server offering a specific code is found).

    Returns:
        List of dicts, one per distinct calculator server:
        {"host", "tcp_port", "name", "os", "activity", "idle", "codes"}.
        Raises OSError if the UDP port cannot be bound.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", udp_port))

    servers: Dict[Tuple[str, int], Dict[str, Any]] = {}
    deadline = time.monotonic() + listen_duration
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            parsed = _parse_funz_broadcast(data)
            if parsed is None:
                continue
            server = {**parsed, "host": addr[0]}
            key = (addr[0], parsed["tcp_port"])
            servers[key] = server
            if stop_when is not None and stop_when(server):
                break
    finally:
        sock.close()
    return list(servers.values())


def run_funz_calculation(
    working_dir: Path,
    funz_uri: str,
    model: Dict,
    timeout: int = None,
    input_files_list: List[str] = None,
    static_entries: List[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Run calculation via Funz server protocol

    Args:
        working_dir: Directory containing input files
        funz_uri: Funz URI (e.g., "funz://:<port>/<code>")
        model: Model definition dict
        timeout: Timeout in seconds (None resolves via model["timeout"], then FZ_RUN_TIMEOUT config default, 3600)
        input_files_list: List of input file names in order (from .fz_hash)
        static_entries: Pre-resolved input_static entries; relative ones are
            explicitly uploaded (they live outside working_dir - only symlinked there
            for local execution), absolute ones are assumed already present server-side

    Returns:
        Dict containing calculation results and status
    """
    # Resolve effective timeout: explicit arg > model's "timeout" entry > config default
    timeout = resolve_timeout(model, timeout)
    # Import here to avoid circular imports
    from ..core import is_interrupted, fzo

    # Check for interrupt before starting
    if is_interrupted():
        return {
            "status": "interrupted",
            "error": "Execution interrupted by user",
            "command": funz_uri,
        }

    start_time = datetime.now()
    env_info = get_environment_info()

    # Funz protocol constants (per org.funz.Protocol in Java source)
    METHOD_RESERVE = "RESERVE"
    METHOD_UNRESERVE = "UNRESERVE"
    METHOD_PUT_FILE = "PUTFILE"
    METHOD_NEW_CASE = "NEWCASE"
    METHOD_EXECUTE = "EXECUTE"
    METHOD_ARCH_RES = "ARCHIVE"
    METHOD_GET_ARCH = "GETFILE"
    METHOD_INTERRUPT = "INTERUPT"  # Note: typo in original Java code

    RET_YES = "Y"
    RET_NO = "N"
    RET_ERROR = "E"
    RET_INFO = "I"
    RET_HEARTBEAT = "H"
    RET_SYNC = "S"

    END_OF_REQ = "/"
    ARCHIVE_FILE = "results.zip"

    try:
        # Parse Funz URI: funz://:<port>/<code>
        # Format: funz://[host]:<port>/<code>
        log_debug(f"Parsing Funz URI: {funz_uri}")

        if not funz_uri.startswith("funz://"):
            return {"status": "error", "error": "Invalid Funz URI format"}

        uri_part = funz_uri[7:]  # Remove "funz://"
        log_debug(f"URI part after 'funz://': {uri_part}")

        # Parse host:port/code
        if "/" not in uri_part:
            return {"status": "error", "error": "Funz URI must specify code: funz://:<port>/<code>"}

        connection_part, code = uri_part.split("/", 1)
        log_debug(f"Connection part: {connection_part}, Code: {code}")

        # Parse host and UDP port
        host = "localhost"  # Default to localhost
        udp_port = 0

        if ":" in connection_part:
            # host:port format
            if connection_part.startswith(":"):
                # :port format (no host)
                port_str = connection_part[1:]
                try:
                    udp_port = int(port_str)
                    log_debug(f"Parsed UDP port (localhost): {udp_port}")
                except ValueError:
                    return {"status": "error", "error": f"Invalid port number: {port_str}"}
            else:
                # host:port format
                host, port_str = connection_part.rsplit(":", 1)
                try:
                    udp_port = int(port_str)
                    log_debug(f"Parsed host:UDP port: {host}:{udp_port}")
                except ValueError:
                    return {"status": "error", "error": f"Invalid port number: {port_str}"}
        else:
            return {"status": "error", "error": "Funz URI must specify UDP port: funz://:<port>/<code>"}

        if not code:
            return {"status": "error", "error": "Funz URI must specify code"}

        log_info(f"📡 Discovering Funz calculator via UDP broadcast on port {udp_port}...")
        log_info(f"🔧 Code: {code}")
        log_debug(f"Working directory: {working_dir}")
        log_debug(f"Timeout: {timeout}s")

        # Discover TCP port via UDP broadcast
        try:
            log_debug(f"Listening for Funz calculator broadcasts on UDP port {udp_port}")
            servers = discover_funz_servers(
                udp_port,
                listen_duration=10,
                stop_when=lambda s: s["idle"] and code in s["codes"],
            )
            log_debug(f"Discovered servers: {servers}")

            if not servers:
                log_error(f"❌ UDP discovery timeout - no calculator found on port {udp_port}")
                return {"status": "error", "error": f"No calculator found on UDP port {udp_port}"}

            # Prefer a server that is idle and offers the requested code, then
            # any server offering the code, then fall back to the first one seen.
            server = next(
                (s for s in servers if s["idle"] and code in s["codes"]),
                next(
                    (s for s in servers if code in s["codes"]),
                    servers[0],
                ),
            )

            tcp_port = server["tcp_port"]
            calculator_name = server["name"]
            available_codes = server["codes"]

            log_info(f"✅ Discovered calculator '{calculator_name}' at {host}:{tcp_port}")
            log_debug(f"Available codes: {available_codes}, activity: {server['activity']}")

            # Verify requested code is available
            if code not in available_codes:
                log_warning(f"⚠️  Requested code '{code}' not in available codes: {available_codes}")

        except OSError as e:
            log_error(f"❌ UDP discovery failed: {e}")
            return {"status": "error", "error": f"UDP discovery failed: {str(e)}"}

        # Create TCP socket connection to discovered port
        log_debug(f"Creating TCP socket connection to {host}:{tcp_port}")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        connection_timeout = 30 if timeout is None else min(timeout, 30)
        sock.settimeout(connection_timeout)
        log_debug(f"Socket timeout set to {connection_timeout}s")

        try:
            log_debug(f"Attempting TCP connection to {host}:{tcp_port}...")
            sock.connect((host, tcp_port))
            log_info(f"✅ Connected to Funz server at {host}:{tcp_port}")
            log_debug(f"Socket state: connected, local={sock.getsockname()}, remote={sock.getpeername()}")

            # Create buffered reader/writer
            sock_file = sock.makefile('rw', buffering=1, encoding='utf-8', newline='\n')
            log_debug("Socket file created with UTF-8 encoding and line buffering")

            def send_message(*lines):
                """Send a protocol message"""
                log_debug(f"→ Sending message: {lines}")
                for line in lines:
                    sock_file.write(str(line) + '\n')
                sock_file.write(END_OF_REQ + '\n')
                sock_file.flush()
                log_debug(f"→ Message sent and flushed")

            def read_response():
                """Read a protocol response until END_OF_REQ

                Returns:
                    Tuple of (status, response_lines) where:
                    - status is the first line (RET_YES, RET_NO, RET_ERROR, etc.) or None on timeout/error
                    - response_lines is the full response including status line
                """
                response = []
                line_count = 0

                # Set socket timeout for reading
                original_timeout = sock.gettimeout()
                sock.settimeout(timeout)

                try:
                    while True:
                        try:
                            line = sock_file.readline().strip()
                        except socket.timeout:
                            log_error(f"❌ Timeout waiting for response after {timeout}s")
                            sock.settimeout(original_timeout)
                            return "TIMEOUT", []

                        line_count += 1
                        log_debug(f"← Received line {line_count}: '{line}'")

                        if not line:
                            # Connection closed
                            log_warning(f"⚠️  Connection closed by server (empty line received)")
                            sock.settimeout(original_timeout)
                            return None, []

                        if line == END_OF_REQ:
                            log_debug(f"← End of response marker received (total {line_count} lines)")
                            break

                        # Handle special responses
                        if line == RET_HEARTBEAT:
                            log_debug("← Heartbeat received, ignoring")
                            continue  # Ignore heartbeats

                        if line == RET_INFO:
                            # Info message - read next line
                            info_line = sock_file.readline().strip()
                            log_info(f"ℹ️  Funz info: {info_line}")
                            continue

                        response.append(line)

                    if not response:
                        log_debug("← Empty response received")
                        sock.settimeout(original_timeout)
                        return None, []

                    log_debug(f"← Response parsed: status={response[0]}, lines={len(response)}")
                    sock.settimeout(original_timeout)
                    return response[0], response

                except Exception as e:
                    log_error(f"❌ Error reading response: {e}")
                    sock.settimeout(original_timeout)
                    return "ERROR", []

            # Step 1: Reserve calculator (two-phase protocol)
            log_info("🔒 Step 1: Reserving calculator...")

            # Phase 1: Send RESERVE command
            log_debug(f"Sending {METHOD_RESERVE} request (phase 1)")
            send_message(METHOD_RESERVE)
            ret, response = read_response()

            # Check for errors/timeout
            if ret == "TIMEOUT":
                log_error(f"❌ Reservation timed out")
                return {"status": "timeout", "error": "Calculator reservation timed out"}
            elif ret == "ERROR":
                log_error(f"❌ Error during reservation")
                return {"status": "error", "error": "Error during calculator reservation"}
            elif ret != RET_YES:
                error_msg = response[1] if len(response) > 1 else "Unknown error"
                log_error(f"❌ Calculator reservation failed: {error_msg}")
                log_debug(f"Full response: {response}")
                return {"status": "error", "error": f"Failed to reserve calculator: {error_msg}"}

            log_debug(f"✅ Phase 1 complete")

            # Phase 2: Send project code and tagged values
            tagged_values = {
                "USERNAME": getpass.getuser()
            }

            log_debug(f"Sending project code '{code}' and tagged values (phase 2)")
            # Send code
            sock_file.write(code + '\n')
            # Send number of tagged values
            sock_file.write(str(len(tagged_values)) + '\n')
            # Send each tagged value
            for key, value in tagged_values.items():
                sock_file.write(key + '\n')
                sock_file.write(str(value) + '\n')
            sock_file.flush()

            # Read phase 2 response
            ret, response = read_response()

            if ret == "TIMEOUT":
                log_error(f"❌ Reservation phase 2 timed out")
                return {"status": "timeout", "error": "Calculator reservation phase 2 timed out"}
            elif ret != RET_YES:
                error_msg = response[1] if len(response) > 1 else "Unknown error"
                log_error(f"❌ Calculator reservation phase 2 failed: {error_msg}")
                return {"status": "error", "error": f"Failed to reserve calculator (phase 2): {error_msg}"}

            # Get secret code from response (for authentication)
            # Response contains: [RET_YES, secret, ip, security]
            secret_code = response[1] if len(response) > 1 else None
            log_info(f"✅ Calculator reserved successfully")
            log_debug(f"Secret code: {secret_code}")

            try:
                # Step 2: Create new case (MUST come before uploading files!)
                # The Funz protocol requires NEW_CASE before PUT_FILE
                log_info("📝 Step 2: Creating new case...")

                # Prepare variables (must include USERNAME)
                variables = {
                    "USERNAME": getpass.getuser()
                }

                log_debug(f"Sending {METHOD_NEW_CASE} request with variables: {variables}")
                send_message(METHOD_NEW_CASE)

                # Send variable count
                sock_file.write(str(len(variables)) + '\n')

                # Send each variable
                for key, value in variables.items():
                    # Truncate multi-line values to first line
                    value_str = str(value).split('\n')[0]
                    if '\n' in str(value):
                        value_str += "..."

                    sock_file.write(key + '\n')
                    sock_file.write(value_str + '\n')

                sock_file.flush()

                # Read response
                ret, case_response = read_response()

                if ret == "TIMEOUT":
                    log_error(f"❌ New case creation timed out")
                    return {"status": "timeout", "error": "New case creation timed out"}
                elif ret != RET_YES:
                    error_msg = case_response[1] if len(case_response) > 1 else "Unknown error"
                    log_error(f"❌ Failed to create new case: {error_msg}")
                    return {"status": "error", "error": f"Failed to create new case: {error_msg}"}

                log_info(f"✅ Case created successfully")

                # Step 3: Upload input files (after NEW_CASE)
                log_info("📤 Step 3: Uploading input files...")
                # (relative_path, real_path) pairs: files physically in working_dir,
                # plus relative static_files entries (uploaded from their real source
                # path, since they live outside working_dir - only symlinked there
                # for local execution). Absolute static_files are assumed already
                # present server-side and are not uploaded.
                files_to_upload = [(item.name, item) for item in working_dir.iterdir() if item.is_file()]
                files_to_upload += [
                    (e["name"], e["source"]) for e in (static_entries or []) if not e["is_absolute"]
                ]
                log_debug(f"Found {len(files_to_upload)} files to upload")

                uploaded_count = 0
                for relative_path, real_path in files_to_upload:
                    # Send PUT_FILE request
                    file_size = real_path.stat().st_size

                    log_info(f"  📄 Uploading {relative_path} ({file_size} bytes)")
                    log_debug(f"Sending {METHOD_PUT_FILE} request for {relative_path}")
                    send_message(METHOD_PUT_FILE, relative_path, file_size)

                    # Wait for acknowledgment
                    ret, ack_response = read_response()
                    if ret != RET_YES:
                        log_warning(f"❌ Failed to upload {relative_path}: {ack_response}")
                        continue

                    log_debug(f"Server ready to receive {relative_path}")

                    # Send file content
                    with open(real_path, 'rb') as f:
                        file_data = f.read()
                        bytes_sent = sock.sendall(file_data)
                        log_debug(f"Sent {len(file_data)} bytes of file data")

                    uploaded_count += 1
                    log_debug(f"✅ Successfully uploaded {relative_path}")

                log_info(f"✅ Uploaded {uploaded_count}/{len(files_to_upload)} files")

                # Step 4: Execute calculation
                log_info(f"⚙️  Step 4: Executing calculation...")
                log_info(f"  Code: {code}")
                log_debug(f"Sending {METHOD_EXECUTE} request")
                send_message(METHOD_EXECUTE, code)

                # Read execution response (may include INFO messages)
                execution_start = datetime.now()
                log_debug(f"Execution started at {execution_start.isoformat()}")
                ret, response = read_response()

                # Check for interrupt during execution
                if is_interrupted():
                    log_warning("⚠️  Interrupt detected, sending interrupt to Funz server...")
                    send_message(METHOD_INTERRUPT, secret_code if secret_code else "")
                    raise KeyboardInterrupt("Execution interrupted by user")

                if ret == "TIMEOUT":
                    log_error(f"❌ Execution timed out after {timeout}s")
                    return {"status": "timeout", "error": f"Execution timed out after {timeout}s"}
                elif ret == "ERROR":
                    log_error(f"❌ Error during execution")
                    return {"status": "error", "error": "Error during execution"}
                elif ret != RET_YES:
                    error_msg = response[1] if len(response) > 1 else "Execution failed"
                    log_error(f"❌ Execution failed: {error_msg}")
                    log_debug(f"Full response: {response}")
                    return {"status": "failed", "error": error_msg}

                execution_end = datetime.now()
                execution_time = (execution_end - execution_start).total_seconds()

                log_info(f"✅ Execution completed in {execution_time:.2f}s")
                log_debug(f"Execution ended at {execution_end.isoformat()}")

                # Step 5: Archive results (required before GET_ARCH)
                log_info("📦 Step 5: Archiving results...")
                log_debug(f"Sending {METHOD_ARCH_RES} request")
                send_message(METHOD_ARCH_RES)
                ret, arch_response = read_response()

                if ret != RET_YES:
                    log_error(f"❌ Failed to archive results: {arch_response}")
                    return {"status": "error", "error": "Failed to archive results"}

                log_info(f"✅ Results archived successfully")

                # Step 6: Download results archive
                log_info("📥 Step 6: Downloading results...")
                log_debug(f"Sending {METHOD_GET_ARCH} request")
                send_message(METHOD_GET_ARCH)

                # Read response (should be Y\n/\n, possibly with INFO messages)
                ret, response = read_response()

                if ret == "TIMEOUT":
                    log_error(f"❌ Archive download timed out")
                    return {"status": "timeout", "error": "Archive download timed out"}
                elif ret != RET_YES:
                    error_msg = response[1] if len(response) > 1 else "Unknown error"
                    log_error(f"❌ Failed to get results archive: {error_msg}")
                    return {"status": "error", "error": f"Failed to get results archive: {error_msg}"}

                # Read lines until we find one that's all digits (the size)
                # Skip any additional protocol responses (Y, /, INFO lines, etc.)
                # This is necessary because transferArchive sends multiple Y\n/\n responses
                max_lines = 50
                archive_size = None

                try:
                    for i in range(max_lines):
                        line = sock_file.readline().strip()
                        log_debug(f"Reading size line {i}: '{line}'")

                        if not line:
                            log_error(f"❌ Connection closed while reading archive size")
                            return {"status": "error", "error": "Connection closed while reading archive size"}

                        if line.isdigit():
                            archive_size = int(line)
                            log_info(f"  Archive size: {archive_size} bytes ({archive_size/1024:.2f} KB)")
                            break
                except socket.timeout:
                    log_error(f"❌ Timeout while reading archive size")
                    return {"status": "timeout", "error": "Timeout while reading archive size"}

                if archive_size is None:
                    log_error(f"❌ Could not find archive size in {max_lines} lines")
                    return {"status": "error", "error": "Could not determine archive size"}

                # Send acknowledgment (just a line, per Java: _reader.readLine())
                log_debug(f"Sending ACK for archive transfer")
                sock_file.write("ACK\n")
                sock_file.flush()

                # Receive archive data
                archive_data = b""
                bytes_received = 0
                chunk_count = 0

                log_debug(f"Receiving archive data in chunks...")
                while bytes_received < archive_size:
                    chunk_size = min(4096, archive_size - bytes_received)
                    chunk = sock.recv(chunk_size)
                    if not chunk:
                        log_warning(f"⚠️  Connection closed before all data received ({bytes_received}/{archive_size} bytes)")
                        break
                    archive_data += chunk
                    bytes_received += len(chunk)
                    chunk_count += 1

                    # Log progress every 100 chunks or at the end
                    if chunk_count % 100 == 0 or bytes_received >= archive_size:
                        progress = (bytes_received / archive_size * 100) if archive_size > 0 else 100
                        log_debug(f"Download progress: {bytes_received}/{archive_size} bytes ({progress:.1f}%)")

                log_info(f"✅ Downloaded {bytes_received} bytes in {chunk_count} chunks")

                # Extract archive to working directory
                if archive_data:
                    import zipfile
                    import io

                    log_debug(f"Extracting ZIP archive ({len(archive_data)} bytes)")
                    try:
                        with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
                            file_list = zf.namelist()
                            log_debug(f"Archive contains {len(file_list)} files: {file_list}")
                            zf.extractall(working_dir)
                            log_info(f"✅ Extracted {len(file_list)} files to {working_dir}")
                    except Exception as e:
                        log_error(f"❌ Failed to extract archive: {e}")
                        log_debug(f"Archive data (first 100 bytes): {archive_data[:100]}")
                else:
                    log_warning("⚠️  No archive data received")

                # Create log file
                end_time = datetime.now()
                total_time = (end_time - start_time).total_seconds()

                log_file_path = working_dir / "log.txt"
                with open(log_file_path, "w") as log_file:
                    log_file.write(f"Calculator: funz://{host}:{tcp_port}/{code}\n")
                    log_file.write(f"Exit code: 0\n")
                    log_file.write(f"Time start: {start_time.isoformat()}\n")
                    log_file.write(f"Time end: {end_time.isoformat()}\n")
                    log_file.write(f"Execution time: {execution_time:.3f} seconds\n")
                    log_file.write(f"Total time: {total_time:.3f} seconds\n")
                    log_file.write(f"User: {env_info['user']}\n")
                    log_file.write(f"Hostname: {env_info['hostname']}\n")
                    log_file.write(f"Funz server: {host}:{tcp_port}\n")
                    log_file.write(f"Timestamp: {time.ctime()}\n")

                # Parse output using fzo
                try:
                    output_results = fzo(working_dir, model)

                    # Convert DataFrame to dict if needed
                    if hasattr(output_results, "to_dict"):
                        output_dict = output_results.iloc[0].to_dict()
                    else:
                        output_dict = output_results

                    output_dict["status"] = "done"
                    output_dict["calculator"] = f"funz://{host}:{tcp_port}"
                    output_dict["command"] = code

                    return output_dict

                except Exception as e:
                    log_warning(f"Could not parse output: {e}")
                    return {
                        "status": "done",
                        "calculator": f"funz://{host}:{tcp_port}",
                        "command": code,
                        "error": f"Output parsing failed: {str(e)}"
                    }

            finally:
                # Step 6: Unreserve calculator
                log_info("Unreserving calculator...")
                try:
                    send_message(METHOD_UNRESERVE, secret_code if secret_code else "")
                    read_response()  # Ignore response
                except Exception as e:
                    log_warning(f"Failed to unreserve: {e}")

        finally:
            try:
                sock_file.close()
            except:
                pass

            try:
                sock.close()
            except:
                pass

    except KeyboardInterrupt:
        return {
            "status": "interrupted",
            "error": "Funz calculation interrupted by user",
            "command": code if 'code' in locals() else funz_uri,
        }

    except socket.timeout:
        return {
            "status": "timeout",
            "error": f"Connection timed out after {timeout} seconds",
            "command": code if 'code' in locals() else funz_uri,
        }

    except Exception as e:
        import traceback
        log_error(f"Funz calculation failed: {e}")
        log_debug(traceback.format_exc())
        return {
            "status": "error",
            "error": f"Funz calculation failed: {str(e)}",
            "command": code if 'code' in locals() else funz_uri,
        }


class FunzCalculator(Calculator):
    scheme = "funz"

    def run(self, working_dir, calculator_uri, model, timeout=None,
            original_input_was_dir=False, original_cwd=None,
            input_files_list=None, static_entries=None):
        return run_funz_calculation(
            working_dir, calculator_uri, model, timeout, input_files_list,
            static_entries=static_entries,
        )
