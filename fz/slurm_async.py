"""
Asynchronous SLURM support for ``slurm://`` calculators (local mode).

Jobs are submitted with ``sbatch`` and followed by a single shared monitor
thread that queries ``sacct`` (falling back to ``squeue``) once per poll
interval for *all* pending jobs, instead of blocking one ``srun`` per case.
"""

import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl

from .logging import log_debug, log_warning

# URI query parameter -> sbatch option. Values are validated, never shell-expanded.
RESOURCE_OPTIONS = {
    "cores": "--cpus-per-task",
    "mem": "--mem",
    "time": "--time",
    "nodes": "--nodes",
    "ntasks": "--ntasks",
    "gres": "--gres",
    "account": "--account",
    "qos": "--qos",
}
_VALUE_RE = re.compile(r"^[A-Za-z0-9_.:,=\-/]+$")

_TERMINAL_OK = {"COMPLETED"}
_TERMINAL_FAIL = {
    "FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL",
    "BOOT_FAIL", "DEADLINE", "PREEMPTED", "REVOKED", "SPECIAL_EXIT",
}
EXIT_MARKER = ".fz_slurm_exit"


def split_slurm_resources(slurm_uri: str) -> Tuple[str, Dict[str, str]]:
    """Split ``slurm://...?cores=4&mem=2G&time=01:00:00`` into (uri, resources)."""
    if "?" not in slurm_uri:
        return slurm_uri, {}
    base, query = slurm_uri.split("?", 1)
    resources = {}
    for key, value in parse_qsl(query, keep_blank_values=True):
        if key not in RESOURCE_OPTIONS:
            raise ValueError(
                f"Unknown SLURM resource '{key}' (allowed: {', '.join(sorted(RESOURCE_OPTIONS))})"
            )
        if not _VALUE_RE.match(value):
            raise ValueError(f"Invalid value for SLURM resource '{key}': {value!r}")
        resources[key] = value
    return base, resources


def resolve_mode() -> str:
    """Return 'sbatch' or 'srun' from FZ_SLURM_MODE (auto|sbatch|srun, default auto)."""
    mode = os.getenv("FZ_SLURM_MODE", "auto").lower()
    if mode == "auto":
        return "sbatch" if shutil.which("sbatch") else "srun"
    if mode not in ("sbatch", "srun"):
        log_warning(f"Invalid FZ_SLURM_MODE={mode!r}, using auto")
        return "sbatch" if shutil.which("sbatch") else "srun"
    return mode


def build_sbatch_command(partition: str, wrapped: str, working_dir: Path,
                         resources: Dict[str, str]) -> List[str]:
    cmd = [
        "sbatch", "--parsable", f"--partition={partition}",
        f"--chdir={working_dir}", "--output=out.txt", "--error=err.txt",
    ]
    cmd += [f"{RESOURCE_OPTIONS[k]}={v}" for k, v in resources.items()]
    cmd.append(f"--wrap={wrapped}")
    return cmd


def submit(partition: str, script: str, input_argument: str, working_dir: Path,
           resources: Dict[str, str]) -> str:
    """Submit one job with sbatch and return its job id."""
    # The marker file gives an exit code even when sacct accounting is disabled.
    wrapped = f"{script} {input_argument}; rc=$?; echo $rc > {EXIT_MARKER}; exit $rc"
    cmd = build_sbatch_command(partition, wrapped, working_dir, resources)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"sbatch failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout.strip().split(";")[0]


def cancel(job_id: str) -> None:
    try:
        subprocess.run(["scancel", job_id], capture_output=True, timeout=30)
    except Exception as e:
        log_warning(f"scancel {job_id} failed: {e}")


class SlurmJobMonitor:
    """One polling thread shared by every pending job; callers wait on events."""

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self._lock = threading.Lock()
        self._pending: Dict[str, threading.Event] = {}
        self._results: Dict[str, Tuple[str, Optional[int]]] = {}
        self._thread: Optional[threading.Thread] = None

    def register(self, job_id: str) -> threading.Event:
        event = threading.Event()
        with self._lock:
            self._pending[job_id] = event
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._loop, daemon=True, name="fz-slurm-monitor")
                self._thread.start()
        return event

    def result(self, job_id: str) -> Tuple[str, Optional[int]]:
        with self._lock:
            return self._results.pop(job_id, ("UNKNOWN", None))

    def forget(self, job_id: str) -> None:
        with self._lock:
            self._pending.pop(job_id, None)

    def _loop(self) -> None:
        while True:
            with self._lock:
                ids = list(self._pending)
            if not ids:
                time.sleep(self.poll_interval)
                with self._lock:
                    if not self._pending:
                        self._thread = None
                        return
                continue
            try:
                states = query_states(ids)
            except Exception as e:  # keep the monitor alive on transient errors
                log_debug(f"SLURM poll failed: {e}")
                states = {}
            for job_id, (state, code) in states.items():
                if state in _TERMINAL_OK or state in _TERMINAL_FAIL:
                    with self._lock:
                        event = self._pending.pop(job_id, None)
                        self._results[job_id] = (state, code)
                    if event:
                        event.set()
            time.sleep(self.poll_interval)


def query_states(job_ids: List[str]) -> Dict[str, Tuple[str, Optional[int]]]:
    """Return {job_id: (state, exit_code)} using one sacct call, else one squeue call."""
    joined = ",".join(job_ids)
    out: Dict[str, Tuple[str, Optional[int]]] = {}
    try:
        proc = subprocess.run(
            ["sacct", "-X", "-n", "-P", "-j", joined, "-o", "JobID,State,ExitCode"],
            capture_output=True, text=True, timeout=60,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            for line in proc.stdout.strip().splitlines():
                job_id, state, exit_code = (line.split("|") + ["", ""])[:3]
                state = state.split()[0] if state else "UNKNOWN"  # "CANCELLED by 123"
                out[job_id] = (state, int(exit_code.split(":")[0]) if exit_code else None)
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    proc = subprocess.run(
        ["squeue", "-h", "-j", joined, "-o", "%i|%T"],
        capture_output=True, text=True, timeout=60,
    )
    active = {}
    for line in proc.stdout.strip().splitlines():
        job_id, _, state = line.partition("|")
        active[job_id] = state
    for job_id in job_ids:
        # Gone from the queue and no accounting: treat as finished, exit code from marker.
        out[job_id] = (active.get(job_id, "COMPLETED"), None)
    return out


_monitor: Optional[SlurmJobMonitor] = None
_monitor_lock = threading.Lock()


def get_monitor() -> SlurmJobMonitor:
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = SlurmJobMonitor(float(os.getenv("FZ_SLURM_POLL_INTERVAL", "2")))
        return _monitor


def read_exit_marker(working_dir: Path) -> Optional[int]:
    try:
        return int((Path(working_dir) / EXIT_MARKER).read_text().strip())
    except Exception:
        return None
