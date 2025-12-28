#!/usr/bin/env python3
"""
Capture network requests to find JSON API endpoints
"""

import asyncio
import json
import websockets

async def capture_network():
    # Connect to Chrome DevTools
    debug_url = "http://127.0.0.1:9222"
    
    # Get list of tabs
    import urllib.request
    with urllib.request.urlopen(f"{debug_url}/json") as response:
        tabs = json.loads(response.read())
    
    if not tabs:
        print("No tabs found. Is Chrome running with --remote-debugging-port=9222?")
        return
    
    # Use first tab
    ws_url = tabs[0]['webSocketDebuggerUrl']
    
    print(f"Connecting to: {ws_url}\n")
    
    async with websockets.connect(ws_url) as ws:
        # Enable Network domain
        await ws.send(json.dumps({
            "id": 1,
            "method": "Network.enable"
        }))
        await ws.recv()
        
        print("Network monitoring enabled\n")
        
        # Navigate to Find A Grave
        url = "https://www.findagrave.com/memorial/search?firstname=John&lastname=Smith&birthyear=1875&birthyearfilter=5&location=London"
        
        await ws.send(json.dumps({
            "id": 2,
            "method": "Page.navigate",
            "params": {"url": url}
        }))
        await ws.recv()
        
        print(f"Navigating to: {url}\n")
        print("Capturing network requests for 10 seconds...\n")
        print("="*80)
        
        # Collect network requests
        requests = []
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < 10:
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(response)
                
                # Look for network events
                if 'method' in data:
                    method = data['method']
                    
                    if method == 'Network.requestWillBeSent':
                        params = data.get('params', {})
                        request = params.get('request', {})
                        url = request.get('url', '')
                        
                        # Filter for interesting requests
                        if any(keyword in url.lower() for keyword in ['api', 'json', 'search', 'memorial', 'ajax']):
                            requests.append({
                                'url': url,
                                'method': request.get('method', 'GET'),
                                'type': params.get('type', 'unknown')
                            })
                            print(f"[{request.get('method', 'GET')}] {url}")
                    
                    elif method == 'Network.responseReceived':
                        params = data.get('params', {})
                        response_data = params.get('response', {})
                        url = response_data.get('url', '')
                        mime_type = response_data.get('mimeType', '')
                        
                        # Look for JSON responses
                        if 'json' in mime_type.lower():
                            print(f"[JSON RESPONSE] {url}")
                            print(f"  MIME: {mime_type}")
                            
            except asyncio.TimeoutError:
                continue
        
        print("\n" + "="*80)
        print(f"\nCaptured {len(requests)} interesting requests")
        
        if requests:
            print("\nSummary:")
            for req in requests:
                print(f"  [{req['method']}] {req['url']}")

if __name__ == "__main__":
    try:
        asyncio.run(capture_network())
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure Chrome is running with:")
        print("google-chrome --remote-debugging-port=9222 --user-data-dir=$HOME/.chrome-debug-profile &")

