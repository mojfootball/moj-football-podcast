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
    total = row.get("total", {}) or row.get("overall", {}) or row.get("stats", {}) or {}
    team = row.get("team", {}) or row.get("teamInfo", {}) or {}

    gf = total.get("scoredGoals") if total.get("scoredGoals") is not None else total.get("goalsFor")
    ga = total.get("receivedGoals") if total.get("receivedGoals") is not None else total.get("goalsAgainst")
    gd = (gf - ga) if (gf is not None and ga is not None) else row.get("goalDifference") or row.get("gd")

    played = total.get("games") if total.get("games") is not None else (total.get("played") if total.get("played") is not None else row.get("played"))
    won = total.get("won") if total.get("won") is not None else row.get("won")
    drawn = total.get("drawn") if total.get("drawn") is not None else (total.get("draw") if total.get("draw") is not None else row.get("drawn"))
    lost = total.get("lost") if total.get("lost") is not None else (total.get("loss") if total.get("loss") is not None else row.get("lost"))

    return {
        "rank": row.get("position") or row.get("rank") or row.get("standing"),
        "team_id": team.get("id") or row.get("teamId"),
        "name": team.get("name") or row.get("teamName") or "Unknown",
        "logo": team.get("logo") or row.get("teamLogo"),
        "played": played,
        "won": won,
        "drawn": drawn,
        "lost": lost,
        "gf": gf,
        "ga": ga,
        "gd": gd,
        "points": row.get("points") if row.get("points") is not None else row.get("pts"),
    }


def get_table_context(league_id, season, home_id, away_id):
    data = get_standings(league_id, season)
    if not data:
        return None

    all_rows = []

    # تابع بازگشتی هوشمند برای استخراج سطور جدول از هر نوع ساختار JSON (لیگ‌ها یا چمپیونزلیگ)
    def extract_rows(obj):
        if isinstance(obj, list):
            for el in obj:
                extract_rows(el)
        elif isinstance(obj, dict):
            if "position" in obj and ("team" in obj or "points" in obj or "stats" in obj):
                all_rows.append(obj)
            else:
                for k, v in obj.items():
                    if k in ("groups", "standings", "data", "table", "rows", "tableRows") and isinstance(v, (list, dict)):
                        extract_rows(v)

    extract_rows(data)

    if not all_rows:
        return None

    # حذف موارد تکراری بر اساس شناسه تیم یا رتبه
    seen = set()
    unique_rows = []
    for r in all_rows:
        team_obj = r.get("team") or {}
        tid = team_obj.get("id") or r.get("teamId") or r.get("position")
        if tid not in seen:
            seen.add(tid)
            unique_rows.append(r)

    unique_rows.sort(key=lambda r: int(r.get("position") or r.get("rank") or 999))

    top8 = [_row(r) for r in unique_rows[:8]]
    top8_ids = {r["team_id"] for r in top8}

    def extra_for(team_id):
        if not team_id or team_id in top8_ids:
            return None
        for r in unique_rows:
            team_obj = r.get("team") or {}
            if team_obj.get("id") == team_id or r.get("teamId") == team_id:
                return _row(r)
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
        away_extra["fa_name"] = fa_map.get(extra["name"] if False else away_extra["name"], away_extra["name"])

    return {
        "top8": top8,
        "home_extra": home_extra,
        "away_extra": away_extra,
        "home_id": home_id,
        "away_id": away_id,
    }
