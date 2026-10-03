import os
import json
import requests

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"].strip()
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-flash-latest:generateContent"
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
    }


def generate_persian_script(summary):
    prompt = f"""
تو داری دیالوگ یه پادکست ورزشی فارسی به اسم "موج فوتبال" رو می‌نویسی.
دو تا مجری داریم:
- "مجتبی" (مرد، کارشناس فنی، تحلیل تاکتیکی و آماری می‌ده)
- "پگاه" (زن، مجری اصلی، سوال می‌پرسه، نظر می‌ده، بعضی‌جاها با مجتبی بحث/مخالفت می‌کنه)

این اطلاعات ساختاریافته از بازی {summary['home_team']} {summary['score']} {summary['away_team']}
(مسابقات: {summary['league']}، ورزشگاه: {summary['venue']}) هست:

{json.dumps(summary, ensure_ascii=False, indent=2)}

یه دیالوگ طبیعی، محاوره‌ای و جذاب بین مجتبی و پ
