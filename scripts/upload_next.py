"""upload_next.py - یک ویدیو از صف (Release های q-*) رو در یوتیوب آپلود می‌کنه."""
import os
import json
import subprocess

from googleapiclient.errors import HttpError

from youtube_uploader import get_service, upload_video, set_thumbnail

STOP_REASONS = ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded")
WORK = "queue_tmp"


def gh(*args):
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True).stdout


def list_queue():
    out = gh("release", "list", "--limit", "200", "--json", "tagName")
    return [r["tagName"] for r in json.loads(out) if r["tagName"].startswith("q-")]


def read_meta(tag):
    d = os.path.join(WORK, tag)
    os.makedirs(d, exist_ok=True)
    gh("release", "download", tag, "--pattern", "youtube.json", "--dir", d, "--clobber")
    with open(os.path.join(d, "youtube.json"), encoding="utf-8") as f:
        return json.load(f)


def main():
    tags = list_queue()
    if not tags:
        print("صف خالیه؛ چیزی برای آپلود نیست.")
        return
    print(f"{len(tags)} ویدیو تو صف هست.")

    candidates = []
    for tag in tags:
        try:
            meta = read_meta(tag)
            candidates.append((meta.get("sort_key", tag), tag, meta))
        except Exception as e:  # noqa: BLE001
            print(f"خوندن {tag} ناموفق: {e}")
    candidates.sort(key=lambda x: x[0])

    yt = get_service()
    for _, tag, meta in candidates:
        d = os.path.join(WORK, tag)
        print(f"\n▶ {tag}: {meta['title']}")
        try:
            gh("release", "download", tag, "--dir", d, "--clobber")
            video = os.path.join(d, "final.mp4")
            thumb = os.path.join(d, "thumbnail.jpg")
            vid = upload_video(yt, video, meta)
        except HttpError as e:
            content = e.content.decode("utf-8", "ignore") if getattr(e, "content", None) else ""
            print(f"آپلود ناموفق: {e}")
            if any(r in content or r in str(e) for r in STOP_REASONS):
                print("سقف روزانه‌ی یوتیوب پر شد؛ دفعه‌ی بعد ادامه می‌دیم.")
                return
            continue
        except Exception as e:  # noqa: BLE001
            print(f"آپلود ناموفق: {e}")
            continue

        print(f"آپلود شد: https://youtu.be/{vid}")
        if os.path.exists(thumb):
            try:
                set_thumbnail(yt, vid, thumb)
                print("کاور تنظیم شد.")
            except Exception as e:  # noqa: BLE001
                print(f"کاور تنظیم نشد (ویدیو آپلود شده): {e}")
        gh("release", "delete", tag, "--cleanup-tag", "--yes")
        print("از صف حذف شد.")
        return  # فقط یک ویدیو در هر اجرا


if __name__ == "__main__":
    main()
