import os
import json
import requests
from datetime import datetime, timedelta, timezone
from teams import TEAMS

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"]
BASE_URL = "https://soccer.highlightly.net/matches"
HEADERS = {"x-rapidapi-key": API_KEY}


def get_matches(team_id, date_str, side):
    params = {side: team_id, "date": date_str, "limit": 50, "offset": 0}
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("data", [])


def find_finished_matches():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    dates_to_check = [str(yesterday), str(today)]
    finished = {}

    for team_fa_name, team_id in TEAMS.items():
        for date_str in dates_to_check:
            for side in ("homeTeamId", "awayTeamId"):
                try:
                    matches = get_matches(team_id, date_str, side)
                except requests.RequestException as e:
                    print(f"خطا در گرفتن بازی‌های {team_fa_name} ({date_str}): {e}")
                    continue
                for m in matches:
                    state_desc = (m.get("state", {}) or {}).get("description", "") or ""
                    if "finish" in state_desc.lower():
                        match_id = m["id"]
                        if match_id not in finished:
                            finished[match_id] = {
                                "id": match_id,
                                "date": m["date"],
                                "league": m["league"]["name"],
                                "home": m["homeTeam"]["name"],
                                "away": m["awayTeam"]["name"],
                                "score": (m.get("state", {}) or {}).get("score", {}).get("current"),
                                "our_team_fa": team_fa_name,
                            }
    return list(finished.values())


if __name__ == "__main__":
    results = find_finished_matches()
    print(f"\n{len(results)} بازی تموم‌شده پیدا شد:\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))
