from __future__ import annotations


def normalize_email(email: str) -> str:
    """Return the canonical email representation used by auth and invitations."""

    return email.strip().lower()
