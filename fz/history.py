"""
Case history tracking and info file generation for fz package.

Provides structured metadata (info.txt) and timestamped event traces (history.txt)
for each case result directory, similar to Funz Java's Case.java.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional


class CaseHistory:
    """Accumulates timestamped events for a single case execution."""

    def __init__(self, case_name: str):
        self._lines = [f"# {case_name}"]

    def append(self, message: str):
        self._lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")

    def write(self, directory: Path):
        (directory / "history.txt").write_text("\n".join(self._lines) + "\n")


def write_info_file(directory: Path, *,
                    state: str,
                    calculator: str,
                    start_time: Optional[datetime] = None,
                    end_time: Optional[datetime] = None,
                    input_variables: Optional[dict] = None,
                    output_values: Optional[dict] = None,
                    error: Optional[str] = None):
    """
    Write a Java-Properties-style info.txt to *directory*.

    Example output::

        state=done
        calc=sh://bash -c 'cat input.txt'
        start=2025-02-20T14:30:01
        end=2025-02-20T14:30:02
        duration=1.23
        input.temp=100
        input.pressure=1
        output.result=42.0

    When the calculation failed::

        state=failed
        calc=sh://nonexistent_command
        error=Command not found locally: 'nonexistent_command'. ...
        start=2025-02-20T14:30:01
        end=2025-02-20T14:30:02
        duration=1.23
    """
    lines = []
    lines.append(f"state={state}")
    lines.append(f"calc={calculator}")

    if error:
        lines.append(f"error={error}")

    if start_time is not None:
        lines.append(f"start={start_time.isoformat(timespec='seconds')}")
    if end_time is not None:
        lines.append(f"end={end_time.isoformat(timespec='seconds')}")
    if start_time is not None and end_time is not None:
        duration = (end_time - start_time).total_seconds()
        lines.append(f"duration={duration:.2f}")

    if input_variables:
        for k, v in input_variables.items():
            lines.append(f"input.{k}={v}")

    if output_values:
        for k, v in output_values.items():
            lines.append(f"output.{k}={v}")

    (directory / "info.txt").write_text("\n".join(lines) + "\n")
