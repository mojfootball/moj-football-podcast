import os
import json
import subprocess

from scene_builder import build_scenes
from record_video import record

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "video_template.html")


def render_page(scenes, out_path):
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__SCENES_JSON__", json.dumps(scenes, ensure_ascii=False))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)


def build_video(summary, timeline, audio_path, out_dir):
    scenes = build_scenes(summary, timeline)
    total_seconds = timeline[-1]["end"]

    with open(os.path.join(out_dir, "scenes.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    page_path = os.path.join(out_dir, "page.html")
    render_page(scenes, page_path)

    print(f"در حال ضبط ویدیو ({total_seconds:.1f} ثانیه)...")
    raw_video_dir = os.path.join(out_dir, "video_raw")
    video_path = record(os.path.abspath(page_path), total_seconds, raw_video_dir)
    print(f"ضبط خام تموم شد: {video_path}")

    final_path = os.path.join(out_dir, "final.mp4")
    print("در حال چسبوندن صدا با ffmpeg...")
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        "-shortest",
        final_path,
    ], check=True)

    print(f"ویدیوی نهایی ساخته شد: {final_path}")
    return final_path


if __name__ == "__main__":
    import sys
    from fetch_match_details import get_match_details
    from generate_analysis import summarize_match, generate_persian_script
    from generate_audio import synthesize_dialogue, build_scene_timeline

    match_id = int(sys.argv[1])
    out_dir = f"output/{match_id}"
    os.makedirs(out_dir, exist_ok=True)

    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)

    audio_path = os.path.join(out_dir, "episode.wav")
    total_seconds = synthesize_dialogue(turns, audio_path)
    timeline = build_scene_timeline(turns, total_seconds)

    build_video(summary, timeline, audio_path, out_dir)
