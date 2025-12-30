#!/usr/bin/env python3
"""
Production genealogy extraction script.

Usage:
    # Production: Extract from live sources
    python extract.py --surname Smith --given-name John --birth-year 1850 --source findagrave
    python extract.py --surname Smith --given-name John --birth-year 1850 --all-sources
    
    # Testing: Use fixtures
    python extract.py --test
    python extract.py --test --source findagrave
    python extract.py --test --verbose
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Import all extractors
from extraction.find_a_grave_extractor import FindAGraveExtractor
from extraction.antenati_extractor import AntenatiExtractor
from extraction.geneanet_extractor import GeneanetExtractor
from extraction.wikitree_extractor import WikiTreeExtractor
from extraction.familysearch_extractor import FamilySearchExtractor
from extraction.ancestry_extractor import AncestryExtractor
from extraction.myheritage_extractor import MyHeritageExtractor
from extraction.freebmd_extractor import FreeBMDExtractor
from extraction.filae_extractor import FilaeExtractor
from extraction.geni_extractor import GeniExtractor

# Import CDP client for production fetching
from cdp_client import fetch_page_content, BotCheckDetected, DailyLimitReached
from rate_limiter import get_rate_limiter
from error_tracker import log_error
import requests


# Source configuration
SOURCES = {
    'findagrave': {
        'name': 'Find A Grave',
        'extractor': FindAGraveExtractor(),
        'url_template': 'https://www.findagrave.com/memorial/search?firstname={given_name}&lastname={surname}&birthyear={birth_year}&birthyearfilter=5',
        'test_fixture': 'tests/fixtures/findagrave_johnson_mary.html',
        'test_params': {'surname': 'Johnson', 'given_name': 'Mary', 'birth_year': 1870}
    },
    'geneanet': {
        'name': 'Geneanet',
        'extractor': GeneanetExtractor(),
        'url_template': 'https://en.geneanet.org/fonds/individus/?nom={surname}&prenom={given_name}&type_periode=birth_between&from={birth_year}&to={birth_year_end}&go=1&size=20',
        'test_fixture': 'tests/fixtures/geneanet_dubois_marie.html',
        'test_params': {'surname': 'Dubois', 'given_name': 'Marie', 'birth_year': 1880}
    },
    'antenati': {
        'name': 'Antenati',
        'extractor': AntenatiExtractor(),
        'url_template': 'https://antenati.cultura.gov.it/search-nominative/?cognome={surname}&nome={given_name}',
        'test_fixture': 'tests/fixtures/antenati_milanese_nominative.html',
        'test_params': {'surname': 'Milanese', 'given_name': 'Giovanni', 'birth_year': 1885}
    },
    'familysearch': {
        'name': 'FamilySearch',
        'extractor': FamilySearchExtractor(),
        'url_template': 'https://www.familysearch.org/en/search/record/results?q.givenName={given_name}&q.surname={surname}&q.birthLikeDate={birth_year}',
        'test_fixture': 'tests/fixtures/familysearch_anderson_margaret.html',
        'test_params': {'surname': 'Anderson', 'given_name': 'Margaret', 'birth_year': 1880},
        'wait_for_selector': 'tr[data-testid*="/ark:/"]'  # Wait for results to load
    },
    'wikitree': {
        'name': 'WikiTree',
        'extractor': WikiTreeExtractor(),
        'url_template': None,  # Uses API
        'test_fixture': 'tests/fixtures/wikitree_smith_john_api.json',
        'test_params': {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1880}
    },
    'ancestry': {
        'name': 'Ancestry',
        'extractor': AncestryExtractor(),
        'url_template': 'https://www.ancestry.com/search/?name={given_name}_{surname}&birth={birth_year}-{birth_year_end}',
        'test_fixture': 'tests/fixtures/ancestry_smith_john.html',
        'test_params': {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1880}
    },
    'myheritage': {
        'name': 'MyHeritage',
        'extractor': MyHeritageExtractor(),
        'url_template': 'https://www.myheritage.com/research?action=query&formId=master&formMode=1&qname=Name+fn.{given_name}+fnmo.2+fnmsvos.1+fnmsmi.1+ln.{surname}+lnmo.4+lnmsdm.1+lnmsmf3.1&qevents-event1=Event+et.birth+ey.{birth_year}+epmo.similar&useTranslation=1',
        'test_fixture': 'tests/fixtures/myheritage_smith_john.html',
        'test_params': {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1880},
        'wait_for_selector': '.search_results_list'  # Wait for results to load
    },
    'filae': {
        'name': 'Filae',
        'extractor': FilaeExtractor(),
        'url_template': 'https://www.filae.com/search?ln={surname}&fn={given_name}&sy={birth_year}&ey={birth_year_end}',
        'test_fixture': 'tests/fixtures/filae_sample.html',
        'test_params': {'surname': 'Dubois', 'given_name': 'Marie', 'birth_year': 1875}
    },
    'geni': {
        'name': 'Geni',
        'extractor': GeniExtractor(),
        'url_template': 'https://www.geni.com/search?search_type=people&names={given_name}+{surname}',
        'test_fixture': 'tests/fixtures/geni_sample.html',
        'test_params': {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1880}
    },
    'freebmd': {
        'name': 'FreeBMD',
        'extractor': FreeBMDExtractor(),
        'url_template': None,  # Uses Playwright form fill
        'test_fixture': 'tests/fixtures/freebmd_smith_john.html',
        'test_params': {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1880}
    }
}


def fetch_freebmd_with_playwright(params: dict, verbose: bool = False) -> str:
    """Fetch FreeBMD results using Playwright form submission

    FreeBMD requires POST form submission to get results.
    Has a 3000 record limit - auto-narrows date range if exceeded.
    """
    from error_tracker import log_error
    import os

    try:
        from playwright.sync_api import sync_playwright
        import time

        # Suppress Node.js deprecation warnings
        os.environ['NODE_OPTIONS'] = '--no-deprecation'

        surname = params.get('surname', '') or ''
        given_name = params.get('given_name', '') or ''
        birth_year = params.get('birth_year', 1880)
        # Start with 2-year range to avoid 3000 limit on common names
        birth_year_end = params.get('birth_year_end', birth_year + 2)

        if verbose:
            print(f"[FreeBMD] Searching for {given_name} {surname} ({birth_year}-{birth_year_end})")

        with sync_playwright() as p:
            # Connect to existing Chrome
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]

            # Always create a new page for FreeBMD (avoid stale tabs)
            page = context.new_page()

            # Auto-dismiss any dialogs to prevent crashes
            def safe_dismiss(dialog):
                try:
                    dialog.dismiss()
                except Exception:
                    pass  # Dialog may have already closed
            page.on("dialog", safe_dismiss)

            try:
                # Navigate to search page
                page.goto("https://www.freebmd.org.uk/cgi/search.pl", timeout=30000)
                page.wait_for_selector('form[name="search"]', timeout=10000)

                if verbose:
                    print("[FreeBMD] Filling form...")

                # Check Births checkbox
                births_checkbox = page.locator('input#typeBirths')
                if not births_checkbox.is_checked():
                    births_checkbox.check()

                # Fill form fields
                page.fill('input[name="surname"]', surname)
                if given_name:
                    page.fill('input[name="given"]', given_name)
                page.fill('input[name="start"]', str(birth_year))
                page.fill('input[name="end"]', str(birth_year_end))

                if verbose:
                    print("[FreeBMD] Submitting form...")

                # Submit and wait for results
                page.click('input[name="find"]')

                # Wait for page to load
                time.sleep(4)

                # Get content
                content = page.content()

                # Check if we exceeded the 3000 limit
                if 'maximum number that can be displayed is 3000' in content:
                    if verbose:
                        print("[FreeBMD] Exceeded 3000 limit, narrowing to 1-year range...")

                    # Retry with just the birth year (1-year range)
                    page.goto("https://www.freebmd.org.uk/cgi/search.pl", timeout=30000)
                    page.wait_for_selector('form[name="search"]', timeout=10000)

                    births_checkbox = page.locator('input#typeBirths')
                    if not births_checkbox.is_checked():
                        births_checkbox.check()

                    page.fill('input[name="surname"]', surname)
                    if given_name:
                        page.fill('input[name="given"]', given_name)
                    page.fill('input[name="start"]', str(birth_year))
                    page.fill('input[name="end"]', str(birth_year))  # Same year = 1 year range

                    page.click('input[name="find"]')
                    time.sleep(4)
                    content = page.content()

                    # If still exceeded, we can't narrow further
                    if 'maximum number that can be displayed is 3000' in content:
                        if verbose:
                            print("[FreeBMD] Still exceeded with 1-year range - name too common")
                        return ""

                if verbose:
                    print(f"[FreeBMD] Got {len(content)} bytes")

                return content

            finally:
                # Always close the tab
                page.close()

    except Exception as e:
        error_msg = str(e)
        log_error('freebmd', 'PLAYWRIGHT_ERROR', error_msg, search_params=params)
        print(f"[ERROR] FreeBMD Playwright fetch failed: {error_msg}")
        return ""


def extract_from_source(source_key, params, test_mode=False, verbose=False, save_html=False):
    """Extract records from a single source (production or test mode)"""
    
    source = SOURCES[source_key]
    
    if verbose:
        print(f"\n{'='*80}")
        print(f"Source: {source['name']}")
        if test_mode:
            print(f"Mode: TEST (using fixture)")
            print(f"Fixture: {source['test_fixture']}")
        else:
            print(f"Mode: PRODUCTION (live fetch)")
        print(f"{'='*80}")
    
    try:
        # Get content (from fixture or live)
        if test_mode:
            fixture_path = Path(source['test_fixture'])
            if not fixture_path.exists():
                raise FileNotFoundError(f"Fixture not found: {source['test_fixture']}")
            
            with open(fixture_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use test params
            params = source['test_params']
        
        else:
            # Production: fetch live data
            if source['url_template'] is None:
                # Special handling for API-based sources
                if source_key == 'wikitree':
                    # WikiTree API with rate limiting (200/min, 4000/hr)
                    api_url = "https://api.wikitree.com/api.php"
                    api_params = {
                        'action': 'searchPerson',
                        'FirstName': params.get('given_name', ''),
                        'LastName': params.get('surname', ''),
                        'BirthDate': str(params.get('birth_year', '')),
                        'BirthDateDecade': str((params.get('birth_year', 1900) // 10) * 10),
                        'format': 'json',
                        'limit': 20,
                        'fields': 'Id,Name,FirstName,LastNameAtBirth,BirthDate,BirthLocation,DeathDate'
                    }

                    if verbose:
                        print(f"Fetching WikiTree API: {api_url}")

                    def fetch_wikitree():
                        response = requests.get(api_url, params=api_params, timeout=15)
                        response.raise_for_status()
                        return response.text

                    rate_limiter = get_rate_limiter()
                    content = rate_limiter.retry_with_backoff(fetch_wikitree, source='wikitree')

                elif source_key == 'freebmd':
                    # FreeBMD requires Playwright form submission
                    content = fetch_freebmd_with_playwright(params, verbose)

                else:
                    raise NotImplementedError(f"{source['name']} requires API implementation")
            else:
                # Build URL
                url_params = params.copy()
                if 'birth_year_end' not in url_params and 'birth_year' in url_params:
                    url_params['birth_year_end'] = url_params['birth_year'] + 10

                url = source['url_template'].format(**url_params)

                if verbose:
                    print(f"Fetching: {url}")

                # Pass wait_for_selector if source needs it (for JS-heavy sites)
                wait_selector = source.get('wait_for_selector')
                content = fetch_page_content(url, source_name=source['name'], wait_for_selector=wait_selector)

            # Save HTML if requested
            if save_html:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_name = f"{params.get('given_name', 'unknown')}_{params.get('surname', 'unknown')}_{params.get('birth_year', 'unknown')}"
                filename = f"test/fixtures/{source_key}-{safe_name}-{timestamp}.html"
                Path('test/fixtures').mkdir(parents=True, exist_ok=True)
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"💾 Saved HTML to {filename}")
        
        # Extract records
        records = source['extractor'].extract_records(content, params)
        
        if verbose:
            print(f"\n✅ Extracted {len(records)} records")
            if records:
                print("\n📋 Top 5 results:")
                for i, rec in enumerate(records[:5], 1):
                    name = rec.get('name', 'Unknown')
                    birth = rec.get('birth_year', '?')
                    place = rec.get('birth_place') or 'unknown'
                    score = rec.get('match_score', 0)
                    print(f"  {i}. {name} (b. {birth}) - {place[:40]} [Score: {score}]")
        
        return {
            'source': source['name'],
            'success': True,
            'count': len(records),
            'records': records
        }
    
    except BotCheckDetected as e:
        # Special handling for bot verification - don't mark as processed
        # so we can retry after user clears the CAPTCHA
        error_msg = str(e)
        print(f"\n⚠️  BOT CHECK DETECTED: {source['name']}")
        print(f"   Please complete the verification in the browser, then retry.")

        return {
            'source': source['name'],
            'success': False,
            'error': error_msg,
            'error_type': 'BOT_CHECK',
            'bot_check': True,  # Flag for caller to handle specially
            'records': []
        }

    except DailyLimitReached as e:
        # Daily limit reached - don't mark as processed, skip this source for today
        error_msg = str(e)
        print(f"\n⚠️  DAILY LIMIT REACHED: {source['name']}")
        print(f"   This source has reached its daily search limit. Try again tomorrow.")

        return {
            'source': source['name'],
            'success': False,
            'error': error_msg,
            'error_type': 'DAILY_LIMIT',
            'daily_limit': True,  # Flag for caller to skip this source
            'records': []
        }

    except Exception as e:
        import traceback
        error_msg = str(e)
        stack_trace = traceback.format_exc()

        # Determine error type
        if '429' in error_msg or 'rate limit' in error_msg.lower():
            error_type = 'RATE_LIMIT'
        elif 'timeout' in error_msg.lower():
            error_type = 'TIMEOUT'
        elif 'navigation' in error_msg.lower():
            error_type = 'NAVIGATION'
        elif '404' in error_msg:
            error_type = 'NOT_FOUND'
        else:
            error_type = 'UNKNOWN'

        # Log error for tracking
        log_error(
            source=source_key,
            error_type=error_type,
            message=error_msg,
            search_params=params,
            stack_trace=stack_trace
        )

        if verbose:
            print(f"\n❌ Error: {error_msg}")
            traceback.print_exc()

        return {
            'source': source['name'],
            'success': False,
            'error': error_msg,
            'error_type': error_type,
            'records': []
        }


def main():
    parser = argparse.ArgumentParser(description='Extract genealogy records from online sources')
    
    # Mode selection
    parser.add_argument('--test', action='store_true',
                       help='Test mode: use fixtures instead of live fetching')
    
    # Source selection
    parser.add_argument('--source', choices=list(SOURCES.keys()),
                       help='Extract from specific source only')
    parser.add_argument('--all-sources', action='store_true',
                       help='Extract from all sources')
    
    # Search parameters (required for production mode)
    parser.add_argument('--surname', help='Surname to search')
    parser.add_argument('--given-name', help='Given name to search')
    parser.add_argument('--birth-year', type=int, help='Birth year to search')
    parser.add_argument('--location', help='Location (optional)')
    
    # Output options
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed output')
    parser.add_argument('--output', '-o', help='Save results to JSON file')
    parser.add_argument('--save-html', action='store_true',
                       help='Save fetched HTML to test/fixtures/ directory')
    
    args = parser.parse_args()
    
    # Validation
    if not args.test:
        if not (args.surname and args.given_name and args.birth_year):
            parser.error("Production mode requires --surname, --given-name, and --birth-year")
    
    if not args.source and not args.all_sources and not args.test:
        parser.error("Must specify --source, --all-sources, or --test")

    # Build search params
    params = {
        'surname': args.surname,
        'given_name': args.given_name,
        'birth_year': args.birth_year,
        'location': args.location
    }

    # Determine which sources to use
    if args.test:
        sources_to_run = [args.source] if args.source else list(SOURCES.keys())
    elif args.all_sources:
        sources_to_run = list(SOURCES.keys())
    else:
        sources_to_run = [args.source]

    # Run extraction
    print("="*80)
    if args.test:
        print("GENEALOGY EXTRACTION - TEST MODE")
    else:
        print("GENEALOGY EXTRACTION - PRODUCTION MODE")
        print(f"Searching for: {args.given_name} {args.surname} (b. {args.birth_year})")
    print("="*80)

    results = []
    for source_key in sources_to_run:
        result = extract_from_source(source_key, params, test_mode=args.test, verbose=args.verbose, save_html=args.save_html)
        results.append(result)

        if not args.verbose:
            status = "✅" if result['success'] else "❌"
            count = result.get('count', 0) if result['success'] else 0
            error = f" ({result.get('error', '')[:40]})" if not result['success'] else ""
            print(f"{status} {result['source']:20} → {count:3} records{error}")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    total_records = sum(r.get('count', 0) for r in results if r['success'])
    successful = sum(1 for r in results if r['success'])
    failed = sum(1 for r in results if not r['success'])

    print(f"Sources tested: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total records: {total_records}")

    # Save results if requested
    if args.output:
        output_data = {
            'timestamp': datetime.now().isoformat(),
            'mode': 'test' if args.test else 'production',
            'search_params': params if not args.test else None,
            'results': results
        }

        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2, default=str)
        print(f"\n✅ Results saved to {args.output}")

    # Exit with error code if any tests failed
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()

