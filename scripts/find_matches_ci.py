"""find_matches_ci.py - بازی‌های امروز رو پیدا می‌کنه و برای matrix گیت‌هاب خروجی می‌ده."""
import os
import json

from find_finished_matches import find_finished_matches

matches = find_finished_matches()
matrix = [{"id": m["id"], "order": i} for i, m in enumerate(matches)]

for m in matches:
    print(f"- {m['home']} {m['score']} {m['away']} ({m['league']}) id={m['id']}")
print(f"{len(matrix)} بازی انتخاب شد.")

out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a", encoding="utf-8") as f:
        f.write("matches=" + json.dumps(matrix, separators=(",", ":")) + "\n")
        f.write(f"count={len(matrix)}\n")
