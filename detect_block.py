"""Blok / shadow-ban tespit yardimcilari.

Amac: HTTP 200 dahi donse 'bozuk/sahte veri' (shadow-ban) veya challenge
sayfasini erken yakalayip sirket IP'sini yakmadan durmak.
"""

from __future__ import annotations

# JSON yerine donen HTML/challenge sayfalarinda gecen isaretler
_CHALLENGE_NEEDLES = (
    "captcha",
    "are you a human",
    "access denied",
    "challenge-platform",
    "cf-browser-verification",
    "px-captcha",
    "/_sec/cp_challenge",
    "datadome",
)


def is_block_status(status: int) -> bool:
    """Net blok sinyali olan status kodlari."""
    return status in (401, 403, 429)


def looks_like_html(text: str) -> bool:
    """JSON beklenirken HTML donmesi = challenge/yonlendirme suphesi."""
    head = (text or "")[:600].lower().lstrip()
    return head.startswith("<!doctype") or head.startswith("<html") or "<html" in head[:200]


def text_has_challenge(text: str) -> bool:
    """Govdede captcha/challenge isareti var mi."""
    low = (text or "")[:2000].lower()
    return any(n in low for n in _CHALLENGE_NEEDLES)


def listing_incomplete(collected: int, reported: int | None, threshold: float) -> bool:
    """Toplanan urun, bildirilen sayinin esik orani altinda mi (shadow-ban olabilir)."""
    if not reported or reported <= 0:
        return False
    return collected < reported * threshold
