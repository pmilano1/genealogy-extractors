# Rate Protection & Reporting System Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Your Search Code                          │
│  (geneanet_module.py, wikitree_module.py, etc.)             │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│  RateLimiter     │    │   SearchReporter │
│  ────────────    │    │  ────────────    │
│ • wait_if_needed │    │ • log_search     │
│ • record_request │    │ • log_error      │
│ • get_stats      │    │ • generate_summary
└────────┬─────────┘    └────────┬─────────┘
         │                       │
         │                       │
    Prevents API              Captures
    Throttling               Everything
         │                       │
         └───────────┬───────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
    .logs/                   .logs/
    ├── search_log.jsonl     ├── detailed_results.md
    ├── errors.jsonl         ├── search_summary.json
    └── (machine-readable)   └── (human-readable)
                                  
                     ▼
            ┌──────────────────┐
            │  LogAnalyzer     │
            │  ────────────    │
            │ • find_matches   │
            │ • find_errors    │
            │ • get_urls       │
            │ • print_report   │
            └──────────────────┘
                     │
                     ▼
            Follow-up Research
            (Manual verification,
             retry errors, etc.)
```

## Data Flow

### 1. Search Execution
```
Your Code
   │
   ├─→ rate_limiter.wait_if_needed("source")
   │   └─→ Sleeps if needed (respects rate limits)
   │
   ├─→ Perform actual search
   │
   ├─→ reporter.log_search(...)
   │   └─→ Writes to search_log.jsonl
   │   └─→ Appends to detailed_results.md
   │
   └─→ rate_limiter.record_request("source")
       └─→ Updates request history
```

### 2. Reporting
```
reporter.print_summary()
   │
   ├─→ Reads search_log.jsonl
   ├─→ Reads errors.jsonl
   │
   ├─→ Generates search_summary.json
   │   └─→ Statistics by source
   │   └─→ Statistics by result
   │   └─→ Per-person summary
   │
   └─→ Prints formatted summary to console
```

### 3. Follow-up Analysis
```
LogAnalyzer
   │
   ├─→ find_matches_for_person()
   │   └─→ Returns all sources that found matches
   │
   ├─→ find_no_matches_for_person()
   │   └─→ Returns sources with NO_MATCH
   │
   ├─→ find_errors_for_person()
   │   └─→ Returns sources with errors
   │
   ├─→ get_urls_for_person()
   │   └─→ Returns URLs for manual verification
   │
   └─→ get_sources_to_retry()
       └─→ Returns sources that had errors
```

## Rate Limiting Logic

```
wait_if_needed(source):
   │
   ├─→ Check minimum delay since last request
   │   └─→ If elapsed < min_delay: sleep(min_delay - elapsed)
   │
   └─→ Check burst limit (max requests in 10 seconds)
       └─→ If recent_requests >= burst_limit: sleep(10 - oldest_request_age)
```

## Log File Formats

### search_log.jsonl
```json
{
  "timestamp": "2025-12-28T14:32:15.123456",
  "source": "geneanet",
  "surname": "Smith",
  "given_name": "John",
  "result": "FOUND_3_MATCHES",
  "wait_time_seconds": 2.5,
  "search_params": {"surname": "Smith", "given_name": "John"},
  "url": "https://geneanet.org/search?...",
  "response_snippet": "First 500 chars of response...",
  "details": {"match_count": 3, "first_match": "John Smith (1850-1920)"}
}
```

### detailed_results.md
```markdown
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

### search_summary.json
```json
{
  "generated_at": "2025-12-28T14:35:00",
  "total_searches": 45,
  "searches_with_results": 12,
  "searches_no_match": 30,
  "total_errors": 3,
  "total_wait_time": 125.5,
  "by_source": {
    "geneanet": {
      "count": 15,
      "total_wait_time": 45.0,
      "results": {"FOUND_3_MATCHES": 5, "NO_MATCH": 10}
    }
  },
  "by_person": {
    "John Smith": {
      "searches": ["geneanet", "wikitree"],
      "found_in": ["geneanet"]
    }
  }
}
```

## Integration Points

### With CDP Modules
```python
class GeneanetModule:
    def __init__(self):
        self.rate_limiter = RateLimiter()
        self.reporter = SearchReporter()
    
    def search(self, surname, given_name):
        wait_time = self.rate_limiter.wait_if_needed("geneanet")
        results = self._perform_search(surname, given_name)
        self.reporter.log_search(
            source="geneanet",
            surname=surname,
            given_name=given_name,
            result=f"FOUND_{len(results)}_MATCHES",
            wait_time=wait_time,
            # ... other details ...
        )
        self.rate_limiter.record_request("geneanet")
        return results
```

### With Orchestrator
```python
class SearchOrchestrator:
    def __init__(self):
        self.modules = {
            "geneanet": GeneanetModule(),
            "wikitree": WikiTreeModule(),
            "freebmd": FreeBMDModule(),
        }
        self.reporter = SearchReporter()
    
    def search_all(self, surname, given_name):
        for source, module in self.modules.items():
            results = module.search(surname, given_name)
        
        # Print summary at the end
        self.reporter.print_summary()
```

## Configuration

### Default Rate Limits
```python
{
    "geneanet": {
        "min_delay": 3.0,
        "max_requests_per_hour": 60,
        "burst_limit": 3,
    },
    "wikitree": {
        "min_delay": 1.0,
        "max_requests_per_hour": 200,
        "burst_limit": 10,
    },
    # ... more sources ...
}
```

### Custom Configuration
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

## Key Design Decisions

1. **Separate Concerns**
   - RateLimiter handles only rate limiting
   - SearchReporter handles only logging
   - LogAnalyzer handles only analysis

2. **Multiple Log Formats**
   - JSONL for machine processing
   - Markdown for human reading
   - JSON for statistics

3. **Full Context Capture**
   - Every search logged with parameters
   - URLs captured for manual verification
   - Errors logged with full traceback

4. **Flexible Configuration**
   - Per-source rate limits
   - Customizable without code changes
   - Sensible defaults provided

5. **Follow-up Ready**
   - All info needed for manual research
   - Easy to query logs
   - Clear error reporting

