"""Activity category normalization and meta-category mapping.

Uses DB-stored activity_mappings as the source of truth instead of hardcoded lists.
"""

from __future__ import annotations

import logging
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from daemon.storage.database import Database

log = logging.getLogger(__name__)

# Valid meta-categories (UI/logic constants)
VALID_META_CATEGORIES = {"focus", "communication", "entertainment", "browsing", "break", "idle", "other"}


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


class ActivityManager:
    """Manages activity normalization and meta-category mapping using DB-stored mappings."""

    def __init__(self, db: Database):
        self._db = db
        self._cache: dict[str, str] = {}  # activity -> meta_category
        self._reload()

    def _reload(self):
        """Load all mappings from DB into cache."""
        self._cache.clear()
        for row in self._db.get_all_activity_mappings():
            self._cache[row["activity"]] = row["meta_category"]

    def get_frequent(self, limit: int = 15) -> list[str]:
        """Get most frequently used activities for LLM prompt examples."""
        return self._db.get_frequent_activities(limit)

    def get_grouped_by_meta(self) -> dict[str, list[str]]:
        """Get all activities grouped by meta_category, ordered by frequency within each group."""
        grouped: dict[str, list[str]] = {}
        for row in self._db.get_all_activity_mappings():
            meta = row["meta_category"]
            if meta not in grouped:
                grouped[meta] = []
            grouped[meta].append(row["activity"])
        return grouped

    def apply_merge(self, old: str, new: str):
        """Merge old activity into new in DB, then reload cache."""
        self._db.merge_activity(old, new)
        self._reload()
        log.info("Merged activity: %s → %s", old, new)

    def normalize_and_register(self, raw: str, meta: str) -> tuple[str, str]:
        """Normalize an activity name and register it in DB.

        Returns (normalized_activity, meta_category).
        """
        if not raw:
            return raw, "other"

        cleaned = raw.strip()

        # Strip parenthetical suffixes that LLMs sometimes append
        # e.g. "アイドル(idle)" → "アイドル", "集中作業(focus)" → "集中作業"
        import re

        m = re.match(r"^(.+?)\s*[（(]([a-zA-Z]+)[)）]$", cleaned)
        if m:
            cleaned = m.group(1).strip()
            suffix = m.group(2).lower()
            # Use the suffix as meta hint if it's a valid meta-category
            if suffix in VALID_META_CATEGORIES and (not meta or meta == "other"):
                meta = suffix

        meta = meta.strip().lower() if meta else "other"
        if meta not in VALID_META_CATEGORIES:
            meta = "other"

        normalized = _normalize_str(cleaned)

        # Exact match against cached activities
        for known in self._cache:
            if _normalize_str(known) == normalized:
                self._db.upsert_activity_mapping(known, meta)
                return known, self._cache[known]

        # Fuzzy match — find best candidate
        threshold = 0.7
        best_score = 0.0
        best_match = ""
        for known in self._cache:
            score = _similarity(cleaned, known)
            if score > best_score:
                best_score = score
                best_match = known

        if best_score >= threshold:
            self._db.upsert_activity_mapping(best_match, meta)
            return best_match, self._cache[best_match]

        # New activity — register it
        self._db.upsert_activity_mapping(cleaned, meta)
        self._cache[cleaned] = meta
        log.info("New activity registered: %s [%s]", cleaned, meta)
        return cleaned, meta

    def get_meta_category(self, activity: str) -> str:
        """Get the meta-category for a given activity.

        Uses exact match first, then fuzzy match, returns 'other' as fallback.
        """
        if not activity:
            return "other"

        # Exact match
        if activity in self._cache:
            return self._cache[activity]

        # Normalized exact match
        normalized = _normalize_str(activity)
        for known, meta in self._cache.items():
            if _normalize_str(known) == normalized:
                return meta

        # Fuzzy match
        best_score = 0.0
        best_meta = "other"
        for known, meta in self._cache.items():
            score = _similarity(activity, known)
            if score > best_score:
                best_score = score
                best_meta = meta

        if best_score >= 0.7:
            return best_meta

        return "other"
