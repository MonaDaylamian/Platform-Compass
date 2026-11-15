
"""Platform Compass: read-only WhatsApp analytics dashboard.

Local mode reads a Git-ignored aggregate JSON from private/.
Private Cloud mode reads only an owner-approved release from Secrets.
Membership totals come from the validated community_members.csv file.
"""

from __future__ import annotations

from pathlib import Path
import sys


import altair as alt
import pandas as pd
import streamlit as st

from dashboard_components import render_overview_total, render_analytics_header
from rwit_theme import (
    CHART_GREEN as RWIT_GREEN,
    CHART_PURPLE as RWIT_PURPLE,
    CHART_YELLOW as RWIT_YELLOW,
    apply_dashboard_theme,
)
from scripts.community_members import get_membership
from rwit_data_mode import is_demo, demo_path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))
from board_reporting import load_board_report  # noqa: E402

LOCAL_BOARD_REPORT = ROOT / "private" / "board_report.json"


def _cloud_settings():
    """No Secrets is normal in local preview mode."""
    try:
        return st.secrets["board"]
    except (KeyError, FileNotFoundError):
        return None


def _is_cloud_mode() -> bool:
    cfg = _cloud_settings()
    if cfg is None:
        return False
    if cfg.get("mode") != "private_cloud":
        raise ValueError("Unrecognized board deployment mode.")
    return True


def read_prepared_report() -> dict:
    if is_demo():
        return load_board_report(demo_path("whatsapp", "board_report.json"))
    cfg = _cloud_settings()
    if cfg is not None:
        if cfg.get("mode") != "private_cloud":
            raise ValueError("Unrecognized board deployment mode.")
        from board_cloud_release import load_cloud_release
        return load_cloud_release(cfg.get("release_b64"))
    return load_board_report(LOCAL_BOARD_REPORT)


def _load_or_warn() -> dict | None:
    try:
        return read_prepared_report()
    except (OSError, ValueError, TypeError, ImportError, KeyError):
        st.error(
            "No valid board report is available. Regenerate the private aggregate "
            "using scripts/build_board_report.py. If hosted, refresh approved Secrets."
        )
        return None


def _pretty(name: str) -> str:
    return name.replace("_", " ").capitalize()


def _wrap_label(text: str, width: int = 18) -> str:
    """Wrap long category labels for readability."""
    words = str(text).split()
    if not words:
        return str(text)

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word

    lines.append(current)
    return "\n".join(lines)


def _header(report: dict) -> None:
    render_analytics_header(
        "WhatsApp Analytics",
        report["period"]["start"],
        report["period"]["end"],
        report["generated_at_utc"],
    )


def _category_chart(report: dict, field: str, *, unit: str) -> None:
    entries = report[field][:5]
    if not entries:
        st.info(
            "No categories meet the disclosure threshold, or no successful "
            "AI classifications are available. Missing bars do not imply zero activity."
        )
        return

    data = pd.DataFrame([
        {
            "Category": _wrap_label(_pretty(item["name"]), width=26),
            unit: item["count"],
        }
        for item in entries
    ])
    bar_color = RWIT_GREEN if field == "needs_by_topic" else RWIT_PURPLE
    maximum = int(data[unit].max())

    common_x = alt.X(
        f"{unit}:Q",
        title=unit,
        axis=alt.Axis(
            tickMinStep=1,
            format="d",
            grid=True,
            gridColor="#E7E8EC",
        ),
        scale=alt.Scale(
            domain=[0, maximum + max(2, round(maximum * 0.16))]
        ),
    )

    common_y = alt.Y(
        "Category:N",
        sort="-x",
        title="",
        axis=alt.Axis(
            labelLimit=280,
            labelLineHeight=18,
            labelFontSize=12,
        ),
    )

    bars = (
        alt.Chart(data)
        .mark_bar(color=bar_color, cornerRadiusEnd=4)
        .encode(
            x=common_x,
            y=common_y,
            tooltip=[
                alt.Tooltip("Category:N", title="Category"),
                alt.Tooltip(f"{unit}:Q", title=unit, format=",d"),
            ],
        )
    )

    values = (
        alt.Chart(data)
        .mark_text(
            align="left",
            baseline="middle",
            dx=7,
            fontSize=12,
            fontWeight="bold",
            color="#30343B",
        )
        .encode(
            x=common_x,
            y=common_y,
            text=alt.Text(f"{unit}:Q", format="d"),
        )
    )

    chart = alt.layer(bars, values).properties(
        height=max(180, len(data) * 55)
    )
    st.altair_chart(chart, use_container_width=True)

    if len(entries) < 5:
        st.caption(
            f"Only {len(entries)} categories meet the privacy threshold. "
            "Smaller groups are withheld for privacy."
        )


def _processing_diagnostics(report: dict) -> None:
    with st.expander(
        "Processing diagnostics · technical details",
        expanded=False,
    ):
        ai = report["ai"]
        processed = ai["successful_requests"]
        not_analyzed = ai["not_analyzed_conversations"]
        unsuccessful = ai["failed_requests"]

        a, b, c = st.columns(3)
        a.metric("Analyzed successfully", processed)
        b.metric("Not analyzed", not_analyzed)
        c.metric("Unsuccessful attempts", unsuccessful)

        st.caption(
            f"Eligible conversations: {ai['eligible_conversations']} · "
            f"AI conversations attempted: {ai['attempted_conversations']}. "
            "'Not analyzed' means eligible conversations not sent to AI; "
            "'unsuccessful' means an attempted request was rejected or failed."
        )

        d, e, f = st.columns(3)
        d.metric("Recorded input tokens", f"{ai['input_tokens']:,}")
        e.metric("Recorded output tokens", f"{ai['output_tokens']:,}")

        duration = ai["average_duration_seconds"]
        f.metric(
            "Average request duration",
            f"{duration:.2f} s" if duration is not None else "N/A",
        )

        missing = ai["missing_usage_records"]

        if missing:
            st.warning(
                f"{missing} AI request log(s) lack complete token usage. "
                "The displayed token figures are recorded totals, "
                "not complete billed usage."
            )
        else:
            st.caption(
                "Token usage logs are complete for recorded attempts; "
                "API charges are not estimated here."
            )

        st.caption(
            "Technical success is not semantic accuracy. "
            "The AI conversation limit may bias the topic "
            "and engagement distributions."
        )


def show_whatsapp_dashboard() -> None:
    report = _load_or_warn()
    if report is None:
        return

    # Read manually maintained membership data.
    try:
        membership = get_membership("whatsapp")
    except (OSError, ValueError, KeyError) as exc:
        st.error(f"WhatsApp membership data unavailable: {exc}")
        return

    _header(report)

    with st.container(key="community_overview"):
        st.subheader("Community Overview")

        total_col, details_col = st.columns(
            [1, 2],
            gap="medium",
        )

        with total_col:
            with st.container(border=True):
                render_overview_total(
                    "Total members",
                    membership["member_count"],
                )

        with details_col:
            with st.container(border=True):
                messages, conversations = st.columns(2)

                messages.metric(
                    "Total messages",
                    report["overall"]["messages"],
                )
                conversations.metric(
                    "Total conversations",
                    report["overall"]["conversations"],
                )

                st.metric(
                    "Active contributors",
                    report["overall"]["distinct_contributors"],
                    help=(
                        "Distinct people who sent at least one "
                        "imported message across the entire report."
                    ),
                )

        st.caption(
            "Total members is a manually maintained community snapshot. "
            "Messages, conversations and active contributors come from "
            "the imported chat. The reporting-period selector below "
            "applies only to the activity trend."
        )

    st.divider()

    st.subheader("What Members Are Looking For")
    st.caption(
        "Top needs and interests grouped into broad themes. "
        "Each theme counts distinct AI-analyzed conversations, "
        "not messages or members; mere announcements are excluded."
    )

    _category_chart(
        report,
        "needs_by_topic",
        unit="Conversations",
    )

    st.subheader("How Members Participate")
    st.caption(
        "How conversations contribute: seeking information, "
        "sharing opportunities, offering support, exchanging "
        "experiences and more. Each intent counts distinct "
        "AI-analyzed conversations, not messages or members."
    )

    _category_chart(
        report,
        "engagement",
        unit="Conversations",
    )

    st.caption(
        "Both charts show up to five categories supported by at least "
        "three distinct AI-analyzed conversations. Smaller or sensitive "
        "topics may be grouped into broad themes or withheld. "
        "A conversation may appear under multiple themes or intents; "
        "totals are not additive. Unanalyzed conversations are excluded."
    )

    st.divider()

    periods = report["periods"]
    labels = [
        f"{p['start']} – {p['end']}"
        for p in periods
    ]

    if len(labels) == 1:
        selected = periods
        st.caption(
            "One reporting period meets the disclosure threshold."
        )
    else:
        chosen = st.select_slider(
            "Select activity reporting periods (both ends included)",
            options=labels,
            value=(labels[0], labels[-1]),
            key="board_period_range",
        )

        start = labels.index(chosen[0])
        end = labels.index(chosen[1])
        selected = periods[start:end + 1]

    st.caption(
        f"Selected activity periods: {selected[0]['start']} "
        f"through {selected[-1]['end']}. "
        "Needs and participation intents cover the full analyzed export."
    )

    st.subheader("Community Activity Over Time")
    st.caption(
        "Messages and distinct active conversations in each reporting "
        "period. A conversation is active if it contains at least one "
        "message in the period. Privacy-safe periods may have different "
        "lengths, so compare volumes with care."
    )

    frame = pd.DataFrame(selected).copy()

    frame["Period"] = frame.apply(
        lambda r: (
            f"{pd.Timestamp(r['start']):%d %b}–"
            f"{pd.Timestamp(r['end']):%d %b}"
        ),
        axis=1,
    )

    chart_data = frame.melt(
        id_vars=["Period", "start", "end"],
        value_vars=["messages", "active_conversations"],
        var_name="Metric",
        value_name="Count",
    )

    chart_data["Metric"] = chart_data["Metric"].map({
        "messages": "Messages",
        "active_conversations": "Active conversations",
    })

    order = frame["Period"].tolist()

    chart = (
        alt.Chart(chart_data)
        .mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
        )
        .encode(
            x=alt.X(
                "Period:N",
                sort=order,
                title="Reporting period",
                axis=alt.Axis(
                    labelAngle=0,
                    labelLimit=115,
                    labelOverlap=False,
                    labelFontSize=11,
                    labelLineHeight=14,
                ),
            ),
            xOffset=alt.XOffset(
                "Metric:N",
                sort=["Messages", "Active conversations"],
            ),
            y=alt.Y(
                "Count:Q",
                title="Count",
                scale=alt.Scale(zero=True),
                axis=alt.Axis(
                    tickMinStep=1,
                    gridColor="#E7E8EC",
                ),
            ),
            color=alt.Color(
                "Metric:N",
                title="",
                sort=["Messages", "Active conversations"],
                scale=alt.Scale(
                    domain=[
                        "Messages",
                        "Active conversations",
                    ],
                    range=[
                        RWIT_GREEN,
                        RWIT_PURPLE,
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "start:N",
                    title="Period start",
                ),
                alt.Tooltip(
                    "end:N",
                    title="Period end",
                ),
                alt.Tooltip(
                    "Metric:N",
                    title="Metric",
                ),
                alt.Tooltip(
                    "Count:Q",
                    title="Count",
                    format=",d",
                ),
            ],
        )
        .properties(height=315)
    )

    st.altair_chart(
        chart,
        use_container_width=True,
    )

    st.caption(
        "Active-conversation counts are distinct within each period, "
        "not across all periods. The overall conversation total above "
        "counts each conversation once."
    )

    with st.expander("Verify activity totals", expanded=False):
        st.dataframe(
            frame.set_index("Period").rename(columns={
                "messages": "Messages",
                "active_contributors": "Contributor-periods",
                "active_conversations": "Active conversations",
                "conversation_starts": "Conversations started",
                "likely_questions": "Likely questions",
                "links": "Messages with links",
                "media": "Messages with media",
            }),
            width="stretch",
        )

    st.divider()

    _processing_diagnostics(report)
