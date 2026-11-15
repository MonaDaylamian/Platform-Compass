"""Pure, conservative cross-channel summaries of validated Sample Tech Community report snapshots.

No member identities, raw WhatsApp messages, live API calls, or remote AI requests.
Different platform measurements are not added into a fabricated engagement total.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any


THEMES = {
    "Learning & technology": ("learning_and_technology", "AI & Technical Learning"),
    "Career & opportunities": ("career_and_job_opportunities", "Career & Opportunities"),
    "Mentorship & networking": ("mentorship_and_networking", "Networking & Community"),
    "Community & events": ("community_and_events", "Events & Announcements"),
    "Inclusion & inspiration": ("language_and_inclusion", "Women in Tech & Inspiration"),
    "Entrepreneurship": ("entrepreneurship", None),
}

# Meetup titles are *indicative* event subjects, not individual-member interests.
EVENT_KEYWORDS = {
    "Learning & technology": ("ai", "machine learning", "python", "data", "coding", "technical", "cyber", "software", "workshop", "llm"),
    "Career & opportunities": ("career", "job", "interview", "cv", "resume", "leadership", "hiring"),
    "Mentorship & networking": ("mentor", "network", "coffee", "connect", "social"),
    "Community & events": ("community", "meetup", "gathering"),
    "Inclusion & inspiration": ("women in tech", "diversity", "inclusion", "inspir", "founder", "empower"),
    "Entrepreneurship": ("entrepreneur", "startup", "business", "founder"),
}


def membership_summary(counts: dict[str, int | None]) -> dict[str, Any]:
    """Never label an incomplete or overlapping sum as unique people."""
    values = {name: counts.get(name) for name in ("WhatsApp", "LinkedIn", "Meetup")}
    complete = all(type(value) is int and value > 0 for value in values.values())
    return {"counts": values, "total": sum(values.values()) if complete else None,
            "complete": complete}


def _month(value: str | date) -> str:
    return str(value)[:7]


def monthly_activity(whatsapp: dict | None, linkedin: dict | None,
                     meetup_events: list[dict] | None) -> dict[str, Any]:
    """Return 0–100 within-platform peak indices on monthly reporting units.

    WhatsApp periods spanning different calendar months cannot be assigned without
    disaggregation that would compromise the existing approved release boundaries.
    They are excluded rather than split or fabricated.
    """
    counts: dict[str, dict[str, int]] = {}
    excluded = 0
    if whatsapp is not None:
        sums: dict[str, int] = defaultdict(int)
        for item in whatsapp["periods"]:
            start, end = _month(item["start"]), _month(item["end"])
            if start != end:
                excluded += 1
                continue
            sums[start] += item["active_conversations"]
        if sums:
            counts["WhatsApp"] = dict(sums)
    if linkedin is not None:
        counts["LinkedIn"] = {
            row["month"]: row["reactions"] + row["comments"] + row["reposts"]
            for row in linkedin["monthly_content"]
        }
    if meetup_events is not None:
        sums = defaultdict(int)
        for event in meetup_events:
            if event["status"] == "Completed":
                sums[_month(event["date"])] += event["attendees"]
        if sums:
            counts["Meetup"] = dict(sums)

    # Use only the common observed months when making a three-platform comparison;
    # months absent from an export are *missing*, not zero activity.
    common = (set.intersection(*(set(values) for values in counts.values()))
              if len(counts) == 3 else set())
    rows = []
    for channel, data in counts.items():
        # Use a shared reference within each channel (all observed months).
        maximum = max(data.values(), default=0)
        for month, amount in sorted(data.items()):
            rows.append({"platform": channel, "month": month, "activity": amount,
                         "index": round(100 * amount / maximum, 1) if maximum else 0.0,
                         "comparable": month in common})
    peaks = []
    if common:
        by_month = {month: round(sum(
            next(row["index"] for row in rows if row["platform"] == channel and row["month"] == month)
            for channel in ("WhatsApp", "LinkedIn", "Meetup")) / 3, 1)
            for month in common}
        maximum = max(by_month.values())
        peaks = sorted(month for month, value in by_month.items() if value == maximum)
    return {"rows": rows, "common_months": sorted(common), "peak_months": peaks,
            "excluded_whatsapp_periods": excluded, "channels": sorted(counts)}


def interest_evidence(whatsapp: dict | None, linkedin: dict | None,
                      meetup_events: list[dict] | None) -> list[dict]:
    """Report per-platform evidence without summing incomparable measurements."""
    result = []
    wa = {entry["name"]: entry["count"] for entry in
          (whatsapp or {}).get("needs_by_topic", [])}
    li = {entry["topic"]: entry for entry in
          (linkedin or {}).get("topic_analysis", {}).get("topics", [])}
    events = [event for event in (meetup_events or []) if event["status"] == "Completed"]
    for label, (wa_key, li_key) in THEMES.items():
        item = {"theme": label, "whatsapp_conversations": wa.get(wa_key),
                "linkedin_interactions": None, "linkedin_posts": None,
                "meetup_events": None, "meetup_attendances": None}
        if li_key in li:
            item["linkedin_interactions"] = li[li_key]["interactions"]
            item["linkedin_posts"] = li[li_key]["posts"]
        matched = []
        for event in events:
            title = " " + event["title"].casefold() + " "
            if any((" " + word + " ") in title if len(word) <= 3 else word in title
                   for word in EVENT_KEYWORDS[label]):
                matched.append(event)
        if matched:
            item["meetup_events"] = len(matched)
            item["meetup_attendances"] = sum(event["attendees"] for event in matched)
        if any(item[field] is not None for field in (
            "whatsapp_conversations", "linkedin_interactions", "meetup_events")):
            item["platforms"] = sum(item[field] is not None for field in (
                "whatsapp_conversations", "linkedin_interactions", "meetup_events"))
            result.append(item)
    # Breadth first; no numerical cross-platform interest score is implied.
    return sorted(result, key=lambda row: (-row["platforms"], row["theme"]))


def interpret_evidence(interests: list[dict], activity: dict) -> str:
    """Transparent evidence-based narrative, *not* a newly generated AI answer."""
    if not interests:
        return "Insufficient classified evidence to identify shared interests across platforms."
    strongest = [item["theme"] for item in interests if item["platforms"] >= 2]
    if strongest:
        statement = "Themes appearing in multiple platform reports include " + ", ".join(strongest[:3]) + "."
    else:
        statement = "The available reports do not yet establish a theme supported by multiple platforms."
    if activity["peak_months"]:
        statement += " Highest relative activity across all three available monthly series: " + ", ".join(activity["peak_months"]) + "."
    else:
        statement += " A reliable three-platform peak cannot be identified from the overlapping monthly data."
    return statement


def membership_counts_from_sources(sources, *, membership_loader=None):
    """Use exactly the same three canonical platform identifiers as the CSV.

    The community_members.csv is the source of truth where available. LinkedIn
    and Meetup validated reports are secondary fallbacks only when CSV is absent.
    No arbitrary/stale fallback can replace a missing WhatsApp membership count.
    """
    if membership_loader is None:
        from scripts.community_members import load_community_members
        membership_loader = load_community_members
    names = {"whatsapp": "WhatsApp", "linkedin": "LinkedIn", "meetup": "Meetup"}
    counts = {label: None for label in names.values()}
    try:
        csv_members = membership_loader()
    except (OSError, ValueError, TypeError, KeyError):
        csv_members = {}
    for platform, label in names.items():
        if platform in csv_members:
            counts[label] = csv_members[platform]["member_count"]
        elif platform == "linkedin" and sources["linkedin"]:
            counts[label] = sources["linkedin"]["followers_total"]
        elif platform == "meetup" and sources["meetup"]:
            counts[label] = sources["meetup"][1]["members"]
    return membership_summary(counts)

