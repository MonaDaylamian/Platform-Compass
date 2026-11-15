"""Platform Compass board-only Meetup Analytics page (no API calls, no member records)."""

from __future__ import annotations

import os

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_components import render_overview_total, render_analytics_header
from rwit_theme import CHART_GREEN as RWIT_GREEN, CHART_PURPLE as RWIT_PURPLE, CHART_YELLOW as RWIT_YELLOW

from scripts.meetup_reporting import load_meetup_data, summarize_meetup
from scripts.meetup_release import read_release
from scripts.community_members import get_membership
from rwit_data_mode import is_demo, demo_path



def _top_chart(events: list[dict], *, title: str, color: str) -> None:
    st.subheader(title)
    if not events:
        st.info("No completed events available.")
        return
    df = pd.DataFrame(events)
    # Title+date is an unambiguous identifier for recurring events.
    df["event_label"] = df.apply(lambda x: f"{x['title']} · {x['date']:%d %b}", axis=1)
    order = df["event_label"].tolist()
    chart = (
        alt.Chart(df)
        .mark_bar(color=color, cornerRadiusEnd=4)
        .encode(
            x=alt.X("attendees:Q", title="Meetup-displayed attendees", scale=alt.Scale(zero=True),
                    axis=alt.Axis(tickMinStep=1, format="d")),
            y=alt.Y("event_label:N", title=None, sort=order,
                    axis=alt.Axis(labelLimit=360, labelFontSize=12)),
            tooltip=[alt.Tooltip("title:N", title="Event"),
                     alt.Tooltip("date:T", title="Date", format="%d %b %Y"),
                     alt.Tooltip("attendees:Q", title="Attendees", format=",d")],
        )
        .properties(height=max(155, 57 * len(df)))
    )
    labels = (
        alt.Chart(df)
        .mark_text(align="left", baseline="middle", dx=7,
                   fontSize=12, fontWeight="bold", color="#30343B")
        .encode(
            x="attendees:Q",
            y=alt.Y("event_label:N", sort=order),
            text=alt.Text("attendees:Q", format=",d"),
        )
    )
    st.altair_chart(alt.layer(chart, labels), use_container_width=True)


def show_meetup_dashboard() -> None:
    try:
        # Opt in explicitly when previewing locally. Some developer machines
        # have [board] mode = "private_cloud" in .streamlit/secrets.toml;
        # that configuration should not prevent local testing of imported PDFs.
        # Do NOT configure this flag in the deployed Streamlit environment.
        local_preview = os.environ.get("RWIT_MEETUP_LOCAL_PREVIEW") == "1"

        if is_demo():
            events, group = load_meetup_data(demo_path("meetup"))
        elif local_preview:
            # Read the owner-generated files under private/meetup/.
            events, group = load_meetup_data()
        else:
            # In the absence of an explicit local-preview opt-in, read only
            # the owner-approved Cloud release; never silently fall back.
            try:
                meetup_cfg = st.secrets.get("meetup", {})
            except FileNotFoundError:
                meetup_cfg = {}
            events, group = read_release(meetup_cfg.get("release_b64"))
        summary = summarize_meetup(events)
        membership = get_membership("meetup")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        st.error("The reviewed Meetup snapshot could not be loaded or validated.")
        return

    render_analytics_header(
        "Meetup Analytics",
        group["report_start"],
        group["report_end"],
        group.get("report_generated_at_utc"),
        fallback_date=group["snapshot_date"],
    )

    st.divider()
    with st.container(key="meetup_community_overview"):
        st.subheader("Community Overview")
        total_col, details_col = st.columns([1, 2], gap="medium")
        with total_col:
            with st.container(border=True):
                render_overview_total("Total members", membership["member_count"])
                
        with details_col:
            with st.container(border=True):
                st.metric("Community rating", f"{group['rating']:.1f}")
                st.caption(f"Based on {group['ratings_count']:,} ratings")

    st.subheader("Event Overview")
    overview = pd.DataFrame(summary["overview"])
    colors = alt.Scale(domain=["All", "Format", "Status"],
                       range=[RWIT_PURPLE, RWIT_GREEN, RWIT_YELLOW])
    chart = (
        alt.Chart(overview)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("category:N", sort=overview["category"].tolist(),
                    title=None, axis=alt.Axis(labelAngle=0, labelLimit=110)),
            y=alt.Y("count:Q", title="Number of events",
                    axis=alt.Axis(tickMinStep=1, format="d")),
            color=alt.Color("group:N", title="Category", scale=colors),
            tooltip=[alt.Tooltip("category:N", title="Category"),
                     alt.Tooltip("count:Q", title="Events", format="d")],
        )
        .properties(height=290)
    )
    value_labels = (
        alt.Chart(overview)
        .mark_text(dy=-9, color="#30343B", fontSize=12, fontWeight="bold")
        .encode(
            x=alt.X("category:N", sort=overview["category"].tolist()),
            y="count:Q",
            text=alt.Text("count:Q", format="d"),
        )
    )
    st.altair_chart(alt.layer(chart, value_labels), use_container_width=True)
    st.caption("The format and status bars describe the same events; do not add all six bars together. "
               "Cancelled and upcoming events are included in the overall event totals.")

    st.divider()
    st.header("Top Events by Attendance")
    _top_chart(summary["top_online"], title="Online events — top 3 available", color=RWIT_PURPLE)
    _top_chart(summary["top_physical"], title="Physical events — top 5 completed events", color=RWIT_GREEN)
    st.caption("Rankings include completed events only. 'Attendees' is the figure displayed "
               "by Meetup in the source snapshot, not independently verified attendance.")

    st.divider()
    st.header("All Events")
    form_col, status_col = st.columns(2)
    with form_col:
        selected_format = st.selectbox("Event format", ["All", "Online", "Physical"], key="meetup_format")
    with status_col:
        selected_status = st.selectbox("Event status", ["All", "Completed", "Cancelled", "Upcoming"],
                                      key="meetup_status")
    filtered = [e for e in events
                if (selected_format == "All" or e["format"] == selected_format)
                and (selected_status == "All" or e["status"] == selected_status)]
    frame = pd.DataFrame(filtered, columns=["date", "title", "format", "location", "attendees", "status"])
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date", ascending=False)
    st.caption(f"Showing {len(frame)} of {len(events)} events")
    st.dataframe(frame, hide_index=True, width="stretch",
                 column_config={
                     "date": st.column_config.DateColumn("Date", format="DD MMM YYYY"),
                     "title": "Event title", "format": "Format", "location": "Location",
                     "attendees": st.column_config.NumberColumn("Attendees", format="%d"),
                     "status": "Status",
                 })
    st.caption("Source: Meetup PDF snapshot (locally generated, owner reviewed). No individual attendee details are included.")
