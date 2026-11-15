"""Shared read-only primary-total presentation for the three Sample Tech Community dashboards."""
from __future__ import annotations

import html
import streamlit as st
from rwit_theme import INK, MUTED_INK


def render_overview_total(label: str, amount: int) -> None:
    """Render the larger primary metric INSIDE its own Streamlit bordered container."""
    title = html.escape(str(label))
    number = f"{int(amount):,}"
    st.markdown(
        f'''<div style="min-height:112px;display:flex;flex-direction:column;
                    justify-content:center;gap:8px;">
            <div style="font-size:0.95rem;color:{MUTED_INK};font-weight:600;">{title}</div>
            <div style="font-size:3.5rem;line-height:1.1;letter-spacing:-0.035em;
                        font-weight:850;color:{INK};">{number}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def render_analytics_header(
    title: str, period_start: str, period_end: str, generated_at: str | None,
    *, fallback_date: str | None = None,
) -> None:
    """Unified analytics header. Date displayed is LinkedIn's period end, not build time."""
    import pandas as pd

    st.title(title)
    start = pd.Timestamp(period_start).strftime("%d %B %Y")
    end = pd.Timestamp(period_end).strftime("%d %B %Y")
    st.write(f"**Reporting period:** {start} – {end}")
    reference = shared_reporting_reference_date()
    if reference:
        date = pd.Timestamp(reference).strftime("%d %B %Y")
        st.caption(f"Report generated at: {date}")
    else:
        st.caption("Report generated at: unavailable until LinkedIn report is prepared")


def shared_reporting_reference_date() -> str | None:
    """Use the LinkedIn content end date for the three page-header displays.

    Local preview reads the private validated report; Cloud reads its approved release.
    This is a reporting reference, NOT the actual generation timestamp.
    """
    import json
    import os
    from pathlib import Path

    from scripts.linkedin_reporting import validate_snapshot

    try:
        if os.environ.get("RWIT_LINKEDIN_LOCAL_PREVIEW") == "1":
            root = Path(__file__).resolve().parent
            path = root / "private" / "linkedin" / "report.json"
            report = validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
        else:
            from scripts.linkedin_release import read_release
            try:
                config = st.secrets.get("linkedin", {})
            except FileNotFoundError:
                config = {}
            report = read_release(config.get("release_b64"))
        return report["content_period"][1]
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return None
