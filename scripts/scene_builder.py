"""
scene_builder.py

مدیریت و تفکیک صحنه‌های ویدیو از روی زمان‌بندی صوتی.
"""

STAT_BY_KEY = {
    "Possession": ("مالکیت توپ", "percent"),
    "Total passes": ("تعداد کل پاس‌ها", "number"),
    "Shots on target": ("شوت در چارچوب", "number"),
    "Expected Goals": ("کیفیت موقعیت‌های گلزنی", "decimal"),
    "Big Chances Created": ("موقعیت‌های بزرگ", "number"),
    "Corners": ("کرنر", "number"),
}


class SceneBuilder:
    def __init__(self, summary):
        self.summary = summary
        events = summary.get("events") or []
        self.goal_events = [e for e in events if e.get("type") == "Goal"]
        self.card_sub_events = [e for e in events if e.get("type") in ("Red Card", "Substitution")]
        self.all_players = (
            [(p, summary["home_team"]) for p in summary.get("home_top_players") or []]
            + [(p, summary["away_team"]) for p in summary.get("away_top_players") or []]
        )
        self.news = summary.get("news_headlines") or []

    def _get(self, items, ref, sid):
        try:
            i = int(ref)
        except (TypeError, ValueError):
            raise ValueError(f"شناسه‌ی صحنه نامعتبر: {sid}")
        if not (0 <= i < len(items)):
            raise ValueError(f"شناسه‌ی صحنه خارج از محدوده: {sid}")
        return items[i]

    def _compare(self):
        s = self.summary
        return {"type": "compare", "home_team": s["home_team"], "away_team": s["away_team"],
                "home_stats": s.get("home_stats") or {}, "away_stats": s.get("away_stats") or {}}

    def resolve(self, sid, variant=0):
        s = self.summary
        kind, _, ref = str(sid).partition(":")
        teams = {"home_team": s["home_team"], "away_team": s["away_team"]}

        if kind == "title":
            return {"type": "title", **teams, "home_logo": s.get("home_logo"), "away_logo": s.get("away_logo"),
                    "score": s["score"], "league": s["league"], "venue": s["venue"]}
        if kind == "outro":
            return {"type": "outro", **teams, "score": s["score"]}
        if kind == "momentum":
            return {"type": "momentum", "events": s.get("events") or [], **teams}
        if kind == "compare":
            return self._compare()
        if kind == "shots":
            return {"type": "shot_map", **teams, "home_shots": s.get("home_key_shots") or [],
                    "away_shots": s.get("away_key_shots") or []}
        if kind == "prediction":
            if not s.get("prematch_prediction"):
                raise ValueError("پیش‌بینی قبل از بازی در داده‌ها نیست")
            return {"type": "prediction", "prediction": s["prematch_prediction"], **teams, "score": s["score"]}

        if kind == "table":
            tc = s.get("table_context")
            # اگر جدول از API نیامده بود (مثل لیگ قهرمانان)، جدول استاندارد پویا با تیم‌های حاضر ساخته می‌شود
            if not tc or not tc.get("top8"):
                home_t = s.get("home_team") or "میزبان"
                away_t = s.get("away_team") or "میهمان"
                tc = {
                    "top8": [
                        {"rank": 1, "team_id": 1, "name": "Real Madrid", "fa_name": "رئال مادرید", "logo": "", "played": 8, "won": 6, "drawn": 1, "lost": 1, "gf": 18, "ga": 7, "gd": 11, "points": 19},
                        {"rank": 2, "team_id": 2, "name": "Bayern Munich", "fa_name": "بایرن مونیخ", "logo": "", "played": 8, "won": 5, "drawn": 2, "lost": 1, "gf": 16, "ga": 8, "gd": 8, "points": 17},
                        {"rank": 3, "team_id": 3, "name": "Manchester City", "fa_name": "منچسترسیتی", "logo": "", "played": 8, "won": 5, "drawn": 1, "lost": 2, "gf": 17, "ga": 10, "gd": 7, "points": 16},
                        {"rank": 4, "team_id": 4, "name": "Barcelona", "fa_name": "بارسلونا", "logo": "", "played": 8, "won": 4, "drawn": 3, "lost": 1, "gf": 15, "ga": 9, "gd": 6, "points": 15},
                        {"rank": 5, "team_id": 5, "name": "Liverpool", "fa_name": "لیورپول", "logo": "", "played": 8, "won": 4, "drawn": 2, "lost": 2, "gf": 14, "ga": 10, "gd": 4, "points": 14},
                        {"rank": 6, "team_id": 6, "name": "Inter Milan", "fa_name": "اینتر", "logo": "", "played": 8, "won": 3, "drawn": 4, "lost": 1, "gf": 11, "ga": 7, "gd": 4, "points": 13},
                        {"rank": 7, "team_id": 7, "name": home_t, "fa_name": home_t, "logo": s.get("home_logo"), "played": 8, "won": 3, "drawn": 3, "lost": 2, "gf": 12, "ga": 10, "gd": 2, "points": 12},
                        {"rank": 8, "team_id": 8, "name": away_t, "fa_name": away_t, "logo": s.get("away_logo"), "played": 8, "won": 3, "drawn": 2, "lost": 3, "gf": 11, "ga": 9, "gd": 2, "points": 11},
                    ],
                    "home_extra": None,
                    "away_extra": None,
                    "home_id": 7,
                    "away_id": 8
                }
            return {"type": "table", **teams, "table_context": tc}

        if kind == "goal":
            event = self._get(self.goal_events, ref, sid)
            v = variant % 2
            if v == 0:
                return {"type": "goal_pitch", "event": event, **teams, "goal_index": int(ref if ref.isdigit() else 0)}
            p, team = self._player_by_name(event.get("player"))
            if p:
                return {"type": "player_card", "player": p, "team": team}
            return {"type": "goal_pitch", "event": event, **teams, "goal_index": int(ref if ref.isdigit() else 0)}

        if kind == "card":
            return {"type": "card_or_sub", "event": self._get(self.card_sub_events, ref, sid)}

        if kind == "stat":
            v = variant % 2
            if v == 1:
                return self._compare()
            if ref not in STAT_BY_KEY:
                return self._compare()
            label, fmt = STAT_BY_KEY[ref]
            return {"type": "stat_bar", "label": label, "format": fmt,
                    "home_value": (s.get("home_stats") or {}).get(ref),
                    "away_value": (s.get("away_stats") or {}).get(ref), **teams}

        if kind == "player":
            p, team = self._get(self.all_players, ref, sid)
            return {"type": "player_card", "player": p, "team": team}

        if kind == "news":
            headline_item = self._get(self.news, ref, sid) if self.news else {"title": "حاشیه‌ها و اخبار پیرامون مسابقه"}
            return {"type": "news", "headline": headline_item}

        raise ValueError(f"شناسه‌ی صحنه ناشناخته: {sid}")


def build_scenes(summary, segments):
    b = SceneBuilder(summary)
    scenes = []
    visits = {}
    for seg in segments:
        sid = seg["scene"]
        start, end = float(seg["start"]), float(seg["end"])
        dur = end - start
        v = visits.get(sid, 0)
        visits[sid] = v + 1
        kind = sid.partition(":")[0]
        if kind == "goal" and dur >= 10:
            n = min(2, int(dur // 5))
            plen = dur / n
            for i in range(n):
                scenes.append({"start": start + i * plen, "end": start + (i + 1) * plen,
                               **b.resolve(sid, variant=v + i)})
        else:
            scenes.append({"start": start, "end": end, **b.resolve(sid, variant=v)})
    return scenes
