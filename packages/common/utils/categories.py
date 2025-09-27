from __future__ import annotations

import re
from collections import Counter
from typing import Iterable, Sequence

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "electronics": {
        "laptop",
        "phone",
        "tablet",
        "earbuds",
        "headphones",
        "charger",
        "macbook",
        "iphone",
        "android",
        "airpods",
    },
    "accessories": {
        "wallet",
        "purse",
        "bag",
        "backpack",
        "belt",
        "watch",
        "bracelet",
    },
    "id_cards": {"id", "badge", "card", "license"},
    "keys": {"key", "keychain", "fob"},
    "water_bottle": {"bottle", "hydro", "flask", "water", "hydroflask"},
    "clothing": {
        "jacket",
        "coat",
        "hoodie",
        "shirt",
        "sweater",
        "scarf",
        "glove",
        "hat",
    },
    "other": set(),
}

_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _tokenize(text: str) -> list[str]:
    return [token for token in _TOKEN_RE.findall(text.lower()) if token]


def infer_category(*sources: Sequence[str] | None, tags: Iterable[str] | None = None) -> str:
    counter: Counter[str] = Counter()
    for source in sources:
        if not source:
            continue
        for token in _tokenize(" ".join(source) if isinstance(source, (list, tuple)) else str(source)):
            for category, keywords in CATEGORY_KEYWORDS.items():
                if keywords and token in keywords:
                    counter[category] += 1
    if tags:
        for tag in tags:
            for token in _tokenize(tag):
                for category, keywords in CATEGORY_KEYWORDS.items():
                    if keywords and token in keywords:
                        counter[category] += 2

    if counter:
        category, _ = counter.most_common(1)[0]
        return category
    return "other"
