"""LinkedIn public-Page aggregate analytics; owner-prepared release only in Cloud."""
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_components import render_overview_total, render_analytics_header
from rwit_theme import CHART_GREEN as GREEN, CHART_PURPLE as PURPLE

from scripts.linkedin_release import read_release
from scripts.linkedin_reporting import validate_snapshot
from scripts.community_members import get_membership
from rwit_data_mode import is_demo, demo_path

ROOT = Path(__file__).resolve().parent


def _report():
    if is_demo():
        return validate_snapshot(json.loads(demo_path("linkedin", "report.json").read_text(encoding="utf-8")))
    if os.environ.get("RWIT_LINKEDIN_LOCAL_PREVIEW") == "1":
        path = ROOT / "private" / "linkedin" / "report.json"
        return validate_snapshot(json.loads(path.read_text(encoding="utf-8")))
    try:
        config = st.secrets.get("linkedin", {})
    except FileNotFoundError:
        config = {}
    return read_release(config.get("release_b64"))


def _bars(items, heading):
    st.subheader(heading)
    if not items:
        st.info("No records available")
        return
    data = pd.DataFrame(items[:8])
    chart = alt.Chart(data).mark_bar(color=PURPLE, cornerRadiusEnd=4).encode(
        x=alt.X("count:Q", title="LinkedIn-reported count", axis=alt.Axis(tickMinStep=1)),
        y=alt.Y("name:N", sort="-x", title=None, axis=alt.Axis(labelLimit=270)),
        tooltip=["name:N", "count:Q"]
    ).properties(height=max(180, len(data) * 36))
    st.altair_chart(chart, use_container_width=True)


def show_linkedin_dashboard():
    try:
        report = _report()
        membership = get_membership("linkedin")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        st.error("LinkedIn Analytics is unavailable: the approved report is missing or invalid.")
        return

    render_analytics_header(
        "LinkedIn Analytics",
        report["content_period"][0],
        report["content_period"][1],
        report.get("generated_at_utc"),
        fallback_date=report["content_period"][1],
    )
    totals = report["totals"]
    with st.container(key="linkedin_community_overview"):
        st.subheader("Community Overview")
        total_col, details_col = st.columns([1, 2], gap="medium")
        with total_col:
            with st.container(border=True):
                render_overview_total("Total followers", membership["member_count"])
        with details_col:
            with st.container(border=True):
                a, b = st.columns(2)
                a.metric("Posts published", f"{totals['posts']:,}")
                b.metric("Impressions", f"{totals['impressions']:,}")
                c, d, e = st.columns(3)
                c.metric("Reactions", f"{totals['reactions']:,}")
                d.metric("Comments", f"{totals['comments']:,}")
                e.metric("Reposts", f"{totals['reposts']:,}")
    st.caption("Followers are a snapshot from the PDF, not a time-period sum. Content interactions are period totals.")

    st.divider()
    st.header("Content Performance")
    monthly = pd.DataFrame(report["monthly_content"])
    metrics = st.multiselect("Show engagement measures", ["impressions", "reactions", "comments", "reposts", "clicks"],
                             default=["reactions", "comments", "reposts"])
    if metrics:
        melted = monthly.melt("month", value_vars=metrics, var_name="metric", value_name="count")
        st.altair_chart(alt.Chart(melted).mark_line(point=True).encode(
            x=alt.X("month:N", title="Month"), y=alt.Y("count:Q", title="Count"),
            color="metric:N", tooltip=["month:N", "metric:N", "count:Q"]
        ).properties(height=320), use_container_width=True)
    st.caption("Metrics are daily activity summed by month. Impressions, likes and clicks are different measures, not unique people.")

    st.subheader("Top Posts by Visible Engagement")
    top = pd.DataFrame(report["top_posts"])
    if not top.empty:
        top["engagement"] = top["reactions"] + top["comments"] + top["reposts"]
        top["title"] = top["title"].str.slice(0, 95)
        st.dataframe(top[["date", "title", "impressions", "reactions", "comments", "reposts", "clicks", "url"]],
                     hide_index=True, use_container_width=True,
                     column_config={"url": st.column_config.LinkColumn("Post link", display_text="Open post")})
    st.caption("Ranked by likes + comments + reposts, not by inferred audience interest. Post metrics may use a different observation window from daily totals.")

    st.divider()
    st.header("Audience Profile")
    choice = st.selectbox("Audience dimension", ["Location", "Industry", "Job function", "Seniority", "Company size"])
    _bars(report["demographics"]["followers"][choice], "Follower Profile")
    st.caption("LinkedIn demographic categories may be incomplete or overlap. Do not treat their sums as total unique followers.")

    st.divider()
    st.header("Page Discovery")
    a, b = st.columns(2)
    a.metric("Page views", f"{totals['page_views']:,}")
    b.metric("Sum of daily unique visitors", f"{totals['daily_unique_visitors_sum']:,}")
    st.caption("Sum of daily unique visitors is not the distinct number of people across the whole reporting period.")
    visit = pd.DataFrame(report["monthly_visitors"])
    st.altair_chart(alt.Chart(visit).mark_bar(color=GREEN).encode(
        x="month:N", y=alt.Y("page_views:Q", title="Page views"), tooltip=["month:N", "page_views:Q"]
    ).properties(height=280), use_container_width=True)

    st.divider()
    st.header("Audience Interests")
    analysis = report.get("topic_analysis")
    if not analysis:
        st.info("Re-import the LinkedIn exports to generate topic analysis.")
    else:
        st.caption("Broad topics assigned from post text using transparent keyword rules (not AI). "
                   "These reflect engagement with published content, not individual followers' interests.")
        a, b, c = st.columns(3)
        a.metric("Posts analyzed", analysis["post_count"])
        b.metric("Readable post texts", analysis["readable_posts"])
        c.metric("Unreadable post texts", analysis["unreadable_posts"])
        categories = pd.DataFrame(analysis["topics"])
        if not categories.empty:
            usable = categories[~categories["topic"].str.startswith("Unclassified")].copy()
            metric = st.selectbox("Compare topics by", [
                "interactions_per_post", "interactions", "comments", "impressions", "posts"],
                format_func=lambda x: {
                    "interactions_per_post": "Interactions per post",
                    "interactions": "Total reactions + comments + reposts",
                    "comments": "Comments", "impressions": "Impressions",
                    "posts": "Posts published"}[x], key="linkedin_topic_metric")
            if not usable.empty:
                chart = alt.Chart(usable).mark_bar(color=PURPLE, cornerRadiusEnd=4).encode(
                    x=alt.X(f"{metric}:Q", title=None),
                    y=alt.Y("topic:N", title=None, sort="-x", axis=alt.Axis(labelLimit=300)),
                    tooltip=["topic:N", "posts:Q", "impressions:Q", "reactions:Q",
                             "comments:Q", "reposts:Q", "interactions_per_post:Q"]
                ).properties(height=max(220, len(usable) * 45))
                st.altair_chart(chart, use_container_width=True)
            st.dataframe(categories[["topic", "posts", "impressions", "reactions", "comments",
                                     "reposts", "interactions_per_post", "interaction_rate"]],
                         hide_index=True, use_container_width=True)
        if analysis["unreadable_posts"]:
            st.warning(f"{analysis['unreadable_posts']} post(s) had unreadable export text and "
                       "were not assigned an inferred topic. Their engagement is shown separately.")
        st.caption("Topic grouping is heuristic, and ambiguous posts may be misclassified. "
                   "Interaction rate here is (reactions + comments + reposts) / impressions; "
                   "it is not LinkedIn's full engagement-rate metric.")
    st.caption("Source: owner-provided LinkedIn Page exports and Page PDF. Public posts only; individual follower records are not imported.")
