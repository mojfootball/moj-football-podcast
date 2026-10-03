import os
import requests

API_KEY = os.environ["HIGHLIGHTLY_API_KEY"]
HEADERS = {"x-rapidapi-key": API_KEY}


def get_match_details(match_id):
    url = f"https://soccer.highlightly.net/matches/{match_id}"
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data[0] if isinstance(data, list) else data
