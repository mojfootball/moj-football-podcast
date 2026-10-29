"""telegram_post.py - ارسال کاور + عنوان + لینک یوتیوب به کانال تلگرام."""
import os
import time

import requests


def send_video_post(thumb_path, title, video_id):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("تلگرام تنظیم نشده؛ ارسال رد شد.")
        return False

    link = f"https://youtu.be/{video_id}"
    caption = f"{title}\n\n▶️ تماشا در یوتیوب:\n{link}\n\n#موج_فوتبال #تحلیل_فوتبال"
    base = f"https://api.telegram.org/bot{token}"

    for attempt in range(3):
        try:
            if thumb_path and os.path.exists(thumb_path):
                with open(thumb_path, "rb") as f:
                    r = requests.post(
                        f"{base}/sendPhoto",
                        data={"chat_id": chat_id, "caption": caption[:1024]},
                        files={"photo": f},
                        timeout=60,
                    )
            else:
                r = requests.post(
                    f"{base}/sendMessage",
                    data={"chat_id": chat_id, "text": caption},
                    timeout=60,
                )
            if r.status_code == 429:
                wait = r.json().get("parameters", {}).get("retry_after", 10)
                time.sleep(min(int(wait) + 1, 60))
                continue
            if r.ok:
                print("در تلگرام ارسال شد.")
                return True
            print(f"تلگرام خطا داد ({r.status_code}): {r.text[:200]}")
        except requests.RequestException as e:
            print(f"خطای شبکه‌ی تلگرام: {e}")
        time.sleep(5 * (attempt + 1))
    return False
