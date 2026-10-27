"""build_one.py <match_id> <order> - ساخت ویدیو + کاور + عنوان/توضیحات یک بازی."""
import os
import sys
import json
import datetime as dt

from fetch_match_details import get_match_details
from generate_analysis import summarize_match, generate_persian_script
from generate_audio import synthesize_dialogue, build_scene_timeline
from build_video import build_video
from youtube_meta import build_metadata


def dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def main(match_id, order):
    out_dir = os.path.join("output", str(match_id))
    os.makedirs(out_dir, exist_ok=True)

    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)
    dump(os.path.join(out_dir, "summary.json"), summary)
    dump(os.path.join(out_dir, "dialogue.json"), turns)

    audio_path = os.path.join(out_dir, "episode.wav")
    total_seconds = synthesize_dialogue(turns, audio_path)
    timeline = build_scene_timeline(turns, total_seconds)
    dump(os.path.join(out_dir, "timing.json"), timeline)

    build_video(summary, timeline, audio_path, out_dir)

    for name in ("final.mp4", "thumbnail.jpg"):
        if not os.path.exists(os.path.join(out_dir, name)):
            raise RuntimeError(f"{name} ساخته نشد؛ بازی {match_id} وارد صف نمی‌شه.")

    meta = build_metadata(summary, details)
    meta["match_id"] = match_id
    meta["order"] = order
    # ترتیب صف: اول روز ساخت، بعد اولویت بازی
    meta["sort_key"] = f"{dt.datetime.now(dt.timezone.utc):%Y-%m-%d}-{int(order):02d}"
    dump(os.path.join(out_dir, "youtube.json"), meta)
    print("عنوان:", meta["title"])


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]) if len(sys.argv) > 2 else 0)
