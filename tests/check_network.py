#!/usr/bin/env python3
"""
Check network requests to see if Find A Grave has JSON API
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cdp_client import CDPClient

def main():
    client = CDPClient()
    
    # Navigate to Find A Grave search
    url = "https://www.findagrave.com/memorial/search?firstname=John&lastname=Smith&birthyear=1875&birthyearfilter=5&location=London"
    
    print(f"Navigating to: {url}\n")
    client.navigate(url)
    
    # Wait for page to load
    import time
    time.sleep(5)
    
    # Get network requests
    print("Fetching network requests...\n")
    print("="*80)
    
    # Use Chrome DevTools Protocol to get network log
    # This would require implementing network monitoring in cdp_client
    # For now, let's just check if there are any XHR/Fetch requests
    
    snapshot = client.get_snapshot()
    
    # Look for API endpoints in the content
    import re
    api_patterns = [
        r'https://[^"\']+/api/[^"\']+',
        r'https://[^"\']+\.json[^"\']*',
        r'/api/v\d+/[^"\']+',
    ]
    
    print("Looking for API endpoints in page content...\n")
    for pattern in api_patterns:
        matches = re.findall(pattern, snapshot)
        if matches:
            print(f"Pattern: {pattern}")
            for match in set(matches[:10]):  # Unique, first 10
                print(f"  - {match}")
            print()
    
    print("="*80)
    print("\nTo see actual network requests, we need to:")
    print("1. Enable Network domain in CDP")
    print("2. Listen to Network.requestWillBeSent events")
    print("3. Listen to Network.responseReceived events")
    print("\nLet me check if cdp_client supports this...")

if __name__ == "__main__":
    main()

