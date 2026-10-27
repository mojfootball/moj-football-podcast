"""upload_next.py - یک ویدیو از صف (Release های q-*) رو در یوتیوب آپلود می‌کنه.
ترتیب: روز جدیدتر اول، داخل هر روز اولویت تیم‌ها. ویدیوهای قدیمی از صف حذف می‌شن."""
import os
import json
import subprocess
import datetime as dt

from googleapiclient.errors import HttpError

from youtube_uploader import get_service, upload_video, set_thumbnail

STOP_REASONS = ("quotaExceeded", "uploadLimitExceeded", "rateLimitExceeded")
WORK = "queue_tmp"
MAX_AGE_DAYS = int(os.environ.get("MAX_QUEUE_AGE_DAYS", "1"))


def today():
    return dt.datetime.now(dt.timezone.utc).date()


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


def parse_key(key):
    """sort_key به شکل YYYY-MM-DD-NN؛ اگه خراب بود، امروز و آخر صف حساب می‌شه."""
    try:
        return dt.date.fromisoformat(key[:10]), int(key[11:])
    except Exception:  # noqa: BLE001
        return today(), 999


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
        except Exception as e:  # noqa: BLE001
            print(f"خوندن {tag} ناموفق: {e}")
            continue
        day, order = parse_key(meta.get("sort_key", ""))
        if (today() - day).days > MAX_AGE_DAYS:
            print(f"{tag} قدیمی شده ({day})؛ از صف حذف شد.")
            try:
                gh("release", "delete", tag, "--cleanup-tag", "--yes")
            except Exception as e:  # noqa: BLE001
                print(f"حذف {tag} ناموفق: {e}")
            continue
        candidates.append((day, order, tag, meta))

    if not candidates:
        print("ویدیوی تازه‌ای تو صف نیست.")
        return

    # روز جدیدتر اول، بعد اولویت بازی
    candidates.sort(key=lambda x: (-x[0].toordinal(), x[1]))

    yt = get_service()
    for day, order, tag, meta in candidates:
        d = os.path.join(WORK, tag)
        print(f"\n▶ {tag} ({day}): {meta['title']}")
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
