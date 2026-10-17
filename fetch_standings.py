# fetch_standings.py
import requests
from bs4 import BeautifulSoup

def get_league_standings(league_name):
    """
    اطلاعات جدول رده‌بندی لیگ را با جزئیات کامل شامل:
    رتبه، نام تیم، تعداد بازی، برد، مساوی، باخت، گل زده، گل خورده، تفاضل گل و امتیاز استخراج می‌کند.
    """
    standings = []
    try:
        print(f"در حال دریافت جدول رده‌بندی برای: {league_name}...")
        
        # نمونه ساختار داده‌ای که برای هر تیم باید استخراج و ذخیره شود:
        # هر تیم شامل یک دیکشنری با کلیدهای زیر خواهد بود:
        # {
        #     "rank": 1,          # رتبه در جدول
        #     "team": "نام تیم",    # نام تیم
        #     "played": 0,        # تعداد بازی
        #     "win": 0,           # برد
        #     "draw": 0,          # مساوی
        #     "loss": 0,          # باخت
        #     "gf": 0,            # گل زده (Goals For)
        #     "ga": 0,            # گل خورده (Goals Against)
        #     "gd": 0,            # تفاضل گل (Goal Difference)
        #     "points": 0         # امتیاز
        # }
        
        # نکته: بسته به سایتی که برای اسکرپ انتخاب می‌کنید (مثل ورزش۳ یا منابع ورزشی دیگر)، 
        # می‌توانید پارس‌کننده BeautifulSoup را اینجا بنویسید.
        
        return standings

    except Exception as e:
        print(f"خطا در دریافت یا پردازش جدول رده‌بندی: {e}")
        return []

def get_team_standing_info(league_name, team_name):
    """
    اطلاعات کامل یک تیم خاص (مثل رتبه، امتیاز، تفاضل و...) را از جدول لیگ پیدا کرده و برمی‌گرداند.
    """
    standings = get_league_standings(league_name)
    for team in standings:
        if team_name.lower() in team["team"].lower() or team["team"].lower() in team_name.lower():
            return team
    return None

if __name__ == "__main__":
    # تست ساده ماژول
    print(get_league_standings("Premier League"))
