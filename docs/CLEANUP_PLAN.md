# Directory Cleanup Plan

## Keep (Production Files)
- extract.py (main entry point)
- cdp_client.py (CDP fetching)
- extraction/ (all extractors)
- tests/fixtures/ (test data)

## Move to docs/
- All .md files except README.md

## Delete (Obsolete/Duplicate)
- Old CDP modules: *_cdp.py (replaced by extract.py)
- Old source modules: findagrave.py, geneanet.py, etc. (replaced by extractors)
- Old test scripts: test_*.py (replaced by extract.py --test)
- Example scripts: example_*.py, run_*.py
- Utility scripts: analyze_*.py, discover_*.py, generate_*.py, query_*.py
- Old infrastructure: base.py, rate_limiter.py, reporter.py, search_cli.py, cdp_orchestrator.py, cdp_search_cli.py
- Test results: test_results.json, E2E_TEST_RESULTS.md

## New Structure
```
scripts/sources/
├── README.md                    # Main documentation
├── extract.py                   # Production entry point
├── cdp_client.py               # CDP fetching utility
├── extraction/                 # Extractor modules
│   ├── __init__.py
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
    ├── ARCHITECTURE.md
    ├── QUICK_START.md
    └── ...
```
