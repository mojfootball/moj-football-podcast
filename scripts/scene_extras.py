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
    B.header(d, "جدول رده‌بندی", y=108)

    tc = s.get("table_context") or {}
    rows = list(tc.get("rows") or [])
    extras = list(tc.get("extras") or [])
    if not rows:
        raise ValueError(f"جدول لیگ خالیه. کلیدهای موجود: {list(tc.keys())}")
    ids = (str(tc.get("home_id")), str(tc.get("away_id")))

    TOP, BOTTOM = 196, 686
    dots_h = 26 if extras else 0
    n = len(rows) + len(extras)
    rh = int(B.clamp((BOTTOM - TOP - dots_h) / n, 28, 48))
    fs = max(15, int(rh * 0.56))
    bsz = rh - 8

    for _, label, x in COLS:
        B.text(d, (x, 168), label, 20, B.MUTED, bold=False)
    B.text(d, (RANK_X, 168), "#", 20, B.MUTED, bold=False)
    B.text(d, (NAME_X, 168), "تیم", 20, B.MUTED, bold=False, anchor="rm")
    d.line((60, 186, W - 60, 186), fill=(255, 255, 255, 90), width=2)

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

        B.text(dr, (RANK_X, cy), B.fnum(row.get("rank")), fs, c_main)
        lg = B.badge(row.get("name"), row.get("logo"), bsz)
        strip.paste(lg, (BADGE_X - bsz // 2, (rh - bsz) // 2), lg)
        B.fit_text(dr, (NAME_X, cy), row.get("fa_name") or row.get("name"), fs, 340, fill=c_main, anchor="rm")

        for key, _, x in COLS:
            v = row.get(key)
            if v is None:
                txt = "-"
            elif key == "gd":
                txt = ("+" if v > 0 else "") + B.fnum(v)
            else:
                txt = B.fnum(v)
            if key == "points":
                B.text(dr, (x, cy), txt, fs + 3, c_pts)
            else:
                B.text(dr, (x, cy), txt, fs, c_num, bold=False)
        return strip

    items = []
    for i, r in enumerate(rows):
        items.append((make_row(r, i), TOP + i * rh))
    dots_y = None
    if extras:
        end_y = TOP + len(rows) * rh
        dots_y = end_y + dots_h // 2
        for j, r in enumerate(extras):
            items.append((make_row(r, j), end_y + dots_h + j * rh))
    n_top = len(rows)

    def dyn(dd, img, lt, dur):
        for i, (strip, yy) in enumerate(items):
            p = B.ease_out((lt - 0.08 * i) / 0.4)
            if p <= 0:
                continue
            r = B.with_alpha(strip, p)
            img.paste(r, (int((1 - p) * 70), yy), r)
        if dots_y is not None:
            q = B.ease_out((lt - 0.08 * n_top) / 0.3)
            if q > 0:
                for k in (-1, 0, 1):
                    cx = W // 2 + k * 22
                    dd.ellipse((cx - 4, dots_y - 4, cx + 4, dots_y + 4), fill=(255, 255, 255, int(210 * q)))
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
    # ===== صحنه‌ی روند بازی (تایم‌لاین دو ستونه) =====
from PIL import Image, ImageDraw

_GOLD = (250, 204, 21)
_RED = (239, 68, 68)
_NAVY = (15, 23, 42)


def _ev_kind(e):
    t = str(e.get("type", "")).lower()
    if "miss" in t or "var" in t:
        return None
    if "goal" in t:
        return "goal"
    if "red" in t:
        return "red"
    if "card" in t or "yellow" in t:
        return "yellow"
    if "sub" in t:
        return "sub"
    return None


def _draw_icon(dr, kind, ix, cy):
    if kind == "goal":
        dr.ellipse((ix - 12, cy - 12, ix + 12, cy + 12), fill=_GOLD + (255,), outline=_NAVY + (255,), width=3)
        dr.ellipse((ix - 4, cy - 4, ix + 4, cy + 4), fill=_NAVY + (255,))
    elif kind in ("yellow", "red"):
        col = _GOLD if kind == "yellow" else _RED
        dr.rounded_rectangle((ix - 8, cy - 12, ix + 8, cy + 12), radius=3, fill=col + (255,))
    else:
        dr.polygon([(ix - 7, cy - 1), (ix + 7, cy - 1), (ix, cy - 12)], fill=(52, 211, 153, 255))
        dr.polygon([(ix - 7, cy + 1), (ix + 7, cy + 1), (ix, cy + 12)], fill=(251, 113, 133, 255))


def scene_momentum(s, summary, B):
    import re as _re
    W = B.W
    base, d = B.new_layer()
    B.header(d, "روند بازی", y=118)
    home, away = s["home_team"], s["away_team"]
    ROWS, PITCH, SPINE, Y0 = 8, 46, W // 2, 262

    def minute(e):
        m = _re.findall(r"\d+", str(e.get("time") or ""))
        return sum(int(x) for x in m[:2]) if m else 0

    evs = []
    for e in sorted(s.get("events") or [], key=minute):
        k = _ev_kind(e)
        if k:
            evs.append((k, e))
    if len(evs) > ROWS:
        evs = [x for x in evs if x[0] != "sub"]
    evs = evs[:ROWS * 4]

    if not evs:
        B.text(d, (W // 2, 380), "رویدادی ثبت نشده", 34, B.MUTED, bold=False)
        return base, None

    def make_row(kind, e, is_home, score):
        st = Image.new("RGBA", (W, 44), (0, 0, 0, 0))
        dr = ImageDraw.Draw(st)
        cy = 22
        col = B.HOME if is_home else B.AWAY
        x0, x1 = (SPINE + 52, W - 60) if is_home else (60, SPINE - 52)
        if kind == "goal":
            B.rrect(dr, (x0, 2, x1, 42), 14, fill=B.GOLD + (70,), outline=B.GOLD + (230,), width=2)
        else:
            B.rrect(dr, (x0, 2, x1, 42), 14, fill=(255, 255, 255, 34))
        B.rrect(dr, (SPINE - 42, 5, SPINE + 42, 39), 17, fill=_NAVY + (240,), outline=col + (255,), width=3)
        B.text(dr, (SPINE, cy - 1), B.fnum(e.get("time")) + "'", 21)
        _draw_icon(dr, kind, x1 - 26, cy)

        name = e.get("player") or "-"
        extra = None
        if kind == "goal" and e.get("assist"):
            extra = "پاس گل: " + str(e["assist"])
        elif kind == "sub" and e.get("assist"):
            extra = "به‌جای " + str(e["assist"])
        left_pad = 110 if kind == "goal" else 24
        maxw = (x1 - 52) - (x0 + left_pad)
        if extra:
            B.fit_text(dr, (x1 - 52, cy - 8), name, 22, maxw, anchor="rm")
            B.fit_text(dr, (x1 - 52, cy + 12), extra, 16, maxw, fill=B.MUTED, bold=False, anchor="rm")
        else:
            B.fit_text(dr, (x1 - 52, cy), name, 24, maxw, anchor="rm")
        if kind == "goal":
            cx = x0 + 52
            B.text(dr, (cx - 22, cy - 1), B.fnum(score[1]), 26, B.GOLD_SOFT)
            B.text(dr, (cx, cy - 3), ":", 24, B.MUTED)
            B.text(dr, (cx + 22, cy - 1), B.fnum(score[0]), 26, B.GOLD_SOFT)
        return st

    hs = as_ = 0
    rows = []
    for k, e in evs:
        is_home = e.get("team") == home
        if k == "goal":
            if is_home:
                hs += 1
            else:
                as_ += 1
        rows.append((make_row(k, e, is_home, (hs, as_)), is_home))
    pages = [rows[i:i + ROWS] for i in range(0, len(rows), ROWS)]

    # سرستون‌ها
    lg_h = B.badge(home, summary.get("home_logo"), 40)
    lg_a = B.badge(away, summary.get("away_logo"), 40)
    base.paste(lg_h, (W - 60 - 40, 176), lg_h)
    base.paste(lg_a, (60, 176), lg_a)
    B.fit_text(d, (W - 60 - 52, 196), home, 30, 400, fill=B.HOME, anchor="rm")
    B.fit_text(d, (60 + 52, 196), away, 30, 400, fill=B.AWAY, anchor="lm")

    # ستون وسط
    n_first = min(ROWS, len(rows))
    d.line((SPINE, 236, SPINE, Y0 + (n_first - 1) * PITCH + 24), fill=(255, 255, 255, 70), width=4)

    # راهنما
    present = [k for k in ("goal", "yellow", "red", "sub") if any(x[0] == k for x in evs)]
    labels = {"goal": "گل", "yellow": "کارت زرد", "red": "کارت قرمز", "sub": "تعویض"}
    step = 170
    lx = W // 2 + (len(present) - 1) * step // 2
    for k in present:
        _draw_icon(d, k, lx, 640)
        B.text(d, (lx - 22, 640), labels[k], 20, B.MUTED, bold=False, anchor="rm")
        lx -= step

    def dyn(dd, img, lt, dur):
        n = len(pages)
        pd = dur / n
        pi = min(n - 1, int(lt / pd))
        lp = lt - pi * pd
        fade = 1.0 if pi == n - 1 else B.clamp((pd - lp) / 0.3)
        for i, (st, is_home) in enumerate(pages[pi]):
            p = B.ease_out((lp - 0.12 * i) / 0.4)
            if p <= 0:
                continue
            r = B.with_alpha(st, p * fade)
            off = int((1 - p) * 60) * (1 if is_home else -1)
            img.paste(r, (off, Y0 + i * PITCH - 22), r)
        if n > 1:
            for j in range(n):
                cx = W // 2 + (j - (n - 1) / 2) * 22
                col = B.GOLD if j == pi else (255, 255, 255, 110)
                dd.ellipse((cx - 5, 664 - 5, cx + 5, 664 + 5), fill=col if len(col) == 4 else col + (255,))
    return base, dyn
