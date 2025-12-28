# Genealogy Source Extraction

Production-ready extraction system for genealogy records from 7 major sources.

## Quick Start

```bash
# Test all sources (uses fixtures)
python extract.py --test

# Test specific source with details
python extract.py --test --source findagrave --verbose

# Production: search one source
python extract.py --surname Smith --given-name John --birth-year 1850 --source findagrave

# Production: search all sources and save results
python extract.py --surname Dubois --given-name Marie --birth-year 1880 --all-sources --output results.json
```

## Supported Sources

| Source | Status | Records | Data Quality | Access Method |
|--------|--------|---------|--------------|---------------|
| **Find A Grave** | ✅ Working | 20 | Full names, birth/death years, complete locations | WEB_FETCH |
| **Geneanet** | ✅ Working | 20 | Full names, birth years, locations | CDP_BROWSER |
| **WikiTree** | ✅ Working | 20 | Full names (with surnames), birth years, locations | API |
| **Ancestry** | ✅ Working | 20 | Clean names, birth years, locations | CDP_BROWSER |
| **FamilySearch** | ✅ Working | 20 | Full names, birth years, clean locations | WEB_FETCH |
| **Antenati** | ⚠️ Limited | 10 | Names only (no birth years - nominative search) | CDP_BROWSER |
| **MyHeritage** | ❌ Disabled | - | Requires subscription, fixture needs replacement | MANUAL_ONLY |

## Data Quality Improvements (Latest)

- **Names**: Proper spacing, no concatenation (e.g., "Mary Ewald Johnson" not "MaryEwaldJohnson")
- **Locations**: Complete multi-part locations (e.g., "Beatrice, Gage County, Nebraska")
- **WikiTree**: Surnames extracted from Name field (e.g., "Smith-269952" → "John Smith")
- **Ancestry**: Clean names with special characters removed
- **FamilySearch**: Event type prefixes removed from locations

## Directory Structure

```
scripts/sources/
├── README.md                    # This file
├── extract.py                   # Main entry point
├── cdp_client.py               # Chrome DevTools Protocol client
├── extraction/                 # Extractor modules
│   ├── base_extractor.py
│   ├── find_a_grave_extractor.py
│   ├── geneanet_extractor.py
│   ├── antenati_extractor.py
│   ├── familysearch_extractor.py
│   ├── wikitree_extractor.py
│   ├── ancestry_extractor.py
│   └── myheritage_extractor.py
├── tests/
│   └── fixtures/               # Test HTML/JSON files
└── docs/                       # Documentation
```

## Requirements

- Python 3.8+
- Chrome browser with remote debugging enabled (for production mode)
- BeautifulSoup4, requests

## Test Results

Last test: **6 sources, 110 records extracted** (MyHeritage disabled)

## Known Limitations

1. **Antenati**: Nominative search doesn't return birth years
2. **MyHeritage**: Requires subscription, has bot detection, needs manual browser access
3. **FamilySearch**: Some locations include dates (acceptable)

See `docs/` for detailed architecture and implementation documentation.
