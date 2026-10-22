"""
episode_tools.py

۱) colloquialize: محاوره‌ای‌سازی افعال و اصطلاحات
۲) annotate_scenes: هماهنگی کامل تصاویر با گفتگوی مجری‌ها
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
    ("نمی‌توانند", "نمی‌تونن"), ("نمی‌تواند", "نمی‌تونه"), ("نمی‌توانم", "نمی‌تونم"), ("نمی‌توانی", "نمی‌تونی"),
    ("می‌توانستند", "می‌تونستن"), ("می‌توانست", "می‌تونست"),
    ("تازه‌نفس", "پرانرژی"), ("تازه‌نفس‌ها", "پرانرژی‌ها"),
    ("می‌توانند", "می‌تونن"), ("می‌تواند", "می‌خواد"), ("می‌توانم", "می‌تونم"), ("می‌توانی", "می‌تونی"),
    ("می‌خواهند", "می‌خوان"), ("می‌خواهد", "می‌خواد"), ("نمی‌خواهند", "نمی‌خوان"), ("نمی‌خواهد", "نمی‌خواد"),
    ("خواهد شد", "می‌شه"), ("خواهند شد", "می‌شن"), ("خواهد کرد", "می‌کنه"),
    ("می‌شود", "می‌شه"), ("نمی‌شود", "نمی‌شه"), ("می‌شوند", "می‌شن"), ("می‌باشد", "هست"),
    ("می‌کند", "می‌کنه"), ("می‌کنند", "می‌کنن"), ("نمی‌کند", "نمی‌کنه"), ("نمی‌کنند", "نمی‌کنن"),
    ("می‌دهد", "می‌ده"), ("می‌دهند", "می‌دن"), ("نمی‌دهد", "نمی‌ده"), ("نمی‌دهند", "نمی‌دن"),
    ("می‌گیرد", "می‌گیره"), ("می‌گیرند", "می‌گیرن"), ("می‌زند", "می‌زنه"), ("می‌زنند", "می‌زنن"),
    ("می‌رود", "می‌ره"), ("می‌روند", "می‌رن"), ("می‌بیند", "می‌بینه"), ("می‌بینند", "می‌بینن"),
    ("می‌گوید", "می‌گه"), ("می‌گویند", "می‌گن"), ("می‌داند", "می‌دونه"), ("می‌دانند", "می‌دونن"),
    ("می‌دانم", "می‌دونم"), ("می‌آید", "میاد"), ("می‌آیند", "میان"), ("نمی‌آید", "نمیاد"),
    ("می‌افتد", "می‌افته"), ("می‌ماند", "می‌مونه"), ("می‌ماندند", "می‌موندن"),
    ("آمدند", "اومدن"), ("آمد", "اومد"), ("آمده", "اومده"), ("آوردند", "آوردن"),
    ("هستند", "هستن"), ("نیستند", "نیستن"), ("بودند", "بودن"), ("داشتند", "داشتن"),
    ("کردند", "کردن"), ("شدند", "شدن"), ("گرفتند", "گرفتن"), ("زدند", "زدن"), ("دادند", "دادن"),
    ("رفتند", "رفتن"), ("گفتند", "گفتن"), ("دیدند", "دیدن"), ("ماندند", "موندن"),
    ("همچنین", "همین‌طور"), ("اما", "ولی"), ("زیرا", "چون"), ("بنابراین", "پس"), ("لذا", "پس"),
    ("چنانچه", "اگه"), ("اگر", "اگه"), ("نیز", "هم"), ("بسیار", "خیلی"), ("آنها", "اونا"),
    ("آن‌ها", "اونا"), ("اینها", "اینا"), ("این‌ها", "اینا"), ("چراکه", "چون"), ("هرچند", "هرچند"),
    ("ایفا کرد", "بازی کرد"), ("ایفا کردند", "بازی کردن"),
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
                    "gemini-2.5-flash:generateContent")


def build_catalog(summary):
    events = summary.get("events") or []
    goals = [e for e in events if e.get("type") == "Goal"]
    cards = [e for e in events if e.get("type") in ("Red Card", "Substitution")]
    players = ([(p, summary["home_team"]) for p in summary.get("home_top_players") or []]
               + [(p, summary["away_team"]) for p in summary.get("away_top_players") or []])
    items = {}
    items["title"] = "معرفی بازی (فقط جمله‌ی اول)"
    items["outro"] = "خداحافظی (فقط جمله‌ی آخر)"
    items["momentum"] = "روند کلی بازی روی خط زمان"
    items["compare"] = "مقایسه‌ی کلی آمار دو تیم"
    items["shots"] = "نقشه‌ی شوت‌ها روی دروازه"
    if summary.get("table_context"):
        items["table"] = "جدول رده‌بندی کامل لیگ"
    if summary.get("prematch_prediction"):
        items["prediction"] = "پیش‌بینی قبل از بازی و مقایسه با نتیجه"
    for i, e in enumerate(goals):
        items[f"goal:{i}"] = f"گل دقیقه {e.get('time')} توسط {e.get('player')} برای {e.get('team')} (پاس گل: {e.get('assist')})"
    for i, e in enumerate(cards):
        items[f"card:{i}"] = f"{e.get('type')} دقیقه {e.get('time')} — {e.get('player')} ({e.get('team')})"
    stat_names = {"Possession": "مالکیت توپ", "Total passes": "تعداد پاس", "Shots on target": "شوت در چارچوب",
                  "Expected Goals": "xG / کیفیت موقعیت‌ها", "Big Chances Created": "موقعیت‌های بزرگ", "Corners": "کرنر"}
    for k, fa_name in stat_names.items():
        if (summary.get("home_stats") or {}).get(k) is not None:
            items[f"stat:{k}"] = f"آمار {fa_name}"
    for i, (p, team) in enumerate(players):
        items[f"player:{i}"] = f"کارت بازیکن {p.get('name')} ({team})"
    for i, _ in enumerate(summary.get("news_headlines") or []):
        items[f"news:{i}"] = "تیتر خبر یا واکنش‌های حاشیه‌ای"
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
        "- Use ONLY ids from the catalog.\n"
        "- First turn must be 'title'. Last turn must be 'outro'. 'title' and 'outro' must not be used anywhere else.\n"
        "- When the hosts discuss the league standings or table, use 'table'.\n"
        "- When the hosts discuss post-match quotes, media reactions, or headlines, use 'news:N'. If news is NOT mentioned, NEVER use 'news'.\n"
        "- If the turn discusses a specific goal, use goal:N.\n"
        "- If it discusses a specific statistic, use stat:Key. If it discusses a specific player, use player:N. "
        "Red card/substitution → card:N.\n"
        "- Return ONLY a JSON array with one object per turn: [{\"i\":0,\"scene\":\"title\"}, ...] covering every turn.\n\n"
        "CATALOG (id: description):\n" + json.dumps(catalog, ensure_ascii=False, indent=1) + "\n\n"
        "DIALOGUE TURNS:\n" + json.dumps(payload_turns, ensure_ascii=False)
    )
    last_error = None
    for attempt in range(3):
        if attempt:
            time.sleep(8 * attempt)
        try:
            resp = requests.post(
                f"{GEMINI_MODEL_URL}?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"response_mime_type": "application/json", "temperature": 0.2}},
                timeout=90,
            )
            resp.raise_for_status()
            raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            data = json.loads(raw)
            chosen = {}
            for row in data:
                i, sc = row.get("i"), row.get("scene")
                if isinstance(i, int) and 0 <= i < len(turns) and sc in catalog:
                    chosen[i] = sc
            if len(chosen) < len(turns) * 0.6:
                raise ValueError("پاسخ ناقص بود")
            fallback = "compare"
            for i, t in enumerate(turns):
                sc = chosen.get(i)
                if sc is None:
                    sc = fallback
                t["scene"] = sc
            turns[0]["scene"] = "title"
            turns[-1]["scene"] = "outro"
            for t in turns[1:-1]:
                if t["scene"] in ("title", "outro"):
                    t["scene"] = "compare"
            print("برچسب صحنه‌ها با موضوع گفتگو هماهنگ شد:", [t["scene"] for t in turns])
            return turns
        except Exception as e:
            last_error = e
            print(f"هماهنگی صحنه‌ها تلاش {attempt + 1} ناموفق: {e}")
    print("برچسب‌های اولیه‌ی Gemini حفظ شد:", last_error)
    return turns


def finalize_turns(turns, summary):
    for t in turns:
        t["text"] = colloquialize(t.get("text", ""))
    return turns
