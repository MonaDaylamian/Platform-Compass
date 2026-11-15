"""Privacy-bounded, local-only aggregation for the Sample Tech Community board review.

An aggregate is NOT automatically anonymous. Release policy is deliberately
conservative; each published needs/intent category and response status must
meet the contributor AND conversation minimum. No raw messages, member IDs,
source texts, or errors enter the JSON. Review each release before hosting.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

import pandas as pd

SCHEMA_VERSION = 3
MIN_CONTRIBUTORS = 5
MIN_INSIGHT_CONVERSATIONS = 3  # Board insight categories: distinct conversations only
# Stable, broad, non-overlapping themes reduce the disclosure of rare specific needs.
# A theme is released only when at least three separate conversations support it.
NEED_THEMES = {
    "career_and_job_opportunities": {
        "career_development", "job_search", "career_transition", "cv_and_interview",
        "workplace", "flexible_work",
    },
    "learning_and_technology": {
        "technical_learning", "artificial_intelligence", "software_engineering",
        "data_and_analytics", "cybersecurity",
    },
    "mentorship_and_networking": {"mentoring", "networking"},
    "community_and_events": {"events", "community_operations"},
    "language_and_inclusion": {"language_barrier"},
    "entrepreneurship": {"entrepreneurship"},
}

MAX_BOARD_JSON_BYTES = 256 * 1024
REPORT_KEYS = {
    "schema_version", "dataset_kind", "review_status", "generated_at_utc",
    "period", "privacy", "overall", "periods", "ai", "topics", "signal_types",
    "needs_by_topic", "engagement", "response_status",
}
PERIOD_KEYS = {
    "start", "end", "messages", "active_contributors", "conversation_starts",
    "active_conversations", "likely_questions", "links", "media",
}
ALLOWED_TOPICS = {
    "career_development", "job_search", "career_transition", "cv_and_interview",
    "technical_learning", "artificial_intelligence", "software_engineering",
    "data_and_analytics", "cybersecurity", "mentoring", "networking", "events",
    "workplace", "language_barrier", "flexible_work", "entrepreneurship",
    "community_operations", "other",
}
ALLOWED_SIGNAL_TYPES = {
    "question", "request_for_help", "concern", "advice", "offer_to_help",
    "job_opportunity", "event_opportunity", "learning_interest",
    "networking_request", "community_feedback", "success_story",
    "general_information",
}
ALLOWED_INTENTS = {
    "seek_information", "seek_advice", "seek_connection", "seek_opportunity",
    "share_opportunity", "offer_support", "share_experience", "express_concern",
    "give_feedback", "promote_event", "other",
}
SEEKING_INTENTS = {"seek_information", "seek_advice", "seek_connection", "seek_opportunity"}
THREE_STATUSES = ("fully_answered", "partially_answered", "unanswered")
ANSWER_STATUSES = set(THREE_STATUSES) | {"acknowledged", "unclear", "not_applicable"}


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    if not required.issubset(frame.columns):
        raise ValueError(f"{name} is missing required report columns: {sorted(required - set(frame.columns))}.")


def _int_number(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"Invalid aggregate: {label}")
    return value


def _iso_date(value: str) -> date:
    if not isinstance(value, str):
        raise ValueError("Invalid reporting period date.")
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("Invalid reporting period format.")
    return parsed


def _released_categories(
    signals: pd.DataFrame, messages: pd.DataFrame, field: str,
) -> list[dict[str, Any]]:
    """Legacy broad distribution kept only for compatibility with old tests.

    The dashboard uses the stricter, author-attributed needs and engagement
    distributions below instead of this conversation-participant proxy.
    """
    if signals.empty or field not in signals or "Conversation_ID" not in signals:
        return []
    allowed = ALLOWED_TOPICS if field == "Primary_Topic" else ALLOWED_SIGNAL_TYPES
    by_conv = messages.groupby("Conversation_ID")["Member_ID"].agg(lambda x: set(x))
    released: list[dict[str, Any]] = []
    for label, group in signals.groupby(field, dropna=True):
        if not isinstance(label, str) or label not in allowed:
            continue
        ids = set(group["Conversation_ID"].dropna())
        members: set = set()
        for conv in ids:
            if conv in by_conv:
                members.update(by_conv.loc[conv])
        if len(ids) >= MIN_CONTRIBUTORS and len(members) >= MIN_CONTRIBUTORS:
            released.append({"name": label, "count": int(len(group))})
    return sorted(released, key=lambda item: (-item["count"], item["name"]))


def _join_signal_authors(
    signals: pd.DataFrame, messages: pd.DataFrame, ai_log: pd.DataFrame,
) -> pd.DataFrame:
    """Match AI signals to their source-message authors and successful runs.

    No author/conversation identifiers from this temporary join are exported.
    Unlogged or unsuccessful AI signal rows are excluded from board insights.
    """
    required_signals = {"Message_ID", "Conversation_ID", "Primary_Topic", "Intent", "Answer_Status"}
    if signals.empty or not required_signals.issubset(signals.columns):
        return pd.DataFrame()
    if ai_log.empty or not {"Conversation_ID", "Status"}.issubset(ai_log.columns):
        return pd.DataFrame()
    if not {"Message_ID", "Member_ID", "Conversation_ID"}.issubset(messages.columns):
        return pd.DataFrame()

    successful_ids = set(
        ai_log.loc[ai_log["Status"].astype(str).str.casefold().eq("success"), "Conversation_ID"]
        .dropna().astype(str)
    )
    if not successful_ids:
        return pd.DataFrame()

    source = messages[["Message_ID", "Conversation_ID", "Member_ID"]].dropna().copy()
    source = source.drop_duplicates(subset="Message_ID", keep=False)
    source["Message_ID"] = source["Message_ID"].astype(str)
    source["Conversation_ID"] = source["Conversation_ID"].astype(str)
    candidates = signals.copy()
    candidates["Message_ID"] = candidates["Message_ID"].astype(str)
    candidates["Conversation_ID"] = candidates["Conversation_ID"].astype(str)
    candidates = candidates[candidates["Conversation_ID"].isin(successful_ids)]
    joined = candidates.merge(
        source.rename(columns={"Conversation_ID": "_Source_Conversation"}),
        on="Message_ID", how="inner", validate="many_to_one",
    )
    return joined.loc[joined["Conversation_ID"] == joined["_Source_Conversation"]].copy()


def _request_like(rows: pd.DataFrame) -> pd.Series:
    """Identify needs/questions; announcements and offers alone aren't needs."""
    strength = rows["Need_Strength"] if "Need_Strength" in rows else pd.Series("none", index=rows.index)
    intent = rows["Intent"] if "Intent" in rows else pd.Series("other", index=rows.index)
    # Both explicit and implicit expressed needs are relevant in a seasonal review.
    return strength.isin(("explicit", "implicit")) | intent.isin(SEEKING_INTENTS)


def _released_authored_categories(
    joined: pd.DataFrame, field: str, allowed: set[str], *,
    needs_only: bool, conversation_only: bool = False,
) -> list[dict[str, Any]]:
    if joined.empty or field not in joined.columns:
        return []
    data = joined.loc[_request_like(joined)] if needs_only else joined
    if data.empty:
        return []
    # Multiple generated signals with the same topic/intent and source message
    # count as one classified message, not repeated needs.
    data = data.drop_duplicates(subset=["Conversation_ID", "Message_ID", field])
    released = []
    for label, group in data.groupby(field, dropna=True):
        if label not in allowed or label == "other":
            continue
        if conversation_only:
            eligible = group["Conversation_ID"].nunique() >= MIN_INSIGHT_CONVERSATIONS
        else:
            # Preserve the more conservative legacy distributions.
            eligible = (
                group["Conversation_ID"].nunique() >= MIN_CONTRIBUTORS
                and group["Member_ID"].nunique() >= MIN_CONTRIBUTORS
            )
        if eligible:
            released.append({"name": label, "count": int(len(group))})
    return sorted(released, key=lambda item: (-item["count"], item["name"]))


def _released_need_themes(joined: pd.DataFrame) -> list[dict[str, Any]]:
    """Return at most five broad needs ranked by DISTINCT conversations.

    Every conversation contributes at most once to any given theme, even if
    several messages or narrow topics match it. Low-support themes are
    withheld, not exposed via a residual 'Other' total. Category labels are
    fixed in code, never taken from raw member text.
    """
    if joined.empty or "Primary_Topic" not in joined or "Conversation_ID" not in joined:
        return []
    needs = joined.loc[_request_like(joined)].copy()
    if needs.empty:
        return []
    themes = []
    for theme, topics in NEED_THEMES.items():
        ids = needs.loc[needs["Primary_Topic"].isin(topics), "Conversation_ID"].dropna().unique()
        if len(ids) >= MIN_INSIGHT_CONVERSATIONS:
            themes.append({"name": theme, "count": int(len(ids))})
    return sorted(themes, key=lambda item: (-item["count"], item["name"]))[:5]


def _released_conversation_intents(joined: pd.DataFrame) -> list[dict[str, Any]]:
    """Count distinct conversations per participation intent, not messages."""
    if joined.empty or "Intent" not in joined or "Conversation_ID" not in joined:
        return []
    released = []
    for intent, group in joined.groupby("Intent", dropna=True):
        if intent not in ALLOWED_INTENTS or intent == "other":
            continue
        count = int(group["Conversation_ID"].nunique())
        if count >= MIN_INSIGHT_CONVERSATIONS:
            released.append({"name": intent, "count": count})
    return sorted(released, key=lambda item: (-item["count"], item["name"]))[:5]


def _response_status(joined: pd.DataFrame) -> dict[str, Any]:
    """AI-estimated status of answer-seeking source messages (not true resolution).

    A source message is counted at most once. Conflicting classifications are
    recorded as unclear. Suppress the *entire* percentage breakdown when any
    nonzero category would expose fewer than 5 authors or conversations.
    """
    empty = {
        "available": False,
        "counts": None,
        "percentages": None,
        "denominator": None,
        "excluded_or_unclear": None,
    }
    if joined.empty or "Answer_Status" not in joined:
        return empty
    seek = joined.loc[_request_like(joined)].copy()
    if seek.empty:
        return empty
    # A source message with multiple signal rows must not inflate the answer
    # denominator. Ambiguous classifications are excluded as unclear.
    request_rows = []
    for (_, message_id), group in seek.groupby(["Conversation_ID", "Message_ID"]):
        valid = set(group["Answer_Status"].dropna().astype(str)) & ANSWER_STATUSES
        if len(valid) != 1:
            status = "unclear"
        else:
            status = next(iter(valid))
        request_rows.append({
            "status": status,
            "member": group["Member_ID"].iloc[0],
            "conversation": group["Conversation_ID"].iloc[0],
        })
    data = pd.DataFrame(request_rows)
    classified = data[data["status"].isin(THREE_STATUSES)]
    counts = {status: int(classified["status"].eq(status).sum()) for status in THREE_STATUSES}
    denom = sum(counts.values())
    if denom == 0:
        return empty
    for status in THREE_STATUSES:
        subset = classified[classified["status"] == status]
        if len(subset) and (
            subset["member"].nunique() < MIN_CONTRIBUTORS
            or subset["conversation"].nunique() < MIN_CONTRIBUTORS
        ):
            return empty
    excluded = int(len(data) - denom)
    # Don't disclose a small excluded/unclear subgroup through subtraction.
    # Suppress the entire visual if it would be possible to infer that subgroup.
    if 0 < excluded < MIN_CONTRIBUTORS:
        return empty

    pct = {k: round(v * 100 / denom, 1) for k, v in counts.items()}
    return {
        "available": True,
        "counts": counts,
        "percentages": pct,
        "denominator": denom,
        "excluded_or_unclear": excluded,
    }


def make_board_report(
    messages: pd.DataFrame,
    conversations: pd.DataFrame,
    signals: pd.DataFrame,
    ai_log: pd.DataFrame,
) -> dict[str, Any]:
    """Aggregate prepared pipeline tables without exposing individual records."""
    _require_columns(messages, {
        "Date", "Member_ID", "Conversation_ID", "Is_Question_Likely", "Has_Link", "Has_Media",
    }, "Messages")
    _require_columns(conversations, {"Conversation_ID", "Conversation_Start", "Included_Message_Count"}, "Conversations")
    if messages.empty:
        raise ValueError("No messages are available for board reporting.")

    m = messages.copy()
    m["Date"] = pd.to_datetime(m["Date"], errors="coerce")
    if m["Date"].isna().any() or m["Member_ID"].isna().any() or m["Conversation_ID"].isna().any():
        raise ValueError("Invalid dates or identifiers. Review the source locally.")
    m["_week"] = m["Date"].dt.normalize() - pd.to_timedelta(m["Date"].dt.weekday, unit="D")
    contributors = int(m["Member_ID"].nunique())
    if contributors < MIN_CONTRIBUTORS:
        raise ValueError("Insufficient participation to create a board report.")
    starts = pd.to_datetime(conversations["Conversation_Start"], errors="coerce")
    if starts.isna().any():
        raise ValueError("Invalid conversation timestamps. Review the source locally.")
    starts = starts.dt.normalize()

    released_groups = []
    pending = []
    for _, group in m.groupby("_week", sort=True):
        pending.append(group)
        if pd.concat(pending)["Member_ID"].nunique() >= MIN_CONTRIBUTORS:
            released_groups.append(pd.concat(pending))
            pending = []
    if pending:
        if not released_groups:
            raise ValueError("Insufficient participation for a released period.")
        released_groups[-1] = pd.concat([released_groups[-1], *pending])

    periods = []
    for group in released_groups:
        start = group["_week"].min().date()
        end = (group["_week"].max() + timedelta(days=6)).date()
        periods.append({
            "start": start.isoformat(), "end": end.isoformat(),
            "messages": int(len(group)),
            "active_contributors": int(group["Member_ID"].nunique()),
            "conversation_starts": int(starts.between(pd.Timestamp(start), pd.Timestamp(end)).sum()),
            # A conversation is active when it has at least one source message
            # in this privacy-safe (potentially merged) reporting period.
            "active_conversations": int(group["Conversation_ID"].nunique()),
            "likely_questions": int(group["Is_Question_Likely"].fillna(False).eq(True).sum()),
            "links": int(group["Has_Link"].fillna(False).eq(True).sum()),
            "media": int(group["Has_Media"].fillna(False).eq(True).sum()),
        })

    eligible = int(pd.to_numeric(conversations["Included_Message_Count"], errors="coerce").fillna(0).gt(0).sum())
    if ai_log.empty:
        attempts = success = failed = input_tokens = output_tokens = missing_usage = 0
        avg_duration = None
    else:
        _require_columns(ai_log, {
            "Conversation_ID", "Status", "Input_Tokens", "Output_Tokens", "Duration_Seconds",
        }, "AIProcessingLog")
        attempts = int(ai_log["Conversation_ID"].dropna().nunique())
        statuses = ai_log["Status"].fillna("").astype(str).str.casefold()
        success = int(statuses.eq("success").sum())
        failed = int(statuses.eq("failed").sum())
        in_values = pd.to_numeric(ai_log["Input_Tokens"], errors="coerce")
        out_values = pd.to_numeric(ai_log["Output_Tokens"], errors="coerce")
        missing_usage = int((in_values.isna() | out_values.isna()).sum())
        input_tokens = int(in_values.sum())
        output_tokens = int(out_values.sum())
        durations = pd.to_numeric(ai_log["Duration_Seconds"], errors="coerce").dropna()
        avg_duration = round(float(durations.mean()), 2) if not durations.empty else None

    joined = _join_signal_authors(signals, m, ai_log)
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset_kind": "rwit_board_aggregate",
        "review_status": "local_review_required",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "period": {"start": m["Date"].min().date().isoformat(), "end": m["Date"].max().date().isoformat()},
        "privacy": {
            "min_contributors_per_period": MIN_CONTRIBUTORS,
            "granularity": "calendar_weeks_merged",
        },
        "overall": {
            "messages": int(len(m)),
            "distinct_contributors": contributors,
            "conversations": int(len(conversations)),
            "likely_questions": int(m["Is_Question_Likely"].fillna(False).eq(True).sum()),
        },
        "periods": periods,
        "ai": {
            "eligible_conversations": eligible,
            "attempted_conversations": attempts,
            "successful_requests": success,
            "failed_requests": failed,
            "not_analyzed_conversations": max(0, eligible - attempts),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "token_usage_complete": missing_usage == 0,
            "missing_usage_records": missing_usage,
            "average_duration_seconds": avg_duration,
        },
        # Keep legacy fields for compatibility; the new board UI does not use them.
        # When source Message_IDs are present, even legacy distributions use
        # the strict source-author join; no participant-based inference.
        "topics": (
            _released_authored_categories(joined, "Primary_Topic", ALLOWED_TOPICS, needs_only=False)
            if "Message_ID" in m.columns
            else _released_categories(signals, m, "Primary_Topic")
        ),
        "signal_types": (
            _released_authored_categories(joined, "Signal_Type", ALLOWED_SIGNAL_TYPES, needs_only=False)
            if "Message_ID" in m.columns
            else _released_categories(signals, m, "Signal_Type")
        ),
        "needs_by_topic": _released_need_themes(joined),
        "engagement": _released_conversation_intents(joined),
        "response_status": _response_status(joined),
    }
    validate_board_report(result)
    return result


def validate_board_report(report: Any) -> dict[str, Any]:
    """Strict schema validation protects the board data boundary."""
    if not isinstance(report, dict) or set(report) != REPORT_KEYS:
        raise ValueError("Unexpected board report schema.")
    if type(report["schema_version"]) is not int or report["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Unsupported board report version.")
    if report["dataset_kind"] != "rwit_board_aggregate" or report["review_status"] != "local_review_required":
        raise ValueError("Unexpected board report provenance.")
    timestamp = report["generated_at_utc"]
    if not isinstance(timestamp, str) or datetime.fromisoformat(timestamp).tzinfo is None:
        raise ValueError("Invalid generation timestamp.")
    coverage = report["period"]
    if not isinstance(coverage, dict) or set(coverage) != {"start", "end"}:
        raise ValueError("Invalid report coverage.")
    if _iso_date(coverage["start"]) > _iso_date(coverage["end"]):
        raise ValueError("Invalid coverage dates.")
    privacy = report["privacy"]
    if (not isinstance(privacy, dict) or set(privacy) != {"min_contributors_per_period", "granularity"}
            or privacy["min_contributors_per_period"] != MIN_CONTRIBUTORS
            or privacy["granularity"] != "calendar_weeks_merged"):
        raise ValueError("Unexpected aggregation policy.")
    overview = report["overall"]
    if not isinstance(overview, dict) or set(overview) != {
        "messages", "distinct_contributors", "conversations", "likely_questions",
    }:
        raise ValueError("Unexpected overview fields.")
    for key, value in overview.items():
        _int_number(value, key)
    if overview["distinct_contributors"] < MIN_CONTRIBUTORS:
        raise ValueError("Small aggregate must not be released.")

    periods = report["periods"]
    if not isinstance(periods, list) or not periods or len(periods) > 500:
        raise ValueError("Unexpected reporting period count.")
    previous_end = None
    for part in periods:
        if not isinstance(part, dict) or set(part) != PERIOD_KEYS:
            raise ValueError("Unexpected period fields.")
        p_start, p_end = _iso_date(part["start"]), _iso_date(part["end"])
        if p_start > p_end or (previous_end is not None and p_start <= previous_end):
            raise ValueError("Reporting periods overlap or are out of order.")
        previous_end = p_end
        for field in PERIOD_KEYS - {"start", "end"}:
            _int_number(part[field], field)
        if part["active_contributors"] < MIN_CONTRIBUTORS:
            raise ValueError("Period contributor threshold is not met.")
    if sum(p["messages"] for p in periods) != overview["messages"]:
        raise ValueError("Aggregate message totals do not reconcile.")
    if sum(p["likely_questions"] for p in periods) != overview["likely_questions"]:
        raise ValueError("Aggregate question totals do not reconcile.")

    ai = report["ai"]
    ai_fields = {
        "eligible_conversations", "attempted_conversations", "successful_requests",
        "failed_requests", "not_analyzed_conversations", "input_tokens", "output_tokens",
        "token_usage_complete", "missing_usage_records", "average_duration_seconds",
    }
    if not isinstance(ai, dict) or set(ai) != ai_fields:
        raise ValueError("Unexpected AI summary schema.")
    for key in ai_fields - {"token_usage_complete", "average_duration_seconds"}:
        _int_number(ai[key], key)
    if type(ai["token_usage_complete"]) is not bool:
        raise ValueError("Invalid token usage status.")
    if ai["token_usage_complete"] != (ai["missing_usage_records"] == 0):
        raise ValueError("Inconsistent token usage summary.")
    if ai["not_analyzed_conversations"] != max(0, ai["eligible_conversations"] - ai["attempted_conversations"]):
        raise ValueError("Inconsistent analyzed conversation count.")
    if ai["attempted_conversations"] > ai["eligible_conversations"]:
        raise ValueError("AI attempts exceed eligible conversations.")
    if ai["successful_requests"] + ai["failed_requests"] > ai["attempted_conversations"]:
        raise ValueError("AI status totals exceed attempted conversations.")
    if (ai["average_duration_seconds"] is not None and
            (not isinstance(ai["average_duration_seconds"], (int, float))
             or ai["average_duration_seconds"] < 0)):
        raise ValueError("Invalid average AI duration.")

    distributions = (
        ("topics", ALLOWED_TOPICS), ("signal_types", ALLOWED_SIGNAL_TYPES),
        ("needs_by_topic", set(NEED_THEMES)), ("engagement", ALLOWED_INTENTS),
    )
    for field, labels in distributions:
        entries = report[field]
        if not isinstance(entries, list) or len(entries) > (5 if field in {"needs_by_topic", "engagement"} else len(labels)):
            raise ValueError("Invalid category distribution.")
        seen = set()
        for item in entries:
            if not isinstance(item, dict) or set(item) != {"name", "count"}:
                raise ValueError("Unexpected category fields.")
            if item["name"] not in labels or item["name"] in seen:
                raise ValueError("Unexpected or duplicate category.")
            seen.add(item["name"])
            minimum = (
                MIN_INSIGHT_CONVERSATIONS
                if field in {"needs_by_topic", "engagement"}
                else MIN_CONTRIBUTORS
            )
            if _int_number(item["count"], "category count") < minimum:
                raise ValueError("Small category must not be released.")

    status = report["response_status"]
    if not isinstance(status, dict) or set(status) != {
        "available", "counts", "percentages", "denominator", "excluded_or_unclear",
    }:
        raise ValueError("Unexpected response status schema.")
    if type(status["available"]) is not bool:
        raise ValueError("Invalid response status availability.")
    if not status["available"]:
        if any(status[key] is not None for key in (
            "counts", "percentages", "denominator", "excluded_or_unclear",
        )):
            raise ValueError("Suppressed response values must be absent.")
    else:
        counts = status["counts"]
        percentages = status["percentages"]
        if not isinstance(counts, dict) or set(counts) != set(THREE_STATUSES):
            raise ValueError("Invalid response counts.")
        if not isinstance(percentages, dict) or set(percentages) != set(THREE_STATUSES):
            raise ValueError("Invalid response percentages.")
        denominator = _int_number(status["denominator"], "response denominator")
        if denominator < MIN_CONTRIBUTORS or sum(counts.values()) != denominator:
            raise ValueError("Response denominator does not reconcile.")
        for label in THREE_STATUSES:
            count = _int_number(counts[label], label)
            if 0 < count < MIN_CONTRIBUTORS:
                raise ValueError("Small response category must not be released.")
            value = percentages[label]
            if (not isinstance(value, (int, float)) or isinstance(value, bool)
                    or value < 0 or value > 100 or abs(value - round(100 * count / denominator, 1)) > 0.01):
                raise ValueError("Inconsistent response percentages.")
        excl = status["excluded_or_unclear"]
        if excl is not None and _int_number(excl, "unclear responses") not in (0,) and excl < MIN_CONTRIBUTORS:
            raise ValueError("Small excluded status must not be released.")
    return report


def save_board_report(report: Mapping[str, Any], destination: Path) -> None:
    checked = validate_board_report(dict(report))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = json.dumps(checked, indent=2, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_BOARD_JSON_BYTES:
        raise ValueError("Board report exceeds size limit.")
    fd, pending_path = tempfile.mkstemp(prefix=".board-report-", suffix=".tmp", dir=str(destination.parent))
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(body)
        os.chmod(pending_path, 0o600)
        os.replace(pending_path, destination)
    finally:
        if os.path.exists(pending_path):
            os.unlink(pending_path)


def load_board_report(location: Path) -> dict[str, Any]:
    location = Path(location)
    if location.stat().st_size > MAX_BOARD_JSON_BYTES:
        raise ValueError("Board report exceeds size limit.")
    return validate_board_report(json.loads(location.read_text(encoding="utf-8")))
