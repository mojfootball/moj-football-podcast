import os
import json
import time
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-lite-latest:generateContent"
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
    lines = [
        "تو داری دیالوگ یه پادکست ورزشی فارسی به اسم موج فوتبال رو می‌نویسی.",
        "دو تا مجری داریم:",
        "- مجتبا (مرد، کارشناس فنی، تحلیل تاکتیکی و آماری می‌ده) — دقت کن اسمش رو دقیقاً همین‌طور یعنی م-ج-ت-ب-ا بنویسی، نه مجتبی",
        "- پگاه (زن، مجری اصلی، سوال می‌پرسه، نظر می‌ده، بعضی‌جاها با مجتبا بحث یا مخالفت می‌کنه)",
        "",
        "این اطلاعات ساختاریافته از بازی " + summary["home_team"] + " "
        + str(summary["score"]) + " " + summary["away_team"]
        + " (مسابقات: " + str(summary["league"]) + "، ورزشگاه: " + str(summary["venue"]) + ") هست:",
        "",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "یه دیالوگ طبیعی، محاوره‌ای و جذاب و نسبتاً مفصل بین مجتبا و پگاه بنویس که:",
        "- با سلام و معرفی کوتاه بازی شروع بشه",
        "- به ترتیب زمانی، همه‌ی رویدادهای مهم بازی (گل‌ها، کارت‌ها، تعویض‌های کلیدی) رو با جزئیات مرور و تحلیل کنن",
        "- عملکرد حداقل دو سه تا از بازیکنان برتر هر تیم (از بخش topPlayers) رو هم جداگانه بررسی کنن",
        "- حداقل دو بار با هم سر موضوعات مختلف بحث یا اختلاف‌نظر داشته باشن، نه فقط یه‌بار",
        "- آمار بازی رو با جزئیات بیشتر و ضمن گفتگو تحلیل کنن (نه فقط چند عدد پرتکرار)، نه خشک و لیست‌وار",
        "- با یه جمع‌بندی و خداحافظی کوتاه تموم بشه",
        "",
        "قوانین مهم:",
        "- فقط از اطلاعاتی که توی داده‌ها اومده استفاده کن",
        "- اسم بازیکن‌ها و تیم‌ها رو دقیقاً عین همون چیزی که توی داده‌ها نوشته شده بنویس، بدون تغییر یا ترکیب حروف فارسی و انگلیسی",
        "- لحن کاملاً محاوره‌ای و دوستانه باشه",
        "- چون باید جزئیات بیشتری پوشش داده بشه، کل گفتگو باید طولانی و کامل باشه، برای حدود هشت تا ده دقیقه خوانده‌شدن (یعنی تقریباً ۱۱۰۰ تا ۱۴۰۰ کلمه)؛ این طول رو با تحلیل عمیق‌تر و مرور جزئیات بیشتر پر کن، نه با تکرار یا حرف‌های اضافه و بی‌ربط",
        "- خروجی رو فقط و فقط به‌صورت یه آرایه‌ی JSON معتبر بده، بدون هیچ توضیح اضافه.",
        "هر عضو آرایه باید دو کلید داشته باشه: speaker (مقدارش female یا male) و text.",
    ]
    prompt = "\n".join(lines)

    last_error = None
    for attempt in range(5):
        if attempt > 0:
            time.sleep(10 * attempt)
        try:
            resp = requests.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"response_mime_type": "application/json"},
                },
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(raw_text)
        except requests.RequestException as e:
            last_error = e
            print(f"تلاش {attempt + 1} ناموفق بود: {e}")

    raise last_error


if __name__ == "__main__":
    import sys
    from fetch_match_details import get_match_details

    match_id = int(sys.argv[1])
    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)
    for turn in turns:
        label = "🎙️ پگاه" if turn["speaker"] == "female" else "🎙️ مجتبا"
        print(f"{label}: {turn['text']}\n")
