"""
Case status spinner for fz package - visual progress indicator for running cases
"""
import os
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
    A visual spinner that shows status of multiple cases in a single line

    Symbols:
    - □ (empty square): Case not yet started
    - |/-\\ (rotating bar): Case currently running
    - ✓ (check mark): Case completed successfully
    - ✗ (cross mark): Case failed

    Example output:
    [□□|/-\\✓✗] ETA: 2m 30s
    """

    def __init__(self, num_cases: int):
        """
        Initialize spinner for multiple cases

        Args:
            num_cases: Total number of cases to track
        """
        self.num_cases = num_cases
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

        # Render final status line to show "Total time:"
        if not clear:
            final_status = self._build_status_line()
            sys.stdout.write('\r' + final_status)
            sys.stdout.flush()
            self.last_output = final_status

        if clear and self.last_output:
            # Clear the line
            sys.stdout.write('\r' + ' ' * len(self.last_output) + '\r')
            sys.stdout.flush()
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

    def _get_status_char(self, status: CaseStatus) -> str:
        """Get the display character for a given status"""
        if status == CaseStatus.PENDING:
            return ' '
        elif status == CaseStatus.RUNNING:
            return self.spinner_chars[self.spinner_index % len(self.spinner_chars)]
        elif status == CaseStatus.DONE:
            return '■'
        elif status == CaseStatus.FAILED:
            return '□'
        else:
            return 'o'

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
        """Build the status line showing all cases"""
        with self.lock:
            # Build character array
            chars = [self._get_status_char(status) for status in self.statuses]

            # For single case, just show the spinner bar
            if self.num_cases == 1:
                status_line = f"[{''.join(chars)}]"
            else:
                # Count statuses
                completed = sum(1 for s in self.statuses if s in (CaseStatus.DONE, CaseStatus.FAILED))
                remaining = self.num_cases - completed

                # Calculate ETA or Total time
                if remaining > 0 and self.case_durations:
                    # Use average duration of completed cases
                    avg_duration = sum(self.case_durations) / len(self.case_durations)
                    eta_seconds = avg_duration * remaining
                    eta_text = f"ETA: {self._format_eta(eta_seconds)}"
                elif remaining > 0:
                    # No completed cases yet, show calculating
                    eta_text = "ETA: ..."
                else:
                    # All cases completed - show total time
                    if self.start_time is not None:
                        total_time = time.time() - self.start_time
                        eta_text = f"Total time: {self._format_eta(total_time)}"
                    else:
                        eta_text = "Done"

                # Build final line
                status_line = f"[{''.join(chars)}] {eta_text}"

            return status_line

    def _animate(self):
        """Animation loop that runs in background thread"""
        while not self.stop_event.is_set():
            # Build and display status line
            status_line = self._build_status_line()

            # Update display (overwrite previous line)
            sys.stdout.write('\r' + status_line)
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
