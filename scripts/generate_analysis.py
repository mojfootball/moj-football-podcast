import os
import json
import time
import requests
from fetch_standings import get_team_standings_for_match

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
    home_standing, away_standing = get_team_standings_for_match(
        league_id, season, home.get("id"), away.get("id")
    )

    return {
        "league": league_name,
        "venue": details.get("venue", {}).get("name"),
        "score": details.get("state", {}).get("score", {}).get("current"),
        "home_team": home.get("name"),
        "away_team": away.get("name"),
        "home_logo": home.get("logo"),
        "away_logo": away.get("logo"),
        "standings": {
            "home_team_standing": home_standing,
            "away_team_standing": away_standing,
        } if (home_standing or away_standing) else None,
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
        "تو داری دیالوگ یه ویدیوی تحلیلی ورزشی فارسی برای یوتیوب به اسم موج فوتبال رو می‌نویسی. این محتوا ویدیوئه نه فقط صدا، پس همه‌جا باید به 'بیننده‌ها' و 'تماشاگرهای کانال' اشاره بشه، نه 'شنونده‌ها'؛ مثلاً باید گفته بشه 'ممنون که این قسمت رو تماشا کردید' نه 'ممنون که گوش دادید'.",
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
        "یه دیالوگ طبیعی، محاوره‌ای و جذاب بین مجتبآ و پگاه بنویس، دقیقاً مثل یه برنامه تحلیلی واقعی که دو کارشناس دارن با هم گپ می‌زنن، نه مثل خوندن خبر.",
        "",
        "نحوه‌ی کار این‌طوریه که این داده‌ها فقط مواد خام تحلیلن، نه چیزی که باید کامل روخونی بشه:",
        "- از بین همه‌ی رویدادها، فقط ۳ تا ۵ تا از مهم‌ترین لحظات بازی (گل‌ها، یه تصمیم جنجالی، یه تعویض تأثیرگذار، یه اخراج) رو انتخاب کن",
        "- برای هرکدوم از این لحظات، مجتبآ و پگاه باید واقعاً دربارش بحث و تبادل‌نظر کنن: چرا این اتفاق افتاد، چه تاثیری رو بازی گذاشت، کی مقصر بود، نظرشون چیه — نه اینکه فقط بگن کی و دقیقه چند چیکار کرد",
        "- کارت‌های زرد معمولی، تعویض‌های کم‌اهمیت و رویدادهای فرعی رو اصلاً لازم نیست همه رو بگن؛ فقط اگه یکی از اونا واقعاً روی روند بازی اثر گذاشت بیارش",
        "- آمار بازی (مالکیت، شوت‌ها، اکسپکتد گل و از این قبیل) فقط باید به‌عنوان مدرک و پشتوانه‌ی یه حرف یا استدلال وسط بحث بیاد، نه به‌صورت یه بلوک جدا که انگار دارن گزارش آماری می‌خونن",
        "- عملکرد یکی دو تا از بازیکنان برتر رو هم در لابه‌لای همون بحث‌ها (نه جدا) بیار",
        "- اگه در بخش standings اطلاعات جدول لیگ (رتبه، بازی، برد، مساوی، باخت، گل زده/خورده، تفاضل گل و امتیاز) موجود بود، حتماً مجری‌ها به جایگاه فعلی تیم‌ها در جدول و تأثیر این نتیجه روی رتبه، تفاضل یا امتیازاتشون اشاره کنن.",
        "- اگه توی بخش news_headlines خبر یا واکنشی بود، نزدیک پایان گفتگو یه بخش حاشیه‌ها بذار. اگه خبر مهمی نبود این بخش رو خیلی کوتاه بگیر یا کامل حذفش کن، چیزی از خودت نساز",
        "- شروع گفتگو همیشه با جمله‌ی استاندارد 'به این قسمت از موج فوتبال خوش آمدید' باشه. هرگز از جملاتی مثل 'اولین قسمت' یا 'قسمت اول' استفاده نکن چون این برنامه‌ها همیشگی و پویا هستن.",
        "- مجری‌ها همیشه در شروع صحبت خودشون رو با احترام و محاوره‌ای معرفی کنن (مثلاً: 'سلام به بینندگان عزیز موج فوتبال، من پگاه هستم...' و مجتبآ هم بگه 'سلام، من هم مجتبآ هستم...')",
        "- برنامه با همین معرفی و سلام شروع بشه و با جمع‌بندی و خداحافظی کوتاه تموم بشه",
        "",
        "قوانین اصطلاحات فوتبالی (خیلی مهم):",
        "- از اصطلاحات رایج و درست فوتبالی فارسی استفاده کن، نه ترجمه‌ی تحت‌اللفظی. مثلاً: Save یعنی 'سیو کرد' یا 'مهار کرد'. Clean sheet یعنی 'دروازه بسته'. Offside یعنی 'آفساید'. Through ball یعنی 'پاس عمقی'.",
        "- Expected Goals (xG) و Expected Assists (xA) رو هیچ‌وقت به‌صورت 'اکسپکتد گل' ننویس؛ به‌جاش بگو 'شاخص کیفیت موقعیت‌ها' یا 'کیفیت موقعیت‌های گلزنی'.",
        "",
        "قوانین لحن (خیلی مهم):",
        "- سراسر متن باید محاوره‌ای باشه. از کلمات رسمی مثل 'لذا'، 'بدین‌ترتیب'، 'به‌منظور' خودداری کن.",
        "- از افعال محاوره‌ای استفاده کن: نتونست، می‌خواد، کرد، بود، شد. هیچ فعلی نباید کتابی باشه.",
        "",
        "قوانین دیگه:",
        "- فقط از اطلاعات داخل داده‌ها استفاده کن.",
        "- اسم همه‌ی بازیکن‌ها و تیم‌ها رو با حروف فارسی بنویس.",
        "- طول گفتگو حدود ۸ تا ۱۰ دقیقه (۱۱۰۰ تا ۱۴۰۰ کلمه) باشه.",
        "",
        "برچسب صحنه‌ی تصویری:",
        "- هر عضو آرایه باید کلید scene داشته باشه (title, momentum, goal, card_or_sub, stat_bar, shot_map, player_card, prediction, table, news, outro).",
        "- صحنه‌ی table زمانی استفاده بشه که مجری‌ها دارن درباره جایگاه تیم‌ها در جدول رده‌بندی، امتیاز و تفاضل صحبت می‌کنند.",
        "- scene باید با موضوع گفتگو هماهنگ باشه و وقتی موضوع تغییر می‌کنه، scene هم تغییر کنه.",
        "- اولین عضو scene=title و آخرین عضو scene=outro داشته باشه.",
        "",
        "- خروجی رو فقط و فقط به‌صورت یه آرایه‌ی JSON معتبر بده، بدون هیچ توضیح اضافه.",
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
