"""
Load or refresh the game schedule from a CSV file into the SQLite database.

The CSV must have columns: date, day_of_week, time, opponent
  - date: ISO format YYYY-MM-DD
  - day_of_week: full name e.g. "Tuesday"
  - time: e.g. "6:45 PM"
  - opponent: e.g. "Lehigh Valley IronPigs"

Optional column:
  - tm_event_id: Ticketmaster Account Manager event id for that game

Running this multiple times is safe — existing rows (matched by date) keep their
status (skip/attend/sold), so decisions are preserved. Only tm_event_id is
refreshed from the CSV when present.
"""

from __future__ import annotations

import csv
import sqlite3

from app.config import settings
from app.database import get_connection, log_activity


def import_schedule(csv_path: str | None = None) -> int:
    """
    Import games from CSV into the database.

    Returns the number of new rows inserted.
    """
    path = csv_path or settings.schedule_csv_path

    inserted = 0
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        _validate_headers(reader.fieldnames or [])

        with get_connection() as conn:
            for row in reader:
                date = row["date"].strip()
                day_of_week = row["day_of_week"].strip()
                time = row["time"].strip()
                opponent = row["opponent"].strip()
                tm_event_id = (row.get("tm_event_id") or "").strip()

                if not all([date, day_of_week, time, opponent]):
                    continue  # skip blank rows

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO games (date, day_of_week, time, opponent)
                    VALUES (?, ?, ?, ?)
                    """,
                    (date, day_of_week, time, opponent),
                )
                if cursor.rowcount:
                    inserted += 1

                # Refresh the event id from the CSV without disturbing status.
                if tm_event_id:
                    conn.execute(
                        "UPDATE games SET tm_event_id = ? WHERE date = ?",
                        (tm_event_id, date),
                    )

    if inserted:
        log_activity(None, "schedule_imported", {"rows_inserted": inserted, "source": path})
        print(f"Imported {inserted} new game(s) from {path}")
    else:
        print(f"No new games to import from {path} (all rows already exist)")

    return inserted


def _validate_headers(headers: list[str]) -> None:
    required = {"date", "day_of_week", "time", "opponent"}
    missing = required - {h.strip().lower() for h in headers}
    if missing:
        raise ValueError(f"CSV is missing required columns: {missing}")
