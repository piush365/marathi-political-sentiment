from __future__ import annotations

import os
import csv
import sys

PROCESSED_PATH = "data/processed/comments_clean.csv"
LABELED_PATH   = "data/labeled/comments_labeled.csv"

LABELS = {
    "1": ("positive", "Support / praise / agreement"),
    "0": ("negative", "Criticism / opposition / anger"),
    "2": ("neutral",  "Factual / mixed / unclear"),
    "s": ("skip",     "Skip — too ambiguous to label"),
}


def load_labeled_ids(filepath: str) -> set[str]:
    """Load already-labeled comment IDs so we can resume interrupted sessions."""
    if not os.path.isfile(filepath):
        return set()
    with open(filepath, encoding="utf-8") as f:
        return {row["comment_id"] for row in csv.DictReader(f)}


def save_label(row: dict, label: str, filepath: str):
    """Append a single labeled comment to CSV."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.isfile(filepath)

    fieldnames = ["comment_id", "video_id", "text", "likes", "label"]
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "comment_id": row["comment_id"],
            "video_id":   row["video_id"],
            "text":       row["text"],
            "likes":      row["likes"],
            "label":      label,
        })


def run(target: int = 200):
    """
    Interactive labeling session.
    Labels are saved immediately after each input — no data loss on crash.
    Press Ctrl+C anytime to exit, progress is saved.
    """
    # load data
    with open(PROCESSED_PATH, encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))

    # resume — skip already labeled
    labeled_ids = load_labeled_ids(LABELED_PATH)
    remaining = [r for r in all_rows if r["comment_id"] not in labeled_ids]

    already_done = len(labeled_ids)
    target_left  = max(0, target - already_done)

    if target_left == 0:
        print(f"Target of {target} labels already reached.")
        return

    to_label = remaining[:target_left]

    print(f"\n── Marathi Political Sentiment Labeler ──────────────────")
    print(f"Already labeled : {already_done}")
    print(f"Target          : {target}")
    print(f"This session    : {len(to_label)} comments to go")
    print(f"\nControls:")
    for key, (name, desc) in LABELS.items():
        print(f"  [{key}] {name:<10} — {desc}")
    print(f"  [q]  quit       — save and exit")
    print(f"─────────────────────────────────────────────────────────\n")

    session_count = 0
    try:
        for idx, row in enumerate(to_label, 1):
            # progress header
            total_done = already_done + session_count
            print(f"[{total_done + 1}/{target}] video: {row['video_id']} | likes: {row['likes']}")
            print(f"\n  {row['text']}\n")

            # get valid input
            while True:
                key = input("  Label (0/1/2/s/q): ").strip().lower()
                if key == "q":
                    raise KeyboardInterrupt
                if key in LABELS:
                    break
                print("  Invalid. Use 0, 1, 2, s, or q.")

            label_name = LABELS[key][0]
            if label_name != "skip":
                save_label(row, label_name, LABELED_PATH)
                session_count += 1
            else:
                print("  Skipped.")

            print()  # breathing room between comments

    except KeyboardInterrupt:
        pass

    # session summary
    total_labeled = already_done + session_count
    print(f"\n── Session Summary ──────────────────────────────────────")
    print(f"Labeled this session : {session_count}")
    print(f"Total labeled so far : {total_labeled} / {target}")
    print(f"Saved → {LABELED_PATH}")
    if total_labeled < target:
        print(f"Run again to continue — progress is saved.")


if __name__ == "__main__":
    # optional: pass target as arg, e.g. python label_tool.py 50
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run(target=target)