from __future__ import annotations

import pathlib
import sqlite3
from datetime import datetime
from itertools import groupby as _groupby

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.database import get_all_games, get_season_summary

_TEMPLATES_DIR = pathlib.Path(__file__).parent / "templates"

dashboard_app = FastAPI(title="Bulls Ticket Manager")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_META = {
    "upcoming":    {"label": "Upcoming",    "css": "bg-slate-600 text-slate-200"},
    "attending":   {"label": "Attending",   "css": "bg-green-600 text-green-100"},
    "skip":        {"label": "Decide",      "css": "bg-amber-500 text-amber-900"},
    "to_list":     {"label": "To List",     "css": "bg-orange-500 text-orange-100"},
    "listed":      {"label": "Listed",      "css": "bg-blue-600 text-blue-100"},
    "sold":        {"label": "Sold",        "css": "bg-yellow-500 text-yellow-900"},
    "to_transfer": {"label": "To Transfer", "css": "bg-purple-500 text-purple-100"},
    "transferred": {"label": "Transferred", "css": "bg-fuchsia-600 text-fuchsia-100"},
}


def _enrich(row: sqlite3.Row) -> dict:
    d = dict(row)
    dt = datetime.strptime(d["date"], "%Y-%m-%d")
    d["date_display"] = dt.strftime("%a, %b %-d")
    d["month_label"] = dt.strftime("%B %Y")
    meta = _STATUS_META.get(d["status"], _STATUS_META["upcoming"])
    d["status_label"] = meta["label"]
    d["status_css"] = meta["css"]
    return d


def _group_by_month(games: list[dict]) -> list[tuple[str, list[dict]]]:
    result = []
    for month, group in _groupby(games, key=lambda g: g["month_label"]):
        result.append((month, list(group)))
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@dashboard_app.get("/", response_class=HTMLResponse)
async def season_overview(request: Request) -> HTMLResponse:
    games = [_enrich(g) for g in get_all_games()]
    grouped = _group_by_month(games)
    summary = get_season_summary()
    return templates.TemplateResponse("season.html", {
        "request": request,
        "grouped": grouped,
        "summary": summary,
    })
