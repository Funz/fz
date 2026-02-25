"""
Case status spinner for fz package - visual progress indicator for running cases
"""
import os
import shutil
import sys
import threading
import time
from typing import List, Dict, Optional
from enum import Enum


class CaseStatus(Enum):
    """Status of a case"""
    PENDING = 'pending'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'


class CaseSpinner:
    """
    A visual progress bar that shows completion percentage in a single line

    Example output:
    ◢ [████████>░░░░░░░░░░░]  35% (7/20) ETA: 1m 45s
    """

    def __init__(self, num_cases: int, num_calculators: int = 1):
        """
        Initialize spinner for multiple cases

        Args:
            num_cases: Total number of cases to track
            num_calculators: Number of parallel calculators (for ETA estimation)
        """
        self.num_cases = num_cases
        self.num_calculators = max(1, num_calculators)  # At least 1
        self.statuses = [CaseStatus.PENDING] * num_cases
        self.spinner_chars = ['◢', '◣', '◤', '◥']
        self.spinner_index = 0
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        self.last_output = ""
        self.enabled = True  # Can be disabled for non-TTY or quiet mode

        # ETA tracking
        self.start_time = None
        self.case_start_times = {}  # Dict[int, float] - case_index -> start time
        self.case_durations = []  # List[float] - completed case durations

    def start(self):
        """Start the spinner animation in a background thread"""
        if not self.enabled or self.num_cases == 0:
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()

    def stop(self, clear: bool = False):
        """
        Stop the spinner animation

        Args:
            clear: If True, clear the spinner line after stopping
        """
        if not self.enabled or self.num_cases == 0:
            return

        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)

        # Clear any previous output first, then render final or clear
        if self.last_output:
            sys.stdout.write('\r' + ' ' * len(self.last_output) + '\r')
            sys.stdout.flush()

        if not clear:
            final_status = self._build_status_line()
            sys.stdout.write('\r' + final_status)
            sys.stdout.flush()
            self.last_output = final_status
        else:
            self.last_output = ""

    def update_status(self, case_index: int, status: CaseStatus):
        """
        Update the status of a specific case

        Args:
            case_index: Index of the case to update
            status: New status for the case
        """
        if not self.enabled or case_index >= self.num_cases:
            return

        with self.lock:
            old_status = self.statuses[case_index]
            self.statuses[case_index] = status

            # Track timing for ETA calculation
            current_time = time.time()

            # Record start time when first case starts running
            if self.start_time is None and status == CaseStatus.RUNNING:
                self.start_time = current_time

            # Track when this case starts
            if status == CaseStatus.RUNNING and case_index not in self.case_start_times:
                self.case_start_times[case_index] = current_time

            # Track duration when case completes (successfully or failed)
            if status in (CaseStatus.DONE, CaseStatus.FAILED) and case_index in self.case_start_times:
                duration = current_time - self.case_start_times[case_index]
                self.case_durations.append(duration)

    def _format_eta(self, seconds: float) -> str:
        """Format ETA in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _build_status_line(self) -> str:
        """Build a fixed-width progress bar with percentage and ETA"""
        with self.lock:
            # Count statuses
            done = sum(1 for s in self.statuses if s == CaseStatus.DONE)
            failed = sum(1 for s in self.statuses if s == CaseStatus.FAILED)
            running = sum(1 for s in self.statuses if s == CaseStatus.RUNNING)
            completed = done + failed
            remaining = self.num_cases - completed
            pct = completed * 100 // self.num_cases if self.num_cases > 0 else 100

            # Spinner character for visual feedback when cases are running
            spinner = self.spinner_chars[self.spinner_index % len(self.spinner_chars)] if running > 0 else ' '

            # Calculate ETA or Total time
            if remaining > 0 and self.case_durations:
                avg_duration = sum(self.case_durations) / len(self.case_durations)
                eta_seconds = (avg_duration * remaining) / self.num_calculators
                time_text = f"ETA: {self._format_eta(eta_seconds)}"
            elif remaining > 0:
                time_text = "ETA: ..."
            else:
                if self.start_time is not None:
                    total_time = time.time() - self.start_time
                    time_text = f"Total: {self._format_eta(total_time)}"
                else:
                    time_text = "Done"

            # Build suffix: " 35% (7/20) ETA: 1m 45s"
            if failed > 0:
                suffix = f" {pct:3d}% ({done}+{failed}err/{self.num_cases}) {time_text}"
            else:
                suffix = f" {pct:3d}% ({completed}/{self.num_cases}) {time_text}"

            # Determine bar width from terminal, reserving space for brackets + spinner + suffix
            try:
                term_width = shutil.get_terminal_size().columns
            except Exception:
                term_width = 80
            # Format: "S [=====>    ] suffix"  where S is spinner char
            overhead = 2 + 1 + 1 + 2 + len(suffix)  # spinner + space + [ + ] + suffix
            bar_width = max(10, min(40, term_width - overhead))

            # Build the bar
            filled = int(bar_width * completed / self.num_cases) if self.num_cases > 0 else bar_width
            filled = min(filled, bar_width)
            if remaining > 0 and filled < bar_width:
                bar = '█' * filled + '>' + '░' * (bar_width - filled - 1)
            else:
                bar = '█' * filled + '░' * (bar_width - filled)

            return f"{spinner} [{bar}]{suffix}"

    def _animate(self):
        """Animation loop that runs in background thread"""
        while not self.stop_event.is_set():
            # Build and display status line
            status_line = self._build_status_line()

            # Clear previous output and write new line
            clear_len = max(len(self.last_output), len(status_line))
            sys.stdout.write('\r' + ' ' * clear_len + '\r' + status_line)
            sys.stdout.flush()
            self.last_output = status_line

            # Increment spinner animation
            self.spinner_index += 1

            # Wait before next update
            time.sleep(0.15)  # Update every 150ms for smooth animation

    def should_enable(self) -> bool:
        """
        Check if spinner should be enabled based on environment

        Returns:
            True if spinner should be enabled
        """
        # # Disable if not a TTY
        # if not sys.stdout.isatty():
        #     return False
        # 
        # # Disable if only 0 or 1 case (not useful)
        # if self.num_cases <= 1:
        #     return False

        # Check if we're in a CI environment (common CI env vars)
        ci_vars = ['CI', 'CONTINUOUS_INTEGRATION', 'TRAVIS', 'CIRCLECI', 'JENKINS', 'GITHUB_ACTIONS']
        if any(var in os.environ for var in ci_vars):
            return False

        return True

    def __enter__(self):
        """Context manager entry"""
        self.enabled = self.should_enable()
        if self.enabled:
            self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.enabled:
            # Stop but don't clear - keep the final status visible
            self.stop(clear=False)
            # Print final newline to move to next line
            print()
