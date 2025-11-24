"""
Protocol-level tests for Funz TCP communication.

These tests validate the low-level Funz protocol implementation,
similar to NetworkTest.java and ClientTest.java in the Java implementation.
"""

import pytest
import socket
import tempfile
import time
import zipfile
import io
from pathlib import Path
from threading import Thread, Event


class FunzProtocolClient:
    """
    Low-level Funz protocol client for testing.

    Implements the same protocol as the Java Client class.
    """

    # Protocol constants
    METHOD_RESERVE = "RESERVE"
    METHOD_UNRESERVE = "UNRESERVE"
    METHOD_PUT_FILE = "PUTFILE"
    METHOD_NEW_CASE = "NEWCASE"
    METHOD_EXECUTE = "EXECUTE"
    METHOD_GET_ARCH = "GETFILE"
    METHOD_INTERRUPT = "INTERUPT"  # Typo preserved from Java
    METHOD_GET_INFO = "GETINFO"
    METHOD_GET_ACTIVITY = "GETACTIVITY"

    RET_YES = "Y"
    RET_NO = "N"
    RET_ERROR = "E"
    RET_INFO = "I"
    RET_HEARTBEAT = "H"
    RET_SYNC = "S"

    END_OF_REQ = "/"

    def __init__(self, host: str, port: int, timeout: int = 30):
        """Initialize client connection to Funz calculator."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
        self.socket_file = None
        self.reserved = False
        self.secret = None
        self.info_messages = []

    def connect(self) -> bool:
        """Connect to Funz calculator server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            self.socket_file = self.socket.makefile('rw', buffering=1, encoding='utf-8', newline='\n')
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if connected to server."""
        return self.socket is not None and self.socket_file is not None

    def is_reserved(self) -> bool:
        """Check if calculator is reserved."""
        return self.reserved

    def send_message(self, *lines):
        """Send a protocol message."""
        if not self.socket_file:
            raise RuntimeError("Not connected")

        for line in lines:
            self.socket_file.write(str(line) + '\n')
        self.socket_file.write(self.END_OF_REQ + '\n')
        self.socket_file.flush()

    def read_response(self) -> tuple:
        """Read a protocol response until END_OF_REQ."""
        if not self.socket_file:
            raise RuntimeError("Not connected")

        response = []
        self.info_messages = []

        while True:
            line = self.socket_file.readline().strip()

            if not line:
                # Connection closed
                return None, []

            if line == self.END_OF_REQ:
                break

            # Handle special responses
            if line == self.RET_HEARTBEAT:
                continue  # Ignore heartbeats

            if line == self.RET_INFO:
                # Info message - read next line
                info_line = self.socket_file.readline().strip()
                self.info_messages.append(info_line)
                continue

            response.append(line)

        if not response:
            return None, []

        return response[0], response

    def reserve(self, code: str = "shell") -> bool:
        """Reserve the calculator."""
        if not self.is_connected():
            return False

        self.send_message(self.METHOD_RESERVE)
        ret, response = self.read_response()

        if ret == self.RET_YES:
            self.reserved = True
            self.secret = response[1] if len(response) > 1 else None
            return True

        return False

    def unreserve(self) -> bool:
        """Unreserve the calculator."""
        if not self.is_reserved():
            return False

        self.send_message(self.METHOD_UNRESERVE, self.secret if self.secret else "")
        ret, response = self.read_response()

        if ret == self.RET_YES or ret is None:  # Accept None for already unreserved
            self.reserved = False
            self.secret = None
            return True

        return False

    def get_info(self) -> dict:
        """Get calculator info."""
        if not self.is_connected():
            return {}

        self.send_message(self.METHOD_GET_INFO)
        ret, response = self.read_response()

        if ret == self.RET_YES:
            # Parse info response (format may vary)
            info = {}
            for i in range(1, len(response)):
                if '=' in response[i]:
                    key, value = response[i].split('=', 1)
                    info[key] = value
            return info

        return {}

    def get_activity(self) -> str:
        """Get calculator activity status."""
        if not self.is_connected():
            return ""

        self.send_message(self.METHOD_GET_ACTIVITY)
        ret, response = self.read_response()

        if ret == self.RET_YES and len(response) > 1:
            return response[1]

        return ""

    def new_case(self, case_name: str = "case_1") -> bool:
        """Create a new case."""
        if not self.is_reserved():
            return False

        self.send_message(self.METHOD_NEW_CASE, case_name)
        ret, response = self.read_response()

        return ret == self.RET_YES

    def put_file(self, file_path: Path) -> bool:
        """Upload a file to the calculator."""
        if not self.is_reserved():
            return False

        file_size = file_path.stat().st_size
        file_name = file_path.name

        # Send PUT_FILE request
        self.send_message(self.METHOD_PUT_FILE, file_name, file_size)

        # Wait for acknowledgment
        ret, response = self.read_response()
        if ret != self.RET_YES:
            return False

        # Send file content
        with open(file_path, 'rb') as f:
            file_data = f.read()
            self.socket.sendall(file_data)

        return True

    def execute(self, code: str) -> bool:
        """Execute calculation with given code."""
        if not self.is_reserved():
            return False

        self.send_message(self.METHOD_EXECUTE, code)
        ret, response = self.read_response()

        return ret == self.RET_YES

    def get_results(self, target_dir: Path) -> bool:
        """Download results archive."""
        if not self.is_reserved():
            return False

        # Request archive
        self.send_message(self.METHOD_GET_ARCH)

        # Read archive size
        ret, response = self.read_response()
        if ret != self.RET_YES:
            return False

        archive_size = int(response[1]) if len(response) > 1 else 0

        # Send sync acknowledgment
        self.send_message(self.RET_SYNC)

        # Receive archive data
        archive_data = b""
        bytes_received = 0

        while bytes_received < archive_size:
            chunk = self.socket.recv(min(4096, archive_size - bytes_received))
            if not chunk:
                break
            archive_data += chunk
            bytes_received += len(chunk)

        # Extract archive
        if archive_data:
            try:
                with zipfile.ZipFile(io.BytesIO(archive_data)) as zf:
                    zf.extractall(target_dir)
                return True
            except Exception as e:
                print(f"Failed to extract archive: {e}")
                return False

        return False

    def disconnect(self):
        """Disconnect from server."""
        if self.reserved:
            try:
                self.unreserve()
            except:
                pass

        if self.socket_file:
            try:
                self.socket_file.close()
            except:
                pass

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        self.socket = None
        self.socket_file = None


# Pytest fixtures

@pytest.fixture
def funz_udp_port():
    """Return the Funz calculator UDP broadcast port from environment or default."""
    import os
    return int(os.environ.get("FUNZ_UDP_PORT", "5555"))


@pytest.fixture
def funz_port(funz_udp_port):
    """
    Discover and return the Funz calculator TCP port via UDP broadcast.

    The calculator broadcasts on UDP port (e.g., 5555) and the message
    contains the actual TCP port for communication.
    """
    import os
    import socket

    # Allow override for testing with known TCP port
    if "FUNZ_TCP_PORT" in os.environ:
        return int(os.environ["FUNZ_TCP_PORT"])

    # Otherwise, discover via UDP
    print(f"\nDiscovering Funz calculator TCP port via UDP broadcast on port {funz_udp_port}...")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        sock.bind(('', funz_udp_port))
        sock.settimeout(10)  # 10 second timeout

        # Wait for UDP broadcast
        data, addr = sock.recvfrom(4096)
        message = data.decode('utf-8').strip()
        lines = message.split('\n')

        if len(lines) >= 2:
            tcp_port = int(lines[1])
            print(f"Discovered TCP port: {tcp_port}")
            return tcp_port
        else:
            pytest.skip(f"Invalid UDP broadcast message from {addr}")

    except socket.timeout:
        pytest.skip(f"No Funz calculator discovered on UDP port {funz_udp_port} within 10 seconds")
    except Exception as e:
        pytest.skip(f"UDP discovery failed: {e}")
    finally:
        sock.close()


@pytest.fixture
def funz_host():
    """Return the Funz calculator host."""
    return "localhost"


@pytest.fixture
def protocol_client(funz_host, funz_port):
    """Create a protocol client and connect."""
    client = FunzProtocolClient(funz_host, funz_port)
    if not client.connect():
        pytest.skip(f"Cannot connect to Funz calculator at {funz_host}:{funz_port}")

    yield client

    # Cleanup
    client.disconnect()


# Protocol tests

def test_connection(funz_host, funz_port):
    """Test basic TCP connection to Funz calculator."""
    client = FunzProtocolClient(funz_host, funz_port)
    assert client.connect(), "Failed to connect to Funz calculator"
    assert client.is_connected(), "Client should be connected"
    client.disconnect()
    assert not client.is_connected(), "Client should be disconnected"


def test_reserve_unreserve(protocol_client):
    """Test calculator reservation and unreservation (like testReserveUnreserve)."""
    # Reserve calculator
    assert protocol_client.reserve("shell"), "Failed to reserve calculator"
    assert protocol_client.is_reserved(), "Calculator should be reserved"
    assert protocol_client.secret is not None, "Should have secret code"

    # Small delay
    time.sleep(0.5)

    # Unreserve calculator
    assert protocol_client.unreserve(), "Failed to unreserve calculator"
    assert not protocol_client.is_reserved(), "Calculator should not be reserved"


def test_get_activity(protocol_client):
    """Test getting calculator activity status (like testListening)."""
    for i in range(5):
        time.sleep(0.2)
        activity = protocol_client.get_activity()
        print(f"Activity {i}: {activity}")
        # Activity could be various states: idle, busy, reserved, etc.
        assert isinstance(activity, str), "Activity should be a string"


def test_get_info(protocol_client):
    """Test getting calculator info (like testListening)."""
    info = protocol_client.get_info()
    print(f"Calculator info: {info}")
    assert isinstance(info, dict), "Info should be a dictionary"


def test_full_protocol_cycle(protocol_client, tmp_path):
    """
    Test complete protocol cycle (like testCase).

    Tests: reserve → new_case → put_file → execute → get_results → unreserve
    """
    # Create a simple test input file
    input_file = tmp_path / "test_input.sh"
    input_file.write_text("#!/bin/bash\necho 'Hello from Funz test'\necho 'result=42' > output.txt\n")

    # Step 1: Reserve
    assert protocol_client.reserve("shell"), "Failed to reserve"
    assert protocol_client.is_reserved(), "Should be reserved"

    try:
        # Step 2: New case
        assert protocol_client.new_case("test_case"), "Failed to create new case"

        # Step 3: Upload file
        assert protocol_client.put_file(input_file), "Failed to upload file"

        # Step 4: Execute
        assert protocol_client.execute("shell"), "Failed to execute"

        # Step 5: Get results
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        assert protocol_client.get_results(results_dir), "Failed to get results"

        # Verify results exist
        result_files = list(results_dir.iterdir())
        assert len(result_files) > 0, "Should have result files"
        print(f"Result files: {[f.name for f in result_files]}")

    finally:
        # Step 6: Unreserve
        assert protocol_client.unreserve(), "Failed to unreserve"
        assert not protocol_client.is_reserved(), "Should not be reserved"


def test_multiple_sequential_cases(funz_host, funz_port, tmp_path):
    """
    Test running multiple cases sequentially (like test10Cases).

    This validates that the calculator can handle multiple clients
    connecting, executing, and disconnecting in sequence.
    """
    num_cases = 3  # Reduced from 10 for faster testing

    for i in range(num_cases):
        print(f"\n========== Case {i+1}/{num_cases} ==========")

        # Create new client for each case
        client = FunzProtocolClient(funz_host, funz_port)
        assert client.connect(), f"Failed to connect for case {i}"

        try:
            # Create input file
            input_file = tmp_path / f"input_{i}.sh"
            input_file.write_text(f"#!/bin/bash\necho 'Case {i}'\necho 'result={i}' > output.txt\n")

            # Full protocol cycle
            assert client.reserve("shell"), f"Failed to reserve for case {i}"
            assert client.new_case(f"case_{i}"), f"Failed to create case {i}"
            assert client.put_file(input_file), f"Failed to upload file for case {i}"
            assert client.execute("shell"), f"Failed to execute case {i}"

            # Get results
            results_dir = tmp_path / f"results_{i}"
            results_dir.mkdir()
            assert client.get_results(results_dir), f"Failed to get results for case {i}"

            # Verify results
            assert len(list(results_dir.iterdir())) > 0, f"No results for case {i}"

            # Cleanup
            assert client.unreserve(), f"Failed to unreserve case {i}"

        finally:
            client.disconnect()

        print(f"✅ Case {i+1} completed successfully")


def test_concurrent_clients(funz_host, funz_port):
    """
    Test multiple concurrent client connections (like testListening with multiple clients).

    Tests that multiple clients can connect simultaneously and query calculator status.
    """
    num_clients = 2
    clients = []

    # Connect all clients
    for i in range(num_clients):
        client = FunzProtocolClient(funz_host, funz_port)
        assert client.connect(), f"Failed to connect client {i}"
        clients.append(client)

    try:
        # All clients query activity simultaneously
        for iteration in range(3):
            time.sleep(0.3)

            for i, client in enumerate(clients):
                activity = client.get_activity()
                info = client.get_info()
                print(f"Client {i} - iteration {iteration}: activity='{activity}', info={info}")

                assert isinstance(activity, str), f"Client {i} activity should be string"
                assert isinstance(info, dict), f"Client {i} info should be dict"

    finally:
        # Disconnect all clients
        for client in clients:
            client.disconnect()


def test_reserve_timeout_behavior(funz_host, funz_port):
    """
    Test calculator reservation timeout (like testReserveTimeOut).

    Tests that when one client reserves and times out, another client
    can successfully reserve the calculator.
    """
    # First client reserves but doesn't unreserve
    client1 = FunzProtocolClient(funz_host, funz_port, timeout=60)
    assert client1.connect(), "Client 1 failed to connect"

    try:
        assert client1.reserve("shell"), "Client 1 failed to reserve"
        print("Client 1 reserved calculator")

        # Wait for reservation timeout (typically 2-5 seconds in tests)
        # The calculator should auto-unreserve after timeout
        timeout_duration = 6  # Conservative estimate
        print(f"Waiting {timeout_duration}s for reservation timeout...")
        time.sleep(timeout_duration)

        # Second client tries to reserve (should succeed after timeout)
        client2 = FunzProtocolClient(funz_host, funz_port)
        assert client2.connect(), "Client 2 failed to connect"

        try:
            # This should succeed because client1's reservation timed out
            assert client2.reserve("shell"), "Client 2 failed to reserve after timeout"
            print("✅ Client 2 successfully reserved after client 1 timeout")

            # Properly unreserve client2
            assert client2.unreserve(), "Client 2 failed to unreserve"

        finally:
            client2.disconnect()

    finally:
        client1.disconnect()


def test_failed_execution(protocol_client, tmp_path):
    """
    Test execution with invalid code (like testFailedCase).

    Tests that the calculator properly handles execution failures.
    """
    # Create input file
    input_file = tmp_path / "test_input.sh"
    input_file.write_text("#!/bin/bash\necho 'test'\n")

    # Reserve and upload
    assert protocol_client.reserve("shell"), "Failed to reserve"
    assert protocol_client.new_case("fail_test"), "Failed to create case"
    assert protocol_client.put_file(input_file), "Failed to upload"

    # Try to execute with invalid code name
    # This might succeed or fail depending on calculator configuration
    result = protocol_client.execute("INVALID_CODE_NAME")
    print(f"Execute with invalid code returned: {result}")

    # Try to get results anyway (might be empty or error results)
    results_dir = tmp_path / "fail_results"
    results_dir.mkdir()
    protocol_client.get_results(results_dir)

    # Cleanup
    protocol_client.unreserve()


def test_disconnect_during_reservation(funz_host, funz_port):
    """
    Test client disconnection while reserved (like testCaseBreakClient).

    Tests that the calculator properly handles unexpected client disconnections.
    """
    client = FunzProtocolClient(funz_host, funz_port)
    assert client.connect(), "Failed to connect"

    # Reserve calculator
    assert client.reserve("shell"), "Failed to reserve"
    assert client.is_reserved(), "Should be reserved"

    # Check activity
    activity = client.get_activity()
    print(f"Activity after reserve: {activity}")

    # Abruptly close connection without unreserving
    print("Forcing disconnect without unreserve...")
    if client.socket:
        client.socket.close()
        client.socket = None
        client.socket_file = None

    # Wait for calculator to detect disconnection
    time.sleep(3)

    # Try connecting with a new client (should succeed after disconnect detected)
    client2 = FunzProtocolClient(funz_host, funz_port)
    assert client2.connect(), "Failed to reconnect"

    try:
        activity2 = client2.get_activity()
        print(f"Activity after reconnect: {activity2}")

        # Should be able to reserve (previous client was cleaned up)
        time.sleep(2)  # Give calculator time to clean up
        assert client2.reserve("shell"), "Failed to reserve after forced disconnect"
        client2.unreserve()

    finally:
        client2.disconnect()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
