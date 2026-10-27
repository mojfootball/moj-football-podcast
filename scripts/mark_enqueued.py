"""mark_enqueued.py - بازی‌های وارد‌شده به صف رو به processed_matches.json اضافه می‌کنه."""
import os
import json
import subprocess

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "processed_matches.json")

out = subprocess.run(["gh", "release", "list", "--limit", "200", "--json", "tagName"],
                     check=True, capture_output=True, text=True).stdout
queued = {int(r["tagName"][2:]) for r in json.loads(out)
          if r["tagName"].startswith("q-") and r["tagName"][2:].isdigit()}

try:
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        ids = set(json.load(f))
except (FileNotFoundError, json.JSONDecodeError):
    ids = set()

ids |= queued
with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(sorted(ids), f, ensure_ascii=False, indent=2)
print(f"{len(queued)} بازی ثبت شد.")
