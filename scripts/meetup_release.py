"""Owner-approved snapshot transport for private Streamlit Cloud (not encryption)."""
import base64
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.meetup_reporting import load_meetup_data, validate_meetup_payload

MAX_BYTES = 100_000


def _encode(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def create_release(data_dir: Path) -> str:
    events, group = load_meetup_data(data_dir)
    document = {"group": group, "events": [{**event, "date": event["date"].isoformat()} for event in events]}
    validate_meetup_payload(document)
    digest = hashlib.sha256(_encode(document)).hexdigest()
    body = _encode({"format": "rwit_meetup_private_v1", "sha256": digest, "payload": document})
    if len(body) > MAX_BYTES:
        raise ValueError('Release too large')
    return base64.b64encode(body).decode('ascii')


def read_release(encoded: Any):
    if not isinstance(encoded, str) or not 0 < len(encoded) < MAX_BYTES * 2:
        raise ValueError('Missing or oversized Meetup release')
    try:
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) > MAX_BYTES:
            raise ValueError('Oversized Meetup release')
        document = json.loads(raw)
        if not isinstance(document, dict) or set(document) != {"format", "sha256", "payload"} or document["format"] != 'rwit_meetup_private_v1':
            raise ValueError('Invalid Meetup release format')
        if document["sha256"] != hashlib.sha256(_encode(document["payload"])).hexdigest():
            raise ValueError('Meetup report digest mismatch')
        return validate_meetup_payload(document["payload"])
    except (TypeError, KeyError, ValueError, UnicodeError) as exc:
        raise ValueError('Invalid Meetup release') from exc
