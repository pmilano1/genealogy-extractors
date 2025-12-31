"""Chrome DevTools Protocol client for genealogy research - Playwright only

All browser automation uses Playwright connecting to Chrome via CDP.
This avoids race conditions from mixing raw WebSocket and Playwright.

Tab Management:
- Cleans up orphaned about:blank tabs periodically before each search
- Creates fresh tabs for each search (Playwright page objects don't persist across sessions)
- Always closes tabs after use in finally block
"""

import json
import subprocess
import threading
import time
import os
from typing import Optional

from .config import get_chrome_config

# Suppress Node.js deprecation warnings from Playwright
os.environ['NODE_OPTIONS'] = '--no-deprecation'


def _get_chrome_url() -> str:
    """Get Chrome debug URL from config."""
    config = get_chrome_config()
    host = config.get('debug_host', '127.0.0.1')
    port = config.get('debug_port', 9222)
    return f"http://{host}:{port}"

# Semaphore to limit concurrent browser connections (reduced from 4 to 2 to prevent CDP overload)
_browser_semaphore = threading.Semaphore(2)

# Track last cleanup time to avoid cleaning too frequently
_last_cleanup_time = 0
_cleanup_interval = 60  # Cleanup at most once per minute

# Track active fetches to prevent cleanup during parallel operations
_active_fetches = 0
_active_fetches_lock = threading.Lock()


def cleanup_stale_tabs(force: bool = False) -> int:
    """Close stale about:blank tabs to prevent tab accumulation.

    Args:
        force: If True, cleanup regardless of interval

    Returns:
        Number of tabs closed
    """
    global _last_cleanup_time

    # Skip cleanup if any fetches are in progress (could close tabs being used)
    with _active_fetches_lock:
        if _active_fetches > 0:
            return 0

    current_time = time.time()
    if not force and (current_time - _last_cleanup_time) < _cleanup_interval:
        return 0

    _last_cleanup_time = current_time
    closed_count = 0

    try:
        # Get list of tabs from Chrome debug port
        chrome_url = _get_chrome_url()
        result = subprocess.run(
            ['curl', '-s', f'{chrome_url}/json'],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0:
            return 0

        tabs = json.loads(result.stdout)

        # Close about:blank tabs (but keep at least one tab open)
        blank_tabs = [t for t in tabs if t.get('url') == 'about:blank']

        # Keep at least one tab if all are blank
        if len(blank_tabs) == len(tabs):
            blank_tabs = blank_tabs[1:]

        for tab in blank_tabs:
            tab_id = tab.get('id')
            if tab_id:
                try:
                    subprocess.run(
                        ['curl', '-s', f'{chrome_url}/json/close/{tab_id}'],
                        capture_output=True,
                        timeout=2
                    )
                    closed_count += 1
                except Exception:
                    pass

        if closed_count > 0:
            print(f"[CDP] Cleaned up {closed_count} stale about:blank tabs")

    except Exception as e:
        # Don't fail the search if cleanup fails
        pass

    return closed_count


class BotCheckDetected(Exception):
    """Raised when bot verification is detected and needs human intervention"""
    pass


class DailyLimitReached(Exception):
    """Raised when a source's daily search limit is reached"""
    pass


def fetch_page_content(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Fetch page content using Playwright via CDP

    All fetches go through Playwright for consistency. Uses a lock to prevent
    multiple threads from fighting over Chrome.

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: Optional CSS selector to wait for (for JS-heavy sites)

    Raises:
        BotCheckDetected: If bot verification requires human intervention
        DailyLimitReached: If source daily limit is hit
    """
    global _active_fetches

    # Cleanup stale tabs before each fetch (rate-limited to once per minute)
    cleanup_stale_tabs()

    # Track active fetches to prevent cleanup from closing tabs we're using
    with _active_fetches_lock:
        _active_fetches += 1

    try:
        # Acquire semaphore to limit concurrent tabs (max 2 at a time)
        with _browser_semaphore:
            return _fetch_with_playwright(url, source_name=source_name, wait_for_selector=wait_for_selector)
    finally:
        with _active_fetches_lock:
            _active_fetches -= 1


def _check_daily_limit(page, source_name: str = None) -> bool:
    """Check if page shows a daily limit message."""
    try:
        content = page.content().lower()

        limit_indicators = [
            'daily limit',
            'reached your limit',
            'limit reached',
            'search limit',
            'too many searches',
            'come back tomorrow',
        ]

        for indicator in limit_indicators:
            if indicator in content:
                print(f"[LIMIT] Daily limit detected on {source_name}: '{indicator}'")
                return True

        return False

    except Exception as e:
        return False


def _handle_bot_check(page, source_name: str = None, max_attempts: int = 3) -> bool:
    """Detect and attempt to handle bot verification popups.

    Returns:
        True if bot check was handled or not present

    Raises:
        BotCheckDetected: If bot check requires human intervention
    """
    # Full-page blocking overlays
    bot_check_selectors = [
        '#challenge-running',
        '#challenge-form',
        '#cf-wrapper',
        'div.captcha-overlay',
        'div.robot-check-overlay',
    ]

    # CAPTCHA iframes
    captcha_iframe_selectors = [
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="hcaptcha.com/captcha"]',
    ]

    # Clickable checkboxes
    checkbox_selectors = [
        '.recaptcha-checkbox',
        '#recaptcha-anchor',
    ]

    for attempt in range(max_attempts):
        bot_check_found = False
        matched_selector = None

        # Check for full-page blockers
        for selector in bot_check_selectors:
            try:
                elem = page.query_selector(selector)
                if elem and elem.is_visible():
                    bot_check_found = True
                    matched_selector = selector
                    break
            except Exception:
                continue

        # Check for large CAPTCHA iframes
        if not bot_check_found:
            for selector in captcha_iframe_selectors:
                try:
                    elem = page.query_selector(selector)
                    if elem and elem.is_visible():
                        box = elem.bounding_box()
                        if box and box['width'] > 200 and box['height'] > 100:
                            bot_check_found = True
                            matched_selector = selector
                            break
                except Exception:
                    continue

        if not bot_check_found:
            return True  # No bot check

        # Try to click checkbox
        clicked = False
        for selector in checkbox_selectors:
            try:
                element = page.query_selector(selector)
                if element and element.is_visible():
                    element.click()
                    clicked = True
                    time.sleep(2)
                    break
            except Exception:
                continue

        if clicked:
            time.sleep(2)
            continue
        else:
            raise BotCheckDetected(
                f"Bot verification detected on {source_name} requires human intervention."
            )

    # Max attempts reached
    for selector in bot_check_selectors:
        try:
            if page.query_selector(selector):
                raise BotCheckDetected(
                    f"Bot verification on {source_name} could not be automatically dismissed."
                )
        except BotCheckDetected:
            raise
        except Exception:
            continue

    return True


def _fetch_with_playwright(url: str, source_name: str = None, wait_for_selector: str = None) -> str:
    """Fetch page content using Playwright via CDP.

    Args:
        url: URL to fetch
        source_name: Name of source (for logging)
        wait_for_selector: CSS selector to wait for before getting content

    Raises:
        BotCheckDetected: If bot verification requires human intervention
        DailyLimitReached: If daily limit reached
    """
    global _active_fetches
    from playwright.sync_api import sync_playwright

    # Cleanup stale about:blank tabs periodically
    cleanup_stale_tabs()

    # Track active fetches to prevent cleanup from closing tabs we're using
    with _active_fetches_lock:
        _active_fetches += 1

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(_get_chrome_url(), timeout=30000)
            context = browser.contexts[0]

            # Handle dialogs at context level before page creation
            def handle_dialog(dialog):
                try:
                    dialog.accept()
                except Exception:
                    pass
            context.on("dialog", handle_dialog)

            page = context.new_page()
            should_close_tab = True

            try:
                page.goto(url, timeout=30000, wait_until="load")

                # Wait for specific selector if provided
                if wait_for_selector:
                    try:
                        page.wait_for_selector(wait_for_selector, timeout=20000)
                    except Exception:
                        pass  # Continue anyway

                # Small delay for final rendering
                time.sleep(2)

                # Check for bot verification
                try:
                    _handle_bot_check(page, source_name)
                except BotCheckDetected:
                    should_close_tab = False
                    raise

                # Check for daily limit
                if _check_daily_limit(page, source_name):
                    raise DailyLimitReached(
                        f"{source_name} daily search limit reached. Try again tomorrow."
                    )

                return page.content()

            finally:
                if should_close_tab:
                    try:
                        page.close(run_before_unload=False)
                    except Exception:
                        pass
    finally:
        with _active_fetches_lock:
            _active_fetches -= 1
