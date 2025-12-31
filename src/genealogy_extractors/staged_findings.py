"""
Staged Findings - Database storage for research results pending review.

Findings are stored locally (SQLite or PostgreSQL) and NOT submitted to the
Kindred API until approved.
"""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from .database import get_database, DatabaseBackend
from .config import is_postgresql


# SQL for creating the staged_findings table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS staged_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    person_id TEXT NOT NULL,
    person_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    extracted_record TEXT,
    match_score REAL,
    search_params TEXT,
    staged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    notes TEXT
)
"""

CREATE_TABLE_SQL_PG = """
CREATE TABLE IF NOT EXISTS staged_findings (
    id SERIAL PRIMARY KEY,
    person_id TEXT NOT NULL,
    person_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    extracted_record JSONB,
    match_score REAL,
    search_params JSONB,
    staged_at TIMESTAMP DEFAULT NOW(),
    status TEXT DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    notes TEXT
)
"""


class StagedFindings:
    """Manages locally staged research findings for later review."""

    def __init__(self):
        """Initialize with database from config."""
        self._db: Optional[DatabaseBackend] = None

    def _get_db(self) -> DatabaseBackend:
        """Get database connection, creating table if needed."""
        if self._db is None:
            self._db = get_database()
            self._ensure_table()
        return self._db

    def _ensure_table(self):
        """Create table if it doesn't exist."""
        try:
            sql = CREATE_TABLE_SQL_PG if is_postgresql() else CREATE_TABLE_SQL
            self._db.execute(sql)
        except Exception as e:
            print(f"[STAGED] Warning: Could not create table: {e}")

    def add_finding(
        self,
        person_id: str,
        person_name: str,
        source_name: str,
        source_url: Optional[str],
        extracted_record: Dict[str, Any],
        match_score: float,
        search_params: Dict[str, Any]
    ) -> int:
        """
        Add a new finding to staging.

        Returns:
            The ID of the staged finding
        """
        db = self._get_db()
        # For SQLite, store JSON as string; PostgreSQL uses JSONB
        record_json = json.dumps(extracted_record) if not is_postgresql() else extracted_record
        params_json = json.dumps(search_params) if not is_postgresql() else search_params

        db.execute("""
            INSERT INTO staged_findings
            (person_id, person_name, source_name, source_url,
             extracted_record, match_score, search_params, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
        """, (
            person_id, person_name, source_name, source_url,
            record_json, match_score, params_json
        ))

        # Get the last inserted ID
        row = db.fetchone("SELECT MAX(id) as id FROM staged_findings")
        return row['id'] if row else 0

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all findings pending review."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT * FROM staged_findings WHERE status = 'pending' ORDER BY id"
        )
        return [self._row_to_dict(r) for r in rows]

    def get_by_person(self, person_id: str) -> List[Dict[str, Any]]:
        """Get all findings for a specific person."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT * FROM staged_findings WHERE person_id = %s ORDER BY id",
            (person_id,)
        )
        return [self._row_to_dict(r) for r in rows]

    def approve(self, finding_id: int, notes: Optional[str] = None):
        """Mark a finding as approved for submission."""
        db = self._get_db()
        db.execute(
            """UPDATE staged_findings
               SET status = 'approved', reviewed_at = NOW(), notes = %s
               WHERE id = %s""",
            (notes, finding_id)
        )

    def reject(self, finding_id: int, notes: Optional[str] = None):
        """Mark a finding as rejected."""
        db = self._get_db()
        db.execute(
            """UPDATE staged_findings
               SET status = 'rejected', reviewed_at = NOW(), notes = %s
               WHERE id = %s""",
            (notes, finding_id)
        )

    def get_approved(self) -> List[Dict[str, Any]]:
        """Get all approved findings ready for submission."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT * FROM staged_findings WHERE status = 'approved' ORDER BY id"
        )
        return [self._row_to_dict(r) for r in rows]

    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        db = self._get_db()

        # SQLite doesn't support FILTER, use separate queries
        total = db.fetchone("SELECT COUNT(*) as cnt FROM staged_findings")
        pending = db.fetchone("SELECT COUNT(*) as cnt FROM staged_findings WHERE status = 'pending'")
        approved = db.fetchone("SELECT COUNT(*) as cnt FROM staged_findings WHERE status = 'approved'")
        rejected = db.fetchone("SELECT COUNT(*) as cnt FROM staged_findings WHERE status = 'rejected'")
        reviewed = db.fetchone("SELECT COUNT(*) as cnt FROM staged_findings WHERE reviewed_at IS NOT NULL")

        stats = {
            "total": total['cnt'] if total else 0,
            "pending": pending['cnt'] if pending else 0,
            "approved": approved['cnt'] if approved else 0,
            "rejected": rejected['cnt'] if rejected else 0,
            "reviewed": reviewed['cnt'] if reviewed else 0,
        }
        stats["by_source"] = self._count_by_source()
        return stats

    def _count_by_source(self) -> Dict[str, int]:
        """Count findings by source."""
        db = self._get_db()
        rows = db.fetchall(
            "SELECT source_name, COUNT(*) as count FROM staged_findings GROUP BY source_name"
        )
        return {r["source_name"]: r["count"] for r in rows}

    def _row_to_dict(self, row: Dict) -> Dict[str, Any]:
        """Convert a database row to a finding dict."""
        # Handle JSON fields - SQLite stores as string, PostgreSQL as dict
        extracted = row["extracted_record"]
        if isinstance(extracted, str):
            extracted = json.loads(extracted)
        search = row["search_params"]
        if isinstance(search, str):
            search = json.loads(search)

        # Handle datetime fields - SQLite returns string, PostgreSQL returns datetime
        staged_at = row.get("staged_at")
        if staged_at and hasattr(staged_at, 'isoformat'):
            staged_at = staged_at.isoformat()
        reviewed_at = row.get("reviewed_at")
        if reviewed_at and hasattr(reviewed_at, 'isoformat'):
            reviewed_at = reviewed_at.isoformat()

        return {
            "id": row["id"],
            "person_id": row["person_id"],
            "person_name": row["person_name"],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "extracted_record": extracted,
            "match_score": row["match_score"],
            "search_params": search,
            "staged_at": staged_at,
            "status": row["status"],
            "reviewed_at": reviewed_at,
            "notes": row["notes"]
        }

    def clear_all(self):
        """Clear all findings (use with caution!)."""
        db = self._get_db()
        db.execute("DELETE FROM staged_findings")

    def close(self):
        """Close database connection."""
        if self._db:
            self._db.close()
            self._db = None

