# Rate Protection & Reporting System

## What Was Created

### 1. **rate_limiter.py** - Rate Protection
Prevents API throttling and bans with:
- **Minimum delay between requests** (source-specific)
- **Burst limiting** (max requests in 10-second window)
- **Hourly request tracking** (prevents exceeding limits)
- **Configurable per source** (Geneanet, WikiTree, FreeBMD, etc.)

**Key Methods**:
- `wait_if_needed(source)` - Waits before request if needed
- `record_request(source)` - Records that request was made
- `get_stats(source)` - Shows current rate limit status

### 2. **reporter.py** - Comprehensive Logging
Captures every search with full context for follow-up research:

**Logs Generated**:
- `search_log.jsonl` - Machine-readable JSON (one per line)
- `detailed_results.md` - Human-readable markdown
- `search_summary.json` - Statistics and aggregates
- `errors.jsonl` - Error tracking with context

**Captured Information**:
- Timestamp of each search
- Source database
- Person searched for (surname, given_name)
- Result (FOUND_X_MATCHES, NO_MATCH, ERROR)
- Wait time (for rate limiting)
- Search parameters used
- Direct URL to results
- Response preview (first 500 chars)
- Additional details (match count, confidence, etc.)
- Full error details if search failed

### 3. **example_with_reporting.py** - Integration Example
Shows how to use both systems together in a real search workflow

### 4. **REPORTING_GUIDE.md** - Complete Documentation
Explains:
- What each log file contains
- How to use the reporting system
- Rate limiting configuration
- Follow-up research workflow
- Key information captured for manual verification

## Quick Start

```python
from rate_limiter import RateLimiter
from reporter import SearchReporter

# Initialize
rate_limiter = RateLimiter()
reporter = SearchReporter(log_dir=".logs")

# Before each search
wait_time = rate_limiter.wait_if_needed("geneanet")

# Perform search...
results = search_geneanet("Smith", "John")

# Log with full details
reporter.log_search(
    source="geneanet",
    surname="Smith",
    given_name="John",
    result=f"FOUND_{len(results)}_MATCHES",
    wait_time=wait_time,
    search_params={"surname": "Smith", "given_name": "John"},
    url="https://geneanet.org/search?...",
    response_snippet=str(results)[:500],
    details={"match_count": len(results)}
)

# Record for rate limiting
rate_limiter.record_request("geneanet")

# At the end
reporter.print_summary()
```

## Default Rate Limits

| Source | Min Delay | Burst Limit | Per Hour |
|--------|-----------|-------------|----------|
| Geneanet | 3.0s | 3/10s | 60 |
| WikiTree | 1.0s | 10/10s | 200 |
| FreeBMD | 2.0s | 5/10s | 100 |
| Antenati | 2.5s | 4/10s | 80 |
| Find A Grave | 1.5s | 8/10s | 150 |

## Log Files Location

All logs saved to `.logs/` directory:
- `search_log.jsonl` - Full search history (machine-readable)
- `detailed_results.md` - Formatted results (human-readable)
- `search_summary.json` - Statistics
- `errors.jsonl` - Error tracking

## For Follow-up Research

The logs contain everything needed to:
1. **Verify results manually** - Each log has the direct URL
2. **Understand failures** - Error logs show what went wrong
3. **Try different parameters** - Logged search params show what was used
4. **Track progress** - Summary shows what's been searched
5. **Plan next steps** - See which sources found results

## Integration with CDP Modules

To integrate with existing CDP modules:

```python
# In your CDP module
from rate_limiter import RateLimiter
from reporter import SearchReporter

class GeneanetModule:
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.reporter = SearchReporter()
    
    def search(self, surname, given_name):
        wait_time = self.rate_limiter.wait_if_needed("geneanet")
        # ... perform search ...
        self.reporter.log_search(...)
        self.rate_limiter.record_request("geneanet")
```

This ensures all searches are protected and logged automatically.

