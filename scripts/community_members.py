
"""Validated aggregate membership counts for Platform Compass."""

import csv
from io import StringIO
from datetime import date
from pathlib import Path
from rwit_data_mode import is_demo, demo_path

ROOT = Path(__file__).resolve().parents[1]
MEMBERS_FILE = ROOT / "input" / "community_members.csv"

PLATFORMS = {"whatsapp", "meetup", "linkedin"}
COLUMNS = ("platform", "member_count", "as_of_date")


def _parse_membership_csv(raw: str) -> dict:
    if not isinstance(raw, str) or len(raw.encode("utf-8")) > 10_000:
        raise ValueError("Membership snapshot is missing or oversized")
    result = {}
    file = StringIO(raw.lstrip("\ufeff"), newline="")
    reader = csv.DictReader(file)

    if tuple(reader.fieldnames or ()) != COLUMNS:
        raise ValueError("Unexpected membership CSV columns")

    for row in reader:
        if None in row or set(row) != set(COLUMNS):
            raise ValueError("Invalid membership CSV row")

        platform = row["platform"].strip().lower()
        raw_count = row["member_count"].strip()

        if platform not in PLATFORMS or platform in result:
            raise ValueError("Unknown or duplicate platform")

        if not raw_count.isascii() or not raw_count.isdecimal():
            raise ValueError("Member count must be a whole number")

        count = int(raw_count)
        if count <= 0:
            raise ValueError("Member count must be positive")

        snapshot_date = date.fromisoformat(
            row["as_of_date"].strip()
        )

        if snapshot_date > date.today():
            raise ValueError("Membership snapshot cannot be future-dated")

        result[platform] = {
            "member_count": count,
            "as_of_date": snapshot_date.isoformat(),
        }

    if set(result) != PLATFORMS:
        raise ValueError("Exactly three platform records are required")

    return result


def load_community_members(path: Path | None = None) -> dict:
    from rwit_deployment_guard import assert_mode
    import os
    mode = os.environ.get("RWIT_DEPLOYMENT")
    if mode == "private_cloud":
        assert_mode("private_cloud")
        if path is not None:
            raise ValueError("Private Cloud cannot load membership from local files")
        import streamlit as st
        try:
            cfg = st.secrets.get("membership", {})
            raw = cfg.get("csv")
        except (KeyError, FileNotFoundError):
            raw = None
        return _parse_membership_csv(raw)
    if mode == "demo":
        assert_mode("demo")
        if path is not None:
            raise ValueError("Demo cannot override membership source")
        path = demo_path("community_members.csv")
    elif path is None:
        path = demo_path("community_members.csv") if is_demo() else MEMBERS_FILE
    if not path.is_file() or path.stat().st_size > 10_000:
        raise ValueError("Missing or invalid membership snapshot")
    return _parse_membership_csv(path.read_text(encoding="utf-8-sig"))


def get_membership(platform: str) -> dict:
    return load_community_members()[platform.lower()]
