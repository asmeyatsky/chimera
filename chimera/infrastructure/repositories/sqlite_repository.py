"""
SQLite Repository

Architectural Intent:
- Persistent storage backend using SQLite (stdlib, zero external deps)
- Stores drift history, playbook runs, and SLO tracking
- Provides a clean repository interface for domain services
- Uses WAL mode for concurrent read/write support

Design Decisions:
- Single database file at configurable path (default: chimera.db)
- Auto-creates tables on first use
- Thread-safe via sqlite3's check_same_thread=False
- Timestamps stored as ISO 8601 strings
"""

from __future__ import annotations
import sqlite3
import json
import logging
from dataclasses import asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SQLiteRepository:
    """Persistent storage using SQLite."""

    def __init__(self, db_path: str = "chimera.db"):
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self) -> None:
        """Open database connection and create tables."""
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info("SQLite repository connected: %s", self._db_path)

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _create_tables(self) -> None:
        """Create tables if they don't exist."""
        assert self._conn is not None
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS drift_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                expected_hash TEXT,
                actual_hash TEXT,
                severity TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                resolved_at TEXT,
                resolution_time_seconds REAL,
                details TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS playbook_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playbook_id TEXT NOT NULL,
                playbook_name TEXT NOT NULL,
                node_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                step_results TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS slo_violations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slo_name TEXT NOT NULL,
                target_availability REAL NOT NULL,
                actual_availability REAL NOT NULL,
                violated_at TEXT NOT NULL,
                window_hours INTEGER NOT NULL,
                details TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS healing_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                command TEXT NOT NULL,
                success INTEGER NOT NULL,
                executed_at TEXT NOT NULL,
                duration_seconds REAL,
                output TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_drift_node ON drift_events(node_id);
            CREATE INDEX IF NOT EXISTS idx_drift_detected ON drift_events(detected_at);
            CREATE INDEX IF NOT EXISTS idx_playbook_node ON playbook_runs(node_id);
            CREATE INDEX IF NOT EXISTS idx_healing_node ON healing_actions(node_id);
        """)

    # -- Drift Events --------------------------------------------------------

    def record_drift(
        self,
        node_id: str,
        severity: str,
        expected_hash: str = "",
        actual_hash: str = "",
        details: str = "",
    ) -> int:
        """Record a drift event. Returns the event ID."""
        assert self._conn is not None
        cursor = self._conn.execute(
            """INSERT INTO drift_events
               (node_id, expected_hash, actual_hash, severity, detected_at, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (node_id, expected_hash, actual_hash, severity,
             datetime.now(UTC).isoformat(), details),
        )
        self._conn.commit()
        return cursor.lastrowid

    def resolve_drift(self, event_id: int, resolution_time_seconds: float) -> None:
        """Mark a drift event as resolved."""
        assert self._conn is not None
        self._conn.execute(
            """UPDATE drift_events
               SET resolved_at = ?, resolution_time_seconds = ?
               WHERE id = ?""",
            (datetime.now(UTC).isoformat(), resolution_time_seconds, event_id),
        )
        self._conn.commit()

    def get_drift_history(
        self,
        node_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get drift event history, optionally filtered by node."""
        assert self._conn is not None
        if node_id:
            rows = self._conn.execute(
                "SELECT * FROM drift_events WHERE node_id = ? ORDER BY detected_at DESC LIMIT ?",
                (node_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM drift_events ORDER BY detected_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_unresolved_drifts(self) -> list[dict]:
        """Get all unresolved drift events."""
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM drift_events WHERE resolved_at IS NULL ORDER BY detected_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Playbook Runs -------------------------------------------------------

    def record_playbook_run(
        self,
        playbook_id: str,
        playbook_name: str,
        node_id: str,
        status: str,
        step_results: list[dict] | None = None,
    ) -> int:
        """Record a playbook execution. Returns the run ID."""
        assert self._conn is not None
        cursor = self._conn.execute(
            """INSERT INTO playbook_runs
               (playbook_id, playbook_name, node_id, status, started_at, step_results)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (playbook_id, playbook_name, node_id, status,
             datetime.now(UTC).isoformat(),
             json.dumps(step_results or [])),
        )
        self._conn.commit()
        return cursor.lastrowid

    def complete_playbook_run(self, run_id: int, status: str) -> None:
        """Mark a playbook run as completed."""
        assert self._conn is not None
        self._conn.execute(
            "UPDATE playbook_runs SET status = ?, completed_at = ? WHERE id = ?",
            (status, datetime.now(UTC).isoformat(), run_id),
        )
        self._conn.commit()

    def get_playbook_runs(
        self,
        node_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get playbook run history."""
        assert self._conn is not None
        if node_id:
            rows = self._conn.execute(
                "SELECT * FROM playbook_runs WHERE node_id = ? ORDER BY started_at DESC LIMIT ?",
                (node_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM playbook_runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- SLO Violations ------------------------------------------------------

    def record_slo_violation(
        self,
        slo_name: str,
        target_availability: float,
        actual_availability: float,
        window_hours: int,
        details: str = "",
    ) -> int:
        """Record an SLO violation. Returns the violation ID."""
        assert self._conn is not None
        cursor = self._conn.execute(
            """INSERT INTO slo_violations
               (slo_name, target_availability, actual_availability, violated_at, window_hours, details)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (slo_name, target_availability, actual_availability,
             datetime.now(UTC).isoformat(), window_hours, details),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_slo_violations(self, limit: int = 50) -> list[dict]:
        """Get SLO violation history."""
        assert self._conn is not None
        rows = self._conn.execute(
            "SELECT * FROM slo_violations ORDER BY violated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # -- Healing Actions -----------------------------------------------------

    def record_healing_action(
        self,
        node_id: str,
        action_type: str,
        command: str,
        success: bool,
        duration_seconds: float = 0.0,
        output: str = "",
    ) -> int:
        """Record a healing action. Returns the action ID."""
        assert self._conn is not None
        cursor = self._conn.execute(
            """INSERT INTO healing_actions
               (node_id, action_type, command, success, executed_at, duration_seconds, output)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (node_id, action_type, command, int(success),
             datetime.now(UTC).isoformat(), duration_seconds, output),
        )
        self._conn.commit()
        return cursor.lastrowid

    def get_healing_history(
        self,
        node_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get healing action history."""
        assert self._conn is not None
        if node_id:
            rows = self._conn.execute(
                "SELECT * FROM healing_actions WHERE node_id = ? ORDER BY executed_at DESC LIMIT ?",
                (node_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM healing_actions ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # -- Stats ---------------------------------------------------------------

    def get_drift_count(self, node_id: Optional[str] = None) -> int:
        """Get total drift event count."""
        assert self._conn is not None
        if node_id:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM drift_events WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM drift_events").fetchone()
        return row[0]

    def get_mean_resolution_time(self, node_id: Optional[str] = None) -> Optional[float]:
        """Get average drift resolution time in seconds."""
        assert self._conn is not None
        if node_id:
            row = self._conn.execute(
                """SELECT AVG(resolution_time_seconds) FROM drift_events
                   WHERE node_id = ? AND resolution_time_seconds IS NOT NULL""",
                (node_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT AVG(resolution_time_seconds) FROM drift_events WHERE resolution_time_seconds IS NOT NULL"
            ).fetchone()
        return row[0]
