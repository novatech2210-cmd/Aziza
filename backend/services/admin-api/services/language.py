"""
Qube Admin API — Language detection
Detects the primary language of a text sample.
Uses langdetect when available; falls back to charset heuristics.
"""

from __future__ import annotations

import re


def detect_language(text: str) -> dict:
    """Return {primary: str, confidence: float} for the given text sample."""
    if not text or not text.strip():
        return {"primary": "unknown", "confidence": 0.0}

    # Try langdetect (pip install langdetect)
    try:
        from langdetect import detect, detect_langs  # type: ignore
        langs = detect_langs(text)
        if langs:
            top = langs[0]
            return {"primary": top.lang, "confidence": round(top.prob, 3)}
    except Exception:
        pass

    # Fallback: simple Unicode-range heuristic
    cyrillic = len(re.findall(r"[\u0400-\u04ff]", text))
    latin = len(re.findall(r"[a-zA-Z]", text))
    total = len(text.strip()) or 1

    if cyrillic / total > 0.3:
        # Distinguish Uzbek Cyrillic (has ʻ, Ўў, Ққ, Ғғ, Ҳҳ) from Russian
        uzbek_chars = len(re.findall(r"[ЎўҚқҒғҲҳ]", text))
        lang = "uz" if uzbek_chars > 2 else "ru"
        return {"primary": lang, "confidence": round(cyrillic / total, 3)}

    if latin / total > 0.5:
        return {"primary": "en", "confidence": round(latin / total, 3)}

    return {"primary": "unknown", "confidence": 0.0}
