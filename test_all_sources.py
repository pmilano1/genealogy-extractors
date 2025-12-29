#!/usr/bin/env python3
"""
Test all genealogy sources with multiple names
Diagnose issues and save HTML for analysis
"""

import subprocess
import time
import json
from pathlib import Path

# Test cases
TEST_CASES = [
    {'surname': 'Smith', 'given_name': 'John', 'birth_year': 1875},
    {'surname': 'Weber', 'given_name': 'Marie', 'birth_year': 1880},
    {'surname': 'Rossi', 'given_name': 'Giovanni', 'birth_year': 1885},
]

# All available sources
SOURCES = ['findagrave', 'geneanet', 'antenati', 'familysearch', 'wikitree', 'ancestry', 'myheritage', 'freebmd']

def test_source(source, params):
    """Test a single source with given parameters"""
    print(f"\n{'='*60}")
    print(f"Testing {source.upper()}: {params['given_name']} {params['surname']} (b. {params['birth_year']})")
    print('='*60)
    
    start = time.time()
    
    try:
        result = subprocess.run(
            ['python3', 'extract.py', 
             '--surname', params['surname'],
             '--given-name', params['given_name'],
             '--birth-year', str(params['birth_year']),
             '--source', source,
             '--save-html'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        elapsed = time.time() - start
        
        # Parse output
        output = result.stdout
        
        # Extract record count
        # Format: "✅ Find A Grave → 20 records"
        record_count = 0
        for line in output.split('\n'):
            if '→' in line and 'records' in line:
                try:
                    # Extract number before "records"
                    parts = line.split('→')[1].strip().split()
                    record_count = int(parts[0])
                    break
                except:
                    pass
        
        # Check for errors
        has_error = 'ERROR' in output or 'Failed' in output or result.returncode != 0
        
        status = '✅' if record_count > 0 else ('❌' if has_error else '⚠️')
        
        print(f"{status} {source:15} → {record_count:3} records in {elapsed:.1f}s")
        
        if has_error:
            print(f"   Error: {result.stderr[:200]}")
        
        return {
            'source': source,
            'params': params,
            'record_count': record_count,
            'elapsed': elapsed,
            'success': record_count > 0,
            'error': has_error
        }
        
    except subprocess.TimeoutExpired:
        print(f"❌ {source:15} → TIMEOUT")
        return {
            'source': source,
            'params': params,
            'record_count': 0,
            'elapsed': 60,
            'success': False,
            'error': True
        }
    except Exception as e:
        print(f"❌ {source:15} → ERROR: {str(e)}")
        return {
            'source': source,
            'params': params,
            'record_count': 0,
            'elapsed': 0,
            'success': False,
            'error': True
        }

def main():
    print("="*60)
    print("GENEALOGY EXTRACTOR - COMPREHENSIVE TEST")
    print("="*60)
    
    results = []
    
    for test_case in TEST_CASES:
        print(f"\n\n{'#'*60}")
        print(f"# Test Case: {test_case['given_name']} {test_case['surname']} (b. {test_case['birth_year']})")
        print(f"{'#'*60}")
        
        for source in SOURCES:
            result = test_source(source, test_case)
            results.append(result)
            time.sleep(1)  # Brief pause between sources
    
    # Summary
    print(f"\n\n{'='*60}")
    print("SUMMARY")
    print('='*60)
    
    by_source = {}
    for r in results:
        source = r['source']
        if source not in by_source:
            by_source[source] = {'total': 0, 'success': 0, 'records': 0}
        by_source[source]['total'] += 1
        if r['success']:
            by_source[source]['success'] += 1
        by_source[source]['records'] += r['record_count']
    
    for source in SOURCES:
        stats = by_source.get(source, {'total': 0, 'success': 0, 'records': 0})
        success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
        print(f"{source:15} → {stats['success']}/{stats['total']} tests passed ({success_rate:.0f}%), {stats['records']} total records")
    
    # Save results
    with open('test_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Saved detailed results to test_results.json")

if __name__ == '__main__':
    main()

