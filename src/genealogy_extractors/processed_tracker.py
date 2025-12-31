"""
Processed Tracker - Tracks which person+source combinations have been searched

Uses database (SQLite or PostgreSQL) to persist across runs.
Prevents redundant searches across multiple runs.
"""

from threading import Lock
from typing import Dict, List, Optional

from .database import get_database, DatabaseBackend


# SQL for creating the search_log table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS search_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    result_count INTEGER DEFAULT 0,
    had_error BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    UNIQUE(person_id, source_name)
)
"""

# PostgreSQL version uses SERIAL instead of AUTOINCREMENT
CREATE_TABLE_SQL_PG = """
CREATE TABLE IF NOT EXISTS search_log (
    id SERIAL PRIMARY KEY,
    person_id TEXT NOT NULL,
    source_name TEXT NOT NULL,
    searched_at TIMESTAMP DEFAULT NOW(),
    result_count INTEGER DEFAULT 0,
    had_error BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    UNIQUE(person_id, source_name)
)
"""


class ProcessedTracker:
    """Database-backed tracking of processed person+source combinations"""

    def __init__(self):
        self.lock = Lock()
        self._db: Optional[DatabaseBackend] = None
        self._cache: Dict[str, set] = {}
        self._cache_loaded = False

    def _get_db(self) -> DatabaseBackend:
        """Get database connection, creating table if needed."""
        if self._db is None:
            self._db = get_database()
            self._ensure_table()
        return self._db

    def _ensure_table(self):
        """Create table if it doesn't exist."""
        from .config import is_postgresql
        try:
            sql = CREATE_TABLE_SQL_PG if is_postgresql() else CREATE_TABLE_SQL
            self._db.execute(sql)
        except Exception as e:
            print(f"[TRACKER] Warning: Could not create table: {e}")

    def _ensure_cache(self):
        """Load cache from database if not loaded"""
        if self._cache_loaded:
            return
        try:
            db = self._get_db()
            rows = db.fetchall("SELECT person_id, source_name FROM search_log")
            for row in rows:
                person_id = row['person_id']
                source_name = row['source_name']
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
                db = self._get_db()
                db.execute("""
                    INSERT INTO search_log (person_id, source_name, result_count, had_error, error_message)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (person_id, source_name)
                    DO UPDATE SET searched_at = NOW(), result_count = excluded.result_count,
                                  had_error = excluded.had_error, error_message = excluded.error_message
                """, (person_id, source, result_count, had_error, error_message))

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
                db = self._get_db()

                row = db.fetchone("SELECT COUNT(DISTINCT person_id) as cnt FROM search_log")
                total_people = row['cnt'] if row else 0

                row = db.fetchone("SELECT COUNT(*) as cnt FROM search_log")
                total_searches = row['cnt'] if row else 0

                rows = db.fetchall("SELECT source_name, COUNT(*) as cnt FROM search_log GROUP BY source_name")
                by_source = {r['source_name']: r['cnt'] for r in rows}

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
                db = self._get_db()
                db.execute("DELETE FROM search_log")
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

