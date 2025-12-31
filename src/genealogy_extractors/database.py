"""
Database abstraction layer supporting SQLite and PostgreSQL.

Automatically uses the configured database type from config.json.
Defaults to SQLite if no configuration exists.
"""

import json
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .config import get_database_config, get_sqlite_path, is_postgresql


class DatabaseBackend(ABC):
    """Abstract database backend."""
    
    @abstractmethod
    def execute(self, query: str, params: tuple = None) -> None:
        """Execute a query without returning results."""
        pass
    
    @abstractmethod
    def fetchall(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute a query and return all results as dicts."""
        pass
    
    @abstractmethod
    def fetchone(self, query: str, params: tuple = None) -> Optional[Dict]:
        """Execute a query and return one result as dict."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the connection."""
        pass


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = None
    
    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn
    
    def execute(self, query: str, params: tuple = None) -> None:
        conn = self._get_conn()
        # Convert PostgreSQL placeholders to SQLite
        query = self._convert_query(query)
        conn.execute(query, params or ())
        conn.commit()
    
    def fetchall(self, query: str, params: tuple = None) -> List[Dict]:
        conn = self._get_conn()
        query = self._convert_query(query)
        cursor = conn.execute(query, params or ())
        return [dict(row) for row in cursor.fetchall()]
    
    def fetchone(self, query: str, params: tuple = None) -> Optional[Dict]:
        conn = self._get_conn()
        query = self._convert_query(query)
        cursor = conn.execute(query, params or ())
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def _convert_query(self, query: str) -> str:
        """Convert PostgreSQL syntax to SQLite."""
        # %s -> ?
        query = query.replace("%s", "?")
        # NOW() -> datetime('now')
        query = query.replace("NOW()", "datetime('now')")
        # ON CONFLICT ... DO UPDATE SET -> SQLite upsert
        # This is a simplified conversion for our use case
        if "ON CONFLICT" in query and "DO UPDATE SET" in query:
            query = query.replace("EXCLUDED.", "excluded.")
        return query


class PostgreSQLBackend(DatabaseBackend):
    """PostgreSQL database backend."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = {
            'host': config.get('host', 'localhost'),
            'port': config.get('port', 5432),
            'database': config.get('database', 'genealogy'),
            'user': config.get('user', 'postgres'),
            'password': config.get('password', '')
        }
        self._conn = None
    
    def _get_conn(self):
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(**self.config)
        return self._conn
    
    def execute(self, query: str, params: tuple = None) -> None:
        conn = self._get_conn()
        with conn.cursor() as cur:
            cur.execute(query, params)
        conn.commit()
    
    def fetchall(self, query: str, params: tuple = None) -> List[Dict]:
        from psycopg2.extras import RealDictCursor
        conn = self._get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
    
    def fetchone(self, query: str, params: tuple = None) -> Optional[Dict]:
        from psycopg2.extras import RealDictCursor
        conn = self._get_conn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
    
    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


def get_database() -> DatabaseBackend:
    """Get the configured database backend.

    Tries PostgreSQL if configured, falls back to SQLite on failure.
    """
    config = get_database_config()

    if is_postgresql():
        try:
            backend = PostgreSQLBackend(config)
            # Test connection
            backend._get_conn()
            return backend
        except Exception as e:
            print(f"[DATABASE] PostgreSQL connection failed: {e}")
            print("[DATABASE] Falling back to SQLite")

    return SQLiteBackend(get_sqlite_path())

