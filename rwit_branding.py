"""Platform Compass shared branding using Streamlit's native image renderer."""
from __future__ import annotations

from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parent
LOGO = ROOT / "assets" / "branding" / "rwit-mark-purple.svg"
FAVICON = ROOT / "assets" / "branding" / "rwit-favicon.png"


def favicon_path() -> str:
    """Local image path accepted by Streamlit page_icon."""
    return str(FAVICON)


def render_sidebar_brand(title: str = "Platform Compass") -> None:
    """Render an actual Streamlit image, styled by the keyed CSS container."""
    if not LOGO.is_file():
        raise FileNotFoundError(f"Missing Sample Tech Community branding asset: {LOGO}")
    with st.container(key="rwit_sidebar_brand"):
        icon_col, title_col = st.columns([1, 4], gap="small", vertical_alignment="center")
        with icon_col:
            st.image(str(FAVICON), width=44)
        with title_col:
            # Streamlit escapes the interpolated text if rendered as text instead of raw HTML.
            st.markdown(f"**{title}**")
