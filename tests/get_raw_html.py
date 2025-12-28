#!/usr/bin/env python3
"""
Get the raw HTML (not accessibility tree) from Find A Grave
"""

import asyncio
import json
import websockets
from pathlib import Path

async def get_raw_html():
    # Connect to Chrome DevTools
    debug_url = "http://127.0.0.1:9222"
    
    # Get list of tabs
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{debug_url}/json") as resp:
            tabs = await resp.json()
    
    if not tabs:
        print("No tabs found. Is Chrome running with --remote-debugging-port=9222?")
        return
    
    # Use first tab
    ws_url = tabs[0]['webSocketDebuggerUrl']
    
    async with websockets.connect(ws_url) as ws:
        # Navigate to Find A Grave
        url = "https://www.findagrave.com/memorial/search?firstname=John&lastname=Smith&birthyear=1875&birthyearfilter=5&location=London"
        
        await ws.send(json.dumps({
            "id": 1,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        
        response = await ws.recv()
        print(f"Navigate response: {response}\n")
        
        # Wait for page to load
        await asyncio.sleep(5)
        
        # Get the HTML source
        await ws.send(json.dumps({
            "id": 2,
            "method": "Runtime.evaluate",
            "params": {
                "expression": "document.documentElement.outerHTML"
            }
        }))
        
        response = await ws.recv()
        data = json.loads(response)
        
        if 'result' in data and 'result' in data['result']:
            html = data['result']['result']['value']
            
            # Save to file
            output_file = Path(__file__).parent / "sample_findagrave_raw.html"
            output_file.write_text(html)
            
            print(f"✅ Saved raw HTML to: {output_file}")
            print(f"   Size: {len(html)} bytes")
            print(f"\nFirst 2000 characters:")
            print("="*80)
            print(html[:2000])
        else:
            print(f"Error: {data}")

if __name__ == "__main__":
    try:
        asyncio.run(get_raw_html())
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure Chrome is running with:")
        print("google-chrome --remote-debugging-port=9222 --user-data-dir=$HOME/.chrome-debug-profile &")

