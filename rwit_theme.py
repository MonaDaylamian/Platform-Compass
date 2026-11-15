"""Platform Compass theme adapter: CSS is the single source of truth.

CSS styles Streamlit components; Python resolves named tokens for Altair.
"""

from pathlib import Path
import re

import streamlit as st

_STYLESHEET = Path(__file__).resolve().parent / "theme" / "rwit_compass.css"


def _css_text() -> str:
    return _STYLESHEET.read_text(encoding="utf-8")


def _css_color(variable: str) -> str:
    """Read a hexadecimal color token from the Compass CSS file."""
    pattern = rf"(?m)^\s*--{re.escape(variable)}\s*:\s*(#[0-9a-fA-F]{{6}})\s*;"
    matches = re.findall(pattern, _css_text())
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one CSS color token: --{variable}")
    return matches[0]


# Altair needs resolved color strings, not CSS var() expressions.
# These names are compatibility aliases for the existing dashboard imports.
PURPLE = _css_color("compass-purple")
GREEN = _css_color("compass-green")
YELLOW = _css_color("compass-yellow")
CHART_PURPLE = PURPLE
CHART_GREEN = _css_color("compass-chart-green")
CHART_YELLOW = YELLOW
INK = _css_color("compass-ink")
MUTED_INK = _css_color("compass-muted")
BACKGROUND = _css_color("compass-ground")
WHITE = _css_color("compass-surface")


def apply_dashboard_theme() -> None:
    """Apply trusted local CSS to all Streamlit pages."""
    st.markdown(f"<style>\n{_css_text()}\n</style>", unsafe_allow_html=True)


# Dedicated About page CSS; loaded only on the two About pages.
_ABOUT_STYLESHEET = Path(__file__).resolve().parent / "theme" / "about_pages.css"


def apply_about_page_theme() -> None:
    """Apply isolated informational-page styles alongside the shared Compass theme."""
    st.markdown(f"<style>\n{_ABOUT_STYLESHEET.read_text(encoding='utf-8')}\n</style>", unsafe_allow_html=True)
