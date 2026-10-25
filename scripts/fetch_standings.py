import os
import json
import time
import requests

from teams import TEAMS

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"].strip()
BASE_URL = "https://soccer.highlightly.net/standings"
HEADERS = {"x-rapidapi-key": API_KEY}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODELS = ["gemini-flash-latest", "gemini-flash-lite-latest"]
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{}:generateContent"

KNOWN_FA = {str(v): k for k, v in TEAMS.items()}
_cache = {}


def get_standings(league_id, season):
    if not league_id or not season:
        return None
    key = (league_id, season)
    if key in _cache:
        return _cache[key]
    data = None
    for attempt in range(1, 4):
        try:
            resp = requests.get(BASE_URL, headers=HEADERS,
                                params={"leagueId": league_id, "season": season}, timeout=40)
            if resp.status_code == 429:
                print("سقف روزانه‌ی Highlightly تموم شده؛ جدول گرفته نشد.")
                break
            resp.raise_for_status()
            data = resp.json()
            break
        except requests.RequestException as e:
            print(f"خطا در گرفتن جدول لیگ {league_id}/{season} (تلاش {attempt}): {e}")
            time.sleep(10 * attempt)
    _cache[key] = data
    return data


def translate_team_names(names):
    names = list(dict.fromkeys(n for n in names if n))
    if not names:
        return {}
    if not GEMINI_API_KEY:
        return {n: n for n in names}
    prompt = (
        "Transliterate each football club or national team name below into Persian (Farsi) script, "
        "the way Persian sports media commonly write it. Return ONLY a JSON object "
        "mapping each original name to its Persian form (same keys as given).\n\n"
        + json.dumps(names, ensure_ascii=False)
    )
    for attempt in range(3):
        for model in GEMINI_MODELS:
            try:
                resp = requests.post(
                    GEMINI_URL.format(model) + "?key=" + GEMINI_API_KEY,
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"response_mime_type": "application/json"}},
                    timeout=60,
                )
                resp.raise_for_status()
                mapping = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                if isinstance(mapping, dict):
                    return {n: str(mapping.get(n) or n) for n in names}
            except Exception as e:  # noqa: BLE001
                print(f"ترجمه‌ی اسم تیم‌ها ({model}) ناموفق: {e}")
        time.sleep(8 * (attempt + 1))
    return {n: n for n in names}


def _num(v):
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(str(v).strip()))
        except ValueError:
            return None


def _row(row):
    team = row.get("team") or row.get("teamInfo") or {}
    if not isinstance(team, dict):
        team = {}
    team_id = team.get("id") or row.get("teamId")
    name = team.get("name") or row.get("teamName") or row.get("name") or "Unknown"
    logo = team.get("logo") or row.get("teamLogo") or team.get("crest") or ""

    sources = [row.get("total"), row.get("overall"), row.get("stats"), row]

    def find(*keys):
        for src in sources:
            if isinstance(src, dict):
                for k in keys:
                    if k in src and src[k] is not None:
                        return src[k]
        return None

    played = _num(find("games", "gamesPlayed", "played", "matchesPlayed", "matchPlayed"))
    won = _num(find("won", "wins", "win", "w"))
    drawn = _num(find("drawn", "draws", "draw", "tied", "d"))
    lost = _num(find("lost", "loses", "losses", "loss", "l"))
    gf = _num(find("scoredGoals", "goalsFor", "gf", "goalsScored"))
    ga = _num(find("receivedGoals", "goalsAgainst", "ga", "goalsConceded"))
    gd = _num(find("goalDifference", "gd", "diff"))
    if gd is None and gf is not None and ga is not None:
        gd = gf - ga
    points = _num(find("points", "pts", "point"))
    rank = _num(row.get("position") or row.get("rank") or row.get("standing") or row.get("pos") or row.get("place"))

    return {
        "rank": rank,
        "team_id": str(team_id) if team_id is not None else str(name),
        "name": name,
        "logo": logo,
        "played": played, "won": won, "drawn": drawn, "lost": lost,
        "gf": gf, "ga": ga, "gd": gd, "points": points,
    }


_TEAM_KEYS = ("team", "teamId", "teamInfo")
_RANK_KEYS = ("position", "rank", "standing", "pos", "place", "points", "pts", "total", "overall")


def _is_row(el):
    return isinstance(el, dict) and any(k in el for k in _TEAM_KEYS) and any(k in el for k in _RANK_KEYS)


def _find_tables(obj, out=None):
    """هر لیست از ردیف‌های جدول = یک جدول (برای لیگ‌های گروهی چندتا پیدا می‌شه)."""
    if out is None:
        out = []
    if isinstance(obj, list):
        rows = [e for e in obj if _is_row(e)]
        if len(rows) >= 2 and len(rows) >= 0.8 * len(obj):
            out.append(rows)
            return out
        for e in obj:
            _find_tables(e, out)
    elif isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (list, dict)):
                _find_tables(v, out)
    return out


def get_table_context(league_id, season, home_id, away_id):
    data = get_standings(league_id, season)
    if not data:
        return None
    hid, aid = str(home_id), str(away_id)

    chosen = None
    for rows in _find_tables(data):
        parsed, seen = [], set()
        for r in rows:
            p = _row(r)
            if p["team_id"] in seen:
                continue
            seen.add(p["team_id"])
            parsed.append(p)
        if hid in seen and aid in seen and (chosen is None or len(parsed) > len(chosen)):
            chosen = parsed
    if not chosen:
        print("جدولی که هر دو تیم توش باشن پیدا نشد؛ صحنه‌ی جدول ساخته نمی‌شه.")
        return None

    chosen.sort(key=lambda p: (p["rank"] if p["rank"] is not None else 10 ** 6, -(p["points"] or 0)))
    for i, p in enumerate(chosen, start=1):
        if p["rank"] is None:
            p["rank"] = i

    top8 = chosen[:8]
    extras = [p for p in chosen[8:] if p["team_id"] in (hid, aid)]

    shown = top8 + extras
    need = [p["name"] for p in shown if p["team_id"] not in KNOWN_FA]
    fa_map = translate_team_names(need)
    for p in shown:
        p["fa_name"] = KNOWN_FA.get(p["team_id"]) or fa_map.get(p["name"], p["name"])

    print(f"جدول لیگ: {len(chosen)} تیم | نمونه‌ی ردیف اول: {top8[0]}")
    return {"top8": top8, "extras": extras, "home_id": hid, "away_id": aid, "total_teams": len(chosen)}
