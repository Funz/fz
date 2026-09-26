"""
Job-array SLURM support for the ``slurm-array://`` calculator (local mode).

Cases that arrive within a short window are batched into ONE
``sbatch --array`` submission; a single shared monitor thread then queries
``sacct`` (falling back to ``squeue``) once per poll interval for all pending
array tasks. ``slurm://`` keeps using a blocking ``srun`` per case.
"""

import os
import re
import shlex
import uuid
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
# Array-only: cap on simultaneously running tasks (sbatch --array=0-N%M)
ARRAY_THROTTLE_KEY = "maxrunning"
MAX_ARRAY_SIZE = 1000  # SLURM's default MaxArraySize
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
        if key not in RESOURCE_OPTIONS and key != ARRAY_THROTTLE_KEY:
            raise ValueError(
                f"Unknown SLURM resource '{key}' (allowed: {', '.join(sorted(list(RESOURCE_OPTIONS) + [ARRAY_THROTTLE_KEY]))})"
            )
        if not _VALUE_RE.match(value):
            raise ValueError(f"Invalid value for SLURM resource '{key}': {value!r}")
        resources[key] = value
    return base, resources


def srun_options(resources: Dict[str, str]) -> str:
    """Resource options for a blocking ``srun`` (slurm://); values are regex-validated."""
    return " ".join(f"{RESOURCE_OPTIONS[k]}={v}" for k, v in resources.items() if k in RESOURCE_OPTIONS)


class ArrayTask:
    """Handle on one case inside a submitted array; ``job_id`` is ``<array>_<index>``."""

    def __init__(self, working_dir: Path):
        self.working_dir = Path(working_dir)
        self.job_id: Optional[str] = None
        self.error: Optional[str] = None
        self.submitted = threading.Event()  # set once job_id (or error) is known


class _Batch:
    def __init__(self, key):
        self.key = key
        self.tasks: List[ArrayTask] = []
        self.timer: Optional[threading.Timer] = None


class ArrayBatcher:
    """Collect concurrently submitted cases and send them as one ``sbatch --array``."""

    def __init__(self, window: float = 1.0):
        self.window = window
        self._lock = threading.Lock()
        self._batches: Dict[tuple, _Batch] = {}

    def add(self, partition: str, script: str, input_argument: str, working_dir: Path,
            resources: Dict[str, str]) -> ArrayTask:
        key = (partition, script, input_argument, tuple(sorted(resources.items())))
        task = ArrayTask(working_dir)
        flush_now = None
        with self._lock:
            batch = self._batches.get(key)
            if batch is None:
                batch = self._batches[key] = _Batch(key)
                batch.timer = threading.Timer(self.window, self._flush, args=(key, batch))
                batch.timer.daemon = True
                batch.timer.start()
            batch.tasks.append(task)
            if len(batch.tasks) >= MAX_ARRAY_SIZE:
                flush_now = batch
        if flush_now:
            self._flush(key, flush_now)
        return task

    def _flush(self, key, batch: _Batch) -> None:
        with self._lock:
            if self._batches.get(key) is not batch:
                return  # already flushed
            del self._batches[key]
            if batch.timer:
                batch.timer.cancel()
        partition, script, input_argument, res = key
        try:
            job_id = submit_array(partition, script, input_argument,
                                  [t.working_dir for t in batch.tasks], dict(res))
            log_debug(f"Submitted SLURM array {job_id} with {len(batch.tasks)} tasks")
            for index, task in enumerate(batch.tasks):
                task.job_id = f"{job_id}_{index}"
        except Exception as e:
            for task in batch.tasks:
                task.error = str(e)
        finally:
            for task in batch.tasks:
                task.submitted.set()


def build_array_command(partition: str, script: str, input_argument: str, manifest: Path,
                        n_tasks: int, resources: Dict[str, str]) -> List[str]:
    """sbatch command for an array; each task cds into its case dir listed in the manifest."""
    array = f"0-{n_tasks - 1}"
    if ARRAY_THROTTLE_KEY in resources:
        array += f"%{resources[ARRAY_THROTTLE_KEY]}"
    # The marker file gives an exit code even when sacct accounting is disabled.
    wrapped = (
        f'd=$(sed -n "$((SLURM_ARRAY_TASK_ID+1))p" {shlex.quote(str(manifest))}); '
        f'cd "$d" || exit 1; '
        f"{script} {input_argument} > out.txt 2> err.txt; rc=$?; "
        f"echo $rc > {EXIT_MARKER}; exit $rc"
    )
    cmd = ["sbatch", "--parsable", f"--partition={partition}", f"--array={array}",
           f"--chdir={manifest.parent}", "--output=/dev/null", "--error=/dev/null"]
    cmd += [f"{RESOURCE_OPTIONS[k]}={v}" for k, v in resources.items() if k in RESOURCE_OPTIONS]
    cmd.append(f"--wrap={wrapped}")
    return cmd


def submit_array(partition: str, script: str, input_argument: str, working_dirs: List[Path],
                 resources: Dict[str, str]) -> str:
    """Submit one array job covering ``working_dirs`` and return the array job id."""
    common = Path(os.path.commonpath([str(d) for d in working_dirs]))
    manifest = common / f".fz_array_{uuid.uuid4().hex[:8]}.manifest"
    manifest.write_text("".join(f"{d}\n" for d in working_dirs))
    cmd = build_array_command(partition, script, input_argument, manifest, len(working_dirs), resources)
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
    # Array tasks are "<array>_<index>"; ask for whole arrays, keep the rows we track.
    joined = ",".join(sorted({j.split("_")[0] for j in job_ids}))
    wanted = set(job_ids)
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
                if job_id in wanted:
                    out[job_id] = (state, int(exit_code.split(":")[0]) if exit_code else None)
            return out
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    proc = subprocess.run(
        ["squeue", "-h", "-r", "-j", joined, "-o", "%i|%T"],
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
_batcher: Optional[ArrayBatcher] = None
_monitor_lock = threading.Lock()


def get_batcher() -> ArrayBatcher:
    global _batcher
    with _monitor_lock:
        if _batcher is None:
            _batcher = ArrayBatcher(float(os.getenv("FZ_SLURM_ARRAY_WINDOW", "1")))
        return _batcher


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
