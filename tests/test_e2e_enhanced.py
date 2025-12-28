#!/usr/bin/env python3
"""
End-to-End Test: Enhanced Orchestrator with One Person
Tests the full integration: CDP → Extraction → API submission
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestration.enhanced_orchestrator import EnhancedCDPOrchestrator
from findagrave_cdp import FindAGraveCDPSource

# Test person - use someone likely to have results
TEST_PERSON = {
    'person_id': 'test_123',
    'surname': 'Smith',
    'given_name': 'John',
    'location': 'London',
    'year_min': 1850,
    'year_max': 1900
}

def test_enhanced_orchestrator():
    """Test enhanced orchestrator with Find A Grave"""
    
    print("="*80)
    print("END-TO-END TEST: Enhanced Orchestrator")
    print("="*80)
    print(f"\nTest Person: {TEST_PERSON['given_name']} {TEST_PERSON['surname']}")
    print(f"Birth: {TEST_PERSON['year_min']}-{TEST_PERSON['year_max']}")
    print(f"Location: {TEST_PERSON['location']}")
    print("\n" + "="*80)
    
    # Initialize enhanced orchestrator
    orchestrator = EnhancedCDPOrchestrator(
        log_dir=".logs",
        cache_dir=".cache"
    )
    
    # Initialize Find A Grave source
    source = FindAGraveCDPSource()
    
    print("\n[STEP 1] Checking cache...")
    
    # Execute search with extraction
    result = orchestrator.search_source_with_extraction(
        source_module=source,
        person_id=TEST_PERSON['person_id'],
        surname=TEST_PERSON['surname'],
        given_name=TEST_PERSON['given_name'],
        location=TEST_PERSON['location'],
        year_min=TEST_PERSON['year_min'],
        year_max=TEST_PERSON['year_max']
    )
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    # Display results
    print(f"\nFound: {result.get('found')}")
    print(f"Message: {result.get('message')}")
    print(f"URL: {result.get('url')}")
    
    # Display extracted records
    records = result.get('records', [])
    print(f"\nExtracted Records: {len(records)}")
    
    if records:
        print("\nTop 5 Records:")
        for i, record in enumerate(records[:5], 1):
            print(f"\n  {i}. {record.get('name')}")
            print(f"     Birth Year: {record.get('birth_year')}")
            print(f"     Birth Place: {record.get('birth_place')}")
            print(f"     Match Score: {record.get('match_score')}/100")
            print(f"     URL: {record.get('url')}")
    
    # Display API response
    if 'api_response' in result:
        print("\n" + "-"*80)
        print("API Submission: ✓ Success")
        print("-"*80)
    elif 'api_error' in result:
        print("\n" + "-"*80)
        print(f"API Submission: ✗ Failed - {result['api_error']}")
        print("-"*80)
    
    # Cache stats
    print("\n" + "="*80)
    print("CACHE STATISTICS")
    print("="*80)
    stats = orchestrator.cache.stats()
    print(f"Total cached entries: {stats['total']}")
    print(f"Valid entries: {stats['valid']}")
    print(f"Expired entries: {stats['expired']}")
    print(f"TTL: {stats['ttl_days']} days")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    
    # Validate results
    assert result.get('found') is not None, "Result should have 'found' field"
    assert result.get('url') is not None, "Result should have 'url' field"
    
    if result.get('found'):
        print("\n✅ Test PASSED: Search found results")
        if records:
            print(f"✅ Test PASSED: Extracted {len(records)} records")
            
            # Validate record structure
            for record in records:
                assert 'name' in record, "Record should have 'name'"
                assert 'url' in record, "Record should have 'url'"
                assert 'match_score' in record, "Record should have 'match_score'"
                assert 'source' in record, "Record should have 'source'"
            
            print("✅ Test PASSED: All records have required fields")
        else:
            print("⚠️  Warning: Found results but no records extracted (parser may need work)")
    else:
        print("\n⚠️  Test PASSED: Search completed (no results found)")
    
    return result


if __name__ == "__main__":
    try:
        result = test_enhanced_orchestrator()
        print("\n" + "="*80)
        print("🎉 END-TO-END TEST SUCCESSFUL")
        print("="*80)
    except Exception as e:
        print("\n" + "="*80)
        print(f"❌ TEST FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        sys.exit(1)

