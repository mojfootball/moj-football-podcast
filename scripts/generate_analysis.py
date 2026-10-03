import os
import json
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-latest:generateContent"
)


def summarize_match(details):
    home = details.get("homeTeam", {})
    away = details.get("awayTeam", {})

    def top_players(team):
        return [
            {
                "name": p.get("name"),
                "position": p.get("position"),
                "stats": {s["name"]: s["value"] for s in p.get("statistics", [])},
            }
            for p in team.get("topPlayers", [])
        ]

    def key_shots(team):
        return [
            s for s in team.get("shots", [])
            if s.get("outcome") in ("Goal", "Saved")
        ][:6]

    def team_stats(team_id):
        for block in details.get("statistics", []):
            if block.get("team", {}).get("id") == team_id:
                return {s["displayName"]: s["value"] for s in block.get("statistics", [])}
        return {}

    return {
        "league": details.get("league", {}).get("name"),
        "venue": details.get("venue", {}).get("name"),
        "score": details.get("state", {}).get("score", {}).get("current"),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "events": [
            {
                "time": e.get("time"),
                "type": e.get("type"),
                "team": e.get("team", {}).get("name"),
                "player": e.get("player"),
                "assist": e.get("assist"),
            }
            for e in details.get("events", [])
        ],
        "home_stats": team_stats(home.get("id")),
        "away_stats": team_stats(away.get("id")),
        "home_top_players": top_players(home),
        "away_top_players": top_players(away),
        "home_key_shots": key_shots(home),
        "away_key_shots": key_shots(away),
    }


def generate_persian_script(summary):
    prompt = f"""
تو یه کارشناس و گزارشگر حرفه‌ای تحلیل فوتبال هستی که برای یه پادکست/کانال یوتیوب فارسی
به اسم "موج فوتبال" متن تحلیل بعد از بازی می‌نویسی.

این اطلاعات ساختاریافته از بازی {summary['home_team']} {summary['score']} {summary['away_team']}
(مسابقات: {summary['league']}، ورزشگاه: {summary['venue']}) هست:

{json.dumps(summary, ensure_ascii=False, indent=2)}

یه متن تحلیلی فارسیِ روان و کارشناسی برای خوانده‌شدن با صدای گوینده بنویس، با این ساختار:
۱. مقدمه‌ی کوتاه (نتیجه، اهمیت بازی)
۲. روند بازی و اتفاقات کلیدی (گل‌ها، لحظات مهم) به ترتیب زمانی
۳. تحلیل آماری کوتاه (مالکیت توپ، شوت‌ها، و هر عدد قابل توجه دیگه)
۴. جمع‌بندی و نکته‌ی پایانی

قوانین مهم:
- فقط از اطلاعاتی که توی داده‌ها اومده استفاده کن، چیزی رو از خودت نساز
- لحن باید کارشناسی و جذاب باشه، نه خشک و گزارشی صرف
- طول متن برای حدود ۲ تا ۳ دقیقه خوانده‌شدن باشه (تقریباً ۳۰۰ تا ۴۵۰ کلمه)
- فقط خود متن رو بنویس، بدون هیچ توضیح اضافه یا عنوان
"""

    resp = requests.post(
        f"{GEMINI_URL}?key={GEMINI_API_KEY}",
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


if __name__ == "__main__":
    import sys
    from fetch_match_details import get_match_details

    match_id = int(sys.argv[1])
    details = get_match_details(match_id)
    summary = summarize_match(details)
    script_text = generate_persian_script(summary)
    print(script_text)
