import os
import requests

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"].strip()
BASE_URL = "https://soccer.highlightly.net/standings"
HEADERS = {"x-rapidapi-key": API_KEY}

# کش داخل همین اجرا؛ هر لیگ/فصل فقط یه‌بار درخواست می‌شه
_cache = {}


def get_standings(league_id, season):
    if not league_id or not season:
        return None
    key = (league_id, season)
    if key in _cache:
        return _cache[key]

    try:
        resp = requests.get(
            BASE_URL,
            headers=HEADERS,
            params={"leagueId": league_id, "season": season},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"خطا در گرفتن جدول لیگ {league_id}/{season}: {e}")
        _cache[key] = None
        return None

    _cache[key] = data
    return data


def _find_team_row(standings_data, team_id):
    if not standings_data:
        return None
    for group in standings_data.get("groups", []) or []:
        for row in group.get("standings", []) or []:
            if row.get("team", {}).get("id") == team_id:
                return row
    return None


def _row_to_standing(row):
    if not row:
        return None
    total = row.get("total", {}) or {}
    gf = total.get("scoredGoals")
    ga = total.get("receivedGoals")
    gd = (gf - ga) if (gf is not None and ga is not None) else None
    return {
        "rank": row.get("position"),
        "played": total.get("games"),
        "win": total.get("wins"),
        "draw": total.get("draws"),
        "loss": total.get("loses"),
        "gf": gf,
        "ga": ga,
        "gd": gd,
        "points": row.get("points"),
    }


def get_team_standings_for_match(league_id, season, home_team_id, away_team_id):
    data = get_standings(league_id, season)
    home_row = _find_team_row(data, home_team_id)
    away_row = _find_team_row(data, away_team_id)
    return _row_to_standing(home_row), _row_to_standing(away_row)
