import os
import json
import requests
from datetime import datetime, timedelta, timezone
from teams import TEAMS, TEAM_PRIORITY

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"].strip()
BASE_URL = "https://soccer.highlightly.net/matches"

HEADERS = {
    "x-rapidapi-key": API_KEY,
}

ID_TO_FA = {team_id: fa_name for fa_name, team_id in TEAMS.items()}
OUR_IDS = set(ID_TO_FA.keys())

STATE_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "processed_matches.json")

DAILY_MATCH_LIMIT = 6

PRIORITY_RANK = {team_id: i for i, team_id in enumerate(TEAM_PRIORITY)}


def match_priority(home_id, away_id):
    home_in = home_id in PRIORITY_RANK
    away_in = away_id in PRIORITY_RANK
    group = 0 if (home_in and away_in) else 1
    ranks = [PRIORITY_RANK[t] for t in (home_id, away_id) if t in PRIORITY_RANK]
    best_rank = min(ranks) if ranks else 999
    return (group, best_rank)


def load_processed_ids():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def get_matches_for_team_date(team_id, date_str, side):
    params = {side: team_id, "date": date_str, "limit": 20, "offset": 0}
    resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json().get("data", [])


def find_finished_matches():
    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    dates_to_check = [str(yesterday)]

    processed_ids = load_processed_ids()
    finished = {}

    for team_id in TEAM_PRIORITY:
        for date_str in dates_to_check:
            for side in ("homeTeamId", "awayTeamId"):
                try:
                    matches = get_matches_for_team_date(team_id, date_str, side)
                except requests.RequestException as e:
                    print(f"خطا در گرفتن بازی‌های تیم {team_id} ({date_str}, {side}): {e}")
                    continue

                for m in matches:
                    home_id = m.get("homeTeam", {}).get("id")
                    away_id = m.get("awayTeam", {}).get("id")

                    state_desc = (m.get("state", {}) or {}).get("description", "") or ""
                    if "finish" not in state_desc.lower():
                        continue

                    match_id = m["id"]
                    if match_id in processed_ids:
                        continue

                    our_team_fa = ID_TO_FA.get(home_id) or ID_TO_FA.get(away_id)
                    if match_id not in finished:
                        finished[match_id] = {
                            "id": match_id,
                            "date": m["date"],
                            "league": m["league"]["name"],
                            "home": m["homeTeam"]["name"],
                            "away": m["awayTeam"]["name"],
                            "score": (m.get("state", {}) or {}).get("score", {}).get("current"),
                            "our_team_fa": our_team_fa,
                            "_priority": match_priority(home_id, away_id),
                        }

    sorted_matches = sorted(finished.values(), key=lambda x: x["_priority"])
    selected = sorted_matches[:DAILY_MATCH_LIMIT]
    for m in selected:
        del m["_priority"]

    return selected


if __name__ == "__main__":
    results = find_finished_matches()
    print(f"\n{len(results)} بازی تموم‌شده پیدا شد:\n")
    print(json.dumps(results, ensure_ascii=False, indent=2))
