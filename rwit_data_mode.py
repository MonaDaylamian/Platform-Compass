"""Explicit demo selection. This module never accesses private source data."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def is_demo() -> bool:
    deployment = os.environ.get("RWIT_DEPLOYMENT")
    if deployment is not None:
        from rwit_deployment_guard import assert_mode
        assert_mode(deployment)
    value = os.environ.get("RWIT_DATA_MODE", "community").strip().lower()
    if value not in {"community", "demo"}:
        raise ValueError("RWIT_DATA_MODE must be 'community' or 'demo'")
    return value == "demo"

def demo_path(*parts: str) -> Path:
    if not is_demo():
        raise ValueError("Demo dataset is unavailable in community mode")
    root = (ROOT / "input" / "demo").resolve()
    path = root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Demo path escapes demo directory")
    return path
