"""
Rate Limiter Utility
Provides thread-safe rate limiting with exponential backoff retry

WikiTree API Rate Limits (from Help:App_Policies):
- 200 requests per minute
- 4000 requests per hour
- Returns Retry-After header on 429 responses
"""

import time
from threading import Lock
from functools import wraps
import requests


class RateLimiter:
    """Thread-safe rate limiter with Retry-After header support

    Default settings are tuned for WikiTree API limits:
    - 200 requests/minute = 1 request per 0.3 seconds
    - We use 1.0s minimum delay for parallel requests to stay safely under limit
    """

    def __init__(self, min_delay: float = 1.0, max_retries: int = 5, backoff_factor: float = 2.0):
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
        """Execute function with Retry-After header support and exponential backoff

        Handles HTTP 429 (Too Many Requests) responses:
        1. First checks for Retry-After header and uses that value
        2. Falls back to exponential backoff if no header present
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                self.wait(source)
                return func(*args, **kwargs)
            except requests.exceptions.HTTPError as e:
                last_exception = e
                response = getattr(e, 'response', None)

                if response is not None and response.status_code == 429:
                    # Check for Retry-After header
                    retry_after = response.headers.get('Retry-After')

                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                            print(f"[RATE LIMIT] {source}: Server says wait {wait_time}s (Retry-After header)")
                        except ValueError:
                            # Retry-After might be a date string, fall back to backoff
                            wait_time = self.min_delay * (self.backoff_factor ** (attempt + 1))
                            print(f"[RATE LIMIT] {source}: Attempt {attempt + 1}/{self.max_retries}, "
                                  f"waiting {wait_time:.1f}s...")
                    else:
                        # No Retry-After header, use exponential backoff
                        wait_time = self.min_delay * (self.backoff_factor ** (attempt + 1))
                        print(f"[RATE LIMIT] {source}: Attempt {attempt + 1}/{self.max_retries}, "
                              f"waiting {wait_time:.1f}s (no Retry-After header)...")

                    time.sleep(wait_time)
                else:
                    # Non-429 HTTP error, don't retry
                    raise

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if it's a rate limit error (non-requests exception)
                if '429' in error_str or 'too many' in error_str or 'rate limit' in error_str:
                    wait_time = self.min_delay * (self.backoff_factor ** (attempt + 1))
                    print(f"[RATE LIMIT] {source}: Attempt {attempt + 1}/{self.max_retries}, "
                          f"waiting {wait_time:.1f}s...")
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
# Using 1.0s delay for parallel requests = 60 requests/min per thread
# With 8 threads, worst case ~480/min but staggered start times help
_rate_limiter = RateLimiter(min_delay=1.0, max_retries=5, backoff_factor=2.0)


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance"""
    return _rate_limiter

