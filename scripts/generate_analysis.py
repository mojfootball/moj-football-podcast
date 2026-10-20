import os
import json
import time
import requests
from fetch_standings import get_table_context

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-lite-latest:generateContent"
)


def summarize_match(details):
    home = details.get("homeTeam", {})
    away = details.get("awayTeam", {})
    league_name = details.get("league", {}).get("name")

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

    prematch_list = details.get("predictions", {}).get("prematch", [])
    prematch = prematch_list[0] if prematch_list else None

    league_id = details.get("league", {}).get("id")
    season = details.get("league", {}).get("season")
    table_context = get_table_context(league_id, season, home.get("id"), away.get("id"))

    return {
        "league": league_name,
        "venue": details.get("venue", {}).get("name"),
        "score": details.get("state", {}).get("score", {}).get("current"),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_logo": home.get("logo"),
        "away_logo": away.get("logo"),
        "table_context": table_context,
        "prematch_prediction": {
            "home_pct": prematch.get("probabilities", {}).get("home"),
            "draw_pct": prematch.get("probabilities", {}).get("draw"),
            "away_pct": prematch.get("probabilities", {}).get("away"),
        } if prematch else None,
        "events": [
            {
                "time": e.get("time"),
                "type": e.get("type"),
                "team": e.get("team", {}).get("name"),
                "player": e.get("player"),
                "assist": e.get("assist"),
                "detail": e.get("detail"),
            }
            for e in details.get("events", [])
        ],
        "home_stats": team_stats(home.get("id")),
        "away_stats": team_stats(away.get("id")),
        "home_top_players": top_players(home),
        "away_top_players": top_players(away),
        "home_key_shots": key_shots(home),
        "away_key_shots": key_shots(away),
        "news_headlines": [
            {"title": n.get("title"), "date": n.get("datePublished")}
            for n in details.get("news", [])[:10]
        ],
    }


def generate_persian_script(summary):
    lines = [
        "تو داری دیالوگ یه ویدیوی تحلیلی ورزشی فارسی برای یوتیوب به اسم موج فوتبال رو می‌نویسی. این محتوا ویدیوئه نه فقط صدا، پس همه‌جا باید به 'بیننده‌ها' و 'تماشاگرهای کانال' اشاره بشه، نه 'شنونده‌ها'.",
        "دو تا مجری داریم:",
        "- مجتبآ (مرد، کارشناس فنی، تحلیل تاکتیکی و آماری می‌ده) — دقت کن اسمش رو دقیقاً همین‌طور یعنی م-ج-ت-ب-آ بنویسی، نه مجتبا یا مجتبی",
        "- پگاه (زن، مجری اصلی، سوال می‌پرسه، نظر می‌ده، بعضی‌جاها با مجتبآ بحث یا مخالفت می‌کنه)",
        "",
        "این اطلاعات ساختاریافته از بازی " + str(summary.get("home_team")) + " "
        + str(summary.get("score")) + " " + str(summary.get("away_team"))
        + " (مسابقات: " + str(summary.get("league")) + "، ورزشگاه: " + str(summary.get("venue")) + ") هست:",
        "",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "یه دیالوگ طبیعی، محاوره‌ای و جذاب بین مجتبآ و پگاه بنویس، دقیقاً مثل یه برنامه تحلیلی واقعی که دو کارشناس دارن با هم گپ می‌زنن.",
        "",
        "نحوه‌ی کار و ساختار برنامه (خیلی مهم):",
        "- طول گفتگو باید بین ۱۴۰۰ تا ۱۸۰۰ کلمه (حدود ۷ تا ۱۰ دقیقه اجرای صوتی) باشه. همه تک‌گل‌ها و اتفاقات بازی رو با جزئیات جذاب بشکافید تا ویدیو کامل و مفصل بشه.",
        "- از بین رویدادها، همه‌ی گل‌ها و اتفاقات کلیدی رو تحلیل کنین و علت و نحوه به ثمر رسیدنشون رو بررسی کنین.",
        "- ترتیب ثابت برنامه:",
        "  ۱) سلام، معرفی مجری‌ها و خوش‌آمدگویی",
        "  ۲) تحلیل مفصل و دقیق تک‌تک گل‌ها و صحنه‌های کلیدی بازی به ترتیب زمان",
        "  ۳) بررسی آمار بازی و عملکرد بازیکنان برتر",
        "  ۴) بررسی وضعیت جدول رده‌بندی (اگر table_context موجود بود)",
        "  ۵) اگر درباره اخبار یا واکنش‌های بعد بازی حرف می‌زنید، اونوقت برچسب news استفاده میشه؛ اگر حرفی زده نمیشه، اصلاً صحنه news نباید تولید بشه.",
        "  ۶) جمع‌بندی و خداحافظی",
        "",
        "قوانین اصطلاحات فوتبالی (خیلی مهم):",
        "- از اصطلاحات رایج فارسی استفاده کن: Save یعنی 'سیو کرد' یا 'مهار کرد'، Clean sheet یعنی 'دروازه بسته'، Offside یعنی 'آفساید'.",
        "- Expected Goals (xG) رو 'شاخص کیفیت موقعیت‌ها' یا 'کیفیت موقعیت‌های گلزنی' بگو.",
        "",
        "قوانین لحن:",
        "- سراسر متن باید محاوره‌ای باشه (نتونست، می‌خواد، کرد، شد، بود). کلمات کتابی مثل 'لذا'، 'بنابراین'، 'بدین‌ترتیب' ممنوعه.",
        "",
        "برچسب صحنه‌ی تصویری:",
        "- هر عضو آرایه باید کلید scene داشته باشه (title, momentum, goal, card_or_sub, stat_bar, shot_map, player_card, prediction, table, news, outro).",
        "- صحنه‌ی table دقیقاً و فقط زمانی استفاده بشه که مجری‌ها دارن درباره وضعیت دو تیم در جدول رده‌بندی صحبت می‌کنند.",
        "- صحنه‌ی news فقط زمانی استفاده بشه که متن گفتگو صراحتاً داره درباره اخبار یا تیتر روزنامه‌ها/مصاحبه‌ها صحبت می‌کنه.",
        "- اولین عضو scene=title و آخرین عضو scene=outro داشته باشه.",
        "",
        "- خروجی رو فقط و فقط به‌صورت یه آرایه‌ی JSON معتبر بده.",
        "هر عضو آرایه باید دقیقاً سه کلید داشته باشه: speaker (مقدارش female یا male)، text، و scene.",
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
            from episode_tools import finalize_turns
            return finalize_turns(json.loads(raw_text), summary)
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
        label = "🎙️ پگاه" if turn["speaker"] == "female" else "🎙️ مجتبآ"
        print(f"[{turn.get('scene')}] {label}: {turn['text']}\n")
