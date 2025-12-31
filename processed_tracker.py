"""
Processed Tracker - Tracks which person+source combinations have been searched

Uses PostgreSQL search_log table to persist across runs.
Prevents redundant searches across multiple runs.
"""

import os
from datetime import datetime
from threading import Lock
from typing import Dict, List, Optional

import psycopg2
from psycopg2.extras import execute_values


class ProcessedTracker:
    """Database-backed tracking of processed person+source combinations"""

    def __init__(self):
        self.lock = Lock()
        self.db_config = {
            'host': os.environ.get('POSTGRES_HOST', '192.168.20.10'),
            'port': int(os.environ.get('POSTGRES_PORT', 5432)),
            'database': os.environ.get('POSTGRES_DB', 'genealogy_local'),
            'user': os.environ.get('POSTGRES_USER', 'postgres'),
            'password': os.environ.get('POSTGRES_PASSWORD', 'changeme_shared_postgres_password')
        }
        # Local cache to reduce DB queries (refreshed periodically)
        self._cache: Dict[str, set] = {}
        self._cache_loaded = False

    def _get_conn(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)

    def _ensure_cache(self):
        """Load cache from database if not loaded"""
        if self._cache_loaded:
            return
        try:
            with self._get_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT person_id, source_name FROM search_log")
                    for person_id, source_name in cur.fetchall():
                        if person_id not in self._cache:
                            self._cache[person_id] = set()
                        self._cache[person_id].add(source_name)
            self._cache_loaded = True
        except Exception as e:
            print(f"[TRACKER] Failed to load cache: {e}")

    def is_processed(self, person_id: str, source: str) -> bool:
        """Check if person+source combo has been searched"""
        with self.lock:
            self._ensure_cache()
            return source in self._cache.get(person_id, set())

    def mark_processed(self, person_id: str, source: str, result_count: int = 0,
                       had_error: bool = False, error_message: str = None):
        """Mark person+source as processed"""
        with self.lock:
            try:
                with self._get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO search_log (person_id, source_name, result_count, had_error, error_message)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (person_id, source_name)
                            DO UPDATE SET searched_at = NOW(), result_count = EXCLUDED.result_count,
                                          had_error = EXCLUDED.had_error, error_message = EXCLUDED.error_message
                        """, (person_id, source, result_count, had_error, error_message))
                    conn.commit()

                # Update cache
                if person_id not in self._cache:
                    self._cache[person_id] = set()
                self._cache[person_id].add(source)

            except Exception as e:
                print(f"[TRACKER] Failed to mark processed: {e}")

    def get_unprocessed_sources(self, person_id: str, all_sources: List[str]) -> List[str]:
        """Get list of sources not yet searched for this person"""
        with self.lock:
            self._ensure_cache()
            processed = self._cache.get(person_id, set())
            return [s for s in all_sources if s not in processed]

    def get_stats(self) -> Dict:
        """Get processing statistics"""
        with self.lock:
            try:
                with self._get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT COUNT(DISTINCT person_id) FROM search_log")
                        total_people = cur.fetchone()[0]

                        cur.execute("SELECT COUNT(*) FROM search_log")
                        total_searches = cur.fetchone()[0]

                        cur.execute("SELECT source_name, COUNT(*) FROM search_log GROUP BY source_name")
                        by_source = dict(cur.fetchall())

                        return {
                            'total_people': total_people,
                            'total_searches': total_searches,
                            'by_source': by_source
                        }
            except Exception as e:
                print(f"[TRACKER] Failed to get stats: {e}")
                return {'total_people': 0, 'total_searches': 0, 'by_source': {}}

    def clear(self):
        """Clear all tracking data"""
        with self.lock:
            try:
                with self._get_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("TRUNCATE search_log")
                    conn.commit()
                self._cache = {}
                self._cache_loaded = False
                print("[TRACKER] Cleared all search history")
            except Exception as e:
                print(f"[TRACKER] Failed to clear: {e}")

    def refresh_cache(self):
        """Force refresh cache from database"""
        with self.lock:
            self._cache = {}
            self._cache_loaded = False
            self._ensure_cache()


# Global tracker instance
_tracker = None


def get_tracker() -> ProcessedTracker:
    """Get the global processed tracker instance"""
    global _tracker
    if _tracker is None:
        _tracker = ProcessedTracker()
    return _tracker

