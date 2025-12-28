# Clean Modular Architecture

## Directory Structure

```
scripts/sources/
├── core/                          # Core infrastructure (NEW)
│   ├── __init__.py
│   ├── cache.py                   # PersistentSearchCache with 30-day TTL
│   ├── graphql_client.py          # GraphQL API client
│   ├── rate_limiter.py            # Rate limiting (KEEP existing)
│   └── progress.py                # Progress bar and ETA
│
├── extraction/                    # Record extraction & scoring (NEW)
│   ├── __init__.py
│   ├── base_extractor.py          # Base class for all extractors
│   ├── find_a_grave_extractor.py  # Find A Grave parser
│   ├── antenati_extractor.py      # Antenati parser
│   ├── geneanet_extractor.py      # Geneanet parser
│   ├── wikitree_extractor.py      # WikiTree parser
│   ├── freebmd_extractor.py       # FreeBMD parser
│   ├── familysearch_extractor.py  # FamilySearch parser
│   ├── ancestry_extractor.py      # Ancestry parser
│   └── myheritage_extractor.py    # MyHeritage parser
│
├── variants/                      # Name & location variants (NEW)
│   ├── __init__.py
│   ├── name_variants.py           # Name translation & phonetic matching
│   ├── location_expander.py       # Location hierarchy & historical names
│   └── data/                      # Translation databases
│       ├── name_translations.json
│       └── location_hierarchy.json
│
├── sources/                       # Source modules (REFACTORED)
│   ├── __init__.py
│   ├── base_source.py             # Base class (KEEP existing base.py)
│   ├── antenati.py                # Antenati source
│   ├── geneanet.py                # Geneanet source
│   ├── wikitree.py                # WikiTree source
│   ├── findagrave.py              # Find A Grave source
│   ├── freebmd.py                 # FreeBMD source
│   ├── familysearch.py            # FamilySearch source
│   ├── ancestry.py                # Ancestry source
│   └── myheritage.py              # MyHeritage source
│
├── orchestration/                 # Search orchestration (NEW)
│   ├── __init__.py
│   ├── orchestrator.py            # Main search orchestrator (refactored cdp_orchestrator.py)
│   ├── parallel_search.py         # Parallel search with rate limits
│   └── source_prioritizer.py     # Source prioritization by region
│
├── tests/                         # Test suite (NEW)
│   ├── __init__.py
│   ├── fixtures/                  # HTML fixtures for parser tests
│   │   ├── find_a_grave_results.html
│   │   ├── antenati_results.html
│   │   └── ...
│   ├── test_extractors.py         # Test all extractors
│   ├── test_cache.py              # Test cache with TTL
│   ├── test_variants.py           # Test name/location variants
│   └── test_integration.py        # End-to-end tests
│
├── cli/                           # Command-line interfaces (NEW)
│   ├── __init__.py
│   ├── search.py                  # Main search CLI
│   └── research.py                # Research automation CLI
│
├── archive/                       # Old files (MOVE HERE)
│   ├── old_cdp_orchestrator.py
│   ├── old_test_scripts/
│   └── old_docs/
│
└── docs/                          # Documentation (CONSOLIDATED)
    ├── README.md                  # Main documentation
    ├── QUICK_START.md             # Quick start guide
    ├── API.md                     # API reference
    └── ROADMAP.md                 # Implementation roadmap
```

## Module Responsibilities

### `core/` - Infrastructure
- **cache.py**: Persistent cache with 30-day TTL, deduplication
- **graphql_client.py**: GraphQL mutations (submitResearch, logSearchAttempt)
- **rate_limiter.py**: Rate limiting (KEEP existing implementation)
- **progress.py**: Progress bar, ETA calculation

### `extraction/` - Record Parsing
- **base_extractor.py**: Abstract base class with `extract_records()` method
- **{source}_extractor.py**: Source-specific HTML parsers
- Each extractor returns: `[{name, birth_year, birth_place, url, match_score}, ...]`
- Graceful degradation: return URL-only if parser fails

### `variants/` - Search Expansion
- **name_variants.py**: Generate name translations, phonetic variants, diminutives
- **location_expander.py**: Generate location hierarchy, historical names
- **data/**: JSON databases for translations (build incrementally)

### `sources/` - Source Modules
- **base_source.py**: Abstract base class (KEEP existing)
- **{source}.py**: Each source implements `build_url()` and `check_results()`
- Sources are THIN - just URL building and result detection
- Extraction logic lives in `extraction/` modules

### `orchestration/` - Search Coordination
- **orchestrator.py**: Main orchestrator (refactored from cdp_orchestrator.py)
- **parallel_search.py**: Parallel search with per-source semaphores
- **source_prioritizer.py**: Prioritize sources by region/coverage

### `tests/` - Testing
- **fixtures/**: Save HTML from each source for regression testing
- **test_extractors.py**: Validate parsers don't break
- **test_integration.py**: End-to-end workflow tests

### `cli/` - User Interfaces
- **search.py**: Single-person search across sources
- **research.py**: Batch research automation

## Migration Plan

1. **Create new directory structure** (don't touch existing files yet)
2. **Implement core modules** (cache, GraphQL, progress)
3. **Implement one extractor** (Find A Grave) with tests
4. **Refactor one source** (findagrave.py) to use new extractor
5. **Validate** with end-to-end test
6. **Repeat** for remaining sources
7. **Move old files** to archive/
8. **Update documentation**

## Key Principles

- **Separation of concerns**: Each module has ONE job
- **Testability**: Every module has unit tests
- **Graceful degradation**: Parsers fail → fall back to URL-only
- **Incremental migration**: Don't break existing functionality
- **Clean imports**: No circular dependencies

