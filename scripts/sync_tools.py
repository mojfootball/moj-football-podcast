"""
sync_tools.py

۱) ترجمه‌ی تیتر خبرها به فارسی
۲) زمان‌بندی دقیق از روی خود فایل صوتی (faster-whisper)
۳) انتخاب تصویر برای هر جمله بر اساس موضوع همون جمله
اگه هماهنگی قابل اعتماد نباشه، خطا می‌ده و ویدیو ساخته نمی‌شه.
"""
import os
import re
import json
import time
import wave
import difflib

import requests

MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]
API = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

LEAD = 0.15
MIN_SEG = 2.0
MIN_COVERAGE = 0.55
MAX_GAP = 18.0


# ---------------------------------------------------------------- Gemini
def _gemini_json(prompt, validate=None, temperature=0.2, attempts=3):
    key = os.environ["GEMINI_API_KEY"].strip()
    last = None
    for attempt in range(attempts):
        for model in MODELS:
            try:
                r = requests.post(
                    API.format(model) + "?key=" + key,
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "response_mime_type": "application/json",
                            "temperature": temperature,
                        },
                    },
                    timeout=120,
                )
                r.raise_for_status()
                raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(raw)
                return validate(data) if validate else data
            except Exception as e:  # noqa: BLE001
                last = e
                print(f"Gemini ({model}) تلاش {attempt + 1} ناموفق: {e}")
        time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Gemini جواب معتبر نداد: {last}")


def _as_list(data):
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return data


# ---------------------------------------------------------------- ترجمه‌ی تیتر خبرها
def prepare_summary(summary):
    items = summary.get("news_headlines") or []
    titles = [(n.get("title") or "") for n in items]
    if not any(titles):
        return summary

    def validate(data):
        data = _as_list(data)
        if not isinstance(data, list) or len(data) != len(titles) or not all(isinstance(x, str) for x in data):
            raise ValueError("تعداد ترجمه‌ها با تعداد تیترها نمی‌خونه")
        return data

    prompt = (
        "Translate each football news headline below into natural, fluent Persian (Farsi), "
        "as a Persian sports site would write it. Write all player, team and coach names in Persian script. "
        "Keep it concise. Return ONLY a JSON array of strings, same length and same order as the input. "
        "If an item is an empty string, return an empty string.\n\n"
        + json.dumps(titles, ensure_ascii=False)
    )
    fa_titles = _gemini_json(prompt, validate=validate)
    new = dict(summary)
    new["news_headlines"] = [{**n, "title": t} for n, t in zip(items, fa_titles)]
    print("تیترهای خبری به فارسی ترجمه شد.")
    return new


# ---------------------------------------------------------------- نرمال‌سازی و جمله‌بندی
_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_DIAC = re.compile("[\u064B-\u065F\u0670\u0640]")
_SPLIT = re.compile(r"(?<=[.!?؟…])\s+")


def norm_word(w):
    w = str(w).translate(_DIG)
    for a, b in (("ك", "ک"), ("ي", "ی"), ("ى", "ی"), ("ۀ", "ه"), ("ة", "ه"),
                 ("أ", "ا"), ("إ", "ا"), ("آ", "ا")):
        w = w.replace(a, b)
    w = w.replace("\u200c", "")
    w = _DIAC.sub("", w)
    return re.sub(r"[^\w]", "", w)


def split_sentences(text):
    parts = [p.strip() for p in _SPLIT.split(str(text).strip()) if p.strip()]
    return parts or [str(text).strip()]


def flatten(timeline):
    sents = []
    for b in timeline:
        if "text" not in b:
            raise RuntimeError("timeline متن نداره؛ فایل scripts/generate_audio.py رو با نسخه‌ی جدید جایگزین کن.")
        for s in split_sentences(b["text"]):
            sents.append({"text": s, "speaker": b.get("speaker")})
    if len(sents) < 5:
        raise RuntimeError("تعداد جمله‌ها خیلی کمه.")
    return sents


def _audio_len(path):
    with wave.open(path, "rb") as wf:
        return wf.getnframes() / wf.getframerate()


# ---------------------------------------------------------------- تشخیص گفتار + تطبیق
def transcribe_words(audio_path):
    from faster_whisper import WhisperModel

    name = os.environ.get("WHISPER_MODEL", "medium")
    print(f"بارگذاری مدل تشخیص گفتار ({name})...")
    model = WhisperModel(name, device="cpu", compute_type="int8")
    t0 = time.time()
    segments, _ = model.transcribe(
        audio_path,
        language="fa",
        word_timestamps=True,
        beam_size=1,
        condition_on_previous_text=False,
        vad_filter=False,
    )
    words = []
    for seg in segments:
        for w in seg.words or []:
            n = norm_word(w.word)
            if n:
                words.append((n, float(w.start), float(w.end)))
    print(f"{len(words)} کلمه از روی صدا تشخیص داده شد ({time.time() - t0:.0f} ثانیه)")
    return words


def align_words(script, heard, total):
    b = [h[0] for h in heard]
    sm = difflib.SequenceMatcher(None, script, b, autojunk=False)
    anchors = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and (i2 - i1) == (j2 - j1)):
            for k in range(i2 - i1):
                anchors[i1 + k] = heard[j1 + k][1]

    n = len(script)
    coverage = len(anchors) / n
    print(f"درصد تطبیق متن با صدا: {coverage * 100:.0f}٪")
    if coverage < MIN_COVERAGE:
        raise RuntimeError(f"تطبیق متن با صدا کافی نیست ({coverage * 100:.0f}٪)؛ ویدیو ساخته نشد.")

    pts = [(-1, 0.0)] + sorted(anchors.items()) + [(n, total)]
    clean = [pts[0]]
    for i, t in pts[1:]:
        clean.append((i, max(t, clean[-1][1])))

    for (i0, t0), (i1, t1) in zip(clean, clean[1:]):
        if (t1 - t0) > MAX_GAP and (i1 - i0) > 1:
            raise RuntimeError(
                f"یه بخش {t1 - t0:.0f} ثانیه‌ای بدون تطبیق مطمئن پیدا شد؛ ویدیو ساخته نشد.")

    times = [0.0] * n
    for (i0, t0), (i1, t1) in zip(clean, clean[1:]):
        for k in range(i0 + 1, i1):
            times[k] = t0 + (t1 - t0) * (k - i0) / (i1 - i0)
        if 0 <= i1 < n:
            times[i1] = t1
    return times, coverage


# ---------------------------------------------------------------- انتخاب تصویر برای هر جمله
def build_catalog(summary):
    events = summary.get("events") or []
    goals = [e for e in events if e.get("type") == "Goal"]
    cards = [e for e in events if e.get("type") in ("Red Card", "Substitution")]
    any_cards = [e for e in events if "card" in str(e.get("type", "")).lower()]
    players = ([(p, summary["home_team"]) for p in summary.get("home_top_players") or []]
               + [(p, summary["away_team"]) for p in summary.get("away_top_players") or []])
    c = {
        "title": "Intro: greetings, hosts introducing themselves, introducing the match (opening only)",
        "outro": "Closing: wrap-up and goodbye (ending only)",
        "momentum": "Overall flow of the match on a timeline (when things happened, how the game developed)",
        "compare": "Overall side-by-side comparison of the two teams' stats",
        "shots": "Shot map on the goal: shooting, chances, saves, finishing",
    }
    if (summary.get("table_context") or {}).get("top8"):
        c["table"] = ("League standings table: league position, points, points gap, title race, "
                      "relegation fight, form in the league, who is above/below whom in the table")
    if any_cards:
        c["cards"] = ("List of all yellow and red cards by team with minute and player: bookings, "
                      "discipline, fouls, who was carded and when")
    if summary.get("prematch_prediction"):
        c["prediction"] = "Pre-match prediction/expectations vs the real result"
    for i, e in enumerate(goals):
        c[f"goal:{i}"] = (f"Goal #{i + 1}: minute {e.get('time')} by {e.get('player')} for {e.get('team')} "
                          f"(assist: {e.get('assist')})")
    for i, e in enumerate(cards):
        c[f"card:{i}"] = f"{e.get('type')} minute {e.get('time')} - {e.get('player')} ({e.get('team')})"
    names = {"Possession": "ball possession", "Total passes": "number of passes",
             "Shots on target": "shots on target", "Expected Goals": "xG / quality of chances",
             "Big Chances Created": "big chances created", "Corners": "corners"}
    for k, label in names.items():
        if (summary.get("home_stats") or {}).get(k) is not None:
            c[f"stat:{k}"] = f"Single statistic: {label}"
    for i, (p, team) in enumerate(players):
        c[f"player:{i}"] = f"Player card: {p.get('name')} ({team}) - individual performance"
    for i, n in enumerate(summary.get("news_headlines") or []):
        c[f"news:{i}"] = f"News headline / post-match reaction: {n.get('title')}"
    return c


def annotate(sents, summary):
    catalog = build_catalog(summary)
    payload = [{"i": i, "text": s["text"]} for i, s in enumerate(sents)]

    def validate(data):
        data = _as_list(data)
        if not isinstance(data, list):
            raise ValueError("خروجی آرایه نیست")
        chosen = {}
        for row in data:
            i, sc = row.get("i"), row.get("scene")
            if isinstance(i, int) and 0 <= i < len(sents) and sc in catalog:
                chosen[i] = sc
        missing = len(sents) - len(chosen)
        if missing > max(2, int(len(sents) * 0.1)):
            raise ValueError(f"{missing} جمله بدون برچسب موند")
        out, prev = [], "title"
        for i in range(len(sents)):
            prev = chosen.get(i, prev)
            out.append(prev)
        return out

    prompt = (
        "You are the visual editor of a Persian football analysis video with two hosts. The dialogue is split into "
        "numbered sentences. For EACH sentence choose the ONE visual from the catalog that matches what is being "
        "said in that exact sentence.\n\n"
        "RULES:\n"
        "- Use ONLY ids from the catalog.\n"
        "- The visual must match the topic being spoken. When the hosts discuss a specific goal (by scorer, minute, "
        "assister, or by describing how it happened), use that goal:N for ALL sentences about that goal, including "
        "the discussion of why it happened.\n"
        "- If the catalog has 'table': whenever the hosts talk about the league table, standings, league position, "
        "points, points gap, title race, European places or relegation, use 'table' for ALL those sentences. "
        "NEVER use compare or stat for that topic.\n"
        "- If the catalog has 'cards': whenever the hosts talk about yellow cards, bookings, fouls or discipline "
        "in general, use 'cards'. A specific red card or substitution -> card:N.\n"
        "- A specific statistic -> stat:Key. An individual player's performance -> player:N. "
        "A news item or coach/player quote -> news:N.\n"
        "- General talk about how the game flowed -> momentum. Overall team comparison -> compare. "
        "Shooting, chances, saves -> shots. Pre-match expectations -> prediction.\n"
        "- Keep the same visual for as long as the topic stays the same. Change the visual exactly when the topic "
        "changes. Do not flip visuals every sentence.\n"
        "- 'title' only for the opening intro sentences; 'outro' only for the closing goodbye sentences.\n"
        "- Return ONLY a JSON array covering every sentence: [{\"i\":0,\"scene\":\"title\"}, ...]\n\n"
        "CATALOG:\n" + json.dumps(catalog, ensure_ascii=False, indent=1) + "\n\n"
        "SENTENCES:\n" + json.dumps(payload, ensure_ascii=False)
    )
    ids = _gemini_json(prompt, validate=validate)

    ids[0] = "title"
    ids[-1] = "outro"
    for i in range(1, len(ids)):
        if ids[i] == "title" and ids[i - 1] != "title":
            ids[i] = ids[i - 1]
    last_non = max((i for i, x in enumerate(ids) if x != "outro"), default=-1)
    for i in range(0, last_non + 1):
        if ids[i] == "outro":
            ids[i] = ids[i - 1] if i > 0 else "title"

    for special in ("table", "cards"):
        if special in catalog and special not in ids:
            print(f"توجه: صحنه‌ی «{special}» برای این ویدیو انتخاب نشد (گوینده‌ها درباره‌اش حرفی نزدن).")
    return ids


# ---------------------------------------------------------------- خروجی اصلی
def _merge_same(segs):
    out = []
    for s in segs:
        if out and out[-1]["scene"] == s["scene"]:
            out[-1]["end"] = s["end"]
        else:
            out.append(dict(s))
    return out


def build_segments(summary, timeline, audio_path, out_dir=None):
    sents = flatten(timeline)
    total = _audio_len(audio_path)

    script = []
    for si, s in enumerate(sents):
        for w in s["text"].split():
            n = norm_word(w)
            if n:
                script.append((n, si))
    if len(script) < 50:
        raise RuntimeError("متن خیلی کوتاهه.")

    heard = transcribe_words(audio_path)
    if len(heard) < len(script) * 0.4:
        raise RuntimeError("تشخیص گفتار خیلی کم کلمه پیدا کرد؛ ویدیو ساخته نشد.")

    times, coverage = align_words([w for w, _ in script], heard, total)

    first = {}
    for k, (_, si) in enumerate(script):
        first.setdefault(si, times[k])
    raw = [first.get(si) for si in range(len(sents))]
    nxt = total
    for si in range(len(raw) - 1, -1, -1):
        if raw[si] is None:
            raw[si] = nxt
        else:
            nxt = raw[si]
    starts = []
    for si, st in enumerate(raw):
        st = 0.0 if si == 0 else max(starts[-1], st - LEAD)
        starts.append(min(st, total))

    scene_ids = annotate(sents, summary)

    segs = []
    for si, sid in enumerate(scene_ids):
        en = starts[si + 1] if si + 1 < len(starts) else total
        segs.append({"scene": sid, "start": starts[si], "end": en})
    segs = _merge_same(segs)

    changed = True
    while changed:
        changed = False
        for k in range(1, len(segs) - 1):
            if segs[k]["end"] - segs[k]["start"] < MIN_SEG:
                segs[k - 1]["end"] = segs[k]["end"]
                del segs[k]
                segs = _merge_same(segs)
                changed = True
                break
    segs[0]["start"] = 0.0
    segs[-1]["end"] = total

    if out_dir:
        try:
            with open(os.path.join(out_dir, "sync_report.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "coverage": round(coverage, 3),
                    "total_seconds": round(total, 1),
                    "sentences": [{"start": round(starts[i], 2), "scene": scene_ids[i], "text": sents[i]["text"]}
                                  for i in range(len(sents))],
                    "segments": segs,
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:  # noqa: BLE001
            print("گزارش هماهنگی ذخیره نشد:", e)

    print(f"{len(sents)} جمله → {len(segs)} صحنه هماهنگ با صدا")
    return segs
