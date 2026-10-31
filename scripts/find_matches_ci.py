"""find_matches_ci.py - بازی‌های دیروز رو پیدا می‌کنه و برای matrix گیت‌هاب خروجی می‌ده.
بازی‌هایی که الان تو صف آپلود هستن (Release های q-*) دوباره ساخته نمی‌شن."""
import os
import json
import subprocess

from find_finished_matches import find_finished_matches


def queued_ids():
    try:
        out = subprocess.run(
            ["gh", "release", "list", "--limit", "200", "--json", "tagName"],
            check=True, capture_output=True, text=True,
        ).stdout
        return {int(r["tagName"][2:]) for r in json.loads(out)
                if r["tagName"].startswith("q-") and r["tagName"][2:].isdigit()}
    except Exception as e:  # noqa: BLE001
        print("خوندن صف ناموفق (ادامه بدون فیلتر):", e)
        return set()


queued = queued_ids()
matches = [m for m in find_finished_matches() if m["id"] not in queued]
matrix = [{"id": m["id"], "order": i} for i, m in enumerate(matches)]

for m in matches:
    print(f"- {m['home']} {m['score']} {m['away']} ({m['league']}) id={m['id']}")
if queued:
    print(f"{len(queued)} بازی از قبل تو صف هست و دوباره ساخته نمی‌شه.")
print(f"{len(matrix)} بازی انتخاب شد.")

out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a", encoding="utf-8") as f:
        f.write("matches=" + json.dumps(matrix, separators=(",", ":")) + "\n")
        f.write(f"count={len(matrix)}\n")
