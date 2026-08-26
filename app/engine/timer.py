"""Performance timing utilities for query pipeline."""

import time
from contextlib import contextmanager
from typing import Generator


class PipelineTimer:
    """Track timing for each pipeline stage."""
    
    def __init__(self):
        self.stages: dict[str, float] = {}
        self._start_times: dict[str, float] = {}
    
    @contextmanager
    def stage(self, name: str) -> Generator[None, None, None]:
        """Context manager to time a stage."""
        start = time.perf_counter()
        self._start_times[name] = start
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000  # ms
            self.stages[name] = elapsed
    
    def total(self) -> float:
        """Total elapsed time across all stages."""
        return sum(self.stages.values())
    
    def summary(self) -> dict[str, float]:
        """Return timing summary."""
        return {
            **self.stages,
            "total_ms": self.total()
        }


# Global timer instance (per-request in real app)
timer = PipelineTimer()
