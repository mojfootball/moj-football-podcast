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
    total = row.get("total", {}) or {}
    gf = total.get("scoredGoals")
    ga = total.get("receivedGoals")
    gd = (gf - ga) if (gf is not None and ga is not None) else None
    team = row.get("team", {}) or {}
    return {
        "rank": row.get("position"),
        "team_id": team.get("id"),
        "name": team.get("name"),
        "logo": team.get("logo"),
        "played": total.get("games"),
        "won": total.get("won"),
        "drawn": total.get("drawn"),
        "lost": total.get("lost"),
        "gf": gf,
        "ga": ga,
        "gd": gd,
        "points": row.get("points"),
    }


def get_table_context(league_id, season, home_id, away_id):
    data = get_standings(league_id, season)
    if not data:
        return None

    all_rows = []
    for group in data.get("groups", []) or []:
        all_rows.extend(group.get("standings", []) or [])
    if not all_rows:
        return None
    all_rows.sort(key=lambda r: r.get("position") or 999)

    top8 = [_row(r) for r in all_rows[:8]]
    top8_ids = {r["team_id"] for r in top8}

    def extra_for(team_id):
        if team_id in top8_ids:
            return None
        for r in all_rows:
            if r.get("team", {}).get("id") == team_id:
                return _row(r)
        return None

    home_extra = extra_for(home_id)
    away_extra = extra_for(away_id)

    names = [r["name"] for r in top8]
    for extra in (home_extra, away_extra):
        if extra:
            names.append(extra["name"])
    fa_map = translate_team_names(names)

    for r in top8:
        r["fa_name"] = fa_map.get(r["name"], r["name"])
    if home_extra:
        home_extra["fa_name"] = fa_map.get(home_extra["name"], home_extra["name"])
    if away_extra:
        away_extra["fa_name"] = fa_map.get(away_extra["name"], away_extra["name"])

    return {
        "top8": top8,
        "home_extra": home_extra,
        "away_extra": away_extra,
        "home_id": home_id,
        "away_id": away_id,
    }
