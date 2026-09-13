from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentBudget:
    max_trials: int = 10
    max_runtime_seconds: int = 3600
    max_no_improvement: int = 5
    max_consecutive_failures: int = 3

    def validate(self):
        if self.max_trials < 1 or self.max_runtime_seconds < 1 or self.max_no_improvement < 1 or self.max_consecutive_failures < 1:
            raise ValueError("experiment budget values must be positive")
        return self

    def can_continue(self, *, started_at: float, completed: int, no_improvement: int, consecutive_failures: int) -> tuple[bool, str | None]:
        if completed >= self.max_trials:
            return False, "max_trials"
        if time.monotonic() - started_at >= self.max_runtime_seconds:
            return False, "max_runtime_seconds"
        if no_improvement >= self.max_no_improvement:
            return False, "max_no_improvement"
        if consecutive_failures >= self.max_consecutive_failures:
            return False, "max_consecutive_failures"
        return True, None
