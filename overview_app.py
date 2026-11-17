"""Board-safe Platform Compass landing page using existing validated releases."""

from __future__ import annotations

from pathlib import Path
from html import escape
import os

import altair as alt
import pandas as pd
import streamlit as st

from rwit_data_mode import is_demo, demo_path
from scripts.community_overview import membership_counts_from_sources
from scripts.community_overview import (
    interest_evidence, monthly_activity,
)
from rwit_theme import CHART_GREEN, CHART_PURPLE, CHART_YELLOW
from dashboard_components import render_report_badges


def _load_sources():
    """Reuse exactly the same validated sources as the individual analytics pages."""
    sources = {"whatsapp": None, "linkedin": None, "meetup": None}
    errors = []
    try:
        from whatsapp_app import read_prepared_report
        sources["whatsapp"] = read_prepared_report()
    except (OSError, ValueError, TypeError, ImportError, KeyError) as exc:
        errors.append("WhatsApp report unavailable")
    try:
        from linkedin_app import _report
        sources["linkedin"] = _report()
    except (OSError, ValueError, TypeError, ImportError, KeyError) as exc:
        errors.append("LinkedIn report unavailable")
    try:
        from scripts.meetup_reporting import load_meetup_data
        from scripts.meetup_release import read_release
        if is_demo():
            sources["meetup"] = load_meetup_data(demo_path("meetup"))
        elif os.environ.get("RWIT_MEETUP_LOCAL_PREVIEW") == "1":
            sources["meetup"] = load_meetup_data()
        else:
            try:
                cfg = st.secrets.get("meetup", {})
            except FileNotFoundError:
                cfg = {}
            sources["meetup"] = read_release(cfg.get("release_b64"))
    except (OSError, ValueError, TypeError, ImportError, KeyError) as exc:
        errors.append("Meetup report unavailable")
    return sources, errors





def _render_interest_section(interests: list[dict]) -> str:
    """Render the five most widely supported themes without combining metrics."""
    cards = []
    for item in interests[:5]:
        evidence = []
        conversations = item.get("whatsapp_conversations")
        if conversations is not None:
            evidence.append(
                '<span class="rwit-interest-chip rwit-interest-chip--whatsapp">'
                '<span class="rwit-interest-chip__icon rwit-interest-chip__icon--whatsapp" aria-hidden="true">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M20 11.5a8.5 8.5 0 0 1-12.7 7.4L3 20l1.2-4.2A8.5 8.5 0 1 1 20 11.5Z"/>'
                '<path d="M8.5 8.5c.4 2.9 2.4 5 5.3 6l1.5-1.3 1.4 1.3c-.3 1.1-1.5 1.9-3 1.5-3.9-1-6-3.1-6.7-6.9-.2-1.2.4-2.2 1.4-2.7Z"/>'
                '</svg></span>'
                f'<strong>WhatsApp</strong> · {int(conversations):,} conversations</span>'
            )
        interactions = item.get("linkedin_interactions")
        if interactions is not None:
            evidence.append(
                '<span class="rwit-interest-chip rwit-interest-chip--linkedin">'
                '<span class="rwit-interest-chip__icon rwit-interest-chip__icon--linkedin" aria-hidden="true">in</span>'
                f'<strong>LinkedIn</strong> · {int(interactions):,} interactions '
                f'({int(item["linkedin_posts"]):,} posts)</span>'
            )
        events = item.get("meetup_events")
        if events is not None:
            evidence.append(
                '<span class="rwit-interest-chip rwit-interest-chip--meetup">'
                '<span class="rwit-interest-chip__icon rwit-interest-chip__icon--meetup" aria-hidden="true">m</span>'
                f'<strong>Meetup</strong> · {int(events):,} completed events, '
                f'{int(item["meetup_attendances"]):,} attendances</span>'
            )
        theme = escape(str(item["theme"]))
        platform_count = int(item["platforms"])
        cards.append(
            '<article class="rwit-interest-card">'
            '<div class="rwit-interest-card__heading">'
            f'<span class="rwit-interest-card__title">{theme}</span>'
            f'<span class="rwit-interest-card__scope">Evidence from {platform_count} '
            f'platform{"s" if platform_count != 1 else ""}</span>'
            '</div>'
            '<div class="rwit-interest-card__evidence">' + ''.join(evidence) + '</div>'
            '</article>'
        )
    content = ''.join(cards) if cards else (
        '<p class="rwit-interests__note">'
        'There is not enough classified evidence to show community interests.</p>'
    )
    return (
        '<section class="rwit-interests" aria-label="Main interests across all platforms">'
        '<div class="rwit-interests__cards">' + content + '</div>'
        '</section>'
    )

def show_overview() -> None:
    # Match WhatsApp Analytics metadata, not a potentially misleading union
    # of independent LinkedIn, Meetup and WhatsApp date ranges.
    sources, _errors = _load_sources()
    whatsapp = sources["whatsapp"]
    if whatsapp:
        period = whatsapp["period"]
        render_report_badges(
            period["start"], period["end"], whatsapp.get("generated_at_utc"),
            scope_note=(
                "Dates refer to the WhatsApp report. LinkedIn and Meetup "
                "may cover different reporting periods."
            ),
        )
    else:
        render_report_badges(
            None, None, None,
            scope_note="WhatsApp reporting metadata is currently unavailable.",
        )
    st.markdown(
        "**Platform Compass** is a data analytics application designed to help "
        "Sample Tech Community understand community engagement and make "
        "informed decisions. It brings together data from LinkedIn, Meetup, "
        "and WhatsApp into clear, interactive dashboards, providing insights "
        "into community activity, growth, and engagement trends while "
        "respecting member privacy."
    )
    wa = sources["whatsapp"]
    li = sources["linkedin"]
    events = sources["meetup"][0] if sources["meetup"] else None
    members = membership_counts_from_sources(sources)

    with st.container(border=True):
        st.subheader("Community at a Glance")
        total_col, chart_col = st.columns([1, 2], gap="large")
        with total_col:
            st.metric("Combined platform memberships",
                      f"{members['total']:,}" if members["complete"] else "Unavailable")
            st.caption("Sum of platform memberships, not unique people. A member may appear on several platforms.")
            if not members["complete"]:
                st.info("The combined total requires a current count for all three platforms.")
        with chart_col:
            st.markdown("**Community size by platform**")
            counts = [{"platform": key, "members": value} for key, value in members["counts"].items()
                      if value is not None]
            if counts:
                frame = pd.DataFrame(counts)
                chart = (alt.Chart(frame).mark_bar(cornerRadiusEnd=5).encode(
                    x=alt.X("members:Q", title="Platform memberships", axis=alt.Axis(format=",d")),
                    y=alt.Y("platform:N", sort=["WhatsApp", "LinkedIn", "Meetup"], title=None),
                    color=alt.Color("platform:N", legend=None,
                        scale=alt.Scale(domain=["WhatsApp", "LinkedIn", "Meetup"],
                                        range=[CHART_GREEN, CHART_PURPLE, CHART_YELLOW])),
                    tooltip=["platform:N", alt.Tooltip("members:Q", format=",d")],
                ).properties(height=180))
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No validated platform membership counts available.")
            if any(value is None for value in members["counts"].values()):
                st.caption("Unavailable platform counts are excluded from the bars.")

    interests = interest_evidence(wa, li, events)
    # Keyed containers allow section-specific spacing through the shared CSS.
    # Headings retain the same Streamlit markdown styling as the platform chart.
    with st.container(key="overview_interests_section"):
        st.markdown("**Main Interests Across All Platforms**")
        st.markdown(_render_interest_section(interests), unsafe_allow_html=True)

    activity = monthly_activity(wa, li, events)
    with st.container(key="overview_engagement_section"):
        st.markdown("**Engagement Over Time**")
        series = activity["rows"]
        if series:
            df = pd.DataFrame(series)
            chart = (alt.Chart(df).mark_line(point=True).encode(
                x=alt.X("month:N", title="Month", sort=sorted({row["month"] for row in series})),
                y=alt.Y("index:Q", title="Within-platform activity index", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("platform:N", title="Platform", scale=alt.Scale(
                    domain=["WhatsApp", "LinkedIn", "Meetup"],
                    range=[CHART_GREEN, CHART_PURPLE, CHART_YELLOW])),
                tooltip=["platform:N", "month:N", alt.Tooltip("activity:Q", format=",d"),
                         alt.Tooltip("index:Q", format=".1f")],
            ).properties(height=310))
            st.altair_chart(chart, use_container_width=True)

