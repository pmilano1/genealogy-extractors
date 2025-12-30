#!/usr/bin/env python3
"""
Migrate staged_findings.json to Postgres database.
"""

import json
import os
import psycopg2
from psycopg2.extras import Json

# Database connection - local swarm postgres via SSH tunnel or direct
DB_CONFIG = {
    "host": "192.168.20.10",
    "port": 5432,
    "database": "genealogy_local",
    "user": "postgres",
    "password": "changeme_shared_postgres_password"
}

STAGING_FILE = "staged_findings.json"


def migrate():
    """Migrate JSON findings to Postgres."""
    if not os.path.exists(STAGING_FILE):
        print(f"No staging file found: {STAGING_FILE}")
        return
    
    with open(STAGING_FILE, 'r') as f:
        data = json.load(f)
    
    findings = data.get("findings", [])
    print(f"Found {len(findings)} findings to migrate")
    
    if not findings:
        print("No findings to migrate")
        return
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    inserted = 0
    skipped = 0
    
    for finding in findings:
        try:
            cur.execute("""
                INSERT INTO staged_findings 
                (person_id, person_name, source_name, source_url, 
                 extracted_record, match_score, search_params, 
                 staged_at, status, reviewed_at, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """, (
                finding.get("person_id"),
                finding.get("person_name"),
                finding.get("source_name"),
                finding.get("source_url"),
                Json(finding.get("extracted_record", {})),
                finding.get("match_score"),
                Json(finding.get("search_params", {})),
                finding.get("staged_at"),
                finding.get("status", "pending"),
                finding.get("reviewed_at"),
                finding.get("notes")
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting finding {finding.get('id')}: {e}")
            skipped += 1
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Migration complete: {inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    migrate()

