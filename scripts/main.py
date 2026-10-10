import json
import os

from find_finished_matches import find_finished_matches, STATE_FILE, load_processed_ids
from fetch_match_details import get_match_details
from generate_analysis import summarize_match, generate_persian_script
from generate_audio import synthesize_dialogue, build_scene_timeline


def save_processed_id(match_id):
    ids = load_processed_ids()
    ids.add(match_id)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, ensure_ascii=False, indent=2)


def process_match(match):
    match_id = match["id"]
    print(f"\n=== پردازش بازی {match['home']} {match['score']} {match['away']} ===")

    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)

    out_dir = os.path.join("output", str(match_id))
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    with open(os.path.join(out_dir, "dialogue.json"), "w", encoding="utf-8") as f:
        json.dump(turns, f, ensure_ascii=False, indent=2)

    total_seconds = synthesize_dialogue(turns, os.path.join(out_dir, "episode.wav"))
    timeline = build_scene_timeline(turns, total_seconds)

    with open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)

    save_processed_id(match_id)
    print(f"پردازش بازی {match_id} با موفقیت تموم شد.")


if __name__ == "__main__":
    matches = find_finished_matches()
    print(f"{len(matches)} بازی برای پردازش امروز انتخاب شد.\n")

    for m in matches:
        try:
            process_match(m)
        except Exception as e:
            print(f"خطا در پردازش بازی {m['id']}: {e}")
