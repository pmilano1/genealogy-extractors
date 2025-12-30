"""
Staged Findings - PostgreSQL storage for research results pending review.

Findings are stored in the local swarm Postgres and NOT submitted to the
genealogy API until approved.
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import psycopg2
from psycopg2.extras import Json, RealDictCursor

# Database configuration - can be overridden via environment variables
DB_CONFIG = {
    "host": os.environ.get("STAGING_DB_HOST", "192.168.20.10"),
    "port": int(os.environ.get("STAGING_DB_PORT", "5432")),
    "database": os.environ.get("STAGING_DB_NAME", "genealogy_local"),
    "user": os.environ.get("STAGING_DB_USER", "postgres"),
    "password": os.environ.get("STAGING_DB_PASSWORD", "changeme_shared_postgres_password")
}


class StagedFindings:
    """Manages locally staged research findings in PostgreSQL for later review."""

    def __init__(self, db_config: Dict[str, Any] = None):
        """Initialize with optional custom database config."""
        self.db_config = db_config or DB_CONFIG
        self._conn = None

    def _get_conn(self):
        """Get or create database connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.db_config)
        return self._conn

    def _execute(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute a query with optional fetch."""
        conn = self._get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if fetch:
                result = cur.fetchall()
            else:
                result = None
            conn.commit()
        return result

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
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO staged_findings
                (person_id, person_name, source_name, source_url,
                 extracted_record, match_score, search_params, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (
                person_id, person_name, source_name, source_url,
                Json(extracted_record), match_score, Json(search_params)
            ))
            finding_id = cur.fetchone()[0]
            conn.commit()
        return finding_id

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get all findings pending review."""
        rows = self._execute(
            "SELECT * FROM staged_findings WHERE status = 'pending' ORDER BY id",
            fetch=True
        )
        return [self._row_to_dict(r) for r in rows]

    def get_by_person(self, person_id: str) -> List[Dict[str, Any]]:
        """Get all findings for a specific person."""
        rows = self._execute(
            "SELECT * FROM staged_findings WHERE person_id = %s ORDER BY id",
            (person_id,), fetch=True
        )
        return [self._row_to_dict(r) for r in rows]

    def approve(self, finding_id: int, notes: Optional[str] = None):
        """Mark a finding as approved for submission."""
        result = self._execute(
            """UPDATE staged_findings
               SET status = 'approved', reviewed_at = NOW(), notes = %s
               WHERE id = %s RETURNING id""",
            (notes, finding_id), fetch=True
        )
        if not result:
            raise ValueError(f"Finding {finding_id} not found")

    def reject(self, finding_id: int, notes: Optional[str] = None):
        """Mark a finding as rejected."""
        result = self._execute(
            """UPDATE staged_findings
               SET status = 'rejected', reviewed_at = NOW(), notes = %s
               WHERE id = %s RETURNING id""",
            (notes, finding_id), fetch=True
        )
        if not result:
            raise ValueError(f"Finding {finding_id} not found")

    def get_approved(self) -> List[Dict[str, Any]]:
        """Get all approved findings ready for submission."""
        rows = self._execute(
            "SELECT * FROM staged_findings WHERE status = 'approved' ORDER BY id",
            fetch=True
        )
        return [self._row_to_dict(r) for r in rows]

    def summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        rows = self._execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'approved') as approved,
                COUNT(*) FILTER (WHERE status = 'rejected') as rejected,
                COUNT(*) FILTER (WHERE reviewed_at IS NOT NULL) as reviewed
            FROM staged_findings
        """, fetch=True)
        stats = dict(rows[0]) if rows else {"total": 0, "pending": 0, "approved": 0, "rejected": 0, "reviewed": 0}
        stats["by_source"] = self._count_by_source()
        return stats

    def _count_by_source(self) -> Dict[str, int]:
        """Count findings by source."""
        rows = self._execute(
            "SELECT source_name, COUNT(*) as count FROM staged_findings GROUP BY source_name",
            fetch=True
        )
        return {r["source_name"]: r["count"] for r in rows}

    def _row_to_dict(self, row: Dict) -> Dict[str, Any]:
        """Convert a database row to a finding dict."""
        return {
            "id": row["id"],
            "person_id": row["person_id"],
            "person_name": row["person_name"],
            "source_name": row["source_name"],
            "source_url": row["source_url"],
            "extracted_record": row["extracted_record"],
            "match_score": row["match_score"],
            "search_params": row["search_params"],
            "staged_at": row["staged_at"].isoformat() if row["staged_at"] else None,
            "status": row["status"],
            "reviewed_at": row["reviewed_at"].isoformat() if row["reviewed_at"] else None,
            "notes": row["notes"]
        }

    def clear_all(self):
        """Clear all findings (use with caution!)."""
        self._execute("DELETE FROM staged_findings")

    def close(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

