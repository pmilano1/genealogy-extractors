# Rate Limiting & Reporting Guide

## Overview

The reporting system captures **every search attempt** with full context, allowing you to:
- Review what was searched and where
- Understand why searches succeeded or failed
- Plan follow-up research based on detailed logs
- Track rate limiting and API usage

## Files Generated

### 1. `search_log.jsonl` (Machine-readable)
One JSON object per line, each containing:
- `timestamp`: When the search was performed
- `source`: Which database (geneanet, wikitree, freebmd, etc.)
- `surname` / `given_name`: Who was searched for
- `result`: FOUND_X_MATCHES, NO_MATCH, ERROR, etc.
- `wait_time_seconds`: How long we waited for rate limiting
- `search_params`: Exact parameters sent to the source
- `url`: The search URL (for manual follow-up)
- `response_snippet`: First 500 chars of response (for debugging)
- `details`: Additional info (match count, confidence, etc.)

### 2. `detailed_results.md` (Human-readable)
Markdown file with formatted search results, organized chronologically:
```
## 2025-12-28T14:32:15.123456 - geneanet
**Person**: John Smith
**Result**: FOUND_3_MATCHES
**Wait Time**: 2.50s
**URL**: https://geneanet.org/search?...
**Search Parameters**:
  - surname: Smith
  - given_name: John
**Details**:
  - match_count: 3
  - first_match: John Smith (1850-1920)
```

### 3. `search_summary.json` (Statistics)
Aggregated statistics including:
- Total searches, errors, wait time
- Breakdown by source (with average wait times)
- Breakdown by result type
- Per-person summary (which sources found them)

### 4. `errors.jsonl` (Error tracking)
Detailed error logs with:
- Error type and message
- Traceback for debugging
- URL and search parameters that caused the error

## Usage Example

```python
from rate_limiter import RateLimiter
from reporter import SearchReporter

# Initialize
rate_limiter = RateLimiter()
reporter = SearchReporter(log_dir=".logs")

# Before each search
wait_time = rate_limiter.wait_if_needed("geneanet")

try:
    # Perform search...
    results = search_geneanet("Smith", "John")
    
    # Log success
    reporter.log_search(
        source="geneanet",
        surname="Smith",
        given_name="John",
        result=f"FOUND_{len(results)}_MATCHES",
        wait_time=wait_time,
        search_params={"surname": "Smith", "given_name": "John"},
        url="https://geneanet.org/search?...",
        response_snippet=str(results)[:500],
        details={
            "match_count": len(results),
            "first_match": results[0] if results else None
        }
    )
    
    # Record for rate limiting
    rate_limiter.record_request("geneanet")
    
except Exception as e:
    # Log error
    reporter.log_error(
        source="geneanet",
        surname="Smith",
        given_name="John",
        error_type=type(e).__name__,
        error_message=str(e),
        traceback=traceback.format_exc()
    )

# At the end
reporter.print_summary()
```

## Rate Limiting Configuration

Default limits per source:
- **Geneanet**: 3 requests/10s, 60/hour, 3s minimum delay
- **WikiTree**: 10 requests/10s, 200/hour, 1s minimum delay
- **FreeBMD**: 5 requests/10s, 100/hour, 2s minimum delay
- **Antenati**: 4 requests/10s, 80/hour, 2.5s minimum delay
- **Find A Grave**: 8 requests/10s, 150/hour, 1.5s minimum delay

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

## Follow-up Research Workflow

1. **Run initial searches** with reporting enabled
2. **Review `detailed_results.md`** to see what was found
3. **Check `search_summary.json`** for statistics
4. **For promising leads**: Use the logged URLs to manually investigate
5. **For errors**: Check `errors.jsonl` to understand what went wrong
6. **Plan next steps** based on which sources had results

## Key Information Captured for Follow-up

Each search log includes:
- ✅ Exact search parameters used
- ✅ Direct URL to results (for manual verification)
- ✅ Response preview (first 500 chars)
- ✅ Confidence/match details
- ✅ Timestamp (for chronological research)
- ✅ Error details if search failed

This allows you to:
- Manually verify any automated findings
- Try different search parameters based on what was logged
- Understand why certain sources didn't find results
- Build a complete audit trail of research

