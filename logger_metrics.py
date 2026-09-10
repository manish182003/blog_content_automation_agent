import sqlite3
import json
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import config

logger = logging.getLogger(__name__)

class MetricsLogger:
    """SQLite-backed metrics logger to track run statistics, reliability, and agent executions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or config.DB_PATH
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    topic TEXT,
                    category TEXT,
                    keyword TEXT,
                    seo_score REAL,
                    groundedness_score REAL,
                    rewrite_attempts INTEGER DEFAULT 0,
                    status TEXT NOT NULL,
                    duration_seconds REAL DEFAULT 0.0,
                    agent_logs TEXT,
                    notion_page_id TEXT,
                    error_message TEXT
                )
            """)
            cursor.execute("DELETE FROM runs WHERE date(timestamp) < date('now', '-30 days')")
            conn.commit()

    def _prune_old_records(self):
        try:
            with self._get_connection() as conn:
                conn.cursor().execute("DELETE FROM runs WHERE date(timestamp) < date('now', '-30 days')")
                conn.commit()
        except Exception:
            pass

    def record_run(
        self,
        run_id: str,
        mode: str,
        status: str,
        topic: Optional[str] = None,
        category: Optional[str] = None,
        keyword: Optional[str] = None,
        seo_score: Optional[float] = None,
        groundedness_score: Optional[float] = None,
        rewrite_attempts: int = 0,
        duration_seconds: float = 0.0,
        agent_logs: Optional[Dict[str, Any]] = None,
        notion_page_id: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Record a completed or failed run into SQLite."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        agent_logs_str = json.dumps(agent_logs or {})

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO runs (
                    run_id, timestamp, mode, topic, category, keyword,
                    seo_score, groundedness_score, rewrite_attempts, status,
                    duration_seconds, agent_logs, notion_page_id, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id, timestamp, mode, topic, category, keyword,
                seo_score, groundedness_score, rewrite_attempts, status,
                duration_seconds, agent_logs_str, notion_page_id, error_message
            ))
            conn.commit()
        logger.info(f"Recorded run {run_id} [Status: {status}, Mode: {mode}] to DB.")

    def has_published_today(self) -> bool:
        """Check if a blog post has already been published to Notion today (for idempotency)."""
        today_str = time.strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM runs 
                WHERE timestamp LIKE ? AND mode = 'LIVE' AND status = 'SUCCESS'
            """, (f"{today_str}%",))
            count = cursor.fetchone()[0]
            return count > 0

    def get_reliability_summary(self) -> Dict[str, Any]:
        """Generate reliability statistics across historical runs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*), AVG(duration_seconds), AVG(seo_score), AVG(groundedness_score) FROM runs")
            total_runs, avg_duration, avg_seo, avg_groundedness = cursor.fetchone()

            cursor.execute("SELECT status, COUNT(*) FROM runs GROUP BY status")
            status_counts = dict(cursor.fetchall())

            cursor.execute("SELECT AVG(rewrite_attempts) FROM runs WHERE rewrite_attempts > 0")
            avg_rewrites = cursor.fetchone()[0] or 0.0

            return {
                "total_runs": total_runs or 0,
                "status_counts": status_counts,
                "success_rate": (status_counts.get("SUCCESS", 0) / total_runs * 100) if total_runs else 0.0,
                "avg_duration_sec": round(avg_duration or 0.0, 2),
                "avg_seo_score": round(avg_seo or 0.0, 2),
                "avg_groundedness_score": round(avg_groundedness or 0.0, 2),
                "avg_rewrite_attempts": round(avg_rewrites, 2)
            }
