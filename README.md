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

| Source | Status | Data Quality | Notes |
|--------|--------|--------------|-------|
| Find A Grave | ✅ Production | ⭐⭐⭐⭐⭐ | Full data (name, birth, death, location, URL) |
| Geneanet | ✅ Production | ⭐⭐⭐⭐⭐ | Full data (name, birth, death, location, URL) |
| FamilySearch | ✅ Production | ⭐⭐⭐⭐⭐ | Full data + parents |
| WikiTree | ✅ Production | ⭐⭐⭐⭐⭐ | Full data via API |
| Antenati | ✅ Production | ⭐⭐⭐ | Names only (nominative search) |
| Ancestry | ⚠️ Working | ⭐⭐ | Needs HTML parsing refinement |
| MyHeritage | ⚠️ Working | ⭐⭐ | Needs HTML parsing refinement |

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

Last test: 5 ancestors × 7 sources = **111 records extracted**

See `docs/` for detailed architecture and implementation documentation.
