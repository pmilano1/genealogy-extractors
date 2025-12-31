"""
Research Runner - Searches ALL sources for ALL people, stages findings for review.

Usage:
    # Search all sources for all people (with limit)
    python3 research.py --limit 10

    # Search specific source only
    python3 research.py --source geneanet --limit 10

    # Search all sources, no limit (full database scan)
    python3 research.py --all

    # Review staged findings interactively
    python3 research.py --review

    # Show summary of staged findings
    python3 research.py --summary

    # Submit approved findings to API
    python3 research.py --submit-approved
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add src to path for package imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from genealogy_extractors.api_client import get_all_people_iterator, person_to_search_params, submit_research
from genealogy_extractors.staged_findings import StagedFindings
from genealogy_extractors.processed_tracker import get_tracker
from extract import SOURCES, extract_from_source


# Sources to skip:
# - wikitree: API rate-limited (429), web scraping requires 2 pages per person
# - scotlandspeople: Requires login, JavaScript search form, returns 404 on direct URLs
# - billiongraves: Returns 403 Forbidden - actively blocks scraping
# - irishgenealogy: Site redesigned with JavaScript form, no direct search URLs
SKIP_SOURCES = {'wikitree', 'scotlandspeople', 'billiongraves', 'irishgenealogy'}

# Track sources that hit daily limit during this session (cleared on restart)
_daily_limit_sources = set()


def search_source(source_key: str, params: Dict[str, Any], person_id: str, verbose: bool = False) -> Dict[str, Any]:
    """Search a single source - designed to run in a thread.

    Marks the person+source as processed after search (unless bot check or daily limit).
    """
    tracker = get_tracker()
    start_time = time.time()

    try:
        result = extract_from_source(source_key, params, test_mode=False, verbose=verbose)
        elapsed = time.time() - start_time

        # Don't mark as processed if bot check - we want to retry after user clears it
        if result.get('bot_check'):
            return {
                'source': source_key,
                'success': False,
                'records': [],
                'error': result.get('error'),
                'bot_check': True,
                'elapsed': elapsed
            }

        # Don't mark as processed if daily limit - skip for rest of session
        if result.get('daily_limit'):
            _daily_limit_sources.add(source_key)
            return {
                'source': source_key,
                'success': False,
                'records': [],
                'error': result.get('error'),
                'daily_limit': True,
                'elapsed': elapsed
            }

        # Mark as processed (even if no results - we tried)
        tracker.mark_processed(person_id, source_key)

        return {
            'source': source_key,
            'success': result.get('success', False),
            'records': result.get('records', []),
            'error': result.get('error'),
            'elapsed': elapsed
        }
    except Exception as e:
        elapsed = time.time() - start_time
        # Still mark as processed to avoid retrying broken sources
        tracker.mark_processed(person_id, source_key)

        return {
            'source': source_key,
            'success': False,
            'records': [],
            'error': str(e),
            'elapsed': elapsed
        }


def search_all_sources_parallel(
    params: Dict[str, Any],
    source_keys: List[str],
    person_id: str,
    verbose: bool = False,
    max_workers: int = 10
) -> Dict[str, Dict[str, Any]]:
    """
    Search all sources in parallel using thread pool.
    Each source gets its own thread (and CDP tab).

    Args:
        params: Search parameters
        source_keys: List of sources to search
        person_id: Person ID for tracking
        verbose: Show detailed output
        max_workers: Max parallel threads (default: 10, one per source)

    Returns:
        Dict mapping source_key -> result dict
    """
    results = {}

    # Run ALL sources simultaneously - each gets its own browser tab
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all searches
        future_to_source = {
            executor.submit(search_source, source_key, params, person_id, verbose): source_key
            for source_key in source_keys
        }

        # Collect results as they complete
        for future in as_completed(future_to_source):
            source_key = future_to_source[future]
            try:
                results[source_key] = future.result()
            except Exception as e:
                results[source_key] = {
                    'source': source_key,
                    'success': False,
                    'records': [],
                    'error': str(e)
                }

    return results


def run_research(
    sources: Optional[List[str]] = None,
    limit: Optional[int] = None,
    min_score: float = 50.0,
    verbose: bool = False,
    parallel: bool = True,
    max_workers: int = 10
):
    """
    Search sources for all people and stage findings locally.

    Args:
        sources: List of sources to search (None = all available)
        limit: Maximum number of people to process
        min_score: Minimum match score to stage (0-100)
        verbose: Show detailed output
        parallel: Run source searches in parallel (default: True)
        max_workers: Max parallel threads (default: 10, one per source)
    """
    # Determine which sources to use
    if sources:
        source_keys = [s for s in sources if s in SOURCES]
    else:
        source_keys = [k for k in SOURCES.keys() if k not in SKIP_SOURCES]

    staging = StagedFindings()

    processed = 0
    total_staged = 0
    start_time = time.time()

    print("=" * 70)
    print("GENEALOGY RESEARCH RUNNER - Enrichment Mode")
    print("=" * 70)
    print(f"Sources: {', '.join(source_keys)}")
    print(f"Mode: {'PARALLEL' if parallel else 'SEQUENTIAL'} (max {max_workers} workers)")
    print(f"Limit: {limit or 'No limit'}")
    print(f"Min score: {min_score}")
    # Show database info from config
    from genealogy_extractors.config import get_database_config
    db_cfg = get_database_config()
    if db_cfg.get('type') == 'postgresql':
        print(f"Database: {db_cfg['host']}:{db_cfg['port']}/{db_cfg['database']}")
    else:
        print(f"Database: SQLite ({db_cfg.get('sqlite_path', 'default')})")
    print("=" * 70)

    # Track progress
    total_to_process = limit or "?"
    actually_searched = 0  # People we actually searched (not skipped)

    for person in get_all_people_iterator():
        if limit and processed >= limit:
            break

        processed += 1

        # Build search params from person
        params = person_to_search_params(person)

        # Skip if no surname (can't search effectively)
        if not params.get("surname"):
            if verbose:
                print(f"[{processed}/{total_to_process}] {person['name_full']} - SKIP (no surname)")
            continue

        # Add birth_year if available, fall back to estimated_birth_year
        birth_year = person.get("birth_year") or person.get("estimated_birth_year")
        if birth_year:
            # Skip ancient/medieval people - no useful records before 1200
            if birth_year < 1200:
                if verbose:
                    print(f"[{processed}/{total_to_process}] {person['name_full']} - SKIP (born {birth_year}, too ancient)")
                continue
            params["birth_year"] = birth_year
            params["is_estimated_year"] = person.get("birth_year") is None
        else:
            # Default to a wide range if no birth year at all
            params["birth_year"] = 1850
            params["is_estimated_year"] = True

        person_start = time.time()
        person_id = person["id"]

        # Filter out already-processed sources for this person
        tracker = get_tracker()
        unprocessed_sources = tracker.get_unprocessed_sources(person_id, source_keys)

        # Also filter out sources that hit daily limit this session
        if _daily_limit_sources:
            unprocessed_sources = [s for s in unprocessed_sources if s not in _daily_limit_sources]

        if not unprocessed_sources:
            print(f"\n[{processed}/{total_to_process}] {person['name_full']} - SKIP (all sources already searched or at daily limit)")
            continue

        actually_searched += 1
        print(f"\n[{processed}/{total_to_process}] {person['name_full']} (searched: {actually_searched})")
        print(f"    Search: {params['surname']}, {params['given_name']} (~{params.get('birth_year', '?')})")

        skipped_count = len(source_keys) - len(unprocessed_sources)
        if skipped_count > 0:
            skip_reasons = []
            if _daily_limit_sources:
                skip_reasons.append(f"{len(_daily_limit_sources)} at daily limit")
            skip_reasons.append(f"{skipped_count - len(_daily_limit_sources)} already searched")
            print(f"    Skipping: {', '.join(skip_reasons)}")

        person_staged = 0

        if parallel and len(unprocessed_sources) > 1:
            # PARALLEL: Search all sources simultaneously
            print(f"    Searching {len(unprocessed_sources)} sources in parallel...")
            results = search_all_sources_parallel(params, unprocessed_sources, person_id, verbose, max_workers)

            for source_key, result in results.items():
                elapsed = result.get('elapsed', 0)
                if not result['success']:
                    # Special message for bot checks
                    if result.get('bot_check'):
                        print(f"    ⚠️  {source_key}: BOT CHECK ({elapsed:.1f}s) - Please verify in browser and retry")
                    elif result.get('daily_limit'):
                        print(f"    ⚠️  {source_key}: DAILY LIMIT ({elapsed:.1f}s) - Try again tomorrow")
                    elif verbose:
                        print(f"    {source_key}: ERROR ({elapsed:.1f}s) - {result.get('error', 'unknown')[:40]}")
                    continue

                records = result.get('records', [])

                if not records:
                    if verbose:
                        print(f"    {source_key}: 0 results ({elapsed:.1f}s)")
                    continue

                # Stage high-quality matches
                staged_count = 0
                for record in records:
                    score = record.get("match_score", 0)
                    if score >= min_score:
                        staging.add_finding(
                            person_id=person["id"],
                            person_name=person["name_full"],
                            source_name=source_key,
                            source_url=record.get("url"),
                            extracted_record=record,
                            match_score=score,
                            search_params=params
                        )
                        staged_count += 1
                        person_staged += 1
                        total_staged += 1

                print(f"    {source_key}: {len(records)} results, {staged_count} staged ({elapsed:.1f}s)")
        else:
            # SEQUENTIAL: Search sources one at a time
            for source_key in unprocessed_sources:
                try:
                    result = extract_from_source(
                        source_key,
                        params,
                        test_mode=False,
                        verbose=verbose
                    )

                    # Don't mark as processed if bot check - we want to retry later
                    if result.get('bot_check'):
                        print(f"    ⚠️  {source_key}: BOT CHECK - Please verify in browser and retry")
                        continue

                    # Don't mark as processed if daily limit - skip for today
                    if result.get('daily_limit'):
                        print(f"    ⚠️  {source_key}: DAILY LIMIT - Try again tomorrow")
                        continue

                    # Mark as processed
                    tracker.mark_processed(person_id, source_key)

                    if not result['success']:
                        if verbose:
                            print(f"    {source_key}: ERROR - {result.get('error', 'unknown')[:40]}")
                        continue

                    records = result.get('records', [])

                    if not records:
                        print(f"    {source_key}: 0 results")
                        continue

                    # Stage high-quality matches
                    staged_count = 0
                    for record in records:
                        score = record.get("match_score", 0)
                        if score >= min_score:
                            staging.add_finding(
                                person_id=person_id,
                                person_name=person["name_full"],
                                source_name=source_key,
                                source_url=record.get("url"),
                                extracted_record=record,
                                match_score=score,
                                search_params=params
                            )
                            staged_count += 1
                            person_staged += 1
                            total_staged += 1

                    print(f"    {source_key}: {len(records)} results, {staged_count} staged")

                except Exception as e:
                    print(f"    {source_key}: ERROR - {str(e)[:50]}")
                    continue

        person_time = time.time() - person_start
        if person_staged > 0:
            print(f"    → Staged {person_staged} findings ({person_time:.1f}s)")
        else:
            print(f"    → No matches ({person_time:.1f}s)")

    # Final summary
    total_time = time.time() - start_time
    print("\n" + "=" * 70)
    print("RESEARCH COMPLETE")
    print("=" * 70)
    print(f"People processed: {processed}")
    print(f"Findings staged: {total_staged}")
    print(f"Total time: {total_time:.1f}s ({total_time/max(processed,1):.1f}s per person)")
    print("\nRun 'python research_runner.py --review' to review findings")
    staging.close()


def review_findings():
    """Interactive review of staged findings."""
    staging = StagedFindings()
    pending = staging.get_pending()

    print(f"\n{'='*70}")
    print("STAGED FINDINGS REVIEW")
    print(f"{'='*70}")
    summary = staging.summary()
    print(f"Pending: {len(pending)} | Approved: {summary['approved']} | Rejected: {summary['rejected']}")
    print(f"{'='*70}\n")

    if not pending:
        print("No pending findings to review.")
        return

    reviewed = 0
    for finding in pending:
        print(f"\n{'─'*70}")
        print(f"[Finding #{finding['id']}] Score: {finding['match_score']:.1f}%")
        print(f"{'─'*70}")
        print(f"PERSON IN DATABASE: {finding['person_name']}")
        print(f"  ID: {finding['person_id']}")
        print(f"  Searched: {finding['search_params']}")

        print(f"\nFOUND RECORD ({finding['source_name']}):")
        record = finding['extracted_record']
        print(f"  Name: {record.get('name')}")
        print(f"  Birth: {record.get('birth_year')} - {record.get('birth_place')}")
        print(f"  Death: {record.get('death_year')} - {record.get('death_place')}")

        if record.get('raw_data'):
            print(f"\n  Additional data:")
            for k, v in record['raw_data'].items():
                if v:
                    print(f"    {k}: {v}")

        if finding.get('source_url'):
            print(f"\n  URL: {finding['source_url']}")

        print()
        action = input("[a]pprove / [r]eject / [s]kip / [q]uit? ").lower().strip()

        if action == 'a':
            notes = input("Notes (optional): ").strip() or None
            staging.approve(finding['id'], notes)
            print("✓ Approved")
            reviewed += 1
        elif action == 'r':
            notes = input("Reason: ").strip() or None
            staging.reject(finding['id'], notes)
            print("✗ Rejected")
            reviewed += 1
        elif action == 'q':
            break
        # 's' or anything else = skip

    print(f"\nReviewed {reviewed} findings this session.")


def submit_approved():
    """Submit approved findings to the API."""
    staging = StagedFindings()
    approved = staging.get_approved()

    print(f"\n{'='*70}")
    print("SUBMITTING APPROVED FINDINGS")
    print(f"{'='*70}")
    print(f"Approved findings to submit: {len(approved)}")

    if not approved:
        print("No approved findings to submit.")
        return

    confirm = input("\nProceed with submission? [y/N] ").lower().strip()
    if confirm != 'y':
        print("Cancelled.")
        return

    submitted = 0
    errors = 0

    for finding in approved:
        try:
            record = finding['extracted_record']

            # Build source citation
            source = {
                "source_type": "website",
                "source_name": finding['source_name'],
                "source_url": finding.get('source_url', ''),
                "action": "create"
            }

            # Build findings (updates to person)
            findings = {}
            if record.get('birth_year') and not finding['search_params'].get('birth_year'):
                findings['birth_year'] = record['birth_year']
            if record.get('birth_place'):
                findings['birth_place'] = record['birth_place']
            if record.get('death_year'):
                findings['death_year'] = record['death_year']
            if record.get('death_place'):
                findings['death_place'] = record['death_place']

            # Submit to API
            result = submit_research(
                person_id=finding['person_id'],
                source=source,
                confidence="MEDIUM",
                findings=findings if findings else None,
                notes=finding.get('notes', f"Enrichment from {finding['source_name']}")
            )

            if result.get('success'):
                print(f"✓ Submitted finding #{finding['id']} for {finding['person_name']}")
                submitted += 1
            else:
                print(f"✗ Failed to submit finding #{finding['id']}")
                errors += 1

        except Exception as e:
            print(f"✗ Error submitting finding #{finding['id']}: {e}")
            errors += 1

    print(f"\nSubmitted: {submitted} | Errors: {errors}")


def show_summary():
    """Show summary of staged findings."""
    staging = StagedFindings()
    summary = staging.summary()

    print(f"\n{'='*50}")
    print("STAGED FINDINGS SUMMARY")
    print(f"{'='*50}")
    print(f"Total findings: {summary['total']}")
    print(f"Pending review: {summary['pending']}")
    print(f"Approved: {summary['approved']}")
    print(f"Rejected: {summary['rejected']}")
    print(f"\nBy source:")
    for source, count in summary.get('by_source', {}).items():
        print(f"  {source}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Search all sources for all people, stage findings for review",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python research_runner.py --limit 5              # Search 5 people, all sources
  python research_runner.py --source geneanet      # Search all people, Geneanet only
  python research_runner.py --all                  # Full database scan (careful!)
  python research_runner.py --review               # Review staged findings
  python research_runner.py --submit-approved      # Submit approved to API
        """
    )

    # Actions
    parser.add_argument("--review", action="store_true",
                        help="Review staged findings interactively")
    parser.add_argument("--summary", action="store_true",
                        help="Show summary of staged findings")
    parser.add_argument("--submit-approved", action="store_true",
                        help="Submit approved findings to API")
    parser.add_argument("--errors", action="store_true",
                        help="Show error tracking summary")

    # Research options
    parser.add_argument("--source", choices=list(SOURCES.keys()),
                        help="Search specific source only")
    parser.add_argument("--limit", type=int,
                        help="Maximum number of people to process")
    parser.add_argument("--all", action="store_true",
                        help="Process all people (no limit)")
    parser.add_argument("--min-score", type=float, default=80.0,
                        help="Minimum match score to stage (default: 80)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show detailed output")
    parser.add_argument("--sequential", action="store_true",
                        help="Disable parallel searching (one source at a time)")
    parser.add_argument("--workers", type=int, default=16,
                        help="Max parallel workers (default: 16, browser limited to 4 tabs)")
    parser.add_argument("--stats", action="store_true",
                        help="Show processing statistics")
    parser.add_argument("--reset", action="store_true",
                        help="Reset processed tracking (re-search everything)")

    args = parser.parse_args()

    # Dispatch to appropriate action
    if args.review:
        review_findings()
    elif args.summary:
        show_summary()
    elif args.submit_approved:
        submit_approved()
    elif args.errors:
        from genealogy_extractors.error_tracker import get_error_tracker
        tracker = get_error_tracker()
        summary = tracker.get_summary()
        print("=" * 50)
        print("ERROR TRACKING SUMMARY")
        print("=" * 50)
        print(f"Total errors logged: {summary['total_errors']}")
        print("\nBy source:")
        for source, count in sorted(summary['by_source'].items(), key=lambda x: -x[1]):
            print(f"  {source}: {count}")
        print("\nBy error type:")
        for etype, count in sorted(summary['by_type'].items(), key=lambda x: -x[1]):
            print(f"  {etype}: {count}")
        print("\nTop errors:")
        for error_key, count in summary['top_errors']:
            print(f"  {error_key}: {count}")
    elif args.stats:
        tracker = get_tracker()
        stats = tracker.get_stats()
        print("=" * 50)
        print("PROCESSING STATISTICS")
        print("=" * 50)
        print(f"Total people searched: {stats['total_people']}")
        print(f"Total source searches: {stats['total_searches']}")
        print("\nSearches by source:")
        for source, count in sorted(stats['by_source'].items(), key=lambda x: -x[1]):
            print(f"  {source}: {count}")
    elif args.reset:
        tracker = get_tracker()
        tracker.clear()
        print("Processed tracking cleared - next run will search all sources")
    elif args.limit or args.all or args.source:
        if not args.all and not args.limit:
            args.limit = 10  # Default safety limit

        sources = [args.source] if args.source else None
        run_research(
            sources=sources,
            limit=args.limit if not args.all else None,
            min_score=args.min_score,
            verbose=args.verbose,
            parallel=not args.sequential,
            max_workers=args.workers
        )
    else:
        parser.print_help()
        sys.exit(1)

