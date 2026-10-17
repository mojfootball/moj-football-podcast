# fetch_standings.py
import requests
from bs4نهار import BeautifulSoup

# لینک‌های پیش‌فرض جدول لیگ‌های مهم در ورزش ۳
LEAGUE_URLS = {
    "persian gulf pro league": "https://www.varzesh3.com/table/league/1/%D6%B9%20%D9%84%DB%8C%DA%AF-%D8%A8%D8%B1%D8%AA%D8%B1-%D8%A7%DB%8C%D8%B1%D8%A7%D9%86",
    "premier league": "https://www.varzesh3.com/table/league/2/%D9%84%DB%8C%DA%AF-%D8%A8%D8%B1%D8%AA%D8%B1-%D8%A7%D9%86%DA%AF%D9%84%D8%B3%D8%AA%D8%A7%D9%86",
    "laliga": "https://www.varzesh3.com/table/league/3/%D9%84%DB%8C%DA%AF-%D8%A7%D8%B3%DBE%D9%86%DB%8C%D8%A7-%D9%84%D8%A7%D9%84%DB%8C%DA%AF%D8%A7",
    "serie a": "https://www.varzesh3.com/table/league/4/%D9%84%DB%8C%DA%AF-%D8%A7%DB%8C%D8%AA%D8%A7%D9%84%DB%8C%D8%A7-%D8%B3%D8%B1%DB%8C-%D8%A2",
    "bundesliga": "https://www.varzesh3.com/table/league/5/%D9%84%DB%8C%DA%AF-%D8%A2%D9%84%D9%85%D8%A7%D9%86-%D8%A8%D9%88%D9%86%D8%AF%D8%B3%D9%84%DB%8C%DA%AF%D8%A7",
    "ligue 1": "https://www.varzesh3.com/table/league/6/%D9%84%DB%8C%DA%AF-%D9%81%D8%B1%D8%A7%D9%86%D8%B3%D9%87",
    "champions league": "https://www.varzesh3.com/table/league/7/%D9%84%DB%8C%DA%AF-%D9%82%D9%87%D8%B1%D9%85%D8%A7%D9%86%D8%A7%D9%86-%D8%A7%D8%B1%D9%88%DBE"
}

def get_league_url_by_name(league_name):
    """نام لیگ را دریافت کرده و لینک مربوط به ورزش ۳ را برمی‌گرداند"""
    if not league_name:
        return None
    name = league_name.lower()
    for key, url in LEAGUE_URLS.items():
        if key in name:
            return url
    return None

def get_league_standings(league_url):
    """
    جدول رده‌بندی را از سایت ورزش ۳ با تمام جزئیات شامل:
    رتبه، نام تیم، تعداد بازی، برد، مساوی، باخت، گل زده، گل خورده، تفاضل گل و امتیاز استخراج می‌کند.
    """
    standings = []
    if not league_url:
        return standings
        
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(league_url, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'class': 'standings-table'})
        if not table:
            table = soup.find('table')
            
        if table:
            rows = table.find_all('tr')
            for rank, row in enumerate(rows[1:], start=1):
                cols = row.find_all('td')
                if len(cols) >= 8:
                    team_name = cols[1].get_text(strip=True)
                    try:
                        played = int(cols[2].get_text(strip=True) or 0)
                        win = int(cols[3].get_text(strip=True) or 0)
                        draw = int(cols[4].get_text(strip=True) or 0)
                        loss = int(cols[5].get_text(strip=True) or 0)
                        gf = int(cols[6].get_text(strip=True) or 0)
                        ga = int(cols[7].get_text(strip=True) or 0)
                        gd = int(cols[8].get_text(strip=True) or 0) if len(cols) > 8 else (gf - ga)
                        points = int(cols[9].get_text(strip=True) or cols[-1].get_text(strip=True) or 0)
                    except ValueError:
                        continue

                    standings.append({
                        "rank": rank,
                        "team": team_name,
                        "played": played,
                        "win": win,
                        "draw": draw,
                        "loss": loss,
                        "gf": gf,
                        "ga": ga,
                        "gd": gd,
                        "points": points
                    })
        
        return standings

    except Exception as e:
        print(f"خطا در اسکرپ جدول رده‌بندی از ورزش ۳: {e}")
        return []

def get_team_standing_info(league_name_or_url, team_name):
    """
    اطلاعات کامل یک تیم خاص را از جدول لیگ پیدا کرده و برمی‌گرداند.
    """
    url = get_league_url_by_name(league_name_or_url) or league_name_or_url
    standings = get_league_standings(url)
    for team in standings:
        if team_name.lower() in team["team"].lower() or team["team"].lower() in team_name.lower():
            return team
    return None
