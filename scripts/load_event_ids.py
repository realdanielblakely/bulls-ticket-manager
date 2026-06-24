#!/usr/bin/env python3
"""
Load Ticketmaster Account Manager event ids from a saved "My Events" page.

The Bulls' portal (am.ticketmaster.com/durhambulls) is a JavaScript app, so the
event ids only exist in the rendered page. Save the My Events page from a
logged-in browser ("Save Page As → Webpage, Complete") and run this to:

  1. parse each game's date + event id out of the saved HTML,
  2. write the ids into schedule.csv (the committed source of truth), and
  3. sync them into the database.

Re-running is safe and idempotent — it only fills/updates the tm_event_id column
and never touches skip/attend/sold decisions.

Usage (from repo root):
    .venv/bin/python -m scripts.load_event_ids "My Events _ Durham Bulls.html"
"""
from __future__ import annotations

import csv
import html
import re
import sys
from datetime import datetime

from app.config import settings
from app.schedule.csv_import import import_schedule

# id="eventTime{ID}" ...>{Day} • {Mon DD, YYYY} • {time}
_EVENT_RE = re.compile(r'id="eventTime(\d+)"[^>]*>([^<]+)')


def parse_event_ids(html_path: str) -> dict[str, str]:
    """Return {iso_date: event_id} parsed from a saved My Events page."""
    raw = open(html_path, encoding="utf-8").read()
    mapping: dict[str, str] = {}
    for event_id, text in _EVENT_RE.findall(raw):
        parts = [p.strip() for p in html.unescape(text).split("•")]
        if len(parts) < 2:
            continue
        try:
            d = datetime.strptime(parts[1], "%b %d, %Y").date()
        except ValueError:
            continue
        mapping[d.isoformat()] = event_id
    return mapping


def update_csv(mapping: dict[str, str], csv_path: str) -> int:
    """Write event ids into the schedule CSV's tm_event_id column. Returns count set."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fieldnames = list(rows[0].keys()) if rows else ["date", "day_of_week", "time", "opponent"]
    if "tm_event_id" not in fieldnames:
        fieldnames.append("tm_event_id")

    set_count = 0
    for row in rows:
        eid = mapping.get(row["date"].strip())
        if eid and row.get("tm_event_id") != eid:
            row["tm_event_id"] = eid
            set_count += 1
        row.setdefault("tm_event_id", row.get("tm_event_id", ""))

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return set_count


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m scripts.load_event_ids "My Events _ Durham Bulls.html"')
        sys.exit(1)
    html_path = sys.argv[1]

    mapping = parse_event_ids(html_path)
    print(f"Parsed {len(mapping)} event id(s) from {html_path}")

    set_count = update_csv(mapping, settings.schedule_csv_path)
    print(f"Wrote {set_count} id(s) into {settings.schedule_csv_path}")

    import_schedule()  # syncs new rows + tm_event_id into the database
    print("Synced to database.")


if __name__ == "__main__":
    main()
