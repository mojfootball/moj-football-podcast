import sys
import json

from fetch_match_details import get_match_details
from generate_analysis import summarize_match, generate_persian_script
from generate_audio import build_scene_timeline
from scene_builder import build_scenes

match_id = int(sys.argv[1])

details = get_match_details(match_id)
summary = summarize_match(details)
turns = generate_persian_script(summary)

total_words = sum(len(t["text"].split()) for t in turns)
total_seconds = total_words / 2.6

timeline = build_scene_timeline(turns, total_seconds)
scenes = build_scenes(summary, timeline)

print(f"\n{len(scenes)} صحنه ساخته شد:\n")
print(json.dumps(scenes, ensure_ascii=False, indent=2))
