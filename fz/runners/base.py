"""Abstract calculator interface (submit / poll / fetch / cancel).

Every backend (sh, ssh, slurm, funz, cache) exposes a :class:`Calculator`.
Backends only have to implement the blocking :meth:`Calculator.run`; the default
``submit``/``poll``/``fetch``/``cancel`` run it on a worker thread. A backend with
native asynchronous job control (e.g. SLURM ``sbatch``) can override them.
"""

import threading
from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict, List, Optional


class Calculator(ABC):
    """A calculator backend, selected by URI scheme."""

    #: URI scheme handled by this backend (e.g. "sh", "ssh")
    scheme: str = ""

    @abstractmethod
    def run(
        self,
        working_dir: Path,
        calculator_uri: str,
        model: Dict,
        timeout: Optional[int] = None,
        original_input_was_dir: bool = False,
        original_cwd: Optional[str] = None,
        input_files_list: Optional[List[str]] = None,
        static_entries: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run one calculation to completion and return its result dict."""

    def submit(self, *args, **kwargs) -> Future:
        """Start a calculation without blocking; returns a handle for poll/fetch/cancel."""
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            return executor.submit(self.run, *args, **kwargs)
        finally:
            executor.shutdown(wait=False)

    def poll(self, handle: Future) -> str:
        """Return "running", "done", "cancelled" or "error" for a submitted calculation."""
        if handle.cancelled():
            return "cancelled"
        if not handle.done():
            return "running"
        return "error" if handle.exception() is not None else "done"

    def fetch(self, handle: Future, timeout: Optional[float] = None) -> Dict[str, Any]:
        """Wait for a submitted calculation and return its result dict."""
        return handle.result(timeout=timeout)

    def cancel(self, handle: Future) -> bool:
        """Best-effort cancel; only effective before the calculation has started."""
        return handle.cancel()
