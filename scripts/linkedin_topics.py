"""Conservative, deterministic LinkedIn post topic classification.

This measures engagement with *published posts*, not follower preferences.
Corrupted legacy Excel text is withheld instead of guessed at.
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict

TOPIC_KEYWORDS = {
    "AI & Technical Learning": (
        "artificial intelligence", "machine learning", "generative ai", "genai", " llm", " ai ",
        "data science", "data analyst", "data engineering", "technical workshop",
        "coding", "programming", "software engineering", "cybersecurity", "hackathon",
        "tech talk", "mcp", "bigquery", "look er", "python", "cloud computing",
    ),
    "Career & Opportunities": (
        "job search", "job hunting", "job opportunity", "job opening", "job vacancy",
        "hiring", "recruitment", "recruiter", "career", "interview", "resume", "cv ",
        "professional development", "mentorship", "mentor", "internship",
        "leadership", "upskill", "transition into tech",
    ),
    "Networking & Community": (
        "networking", "meetup", "meet-up", "co-working", "coworking", "community",
        "gathering", "drinks", "coffee chat", "get together", "get-together",
        "connect with", "friendship", "social event", "halloween",
    ),
    "Women in Tech & Inspiration": (
        "women in tech", "women in technology", "women in stem", "inspiring women",
        "female founder", "gender diversity", "women empowerment", "empower women",
        "representation", "role model", "women leaders", "celebrat", "achievement",
    ),
    "Events & Announcements": (
        "register now", "sign up", "rsvp", "save the date", "upcoming event",
        "join us", "don't miss", "event announcement", "tickets", "registration",
        "reminder", "tomorrow", "next session", "webinar",
    ),
}


def readable(text: str) -> bool:
    """Reject obvious damaged text, allowing legitimate Unicode accents and emojis."""
    if not text or len(text.strip()) < 24:
        return False
    sample = text[:1600]
    if "\ufffd" in sample or "\x00" in sample:
        return False
    if any(ord(c) < 32 and c not in '\n\t\r' for c in sample):
        return False
    # Legacy UTF-16 bytes decoded incorrectly often become CJK ideographs.
    strange = sum(unicodedata.name(c, '').startswith((
        'CJK UNIFIED', 'HANGUL SYLLABLE', 'HIRAGANA', 'KATAKANA'
    )) for c in sample)
    return strange / max(1, len(sample)) < 0.04


def classify(text: str) -> str:
    if not readable(text):
        return "Unclassified (unreadable text)"
    normalized = ' ' + re.sub(r'\s+', ' ', text).casefold() + ' '
    score = {topic: sum(1 for phrase in phrases if phrase in normalized)
             for topic, phrases in TOPIC_KEYWORDS.items()}
    winning_score = max(score.values())
    if not winning_score:
        return "Other / no keyword match"
    # Ordered priority resolves ties. Categories are indicative, not ground truth.
    return next(topic for topic, value in score.items() if value == winning_score)


def aggregate_topics(posts: list[dict]) -> dict:
    groups = defaultdict(lambda: dict(posts=0, impressions=0, reactions=0,
                                      comments=0, reposts=0, clicks=0))
    for post in posts:
        topic = classify(str(post.get('title') or ''))
        g = groups[topic]
        g['posts'] += 1
        for k in ('impressions', 'reactions', 'comments', 'reposts', 'clicks'):
            g[k] += int(post.get(k, 0))
    items = []
    for topic, values in groups.items():
        engagements = values['reactions'] + values['comments'] + values['reposts']
        items.append(dict(topic=topic, **values, interactions=engagements,
                          interactions_per_post=round(engagements / values['posts'], 2),
                          interaction_rate=round(100 * engagements / values['impressions'], 2)
                          if values['impressions'] else None))
    items.sort(key=lambda x: (-x['interactions'], x['topic']))
    unclassified = groups.get('Unclassified (unreadable text)', {}).get('posts', 0)
    return {'method': 'keyword_rules_v1', 'post_count': len(posts),
            'readable_posts': len(posts) - unclassified, 'unreadable_posts': unclassified,
            'topics': items}
