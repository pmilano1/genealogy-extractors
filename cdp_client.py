"""Chrome DevTools Protocol client for genealogy research"""

import asyncio
import json
import websockets
from typing import Optional
from urllib.parse import urlparse
import urllib.request


class CDPClient:
    """Async CDP client for Chrome automation

    Creates a fresh tab for each request and closes it after use.
    """

    MAX_TABS = 15  # Emergency cleanup threshold

    def __init__(self, debug_url: str = "http://127.0.0.1:9222", source_name: str = None):
        self.debug_url = debug_url
        self.ws = None
        self.message_id = 0
        self.pending_responses = {}
        self.target_id = None
        self.source_name = source_name

    async def connect(self) -> bool:
        """Connect to Chrome DevTools Protocol - creates a new tab"""
        try:
            # Get list of targets (pages)
            response = urllib.request.urlopen(f"{self.debug_url}/json/list")
            targets = json.loads(response.read().decode())
            page_targets = [t for t in targets if t.get("type") == "page"]

            # Emergency cleanup if too many tabs
            if len(page_targets) >= self.MAX_TABS:
                tabs_to_close = len(page_targets) - self.MAX_TABS + 5
                for i in range(tabs_to_close):
                    target_id = page_targets[i].get("id")
                    try:
                        req = urllib.request.Request(f"{self.debug_url}/json/close/{target_id}", method='GET')
                        urllib.request.urlopen(req)
                    except Exception:
                        pass

            # Create a new tab
            req = urllib.request.Request(f"{self.debug_url}/json/new", method='PUT')
            response = urllib.request.urlopen(req)
            page_target = json.loads(response.read().decode())

            self.target_id = page_target.get("id")

            ws_url = page_target.get("webSocketDebuggerUrl")
            if not ws_url:
                print(f"[ERROR] No WebSocket URL for {self.source_name}")
                return False

            self.ws = await websockets.connect(ws_url)
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
                    # Timeout is not an error - page usually loads anyway
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
    
    async def check_for_bot_verification(self) -> bool:
        """Check if page has bot verification popup.

        Only checks for VISIBLE, full-page blocking CAPTCHA elements.
        Avoids false positives from hidden tracking/ad elements.

        Returns:
            True if bot check is detected, False otherwise
        """
        try:
            result = await self.send_command("Runtime.evaluate", {
                "expression": """
                    (function() {
                        // Only check for VISIBLE full-page blockers
                        // Very specific selectors to avoid false positives
                        var blockerSelectors = [
                            '#challenge-running',
                            '#challenge-form',
                            '#cf-wrapper',
                            'div.captcha-overlay',
                            'div.robot-check-overlay'
                        ];

                        for (var i = 0; i < blockerSelectors.length; i++) {
                            var el = document.querySelector(blockerSelectors[i]);
                            if (el && el.offsetParent !== null) {
                                return blockerSelectors[i];
                            }
                        }

                        // Check for large CAPTCHA iframes (must be visible and large)
                        var iframeSelectors = [
                            'iframe[src*="challenges.cloudflare.com"]',
                            'iframe[src*="hcaptcha.com/captcha"]'
                        ];

                        for (var i = 0; i < iframeSelectors.length; i++) {
                            var el = document.querySelector(iframeSelectors[i]);
                            if (el && el.offsetParent !== null) {
                                var rect = el.getBoundingClientRect();
                                if (rect.width > 200 && rect.height > 100) {
                                    return iframeSelectors[i];
                                }
                            }
                        }

                        return null;
                    })()
                """
            })

            # Navigate nested result
            if "result" in result:
                inner = result["result"]
                if isinstance(inner, dict) and "result" in inner:
                    value_obj = inner["result"]
                    if isinstance(value_obj, dict) and value_obj.get("value"):
                        matched = value_obj.get("value")
                        print(f"[BOT-CHECK] CDP detected: {matched}")
                        return True
            return False

        except Exception as e:
            print(f"[ERROR] Bot check detection failed: {e}")
            return False

    async def close(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()

    def close_tab(self):
        """Close the current tab to prevent accumulation"""
        if self.target_id:
            try:
                urllib.request.urlopen(f"{self.debug_url}/json/close/{self.target_id}")
            except Exception as e:
                print(f"[WARNING] Failed to close tab: {str(e)}")


async def fetch_with_cdp(url: str, debug_url: str = "http://127.0.0.1:9222", source_name: str = None) -> str:
    """Fetch page content using CDP

    Args:
        url: URL to fetch
        debug_url: Chrome debug URL
        source_name: Name of source (for logging)

    Raises:
        BotCheckDetected: If bot verification requires human intervention
    """
    # Import here to avoid circular dependency (BotCheckDetected defined below)
    client = CDPClient(debug_url, source_name=source_name)

    try:
        if not await client.connect():
            return ""

        if not await client.navigate(url):
            return ""

        # Check for bot verification before returning content
        if await client.check_for_bot_verification():
            # Close tab but raise exception for caller to handle
            await client.close()
            client.close_tab()
            # Can't import BotCheckDetected here due to order, use RuntimeError
            raise RuntimeError(
                f"BOT_CHECK_DETECTED: Bot verification on {source_name} requires human intervention. "
                "Please complete the verification in the browser, then retry."
            )

        content = await client.get_page_content()
        return content

    finally:
        await client.close()
        # Close the tab to prevent accumulation
        client.close_tab()


def fetch_page_content(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Synchronous wrapper for CDP fetch

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: Optional CSS selector to wait for (for JS-heavy sites)

    Raises:
        BotCheckDetected: If bot verification requires human intervention
    """
    # Use Playwright for sources that need special wait handling
    if wait_for_selector:
        return fetch_with_playwright(url, source_name=source_name, wait_for_selector=wait_for_selector)

    try:
        return asyncio.run(fetch_with_cdp(url, source_name=source_name))
    except RuntimeError as e:
        # Convert CDP bot check detection to proper exception
        if "BOT_CHECK_DETECTED" in str(e):
            raise BotCheckDetected(str(e).replace("BOT_CHECK_DETECTED: ", ""))
        print(f"[ERROR] CDP fetch failed: {str(e)}")
        return ""
    except Exception as e:
        print(f"[ERROR] CDP fetch failed: {str(e)}")
        return ""


class BotCheckDetected(Exception):
    """Raised when bot verification is detected and needs human intervention"""
    pass


class DailyLimitReached(Exception):
    """Raised when a source's daily search limit is reached"""
    pass


def _check_daily_limit(page, source_name: str = None) -> bool:
    """Check if page shows a daily limit message.

    Args:
        page: Playwright page object
        source_name: Name of source for logging

    Returns:
        True if daily limit detected
    """
    # Check page content for limit messages
    try:
        content = page.content().lower()

        # MyHeritage specific limit messages
        limit_indicators = [
            'daily limit',
            'reached your limit',
            'limit reached',
            'search limit',
            'too many searches',
            'come back tomorrow',
            'exceeded.*limit',
            'maximum.*searches',
        ]

        for indicator in limit_indicators:
            if indicator in content:
                print(f"[LIMIT] Daily limit detected on {source_name}: '{indicator}'")
                return True

        # Also check for specific elements that indicate limits
        limit_selectors = [
            '[class*="limit"]',
            '[class*="quota"]',
            '.search-limit-message',
            '.daily-limit',
        ]

        for selector in limit_selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    text = elem.text_content() or ''
                    if 'limit' in text.lower():
                        print(f"[LIMIT] Daily limit element found on {source_name}")
                        return True
            except Exception:
                continue

        return False

    except Exception as e:
        print(f"[LIMIT] Error checking daily limit: {e}")
        return False


def _handle_bot_check(page, source_name: str = None, max_attempts: int = 3) -> bool:
    """Detect and attempt to handle bot verification popups.

    Args:
        page: Playwright page object
        source_name: Name of source for logging
        max_attempts: Maximum auto-click attempts

    Returns:
        True if bot check was handled or not present

    Raises:
        BotCheckDetected: If bot check requires human intervention
    """
    import time

    # Very specific bot check selectors - ONLY full-page blocking overlays
    # These should cover the main content and prevent interaction
    bot_check_selectors = [
        # Cloudflare challenge page (replaces entire content)
        '#challenge-running',
        '#challenge-form',
        '#cf-wrapper',
        # Full-page CAPTCHA overlays
        'div.captcha-overlay',
        'div.robot-check-overlay',
    ]

    # These are less reliable - only check if they're large/blocking
    captcha_iframe_selectors = [
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="hcaptcha.com/captcha"]',
    ]

    # Clickable checkbox selectors (simple bot checks)
    checkbox_selectors = [
        '.recaptcha-checkbox',
        '#recaptcha-anchor',
    ]

    for attempt in range(max_attempts):
        # Check if any bot verification is present
        bot_check_found = False
        matched_selector = None

        # First check for full-page blockers
        for selector in bot_check_selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    bot_check_found = True
                    matched_selector = selector
                    print(f"[BOT-CHECK] Detected blocking overlay on {source_name}: {selector}")
                    break
            except Exception:
                continue

        # Then check for large CAPTCHA iframes (must be prominently visible)
        if not bot_check_found:
            for selector in captcha_iframe_selectors:
                try:
                    elem = page.query_selector(selector)
                    if elem and elem.is_visible():
                        # Check if iframe is large enough to be a real blocker
                        box = elem.bounding_box()
                        if box and box['width'] > 200 and box['height'] > 100:
                            bot_check_found = True
                            matched_selector = selector
                            print(f"[BOT-CHECK] Detected CAPTCHA iframe on {source_name}: {selector} ({box['width']}x{box['height']})")
                            break
                except Exception:
                    continue

        if not bot_check_found:
            return True  # No bot check, proceed normally

        # Try to click checkbox/submit to dismiss simple checks
        clicked = False
        for selector in checkbox_selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    print(f"[BOT-CHECK] Attempting to click: {selector}")
                    element.click()
                    clicked = True
                    time.sleep(2)  # Wait for verification
                    break
            except Exception as e:
                print(f"[BOT-CHECK] Click failed for {selector}: {e}")
                continue

        if clicked:
            # Check if bot check is still present after clicking
            time.sleep(2)
            continue  # Try again to verify it's gone
        else:
            # Bot check present but no clickable element found - needs human
            raise BotCheckDetected(
                f"Bot verification detected on {source_name} requires human intervention. "
                "Please complete the verification in the browser, then retry."
            )

    # Max attempts reached, check if still blocked
    for selector in bot_check_selectors:
        try:
            if page.query_selector(selector):
                raise BotCheckDetected(
                    f"Bot verification on {source_name} could not be automatically dismissed. "
                    "Please complete the verification manually."
                )
        except BotCheckDetected:
            raise
        except Exception:
            continue

    return True


def fetch_with_playwright(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Fetch page content using Playwright (better for JS-heavy sites)

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: CSS selector to wait for before getting content

    Reuses existing tab for the same source domain to avoid tab accumulation.

    Raises:
        BotCheckDetected: If bot verification requires human intervention
    """
    try:
        from playwright.sync_api import sync_playwright
        from urllib.parse import urlparse
        import time
        import os

        # Suppress Node.js deprecation warnings from Playwright
        os.environ['NODE_OPTIONS'] = '--no-deprecation'

        # Extract domain from URL for tab matching
        domain = urlparse(url).netloc.lower()

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]

            # Create a fresh tab
            page = context.new_page()
            should_close_tab = True  # Track whether to close tab

            try:
                page.goto(url, timeout=30000, wait_until="load")

                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        page.wait_for_selector(wait_for_selector, timeout=20000)
                    except Exception:
                        pass  # Selector not found, continue anyway

                # Small delay for any final rendering
                time.sleep(2)

                # Check for and handle bot verification
                # If bot check detected, DON'T close the tab - leave it open for user
                try:
                    _handle_bot_check(page, source_name)
                except BotCheckDetected:
                    # Leave tab open so user can see and complete verification
                    should_close_tab = False
                    print(f"[BOT-CHECK] Tab left open for {source_name} - please complete verification")
                    raise

                # Check for daily limit messages (e.g., MyHeritage)
                if _check_daily_limit(page, source_name):
                    raise DailyLimitReached(
                        f"{source_name} daily search limit reached. Try again tomorrow."
                    )

                return page.content()

            finally:
                # Close tab unless we want to leave it open for user
                if should_close_tab:
                    try:
                        page.close(run_before_unload=False)
                    except Exception:
                        pass

    except (BotCheckDetected, DailyLimitReached):
        # Re-raise these exceptions so caller can handle
        raise
    except Exception as e:
        from error_tracker import log_error
        log_error(source_name or 'playwright', 'PLAYWRIGHT_ERROR', str(e))
        return ""

