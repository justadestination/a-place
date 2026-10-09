"""Global rate limiting and abuse protection for ShadeNet and NightCal.

Task 6.7:
    Beyond tally limits: login attempts, submissions, API — all rate-limited
    with sane defaults and operator overrides.
    Done when: limits documented; abuse test suite passes.
    Tests: [abuse] flood each endpoint, assert 429s and no data corruption.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from shadenet.logging import get_logger

logger = get_logger("shadenet.ratelimit")

# Default rate limits: (capacity, refill_rate_per_sec)
# capacity = max burst, refill_rate = sustained rate
DEFAULT_LIMITS = {
    "api": (60.0, 1.0),          # 60 burst, 1 req/sec sustained
    "login": (5.0, 0.1),         # 5 burst, 1 req every 10s
    "submissions": (15.0, 0.5),  # 15 burst, 1 write every 2s
    "operator": (1000.0, 100.0), # Operator endpoints
}


@dataclass
class TokenBucket:
    capacity: float
    refill_rate: float
    tokens: float = field(init=False)
    last_update: float = field(init=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_update = time.time()

    def consume(self, amount: float = 1.0) -> tuple[bool, int]:
        """Try to consume tokens. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)

        if self.tokens >= amount:
            self.tokens -= amount
            return True, 0

        # Calculate wait time needed for 1 token
        deficit = amount - self.tokens
        retry_after = max(1, int(deficit / self.refill_rate) + 1)
        return False, retry_after


class RateLimiter:
    def __init__(self, limits: Optional[dict[str, tuple[float, float]]] = None) -> None:
        self.limits = limits or dict(DEFAULT_LIMITS)
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()
        self._exempt_tokens: set[str] = set()

    def add_operator_override(self, token_or_key: str) -> None:
        """Register an operator token/key that is exempt from rate limits."""
        with self._lock:
            self._exempt_tokens.add(token_or_key.strip())

    def remove_operator_override(self, token_or_key: str) -> None:
        """Remove an exempt token/key."""
        with self._lock:
            self._exempt_tokens.discard(token_or_key.strip())

    def is_exempt(self, token_or_key: Optional[str]) -> bool:
        """Check if an authorization or operator token is exempt."""
        if not token_or_key:
            return False
        with self._lock:
            return token_or_key.strip() in self._exempt_tokens

    def check(
        self,
        client_id: str,
        category: str = "api",
        cost: float = 1.0,
        auth_token: Optional[str] = None,
    ) -> tuple[bool, int]:
        """Check whether a request is allowed. Returns (allowed, retry_after)."""
        if self.is_exempt(auth_token):
            return True, 0

        cap_rate = self.limits.get(category, self.limits.get("api", (60.0, 1.0)))
        bucket_key = f"{category}:{client_id}"

        with self._lock:
            if bucket_key not in self._buckets:
                self._buckets[bucket_key] = TokenBucket(
                    capacity=cap_rate[0],
                    refill_rate=cap_rate[1],
                )
            bucket = self._buckets[bucket_key]
            allowed, retry_after = bucket.consume(cost)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                client_id=client_id,
                category=category,
                retry_after=retry_after,
            )

        return allowed, retry_after

    def reset(self) -> None:
        """Reset all rate limiting state."""
        with self._lock:
            self._buckets.clear()


# Global singleton limiter
limiter = RateLimiter()
