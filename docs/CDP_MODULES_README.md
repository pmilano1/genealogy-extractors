# CDP Genealogy Modules

Complete Chrome DevTools Protocol (CDP) integration for mainstream genealogy sites.

## Supported Sources

| Source | Module | Type | Notes |
|--------|--------|------|-------|
| **Antenati** | `antenati_cdp.py` | Italian records | Birth, marriage, death records |
| **Geneanet** | `geneanet_cdp.py` | Multi-country | Cloudflare protection (requires CDP) |
| **WikiTree** | `wikitree_cdp.py` | API-based | Uses WikiTree API (no CDP needed) |
| **Find A Grave** | `findagrave_cdp.py` | Cemetery records | Burial and memorial records |
| **FreeBMD** | `freebmd_cdp.py` | UK records | Birth, marriage, death records |
| **FamilySearch** | `familysearch_cdp.py` | Multi-country | Largest genealogy database |
| **Ancestry** | `ancestry_cdp.py` | Multi-country | Requires subscription |
| **MyHeritage** | `myheritage_cdp.py` | Multi-country | DNA + records |

## Architecture

### CDP Orchestrator (`cdp_orchestrator.py`)

Main orchestrator that handles:
- Chrome DevTools Protocol interactions
- Rate limiting (prevents API throttling)
- Search logging and reporting
- Error handling and recovery

```python
from cdp_orchestrator import CDPOrchestrator
from antenati_cdp import AntenatiCDPSource

orchestrator = CDPOrchestrator(log_dir=".logs")
source = AntenatiCDPSource()

result = orchestrator.search_source(
    source,
    surname="Smith",
    given_name="John",
    location="London",
    year_min=1850,
    year_max=1920
)
```

### Source Modules

Each source module provides:
- `build_url()` - Constructs search URL with parameters
- `check_results()` - Parses results and detects matches

```python
from antenati_cdp import AntenatiCDPSource

source = AntenatiCDPSource()
url = source.build_url("Smith", "John", "London", 1850, 1920)
found, message = source.check_results(page_content)
```

## Integration with Chrome DevTools MCP

The orchestrator uses these MCP tools:
- `navigate_page_chrome-devtools` - Navigate to URL
- `take_snapshot_chrome-devtools` - Get page content
- `fill_chrome-devtools` - Fill form fields
- `click_chrome-devtools` - Click elements
- `wait_for_chrome-devtools` - Wait for text

## Usage Examples

### Search Single Source

```python
from cdp_orchestrator import CDPOrchestrator
from antenati_cdp import AntenatiCDPSource

orchestrator = CDPOrchestrator()
source = AntenatiCDPSource()

result = orchestrator.search_source(
    source,
    surname="Iacobelli",
    given_name="Louisa",
    location="Pietradefusi",
    year_min=1800,
    year_max=1900
)

print(f"Found: {result['found']}")
print(f"Message: {result['message']}")
```

### Search Multiple Sources

```python
from cdp_orchestrator import CDPOrchestrator
from antenati_cdp import AntenatiCDPSource
from geneanet_cdp import GeneanetCDPSource
from familysearch_cdp import FamilySearchCDPSource

orchestrator = CDPOrchestrator()
sources = [
    AntenatiCDPSource(),
    GeneanetCDPSource(),
    FamilySearchCDPSource(),
]

result = orchestrator.search_person(
    surname="Smith",
    given_name="John",
    sources=sources,
    location="London",
    year_min=1850,
    year_max=1920
)

print(f"Found in: {result['found_in']}")
print(f"Errors: {result['errors']}")
```

### Generate Report

```python
orchestrator = CDPOrchestrator()
# ... run searches ...
report = orchestrator.generate_report()
print(report)
```

## Testing

Run integration tests:

```bash
python3 scripts/sources/test_cdp_modules.py
```

Tests:
1. URL building for all sources
2. Result checking logic
3. Orchestrator functionality

## Rate Limiting

Integrated rate limiter prevents API throttling:
- Minimum delay between requests (configurable per source)
- Burst limit (max requests in 10 seconds)
- Hourly request tracking

## Logging

All searches logged to `.logs/`:
- `search_log.jsonl` - Machine-readable log
- `detailed_results.md` - Human-readable results
- `search_summary.json` - Statistics
- `errors.jsonl` - Error tracking

## Notes

- **Geneanet**: Requires CDP due to Cloudflare protection
- **WikiTree**: Uses API instead of CDP
- **FamilySearch**: Some records require login
- **Ancestry**: Most records require subscription
- **MyHeritage**: Some features require subscription

