"""Platform Compass: navigation for the read-only community board dashboards.

Local and Cloud launches intentionally select different report sources. Running
``streamlit run board_app.py`` reads validated local snapshots automatically;
``streamlit run board_cloud_app.py`` reads ONLY approved Cloud releases.
"""

from __future__ import annotations

import os
import streamlit as st
from rwit_branding import render_sidebar_brand, favicon_path
from rwit_data_mode import is_demo

from rwit_theme import apply_dashboard_theme
from overview_app import show_overview as render_community_overview
from whatsapp_app import show_whatsapp_dashboard
from meetup_app import show_meetup_dashboard
from linkedin_app import show_linkedin_dashboard
from community_about_app import show_community_about
from project_about_app import show_project_about


# Legacy report readers use these opt-in flags. Keep configuration centralized
# here so local users never have to remember special shell commands. In Cloud,
# unset both flags explicitly to prevent local data from being used as fallback.
LOCAL_PREVIEW_FLAGS = (
    "RWIT_LINKEDIN_LOCAL_PREVIEW",
    "RWIT_MEETUP_LOCAL_PREVIEW",
)


def configure_report_sources(*, cloud_mode: bool) -> None:
    """Choose the data boundary before any dashboard page reads a report.

    The Cloud entry point must pass ``cloud_mode=True`` after validating the
    approved WhatsApp release. Never infer Cloud mode from the mere presence of
    a local ``.streamlit/secrets.toml``, which developers may also have.
    """
    from rwit_deployment_guard import assert_mode
    deployment = os.environ.get("RWIT_DEPLOYMENT")
    if deployment is not None:
        assert_mode("private_cloud" if cloud_mode else "demo")
    for flag in LOCAL_PREVIEW_FLAGS:
        if cloud_mode or deployment == "demo":
            os.environ.pop(flag, None)
        else:
            os.environ[flag] = "1"


def show_overview() -> None:
    """Landing page wrapper retained for existing navigation/test contracts."""
    st.title("Board Dashboard")
    render_community_overview()


def main(*, cloud_mode: bool = False) -> None:
    configure_report_sources(cloud_mode=cloud_mode)

    st.set_page_config(
        page_title="Platform Compass · Board",
        page_icon=str(favicon_path()),
        layout="wide",
    )

    apply_dashboard_theme()
    if is_demo():
        st.info("Demo — Synthetic Data · All analytics are fictional.")

    pages = [
        st.Page(show_overview, title="Board Dashboard", icon=":material/dashboard:", default=True),
        st.Page(show_whatsapp_dashboard, title="WhatsApp Analytics", icon=":material/chat:"),
        st.Page(show_meetup_dashboard, title="Meetup Analytics", icon=":material/event:"),
        st.Page(show_linkedin_dashboard, title="LinkedIn Analytics", icon=":material/monitoring:"),
        st.Page(show_community_about, title="About the Community", icon=":material/groups:"),
        st.Page(show_project_about, title="About the Project", icon=":material/info:"),
    ]

    page = st.navigation(pages, position="hidden")

    with st.sidebar:
        render_sidebar_brand()
        for destination in pages:
            if destination.title == "About the Community":
                with st.container(key="rwit_about_menu_separator"):
                    st.divider()
            st.page_link(destination, label=destination.title, icon=destination.icon)

    page.run()


if __name__ == "__main__":
    main()
