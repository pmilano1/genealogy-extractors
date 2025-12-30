#!/usr/bin/env python3
"""Analyze staged findings against genealogy site data"""

import json
import subprocess
import psycopg2
from collections import defaultdict

# Database connection
DB_CONFIG = {
    'host': '192.168.20.10',
    'port': 5432,
    'database': 'genealogy_local',
    'user': 'postgres',
    'password': 'changeme_shared_postgres_password'
}

API_URL = 'https://family.milanese.life/api/graphql'
API_KEY = '390095c80355901c6ffc3e5cc7d4f9194d54faa5b47e98eb5ff662769bc20976'

def query_api(query):
    cmd = [
        'curl', '-s', '-X', 'POST', API_URL,
        '-H', 'Content-Type: application/json',
        '-H', f'X-API-Key: {API_KEY}',
        '-d', json.dumps({'query': query})
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(result.stdout)

def get_staged_findings():
    """Get all staged findings from local DB"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("""
        SELECT person_id, person_name, source_name, match_score, 
               extracted_record, search_params
        FROM staged_findings
        WHERE status = 'pending'
        ORDER BY person_id, match_score DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_people_from_api(person_ids):
    """Get people data from genealogy API"""
    # Query in batches
    people = {}
    for pid in person_ids:
        query = f'''
        query {{
          person(id: "{pid}") {{
            id
            name_full
            birth_year
            birth_place
            death_year
            death_place
          }}
        }}
        '''
        result = query_api(query)
        if result.get('data', {}).get('person'):
            people[pid] = result['data']['person']
    return people

def analyze():
    print("=" * 70)
    print("STAGED FINDINGS ANALYSIS")
    print("=" * 70)

    # Get staged findings
    findings = get_staged_findings()
    print(f"\nTotal staged findings: {len(findings)}")

    # Group by person
    by_person = defaultdict(list)
    for row in findings:
        by_person[row[0]].append({
            'person_name': row[1],
            'source': row[2],
            'score': row[3],
            'record': row[4],
            'params': row[5]
        })

    print(f"Unique people with findings: {len(by_person)}")

    # Get site data for ALL people
    print("\nFetching site data for all people...")
    person_ids = list(by_person.keys())
    site_people = get_people_from_api(person_ids)
    print(f"Got {len(site_people)} people from site")

    # Detailed analysis
    stats = {
        'can_fill_birth_year': [],
        'can_fill_birth_place': [],
        'can_fill_death_year': [],
        'can_fill_death_place': [],
        'conflicts': [],
        'corroborated': [],  # Multiple sources agree
        'ancient_junk': [],  # Pre-1200 data
        'low_quality': [],   # Score < 50
    }

    for pid, person_findings in by_person.items():
        site_person = site_people.get(pid)
        if not site_person:
            continue

        # Filter ancient junk
        name = site_person['name_full']
        if any(x in name for x in ['BC', 'Deceased', '0700', '0800', '0900']):
            stats['ancient_junk'].append(pid)
            continue

        high_score = [f for f in person_findings if f['score'] >= 70]
        low_score = [f for f in person_findings if f['score'] < 50]
        stats['low_quality'].extend([(pid, f['source']) for f in low_score])

        if not high_score:
            continue

        # Check for corroboration (multiple sources agree on birth_year)
        birth_years = {}
        for f in high_score:
            by = f['record'].get('birth_year')
            if by:
                birth_years[by] = birth_years.get(by, 0) + 1

        for by, count in birth_years.items():
            if count >= 2:
                stats['corroborated'].append((pid, name, by, count))

        # Check what we can fill
        for f in high_score:
            rec = f['record']

            # Birth year
            if rec.get('birth_year'):
                try:
                    found_by = int(rec['birth_year'])
                    if not site_person['birth_year']:
                        stats['can_fill_birth_year'].append((pid, name, found_by, f['source'], f['score']))
                    elif abs(site_person['birth_year'] - found_by) > 2:
                        stats['conflicts'].append((pid, name, 'birth_year', site_person['birth_year'], found_by, f['source']))
                except:
                    pass

            # Birth place
            if rec.get('birth_place') and not site_person.get('birth_place'):
                stats['can_fill_birth_place'].append((pid, name, rec['birth_place'], f['source'], f['score']))

            # Death year
            if rec.get('death_year'):
                try:
                    found_dy = int(rec['death_year'])
                    if not site_person.get('death_year'):
                        stats['can_fill_death_year'].append((pid, name, found_dy, f['source'], f['score']))
                except:
                    pass

            # Death place
            if rec.get('death_place') and not site_person.get('death_place'):
                stats['can_fill_death_place'].append((pid, name, rec['death_place'], f['source'], f['score']))

    # Print results
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Ancient/junk people (skipped): {len(stats['ancient_junk'])}")
    print(f"Low quality findings (<50): {len(stats['low_quality'])}")
    print(f"Conflicts detected: {len(stats['conflicts'])}")
    print()
    print(f"✓ Can fill birth_year: {len(stats['can_fill_birth_year'])}")
    print(f"✓ Can fill birth_place: {len(stats['can_fill_birth_place'])}")
    print(f"✓ Can fill death_year: {len(stats['can_fill_death_year'])}")
    print(f"✓ Can fill death_place: {len(stats['can_fill_death_place'])}")
    print(f"✓ Corroborated (2+ sources): {len(stats['corroborated'])}")

    print("\n" + "=" * 70)
    print("HIGH-VALUE: CORROBORATED BIRTH YEARS (2+ sources agree)")
    print("=" * 70)
    for pid, name, by, count in sorted(stats['corroborated'], key=lambda x: -x[3])[:15]:
        print(f"  {name}: birth_year={by} ({count} sources)")

    print("\n" + "=" * 70)
    print("CAN FILL BIRTH YEAR (high confidence)")
    print("=" * 70)
    seen = set()
    for pid, name, by, source, score in sorted(stats['can_fill_birth_year'], key=lambda x: -x[4])[:20]:
        if pid not in seen:
            print(f"  {name}: {by} ({source}, score={score})")
            seen.add(pid)

    print("\n" + "=" * 70)
    print("CONFLICTS (needs review)")
    print("=" * 70)
    for pid, name, field, site_val, found_val, source in stats['conflicts'][:15]:
        print(f"  {name}: {field} site={site_val} vs found={found_val} ({source})")

if __name__ == '__main__':
    analyze()

