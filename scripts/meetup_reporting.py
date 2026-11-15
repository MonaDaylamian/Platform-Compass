"""Read-only, snapshot-based Meetup event reporting for Platform Compass."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "private" / "meetup"
EXPECTED_COLUMNS = ("date", "title", "format", "location", "attendees", "status")
FORMATS = {"Online", "Physical"}
STATUSES = {"Completed", "Cancelled", "Upcoming"}
MAX_EVENTS = 1000


def load_meetup_data(data_dir: Path = DATA_DIR) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate curated snapshot data before displaying it to board viewers."""
    group = json.loads((data_dir / "group_snapshot.json").read_text(encoding="utf-8"))
    required = {"name", "url", "snapshot_date", "report_start", "report_end",
                "members", "rating", "ratings_count", "source"}
    if set(group) not in (required, required | {"report_generated_at_utc"}):
        raise ValueError("Unexpected group snapshot schema")
    if "report_generated_at_utc" in group:
        from datetime import datetime
        try:
            generated = datetime.fromisoformat(group["report_generated_at_utc"])
            if generated.tzinfo is None:
                raise ValueError("Missing timezone")
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid Meetup report generation timestamp") from exc
    start = date.fromisoformat(group["report_start"])
    end = date.fromisoformat(group["report_end"])
    snapshot = date.fromisoformat(group["snapshot_date"])
    if start > end or not (start <= snapshot <= end):
        raise ValueError("Invalid Meetup reporting dates")
    if (not isinstance(group["name"], str) or not group["name"]
            or group["url"] != "https://example.com/"
            or any(type(group[x]) is not int or group[x] < 0 for x in ("members", "ratings_count"))
            or type(group["rating"]) not in (int, float)
            or not 0 <= group["rating"] <= 5):
        raise ValueError("Invalid Meetup group metadata")

    events_path = data_dir / "events_2026.csv"
    if events_path.stat().st_size > 200_000:
        raise ValueError("Meetup data file is unexpectedly large")
    with events_path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
            raise ValueError("Unexpected Meetup CSV columns")
        events = []
        seen = set()
        for row in reader:
            if len(events) >= MAX_EVENTS:
                raise ValueError("Too many Meetup events")
            if None in row or any(v is None or not str(v).strip() for v in row.values()):
                raise ValueError("Incomplete Meetup event")
            event_date = date.fromisoformat(row["date"])
            if not start <= event_date <= end:
                raise ValueError("Event outside reporting period")
            if row["format"] not in FORMATS or row["status"] not in STATUSES:
                raise ValueError("Invalid event format or status")
            if (row["format"] == "Online") != (row["location"] == "Online"):
                raise ValueError("Event format and location disagree")
            if row["status"] == "Upcoming" and event_date <= snapshot:
                raise ValueError("Upcoming event is not after snapshot date")
            if row["status"] == "Completed" and event_date > snapshot:
                raise ValueError("Completed event is after snapshot date")
            attendees = int(row["attendees"])
            if str(attendees) != row["attendees"] or attendees < 0:
                raise ValueError("Invalid attendee number")
            key = (event_date, row["title"])
            if key in seen:
                raise ValueError("Duplicate Meetup event")
            seen.add(key)
            events.append({"date": event_date, "title": row["title"],
                           "format": row["format"], "location": row["location"],
                           "attendees": attendees, "status": row["status"]})
    if not events:
        raise ValueError("No Meetup events")
    return events, group


def summarize_meetup(events: list[dict[str, Any]]) -> dict[str, Any]:
    formats = Counter(e["format"] for e in events)
    statuses = Counter(e["status"] for e in events)

    def top_events(event_format: str) -> list[dict[str, Any]]:
        eligible = [e for e in events if e["format"] == event_format and e["status"] == "Completed"]
        return sorted(eligible, key=lambda e: (-e["attendees"], e["date"], e["title"]))[:5]

    return {
        "overview": [
            {"category": "All events", "count": len(events), "group": "All"},
            {"category": "Online", "count": formats["Online"], "group": "Format"},
            {"category": "Physical", "count": formats["Physical"], "group": "Format"},
            {"category": "Completed", "count": statuses["Completed"], "group": "Status"},
            {"category": "Cancelled", "count": statuses["Cancelled"], "group": "Status"},
            {"category": "Upcoming", "count": statuses["Upcoming"], "group": "Status"},
        ],
        "top_online": top_events("Online"),
        "top_physical": top_events("Physical"),
    }


def validate_meetup_payload(payload: dict) -> tuple[list[dict], dict]:
    """Reject extra fields or invalid values from an owner-approved Cloud release."""
    if not isinstance(payload, dict) or set(payload) != {"group", "events"}:
        raise ValueError("Unexpected Meetup release schema")
    group, events = payload["group"], payload["events"]
    required = {"name", "url", "snapshot_date", "report_start", "report_end", "members", "rating", "ratings_count", "source"}
    if not isinstance(group, dict) or set(group) not in (required, required | {"report_generated_at_utc"}):
        raise ValueError("Invalid Meetup group schema")
    start, end, snapshot = (date.fromisoformat(group[k]) for k in ("report_start", "report_end", "snapshot_date"))
    if start > end or not start <= snapshot <= end:
        raise ValueError("Invalid date range")
    if group["name"] != "Sample Tech Community" or group["url"] != "https://example.com/":
        raise ValueError("Invalid Meetup group")
    if any(type(group[k]) is not int or group[k] < 0 for k in ("members", "ratings_count")) or type(group["rating"]) not in (int, float) or not 0 <= group["rating"] <= 5:
        raise ValueError("Invalid group metrics")
    if not isinstance(events, list) or not 0 < len(events) <= MAX_EVENTS:
        raise ValueError("Invalid event list")
    seen = set()
    verified = []
    for row in events:
        if not isinstance(row, dict) or set(row) != set(EXPECTED_COLUMNS):
            raise ValueError("Unexpected Meetup event fields")
        d = date.fromisoformat(row["date"])
        if not start <= d <= end or row["format"] not in FORMATS or row["status"] not in STATUSES:
            raise ValueError("Invalid event date or enum")
        if any(not isinstance(row[k], str) or not row[k].strip() or len(row[k]) > 500 for k in ("title", "location")):
            raise ValueError("Invalid event text")
        if (row["format"] == "Online") != (row["location"] == "Online"):
            raise ValueError("Format/location mismatch")
        if type(row["attendees"]) is not int or row["attendees"] < 0:
            raise ValueError("Invalid attendance number")
        if row["status"] == "Upcoming" and d <= snapshot or row["status"] == "Completed" and d > snapshot:
            raise ValueError("Invalid event status for snapshot")
        key = (d, row["title"])
        if key in seen:
            raise ValueError("Duplicate Meetup event")
        seen.add(key)
        verified.append({**row, "date": d})
    return verified, group
