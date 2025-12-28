#!/usr/bin/env python3
"""Check what HTML content we're actually getting from CDP"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_orchestrator import CDPOrchestrator
from findagrave_cdp import FindAGraveCDPSource

orchestrator = CDPOrchestrator(log_dir=".logs")
source = FindAGraveCDPSource()

result = orchestrator.search_source(
    source_module=source,
    surname='Smith',
    given_name='John',
    location='London',
    year_min=1850,
    year_max=1900
)

content = result.get('content', '')

# Check if we have HTML tags
has_html = '<a' in content or '<div' in content
has_memorial_links = 'memorial/' in content

print(f"Content length: {len(content)} bytes")
print(f"Has HTML tags: {has_html}")
print(f"Has memorial links: {has_memorial_links}")

# Count memorial IDs
import re
memorial_ids = re.findall(r'memorial/(\d+)', content)
print(f"Memorial IDs found: {len(memorial_ids)}")
print(f"Unique memorial IDs: {len(set(memorial_ids))}")

if memorial_ids:
    print(f"\nFirst 10 memorial IDs:")
    for mid in memorial_ids[:10]:
        print(f"  - {mid}")

# Save content to file for inspection
output_file = Path(__file__).parent / "cdp_content.txt"
output_file.write_text(content)
print(f"\n✅ Saved content to: {output_file}")

