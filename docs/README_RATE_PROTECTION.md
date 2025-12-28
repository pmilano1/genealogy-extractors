# Rate Protection & Comprehensive Reporting System

## What You Get

A complete system for **safe, protected searches** with **detailed logging** for follow-up research:

### 🛡️ Rate Protection
- **Prevents API throttling** - Respects minimum delays between requests
- **Burst limiting** - Prevents exceeding request limits in short windows
- **Hourly tracking** - Monitors total requests per hour
- **Source-specific configs** - Different limits for each database

### 📊 Comprehensive Reporting
- **Every search logged** - Nothing is lost
- **Full context captured** - Parameters, URLs, responses, errors
- **Multiple formats** - JSON (machine), Markdown (human), Statistics
- **Follow-up ready** - All info needed for manual verification

## Files Created

| File | Purpose |
|------|---------|
| `rate_limiter.py` | Rate limiting logic |
| `reporter.py` | Search logging and reporting |
| `query_logs.py` | Analyze logs for follow-up research |
| `example_with_reporting.py` | Integration example |
| `REPORTING_GUIDE.md` | Detailed documentation |
| `RATE_PROTECTION_SUMMARY.md` | Quick reference |

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

## Log Files Generated

All saved to `.logs/` directory:

### `search_log.jsonl` - Machine-readable
One JSON object per line with:
- Timestamp, source, person name
- Result (FOUND_X_MATCHES, NO_MATCH, ERROR)
- Wait time, search parameters
- URL, response preview
- Additional details

### `detailed_results.md` - Human-readable
Formatted markdown with:
- Chronological search history
- Search parameters for each attempt
- Direct URLs for manual verification
- Error details with context

### `search_summary.json` - Statistics
Aggregated data:
- Total searches, errors, wait time
- Breakdown by source
- Breakdown by result type
- Per-person summary

### `errors.jsonl` - Error tracking
Detailed error logs with:
- Error type and message
- Traceback for debugging
- URL and parameters that caused error

## For Follow-up Research

Use `query_logs.py` to analyze logs:

```python
from query_logs import LogAnalyzer

analyzer = LogAnalyzer()

# Find all matches for a person
matches = analyzer.find_matches_for_person("Smith", "John")

# Get URLs for manual verification
urls = analyzer.get_urls_for_person("Smith", "John")

# Find sources that had errors (should retry)
retry = analyzer.get_sources_to_retry("Smith", "John")

# Print detailed report
analyzer.print_person_report("Smith", "John")
```

## Default Rate Limits

| Source | Min Delay | Burst | Per Hour |
|--------|-----------|-------|----------|
| Geneanet | 3.0s | 3/10s | 60 |
| WikiTree | 1.0s | 10/10s | 200 |
| FreeBMD | 2.0s | 5/10s | 100 |
| Antenati | 2.5s | 4/10s | 80 |
| Find A Grave | 1.5s | 8/10s | 150 |

Customize with:
```python
custom_config = {
    "geneanet": {
        "min_delay": 5.0,
        "max_requests_per_hour": 40,
        "burst_limit": 2,
    }
}
rate_limiter = RateLimiter(config=custom_config)
```

## Key Features

✅ **Safe** - Respects API rate limits  
✅ **Logged** - Every search recorded with full context  
✅ **Detailed** - Captures parameters, URLs, responses, errors  
✅ **Queryable** - Analyze logs to plan follow-up research  
✅ **Flexible** - Customizable per source  
✅ **Transparent** - Human-readable markdown logs  

## Integration with CDP Modules

Add to your existing CDP modules:

```python
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

All searches automatically protected and logged!

