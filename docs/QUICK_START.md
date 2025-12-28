# Quick Start Guide

## Run Searches in 3 Steps

### 1. Create a CSV file with people to search

```csv
surname,given_name
Smith,John
Johnson,Mary
Williams,Robert
```

Save as `my_people.csv`

### 2. Run the CLI

```bash
python3 scripts/sources/search_cli.py \
  --people my_people.csv \
  --sources geneanet,wikitree,freebmd,antenati,findagrave
```

### 3. Review Results

```bash
# Human-readable results
cat .logs/detailed_results.md

# Statistics
cat .logs/search_summary.json | jq .

# Errors (if any)
cat .logs/errors.jsonl
```

## CLI Options

```bash
python3 scripts/sources/search_cli.py \
  --people <csv_file>              # Required: CSV with surname, given_name
  --sources <source1,source2,...>  # Optional: comma-separated sources
  --log-dir <directory>            # Optional: where to save logs (default: .logs)
```

## Available Sources

- `geneanet` - French/Italian records
- `wikitree` - Global genealogy database
- `freebmd` - UK vital records
- `antenati` - Italian records
- `findagrave` - Cemetery records

## Analyze Results

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

## Log Files

| File | Format | Purpose |
|------|--------|---------|
| `search_log.jsonl` | JSON | Machine-readable search history |
| `detailed_results.md` | Markdown | Human-readable results |
| `search_summary.json` | JSON | Statistics and aggregates |
| `errors.jsonl` | JSON | Error tracking |

## Example: Test Run

```bash
# Run test with 10 people × 5 sources
python3 scripts/sources/search_cli.py \
  --people scripts/sources/test_people.csv \
  --sources geneanet,wikitree,freebmd,antenati,findagrave
```

Results from test run:
- **71 searches** completed
- **42 found results** (59%)
- **3 errors** (4.2%)
- **43.6 seconds** total (includes rate limiting)

## Customize Rate Limits

```python
from rate_limiter import RateLimiter

custom_config = {
    "geneanet": {
        "min_delay": 5.0,           # Wait 5 seconds between requests
        "max_requests_per_hour": 40, # Max 40 requests per hour
        "burst_limit": 2,            # Max 2 requests in 10 seconds
    }
}

rate_limiter = RateLimiter(config=custom_config)
```

## Integration with Real APIs

Replace the `simulate_search()` function in `search_cli.py` with actual API calls:

```python
def simulate_search(source: str, surname: str, given_name: str) -> dict:
    """Replace with real API calls"""
    
    if source == "geneanet":
        return geneanet_search(surname, given_name)
    elif source == "wikitree":
        return wikitree_search(surname, given_name)
    # ... etc
```

## Troubleshooting

### No results found?
- Check `.logs/detailed_results.md` for what was searched
- Check `.logs/errors.jsonl` for any errors
- Verify search parameters in `.logs/search_summary.json`

### Rate limiting too aggressive?
- Customize config in `rate_limiter.py`
- Adjust `min_delay` and `max_requests_per_hour`

### Want to retry failed searches?
- Use `LogAnalyzer.get_sources_to_retry()`
- Re-run with just those sources

## Files

```
scripts/sources/
├── search_cli.py              # Main CLI tool
├── rate_limiter.py            # Rate limiting
├── reporter.py                # Logging
├── query_logs.py              # Analysis
├── test_people.csv            # Example data
├── QUICK_START.md             # This file
├── README_RATE_PROTECTION.md  # Full documentation
└── TEST_RESULTS.md            # Test results
```

## Next Steps

1. Create your own `people.csv` file
2. Run searches with `search_cli.py`
3. Review results in `.logs/`
4. Use `LogAnalyzer` for follow-up research
5. Integrate with real API calls

That's it! 🚀

