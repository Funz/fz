"""SLURM job-array calculator (``slurm-array://``, local SLURM only).

Cases submitted concurrently on the same URI are batched into ONE
``sbatch --array`` job (see :mod:`fz.slurm_async`) instead of each blocking on
its own ``srun``, as ``slurm://`` (:mod:`fz.runners.slurm`) does.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Calculator
from .errors import classify_error
from .manager import get_environment_info, resolve_timeout
from .slurm import parse_slurm_uri
from .. import slurm_async
from ..logging import log_info


def run_slurm_array_calculation(
    working_dir: Path,
    slurm_uri: str,
    model: Dict,
    timeout: Optional[int] = None,
    input_files_list: Optional[List[str]] = None,
    static_entries: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run one case through ``slurm-array://[:]partition/script[?resources]``."""
    timeout = resolve_timeout(model, timeout, "slurm")

    from ..core import is_interrupted

    if is_interrupted():
        return {"status": "interrupted", "error": "Execution interrupted by user", "command": slurm_uri}

    try:
        base_uri, resources = slurm_async.split_slurm_resources(slurm_uri)
        host, port, username, password, partition, script = parse_slurm_uri(
            base_uri.replace("slurm-array://", "slurm://", 1)
        )
    except Exception as e:
        return {"status": "error", "error": f"SLURM calculation failed: {str(e)}"}

    if host is not None:
        return {
            "status": "error",
            "error": (
                "slurm-array:// supports local SLURM only "
                "(use slurm://user@host:partition/script for remote)"
            ),
        }

    log_info(f"SLURM array calculation: partition={partition}, script={script}")
    start_time = datetime.now()
    env_info = get_environment_info()
    input_argument = " ".join(input_files_list) if input_files_list else "."

    command = f"sbatch --array --partition={partition} {script} {input_argument}"
    monitor = slurm_async.get_monitor()
    task = slurm_async.get_batcher().add(partition, script, input_argument, working_dir, resources)
    while not task.submitted.wait(0.5):
        if is_interrupted():
            return {"status": "interrupted", "error": "SLURM calculation interrupted by user",
                    "command": command}
    if task.error:
        return {"status": "error", "error": task.error, "command": command}
    job_id = task.job_id
    log_info(f"Submitted SLURM array task {job_id}: {command}")
    event = monitor.register(job_id)

    waited = 0.0
    while not event.wait(0.5):
        waited += 0.5
        if is_interrupted():
            slurm_async.cancel(job_id)
            monitor.forget(job_id)
            return {"status": "interrupted", "error": "SLURM calculation interrupted by user",
                    "command": command}
        if timeout is not None and waited >= timeout:
            slurm_async.cancel(job_id)
            monitor.forget(job_id)
            return {
                "status": "timeout",
                "error": f"SLURM job timed out after {timeout} seconds on partition '{partition}'",
                "command": command,
            }

    state, exit_code = monitor.result(job_id)
    marker = slurm_async.read_exit_marker(working_dir)
    if exit_code is None or (exit_code == 0 and marker not in (None, 0)):
        exit_code = marker
    if exit_code is None:
        exit_code = 0 if state == "COMPLETED" else 1
    failed = state != "COMPLETED" or exit_code != 0

    end_time = datetime.now()
    with open(working_dir / "log.txt", "w") as log_file:
        log_file.write(f"Command: {command}\n")
        log_file.write(f"Exit code: {exit_code}\n")
        log_file.write(f"SLURM job id: {job_id}\n")
        log_file.write(f"SLURM state: {state}\n")
        log_file.write(f"SLURM partition: {partition}\n")
        log_file.write(f"Time start: {start_time.isoformat()}\n")
        log_file.write(f"Time end: {end_time.isoformat()}\n")
        log_file.write(f"Execution time: {(end_time - start_time).total_seconds():.3f} seconds\n")
        log_file.write(f"User: {env_info['user']}\n")
        log_file.write(f"Hostname: {env_info['hostname']}\n")

    if failed:
        stderr_content = ""
        try:
            stderr_content = (working_dir / "err.txt").read_text().strip()
        except Exception:
            pass
        if state == "TIMEOUT":
            return {"status": "timeout",
                    "error": f"SLURM job {job_id} hit its time limit on partition '{partition}'",
                    "command": command}
        return {
            "status": "failed",
            "exit_code": exit_code,
            "error": classify_error(stderr=stderr_content, exit_code=exit_code,
                                    command=command, protocol="slurm"),
            "stderr": stderr_content,
            "command": command,
        }

    from ..core import fzo

    output_results = fzo(working_dir, model)
    output_dict = output_results.iloc[0].to_dict() if hasattr(output_results, "to_dict") else output_results
    output_error = output_dict.pop("_output_error", None)
    output_dict["status"] = "done"
    output_dict["calculator"] = f"slurm-array://{partition}"
    output_dict["command"] = command
    if output_error:
        output_dict["error"] = f"Missing output: {output_error}"
    return output_dict


class SlurmArrayCalculator(Calculator):
    scheme = "slurm-array"

    def run(self, working_dir, calculator_uri, model, timeout=None,
            original_input_was_dir=False, original_cwd=None,
            input_files_list=None, static_entries=None):
        return run_slurm_array_calculation(
            working_dir, calculator_uri, model, timeout, input_files_list,
            static_entries=static_entries,
        )
