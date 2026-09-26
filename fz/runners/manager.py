"""Calculator instance registry and environment info."""

import os
import socket
import platform
import uuid
import threading
import getpass
from collections import defaultdict
from typing import Dict, List, Optional

from ..logging import log_warning, log_debug
from ..config import get_config


def get_environment_info() -> Dict[str, str]:
    """
    Get environment information for logging

    Returns:
        Dict with environment variables and system info
    """
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"

    try:
        username = getpass.getuser()
    except:
        username = os.getenv("USER", os.getenv("USERNAME", "unknown"))

    return {
        "user": username,
        "hostname": hostname,
        "operating_system": platform.system(),
        "platform": platform.platform(),
        "working_dir": os.getcwd(),
        "python_version": platform.python_version(),
    }


class CalculatorManager:
    """Thread-safe calculator management for parallel execution"""

    def __init__(self):
        self._lock = threading.Lock()
        self._calculator_locks = defaultdict(threading.Lock)
        self._calculator_owners = {}  # calculator_id -> thread_id mapping
        self._calculator_registry = {}  # calculator_id -> original_uri mapping

    def register_calculator_instances(self, calculator_uris: List[str]) -> List[str]:
        """
        Register calculator instances with unique IDs for each occurrence

        Args:
            calculator_uris: List of calculator URIs (may contain duplicates)

        Returns:
            List of unique calculator IDs
        """
        calculator_ids = []
        with self._lock:
            for uri in calculator_uris:
                # Generate unique alphanumeric ID for tmux compatibility
                unique_id = uuid.uuid4().hex[:8]
                calc_id = f"{uri}#{unique_id}"
                self._calculator_registry[calc_id] = uri
                calculator_ids.append(calc_id)
        return calculator_ids

    def get_original_uri(self, calculator_id: str) -> str:
        """Get the original URI for a calculator ID"""
        return self._calculator_registry.get(calculator_id, calculator_id)

    def acquire_calculator(self, calculator_id: str, thread_id: int) -> bool:
        """
        Try to acquire exclusive access to a calculator

        Args:
            calculator_id: Calculator ID to acquire
            thread_id: Thread ID requesting the calculator

        Returns:
            True if calculator was acquired, False if already in use
        """
        calc_lock = self._calculator_locks[calculator_id]

        # Try to acquire the calculator lock (non-blocking)
        acquired = calc_lock.acquire(blocking=False)

        if acquired:
            with self._lock:
                self._calculator_owners[calculator_id] = thread_id
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"🔒 [Thread {thread_id}] Acquired calculator: {original_uri} (ID: {calculator_id})"
            )
            return True
        else:
            current_owner = self._calculator_owners.get(calculator_id, "unknown")
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"⏳ [Thread {thread_id}] Calculator {original_uri} (ID: {calculator_id}) is busy (owned by thread {current_owner})"
            )
            return False

    def release_calculator(self, calculator_id: str, thread_id: int):
        """
        Release exclusive access to a calculator

        Args:
            calculator_id: Calculator ID to release
            thread_id: Thread ID releasing the calculator
        """
        try:
            with self._lock:
                if calculator_id in self._calculator_owners:
                    del self._calculator_owners[calculator_id]

            calc_lock = self._calculator_locks[calculator_id]
            calc_lock.release()
            original_uri = self.get_original_uri(calculator_id)
            log_debug(
                f"🔓 [Thread {thread_id}] Released calculator: {original_uri} (ID: {calculator_id})"
            )
        except Exception as e:
            original_uri = self.get_original_uri(calculator_id)
            log_warning(
                f"⚠️ [Thread {thread_id}] Error releasing calculator {original_uri} (ID: {calculator_id}): {e}"
            )

    def get_available_calculator(
        self, calculator_ids: List[str], thread_id: int, case_index: int
    ) -> Optional[str]:
        """
        Get an available calculator from the list, preferring round-robin distribution

        Args:
            calculator_ids: List of calculator IDs to choose from
            thread_id: Thread ID requesting a calculator
            case_index: Case index for round-robin distribution

        Returns:
            Available calculator ID or None if all are busy
        """
        if not calculator_ids:
            return None

        # Try round-robin selection first
        preferred_index = case_index % len(calculator_ids)
        preferred_calc = calculator_ids[preferred_index]

        if self.acquire_calculator(preferred_calc, thread_id):
            return preferred_calc

        # If preferred calculator is busy, try others
        for calc in calculator_ids:
            if calc != preferred_calc and self.acquire_calculator(calc, thread_id):
                return calc

        # All calculators are busy
        return None

    def cleanup_all_calculators(self):
        """
        Release all calculator locks and clear internal state

        This should be called when fzr execution is complete to ensure
        proper cleanup of resources.
        """
        with self._lock:
            # Force release all calculator locks
            for calc_id, calc_lock in self._calculator_locks.items():
                try:
                    # Try to release the lock (may fail if not held)
                    if calc_id in self._calculator_owners:
                        thread_id = self._calculator_owners[calc_id]
                        log_debug(
                            f"🧹 Cleanup: Force-releasing calculator {calc_id} from thread {thread_id}"
                        )
                        calc_lock.release()
                except Exception as e:
                    # Lock might not be held, which is fine
                    pass

            # Clear all state
            self._calculator_locks.clear()
            self._calculator_owners.clear()
            self._calculator_registry.clear()
            self._next_id = 1

        log_debug("🧹 CalculatorManager cleanup completed")

    def get_active_calculators(self) -> Dict[str, int]:
        """
        Get currently active calculators and their owners

        Returns:
            Dict mapping calculator ID to thread ID for active calculators
        """
        with self._lock:
            return dict(self._calculator_owners)


# Global instance
_calculator_manager = CalculatorManager()


def resolve_timeout(model: Optional[Dict], timeout: Optional[int] = None) -> Optional[int]:
    """
    Resolve the effective run timeout in seconds.

    Precedence: explicit `timeout` argument > model's own "timeout" entry >
    FZ_RUN_TIMEOUT config default. A model "timeout" of None/null or 0 disables
    the timeout for that model (returns None, meaning no timeout).

    Returns:
        Timeout in seconds, or None if the timeout is disabled.
    """
    if timeout is not None:
        return timeout
    if isinstance(model, dict) and "timeout" in model:
        model_timeout = model["timeout"]
        if model_timeout is None or model_timeout == 0:
            return None
        return int(model_timeout)
    return get_config().run_timeout
