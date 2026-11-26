"""Regression checks for readable Compass text across appearance modes.

The app intentionally keeps a light content canvas even when Streamlit is in
dark appearance mode. These checks guard the native metric/widget overrides.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "theme" / "rwit_compass.css").read_text(encoding="utf-8")


def _color(name: str) -> str:
    match = re.search(rf"--{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{6}})\s*;", CSS)
    if not match:
        raise AssertionError(f"Missing theme color token: {name}")
    return match.group(1)


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
              for channel in channels]
    return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def _contrast(first: str, second: str) -> float:
    light, dark = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class TestThemeContrast(unittest.TestCase):
    def test_native_metric_and_widget_rules_stay_scoped_to_content(self) -> None:
        expected = {
            "stMetricLabel": "compass-muted",
            "stMetricValue": "compass-ink",
            "stWidgetLabel": "compass-ink",
        }
        for component, token in expected.items():
            selector = f'[data-testid="stAppViewContainer"] [data-testid="{component}"]'
            pattern = re.escape(selector) + r"[^{}]*\{([^{}]*)\}"
            with self.subTest(component=component):
                match = re.search(pattern, CSS)
                self.assertIsNotNone(match, f"Missing scoped {component} CSS rule")
                self.assertIn(f"color: var(--{token}) !important;", match.group(1))

    def test_text_contrast_on_light_dashboard_surfaces(self) -> None:
        for background in ("compass-ground", "compass-overview", "compass-surface"):
            for foreground in ("compass-ink", "compass-muted"):
                with self.subTest(background=background, foreground=foreground):
                    self.assertGreaterEqual(_contrast(_color(foreground), _color(background)), 4.5)


if __name__ == "__main__":
    unittest.main()
