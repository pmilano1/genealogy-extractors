#!/usr/bin/env python3
"""Debug the Find A Grave parser"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from extraction.find_a_grave_extractor import FindAGraveExtractor

# Load the saved HTML
html_file = Path(__file__).parent / "sample_findagrave.html"
content = html_file.read_text()

search_params = {
    'surname': 'Smith',
    'given_name': 'John',
    'location': 'London',
    'year_min': 1850,
    'year_max': 1900
}

extractor = FindAGraveExtractor()

# Debug: show first 50 lines
lines = [line.strip() for line in content.split('\n') if line.strip()]
print("First 50 lines:")
for i, line in enumerate(lines[:50]):
    print(f"{i:3d}: {line}")
print("\n" + "="*80 + "\n")

records = extractor.extract_records(content, search_params)

print(f"Extracted {len(records)} records\n")

for i, record in enumerate(records, 1):
    print(f"{i}. {record['name']}")
    print(f"   Birth: {record.get('birth_year')} in {record.get('birth_place')}")
    print(f"   Death: {record.get('death_year')}")
    print(f"   Cemetery: {record.get('cemetery')}")
    print(f"   Score: {record['match_score']}/100")
    print()

