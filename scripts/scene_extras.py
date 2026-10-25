"""
scene_extras.py - صحنه‌های جدول لیگ و کارت‌ها
B = ماژول build_video (ابزارهای ترسیم مشترک)
"""
import re
from PIL import Image, ImageDraw

NAVY = (15, 23, 42)
CARD_YELLOW = (250, 204, 21)
CARD_RED = (239, 68, 68)

COLS = [
    ("played", "بازی", 700), ("won", "برد", 625), ("drawn", "مساوی", 550), ("lost", "باخت", 475),
    ("gf", "گل زده", 400), ("ga", "گل خورده", 325), ("gd", "تفاضل", 250), ("points", "امتیاز", 140),
]
RANK_X, BADGE_X, NAME_X = 1188, 1128, 1100


def _minute(t):
    m = re.findall(r"\d+", str(t or ""))
    return sum(int(x) for x in m[:2]) if m else 0


def scene_table(s, summary, B):
    W = B.W
    base, d = B.new_layer()
    B.header(d, "جدول رده‌بندی", y=118)

    tc = s.get("table_context") or {}
    rows = list(tc.get("top8") or [])
    extras = list(tc.get("extras") or [])
    if not rows:
        raise ValueError("جدول لیگ خالیه")
    ids = (str(tc.get("home_id")), str(tc.get("away_id")))

    rh = 38 if (len(rows) > 6 or extras) else 48

    for _, label, x in COLS:
        B.text(d, (x, 190), label, 21, B.MUTED, bold=False)
    B.text(d, (RANK_X, 190), "#", 21, B.MUTED, bold=False)
    B.text(d, (NAME_X, 190), "تیم", 21, B.MUTED, bold=False, anchor="rm")
    d.line((60, 210, W - 60, 210), fill=(255, 255, 255, 90), width=2)

    def make_row(row, idx):
        strip = Image.new("RGBA", (W, rh), (0, 0, 0, 0))
        dr = ImageDraw.Draw(strip)
        hl = str(row.get("team_id")) in ids
        if hl:
            B.rrect(dr, (60, 2, W - 60, rh - 2), 12, fill=B.GOLD_SOFT + (250,))
            c_main, c_num, c_pts = NAVY, NAVY, NAVY
        else:
            B.rrect(dr, (60, 2, W - 60, rh - 2), 12, fill=(255, 255, 255, 30 if idx % 2 == 0 else 14))
            c_main, c_num, c_pts = B.TEXT, (226, 233, 247), B.GOLD
        cy = rh // 2

        B.text(dr, (RANK_X, cy), B.fnum(row.get("rank")), 22, c_main)
        lg = B.badge(row.get("name"), row.get("logo"), 28)
        strip.paste(lg, (BADGE_X - 14, (rh - 28) // 2), lg)
        B.fit_text(dr, (NAME_X, cy), row.get("fa_name") or row.get("name"), 22, 340, fill=c_main, anchor="rm")

        for key, _, x in COLS:
            v = row.get(key)
            if v is None:
                txt = "-"
            elif key == "gd":
                txt = ("+" if v > 0 else "") + B.fnum(v)
            else:
                txt = B.fnum(v)
            if key == "points":
                B.text(dr, (x, cy), txt, 26, c_pts)
            else:
                B.text(dr, (x, cy), txt, 22, c_num, bold=False)
        return strip

    items = []
    y = 236
    for i, r in enumerate(rows):
        items.append((make_row(r, i), y))
        y += rh
    dots_y = None
    if extras:
        dots_y = y - rh // 2 + 22
        y = dots_y + 30
        for j, r in enumerate(extras):
            items.append((make_row(r, j), y))
            y += rh
    n_top = len(rows)

    def dyn(dd, img, lt, dur):
        for i, (strip, yy) in enumerate(items):
            p = B.ease_out((lt - 0.1 * i) / 0.4)
            if p <= 0:
                continue
            r = B.with_alpha(strip, p)
            img.paste(r, (int((1 - p) * 70), yy - rh // 2), r)
        if dots_y is not None:
            q = B.ease_out((lt - 0.1 * n_top) / 0.3)
            if q > 0:
                for k in (-1, 0, 1):
                    cx = W // 2 + k * 22
                    dd.ellipse((cx - 5, dots_y - 5, cx + 5, dots_y + 5), fill=(255, 255, 255, int(210 * q)))
    return base, dyn


def scene_cards(s, summary, B):
    base, d = B.new_layer()
    B.header(d, "کارت‌های بازی", y=118)
    home, away = s["home_team"], s["away_team"]
    cards = sorted(s.get("events") or [], key=lambda e: _minute(e.get("time")))

    cols = [(home, 655, B.HOME, summary.get("home_logo")),
            (away, 65, B.AWAY, summary.get("away_logo"))]
    items = []
    MAXR = 7

    def make_row(e):
        st = Image.new("RGBA", (560, 42), (0, 0, 0, 0))
        dr = ImageDraw.Draw(st)
        B.rrect(dr, (0, 2, 559, 40), 14, fill=(255, 255, 255, 30))
        is_red = "red" in str(e.get("type", "")).lower()
        col = CARD_RED if is_red else CARD_YELLOW
        dr.rounded_rectangle((526, 8, 546, 34), radius=4, fill=col + (255,))
        B.fit_text(dr, (512, 21), e.get("player") or "-", 24, 330, fill=B.TEXT, anchor="rm")
        dr.text((60, 21), B.fa(B.fnum(e.get("time")) + "'"), font=B.font(24, False),
                fill=B.MUTED + (255,), anchor="mm")
        return st

    for name, x0, color, logo in cols:
        right = x0 + 560
        lg = B.badge(name, logo, 44)
        base.paste(lg, (right - 44, 183), lg)
        B.fit_text(d, (right - 56, 205), name, 32, 330, fill=color, anchor="rm")
        mine = [e for e in cards if e.get("team") == name]
        if not mine:
            B.text(d, (x0 + 280, 300), "بدون کارت", 28, B.MUTED, bold=False)
            continue
        shown = mine if len(mine) <= MAXR else mine[:MAXR - 1]
        for i, e in enumerate(shown):
            items.append((make_row(e), x0, 268 + 50 * i))
        if len(mine) > MAXR:
            B.text(d, (x0 + 280, 268 + 50 * (MAXR - 1)), f"و {B.fnum(len(mine) - MAXR + 1)} کارت دیگر", 24,
                   B.MUTED, bold=False)

    def dyn(dd, img, lt, dur):
        for i, (st, x0, y) in enumerate(items):
            p = B.ease_out((lt - 0.12 * i) / 0.4)
            if p <= 0:
                continue
            r = B.with_alpha(st, p)
            img.paste(r, (x0 + int((1 - p) * 50), y - 21), r)
    return base, dyn
