from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Generator

from app.config import settings


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_tables() -> None:
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS config (
                key   TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS games (
                id                  INTEGER PRIMARY KEY,
                date                TEXT NOT NULL UNIQUE,
                day_of_week         TEXT NOT NULL,
                time                TEXT NOT NULL,
                opponent            TEXT NOT NULL,
                status              TEXT DEFAULT 'upcoming',
                listed_price        REAL,
                sold_price          REAL,
                tm_sell_url         TEXT,
                created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS activity_log (
                id         INTEGER PRIMARY KEY,
                game_id    INTEGER REFERENCES games(id),
                action     TEXT NOT NULL,
                details    TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
    # Additive migrations — safe to re-run (no-op if the column already exists)
    with get_connection() as conn:
        for migration_sql in [
            "ALTER TABLE games ADD COLUMN tm_sell_url TEXT",
        ]:
            try:
                conn.execute(migration_sql)
            except sqlite3.OperationalError:
                pass  # column already exists


# ---------------------------------------------------------------------------
# Games queries
# ---------------------------------------------------------------------------

def get_games_for_week(monday: date, sunday: date) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM games
            WHERE date BETWEEN ? AND ?
            ORDER BY date
            """,
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()
    return rows


def get_upcoming_games_for_week(monday: date, sunday: date) -> list[sqlite3.Row]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM games
            WHERE date BETWEEN ? AND ?
              AND status = 'upcoming'
            ORDER BY date
            """,
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()
    return rows


def update_game_status(game_id: int, status: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE games SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, game_id),
        )


def set_game_tm_url(game_id: int, url: str) -> None:
    """Store the Ticketmaster 'sell this game' link for one game."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE games SET tm_sell_url=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (url, game_id),
        )


def mark_listed(game_id: int, listed_price: float) -> None:
    """Owner confirmed the game's tickets are listed on Ticketmaster."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE games SET status='listed', listed_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (listed_price, game_id),
        )


def mark_sold(game_id: int, sold_price: float) -> None:
    """Owner confirmed the game's tickets sold on Ticketmaster."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE games SET status='sold', sold_price=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (sold_price, game_id),
        )


def get_games_by_status(statuses: tuple[str, ...]) -> list[sqlite3.Row]:
    """Games from today forward in any of the given statuses (for confirm commands)."""
    placeholders = ",".join("?" * len(statuses))
    with get_connection() as conn:
        return conn.execute(
            f"""SELECT * FROM games
                WHERE date >= ? AND status IN ({placeholders})
                ORDER BY date""",
            (date.today().isoformat(), *statuses),
        ).fetchall()


def get_game_by_id(game_id: int) -> sqlite3.Row | None:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()


def get_next_games(limit: int = 7) -> list[sqlite3.Row]:
    """Return the next N games from today forward, across any future week."""
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT * FROM games
            WHERE date >= ?
            ORDER BY date
            LIMIT ?
            """,
            (date.today().isoformat(), limit),
        ).fetchall()


def get_all_games() -> list[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute("SELECT * FROM games ORDER BY date").fetchall()


def get_season_summary() -> dict:
    with get_connection() as conn:
        status_rows = conn.execute(
            "SELECT status, COUNT(*) as count FROM games GROUP BY status"
        ).fetchall()
        earnings_row = conn.execute(
            "SELECT COALESCE(SUM(sold_price), 0) as total FROM games WHERE status = 'sold'"
        ).fetchone()
    counts = {r["status"]: r["count"] for r in status_rows}
    return {
        "total": sum(counts.values()),
        "upcoming": counts.get("upcoming", 0),
        "attending": counts.get("attending", 0),
        "skip": counts.get("skip", 0),
        "listed": counts.get("listed", 0),
        "sold": counts.get("sold", 0),
        "earnings": float(earnings_row["total"]) if earnings_row else 0.0,
    }


# ---------------------------------------------------------------------------
# Activity log
# ---------------------------------------------------------------------------

def log_activity(game_id: int | None, action: str, details: dict | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO activity_log (game_id, action, details) VALUES (?, ?, ?)",
            (game_id, action, json.dumps(details) if details else None),
        )


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def get_config(key: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_config(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---------------------------------------------------------------------------
# Week boundary helpers
# ---------------------------------------------------------------------------

def next_week_bounds() -> tuple[date, date]:
    """Return (monday, sunday) for next calendar week."""
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    monday = today + timedelta(days=days_until_monday)
    sunday = monday + timedelta(days=6)
    return monday, sunday


def this_week_bounds() -> tuple[date, date]:
    """Return (monday, sunday) for the current calendar week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday
