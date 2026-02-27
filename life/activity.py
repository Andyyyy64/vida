"""Activity category normalization and meta-category mapping."""

from __future__ import annotations

import unicodedata

# Canonical activity categories
CANONICAL_ACTIVITIES: list[str] = [
    "プログラミング",
    "YouTube視聴",
    "ブラウジング",
    "チャット",
    "SNS",
    "ゲーム",
    "休憩",
    "離席",
    "ドキュメント閲覧",
    "コンテンツ制作",
    "会話",
    "読書",
    "音楽",
    "食事",
    "睡眠",
    "不在",
]

# Meta-categories for productivity scoring
META_CATEGORIES: dict[str, list[str]] = {
    "focus": ["プログラミング", "ドキュメント閲覧", "コンテンツ制作", "読書"],
    "communication": ["チャット", "会話"],
    "entertainment": ["YouTube視聴", "ゲーム", "SNS", "音楽"],
    "browsing": ["ブラウジング"],
    "break": ["休憩", "離席", "食事"],
    "idle": ["睡眠", "不在"],
}


def _normalize_str(s: str) -> str:
    """Normalize unicode and strip whitespace for comparison."""
    return unicodedata.normalize("NFKC", s).strip().lower()


def _similarity(a: str, b: str) -> float:
    """Simple character-level similarity ratio between two strings.

    Uses longest common subsequence ratio — no external dependencies.
    """
    na, nb = _normalize_str(a), _normalize_str(b)

    # Exact match
    if na == nb:
        return 1.0

    # Substring containment (e.g. "プログラミングと会話" contains "プログラミング")
    if na in nb or nb in na:
        shorter = min(len(na), len(nb))
        longer = max(len(na), len(nb))
        return shorter / longer if longer > 0 else 0.0

    # LCS-based similarity
    m, n = len(na), len(nb)
    if m == 0 or n == 0:
        return 0.0

    # Space-efficient LCS length
    prev = [0] * (n + 1)
    for i in range(1, m + 1):
        curr = [0] * (n + 1)
        for j in range(1, n + 1):
            if na[i - 1] == nb[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev = curr

    lcs_len = prev[n]
    return (2.0 * lcs_len) / (m + n)


def normalize_activity(raw: str) -> str:
    """Normalize an activity name to its canonical form.

    Uses fuzzy matching to find the best canonical category.
    If no good match is found (similarity < threshold), returns the
    original string to allow new categories to emerge.
    """
    if not raw:
        return raw

    cleaned = raw.strip()
    normalized = _normalize_str(cleaned)

    # Exact match against canonical list
    for canonical in CANONICAL_ACTIVITIES:
        if _normalize_str(canonical) == normalized:
            return canonical

    # Fuzzy match — find best candidate
    threshold = 0.5
    best_score = 0.0
    best_match = ""
    for canonical in CANONICAL_ACTIVITIES:
        score = _similarity(cleaned, canonical)
        if score > best_score:
            best_score = score
            best_match = canonical

    if best_score >= threshold:
        return best_match

    return cleaned


def get_meta_category(activity: str) -> str:
    """Get the meta-category for a given activity.

    Returns 'other' if no meta-category is found.
    """
    normalized = normalize_activity(activity)
    for meta, activities in META_CATEGORIES.items():
        if normalized in activities:
            return meta
    return "other"


def get_canonical_categories() -> list[str]:
    """Return list of all canonical activity category names."""
    return list(CANONICAL_ACTIVITIES)
