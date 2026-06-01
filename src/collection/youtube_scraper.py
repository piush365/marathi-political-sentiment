from __future__ import annotations

import os
import csv
from datetime import datetime, timezone
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in .env file")

youtube = build("youtube", "v3", developerKey=API_KEY)

# quota tracking — each commentThreads.list call = 1 unit
QUOTA_USED = 0


def get_comments(video_id: str, max_comments: int = 100) -> list[dict]:
    """
    Fetch top-level comments from a YouTube video.
    Always fetches 100 per request (max allowed) to minimize API calls.
    Returns a list of dicts with comment metadata.
    """
    global QUOTA_USED
    comments = []
    next_page_token = None

    try:
        while len(comments) < max_comments:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,          # always max — don't waste a call on fewer
                pageToken=next_page_token,
                textFormat="plainText",
                order="relevance"        # top comments first = better quality data
            )
            response = request.execute()
            QUOTA_USED += 1
            print(f"  [quota] API calls used this session: {QUOTA_USED}")

            for item in response["items"]:
                snippet = item["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "video_id": video_id,
                    "comment_id": item["snippet"]["topLevelComment"]["id"],
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
            print(f"[error] Comments disabled or quota exceeded for video: {video_id}")
        elif e.resp.status == 404:
            print(f"[error] Video not found: {video_id}")
        else:
            print(f"[error] HTTP {e.resp.status} for video {video_id}: {e}")
        return comments  # return whatever we got before the error

    # slice to exact requested amount
    return comments[:max_comments]


def save_to_csv(comments: list[dict], filepath: str):
    """
    Save comments to CSV.
    Appends if file exists (so multiple video runs don't overwrite each other).
    Writes header only if file is new.
    """
    if not comments:
        print("[warn] No comments to save.")
        return

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    file_exists = os.path.isfile(filepath)
    fieldnames = list(comments[0].keys())

    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(comments)

    print(f"[saved] {len(comments)} comments → {filepath}")


if __name__ == "__main__":
    TEST_VIDEO_ID = "JV05-3hknYk"  # ABP Majha — Maharashtra Vidhan Sabha 2024

    print(f"Fetching comments for video: {TEST_VIDEO_ID}")
    comments = get_comments(TEST_VIDEO_ID, max_comments=50)
    print(f"Fetched: {len(comments)} comments")

    if comments:
        print("\nSample comment:")
        print(comments[0]["text"])

    save_to_csv(comments, "data/raw/test_comments.csv")
    print(f"\nTotal quota used this session: {QUOTA_USED} units")