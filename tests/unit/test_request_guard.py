import pytest
import time
from collections import deque

from app.main import _check_rate_limit, RATE_LIMIT_QUERIES, RATE_LIMIT_WINDOW_SECONDS


def test_rate_limit_allows_under_threshold():
    timestamps: deque = deque()
    for _ in range(RATE_LIMIT_QUERIES - 1):
        timestamps.append(time.monotonic() - 1)
    # Should NOT raise
    _check_rate_limit(timestamps)


def test_rate_limit_blocks_at_threshold():
    timestamps: deque = deque()
    now = time.monotonic()
    for _ in range(RATE_LIMIT_QUERIES):
        timestamps.append(now - 1)  # all within the window
    with pytest.raises(RuntimeError, match="Rate limit"):
        _check_rate_limit(timestamps)


def test_rate_limit_resets_after_window():
    timestamps: deque = deque()
    old = time.monotonic() - RATE_LIMIT_WINDOW_SECONDS - 1
    for _ in range(RATE_LIMIT_QUERIES):
        timestamps.append(old)  # all outside the window
    # Should NOT raise (old timestamps expire)
    _check_rate_limit(timestamps)
