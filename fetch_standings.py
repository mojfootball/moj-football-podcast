# fetch_standings.py
import requests
from bs4 import BeautifulSoup

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
        
        # پیدا کردن جدول رده‌بندی در صفحه ورزش ۳
        table = soup.find('table', {'class': 'standings-table'})
        if not table:
            table = soup.find('table')
            
        if table:
            rows = table.find_all('tr')
            for rank, row in enumerate(rows[1:], start=1):  # رد کردن سطر هدر جدول
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

def get_team_standing_info(league_url, team_name):
    """
    اطلاعات کامل یک تیم خاص را از جدول لیگ پیدا کرده و برمی‌گرداند.
    """
    standings = get_league_standings(league_url)
    for team in standings:
        if team_name.lower() in team["team"].lower() or team["team"].lower() in team_name.lower():
            return team
    return None
