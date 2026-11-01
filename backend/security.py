"""Access rules for Student Management System.

Only three email addresses may sign in. Every API route except health,
login, and first-time activation requires a valid session for one of them.
"""

from __future__ import annotations

ALLOWED_EMAILS = frozenset(
    {
        "nareshramrajasimhan18@gmail.com",
        "nareshram4804@gmail.com",
        "nareshramstudies@gmail.com",
    }
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def is_allowed_email(email: str) -> bool:
    return normalize_email(email) in ALLOWED_EMAILS
