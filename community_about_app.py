"""Information about Sample Tech Community; no private report access."""
from __future__ import annotations

from pathlib import Path
import streamlit as st
from rwit_theme import apply_about_page_theme

ASSETS = Path(__file__).resolve().parent / 'assets' / 'qr_codes'
PLATFORMS = (
    ('LinkedIn', 'Professional network and updates', 'https://example.com/', 'QRCode-RWIT-Linkedin.png'),
    ('Meetup', 'Events and gatherings', 'https://example.com/', 'QRCode-RWIT-Meetup.png'),
    ('Community contact', 'Example community contact information', 'https://example.com/', 'QRCode-RWIT-Whatsapp.jpeg'),
    ('Website', 'Explore the community', 'https://example.com/', 'QRCode-RWIT-Website.png'),
)
ACTIVITIES = (
    ('💻 Tech events', 'Talks, workshops and hands-on sessions'),
    ('💼 Career events', 'Hiring, CVs, personal and career development'),
    ('☕ Social events', 'Informal get-togethers and networking'),
    ('🤝 Mentorship', 'One-to-one guidance and peer support'),
    ('👥 Community meetups', 'Regular gatherings across Rotterdam'),
    ('🧑‍💻 Co-working days', 'Focused work alongside community members'),
)


def show_community_about() -> None:
    apply_about_page_theme()
    st.title('About the Community')
    with st.container(key='about_community_intro'):
        st.caption('ROTTERDAM WOMEN IN TECH')
        st.header('Connect · Empower · Support')
        st.write(
            'Sample Tech Community (Sample Tech Community) is a warm, international, volunteer-led '
            'community offering a safe and inclusive space for women in tech to connect, '
            'learn and grow professionally.'
        )

    st.subheader('Our mission & vision')
    left, right = st.columns(2, gap='medium')
    with left:
        with st.container(border=True):
            st.markdown('**Our mission**')
            st.write('Connect, support and empower women with international backgrounds in tech through an inclusive community where connections, learning and growth thrive.')
    with right:
        with st.container(border=True):
            st.markdown('**Our vision**')
            st.write('A Rotterdam where women in tech feel seen, supported and empowered to grow, connect and shape the future of technology together.')

    st.subheader('What we do')
    for index in range(0, len(ACTIVITIES), 2):
        columns = st.columns(2, gap='medium')
        for column, (name, description) in zip(columns, ACTIVITIES[index:index + 2]):
            with column:
                with st.container(border=True):
                    st.markdown(f'**{name}**')
                    st.write(description)

    st.subheader('Connect with Sample Tech Community')
    st.write('Explore the community and connect through its official channels.')
    columns = st.columns(2, gap='medium')
    for index, (name, description, url, image_name) in enumerate(PLATFORMS):
        with columns[index % 2]:
            with st.container(border=True):
                st.markdown(f'**{name}**')
                st.caption(description)
                st.link_button(f'Open {name}', url, use_container_width=True)
                with st.expander(f'Show {name} QR code'):
                    qr_path = ASSETS / image_name
                    if qr_path.is_file():
                        st.image(str(qr_path), width=220)
                    else:
                        st.info('QR code is unavailable. Use the link above.')
    st.caption('Community information adapted from the sample community overview (2026).')
