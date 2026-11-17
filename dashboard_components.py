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


def _reporting_date(value: object) -> str | None:
    """Format validated report date/timestamp; do not invent missing values."""
    if value is None or value == "":
        return None
    try:
        import pandas as pd
        parsed = pd.Timestamp(value)
        if pd.isna(parsed):
            return None
        return parsed.strftime("%d %b %Y")
    except (ValueError, TypeError, OverflowError):
        return None


def render_report_badges(
    period_start: object,
    period_end: object,
    generated_at: object,
    *,
    scope_note: str | None = None,
) -> None:
    """Show purple reporting-period and teal generation-date badges."""
    start = _reporting_date(period_start)
    end = _reporting_date(period_end)
    period = f"{start} – {end}" if start and end else "Unavailable"
    # Viewer date (not the data-generation timestamp).
    from datetime import datetime
    from zoneinfo import ZoneInfo
    viewed = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d %b %Y")
    period = html.escape(period)
    viewed = html.escape(viewed)

    st.markdown(
        '<div class="compass-report-badges" aria-label="Reporting information">'
        '<div class="compass-report-badge compass-report-badge--period">'
        '<span class="compass-report-badge__icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="5" width="18" height="16" rx="2"/>'
        '<path d="M7 3v4M17 3v4M3 10h18M8 14h3M13 14h3"/>'
        '</svg></span>'
        '<span class="compass-report-badge__content">'
        '<span class="compass-report-badge__label">REPORTING PERIOD</span>'
        f'<span class="compass-report-badge__value">{period}</span>'
        '</span></div>'
        '<div class="compass-report-badge compass-report-badge--generated">'
        '<span class="compass-report-badge__icon" aria-hidden="true">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="5" width="18" height="16" rx="2"/>'
        '<path d="M7 3v4M17 3v4M3 10h18m-12 5 2 2 4-4"/>'
        '</svg></span>'
        '<span class="compass-report-badge__content">'
        '<span class="compass-report-badge__label">VIEWED ON</span>'
        f'<span class="compass-report-badge__value">{viewed}</span>'
        '</span></div></div>',
        unsafe_allow_html=True,
    )
    if scope_note:
        st.caption(scope_note)


def render_analytics_header(
    title: str, period_start: str, period_end: str, generated_at: str | None,
    *, fallback_date: str | None = None,
) -> None:
    """Shared header used by all three individual analytics dashboards.

    A snapshot/content period-end is not the true report generation time.
    The fallback_date parameter remains accepted for existing callers.
    """
    st.title(title)
    render_report_badges(period_start, period_end, generated_at)


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
