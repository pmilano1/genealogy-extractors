"""
Rate Limiter Utility
Provides thread-safe rate limiting with exponential backoff retry

WikiTree API Rate Limits (from Help:App_Policies):
- 200 requests per minute
- 4000 requests per hour
"""

import time
from threading import Lock
from functools import wraps


class RateLimiter:
    """Thread-safe rate limiter with exponential backoff

    Default settings are tuned for WikiTree API limits:
    - 200 requests/minute = 1 request per 0.3 seconds
    - We use 0.5s minimum delay to stay safely under the limit
    """

    def __init__(self, min_delay: float = 0.5, max_retries: int = 3, backoff_factor: float = 2.0):
        self.min_delay = min_delay
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.last_request_time = {}  # Per-source tracking
        self.request_counts = {}  # Per-source request counting
        self.lock = Lock()

    def wait(self, source: str = "default"):
        """Enforce minimum delay between requests for a source"""
        with self.lock:
            now = time.time()
            last_time = self.last_request_time.get(source, 0)
            elapsed = now - last_time

            if elapsed < self.min_delay:
                wait_time = self.min_delay - elapsed
                time.sleep(wait_time)

            self.last_request_time[source] = time.time()

            # Track request count
            if source not in self.request_counts:
                self.request_counts[source] = 0
            self.request_counts[source] += 1

    def retry_with_backoff(self, func, source: str = "default", *args, **kwargs):
        """Execute function with exponential backoff retry on failure

        Handles HTTP 429 (Too Many Requests) and similar rate limit errors.
        Uses exponential backoff: delay doubles with each retry attempt.
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                self.wait(source)
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if it's a rate limit error
                if '429' in error_str or 'too many' in error_str or 'rate limit' in error_str:
                    # Exponential backoff: 1s, 2s, 4s, 8s, etc.
                    wait_time = self.min_delay * (self.backoff_factor ** (attempt + 1))
                    print(f"[RATE LIMIT] {source}: Attempt {attempt + 1}/{self.max_retries}, "
                          f"waiting {wait_time:.1f}s before retry...")
                    time.sleep(wait_time)
                else:
                    # Non-rate-limit error, don't retry
                    raise

        # All retries exhausted
        print(f"[RATE LIMIT] {source}: All {self.max_retries} retries exhausted")
        raise last_exception

    def get_stats(self, source: str = "default") -> dict:
        """Get request statistics for a source"""
        return {
            "source": source,
            "request_count": self.request_counts.get(source, 0),
            "last_request": self.last_request_time.get(source, 0)
        }


# Global rate limiter instance
# Settings tuned for WikiTree API: 200/min, 4000/hr
# Using 0.5s delay = 120 requests/min (safely under 200 limit)
_rate_limiter = RateLimiter(min_delay=0.5, max_retries=3, backoff_factor=2.0)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return _rate_limiter

