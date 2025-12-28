# CDP Modules - Quick Start

## What's Included

✅ **8 Genealogy Source Modules** (CDP-based browser automation)
- Antenati (Italian records)
- Geneanet (Multi-country, Cloudflare protected)
- WikiTree (API-based)
- Find A Grave (Cemetery records)
- FreeBMD (UK vital records)
- FamilySearch (Largest genealogy database)
- Ancestry (Major platform, subscription)
- MyHeritage (DNA + records)

✅ **CDP Orchestrator** (handles all browser interactions)
✅ **Rate Limiter** (prevents API throttling)
✅ **Reporter** (logs all searches)
✅ **Integration Tests** (verify all modules work)

## Files Created

```
scripts/sources/
├── cdp_orchestrator.py          # Main orchestrator
├── antenati_cdp.py              # Antenati module
├── geneanet_cdp.py              # Geneanet module
├── wikitree_cdp.py              # WikiTree module
├── findagrave_cdp.py            # Find A Grave module
├── freebmd_cdp.py               # FreeBMD module
├── familysearch_cdp.py          # FamilySearch module (NEW)
├── ancestry_cdp.py              # Ancestry module (NEW)
├── myheritage_cdp.py            # MyHeritage module (NEW)
├── test_cdp_modules.py          # Integration tests
├── CDP_MODULES_README.md        # Full documentation
└── CDP_QUICK_START.md           # This file
```

## Basic Usage

### Search Single Source

```python
from cdp_orchestrator import CDPOrchestrator
from antenati_cdp import AntenatiCDPSource

orchestrator = CDPOrchestrator()
source = AntenatiCDPSource()

result = orchestrator.search_source(
    source,
    surname="Smith",
    given_name="John",
    location="London",
    year_min=1850,
    year_max=1920
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
```

## Run Tests

```bash
python3 scripts/sources/test_cdp_modules.py
```

Output shows:
- URL building for all 8 sources
- Result checking logic
- Orchestrator functionality

## How It Works

1. **Source Module** builds search URL with parameters
2. **CDP Orchestrator** navigates to URL using Chrome DevTools
3. **Orchestrator** takes snapshot of results page
4. **Source Module** parses results and detects matches
5. **Reporter** logs search with full context
6. **Rate Limiter** prevents API throttling

## Integration with Chrome DevTools MCP

The orchestrator uses these MCP tools:
- `navigate_page_chrome-devtools` - Go to URL
- `take_snapshot_chrome-devtools` - Get page content
- `fill_chrome-devtools` - Fill form fields
- `click_chrome-devtools` - Click buttons
- `wait_for_chrome-devtools` - Wait for content

## Key Features

✅ **Rate Limiting** - Prevents API throttling
✅ **Comprehensive Logging** - Every search logged
✅ **Error Handling** - Graceful error recovery
✅ **Multi-Source** - Search across 8 genealogy sites
✅ **Flexible** - Easy to add new sources
✅ **Tested** - Integration tests included

## Next Steps

1. Review `CDP_MODULES_README.md` for full documentation
2. Run `test_cdp_modules.py` to verify setup
3. Use `CDPOrchestrator` to automate searches
4. Check `.logs/` for search results and statistics

## Notes

- **Geneanet**: Requires CDP (Cloudflare protection)
- **WikiTree**: Uses API (no CDP needed)
- **FamilySearch**: Some records require login
- **Ancestry**: Most records require subscription
- **MyHeritage**: Some features require subscription

