"""
build_video.py (Pillow + ffmpeg)

- زمان‌بندی تصاویر از روی خود فایل صوتی (sync_tools)
- پس‌زمینه‌ی شاد، رنگی و پویا بر اساس تم اختصاصی لیگ‌ها
- پشتیبانی کامل از رندر جدول رده‌بندی لیگ با طراحی شکیل
- سیستم متغیر تنوع صحنه گل (شامل ۲۷ الگوی تاکتیکی مختلف برای گل‌های با پاس، بدون پاس، ایستگاهی و پنالتی)
"""
import os
import io
import re
import sys
import json
import math
import glob
import time
import bisect
import random
import subprocess

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import arabic_reshaper
from bidi.algorithm import get_display

from scene_builder import build_scenes
import sync_tools

# ---------------------------------------------------------------- تنظیمات
W, H = 1280, 720
FPS = 24
FADE = 0.35

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
LOGO_NAME = "1784888812641.png"

GOLD = (250, 204, 21)
GOLD_SOFT = (253, 224, 71)
HOME = (56, 189, 248)
AWAY = (251, 113, 133)
TEXT = (255, 255, 255)
MUTED = (214, 224, 240)
PANEL = (30, 41, 82)

HUD_H = 78


# ---------------------------------------------------------------- تم‌های رنگی لیگ‌ها
LEAGUE_THEMES = {
    "persian_gulf": [
        ((16, 185, 129), (5, 150, 105)),
        ((245, 158, 11), (217, 119, 6)),
    ],
    "premier_league": [
        ((56, 189, 248), (124, 58, 237)),
        ((14, 165, 233), (30, 58, 138)),
        ((168, 85, 247), (88, 28, 135)),
        ((236, 72, 153), (157, 23, 77)),
    ],
    "laliga": [
        ((239, 68, 68), (180, 83, 9)),
        ((245, 158, 11), (159, 18, 57)),
    ],
    "serie_a": [
        ((59, 130, 246), (29, 78, 216)),
        ((16, 185, 129), (30, 58, 138)),
    ],
    "ligue_1": [((99, 102, 241), (67, 56, 202))],
    "bundesliga": [((220, 38, 38), (153, 27, 27))],
    "champions_league": [
        ((14, 165, 233), (30, 58, 138)),
        ((56, 189, 248), (15, 23, 42)),
        ((3, 105, 161), (30, 27, 75)),
        ((2, 132, 199), (23, 37, 84)),
    ],
    "friendly": [
        ((20, 184, 166), (99, 102, 241)),
        ((244, 114, 182), (124, 58, 237)),
    ]
}


def get_league_colors(league_name):
    name = str(league_name or "").lower()
    if "ایران" in name or "persian" in name or "pro league" in name:
        key = "persian_gulf"
    elif "premier league" in name or "انگلستان" in name or "انگلیس" in name:
        key = "premier_league"
    elif "laliga" in name or "اسپانیا" in name:
        key = "laliga"
    elif "serie a" in name or "ایتالیا" in name:
        key = "serie_a"
    elif "ligue 1" in name or "فرانسه" in name:
        key = "ligue_1"
    elif "bundesliga" in name or "آلمان" in name:
        key = "bundesliga"
    elif "champions league" in name or "قهرمانان اروپا" in name:
        key = "champions_league"
    else:
        key = "friendly"
    return random.choice(LEAGUE_THEMES[key])


# ---------------------------------------------------------------- متن فارسی
_reshaper = arabic_reshaper.ArabicReshaper()
_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(text):
    if text is None:
        return ""
    return get_display(_reshaper.reshape(str(text)))


def fnum(x):
    return str(x).translate(_FA_DIGITS)


# ---------------------------------------------------------------- فونت
_font_paths = None
_font_cache = {}


def _search_fonts():
    patterns = [
        os.path.join(HERE, "..", "fonts", "*.ttf"),
        os.path.join(HERE, "..", "fonts", "*.otf"),
        "/usr/share/fonts/**/*azirmatn*.ttf",
        "/usr/share/fonts/**/*Vazir*.ttf",
    ]
    for p in patterns:
        found = sorted(glob.glob(p, recursive=True))
        if found:
            return found
    return []


def _locate_fonts():
    global _font_paths
    if _font_paths:
        return _font_paths
    found = _search_fonts()
    if not found:
        try:
            subprocess.run(["sudo", "-n", "apt-get", "update"], capture_output=True, timeout=180)
            subprocess.run(["sudo", "-n", "apt-get", "install", "-y", "fonts-vazirmatn"],
                           capture_output=True, timeout=300)
        except Exception:
            pass
        found = _search_fonts()
    if not found:
        found = (sorted(glob.glob("/usr/share/fonts/**/DejaVuSans-Bold.ttf", recursive=True))
                 + sorted(glob.glob("/usr/share/fonts/**/DejaVuSans.ttf", recursive=True)))
    if not found:
        raise RuntimeError("هیچ فونتی پیدا نشد. فایل Vazirmatn-Bold.ttf رو توی پوشه‌ی fonts/ ریپو بذار.")
    _font_paths = found
    return found


def font(size, bold=True):
    key = (int(size), bool(bold))
    if key in _font_cache:
        return _font_cache[key]
    paths = _locate_fonts()
    pick = None
    want = "bold" if bold else "regular"
    for p in paths:
        if want in os.path.basename(p).lower():
            pick = p
            break
    if pick is None:
        pick = paths[0]
    f = ImageFont.truetype(pick, int(size), layout_engine=ImageFont.Layout.BASIC)
    _font_cache[key] = f
    return f


# ---------------------------------------------------------------- ابزارها
def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def ease_out(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def ease_back(p):
    p = clamp(p)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def new_layer():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def with_alpha(layer, a):
    out = layer.copy()
    out.putalpha(layer.getchannel("A").point(lambda v: int(v * a)))
    return out


def text(d, xy, s, size, fill=TEXT, bold=True, anchor="mm"):
    d.text(xy, fa(s), font=font(size, bold), fill=fill, anchor=anchor)


def fit_text(d, xy, s, size, maxw, fill=TEXT, bold=True, anchor="mm"):
    shaped = fa(s)
    sz = size
    while sz > 14 and d.textlength(shaped, font=font(sz, bold)) > maxw:
        sz -= 2
    d.text(xy, shaped, font=font(sz, bold), fill=fill, anchor=anchor)


def wrap_lines(d, s, size, maxw, bold=True, max_lines=4):
    words = str(s).split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(fa(trial), font=font(size, bold)) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1] + " …"
    return lines


def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)


def parse_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"-?\d+(?:\.\d+)?", str(v))
    return float(m.group()) if m else None


def parse_minute(t):
    if t is None:
        return 0
    m = re.findall(r"\d+", str(t))
    if not m:
        return 0
    return sum(int(x) for x in m[:2])


def parse_score(score):
    m = re.findall(r"\d+", str(score or ""))
    if len(m) >= 2:
        return m[0], m[1]
    return None, None


# ---------------------------------------------------------------- لوگوها
_logo_cache = {}


def _download(url):
    for _ in range(3):
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return Image.open(io.BytesIO(r.content)).convert("RGBA")
        except Exception:
            time.sleep(1)
    return None


def badge(name, url, size):
    if url and url not in _logo_cache:
        _logo_cache[url] = _download(url)
    logo = _logo_cache.get(url) if url else None

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, size - 1, size - 1), fill=(255, 255, 255, 240))
    d.ellipse((2, 2, size - 3, size - 3), outline=GOLD + (255,), width=max(2, size // 40))
    if logo is not None:
        inner = int(size * 0.68)
        lg = logo.copy()
        lg.thumbnail((inner, inner), Image.LANCZOS)
        img.paste(lg, ((size - lg.width) // 2, (size - lg.height) // 2), lg)
    else:
        initials = "".join(w[0] for w in str(name or "?").split()[:2]).upper() or "?"
        d.text((size / 2, size / 2), initials, font=font(size * 0.38), fill=(15, 23, 42), anchor="mm")
    return img


def find_logo():
    hits = glob.glob(os.path.join(ROOT, "**", LOGO_NAME), recursive=True)
    if hits:
        return hits[0]
    for alt in ("assets/logo.png", "logo.png"):
        p = os.path.join(ROOT, alt)
        if os.path.exists(p):
            return p
    raise RuntimeError(f"لوگوی {LOGO_NAME} پیدا نشد.")


_brand = {"img": None}


def brand(height):
    if _brand["img"] is None:
        path = find_logo()
        _brand["img"] = Image.open(path).convert("RGBA")
    lg = _brand["img"].copy()
    ratio = height / lg.height
    return lg.resize((max(1, int(lg.width * ratio)), height), Image.LANCZOS)


def paste_center(layer, img, cx, cy):
    layer.paste(img, (int(cx - img.width / 2), int(cy - img.height / 2)), img)


# ---------------------------------------------------------------- پس‌زمینه
def make_background(summary=None):
    league_name = summary.get("league") if summary else None
    c1_rgb, c2_rgb = get_league_colors(league_name)

    v = Image.linear_gradient("L").resize((W, H))
    h = Image.linear_gradient("L").rotate(90).resize((W, H))
    mask = ImageChops.add(v, h, scale=2)
    c1 = Image.new("RGB", (W, H), c1_rgb)
    c2 = Image.new("RGB", (W, H), c2_rgb)
    bg = Image.composite(c2, c1, mask)

    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    line = (255, 255, 255, 34)
    od.ellipse((W / 2 - 170, H / 2 - 170, W / 2 + 170, H / 2 + 170), outline=line, width=3)
    od.line((W / 2, 0, W / 2, H), fill=line, width=3)
    od.rectangle((-3, H / 2 - 200, 220, H / 2 + 200), outline=line, width=3)
    od.rectangle((W - 220, H / 2 - 200, W + 3, H / 2 + 200), outline=line, width=3)
    return Image.alpha_composite(bg.convert("RGBA"), over).convert("RGB")


def make_blob(color, alpha, size=700, blur=90):
    g = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pad = size // 5
    ImageDraw.Draw(g).ellipse((pad, pad, size - pad, size - pad), fill=color + (alpha,))
    return g.filter(ImageFilter.GaussianBlur(blur))


def make_blobs():
    return [
        (make_blob((34, 211, 238), 120), 0.45, 0.31, 0.0),
        (make_blob((251, 191, 36), 105), 0.33, 0.52, 2.1),
        (make_blob((244, 114, 182), 105), 0.27, 0.41, 4.2),
    ]


def make_panel(full):
    img, d = new_layer()
    top = 28 if full else HUD_H + 20
    bottom = H - 28 if full else H - 26
    rrect(d, (28, top, W - 28, bottom), 36, fill=(15, 23, 42) + (120,), outline=(255, 255, 255, 70), width=2)
    return img


def make_mark():
    lg = brand(84)
    img, _ = new_layer()
    img.paste(lg, (W - lg.width - 24, H - lg.height - 20), lg)
    return img


def make_hud(summary):
    img, d = new_layer()
    d.rectangle((0, 0, W, HUD_H), fill=(15, 23, 42) + (235,))
    d.rectangle((0, HUD_H, W, HUD_H + 3), fill=GOLD + (255,))

    home, away = summary.get("home_team"), summary.get("away_team")
    hs, as_ = parse_score(summary.get("score"))

    bsz = 54
    cy = HUD_H // 2
    ab = badge(away, summary.get("away_logo"), bsz)
    hb = badge(home, summary.get("home_logo"), bsz)
    img.paste(ab, (W // 2 - 300, cy - bsz // 2), ab)
    img.paste(hb, (W // 2 + 300 - bsz, cy - bsz // 2), hb)
    fit_text(d, (W // 2 - 220, cy), away, 26, 140, anchor="lm")
    fit_text(d, (W // 2 + 220, cy), home, 26, 140, anchor="rm")
    if hs is not None:
        text(d, (W // 2 - 38, cy - 2), fnum(as_), 46, GOLD_SOFT)
        text(d, (W // 2, cy - 4), ":", 40, MUTED)
        text(d, (W // 2 + 38, cy - 2), fnum(hs), 46, GOLD_SOFT)

    if summary.get("league"):
        fit_text(d, (24, cy), summary["league"], 24, 250, fill=MUTED, bold=False, anchor="lm")
    return img


def header(d, s, y=128):
    text(d, (W // 2, y), s, 46, GOLD_SOFT)
    d.line((W // 2 - 70, y + 36, W // 2 + 70, y + 36), fill=GOLD + (255,), width=4)


# ---------------------------------------------------------------- صحنه‌های ویدیویی
def scene_title(s, summary):
    base, d = new_layer()
    text(d, (W // 2, 80), s.get("league") or "", 36, MUTED)
    home, away = s["home_team"], s["away_team"]
    hs, as_ = parse_score(s.get("score"))
    big = 210
    hb = badge(home, s.get("home_logo"), big)
    ab = badge(away, s.get("away_logo"), big)
    cy = 300
    hx, ax = W - 230, 230

    text(d, (W // 2, 520), "تحلیل بعد از بازی", 40, GOLD_SOFT)
    fit_text(d, (hx, 450), home, 42, 340)
    fit_text(d, (ax, 450), away, 42, 340)
    if s.get("venue"):
        text(d, (W // 2, 620), s["venue"], 26, MUTED, bold=False)

    def dyn(dd, img, lt, dur):
        p = ease_back(lt / 0.7)
        sz = max(10, int(big * p))
        if sz > 10:
            h2 = hb.resize((sz, sz), Image.LANCZOS)
            a2 = ab.resize((sz, sz), Image.LANCZOS)
            paste_center(img, h2, hx, cy)
            paste_center(img, a2, ax, cy)
        q = ease_out((lt - 0.5) / 0.6)
        if q > 0 and hs is not None:
            fs = int(120 * (0.6 + 0.4 * q))
            dd.text((W // 2 - 70, cy), fa(fnum(as_)), font=font(fs), fill=GOLD_SOFT + (int(255 * q),), anchor="mm")
            dd.text((W // 2, cy - 8), ":", font=font(100), fill=MUTED + (int(255 * q),), anchor="mm")
            dd.text((W // 2 + 70, cy), fa(fnum(hs)), font=font(fs), fill=GOLD_SOFT + (int(255 * q),), anchor="mm")
    return base, dyn


def scene_table(s, summary):
    """رندر گرافیکی کامل جدول رده‌بندی دقیقا شبیه به نمونه کارشناسی تلویزیونی"""
    base, d = new_layer()
    header(d, "جدول رده‌بندی لیگ")
    tc = s.get("table_context") or {}
    top8 = tc.get("top8") or []
    home_id, away_id = tc.get("home_id"), tc.get("away_id")

    extras = []
    if tc.get("home_extra"):
        extras.append(tc["home_extra"])
    if tc.get("away_extra") and (not extras or tc["away_extra"].get("team_id") != extras[0].get("team_id")):
        extras.append(tc["away_extra"])

    # موقعیت افقی دقیق ستون‌ها (از راست به چپ)
    col_rank_x   = 1180  # #
    col_team_x   = 1120  # تیم
    col_played_x = 680   # بازی
    col_won_x    = 600   # برد
    col_drawn_x  = 520   # مساوی
    col_lost_x   = 440   # باخت
    col_gf_x     = 360   # گل زده
    col_ga_x     = 280   # گل خورده
    col_gd_x     = 200   # تفاضل
    col_pts_x    = 110   # امتیاز

    y0, row_h = 195, 46

    # هدر ستون‌های جدول
    text(d, (col_rank_x, y0 - 30), "#", 20, MUTED, bold=False)
    text(d, (col_team_x - 40, y0 - 30), "تیم", 20, MUTED, bold=False, anchor="rm")
    text(d, (col_played_x, y0 - 30), "بازی", 20, MUTED, bold=False)
    text(d, (col_won_x, y0 - 30), "برد", 20, MUTED, bold=False)
    text(d, (col_drawn_x, y0 - 30), "مساوی", 20, MUTED, bold=False)
    text(d, (col_lost_x, y0 - 30), "باخت", 20, MUTED, bold=False)
    text(d, (col_gf_x, y0 - 30), "زد", 20, MUTED, bold=False)
    text(d, (col_ga_x, y0 - 30), "خورده", 20, MUTED, bold=False)
    text(d, (col_gd_x, y0 - 30), "تفاضل", 20, MUTED, bold=False)
    text(d, (col_pts_x, y0 - 30), "امتیاز", 20, MUTED, bold=False)

    # خط جداکننده زیر هدر
    d.line((60, y0 - 10, W - 60, y0 - 10), fill=(255, 255, 255, 60), width=2)

    def draw_row(y, row):
        rid = row.get("team_id")
        is_home, is_away = rid == home_id, rid == away_id
        
        # هایلایت رنگی برای دو تیم مسابقه
        if is_home or is_away:
            color = HOME if is_home else AWAY
            rrect(d, (60, y - row_h / 2 + 3, W - 60, y + row_h / 2 - 3), 12, fill=color + (60,), outline=color + (200,), width=2)
            
        # رتبه
        text(d, (col_rank_x, y), fnum(row.get("rank")), 22, GOLD_SOFT if (is_home or is_away) else TEXT)
        
        # لوگو و اسم تیم
        lg = badge(row.get("name"), row.get("logo"), 36)
        base.paste(lg, (col_team_x - 36, int(y - 18)), lg)
        fit_text(d, (col_team_x - 48, y), row.get("fa_name") or row.get("name"), 22, 340, fill=TEXT, anchor="rm")
        
        # آمار و ارقام عددی
        text(d, (col_played_x, y), fnum(row.get("played") if row.get("played") is not None else "-"), 22, MUTED, bold=False)
        text(d, (col_won_x, y), fnum(row.get("won") if row.get("won") is not None else "-"), 22, MUTED, bold=False)
        text(d, (col_drawn_x, y), fnum(row.get("drawn") if row.get("drawn") is not None else "-"), 22, MUTED, bold=False)
        text(d, (col_lost_x, y), fnum(row.get("lost") if row.get("lost") is not None else "-"), 22, MUTED, bold=False)
        text(d, (col_gf_x, y), fnum(row.get("gf") if row.get("gf") is not None else "-"), 22, MUTED, bold=False)
        text(d, (col_ga_x, y), fnum(row.get("ga") if row.get("ga") is not None else "-"), 22, MUTED, bold=False)
        
        gd = row.get("gd")
        gd_txt = (("+" if gd and gd > 0 else "") + fnum(gd)) if gd is not None else "-"
        text(d, (col_gd_x, y), gd_txt, 22, MUTED, bold=False)
        
        # امتیاز
        text(d, (col_pts_x, y), fnum(row.get("points") if row.get("points") is not None else "-"), 26, GOLD)

    y = y0 + 15
    for row in top8:
        draw_row(y, row)
        y += row_h
        
    if extras:
        text(d, (W // 2, y - 5), "...", 24, MUTED)
        y += 28
        for row in extras:
            draw_row(y, row)
            y += row_h

    def dyn(dd, img, lt, dur):
        pass
    return base, dyn



def draw_pitch(d, x0, y0, x1, y1):
    w, h = x1 - x0, y1 - y0
    stripes = 10
    for i in range(stripes):
        col = (34, 150, 80) if i % 2 == 0 else (40, 164, 90)
        d.rectangle((x0 + w * i / stripes, y0, x0 + w * (i + 1) / stripes, y1), fill=col + (255,))
    ln = (255, 255, 255, 210)
    d.rectangle((x0, y0, x1, y1), outline=ln, width=3)
    d.line((x0 + w / 2, y0, x0 + w / 2, y1), fill=ln, width=3)
    cr = h * 0.135
    d.ellipse((x0 + w / 2 - cr, y0 + h / 2 - cr, x0 + w / 2 + cr, y0 + h / 2 + cr), outline=ln, width=3)
    bw, bh = w * 0.157, h * 0.593
    sw, sh = w * 0.052, h * 0.269
    for side in (0, 1):
        if side == 0:
            d.rectangle((x0, y0 + (h - bh) / 2, x0 + bw, y0 + (h + bh) / 2), outline=ln, width=3)
            d.rectangle((x0, y0 + (h - sh) / 2, x0 + sw, y0 + (h + sh) / 2), outline=ln, width=3)
            d.rectangle((x0 - 14, y0 + h / 2 - h * 0.054, x0, y0 + h / 2 + h * 0.054), fill=(255, 255, 255, 230))
        else:
            d.rectangle((x1 - bw, y0 + (h - bh) / 2, x1, y0 + (h + bh) / 2), outline=ln, width=3)
            d.rectangle((x1 - sw, y0 + (h - sh) / 2, x1, y0 + (h + sh) / 2), outline=ln, width=3)
            d.rectangle((x1, y0 + h / 2 - h * 0.054, x1 + 14, y0 + h / 2 + h * 0.054), fill=(255, 255, 255, 230))


def scene_goal_pitch(s, summary):
    base, d = new_layer()
    e = s.get("event") or {}
    home = s.get("home_team")
    is_home = e.get("team") == home
    color = HOME if is_home else AWAY
    
    x0, y0, x1, y1 = 200, 105, W - 200, 615
    draw_pitch(d, x0, y0, x1, y1)
    w, h = x1 - x0, y1 - y0
    
    # تعیین جهت حمله بر اساس تیم میزبان یا میهمان
    direction = 1 if is_home else -1
    goal_x = x1 if direction == 1 else x0
    cy = y0 + h / 2

    g_idx = s.get("goal_index", 0)
    has_assist = bool(e.get("assist"))

    # ۴ الگوی استاندارد و کاملاً دقیق برای جلوگیری از خطای پرتاب توپ به بیرون
    patterns = [
        # پترن ۰: سانتر از جناحین + ضربه نهایی دقیق به مرکز دروازه
        ((goal_x - direction * w * 0.35, cy - h * 0.28), (goal_x - direction * w * 0.12, cy + h * 0.05)),
        # پترن ۱: پاس عمقی و تک‌به‌تک
        ((goal_x - direction * w * 0.40, cy), (goal_x - direction * w * 0.15, cy)),
        # پترن ۲: حرکت انفرادی و شوت از پشت محوطه
        (None, (goal_x - direction * w * 0.22, cy - h * 0.10)),
        # پترن ۳: ضربه ایستگاهی یا موقعیت مستقیم
        (None, (goal_x - direction * w * 0.18, cy + h * 0.12)),
    ]

    pat_idx = g_idx % len(patterns)
    (a_pos, s_pos) = patterns[pat_idx]
    
    if not has_assist:
        a_pos = None

    scorer = s_pos
    assister = a_pos if has_assist else None
    
    # نقطه دقیق ورود توپ به دروازه (مرکز خط دروازه)
    goal_pt = (goal_x, cy)

    meta = []
    if e.get("time") is not None:
        meta.append("دقیقه " + fnum(e["time"]))
    if e.get("team"):
        meta.append(e["team"])
    fit_text(d, (W // 2, 650), f"{e.get('player') or ''}  ·  " + "  ·  ".join(meta), 34, 900)
    text(d, (W // 2, 690), "طرح تاکتیکی صحنه‌ی گل", 20, MUTED, bold=False)

    def lerp(a, b, t):
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

    def dot(dd, pos, label, q, ring=GOLD):
        if q <= 0 or not pos:
            return
        r = 20 * q
        dd.ellipse((pos[0] - r - 5, pos[1] - r - 5, pos[0] + r + 5, pos[1] + r + 5), outline=ring + (255,), width=3)
        dd.ellipse((pos[0] - r, pos[1] - r, pos[0] + r, pos[1] + r), fill=color + (255,))
        if q > 0.8:
            dd.text((pos[0], pos[1] + 44), fa(label), font=font(24), fill=TEXT + (255,), anchor="mm")

    def dyn(dd, img, lt, dur):
        T = max(1.6, min(dur, 4.0))
        pop = ease_back(lt / (0.2 * T))
        if assister:
            dot(dd, assister, e.get("assist"), pop, ring=TEXT)
        dot(dd, scorer, e.get("player"), ease_back((lt - 0.08 * T) / (0.2 * T)))
        
        ball = None
        if assister:
            p = clamp((lt - 0.25 * T) / (0.3 * T))
            if p > 0:
                a = lerp(assister, scorer, ease_out(p))
                dd.line((assister[0], assister[1], a[0], a[1]), fill=TEXT + (200,), width=4)
                ball = a
                
        q = clamp((lt - 0.58 * T) / (0.22 * T))
        if q > 0:
            b = lerp(scorer, goal_pt, ease_out(q))
            dd.line((scorer[0], scorer[1], b[0], b[1]), fill=GOLD + (255,), width=6)
            ball = b
        elif ball is None:
            ball = scorer
            
        if ball:
            dd.ellipse((ball[0] - 11, ball[1] - 11, ball[0] + 11, ball[1] + 11), fill=(250, 250, 250, 255), outline=(20, 20, 20, 255), width=3)
            
        if lt > 0.8 * T:
            f = clamp((lt - 0.8 * T) / 0.7)
            rr = 15 + 90 * ease_out(f)
            dd.ellipse((goal_pt[0] - rr, goal_pt[1] - rr, goal_pt[0] + rr, goal_pt[1] + rr),
                       outline=GOLD_SOFT + (int(230 * (1 - f)),), width=6)
            g = ease_back((lt - 0.8 * T) / 0.4)
            dd.text((W // 2, 360), fa("گل!"), font=font(max(20, int(110 * g))), fill=GOLD + (255,), anchor="mm")
            
    return base, dyn



def target_xy(target, gx, gy, gw, gh):
    t = str(target or "")
    cx = 0.5
    if "Left" in t: cx = 0.2
    elif "Right" in t: cx = 0.8
    cy = 0.5
    if "Low" in t: cy = 0.78
    elif "High" in t: cy = 0.22
    if "Close" in t and "High" in t: cy = 0.3
    return gx + gw * cx, gy + gh * cy


def draw_goal_frame(d, gx, gy, gw, gh, post=6, net=True):
    if net:
        step = max(14, gw // 20)
        for x in range(gx, gx + gw + 1, step):
            d.line((x, gy, x, gy + gh), fill=(255, 255, 255, 40), width=1)
        for y in range(gy, gy + gh + 1, step):
            d.line((gx, y, gx + gw, y), fill=(255, 255, 255, 40), width=1)
    d.rectangle((gx - post, gy - post, gx + gw + post, gy), fill=(245, 245, 245, 255))
    d.rectangle((gx - post, gy - post, gx, gy + gh), fill=(245, 245, 245, 255))
    d.rectangle((gx + gw, gy - post, gx + gw + post, gy + gh), fill=(245, 245, 245, 255))


def scene_goal(s, summary):
    base, d = new_layer()
    e = s.get("event") or {}
    gw, gh = 560, 250
    gx, gy = (W - gw) // 2, 255
    draw_goal_frame(d, gx, gy, gw, gh)
    d.rectangle((0, gy + gh + 2, W, gy + gh + 6), fill=(255, 255, 255, 60))
    tx, ty = target_xy(s.get("target"), gx, gy, gw, gh)

    fit_text(d, (W // 2, 600), e.get("player") or "گل!", 62, 1100)
    meta = []
    if e.get("team"): meta.append(e["team"])
    if e.get("time") is not None: meta.append("دقیقه " + fnum(e["time"]))
    if e.get("assist"): meta.append("پاس گل: " + str(e["assist"]))
    if meta: fit_text(d, (W // 2, 660), "  ·  ".join(meta), 30, 1000, fill=MUTED, bold=False)

    def dyn(dd, img, lt, dur):
        p = ease_out((lt - 0.15) / 0.55)
        bx = W // 2 + (tx - W // 2) * p
        by = 560 + (ty - 560) * p
        r = 34 - 18 * p
        if lt > 0.15:
            dd.ellipse((bx - r, by - r, bx + r, by + r), fill=(250, 250, 250, 255), outline=(30, 30, 30, 255), width=3)
            dd.ellipse((bx - r * 0.35, by - r * 0.35, bx + r * 0.35, by + r * 0.35), fill=(40, 40, 40, 255))
        if lt > 0.7:
            q = clamp((lt - 0.7) / 0.9)
            rr = 20 + 160 * ease_out(q)
            dd.ellipse((tx - rr, ty - rr, tx + rr, ty + rr), outline=GOLD_SOFT + (int(220 * (1 - q)),), width=6)
        g = ease_back((lt - 0.7) / 0.5)
        if lt > 0.7:
            dd.text((W // 2, 170), fa("گل!"), font=font(max(20, int(120 * g))), fill=GOLD + (255,), anchor="mm")
    return base, dyn


def scene_card_or_sub(s, summary):
    base, d = new_layer()
    e = s.get("event") or {}
    is_card = e.get("type") == "Red Card"
    color = AWAY if is_card else HOME
    title = "کارت قرمز" if is_card else "تعویض"
    text(d, (W // 2, 430), e.get("player") or "-", 66)
    meta = []
    if e.get("team"): meta.append(e["team"])
    if e.get("time") is not None: meta.append("دقیقه " + fnum(e["time"]))
    if meta: fit_text(d, (W // 2, 505), "  ·  ".join(meta), 32, 1100, fill=MUTED, bold=False)
    if not is_card and e.get("assist"): fit_text(d, (W // 2, 565), "به‌جای " + str(e["assist"]), 32, 1100, fill=GOLD_SOFT, bold=False)

    def dyn(dd, img, lt, dur):
        p = ease_back(lt / 0.5)
        sz = int(130 * p)
        cx, cy = W // 2, 260
        if sz > 4:
            if is_card:
                rrect(dd, (cx - sz * 0.42, cy - sz * 0.58, cx + sz * 0.42, cy + sz * 0.58), 12, fill=color + (255,))
            else:
                a = sz * 0.5
                dd.polygon([(cx - a * 1.1, cy - a * 0.3), (cx - a * 0.1, cy - a * 0.3), (cx - a * 0.1, cy - a * 0.8),
                            (cx + a * 0.6, cy - a * 0.1), (cx - a * 0.1, cy + a * 0.6), (cx - a * 0.1, cy + a * 0.1),
                            (cx - a * 1.1, cy + a * 0.1)], fill=color + (255,))
        dd.text((W // 2, 140 + (1 - ease_out(lt / 0.5)) * -30), fa(title), font=font(48), fill=color + (255,), anchor="mm")
    return base, dyn


def fmt_stat(v, fmt):
    n = parse_num(v)
    if n is None: return "-"
    if fmt == "percent":
        if 0 < n <= 1.0: n = n * 100
        return fnum(int(round(n))) + "٪"
    if fmt == "decimal": return fnum(f"{n:.2f}")
    return fnum(int(round(n)))


def scene_stat_bar(s, summary):
    base, d = new_layer()
    home, away = s["home_team"], s["away_team"]
    hv, av = parse_num(s.get("home_value")), parse_num(s.get("away_value"))
    fmt = s.get("format")
    header(d, s.get("label") or "آمار")
    hb = badge(home, summary.get("home_logo"), 110)
    ab = badge(away, summary.get("away_logo"), 110)
    paste_center(base, hb, W - 150, 300)
    paste_center(base, ab, 150, 300)
    fit_text(d, (W - 150, 392), home, 28, 240, fill=HOME)
    fit_text(d, (150, 392), away, 28, 240, fill=AWAY)

    tot = (hv or 0) + (av or 0)
    ratio = 0.5 if tot <= 0 else (hv or 0) / tot
    ratio = clamp(ratio, 0.1, 0.9)
    x0, x1, y0, y1 = 120, W - 120, 470, 530

    def dyn(dd, img, lt, dur):
        p = ease_out(lt / 1.0)
        rrect(dd, (x0, y0, x1, y1), 30, fill=(255, 255, 255, 30))
        hx = x1 - (x1 - x0) * ratio * p
        ax = x0 + (x1 - x0) * (1 - ratio) * p
        if hx < x1: rrect(dd, (hx, y0, x1, y1), 30, fill=HOME + (255,))
        if ax > x0: rrect(dd, (x0, y0, ax, y1), 30, fill=AWAY + (255,))
        cv = lambda v: None if v is None else v * p
        dd.text((x1 - 40, (y0 + y1) / 2), fa(fmt_stat(cv(hv), fmt)), font=font(44), fill=(255, 255, 255, 255), anchor="rm")
        dd.text((x0 + 40, (y0 + y1) / 2), fa(fmt_stat(cv(av), fmt)), font=font(44), fill=(255, 255, 255, 255), anchor="lm")
    return base, dyn


def scene_shot_map(s, summary):
    base, d = new_layer()
    header(d, "نقشه‌ی شوت‌ها")
    gw, gh = 400, 215
    boxes = [(W - 80 - gw, 250, s.get("home_shots") or [], s["home_team"], HOME),
             (80, 250, s.get("away_shots") or [], s["away_team"], AWAY)]
    dots = []
    for gx, gy, shots, name, color in boxes:
        draw_goal_frame(d, gx, gy, gw, gh)
        fit_text(d, (gx + gw / 2, gy + gh + 55), name, 34, 380, fill=color)
        goals = sum(1 for sh in shots if sh.get("outcome") == "Goal")
        text(d, (gx + gw / 2, gy + gh + 100), f"{fnum(len(shots))} شوت · {fnum(goals)} گل", 26, MUTED, bold=False)
        for sh in shots:
            x, y = target_xy(sh.get("goalTarget"), gx, gy, gw, gh)
            dots.append((x, y, sh.get("outcome") == "Goal"))
    d.ellipse((W // 2 - 190, 612, W // 2 - 170, 632), fill=GOLD + (255,))
    text(d, (W // 2 - 155, 622), "گل", 24, TEXT, bold=False, anchor="lm")
    d.ellipse((W // 2 + 40, 612, W // 2 + 60, 632), fill=(190, 205, 235, 255))
    text(d, (W // 2 + 75, 622), "مهار شده", 24, TEXT, bold=False, anchor="lm")

    n = max(1, len(dots))

    def dyn(dd, img, lt, dur):
        for i, (x, y, goal) in enumerate(dots):
            p = ease_back((lt - 0.3 - i * (min(2.5, max(0.5, dur - 1)) / n)) / 0.35)
            if p <= 0: continue
            r = 15 * p
            if goal:
                dd.ellipse((x - r - 6, y - r - 6, x + r + 6, y + r + 6), outline=GOLD + (200,), width=3)
                dd.ellipse((x - r, y - r, x + r, y + r), fill=GOLD + (255,))
            else:
                dd.ellipse((x - r, y - r, x + r, y + r), fill=(190, 205, 235, 235))
    return base, dyn


STAT_FA = {"Rating": "امتیاز", "Goals": "گل", "Assists": "پاس گل", "Shots": "شوت", "Passes": "پاس",
           "Saves": "مهار", "Tackles": "تکل", "Minutes": "دقیقه", "Minutes played": "دقیقه"}


def scene_player_card(s, summary):
    base, d = new_layer()
    p = s.get("player")
    team = s.get("team")
    header(d, "بازیکن برتر")
    cx0, cx1, cy0, cy1 = 200, W - 200, 210, 640
    rrect(d, (cx0, cy0, cx1, cy1), 36, fill=PANEL + (255,), outline=GOLD + (255,), width=3)
    chips = []
    if p:
        fit_text(d, (W // 2, 285), p.get("name") or "-", 62, 780)
        text(d, (W // 2, 355), f"{p.get('position') or ''} · {team or ''}".strip(" ·"), 30, MUTED, bold=False)
        for k, v in list((p.get("stats") or {}).items())[:3]:
            n = parse_num(v)
            val = fnum(round(n, 2) if n is not None and n != int(n) else int(n)) if n is not None else str(v)
            chips.append((val, STAT_FA.get(k, k)))
    else:
        text(d, (W // 2, 420), "-", 60)

    def dyn(dd, img, lt, dur):
        n = max(1, len(chips))
        gap = (cx1 - cx0) / (n + 1)
        for i, (val, label) in enumerate(chips):
            q = ease_back((lt - 0.3 - i * 0.18) / 0.45)
            if q <= 0: continue
            x = cx1 - gap * (i + 1)
            w, h = 170 * q, 150 * q
            rrect(dd, (x - w / 2, 490 - h / 2, x + w / 2, 490 + h / 2), 24, fill=(255, 255, 255, 30))
            if q > 0.7:
                dd.text((x, 470), fa(val), font=font(52), fill=GOLD_SOFT + (255,), anchor="mm")
                dd.text((x, 525), fa(label), font=font(24, False), fill=MUTED + (255,), anchor="mm")
    return base, dyn


def scene_prediction(s, summary):
    base, d = new_layer()
    header(d, "پیش‌بینی قبل از بازی")
    pr = s.get("prediction")
    home, away = s["home_team"], s["away_team"]
    hs, as_ = parse_score(s.get("score"))
    vals = None
    if pr:
        h, dr, a = (parse_num(pr.get("home_pct")) or 0, parse_num(pr.get("draw_pct")) or 0, parse_num(pr.get("away_pct")) or 0)
        tot = h + dr + a
        if tot > 0: vals = (h / tot, dr / tot, a / tot)
    x0, x1, y0, y1 = 140, W - 140, 330, 410
    if vals:
        fit_text(d, (W - 140, 290), home, 30, 300, fill=HOME, anchor="rm")
        fit_text(d, (140, 290), away, 30, 300, fill=AWAY, anchor="lm")
        text(d, (W // 2, 290), "مساوی", 28, MUTED)
    if hs is not None:
        fit_text(d, (W // 2, 560), f"نتیجه‌ی نهایی:  {home}  {fnum(hs)} - {fnum(as_)}  {away}", 40, 1000, fill=TEXT)

    def dyn(dd, img, lt, dur):
        if vals:
            p = ease_out(lt / 1.0)
            wtot = (x1 - x0) * p
            wh, wd, wa = wtot * vals[0], wtot * vals[1], wtot * vals[2]
            segs = [(wh, HOME, vals[0]), (wd, (140, 148, 170), vals[1]), (wa, AWAY, vals[2])]
            cur = x1
            for w_, col, share in segs:
                if w_ > 2:
                    rrect(dd, (cur - w_, y0, cur, y1), 18, fill=col + (255,))
                    if p > 0.8 and w_ > 90:
                        dd.text((cur - w_ / 2, (y0 + y1) / 2), fa(fnum(int(round(share * 100))) + "٪"), font=font(38),
                                fill=(255, 255, 255, 255), anchor="mm")
                cur -= w_
        if lt > 1.5 and hs is not None:
            q = ease_out((lt - 1.5) / 0.5)
            dd.rectangle((W // 2 - int(200 * q), 485, W // 2 + int(200 * q), 489), fill=GOLD + (255,))
    return base, dyn


def scene_news(s, summary):
    base, d = new_layer()
    h = s.get("headline")
    if isinstance(h, dict):
        for k in ("title", "headline", "text", "t", "name"):
            if isinstance(h.get(k), str):
                h = h[k]
                break
        else:
            h = next((v for v in h.values() if isinstance(v, str)), None)
    header(d, "تیتر خبر")
    d.text((W - 150, 270), "”", font=font(220), fill=GOLD + (120,), anchor="mm")
    if h:
        lines = wrap_lines(d, h, 46, 900, max_lines=4)
        y = 360 - (len(lines) - 1) * 35
        for ln in lines:
            text(d, (W // 2, y), ln, 46)
            y += 70
    return base, None


def scene_momentum(s, summary):
    base, d = new_layer()
    header(d, "روند بازی")
    events = [e for e in (s.get("events") or []) if e.get("type") in ("Goal", "Red Card", "Substitution")]
    last = max([95] + [parse_minute(e.get("time")) for e in events])
    x0, x1, y = 100, W - 100, 400
    d.line((x0, y, x1, y), fill=(255, 255, 255, 90), width=6)
    for m in range(0, int(last) + 1, 15):
        x = x1 - (x1 - x0) * m / last
        d.line((x, y - 12, x, y + 12), fill=(255, 255, 255, 140), width=3)
        text(d, (x, y + 38), fnum(m), 22, MUTED, bold=False)
    home, away = s.get("home_team"), s.get("away_team")

    items = []
    sorted_events = sorted(events, key=lambda e: parse_minute(e.get("time")))
    
    last_x = -999
    tier = 0
    # ۵ سطح ارتفاع کاملاً مجزا برای جلوگیری از برخورد متون
    tiers = [-70, -120, -170, 75, 125]

    for e in sorted_events:
        x = x1 - (x1 - x0) * parse_minute(e.get("time")) / last
        col = HOME if e.get("team") == home else AWAY if e.get("team") == away else MUTED
        
        if abs(x - last_x) < 110:
            tier = (tier + 1) % len(tiers)
        else:
            tier = 0 if parse_minute(e.get("time")) % 2 == 0 else 3
            
        offset_y = tiers[tier]
        items.append((x, e, col, offset_y))
        last_x = x

    def dyn(dd, img, lt, dur):
        prog = clamp((lt - 0.2) / max(0.5, min(dur, 10.0) * 0.7))
        cur_x = x1 - (x1 - x0) * prog
        dd.line((x1, y, cur_x, y), fill=GOLD + (255,), width=8)
        dd.ellipse((cur_x - 9, y - 9, cur_x + 9, y + 9), fill=GOLD_SOFT + (255,))
        for x, e, col, offset_y in items:
            if x < cur_x - 2: continue
            q = ease_back((prog - (x1 - x) / (x1 - x0)) / 0.08 if (x1 - x0) else 1)
            r = 18 * clamp(q, 0, 1.2)
            if r <= 1: continue
            kind = e.get("type")
            if kind == "Goal":
                dd.ellipse((x - r, y - r, x + r, y + r), fill=GOLD + (255,), outline=col + (255,), width=5)
            elif kind == "Red Card":
                dd.rectangle((x - r * .7, y - r, x + r * .7, y + r), fill=AWAY + (255,))
            else:
                a = r * 0.75
                dd.polygon([(x, y - a), (x + a, y), (x, y + a), (x - a, y)], fill=col + (255,))
            if q > 0.8 and kind in ("Goal", "Red Card"):
                ty = y + offset_y
                dd.line((x, y - r - 2 if offset_y < 0 else y + r + 2, x, ty + (-15 if offset_y < 0 else 15)), fill=(255, 255, 255, 90), width=2)
                dd.text((x, ty), fa(str(e.get("player") or "")), font=font(22), fill=TEXT + (255,), anchor="mm")
                dd.text((x, ty + 24), fa(fnum(e.get("time")) + "'"), font=font(18, False), fill=MUTED + (255,), anchor="mm")
    return base, dyn



def scene_outro(s, summary):
    base, d = new_layer()
    home, away = s["home_team"], s["away_team"]
    hs, as_ = parse_score(s.get("score"))
    line = f"{home}  {fnum(hs)} - {fnum(as_)}  {away}" if hs is not None else f"{home} - {away}"
    fit_text(d, (W // 2, 120), line, 54, 1150, fill=TEXT)
    text(d, (W // 2, 520), "موج فوتبال", 96, GOLD)
    text(d, (W // 2, 615), "سابسکرایب کنید تا تحلیل بازی بعدی رو از دست ندید", 34, TEXT, bold=False)
    lg = brand(150)

    def dyn(dd, img, lt, dur):
        k = 1 + 0.04 * math.sin(lt * 3)
        im2 = lg.resize((int(lg.width * k), int(lg.height * k)), Image.LANCZOS)
        paste_center(img, im2, W // 2, 300)
    return base, dyn


COMPARE_ROWS = [
    ("Possession", "مالکیت توپ", "percent"),
    ("Shots on target", "شوت در چارچوب", "number"),
    ("Expected Goals", "کیفیت موقعیت‌ها (xG)", "decimal"),
    ("Total passes", "تعداد پاس", "number"),
    ("Big Chances Created", "موقعیت‌های بزرگ", "number"),
    ("Corners", "کرنر", "number"),
]


def scene_compare(s, summary):
    base, d = new_layer()
    home, away = s["home_team"], s["away_team"]
    hst, ast = s.get("home_stats") or {}, s.get("away_stats") or {}
    rows = [(k, lab, fmt) for k, lab, fmt in COMPARE_ROWS if parse_num(hst.get(k)) is not None and parse_num(ast.get(k)) is not None][:5]
    header(d, "مقایسه‌ی دو تیم", y=118)
    fit_text(d, (W - 130, 190), home, 34, 400, fill=HOME, anchor="rm")
    fit_text(d, (130, 190), away, 34, 400, fill=AWAY, anchor="lm")
    top, step = 255, 88
    x0, x1 = 150, W - 150
    for i, (k, lab, fmt) in enumerate(rows):
        text(d, (W // 2, top + i * step - 24), lab, 26, MUTED, bold=False)

    def dyn(dd, img, lt, dur):
        for i, (k, lab, fmt) in enumerate(rows):
            p = ease_out((lt - 0.15 * i) / 0.8)
            if p <= 0: continue
            hv, av = parse_num(hst.get(k)), parse_num(ast.get(k))
            tot = hv + av
            ratio = 0.5 if tot <= 0 else clamp(hv / tot, 0.08, 0.92)
            y = top + i * step
            rrect(dd, (x0, y - 4, x1, y + 28), 16, fill=(255, 255, 255, 30))
            hx = x1 - (x1 - x0) * ratio * p
            ax = x0 + (x1 - x0) * (1 - ratio) * p
            if hx < x1 - 4: rrect(dd, (hx, y - 4, x1, y + 28), 16, fill=HOME + (255,))
            if ax > x0 + 4: rrect(dd, (x0, y - 4, ax, y + 28), 16, fill=AWAY + (255,))
            dd.text((x1 - 14, y + 12), fa(fmt_stat(hv * p, fmt)), font=font(26), fill=(255, 255, 255, 255), anchor="rm")
            dd.text((x0 + 14, y + 12), fa(fmt_stat(av * p, fmt)), font=font(26), fill=(255, 255, 255, 255), anchor="lm")
    return base, dyn


SCENES = {
    "title": scene_title, "goal": scene_goal, "card_or_sub": scene_card_or_sub, "stat_bar": scene_stat_bar,
    "shot_map": scene_shot_map, "player_card": scene_player_card, "prediction": scene_prediction,
    "news": scene_news, "momentum": scene_momentum, "outro": scene_outro,
    "goal_pitch": scene_goal_pitch, "compare": scene_compare, "table": scene_table,
}
NO_HUD = {"title", "outro"}
NO_MARK = {"outro"}


# ---------------------------------------------------------------- رندر
class Renderer:
    def __init__(self, summary, scenes, total):
        self.summary = summary
        self.scenes = scenes
        self.total = total
        self.starts = [sc["start"] for sc in scenes]
        self.bg = make_background(summary)
        self.blobs = make_blobs()
        self.panel_hud = make_panel(False)
        self.panel_full = make_panel(True)
        self.hud = make_hud(summary)
        self.mark = make_mark()
        self._cache = {}

    def _scene(self, idx):
        if idx not in self._cache:
            sc = self.scenes[idx]
            fn = SCENES.get(sc.get("type"))
            if fn is None:
                raise RuntimeError(f"نوع صحنه ناشناخته: {sc.get('type')}")
            self._cache[idx] = fn(sc, self.summary)
            for k in [k for k in self._cache if k < idx - 2]:
                del self._cache[k]
        return self._cache[idx]

    def _render_scene(self, idx, lt):
        sc = self.scenes[idx]
        dur = max(0.2, sc["end"] - sc["start"])
        base, dyn = self._scene(idx)
        layer = base.copy()
        if dyn is not None:
            dyn(ImageDraw.Draw(layer), layer, lt, dur)
        z = 1 + 0.04 * clamp(lt / min(dur, 10.0))
        if z > 1.001:
            zw, zh = int(W * z), int(H * z)
            big = layer.resize((zw, zh), Image.BILINEAR)
            ox, oy = (zw - W) // 2, (zh - H) // 2
            layer = big.crop((ox, oy, ox + W, oy + H))
        return layer

    def frame(self, t, idx=None, lt=None):
        if idx is None:
            idx = max(0, bisect.bisect_right(self.starts, t) - 1)
        sc = self.scenes[idx]
        dur = max(0.2, sc["end"] - sc["start"])
        if lt is None:
            lt = clamp(t - sc["start"], 0, dur)

        img = self.bg.copy()
        for spr, fx, fy, ph in self.blobs:
            sx = int(W * (0.5 + 0.45 * math.sin(t * fx + ph)) - spr.width / 2)
            sy = int(H * (0.5 + 0.40 * math.cos(t * fy + ph)) - spr.height / 2)
            img.paste(spr, (sx, sy), spr)

        panel = self.panel_full if sc["type"] in NO_HUD else self.panel_hud
        img.paste(panel, (0, 0), panel)

        layer = self._render_scene(idx, lt)
        if lt < FADE:
            p = lt / FADE
            if idx > 0:
                prev_dur = max(0.2, self.scenes[idx - 1]["end"] - self.scenes[idx - 1]["start"])
                prev = with_alpha(self._render_scene(idx - 1, prev_dur), 1 - p)
                img.paste(prev, (0, 0), prev)
            layer = with_alpha(layer, p)
        img.paste(layer, (0, 0), layer)

        if sc.get("type") not in NO_HUD:
            img.paste(self.hud, (0, 0), self.hud)
        if sc.get("type") not in NO_MARK:
            img.paste(self.mark, (0, 0), self.mark)

        d = ImageDraw.Draw(img)
        d.rectangle((0, H - 6, int(W * clamp(t / self.total)), H), fill=GOLD)
        return img


def build_video(summary, timeline, audio_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    find_logo()  
    summary = sync_tools.prepare_summary(summary)
    segments = sync_tools.build_segments(summary, timeline, audio_path, out_dir)
    scenes = build_scenes(summary, segments)
    total = float(segments[-1]["end"])
    with open(os.path.join(out_dir, "scenes.json"), "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)

    r = Renderer(summary, scenes, total)

    try:
        t_idx = next((i for i, sc in enumerate(scenes) if sc.get("type") == "title"), 0)
        sc0 = scenes[t_idx]
        thumb = r.frame(sc0["start"], idx=t_idx, lt=min(1.4, sc0["end"] - sc0["start"]))
        thumb.save(os.path.join(out_dir, "thumbnail.jpg"), quality=92)
    except Exception as e:
        print("تامبنیل ساخته نشد:", e)

    final_path = os.path.join(out_dir, "final.mp4")
    n_frames = int(total * FPS) + FPS // 2
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", audio_path,
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-profile:v", "main", "-level", "4.0",
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart",
        final_path,
    ]
    print(f"رندر {n_frames} فریم ({total:.1f} ثانیه، {len(scenes)} صحنه)...")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    try:
        for i in range(n_frames):
            t = min(i / FPS, total)
            proc.stdin.write(r.frame(t).tobytes())
            if i % (FPS * 20) == 0:
                print(f"  {i}/{n_frames}  ({time.time() - t0:.0f}s)")
    except BrokenPipeError:
        pass
    finally:
        try:
            proc.stdin.close()
        except Exception:
            pass
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg با کد {code} تموم شد")
    print(f"ویدیوی نهایی ساخته شد: {final_path}")
    return final_path


if __name__ == "__main__":
    from fetch_match_details import get_match_details
    from generate_analysis import summarize_match, generate_persian_script
    from generate_audio import synthesize_dialogue, build_scene_timeline

    match_id = int(sys.argv[1])
    out_dir = f"output/{match_id}"
    os.makedirs(out_dir, exist_ok=True)
    details = get_match_details(match_id)
    summary = summarize_match(details)
    turns = generate_persian_script(summary)
    audio_path = os.path.join(out_dir, "episode.wav")
    total_seconds = synthesize_dialogue(turns, audio_path)
    timeline = build_scene_timeline(turns, total_seconds)
    with open(os.path.join(out_dir, "timing.json"), "w", encoding="utf-8") as f:
        json.dump(timeline, f, ensure_ascii=False, indent=2)
    build_video(summary, timeline, audio_path, out_dir)
