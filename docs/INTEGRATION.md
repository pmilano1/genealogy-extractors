# Integration: New Modules + Existing CDP Code

## Architecture Overview

The new modules **enhance** the existing CDP code, they don't replace it.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENHANCED CDP ORCHESTRATOR                     │
│  (orchestration/enhanced_orchestrator.py)                       │
│                                                                  │
│  Inherits from: cdp_orchestrator.py (KEEPS ALL CDP CODE)       │
│  Adds: Extraction, Caching, GraphQL submission                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   1. Check Cache (NEW)                  │
        │      core/cache.py                      │
        │      - 30-day TTL                       │
        │      - Avoid redundant searches         │
        └─────────────────────────────────────────┘
                              │
                              ▼ (cache miss)
        ┌─────────────────────────────────────────┐
        │   2. Execute Base Search (EXISTING)     │
        │      cdp_orchestrator.py                │
        │      - Navigate to URL (CDP)            │
        │      - Take snapshot (CDP)              │
        │      - Rate limiting                    │
        │      - Check if results found           │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   3. Source Module (EXISTING)           │
        │      sources/{source}_cdp.py            │
        │      - build_url()                      │
        │      - check_results()                  │
        │      Returns: found=True/False          │
        └─────────────────────────────────────────┘
                              │
                              ▼ (if found)
        ┌─────────────────────────────────────────┐
        │   4. Extract Records (NEW)              │
        │      extraction/{source}_extractor.py   │
        │      - Parse HTML                       │
        │      - Extract structured data          │
        │      - Calculate match scores           │
        │      Returns: [{name, year, place}...]  │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   5. Submit to API (NEW)                │
        │      core/graphql_client.py             │
        │      - submitResearch mutation          │
        │      - logSearchAttempt mutation        │
        │      Submits: Structured records        │
        └─────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │   6. Cache Result (NEW)                 │
        │      core/cache.py                      │
        │      - Save for 30 days                 │
        │      - Resume after crash               │
        └─────────────────────────────────────────┘
```

## What We Keep (Existing CDP Code)

### `cdp_orchestrator.py` ✅
- Browser navigation using Chrome DevTools MCP
- Snapshot capture
- Rate limiting
- Error handling
- Parallel search coordination

### `sources/{source}_cdp.py` ✅
- URL building logic
- Result detection (found/not found)
- Source-specific search parameters

### `cdp_client.py` ✅
- Chrome DevTools MCP integration
- Page navigation
- Content fetching

### `rate_limiter.py` ✅
- Rate limiting per source
- Prevents API throttling

## What We Add (New Modules)

### `extraction/{source}_extractor.py` ✨
- **Purpose**: Parse HTML → structured records
- **Input**: HTML content from CDP snapshot
- **Output**: `[{name, birth_year, birth_place, url, match_score}, ...]`
- **Fallback**: If parser fails → return URL-only record

### `core/cache.py` ✨
- **Purpose**: Avoid redundant searches
- **TTL**: 30 days
- **Benefit**: Resume after crash, reuse across runs

### `core/graphql_client.py` ✨
- **Purpose**: Submit structured records to API
- **Mutations**: `submitResearch`, `logSearchAttempt`
- **Benefit**: User reviews 10-20 records, not 6,938

### `core/progress.py` ✨
- **Purpose**: Show progress and ETA
- **Benefit**: User knows how long search will take

## Example: Find A Grave Search

### OLD FLOW
```python
orchestrator = CDPOrchestrator()
source = FindAGraveCDPSource()

result = orchestrator.search_source(
    source, "Smith", "John", "London", 1850, 1900
)
# Returns: {'found': True, 'message': 'FOUND (6,938 results)', 'url': '...'}
# User manually reviews 6,938 results
```

### NEW FLOW
```python
orchestrator = EnhancedCDPOrchestrator()
source = FindAGraveCDPSource()

result = orchestrator.search_source_with_extraction(
    source, person_id="123", surname="Smith", given_name="John", 
    location="London", year_min=1850, year_max=1900
)
# Returns: {
#   'found': True, 
#   'message': 'FOUND (6,938 results)',
#   'records': [
#     {'name': 'John Smith', 'birth_year': 1875, 'birth_place': 'London', 'match_score': 85},
#     {'name': 'John Smith', 'birth_year': 1878, 'birth_place': 'London', 'match_score': 82},
#     ...  # 10-20 records total
#   ],
#   'api_response': {...}  # Submitted to GraphQL API
# }
# User reviews 10-20 records in UI
```

## Key Points

1. **All CDP code is preserved** - We inherit from `CDPOrchestrator`
2. **Extractors are optional** - If no extractor exists, falls back to old behavior
3. **Graceful degradation** - If parser fails, returns URL-only record
4. **Backward compatible** - Old scripts still work
5. **Incremental migration** - Can add extractors one source at a time

## Migration Path

1. ✅ **Phase 1**: Build new modules (cache, extractors, GraphQL)
2. 🔄 **Phase 2**: Create `EnhancedCDPOrchestrator` (inherits from old)
3. ⏳ **Phase 3**: Update scripts to use enhanced orchestrator
4. ⏳ **Phase 4**: Test with real searches
5. ⏳ **Phase 5**: Archive old files once validated

**Current Status**: Phase 2 complete, ready for Phase 3

