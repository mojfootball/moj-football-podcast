"""
episode_tools.py
ابزارهای محاوره‌ای‌سازی متن و همگام‌سازی صحنه‌ها با نام گوینده «ماهور».
"""
import os
import re
import json
import time
import requests

ZW = "\u200c"
_L = "\u0600-\u06FF"

PAIRS = [
    ("نتوانستند", "نتونستن"), ("نتوانستم", "نتونستم"), ("نتوانست", "نتونست"),
    ("توانستند", "تونستن"), ("توانستم", "تونستم"), ("توانست", "تونست"),
    ("نمی‌توانستند", "نمی‌تونستن"), ("نمی‌توانست", "نمی‌تونست"),
    ("نمی‌توانند", "نمی‌تونن"), ("نمی‌تواند", "نمی‌تونه"), ("نمی‌توانم", "نمی‌تونم"),
    ("می‌خواهد", "می‌خواد"), ("می‌شود", "می‌شه"), ("می‌کند", "می‌کنه"),
    ("می‌کنند", "می‌کنن"), ("می‌دهد", "می‌ده"), ("می‌گیرد", "می‌گیره"),
    ("هستند", "هستن"), ("بودند", "بودن"), ("کردند", "کردن"), ("شدند", "شدن"),
    ("اما", "ولی"), ("زیرا", "چون"), ("بنابراین", "پس"), ("اگر", "اگه"),
    ("بسیار", "خیلی"), ("آنها", "اونا"), ("اینها", "اینا"),
]


def _pat(word):
    esc = re.escape(word).replace(ZW, f"[{ZW} ]?")
    return re.compile(rf"(?<![{_L}{ZW}]){esc}(?![{_L}{ZW}])")


_RULES = [(_pat(a), b) for a, b in sorted(PAIRS, key=lambda p: -len(p[0]))]
_RA = re.compile(rf"(?<=[{_L}{ZW}]) را(?=[\s،.!؟…:]|$)")
_AST = re.compile(rf"(?<=[{_L}{ZW}]) است(?=[\s،.!؟…:]|$)")


def colloquialize(text):
    if not text:
        return text
    t = text.replace("ك", "ک").replace("ي", "ی")
    for pat, repl in _RULES:
        t = pat.sub(repl, t)
    t = _RA.sub(" رو", t)
    t = _AST.sub(" هست", t)
    return t


GEMINI_MODEL_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
                    "gemini-flash-latest:generateContent")


def build_catalog(summary):
    events = summary.get("events") or []
    goals = [e for e in events if e.get("type") == "Goal"]
    cards = [e for e in events if e.get("type") in ("Red Card", "Substitution")]
    players = ([(p, summary["home_team"]) for p in summary.get("home_top_players") or []]
               + [(p, summary["away_team"]) for p in summary.get("away_top_players") or []])
    items = {
        "title": "معرفی بازی",
        "outro": "خداحافظی",
        "momentum": "روند کلی بازی",
        "compare": "مقایسه‌ی آمار دو تیم",
        "shots": "نقشه‌ی شوت‌ها",
        "table": "جدول رده‌بندی کامل لیگ شامل تمامی آمار برد، باخت و امتیازات",
    }
    if summary.get("news_headlines"):
        items["news:0"] = "تیتر اخبار و حاشیه‌ها"
    for i, e in enumerate(goals):
        items[f"goal:{i}"] = f"گل دقیقه {e.get('time')} توسط {e.get('player')}"
    for i, e in enumerate(cards):
        items[f"card:{i}"] = f"{e.get('type')} دقیقه {e.get('time')}"
    for i, (p, team) in enumerate(players):
        items[f"player:{i}"] = f"بازیکن {p.get('name')}"
    return items


def annotate_scenes(turns, summary):
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return turns
    catalog = build_catalog(summary)
    payload_turns = [{"i": i, "speaker": t.get("speaker"), "text": t.get("text")} for i, t in enumerate(turns)]
    prompt = (
        "You are the visual editor of a Persian football analysis video. For EACH dialogue turn choose the one visual "
        "that best matches what the speakers are talking about in that exact turn.\n\n"
        "RULES:\n"
        "- Use ONLY ids from the catalog keys.\n"
        "- First turn must be 'title'. Last turn must be 'outro'.\n"
        "- When the hosts discuss league standings or table, use 'table'.\n"
        "- When the hosts discuss news, quotes, or post-match headlines, use 'news:0'.\n"
        "- When discussing goals, use goal:N.\n"
        "- Return ONLY a JSON array with one object per turn: [{\"i\":0,\"scene\":\"title\"}, ...]\n\n"
        "CATALOG:\n" + json.dumps(catalog, ensure_ascii=False, indent=1) + "\n\n"
        "DIALOGUE:\n" + json.dumps(payload_turns, ensure_ascii=False)
    )
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{GEMINI_MODEL_URL}?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}},
                timeout=90,
            )
            resp.raise_for_status()
            data = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
            chosen = {row["i"]: row["scene"] for row in data if "i" in row and "scene" in row}
            for i, t in enumerate(turns):
                t["scene"] = chosen.get(i, "compare")
            turns[0]["scene"] = "title"
            turns[-1]["scene"] = "outro"
            return turns
        except Exception as e:
            print(f"تلاش {attempt + 1} ناموفق: {e}")
    return turns


def finalize_turns(turns, summary):
    for t in turns:
        t["text"] = colloquialize(t.get("text", ""))
    try:
        turns = annotate_scenes(turns, summary)
    except Exception as e:
        print("annotate_scenes خطا داد:", e)
    return turns
