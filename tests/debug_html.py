#!/usr/bin/env python3
"""
Debug script to see what HTML we're getting from Find A Grave
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_orchestrator import CDPOrchestrator
from findagrave_cdp import FindAGraveCDPSource

# Test person
TEST_PERSON = {
    'surname': 'Smith',
    'given_name': 'John',
    'location': 'London',
    'year_min': 1850,
    'year_max': 1900
}

def main():
    orchestrator = CDPOrchestrator(log_dir=".logs")
    source = FindAGraveCDPSource()
    
    result = orchestrator.search_source(
        source_module=source,
        surname=TEST_PERSON['surname'],
        given_name=TEST_PERSON['given_name'],
        location=TEST_PERSON['location'],
        year_min=TEST_PERSON['year_min'],
        year_max=TEST_PERSON['year_max']
    )
    
    if result.get('content'):
        # Save HTML to file
        html_file = Path(__file__).parent / "sample_findagrave.html"
        html_file.write_text(result['content'])
        print(f"✅ Saved HTML to: {html_file}")
        print(f"   Size: {len(result['content'])} bytes")
        
        # Show first 2000 chars
        print("\n" + "="*80)
        print("FIRST 2000 CHARACTERS:")
        print("="*80)
        print(result['content'][:2000])
    else:
        print("❌ No content in result")

if __name__ == "__main__":
    main()

