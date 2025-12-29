"""Chrome DevTools Protocol client for genealogy research"""

import asyncio
import json
import websockets
from typing import Optional
from urllib.parse import urlparse
import urllib.request


# Global event loop and source tabs - persist across calls
_event_loop = None
_source_tabs = {}  # Global dict to track tabs per source


class CDPClient:
    """Async CDP client for Chrome automation"""

    MAX_TABS = 10  # Maximum number of tabs to keep open

    def __init__(self, debug_url: str = "http://127.0.0.1:9222", source_name: str = None):
        self.debug_url = debug_url
        self.ws = None
        self.message_id = 0
        self.pending_responses = {}
        self.target_id = None  # Track which target we're using
        self.source_name = source_name  # Track which source this client is for
        
    async def connect(self) -> bool:
        """Connect to Chrome DevTools Protocol with tab management per source"""
        try:
            # Check if we already have a tab for this source
            if self.source_name and self.source_name in _source_tabs:
                target_id = _source_tabs[self.source_name]
                print(f"[CDP] Reusing tab for {self.source_name}")

                # Verify the tab still exists
                response = urllib.request.urlopen(f"{self.debug_url}/json/list")
                targets = json.loads(response.read().decode())
                page_target = next((t for t in targets if t.get("id") == target_id), None)

                if page_target:
                    self.target_id = target_id
                    ws_url = page_target.get("webSocketDebuggerUrl")
                    if ws_url:
                        self.ws = await websockets.connect(ws_url)
                        print(f"[CDP] Connected to Chrome DevTools Protocol")
                        return True

            # Get list of targets (pages)
            response = urllib.request.urlopen(f"{self.debug_url}/json/list")
            targets = json.loads(response.read().decode())

            # Count existing page tabs
            page_targets = [t for t in targets if t.get("type") == "page"]
            print(f"[CDP] Found {len(page_targets)} existing tabs")

            # Close old tabs if we exceed MAX_TABS
            if len(page_targets) >= self.MAX_TABS:
                print(f"[CDP] Closing old tabs (limit: {self.MAX_TABS})")
                # Close the oldest tabs (first ones in list)
                tabs_to_close = len(page_targets) - self.MAX_TABS + 1
                for i in range(tabs_to_close):
                    target_id = page_targets[i].get("id")
                    try:
                        req = urllib.request.Request(f"{self.debug_url}/json/close/{target_id}", method='GET')
                        urllib.request.urlopen(req)
                        print(f"[CDP] Closed tab {target_id}")
                    except Exception as e:
                        print(f"[WARNING] Failed to close tab: {str(e)}")

                # Refresh target list
                response = urllib.request.urlopen(f"{self.debug_url}/json/list")
                targets = json.loads(response.read().decode())
                page_targets = [t for t in targets if t.get("type") == "page"]

            # Create a new tab for this source
            print(f"[CDP] Creating new tab for {self.source_name or 'unknown'}")
            req = urllib.request.Request(f"{self.debug_url}/json/new", method='PUT')
            response = urllib.request.urlopen(req)
            page_target = json.loads(response.read().decode())

            self.target_id = page_target.get("id")

            # Store this tab for the source
            if self.source_name:
                _source_tabs[self.source_name] = self.target_id

            ws_url = page_target.get("webSocketDebuggerUrl")
            if not ws_url:
                print("[ERROR] No WebSocket URL found for page target")
                return False

            # Connect to WebSocket
            self.ws = await websockets.connect(ws_url)
            print(f"[CDP] Connected to Chrome DevTools Protocol")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to connect to CDP: {str(e)}")
            return False
    
    async def send_command(self, method: str, params: dict = None) -> dict:
        """Send a CDP command and wait for response"""
        if not self.ws:
            return {"error": "Not connected"}

        self.message_id += 1
        msg_id = self.message_id

        command = {
            "id": msg_id,
            "method": method,
            "params": params or {}
        }

        # Send command
        await self.ws.send(json.dumps(command))

        # Wait for response with timeout
        try:
            while True:
                response = await asyncio.wait_for(self.ws.recv(), timeout=10)
                data = json.loads(response)

                if data.get("id") == msg_id:
                    return data
        except asyncio.TimeoutError:
            print(f"[ERROR] Command timeout: {method}")
            return {"error": "timeout"}
    
    async def navigate(self, url: str, timeout: int = 10) -> bool:
        """Navigate to URL and wait for page load

        Args:
            url: URL to navigate to
            timeout: Maximum seconds to wait (default 10)
        """
        try:
            # Enable Page domain
            await self.send_command("Page.enable")

            # Navigate
            result = await self.send_command("Page.navigate", {"url": url})
            if "error" in result:
                print(f"[ERROR] Navigation failed: {result['error']}")
                return False

            # Simple approach: wait for document.readyState == "complete" + fixed delay
            # This is more reliable than event-based waiting for JS-heavy sites
            start_time = asyncio.get_event_loop().time()
            while True:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"[WARNING] Navigation timeout after {timeout}s")
                    # Still return True - page might have loaded
                    await asyncio.sleep(2)
                    return True

                # Check if document is ready
                result = await self.send_command("Runtime.evaluate", {
                    "expression": "document.readyState"
                })

                if result.get("result", {}).get("value") == "complete":
                    # Wait 2 seconds for JavaScript to render
                    await asyncio.sleep(2)
                    return True

                await asyncio.sleep(0.5)

        except Exception as e:
            print(f"[ERROR] Navigation error: {str(e)}")
            return False


    async def get_page_content(self) -> str:
        """Get current page HTML content

        For large pages, gets just the main content area to avoid WebSocket size limits.
        """
        try:
            # Enable Runtime domain
            await self.send_command("Runtime.enable")

            # Strategy: Get just the search results container, not the entire page
            # This avoids the 1MB WebSocket message limit
            result = await self.send_command("Runtime.evaluate", {
                "expression": """
                    (function() {
                        // Try to find the main content container
                        var main = document.querySelector('main') ||
                                   document.querySelector('#main') ||
                                   document.querySelector('.main-content') ||
                                   document.querySelector('[role="main"]') ||
                                   document.body;

                        // Get the HTML, but limit to 800KB to stay under 1MB limit
                        var html = main.outerHTML;
                        if (html.length > 800000) {
                            html = html.substring(0, 800000);
                        }
                        return html;
                    })()
                """
            })

            # Navigate the nested result structure
            if "result" in result:
                inner_result = result["result"]
                if isinstance(inner_result, dict) and "result" in inner_result:
                    value_obj = inner_result["result"]
                    if isinstance(value_obj, dict) and "value" in value_obj:
                        return value_obj["value"]

            return ""

        except Exception as e:
            print(f"[ERROR] Failed to get page content: {str(e)}")
            return ""
    
    async def close(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()

    def close_tab(self):
        """Close the current tab (optional - can reuse tabs)"""
        if self.target_id:
            try:
                urllib.request.urlopen(f"{self.debug_url}/json/close/{self.target_id}")
                print(f"[CDP] Closed tab {self.target_id}")
            except Exception as e:
                print(f"[WARNING] Failed to close tab: {str(e)}")


async def fetch_with_cdp(url: str, debug_url: str = "http://127.0.0.1:9222", source_name: str = None) -> str:
    """Fetch page content using CDP

    Args:
        url: URL to fetch
        debug_url: Chrome debug URL
        source_name: Name of source (for logging)
    """
    client = CDPClient(debug_url, source_name=source_name)

    try:
        if not await client.connect():
            return ""

        if not await client.navigate(url):
            return ""

        content = await client.get_page_content()
        return content

    finally:
        await client.close()


def fetch_page_content(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Synchronous wrapper for CDP fetch

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: Optional CSS selector to wait for (for JS-heavy sites)
    """
    # Use Playwright for sources that need special wait handling
    if wait_for_selector:
        return fetch_with_playwright(url, source_name=source_name, wait_for_selector=wait_for_selector)

    try:
        return asyncio.run(fetch_with_cdp(url, source_name=source_name))
    except Exception as e:
        print(f"[ERROR] CDP fetch failed: {str(e)}")
        return ""


def fetch_with_playwright(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Fetch page content using Playwright (better for JS-heavy sites)

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: CSS selector to wait for before getting content
    """
    try:
        from playwright.sync_api import sync_playwright
        import time

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]

            # Reuse last page or create new one
            pages = context.pages
            page = pages[-1] if pages else context.new_page()

            print(f"[Playwright] Navigating to {source_name or 'page'}...")
            page.goto(url, timeout=30000, wait_until="load")

            # Wait for specific selector if provided
            if wait_for_selector:
                try:
                    page.wait_for_selector(wait_for_selector, timeout=20000)
                    print(f"[Playwright] Found results selector")
                except Exception:
                    print(f"[Playwright] Selector not found, continuing...")

            # Small delay for any final rendering
            time.sleep(2)

            content = page.content()
            print(f"[Playwright] Got {len(content)} bytes")
            return content

    except Exception as e:
        print(f"[ERROR] Playwright fetch failed: {str(e)}")
        return ""

