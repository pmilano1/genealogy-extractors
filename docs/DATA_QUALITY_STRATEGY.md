# Data Quality Strategy - Signal vs Noise

## The Core Problem

**Current State**: "John Smith, London, 1875" returns 6,938 records on Find A Grave.  
**Reality**: 6,937 are noise. Only 1 (maybe) is your ancestor.

**Question**: How do we filter 6,938 down to 5-10 high-quality candidates worth reviewing?

---

## Strategy 1: Extract Actual Record Data (Not Just "FOUND")

### Problem
**Current**: We just detect "6,938 records found" and submit URL.  
**You still have to**: Click URL → manually scan 6,938 results → find the right one.

### Solution: Scrape Top Results
Instead of just detecting "FOUND", extract the **top 10-20 actual records** with details:

```python
def extract_search_results(content, source_name):
    """Extract actual record details from search results page"""
    
    if source_name == "Find A Grave":
        # Parse memorial cards from HTML
        records = []
        for memorial in parse_memorial_cards(content):
            records.append({
                'name': memorial.name,
                'birth_year': memorial.birth_year,
                'death_year': memorial.death_year,
                'birth_place': memorial.birth_place,
                'death_place': memorial.death_place,
                'cemetery': memorial.cemetery,
                'memorial_url': memorial.url,
                'match_score': calculate_match_score(memorial, search_params)
            })
        
        # Sort by match score, return top 10
        return sorted(records, key=lambda x: x['match_score'], reverse=True)[:10]
```

**Impact**: Submit 10 specific records instead of 6,938 generic results.

---

## Strategy 2: Calculate Match Scores (Confidence Filtering)

### Problem
**Current**: All "FOUND" results treated equally.  
**Reality**: "John Smith, b.1875 London" is better than "John Smith, b.1920 New York".

### Solution: Score Each Record
```python
def calculate_match_score(record, search_params):
    """Score 0-100 based on how well record matches search criteria"""
    score = 0
    
    # Name match (40 points max)
    if exact_match(record.surname, search_params.surname):
        score += 20
    elif fuzzy_match(record.surname, search_params.surname):
        score += 10
    
    if exact_match(record.given_name, search_params.given_name):
        score += 20
    elif fuzzy_match(record.given_name, search_params.given_name):
        score += 10
    
    # Birth year match (30 points max)
    if record.birth_year:
        year_diff = abs(record.birth_year - search_params.year_mid)
        if year_diff == 0:
            score += 30
        elif year_diff <= 2:
            score += 25
        elif year_diff <= 5:
            score += 15
        elif year_diff <= 10:
            score += 5
    
    # Location match (30 points max)
    if record.birth_place and search_params.location:
        if exact_location_match(record.birth_place, search_params.location):
            score += 30
        elif same_country(record.birth_place, search_params.location):
            score += 15
        elif same_region(record.birth_place, search_params.location):
            score += 20
    
    return score

# Filter: Only submit records with score >= 60
high_quality_records = [r for r in records if r['match_score'] >= 60]
```

**Impact**: 6,938 results → 5-10 high-confidence matches.

---

## Strategy 3: Cross-Source Validation

### Problem
**Current**: Each source searched independently.  
**Reality**: If 3 sources agree on same person, confidence is HIGH. If only 1 source has it, confidence is LOW.

### Solution: Cluster Results Across Sources
```python
def cluster_results_across_sources(all_results):
    """Group results that likely refer to same person"""
    
    clusters = []
    
    for result in all_results:
        # Find existing cluster that matches
        matched_cluster = None
        for cluster in clusters:
            if same_person(result, cluster['canonical']):
                matched_cluster = cluster
                break
        
        if matched_cluster:
            # Add to existing cluster
            matched_cluster['sources'].append(result['source'])
            matched_cluster['records'].append(result)
            matched_cluster['confidence'] += 20  # Boost confidence
        else:
            # Create new cluster
            clusters.append({
                'canonical': result,
                'sources': [result['source']],
                'records': [result],
                'confidence': result['match_score']
            })
    
    # Sort by confidence (multi-source matches first)
    return sorted(clusters, key=lambda x: x['confidence'], reverse=True)

# Example output:
# Cluster 1: Found in Ancestry, FamilySearch, Find A Grave (confidence: 95)
# Cluster 2: Found in WikiTree only (confidence: 65)
# Cluster 3: Found in Geneanet only (confidence: 60)
```

**Impact**: Prioritize records found in multiple sources (higher confidence).

---

## Strategy 4: Contextual Filtering (Impossible Results)

### Problem
**Current**: Submit "John Smith b.1875 Italy" even though he died in 1880 in New York (from existing family tree).  
**Reality**: If we know he died in 1880, he can't have children born in 1900.

### Solution: Use Existing Family Tree Data
```python
def filter_impossible_results(records, person_data):
    """Remove results that contradict known family tree data"""
    
    filtered = []
    
    for record in records:
        # Check death date constraint
        if person_data.death_year and record.birth_year > person_data.death_year:
            continue  # Can't be born after death
        
        # Check marriage date constraint
        if person_data.marriage_year and record.birth_year > person_data.marriage_year - 12:
            continue  # Can't marry before age 12
        
        # Check children's birth dates
        if person_data.children:
            oldest_child_birth = min(c.birth_year for c in person_data.children)
            if record.death_year and record.death_year < oldest_child_birth:
                continue  # Can't die before having children
        
        # Check geographic plausibility
        if person_data.known_locations:
            if not geographically_plausible(record.location, person_data.known_locations):
                continue  # Can't be in Italy and USA same year
        
        filtered.append(record)
    
    return filtered
```

**Impact**: Eliminate 30-50% of false positives using timeline logic.

---

## Strategy 5: Source Quality Weighting

### Problem
**Current**: Ancestry.com family tree = same weight as civil birth record.  
**Reality**: Primary sources (vital records) >> secondary sources (census) >> tertiary sources (family trees).

### Solution: Weight by Source Type
```python
SOURCE_QUALITY = {
    'vital_record': 100,      # Birth/death/marriage certificates
    'church_record': 95,      # Baptism, burial records
    'census': 80,             # Government census
    'military': 80,           # Military records
    'immigration': 75,        # Ship manifests, naturalization
    'newspaper': 70,          # Obituaries, announcements
    'cemetery': 60,           # Gravestones (can have errors)
    'family_tree': 40,        # User-submitted trees (often wrong)
}

def adjust_confidence_by_source_quality(record, source_name):
    """Adjust match score based on source quality"""
    
    # Determine source type
    if 'vital' in source_name.lower() or 'civil' in source_name.lower():
        source_type = 'vital_record'
    elif 'church' in source_name.lower() or 'parish' in source_name.lower():
        source_type = 'church_record'
    elif 'census' in source_name.lower():
        source_type = 'census'
    elif 'grave' in source_name.lower() or 'cemetery' in source_name.lower():
        source_type = 'cemetery'
    elif 'tree' in source_name.lower():
        source_type = 'family_tree'
    else:
        source_type = 'unknown'
    
    quality_weight = SOURCE_QUALITY.get(source_type, 50) / 100.0
    record['adjusted_score'] = record['match_score'] * quality_weight
    record['source_quality'] = source_type
    
    return record
```

**Impact**: Prioritize vital records over family trees.

---

## Strategy 6: Smart Pagination (Don't Scrape All 6,938)

### Problem
**Current**: Either scrape all 6,938 results (slow) or just first page (miss good matches on page 50).  
**Reality**: Best matches are usually in first 2-3 pages if sorted by relevance.

### Solution: Adaptive Pagination
```python
def smart_pagination(source, search_params):
    """Scrape pages until match quality drops below threshold"""
    
    all_records = []
    page = 1
    consecutive_low_quality_pages = 0
    
    while page <= 10:  # Max 10 pages
        records = scrape_page(source, search_params, page)
        
        # Calculate average match score for this page
        avg_score = sum(r['match_score'] for r in records) / len(records)
        
        all_records.extend(records)
        
        # Stop if 3 consecutive pages with avg score < 50
        if avg_score < 50:
            consecutive_low_quality_pages += 1
            if consecutive_low_quality_pages >= 3:
                break
        else:
            consecutive_low_quality_pages = 0
        
        page += 1
    
    return all_records
```

**Impact**: Get high-quality results from pages 1-5, skip pages 6-100.

---

## Implementation: Complete Pipeline

```python
def research_person_with_quality_filtering(person_id, search_params, sources):
    """Complete pipeline with quality filtering"""
    
    # Step 1: Search all sources
    raw_results = search_all_sources(person_id, search_params, sources)
    
    # Step 2: Extract actual records (not just "FOUND")
    extracted_records = []
    for result in raw_results:
        if result['found']:
            records = extract_search_results(result['content'], result['source'])
            extracted_records.extend(records)
    
    # Step 3: Calculate match scores
    scored_records = [calculate_match_score(r, search_params) for r in extracted_records]
    
    # Step 4: Filter by minimum score (60+)
    high_quality = [r for r in scored_records if r['match_score'] >= 60]
    
    # Step 5: Adjust by source quality
    weighted_records = [adjust_confidence_by_source_quality(r, r['source']) for r in high_quality]
    
    # Step 6: Filter impossible results
    person_data = get_person_data(person_id)
    plausible_records = filter_impossible_results(weighted_records, person_data)
    
    # Step 7: Cluster across sources
    clusters = cluster_results_across_sources(plausible_records)
    
    # Step 8: Submit top 10 clusters to API
    for cluster in clusters[:10]:
        submit_to_api(person_id, cluster)
    
    return clusters
```

---

## Expected Impact

**Before**:
- Submit: "6,938 records found on Find A Grave" (URL only)
- You review: All 6,938 manually
- Time: 2 hours per person

**After**:
- Submit: 5-10 specific records with names, dates, places, match scores
- You review: Only high-confidence matches
- Time: 5 minutes per person

**Quality Metrics**:
- Precision: 80%+ (8 out of 10 submitted records are correct)
- Recall: 90%+ (find the right person if they exist in sources)
- Review time: -95% (2 hours → 5 minutes)

