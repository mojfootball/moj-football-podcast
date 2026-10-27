"""youtube_uploader.py - آپلود ویدیو و تنظیم کاور در یوتیوب."""
import os
import time
import random

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
MAX_THUMB_BYTES = 2_000_000


def get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"].strip(),
        token_uri=TOKEN_URI,
        client_id=os.environ["YT_CLIENT_ID"].strip(),
        client_secret=os.environ["YT_CLIENT_SECRET"].strip(),
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(yt, video_path, meta, publish_at_iso=None):
    """اگه publish_at_iso نده، ویدیو همون لحظه عمومی منتشر می‌شه."""
    status = {"selfDeclaredMadeForKids": False}
    if publish_at_iso:
        status["privacyStatus"] = "private"
        status["publishAt"] = publish_at_iso
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": meta["title"],
            "description": meta["description"],
            "tags": meta.get("tags") or [],
            "categoryId": "17",  # Sports
            "defaultLanguage": "fa",
            "defaultAudioLanguage": "fa",
        },
        "status": status,
    }
    media = MediaFileUpload(video_path, mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response, retries = None, 0
    while response is None:
        try:
            _, response = req.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and retries < 8:
                retries += 1
                time.sleep(min(60, 2 ** retries) + random.random())
                continue
            raise
        except OSError as e:
            if retries >= 8:
                raise
            retries += 1
            print(f"خطای شبکه ({e}); تلاش مجدد {retries}")
            time.sleep(min(60, 2 ** retries) + random.random())
    return response["id"]


def _prepare_thumb(path):
    if os.path.getsize(path) <= MAX_THUMB_BYTES:
        return path
    from PIL import Image
    out = path.rsplit(".", 1)[0] + "_small.jpg"
    img = Image.open(path).convert("RGB")
    for q in (85, 75, 65, 55):
        img.save(out, quality=q, optimize=True)
        if os.path.getsize(out) <= MAX_THUMB_BYTES:
            break
    return out


def set_thumbnail(yt, video_id, thumb_path):
    path = _prepare_thumb(thumb_path)
    yt.thumbnails().set(
        videoId=video_id,
        media_body=MediaFileUpload(path, mimetype="image/jpeg"),
    ).execute()
