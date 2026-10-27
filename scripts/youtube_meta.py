"""youtube_meta.py - عنوان، توضیحات (کپشن) و تگ اختصاصی هر بازی."""
import re

from teams import TEAMS

ID_TO_FA = {v: k for k, v in TEAMS.items()}
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
CHANNEL = "موج فوتبال"


def _fnum(x):
    return str(x).translate(FA_DIGITS)


def _clean(s):
    return re.sub(r"[<>]", "", str(s or "")).strip()


def _fa_name(team, summary):
    tid = (team or {}).get("id")
    if tid in ID_TO_FA:
        return ID_TO_FA[tid]
    tc = summary.get("table_context") or {}
    for r in (tc.get("rows") or []) + (tc.get("extras") or []):
        if str(r.get("team_id")) == str(tid) and r.get("fa_name"):
            return r["fa_name"]
    return (team or {}).get("name") or ""


def _hashtag(name):
    return "#" + re.sub(r"[^\w]+", "_", _clean(name)).strip("_") if name else ""


def build_metadata(summary, details):
    home = _clean(_fa_name(details.get("homeTeam"), summary))
    away = _clean(_fa_name(details.get("awayTeam"), summary))
    league = _clean(summary.get("league"))
    venue = _clean(summary.get("venue"))

    nums = re.findall(r"\d+", str(summary.get("score") or ""))
    score = f"{_fnum(nums[0])} - {_fnum(nums[1])}" if len(nums) >= 2 else ""

    title = f"{home} {score} {away} | تحلیل بازی | {CHANNEL}"
    if len(title) > 100:
        title = f"{home} {score} {away} | تحلیل بازی"
    title = title[:100]

    lines = [f"تحلیل کامل بازی {home} {score} {away}"]
    if league:
        lines.append(f"🏆 {league}")
    if venue:
        lines.append(f"🏟 {venue}")

    goals = [e for e in (summary.get("events") or []) if e.get("type") == "Goal"]
    if goals:
        lines += ["", "⚽ گل‌ها:"]
        for e in goals:
            lines.append(f"• دقیقه {_fnum(e.get('time'))}: {_clean(e.get('player'))} ({_clean(e.get('team'))})")

    lines += [
        "",
        "در این ویدیو گل‌ها، آمار کلیدی، بازیکنان برتر، جدول لیگ و حاشیه‌های بازی رو بررسی می‌کنیم.",
        f"برای دیدن تحلیل بازی‌های بعدی کانال {CHANNEL} رو سابسکرایب کنید.",
        "",
        "این ویدیو با کمک هوش مصنوعی تولید شده است.",
        "",
        " ".join(t for t in ["#موج_فوتبال", "#تحلیل_فوتبال", _hashtag(home), _hashtag(away)] if t),
    ]
    description = "\n".join(lines)[:4800]

    tags, total = [], 0
    for t in [CHANNEL, "تحلیل فوتبال", "فوتبال", home, away, league, f"{home} {away}"]:
        t = _clean(t)
        if t and t not in tags and total + len(t) < 450:
            tags.append(t)
            total += len(t) + 1

    return {"title": title, "description": description, "tags": tags}
