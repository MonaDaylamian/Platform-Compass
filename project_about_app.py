"""About Platform Compass: architecture and transparent privacy description."""
from __future__ import annotations

import streamlit as st
from rwit_theme import apply_about_page_theme
from rwit_data_mode import is_demo

DEVELOPER_URL = 'https://www.linkedin.com/in/mona-daylamian/'


def _workflow() -> None:
    """A native Streamlit Graphviz flowchart with actual connected arrows."""
    diagram = r"""digraph RWIT {
      graph [rankdir=TB, bgcolor="transparent", pad="0.24",
             nodesep="0.55", ranksep="0.68", splines=polyline,
             compound=true, fontname="Helvetica"]
      node [shape=box, style="rounded,filled", penwidth=1.4,
            fontname="Helvetica", fontsize=14, margin="0.25,0.18"]
      edge [color="#909090", arrowsize=0.7, penwidth=1.3]

      subgraph cluster_sources {
        label="1. Data Sources"; labelloc="t"; fontsize=17;
        color="#DEDEDE"; bgcolor="#F6F6F6"; style=rounded;
        wa [label="WhatsApp exports", color="#159E94", fillcolor="#E2F5F2", fontcolor="#14554E"];
        li [label="LinkedIn reports", color="#159E94", fillcolor="#E2F5F2", fontcolor="#14554E"];
        me [label="Meetup reports", color="#159E94", fillcolor="#E2F5F2", fontcolor="#14554E"];
        {rank=same; wa; li; me;}
      }
      subgraph cluster_processing {
        label="2. Private Data Processing"; fontsize=17;
        color="#DEDEDE"; bgcolor="#F6F6F6"; style=rounded;
        parsing [label="Import, parse and validate", color="#9855EA", fillcolor="#F0E5FA", fontcolor="#523078"];
        ai [label="Optional AI-assisted signal extraction\n(WhatsApp conversations only)", color="#9855EA", fillcolor="#F0E5FA", fontcolor="#523078"];
        privacy [label="Aggregation and privacy controls", color="#9855EA", fillcolor="#F0E5FA", fontcolor="#523078"];
        parsing -> ai [label="WhatsApp", fontsize=10];
        ai -> privacy;
        parsing -> privacy [label="LinkedIn / Meetup", fontsize=10];
      }
      subgraph cluster_review {
        label="3. Review and Approval"; fontsize=17;
        color="#DEDEDE"; bgcolor="#F6F6F6"; style=rounded;
        validate [label="Validate reports", color="#D4A21F", fillcolor="#FFF3D2", fontcolor="#71551E"];
        review [label="Owner review and release approval", color="#D4A21F", fillcolor="#FFF3D2", fontcolor="#71551E"];
        validate -> review;
      }
      subgraph cluster_dashboard {
        label="4. Platform Compass"; fontsize=17;
        color="#DEDEDE"; bgcolor="#F6F6F6"; style=rounded;
        board [label="Board Dashboard", color="#159E94", fillcolor="#E2F5F2", fontcolor="#14554E"];
        platform [label="Platform Analytics", color="#159E94", fillcolor="#E2F5F2", fontcolor="#14554E"];
        {rank=same; board; platform;}
      }
      wa -> parsing;
      li -> parsing;
      me -> parsing;
      privacy -> validate;
      review -> board;
      review -> platform;
    }"""
    st.graphviz_chart(diagram, use_container_width=True)
    st.caption(
        "Conceptual pipeline: source-specific parsing, optional WhatsApp AI extraction, "
        "privacy-bounded reporting, and owner-approved release. "
        "Cross-platform AI interpretation is a separate optional aggregate-only workflow."
    )



def show_project_about() -> None:
    apply_about_page_theme()
    st.title('About the Project')
    with st.container(key='about_project_intro'):
        st.caption('PLATFORM COMPASS · COMMUNITY INTELLIGENCE' if is_demo() else 'PLATFORM COMPASS · COMMUNITY INTELLIGENCE')
        st.header('Turning community activity into meaningful insights')
        if is_demo():
            st.write(
                'Platform Compass is a privacy-conscious community analytics application '
                'designed to help communities and organizations better understand their '
                "members' needs, interests, and engagement across social platforms, "
                'without the time-consuming effort of manually reviewing individual '
                'conversations and interactions.'
            )
            st.write(
                'The board of Rotterdam Women in Tech (RWiT) needed a clearer '
                "understanding of members' needs and priorities to guide future "
                'activities and strategic planning. Platform Compass addresses this '
                'challenge by transforming fragmented community activity into meaningful, '
                'actionable insights that support evidence-based decisions.'
            )
        else:
            st.write(
                'Platform Compass is a privacy-conscious data analytics application that brings '
                'together LinkedIn, Meetup and WhatsApp reporting to help Rotterdam Women '
                'in Tech understand engagement, identify recurring themes and support '
                'informed community decisions.'
            )

    st.subheader('Project objectives')
    items = (
        ('📊 Measure engagement', 'Understand community activity and growth across platforms.'),
        ('🔎 Identify needs', 'Find recurring interests and themes in analyzed conversations.'),
        ('🗓️ Support planning', 'Use validated evidence to inform community priorities.'),
        ('🛡️ Respect privacy', 'Report insights without exposing raw member conversations.'),
    )
    for index in range(0, len(items), 2):
        columns = st.columns(2)
        for column, (heading, description) in zip(columns, items[index:index + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f'**{heading}**')
                    st.write(description)

    st.subheader('How it works')
    _workflow()

    st.subheader('Technical overview')
    technology = {
        'Application': 'Python · Streamlit',
        'Visualizations': 'Altair and Streamlit components',
        'Data handling': 'Python · Pandas · validated JSON/CSV/Excel reports',
        'Data sources': 'WhatsApp export · LinkedIn reports · Meetup reports',
        'AI provider': 'OpenAI API',
        'AI model': 'gpt-6-luna',
        'AI use cases': 'WhatsApp signal extraction; optional cross-platform aggregate interpretation',
        'Deployment': 'Public Streamlit synthetic demo',
        'Quality checks': 'Schema validation and Pytest regression suite',
        'Source control': 'Public GitHub snapshot generated from private source',
    }
    for label, detail in technology.items():
        left, right = st.columns([1, 2])
        left.markdown(f'**{label}**')
        right.write(detail)

    with st.expander('Advanced technical details'):
        st.write(
            'WhatsApp conversations are reconstructed and optionally classified into structured '
            'signals using a validated output schema. Reporting aggregates those signals and '
            'applies minimum-contributor and minimum-conversation requirements.'
        )
        st.write(
            'LinkedIn and Meetup reports use source-specific import and validation paths. '
            'A separate owner-controlled AI workflow can draft interpretations from reviewed '
            'aggregate evidence; drafts require explicit approval and need not be shown in the dashboard.'
        )
        st.write(
            'The Cloud entry point reads owner-approved report releases. The local entry '
            'point can read private files for development. Cloud Secrets contain encoded '
            'releases; base64 is not encryption.'
        )

    st.subheader('Privacy, security & responsible AI')
    safeguards = (
        ('Data minimization', 'Dashboard reports exclude raw WhatsApp messages, member identifiers, source excerpts and private processing errors.'),
        ('Member anonymization', 'WhatsApp preprocessing is configured to anonymize members, although aggregation by itself does not guarantee anonymity.'),
        ('Disclosure thresholds', 'Released WhatsApp needs/intent categories and response statuses require at least five distinct contributors and three distinct conversations.'),
        ('Controlled processing', 'Raw exports and detailed workbooks are owner-controlled local files excluded from Git. Dashboard visitors cannot run AI or upload WhatsApp exports.'),
        ('Restricted access', 'The Cloud dashboard is designed for authorized viewers and requires approved report releases.'),
        ('Transparent interpretation', 'LinkedIn engagement, Meetup attendance and WhatsApp AI-analyzed conversations have different measurement units; memberships are not deduplicated across platforms.'),
        ('Human review', 'This version does not implement human-in-the-loop decision controls. There are no automated-action risk thresholds or actions requiring human confirmation. Owner review and approval of reports before publication is a separate safeguard.'),
        ('How AI processes community data', 'Platform Compass uses OpenAI to identify trends and interests in WhatsApp conversations. Selected conversation content is processed through the OpenAI API, while the dashboard displays only aggregated results. Cross-platform AI analysis uses aggregated data without sharing original conversations.'),
    )
    for label, detail in safeguards:
        with st.container(border=True):
            st.markdown(f'**{label}**')
            st.write(detail)

    with st.expander('Data governance and reporting limitations'):
        st.write(
            'This page describes implemented application safeguards, not a complete legal '
            'privacy policy. Formal decisions about GDPR lawful basis, member notices, '
            'retention/deletion periods and data subject request procedures must be '
            'confirmed by the responsible community organization.'
        )
        st.write(
            'Meetup attendance is sourced from Meetup displays and is not independently '
            'verified. AI-analyzed conversation counts do not represent unique individuals. '
            'Reporting periods may differ across sources or be merged for privacy.'
        )

    st.subheader('Project credit')
    if is_demo():
        st.write(
            'Platform Compass was designed and developed by **Mona Daylamian**, '
            'a tech board member of Rotterdam Women in Tech (RWiT), in response '
            'to a real-world challenge identified within the community.'
        )
        st.write(
            'This public version is a portfolio demonstration built entirely on '
            'synthetic data. It showcases the application\'s capabilities and '
            'technical approach without exposing real community or member information.'
        )
    else:
        st.write('Platform Compass is a synthetic portfolio demonstration.')
    st.link_button('Connect with Mona on LinkedIn', DEVELOPER_URL)
