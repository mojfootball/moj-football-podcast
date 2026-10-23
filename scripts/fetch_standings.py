import os
import json
import requests

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"].strip()
BASE_URL = "https://soccer.highlightly.net/standings"
HEADERS = {"x-rapidapi-key": API_KEY}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-lite-latest:generateContent"
)

_cache = {}


def get_standings(league_id, season):
    if not league_id or not season:
        return None
    key = (league_id, season)
    if key in _cache:
        return _cache[key]
    try:
        resp = requests.get(
            BASE_URL, headers=HEADERS,
            params={"leagueId": league_id, "season": season}, timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"خطا در گرفتن جدول لیگ {league_id}/{season}: {e}")
        _cache[key] = None
        return None
    _cache[key] = data
    return data


def translate_team_names(names):
    names = list(dict.fromkeys(n for n in names if n))
    if not names:
        return {}
    if not GEMINI_API_KEY:
        return {n: n for n in names}
    prompt = (
        "Transliterate each football club name below into Persian (Farsi) script, "
        "the way Persian sports media commonly write it. Return ONLY a JSON object "
        "mapping each original name to its Persian form (same keys as given).\n\n"
        + json.dumps(names, ensure_ascii=False)
    )
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
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        mapping = json.loads(raw)
        return {n: mapping.get(n, n) for n in names}
    except Exception as e:
        print(f"ترجمه‌ی اسم تیم‌های جدول ناموفق بود: {e}")
        return {n: n for n in names}


def _row(row):
    """استخراج امن و استاندارد اطلاعات هر تیم از هر نوع ساختار API (لیگ‌ها، جام‌ها، قاره‌ای و ملی)"""
    team = row.get("team") or row.get("teamInfo") or {}
    team_id = team.get("id") or row.get("teamId") or row.get("id")
    name = team.get("name") or row.get("teamName") or row.get("name") or "Unknown"
    logo = team.get("logo") or row.get("teamLogo") or team.get("crest") or ""

    stats_sources = [
        row.get("total"),
        row.get("overall"),
        row.get("stats"),
        row,
    ]

    def find_val(*keys):
        for src in stats_sources:
            if isinstance(src, dict):
                for k in keys:
                    if k in src and src[k] is not None:
                        return src[k]
        return None

    played = find_val("games", "played", "matchesPlayed", "matchPlayed")
    won = find_val("won", "wins")
    drawn = find_val("drawn", "draw", "tied")
    lost = find_val("lost", "loss", "losses")

    gf = find_val("scoredGoals", "goalsFor", "gf", "goalsScored")
    ga = find_val("receivedGoals", "goalsAgainst", "ga", "goalsConceded")
    gd = find_val("goalDifference", "gd", "diff")
    if gd is None and gf is not None and ga is not None:
        try:
            gd = int(gf) - int(ga)
        except Exception:
            pass

    points = find_val("points", "pts", "point")
    rank = row.get("position") or row.get("rank") or row.get("standing") or row.get("pos") or row.get("place")

    return {
        "rank": rank,
        "team_id": team_id,
        "name": name,
        "logo": logo,
        "played": played,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "gf": gf,
        "ga": ga,
        "gd": gd,
        "points": points,
    }


def get_table_context(league_id, season, home_id, away_id):
    data = get_standings(league_id, season)
    if not data:
        return None

    all_rows = []

    # اسکن بازگشتی و عمیق برای پیدا کردن ردیف‌های جدول در تمامی فرمت‌های تورنمنت‌ها
    def extract_rows(obj):
        if isinstance(obj, list):
            for el in obj:
                extract_rows(el)
        elif isinstance(obj, dict):
            if any(k in obj for k in ("position", "rank", "standing", "points", "pts")) and (
                "team" in obj or "teamId" in obj or "teamInfo" in obj or "name" in obj
            ):
                all_rows.append(obj)
            else:
                for k, v in obj.items():
                    if isinstance(v, (list, dict)):
                        extract_rows(v)

    extract_rows(data)

    if not all_rows:
        return None

    # حذف موارد تکراری و نرمال‌سازی
    seen = set()
    unique_rows = []
    for r in all_rows:
        parsed = _row(r)
        tid = parsed["team_id"] or parsed["name"]
        if tid not in seen and tid != "Unknown":
            seen.add(tid)
            unique_rows.append(parsed)

    # مرتب‌سازی بر اساس رتبه یا امتیاز
    def sort_key(x):
        try:
            r = x.get("rank")
            if r is not None:
                return (0, int(r))
        except Exception:
            pass
        try:
            p = x.get("points")
            if p is not None:
                return (1, -int(p))
        except Exception:
            pass
        return (2, 0)

    unique_rows.sort(key=sort_key)

    for idx, row in enumerate(unique_rows, start=1):
        if row.get("rank") is None:
            row["rank"] = idx

    top8 = unique_rows[:8]
    top8_ids = {r["team_id"] for r in top8}

    def extra_for(team_id):
        if not team_id:
            return None
        for r in unique_rows:
            if r.get("team_id") == team_id:
                if r.get("team_id") in top8_ids:
                    return None
                return r
        return None

    home_extra = extra_for(home_id)
    away_extra = extra_for(away_id)

    names = [r["name"] for r in top8 if r.get("name")]
    for extra in (home_extra, away_extra):
        if extra and extra.get("name"):
            names.append(extra["name"])
    fa_map = translate_team_names(names)

    for r in top8:
        if r.get("name"):
            r["fa_name"] = fa_map.get(r["name"], r["name"])
    if home_extra and home_extra.get("name"):
        home_extra["fa_name"] = fa_map.get(home_extra["name"], home_extra["name"])
    if away_extra and away_extra.get("name"):
        away_extra["fa_name"] = fa_map.get(away_extra["name"], away_extra["name"])

    return {
        "top8": top8,
        "home_extra": home_extra,
        "away_extra": away_extra,
        "home_id": home_id,
        "away_id": away_id,
    }
