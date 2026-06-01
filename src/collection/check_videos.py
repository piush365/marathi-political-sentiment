import os
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("YOUTUBE_API_KEY not found in .env file")

youtube = build("youtube", "v3", developerKey=API_KEY)

QUOTA_USED = 0

VIDEO_IDS = [
    "GeSQvsYaOAM", "Ipjcb19EPmg", "ajpkpKme3kY", "4vIsDw444Tk",
    "aR8R-7PDb3w", "E_ej1Dm-BkQ", "TtdShwa6LC8", "QcTu2eFYhFs",
    "hw2S1oC6qrc", "HUF39iijLK0", "8vrPpbmu4Cs", "Fu9U0hMusU8",
    "14pV8uDeDdo", "M3DDplBfrOY", "n6sI2gYyTqk", "71-f89vFzMA",
    "SKSMzAcTpTY", "foz4yNi2YR4", "Vvq86HM6-ZI", "eUSKnw5qqwE"
]


def check_videos(video_ids: list[str]) -> tuple[list[dict], list[str]]:
    """
    Fetch title, comment count, and status for a list of video IDs.
    Batches 50 IDs per request — 1 quota unit per batch.
    20 videos = 1 API call total.

    Returns:
        found   : list of video metadata dicts
        missing : list of IDs that were deleted/private/not found
    """
    global QUOTA_USED
    found = []
    missing = []

    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        batch_ids_set = set(batch)

        try:
            response = youtube.videos().list(
                part="snippet,statistics",   # dropped liveStreamingDetails — use snippet instead
                id=",".join(batch)
            ).execute()
            QUOTA_USED += 1

            returned_ids = set()
            for item in response["items"]:
                vid_id = item["id"]
                returned_ids.add(vid_id)
                snippet = item["snippet"]
                stats = item.get("statistics", {})

                # liveBroadcastContent: "live" | "upcoming" | "none"
                live_status = snippet.get("liveBroadcastContent", "none")
                is_live = live_status in ("live", "upcoming")

                # differentiate disabled comments vs zero comments
                if "commentCount" not in stats:
                    comment_count = None   # None = comments disabled
                else:
                    comment_count = int(stats["commentCount"])

                found.append({
                    "video_id": vid_id,
                    "title": snippet["title"],
                    "channel": snippet["channelTitle"],
                    "comment_count": comment_count,
                    "is_live": is_live,
                    "live_status": live_status,
                    "published_at": snippet["publishedAt"],
                })

            # anything in batch not returned = deleted/private
            missing.extend(batch_ids_set - returned_ids)

        except HttpError as e:
            print(f"[error] HTTP {e.resp.status}: {e}")

    return found, missing


if __name__ == "__main__":
    print(f"Checking {len(VIDEO_IDS)} videos...\n")
    videos, missing = check_videos(VIDEO_IDS)

    # sort: comments disabled last, then by count descending
    videos.sort(
        key=lambda x: x["comment_count"] if x["comment_count"] is not None else -1,
        reverse=True
    )

    print(f"{'ID':<15} {'COMMENTS':>9} {'STATUS':<10}  TITLE")
    print("-" * 100)
    for v in videos:
        count_str = str(v["comment_count"]) if v["comment_count"] is not None else "DISABLED"
        status = "🔴 LIVE" if v["is_live"] else "ok"
        print(f"{v['video_id']:<15} {count_str:>9} {status:<10}  {v['title'][:70]}")

    if missing:
        print(f"\n[warn] {len(missing)} video(s) not found (deleted/private): {missing}")

    print(f"\nTotal quota used: {QUOTA_USED} unit(s)")