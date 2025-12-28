# Python CDP Research Automation - Top 10 Improvements

**Goal**: Make Step 1 (automated search) fast and comprehensive. You manually vet results before submitting to genealogy site.

---

## Top 10 Python Code Improvements

### 1. **Search with Name Variants (Data-Driven)**
**Current**: Search "Giovanni Rossi" only
**Improved**: Search Giovanni, John, Jean, Johann, Ivan (all variants from translation database)

**Code Change**:
```python
# Add name_variants.py with comprehensive translation data
class NameVariantGenerator:
    def __init__(self):
        # Load translation database (build from FamilySearch, Behind the Name, etc.)
        self.translations = self.load_translation_db()
        # Example structure:
        # {
        #   'Giovanni': {'english': ['John'], 'french': ['Jean'], 'german': ['Johann']},
        #   'Giuseppe': {'english': ['Joseph'], 'spanish': ['José']},
        #   'Maria': {'english': ['Mary'], 'french': ['Marie']}
        # }

    def generate_variants(self, given_name, surname, country):
        variants = {
            'given_name': [given_name],
            'surname': [surname]
        }

        # Language-specific translations
        if given_name in self.translations:
            for lang_variants in self.translations[given_name].values():
                variants['given_name'].extend(lang_variants)

        # Phonetic variants (Soundex, Metaphone)
        variants['given_name'].append(soundex(given_name))
        variants['given_name'].append(metaphone(given_name))

        # Diminutives (Giovanni → Gianni, John → Jack)
        variants['given_name'].extend(self.get_diminutives(given_name))

        # Surname variants (common misspellings, OCR errors)
        variants['surname'].extend(self.get_surname_variants(surname))

        # Deduplicate
        variants['given_name'] = list(set(variants['given_name']))
        variants['surname'] = list(set(variants['surname']))

        return variants

# In search loop: try all variants
variant_gen = NameVariantGenerator()
variants = variant_gen.generate_variants(given_name, surname, country)

for gn in variants['given_name']:
    for sn in variants['surname']:
        search(gn, sn, ...)
```

**Impact**: +30-50% more matches for immigrant families

**Data Sources**:
- FamilySearch name variants API
- Behind the Name database
- Wikipedia given name translations
- Build incrementally as you encounter new names

---

### 2. **Search Parent/Child Locations (Data-Driven)**
**Current**: Search "Naples" only
**Improved**: Search Naples, Campania, Italy (hierarchy from GeoNames database)

**Code Change**:
```python
# Add location_expander.py with GeoNames database
class LocationExpander:
    def __init__(self):
        # Load GeoNames database (https://www.geonames.org/)
        # Or use geocoding API (Google Maps, OpenStreetMap)
        self.geonames = self.load_geonames_db()

        # Historical name changes
        self.historical_names = {
            'Königsberg': 'Kaliningrad',
            'Bombay': 'Mumbai',
            'Leningrad': 'St. Petersburg',
            'Constantinople': 'Istanbul'
        }

    def expand_location(self, location, country):
        locations = [location]

        # Look up in GeoNames database
        place = self.geonames.lookup(location, country)

        if place:
            # Add hierarchy: city → province → region → country
            locations.extend(place.hierarchy)
            # Example: Naples → Napoli → Campania → Italy
        else:
            # Fallback: just add country
            locations.append(country)

        # Add historical names
        if location in self.historical_names:
            locations.append(self.historical_names[location])

        # Add alternate spellings (Napoli vs Naples)
        locations.extend(self.get_alternate_spellings(location))

        return list(set(locations))  # Deduplicate

# In search: try all location variants
expander = LocationExpander()
locations = expander.expand_location(location, country)

for loc in locations:
    search(..., location=loc)
```

**Impact**: +20-30% more matches from location variants

**Data Sources**:
- GeoNames database (free download)
- OpenStreetMap Nominatim API
- Wikipedia historical place names

---

### 3. **Skip Sources That Don't Have Records for Time Period**
**Current**: Search all sources regardless of era
**Improved**: Skip Antenati for pre-1866 Italy (civil registration didn't exist)

**Code Change**:
```python
# Add to each source module
class AntenatiCDPSource:
    def __init__(self):
        self.coverage = {
            'Italy': {'start_year': 1866, 'end_year': 1950},
            'France': {'start_year': 1792, 'end_year': 1950}
        }

    def has_coverage(self, country, year_min, year_max):
        if country not in self.coverage:
            return False
        cov = self.coverage[country]
        return year_max >= cov['start_year'] and year_min <= cov['end_year']

# In orchestrator: filter sources
sources_to_search = [s for s in sources if s.has_coverage(country, year_min, year_max)]
```

**Impact**: -40% wasted searches, faster results

---

### 4. **Prioritize Sources by Region**
**Current**: Search all 7 sources in random order
**Improved**: Search Antenati first for Italy, Geneanet first for France

**Code Change**:
```python
# Add source_prioritizer.py
def prioritize_sources(sources, country):
    priority_map = {
        'Italy': ['Antenati', 'FamilySearch', 'Ancestry'],
        'France': ['Geneanet', 'FamilySearch', 'Ancestry'],
        'UK': ['FreeBMD', 'FamilySearch', 'Ancestry']
    }

    priority = priority_map.get(country, [])

    # Sort sources by priority
    def sort_key(source):
        try:
            return priority.index(source.name)
        except ValueError:
            return 999  # Not in priority list

    return sorted(sources, key=sort_key)

# In orchestrator
sources = prioritize_sources(sources, country)
```

**Impact**: Find matches 2-3x faster (search best sources first)

---

### 5. **Extract & Score Actual Records (Not Just "FOUND")** ⚠️ MOST COMPLEX
**Current**: Submit "6,938 records found" URL → you manually review all 6,938
**Improved**: Extract top 10 records, score each, submit ALL to API (filter in UI, not Python)

**Code Change**:
```python
# Add record_extractor.py
class RecordExtractor:
    def extract_records(self, content, source_name, search_params):
        """Extract actual records from search results page"""
        records = []

        if source_name == "Find A Grave":
            for memorial in self.parse_memorial_cards(content):
                record = {
                    'name': memorial.name,
                    'birth_year': memorial.birth_year,
                    'death_year': memorial.death_year,
                    'birth_place': memorial.birth_place,
                    'cemetery': memorial.cemetery,
                    'url': memorial.url
                }
                # Calculate match score (0-100)
                record['match_score'] = self.calculate_match_score(record, search_params)
                records.append(record)

        # Sort by score, return top 10
        return sorted(records, key=lambda x: x['match_score'], reverse=True)[:10]

    def calculate_match_score(self, record, search_params):
        """Score 0-100 based on name, date, location match"""
        score = 0

        # Name match (40 points)
        if exact_match(record['name'], search_params.full_name):
            score += 40
        elif fuzzy_match(record['name'], search_params.full_name):
            score += 20

        # Birth year match (30 points)
        if record['birth_year']:
            year_diff = abs(record['birth_year'] - search_params.year_mid)
            if year_diff <= 2:
                score += 30
            elif year_diff <= 5:
                score += 15

        # Location match (30 points)
        if record['birth_place'] and search_params.location:
            if same_location(record['birth_place'], search_params.location):
                score += 30
            elif same_country(record['birth_place'], search_params.location):
                score += 15

        return score

# Add graphql_submitter.py
class GraphQLSubmitter:
    def submit_records(self, person_id, source_name, records):
        """Submit ALL extracted records to API (let user filter in UI)"""

        for record in records:  # Submit ALL, not just high-quality
            mutation = {
                "query": """
                mutation SubmitRecord($input: RecordInput!) {
                  submitRecord(input: $input) {
                    id
                    status
                  }
                }
                """,
                "variables": {
                    "input": {
                        "person_id": person_id,
                        "source_name": source_name,
                        "url": record['url'],
                        "name": record['name'],
                        "birth_year": record['birth_year'],
                        "birth_place": record['birth_place'],
                        "match_score": record['match_score'],
                        "confidence": "HIGH" if record['match_score'] >= 80 else "MEDIUM" if record['match_score'] >= 60 else "LOW",
                        "status": "PENDING_REVIEW"
                    }
                }
            }
            # Submit to API...

        return len(records)

    def extract_with_fallback(self, content, source_name, search_params, url):
        """Extract records with graceful degradation if parser fails"""
        try:
            records = self.extract_records(content, source_name, search_params)

            # Validate extraction worked
            if len(records) == 0 and "results" in content.lower():
                # Page has results but parser failed
                self.log_parser_failure(source_name, "Parser returned 0 records but page has results")
                # Fall back to URL-only submission
                return [{'url': url, 'match_score': 50, 'name': 'PARSE_FAILED', 'source': source_name}]

            return records
        except Exception as e:
            # Parser broke completely
            self.log_parser_failure(source_name, str(e))
            # Fall back to URL-only submission
            return [{'url': url, 'match_score': 50, 'name': 'PARSE_ERROR', 'source': source_name}]

# In cdp_orchestrator.py
def search_source(self, source_module, person_id, search_params, ...):
    # Do search
    content = page.content()

    if found:
        # Extract actual records (not just "FOUND")
        records = self.record_extractor.extract_records(content, source_name, search_params)

        # Submit high-quality records to API
        submitted = self.graphql_submitter.submit_records(person_id, source_name, records)

        print(f"  ✓ Extracted {len(records)} records, submitted {submitted} to API")
```

**Impact**: 6,938 results → 10-20 extracted records submitted to API (user filters by score in UI)

**Why submit ALL records**: Easier to filter in UI than re-run searches. User can adjust threshold (show 80+, 60+, or all 40+).

**Complexity Note**: This is the hardest feature to implement:
- Custom parser needed for each source (7 sources × 4 hours = 28 hours)
- HTML structure changes over time (need maintenance strategy)
- Edge cases: missing data, different layouts, pagination
- Testing: Save HTML fixtures, validate parsers don't break
- **Realistic timeline: 1-2 weeks, not 1-2 days**

---

### 6. **Retry with Fuzzy Name Matching**
**Current**: "Rossi" doesn't match "Possi" (OCR error)
**Improved**: Try Levenshtein distance ≤2 variants

**Code Change**:
```python
# Add fuzzy_matcher.py
def generate_fuzzy_variants(name):
    variants = [name]

    # Common OCR errors
    ocr_map = {'R': 'P', 'S': 'C', 'I': 'L', 'O': 'Q'}
    for i, char in enumerate(name):
        if char in ocr_map:
            variant = name[:i] + ocr_map[char] + name[i+1:]
            variants.append(variant)

    # Drop middle initials
    if '.' in name:
        variants.append(name.replace('.', ''))

    return variants

# In search: if no match, try fuzzy variants
if not found:
    for variant in generate_fuzzy_variants(surname):
        search(..., surname=variant)
```

**Impact**: +15-25% more matches from OCR errors

---

### 7. **Parallel Search with Rate Limit Coordination**
**Current**: Search person 1 across 7 sources, then person 2, etc. (sequential)
**Improved**: Search multiple people in parallel, but limit concurrency per source to avoid bans

**Code Change**:
```python
# In run_european_research.py
from asyncio import Semaphore

class CDPOrchestrator:
    def __init__(self):
        # Limit concurrent searches per source (avoid rate limits)
        self.source_semaphores = {
            'Antenati': Semaphore(2),      # Max 2 concurrent
            'Geneanet': Semaphore(3),      # Max 3 concurrent
            'WikiTree': Semaphore(5),      # Max 5 concurrent
            'FamilySearch': Semaphore(3),
            'Ancestry': Semaphore(2),
            'MyHeritage': Semaphore(2),
            'Find A Grave': Semaphore(5)
        }

    async def search_source(self, source, person):
        """Search with concurrency limit per source"""
        async with self.source_semaphores[source.name]:
            # Only N searches to this source at a time
            return await self._do_search(source, person)

async def search_all_parallel(tasks, sources):
    """Search multiple people in parallel (with per-source limits)"""
    async def search_one_person_all_sources(task):
        return await orchestrator.search_person_parallel(
            surname=task['surname'],
            given_name=task['given_name'],
            sources=sources,
            ...
        )

    # Search up to 20 people in parallel (not all 500 at once)
    batch_size = 20
    all_results = []

    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i+batch_size]
        results = await asyncio.gather(*[
            search_one_person_all_sources(task) for task in batch
        ])
        all_results.extend(results)

    return all_results

# Run it
results = asyncio.run(search_all_parallel(european_tasks, sources))
```

**Impact**: -70% total research time (500 people in 16 hours instead of 83)

**Why limit concurrency**: 500 people × 7 sources = 3,500 simultaneous requests would trigger rate limits and bans. Batching + per-source semaphores keeps you under radar.

---

### 8. **Persistent Cache to Avoid Duplicate Searches**
**Current**: Search "John Smith 1875 London" every time script runs
**Improved**: Cache results to disk, reuse across runs (even weeks later)

**Code Change**:
```python
# Add search_cache.py
import json
import hashlib
from pathlib import Path

class PersistentSearchCache:
    def __init__(self, cache_dir=".cache/searches"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, source_name, surname, given_name, location, year_min, year_max):
        """Generate unique cache key from search parameters"""
        key_string = f"{source_name}:{surname}:{given_name}:{location}:{year_min}:{year_max}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def get(self, source_name, surname, given_name, location, year_min, year_max):
        """Get cached result if exists and not expired"""
        cache_key = self._generate_cache_key(source_name, surname, given_name, location, year_min, year_max)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            with open(cache_file) as f:
                cached = json.load(f)

                # Check if cache is stale (30 days)
                from datetime import datetime, timedelta
                cache_age = datetime.now() - datetime.fromisoformat(cached['timestamp'])

                if cache_age > timedelta(days=30):
                    print(f"  [CACHE EXPIRED] Re-searching (cache is {cache_age.days} days old)")
                    return None

                print(f"  [CACHE HIT] Reusing result from {cached['timestamp']} ({cache_age.days} days old)")
                return cached['result']

        return None

    def set(self, source_name, surname, given_name, location, year_min, year_max, result):
        """Save result to cache"""
        from datetime import datetime

        cache_key = self._generate_cache_key(source_name, surname, given_name, location, year_min, year_max)
        cache_file = self.cache_dir / f"{cache_key}.json"

        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'source': source_name,
                'search_params': {
                    'surname': surname,
                    'given_name': given_name,
                    'location': location,
                    'year_min': year_min,
                    'year_max': year_max
                },
                'result': result
            }, f, indent=2)

# Add to cdp_orchestrator.py
class CDPOrchestrator:
    def __init__(self, cache_dir=".cache/searches"):
        self.cache = PersistentSearchCache(cache_dir)

    def search_source(self, source_module, surname, given_name, location, year_min, year_max):
        # Check cache first
        cached_result = self.cache.get(
            source_module.name, surname, given_name, location, year_min, year_max
        )

        if cached_result is not None:
            return cached_result

        # Search and cache
        result = self._do_search(source_module, ...)

        self.cache.set(
            source_module.name, surname, given_name, location, year_min, year_max, result
        )

        return result
```

**Impact**:
- -30% redundant searches within same run
- -70% redundant searches across multiple runs (cache persists)
- Restart script after crash? Resume from cache
- Re-run next week? Reuse all previous searches
- Cache expires after 30 days (catch new records added to sources)

---

### 9. **Add Progress Bar & ETA**
**Current**: No idea how long 500 people will take
**Improved**: Show "Person 47/500 (9%), ETA: 2h 15m"

**Code Change**:
```python
# Add tqdm progress bar
from tqdm import tqdm
import time

start_time = time.time()
for task_idx, task in enumerate(tqdm(european_tasks, desc="Researching"), 1):
    # Search person
    result = orchestrator.search_person_parallel(...)

    # Calculate ETA
    elapsed = time.time() - start_time
    avg_time_per_person = elapsed / task_idx
    remaining = len(european_tasks) - task_idx
    eta_seconds = remaining * avg_time_per_person

    tqdm.write(f"ETA: {eta_seconds/3600:.1f}h")
```

**Impact**: Better UX, know when to check back

---

### 10. **Smart Rate Limiting (Adaptive)**
**Current**: Fixed 3-second delay for all sources
**Improved**: Adjust delay based on response times & errors

**Code Change**:
```python
# Update rate_limiter.py
class RateLimiter:
    def __init__(self):
        self.adaptive_delays = {}  # Track per-source delays

    def wait_if_needed(self, source):
        # Start with default delay
        delay = self.config[source]['min_delay']

        # If we got errors recently, increase delay
        if source in self.recent_errors:
            error_count = len(self.recent_errors[source])
            delay *= (1 + error_count * 0.5)  # +50% per error

        # If we got fast responses, decrease delay
        if source in self.recent_response_times:
            avg_response = sum(self.recent_response_times[source]) / len(...)
            if avg_response < 1.0:  # Fast responses
                delay *= 0.8  # -20%

        time.sleep(delay)
        return delay
```

**Impact**: -20% wait time while avoiding bans

---

## Implementation Priority (Incremental Rollout)

**Week 1 - Quick Wins (Test with 10 people)**:
- #8: Persistent cache with 30-day TTL
- #9: Progress bar & ETA
- GraphQL API integration (fetch tasks, submit results)
- **Deliverable**: Script runs faster, shows progress, integrates with API

**Week 2 - Record Extraction for ONE Source (Test with 50 people)**:
- #5: Record extraction & scoring for Find A Grave only
- Add parser tests (save HTML fixtures)
- Graceful degradation when parser fails
- **Deliverable**: Find A Grave submits 10-20 extracted records per person
- **Validate**: How many records extracted? How accurate are scores?

**Week 3 - Expand Record Extraction (Test with 100 people)**:
- #5: Record extraction for remaining sources (Antenati, Geneanet, WikiTree, etc.)
- Each source needs custom parser (4 hours × 6 sources = 24 hours)
- **Deliverable**: All sources submit extracted records

**Week 4 - Name & Location Variants (Test with 100 people)**:
- #1: Name variant generation (start with simple translations, expand over time)
- #2: Location expansion (start with hardcoded, migrate to GeoNames later)
- **Deliverable**: +30-50% more matches from variants

**Week 5 - Source Optimization (Test with 500 people)**:
- #4: Source prioritization by region
- #3: Skip sources without coverage for time period
- **Deliverable**: Faster searches, fewer wasted attempts

**Week 6 - Parallelization (Test with 500 people)**:
- #7: Parallel search with rate limit coordination
- #10: Adaptive rate limiting
- **Deliverable**: -70% total research time

**Week 7 - Polish & Testing**:
- #6: Fuzzy matching for OCR errors
- Comprehensive testing across all sources
- Fix edge cases and bugs
- **Deliverable**: Production-ready system

**Week 8+ - Advanced Features (Optional)**:
- Cross-source clustering (same person in multiple sources = HIGH confidence)
- Contextual filtering (use existing family tree to eliminate impossible results)
- Source quality weighting (vital records > census > family trees)
- Feedback loop learning (adjust thresholds based on approvals/rejections)

---

## Testing Strategy

**After each phase, validate**:
1. **Extraction accuracy**: Manually review 20 random extractions, verify data is correct
2. **Match score accuracy**: Do high-scoring matches actually look better than low-scoring?
3. **False negative rate**: Are we missing obvious matches? (check cache for NO_MATCH results)
4. **Parser breakage**: Run tests against saved HTML fixtures, detect when sites change

**Test suite**:
```python
# tests/test_parsers.py
def test_find_a_grave_parser():
    """Test Find A Grave parser with real HTML fixture"""
    html = load_fixture('find_a_grave_search_results.html')
    extractor = RecordExtractor()
    records = extractor.extract_records(html, 'Find A Grave', search_params)

    assert len(records) > 0, "Parser should extract records"
    assert records[0]['name'] == 'John Smith', "Name should be extracted correctly"
    assert records[0]['birth_year'] == 1875, "Birth year should be extracted"
    assert records[0]['match_score'] > 60, "Match score should be calculated"

# Run tests daily to detect site changes
# pytest tests/test_parsers.py
```

---

## Expected Impact

**Current State**:
- 500 people × 10 min/person = **83 hours**
- Match rate: ~40%
- Submit: "6,938 records found" (URL only)
- You review: All 6,938 results manually
- Manual copy/paste of URLs

**After Week 1-4 (Record Extraction + Name Variants)**:
- 500 people × 2 min/person = **16 hours** (-80% search time)
- Match rate: ~70% (+75%)
- Submit: **10-20 specific records** per person with names, dates, places, match scores
- You review: Filter by score in UI (show 80+, 60+, or all 40+)
- **Review time per person**: 2 hours → 5 minutes (-95%)

**After Week 5-7 (Full Optimization)**:
- Parallel search with rate limit coordination
- Source prioritization and coverage filtering
- Fuzzy matching for OCR errors
- **Search time**: 16 hours → 5 hours (-70% from parallelization)
- **Match rate**: 70% → 85% (+15% from fuzzy matching and variants)

**After Week 8+ (Advanced Features - Optional)**:
- Cross-source validation (same person in 3 sources = 95% confidence)
- Contextual filtering (eliminate impossible results using family tree logic)
- Source quality weighting (prioritize vital records over family trees)
- **Precision**: 80%+ (8 out of 10 submitted records are correct)
- **Recall**: 90%+ (find the right person if they exist in sources)

**Workflow**:
1. Run Python script → searches 500 people across 7 sources
2. ~425 people matched (85% success rate after all optimizations)
3. Extract top 10-20 records per match → ~6,000 total records
4. Score each record (0-100) → submit ALL to API (not filtered)
5. Submit to API with status="PENDING_REVIEW"
6. Open genealogy frontend → "Review Queue" shows 6,000 records
7. **Filter in UI**: Show only 80+ score → ~1,500 high-confidence records (avg 3-4 per person)
8. For each record: see name, birth year, place, match score, URL
9. Click URL → verify → click "Approve" or "Reject"
10. Approved records auto-create parents/links in family tree
11. If needed, lower threshold to 60+ to see more matches

**Bottom Line**:
- **Search**: 83 hours → 5 hours (-94% with parallelization)
- **Review**: 1,000 hours → 50 hours (-95% by reviewing extracted records, not raw search results)
- **Total**: 1,083 hours → 55 hours (-95%)
- **Quality**: 80%+ precision, 90%+ recall
- **Flexibility**: Filter by score in UI, don't re-run searches

**Realistic Timeline**: 7-8 weeks for full implementation (not 4-5 weeks)

Transform from "dumb search" to **intelligent research assistant** that does 95% of the work for you.

