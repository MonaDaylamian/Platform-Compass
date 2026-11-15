"""Base64 is packaging, NOT encryption. Validate before showing in Cloud."""
import base64
import hashlib
import json
from scripts.linkedin_reporting import validate_snapshot

MAX_BYTES = 180_000


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def create_release(report):
    validate_snapshot(report)
    raw = _encode({"schema": "rwit_linkedin_release_v1", "payload": report,
                   "sha256": hashlib.sha256(_encode(report)).hexdigest()})
    if len(raw) > MAX_BYTES:
        raise ValueError("LinkedIn release too large")
    return base64.b64encode(raw).decode("ascii")


def read_release(value):
    if not isinstance(value, str) or len(value) > MAX_BYTES * 2:
        raise ValueError("Missing or oversized LinkedIn release")
    try:
        raw = base64.b64decode(value, validate=True)
        if len(raw) > MAX_BYTES:
            raise ValueError("Oversized LinkedIn release")
        parsed = json.loads(raw)
        if parsed.get("schema") != "rwit_linkedin_release_v1":
            raise ValueError("Unexpected release format")
        report = validate_snapshot(parsed["payload"])
        if hashlib.sha256(_encode(report)).hexdigest() != parsed["sha256"]:
            raise ValueError("Release digest mismatch")
        return report
    except (KeyError, TypeError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid LinkedIn release") from exc
