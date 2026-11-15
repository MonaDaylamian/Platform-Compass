
"""Local-only LinkedIn export importer and validated board snapshot builder."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from scripts.community_members import get_membership
from scripts.linkedin_topics import aggregate_topics

KINDS = ("content", "followers", "visitors")
DEMOS = ("Location", "Job function", "Seniority", "Industry", "Company size")


def _libreoffice_binary() -> str:
    """Find LibreOffice's headless converter on macOS, Linux or Windows PATH."""
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for item in candidates:
        if item and Path(item).is_file():
            return str(item)
    raise RuntimeError(
        "LibreOffice is required to decode LinkedIn's legacy .xls text reliably. "
        "On macOS install once with: brew install --cask libreoffice"
    )


def _convert_book(path: Path, converted: Path) -> Path:
    """Convert original .xls preserving LinkedIn shared-string post descriptions."""
    converted.mkdir(parents=True, exist_ok=True)
    target = converted / f"linkedin_{next(k for k in KINDS if k in path.name.lower())}.xlsx"

    if path.suffix.lower() == ".xlsx":
        shutil.copy2(path, target)
        return target

    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="linkedin-convert-") as tmp:
        profile_url = (Path(tmp) / "lo_profile").as_uri()
        command = [
            _libreoffice_binary(),
            f"-env:UserInstallation={profile_url}",
            "--headless",
            "--convert-to",
            "xlsx",
            "--outdir",
            tmp,
            str(path),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        output = Path(tmp) / (path.stem + ".xlsx")

        if result.returncode != 0 or not output.is_file():
            raise RuntimeError(
                f"LinkedIn XLS conversion failed: {result.stderr[-300:]}"
            )
        shutil.copy2(output, target)

    return target


def _read_book(path: Path) -> dict[str, pd.DataFrame]:
    return pd.read_excel(
        path,
        sheet_name=None,
        engine="openpyxl",
        header=None,
        dtype=object,
    )


def _table(book: dict, sheet: str, header_row: int = 0) -> pd.DataFrame:
    if sheet not in book:
        raise ValueError(f"Missing LinkedIn worksheet: {sheet}")

    frame = book[sheet]
    if len(frame) <= header_row:
        raise ValueError(f"Empty worksheet: {sheet}")

    headers = [
        str(x).strip() if pd.notna(x) else ""
        for x in frame.iloc[header_row].tolist()
    ]
    data = frame.iloc[header_row + 1:].copy()
    data.columns = headers

    return data.dropna(how="all").reset_index(drop=True)


def _required(df: pd.DataFrame, *headers: str) -> None:
    missing = [x for x in headers if x not in df.columns]
    if missing:
        raise ValueError(
            f"LinkedIn export schema changed. Missing columns: {missing}"
        )


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def _date(series: pd.Series) -> pd.Series:
    return pd.to_datetime(
        series,
        format="%m/%d/%Y",
        errors="coerce",
    )


def _scalar_number(value) -> int:
    parsed = pd.to_numeric(value, errors="coerce")
    return int(parsed) if pd.notna(parsed) else 0


def _metric(frame: pd.DataFrame, field: str) -> int:
    _required(frame, field)
    return int(_number(frame[field]).sum())


def _monthly(
    frame: pd.DataFrame,
    columns: dict[str, str],
) -> list[dict]:
    _required(frame, "Date", *columns.values())

    data = frame.copy()
    data["date_parsed"] = _date(data["Date"])

    if data["date_parsed"].isna().any():
        raise ValueError("Invalid Date in LinkedIn metrics")

    data["month"] = data["date_parsed"].dt.strftime("%Y-%m")

    for output, col in columns.items():
        data[output] = _number(data[col])

    return (
        data.groupby("month", as_index=False)[list(columns)]
        .sum()
        .round()
        .astype({x: int for x in columns})
        .to_dict("records")
    )


def _demographics(book: dict) -> dict:
    out = {}

    for sheet in DEMOS:
        data = _table(book, sheet)

        if data.shape[1] < 2:
            raise ValueError(
                f"Unexpected demographics schema: {sheet}"
            )

        label, amount = data.columns[:2]
        items = [
            {"name": str(name), "count": int(count)}
            for name, count in zip(data[label], _number(data[amount]))
            if pd.notna(name) and count > 0
        ]
        out[sheet] = sorted(
            items,
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

    return out


def build_snapshot(source: Path, converted: Path) -> dict:
    """Build LinkedIn analytics using Excel exports and membership CSV."""

    # Validate membership data before processing the workbooks.
    membership = get_membership("linkedin")

    # Exactly one Excel export is required for each type.
    files = {}

    for kind in KINDS:
        matches = sorted(
            p for p in source.iterdir()
            if p.is_file()
            and kind in p.name.lower()
            and p.suffix.lower() in (".xls", ".xlsx")
        )

        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one {kind} .xls/.xlsx "
                f"in {source}, got {len(matches)}"
            )

        files[kind] = matches[0]

    converted.mkdir(parents=True, exist_ok=True)
    books = {}

    for kind, path in files.items():
        converted_path = _convert_book(path, converted)
        books[kind] = _read_book(converted_path)

    content = books["content"]
    metrics = _table(content, "Metrics", 1)
    posts = _table(content, "All posts", 1)

    _required(
        posts,
        "Post title",
        "Post link",
        "Created date",
        "Impressions",
        "Clicks",
        "Likes",
        "Comments",
        "Reposts",
        "Engagement rate",
    )

    visitors = _table(
        books["visitors"],
        "Visitor metrics",
    )
    followers = _table(
        books["followers"],
        "New followers",
    )

    metrics["parsed_date"] = _date(metrics["Date"])
    visitors["parsed_date"] = _date(visitors["Date"])
    followers["parsed_date"] = _date(followers["Date"])

    if any(
        frame["parsed_date"].isna().any()
        for frame in (metrics, visitors, followers)
    ):
        raise ValueError(
            "LinkedIn report contains invalid dates"
        )

    post_records = []

    for _, row in posts.iterrows():
        post_date = pd.to_datetime(
            row["Created date"],
            format="%m/%d/%Y",
            errors="coerce",
        )

        if pd.isna(post_date):
            raise ValueError("Invalid post date")

        title = str(row["Post title"] or "").strip()
        link = str(row["Post link"] or "").strip()

        if not link.startswith("https://www.linkedin.com/"):
            raise ValueError("Unexpected post link")

        post_records.append({
            "date": post_date.date().isoformat(),
            "title": title[:400],
            "url": link,
            "impressions": _scalar_number(row["Impressions"]),
            "clicks": _scalar_number(row["Clicks"]),
            "reactions": _scalar_number(row["Likes"]),
            "comments": _scalar_number(row["Comments"]),
            "reposts": _scalar_number(row["Reposts"]),
        })

    post_records.sort(
        key=lambda x: (
            x["reactions"] + x["comments"] + x["reposts"],
            x["impressions"],
        ),
        reverse=True,
    )

    output = {
        "schema": "rwit_linkedin_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),

        # Membership counts now come from the shared CSV.
        "followers_total": membership["member_count"],
        "followers_as_of": membership["as_of_date"],

        "period_start": min(
            metrics["parsed_date"].min(),
            visitors["parsed_date"].min(),
        ).date().isoformat(),

        "period_end": max(
            metrics["parsed_date"].max(),
            visitors["parsed_date"].max(),
        ).date().isoformat(),

        "content_period": [
            metrics["parsed_date"].min().date().isoformat(),
            metrics["parsed_date"].max().date().isoformat(),
        ],

        "visitor_period": [
            visitors["parsed_date"].min().date().isoformat(),
            visitors["parsed_date"].max().date().isoformat(),
        ],

        "follower_growth_period": [
            followers["parsed_date"].min().date().isoformat(),
            followers["parsed_date"].max().date().isoformat(),
        ],

        "totals": {
            "posts": len(post_records),
            "impressions": _metric(metrics, "Impressions (total)"),
            "reactions": _metric(metrics, "Reactions (total)"),
            "comments": _metric(metrics, "Comments (total)"),
            "reposts": _metric(metrics, "Reposts (total)"),
            "clicks": _metric(metrics, "Clicks (total)"),
            "page_views": _metric(
                visitors,
                "Total page views (total)",
            ),
            "daily_unique_visitors_sum": _metric(
                visitors,
                "Total unique visitors (total)",
            ),
            "new_followers": _metric(
                followers,
                "Total followers",
            ),
        },

        "monthly_content": _monthly(
            metrics,
            {
                "impressions": "Impressions (total)",
                "reactions": "Reactions (total)",
                "comments": "Comments (total)",
                "reposts": "Reposts (total)",
                "clicks": "Clicks (total)",
            },
        ),

        "monthly_visitors": _monthly(
            visitors,
            {"page_views": "Total page views (total)"},
        ),

        "demographics": {
            "followers": _demographics(books["followers"]),
            "visitors": _demographics(books["visitors"]),
        },

        # Only public post-level and aggregate records.
        "top_posts": post_records[:10],
        "topic_analysis_status": "keyword_rules_v1",
        "topic_analysis": aggregate_topics(post_records),
    }

    validate_snapshot(output)
    return output


def validate_snapshot(data: dict) -> dict:
    if not isinstance(data, dict) or data.get("schema") != "rwit_linkedin_v1":
        raise ValueError("Wrong LinkedIn snapshot schema")

    if "generated_at_utc" in data:
        try:
            generated = datetime.fromisoformat(
                data["generated_at_utc"]
            )
            if generated.tzinfo is None:
                raise ValueError("Missing timezone")
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid LinkedIn generation timestamp"
            ) from exc

    if (
        not isinstance(data.get("followers_total"), int)
        or data["followers_total"] <= 0
    ):
        raise ValueError("Invalid total followers")

    if (
        not isinstance(data.get("totals"), dict)
        or data["totals"].get("posts", -1) < 0
    ):
        raise ValueError("Invalid content totals")

    if len(data.get("monthly_content", [])) == 0:
        raise ValueError("No activity records")

    if "topic_analysis" in data:
        analysis = data["topic_analysis"]

        if (
            not isinstance(analysis, dict)
            or analysis.get("post_count") != data["totals"]["posts"]
        ):
            raise ValueError(
                "LinkedIn topic analysis post count mismatch"
            )

        topics = analysis.get("topics", [])

        if (
            sum(x["posts"] for x in topics)
            != data["totals"]["posts"]
        ):
            raise ValueError(
                "LinkedIn topic totals mismatch"
            )

    return data


def write_snapshot(snapshot: dict, path: Path) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    path.write_text(
        json.dumps(
            validate_snapshot(snapshot),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
