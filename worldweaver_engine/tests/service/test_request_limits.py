from __future__ import annotations

from src.services.request_limits import FixedWindowRateLimiter


def test_fixed_window_rate_limiter_resets_each_minute():
    limiter = FixedWindowRateLimiter()

    assert limiter.allow("login:visitor", limit=2, now=100.0)[0] is True
    assert limiter.allow("login:visitor", limit=2, now=101.0)[0] is True
    allowed, retry_after = limiter.allow("login:visitor", limit=2, now=102.0)
    assert allowed is False
    assert retry_after == 18
    assert limiter.allow("login:visitor", limit=2, now=120.0)[0] is True


def test_zero_limit_disables_rate_limiter():
    limiter = FixedWindowRateLimiter()
    assert limiter.allow("login:visitor", limit=0, now=100.0) == (True, 0)
