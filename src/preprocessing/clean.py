from __future__ import annotations

import os
import re
import csv
from collections import Counter
from langdetect import detect, LangDetectException, DetectorFactory

# fix langdetect randomness — critical for research reproducibility
DetectorFactory.seed = 0

# ── paths ─────────────────────────────────────────────────────────────────────
RAW_PATH       = "data/raw/comments.csv"
PROCESSED_PATH = "data/processed/comments_clean.csv"

# ── thresholds ────────────────────────────────────────────────────────────────
MIN_WORDS            = 3    # below this = too short to carry sentiment
MAX_WORDS            = 150  # above this = rare, usually copy-paste spam
MIN_DEVANAGARI_RATIO = 0.4  # at least 40% of chars must be Devanagari
LANGDETECT_MIN_WORDS = 6    # only run langdetect if comment has 6+ words


# ── helpers ───────────────────────────────────────────────────────────────────

def devanagari_ratio(text: str) -> float:
    """Fraction of characters that are Devanagari script (U+0900–U+097F)."""
    if not text:
        return 0.0
    deva_chars = sum(1 for c in text if '\u0900' <= c <= '\u097f')
    return deva_chars / len(text)


def clean_text(text: str) -> str:
    """
    Clean raw comment text.
    Order matters: URLs first, then mentions/hashtags, then whitespace.
    """
    text = re.sub(r'http\S+|www\S+', '', text)  # remove URLs
    text = re.sub(r'@\w+', '', text)             # remove mentions
    text = re.sub(r'#\w+', '', text)             # remove hashtags
    text = re.sub(r'\s+', ' ', text)             # normalize whitespace
    return text.strip()


def is_marathi(text: str) -> bool:
    """
    Detect if text is Marathi ('mr').
    Only called when word count >= LANGDETECT_MIN_WORDS — unreliable on short text.
    Seeded via DetectorFactory.seed = 0 for reproducibility.
    """
    try:
        return detect(text) == "mr"
    except LangDetectException:
        return False


def filter_comment(text: str) -> tuple[bool, str]:
    """
    Run all filters in order: cheap → expensive.
    Returns (passed, reason) where reason='ok' if passed.

    Order:
      1. Length check     — O(n) word split, cheapest
      2. Devanagari ratio — O(n) char scan, cheap
      3. Language detect  — external lib, expensive — runs last
    """
    word_count = len(text.split())

    # 1. length
    if word_count < MIN_WORDS:
        return False, "too_short"
    if word_count > MAX_WORDS:
        return False, "too_long"

    # 2. script
    if devanagari_ratio(text) < MIN_DEVANAGARI_RATIO:
        return False, "low_devanagari"

    # 3. language — only run on longer text where langdetect is reliable
    if word_count >= LANGDETECT_MIN_WORDS and not is_marathi(text):
        return False, "not_marathi"

    return True, "ok"


# ── main pipeline ─────────────────────────────────────────────────────────────

def run(raw_path: str = RAW_PATH, processed_path: str = PROCESSED_PATH):
    # load
    with open(raw_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded       : {len(rows)} raw comments")

    # deduplicate — comment_id first (exact same comment),
    # then text (same content posted by different users)
    seen_ids:   set[str] = set()
    seen_texts: set[str] = set()
    deduped = []
    for row in rows:
        if row["comment_id"] in seen_ids or row["text"] in seen_texts:
            continue
        seen_ids.add(row["comment_id"])
        seen_texts.add(row["text"])
        deduped.append(row)

    print(f"After dedup  : {len(deduped)} comments ({len(rows) - len(deduped)} removed)")

    # clean + filter
    passed = []
    drop_reasons: Counter = Counter()

    for row in deduped:
        cleaned = clean_text(row["text"])
        ok, reason = filter_comment(cleaned)

        if ok:
            row["text"] = cleaned
            passed.append(row)
        else:
            drop_reasons[reason] += 1

    # save
    os.makedirs(os.path.dirname(processed_path), exist_ok=True)
    if passed:
        fieldnames = list(passed[0].keys())
        with open(processed_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(passed)

    # report
    total_dropped = len(deduped) - len(passed)
    survival_rate = len(passed) / len(rows) * 100

    print(f"\n── Results ──────────────────────────────")
    print(f"Passed filters : {len(passed)}")
    print(f"Dropped        : {total_dropped}")
    print(f"Survival rate  : {survival_rate:.1f}%")
    print(f"\nDrop reasons:")
    for reason, count in drop_reasons.most_common():
        pct = count / len(deduped) * 100
        print(f"  {reason:<20} {count:>4}  ({pct:.1f}%)")
    print(f"\nSaved → {processed_path}")


if __name__ == "__main__":
    run()