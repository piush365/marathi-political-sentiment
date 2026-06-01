from __future__ import annotations

import os
import csv
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in .env file")

youtube = build("youtube", "v3", developerKey=API_KEY)

QUOTA_USED = 0

# verified video IDs — political Marathi content, >300 comments
VIDEO_IDS = [
    "Vvq86HM6-ZI",  # 2066 - Fadnavis vs Thackeray debate
    "71-f89vFzMA",  # 1813 - Uddhav assembly speech
    "GeSQvsYaOAM",  # 1091 - Raj Thackeray speech
    "Ipjcb19EPmg",  # 1010 - Maharashtra politics analysis
    "ajpkpKme3kY",  #  888 - Sharad Pawar political journey
    "SKSMzAcTpTY",  #  587 - Fadnavis controversy
    "8vrPpbmu4Cs",  #  507 - MVA vs Mahayuti
    "Fu9U0hMusU8",  #  504 - MVA vs Mahayuti Marathwada
    "HUF39iijLK0",  #  428 - Maratha reservation
    "hw2S1oC6qrc",  #  412 - Maratha reservation special report
    "eUSKnw5qqwE",  #  394 - Raj Thackeray on Fadnavis
    "aR8R-7PDb3w",  #  383 - MNS in Maharashtra politics
]


def load_existing_ids(filepath: str) -> set[str]:
    """
    Load already-scraped comment IDs from existing CSV.
    Prevents duplicates if script is re-run.
    Returns empty set if file doesn't exist.
    """
    if not os.path.isfile(filepath):
        return set()

    existing = set()
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add(row["comment_id"])

    print(f"[info] Loaded {len(existing)} existing comment IDs from {filepath}")
    return existing


def get_comments(
    video_id: str,
    max_comments: int = 200,
    existing_ids: set[str] | None = None
) -> list[dict]:
    """
    Fetch top-level comments from a single video.
    Skips comments already in existing_ids.
    Always requests 100 per call (API max) to minimize quota usage.
    Cost: ceil(max_comments / 100) units per video.
    """
    global QUOTA_USED
    if existing_ids is None:
        existing_ids = set()

    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=next_page_token,
                textFormat="plainText",
                order="relevance"
            )
            response = request.execute()
            QUOTA_USED += 1

            items = response.get("items", [])
            if not items:
                break  # empty page — stop immediately, don't loop

            for item in items:
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comment_id = item["snippet"]["topLevelComment"]["id"]

                if comment_id in existing_ids:
                    continue  # skip already scraped

                comments.append({
                    "video_id": video_id,
                    "comment_id": comment_id,
                    "text": snippet["textDisplay"],
                    "likes": snippet["likeCount"],
                    "published_at": snippet["publishedAt"],
                    "scraped_at": datetime.now(timezone.utc).isoformat()
                })

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

    except HttpError as e:
        if e.resp.status == 403:
            print(f"  [skip] Comments disabled or quota exceeded: {video_id}")
        elif e.resp.status == 404:
            print(f"  [skip] Video not found: {video_id}")
        else:
            print(f"  [error] HTTP {e.resp.status} for {video_id}: {e}")

    return comments[:max_comments]


def save_to_csv(comments: list[dict], filepath: str):
    """
    Append comments to CSV.
    Writes header only if file is new.
    """
    if not comments:
        print("  [warn] No comments to save.")
        return

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.isfile(filepath)
    fieldnames = list(comments[0].keys())

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(comments)


def scrape_all(
    video_ids: list[str],
    max_per_video: int = 200,
    output_path: str = "data/raw/comments.csv"
):
    """
    Scrape comments from all videos into a single CSV.
    Skips already-scraped comments — safe to re-run.
    """
    existing_ids = load_existing_ids(output_path)
    total_saved = 0

    for idx, vid_id in enumerate(video_ids, 1):
        print(f"[{idx}/{len(video_ids)}] Scraping {vid_id}...")
        comments = get_comments(vid_id, max_comments=max_per_video, existing_ids=existing_ids)

        if comments:
            save_to_csv(comments, output_path)
            # update existing_ids so mid-run dupes are caught too
            existing_ids.update(c["comment_id"] for c in comments)
            total_saved += len(comments)
            print(f"  Fetched: {len(comments)} | Total saved: {total_saved} | Quota used: {QUOTA_USED}")
        else:
            print(f"  [skip] No new comments for {vid_id}")

    print(f"\nDone. {total_saved} new comments saved to {output_path}")
    print(f"Total quota used: {QUOTA_USED} units")


if __name__ == "__main__":
    # pass --test to scrape just the first video (for quick checks)
    if "--test" in sys.argv:
        scrape_all(
            video_ids=VIDEO_IDS[:1],
            max_per_video=50,
            output_path="data/raw/comments.csv"
        )
    else:
        scrape_all(
            video_ids=VIDEO_IDS,
            max_per_video=200,
            output_path="data/raw/comments.csv"
        )