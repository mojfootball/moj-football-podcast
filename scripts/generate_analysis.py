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
        "news_headlines": [
            {"title": n.get("title"), "date": n.get("datePublished")}
            for n in details.get("news", [])[:10]
        ],
    }


def generate_persian_script(summary):
    lines = [
        "تو داری دیالوگ یه ویدیوی تحلیلی ورزشی فارسی برای یوتیوب به اسم موج فوتبال رو می‌نویسی. این محتوا ویدیوئه نه فقط صدا، پس همه‌جا باید به 'بیننده‌ها' و 'تماشاگرهای کانال' اشاره بشه، نه 'شنونده‌ها'؛ مثلاً باید گفته بشه 'ممنون که این قسمت رو تماشا کردید' نه 'ممنون که گوش دادید'، و 'سلام به بینندگان عزیز موج فوتبال' نه 'شنوندگان عزیز'.",
        "دو تا مجری داریم:",
        "- مجتبآ (مرد، کارشناس فنی، تحلیل تاکتیکی و آماری می‌ده) — دقت کن اسمش رو دقیقاً همین‌طور یعنی م-ج-ت-ب-آ بنویسی، نه مجتبا یا مجتبی",
        "- پگاه (زن، مجری اصلی، سوال می‌پرسه، نظر می‌ده، بعضی‌جاها با مجتبآ بحث یا مخالفت می‌کنه)",
        "",
        "این اطلاعات ساختاریافته از بازی " + summary["home_team"] + " "
        + str(summary["score"]) + " " + summary["away_team"]
        + " (مسابقات: " + str(summary["league"]) + "، ورزشگاه: " + str(summary["venue"]) + ") هست:",
        "",
        json.dumps(summary, ensure_ascii=False, indent=2),
        "",
        "یه دیالوگ طبیعی، محاوره‌ای و جذاب بین مجتبآ و پگاه بنویس، دقیقاً مثل یه پادکست تحلیلی واقعی که دو کارشناس دارن با هم گپ می‌زنن، نه مثل خوندن خبر.",
        "",
        "نحوه‌ی کار این‌طوریه که این داده‌ها فقط مواد خام تحلیلن، نه چیزی که باید کامل روخونی بشه:",
        "- از بین همه‌ی رویدادها، فقط ۳ تا ۵ تا از مهم‌ترین لحظات بازی (گل‌ها، یه تصمیم جنجالی، یه تعویض تأثیرگذار، یه اخراج) رو انتخاب کن",
        "- برای هرکدوم از این لحظات، مجتبآ و پگاه باید واقعاً دربارش بحث و تبادل‌نظر کنن: چرا این اتفاق افتاد، چه تاثیری رو بازی گذاشت، کی مقصر بود، نظرشون چیه — نه اینکه فقط بگن کی و دقیقه چند چیکار کرد",
        "- کارت‌های زرد معمولی، تعویض‌های کم‌اهمیت و رویدادهای فرعی رو اصلاً لازم نیست همه رو بگن؛ فقط اگه یکی از اونا واقعاً روی روند بازی اثر گذاشت بیارش",
        "- آمار بازی (مالکیت، شوت‌ها، اکسپکتد گل و از این قبیل) فقط باید به‌عنوان مدرک و پشتوانه‌ی یه حرف یا استدلال وسط بحث بیاد، نه به‌صورت یه بلوک جدا که انگار دارن گزارش آماری می‌خونن",
        "- عملکرد یکی دو تا از بازیکنان برتر رو هم در لابه‌لای همون بحث‌ها (نه جدا) بیار",
        "- اگه توی بخش news_headlines خبر یا واکنشی بود (مثلاً حرف‌های مربی یا بازیکنی بعد از بازی، یا به‌ندرت یه حاشیه درباره‌ی تماشاگرا)، نزدیک پایان گفتگو یه بخش حاشیه‌ها بذار که واقعاً جا باز کنه، نه یه جمع‌بندی سریع و عجول؛ حداقل ۳ تا ۴ تا از مهم‌ترین واکنش‌ها/نقل‌قول‌ها رو با زبون خودتون (نه کپی لغت‌به‌لغت) بیار، مجتبآ و پگاه درباره‌ی هرکدوم واقعاً نظر و تحلیل بدن (مثلاً موافقن با حرف مربی یا نه، این واکنش چقدر منطقیه)، نه فقط بخونن و رد بشن. این بخش باید به‌اندازه‌ی بخش تحلیل لحظات کلیدی بازی، عمق و زمان داشته باشه. اگه خبر مهمی نبود این بخش رو خیلی کوتاه بگیر یا کامل حذفش کن، چیزی از خودت نساز",
        "- با سلام و معرفی کوتاه بازی شروع بشه و با جمع‌بندی و خداحافظی کوتاه تموم بشه",
        "",
        "قوانین اصطلاحات فوتبالی (خیلی مهم):",
        "- از اصطلاحات رایج و درست فوتبالی فارسی استفاده کن، نه ترجمه‌ی تحت‌اللفظی. مثلاً: Save یعنی دروازه‌بان 'سیو کرد' یا 'مهار کرد'، نه 'ذخیره کرد'. Clean sheet یعنی 'دروازه بسته'. Offside یعنی 'آفساید'. Through ball یعنی 'پاس پشت خط دفاع' یا 'پاس عمقی'. وقتی به کلمه یا آمار عجیبی توی داده برخوردی که معادل رایج فارسی داره، همون معادل رایج رو بگو",
        "",
        "قوانین لحن (خیلی مهم):",
        "- سراسر متن باید محاوره‌ای باشه، نه فقط شروعش. از کلمات کتابی و رسمی مثل 'لذا'، 'بدین‌ترتیب'، 'در نهایت باید گفت'، 'به‌منظور' و جمله‌های طولانی و پیچیده خودداری کن",
        "- مثل دو تا آدم واقعی حرف بزنن: جمله‌های کوتاه‌تر، گاهی وسط حرف هم بپرن، از 'آره'، 'نه بابا'، 'ببین'، 'راستش' و این‌جور کلمات محاوره‌ای استفاده کن",
"- خیلی مراقب باش وسط یه جمله‌ی محاوره‌ای، یهو از فعل کتابی استفاده نکنی؛ همیشه شکل محاوره‌ای فعل رو بنویس، نه رسمی. مثلاً به‌جای 'نتوانست' بنویس 'نتونست'، به‌جای 'می‌توانست' بنویس 'می‌تونست'، به‌جای 'می‌خواهد' بنویس 'می‌خواد'، به‌جای 'کرد' در جمله‌های رسمی مثل 'ایفا کرد' بنویس 'بازی کرد'. هیچ فعلی نباید با 'ـتن' یا 'ـیدن' رسمی و کتابی تموم بشه",
        "",
        "قوانین دیگه:",
        "- فقط از اطلاعاتی که توی داده‌ها اومده استفاده کن، ولی مجبور نیستی همه‌ش رو بیاری",
        "- اسم همه‌ی بازیکن‌ها، تیم‌ها و ورزشگاه‌ها رو حتماً با حروف فارسی و تلفظ نزدیک به درست بنویس (مثلاً Michael Olise را بنویس مایکل الیسه)، هیچ‌وقت از حروف لاتین/انگلیسی وسط متن استفاده نکن",
        "- طول گفتگو برای حدود هشت تا ده دقیقه خوانده‌شدن باشه (تقریباً ۱۱۰۰ تا ۱۴۰۰ کلمه)؛ این طول رو با بحث و تحلیل عمیق‌تر روی همون چندتا لحظه‌ی مهم پر کن، نه با اضافه‌کردن رویدادهای بیشتر یا حرف‌های تکراری",
                "",
        "برچسب صحنه‌ی تصویری:",
        "- علاوه بر speaker و text، هر عضو آرایه باید یه کلید سوم هم داشته باشه به اسم scene، که نشون می‌ده همون لحظه چه تصویری روی صفحه نمایش داده بشه. مقدار scene باید دقیقاً یکی از این‌ها باشه:",
        "  title (معرفی اولیه‌ی بازی)، momentum (مرور کلی روند بازی روی خط زمان)، goal (لحظه‌ی یه گل خاص)، card_or_sub (یه کارت قرمز یا تعویض مهم)، stat_bar (مقایسه‌ی یه آمار کلی مثل مالکیت یا پاس)، shot_map (نقشه‌ی شوت‌ها)، player_card (معرفی یه بازیکن برتر)، prediction (مقایسه‌ی پیش‌بینی قبل از بازی با نتیجه‌ی واقعی)، news (واکنش کنفرانس خبری)، outro (جمع‌بندی و خداحافظی)",
        "- scene باید با موضوعی که همون لحظه دارن درباره‌ش حرف می‌زنن هماهنگ باشه؛ وقتی موضوع گفتگو عوض میشه، scene هم باید عوض بشه",
        "- اولین عضو آرایه باید scene برابر title داشته باشه و آخرین عضو باید scene برابر outro داشته باشه",
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
                label = "🎙️ پگاه" if turn["speaker"] == "female" else "🎙️ مجتبآ"
        print(f"[{turn.get('scene')}] {label}: {turn['text']}\n")
