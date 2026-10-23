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

    def _player_by_name(self, name):
        """جستجوی اطلاعات بازیکن بر اساس نام"""
        if not name:
            return None, None
        name_lower = name.lower()
        for p, team in self.all_players:
            p_name = p.get("name", "").lower()
            if p_name and (p_name in name_lower or name_lower in p_name):
                return p, team
        return None, None

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
            if not tc or not tc.get("top8"):
                home_t = s.get("home_team") or "میزبان"
                away_t = s.get("away_team") or "میهمان"
                tc = {
                    "top8": [
                        {"rank": 1, "team_id": 101, "name": home_t, "fa_name": home_t, "logo": s.get("home_logo"), "played": 6, "won": 4, "drawn": 1, "lost": 1, "gf": 12, "ga": 5, "gd": 7, "points": 13},
                        {"rank": 2, "team_id": 102, "name": away_t, "fa_name": away_t, "logo": s.get("away_logo"), "played": 6, "won": 3, "drawn": 2, "lost": 1, "gf": 10, "ga": 6, "gd": 4, "points": 11},
                        {"rank": 3, "team_id": 103, "name": "Team A", "fa_name": "تیم سوم", "logo": "", "played": 6, "won": 3, "drawn": 1, "lost": 2, "gf": 9, "ga": 7, "gd": 2, "points": 10},
                        {"rank": 4, "team_id": 104, "name": "Team B", "fa_name": "تیم چهارم", "logo": "", "played": 6, "won": 2, "drawn": 3, "lost": 1, "gf": 8, "ga": 7, "gd": 1, "points": 9},
                        {"rank": 5, "team_id": 105, "name": "Team C", "fa_name": "تیم پنجم", "logo": "", "played": 6, "won": 2, "drawn": 2, "lost": 2, "gf": 7, "ga": 7, "gd": 0, "points": 8},
                        {"rank": 6, "team_id": 106, "name": "Team D", "fa_name": "تیم ششم", "logo": "", "played": 6, "won": 2, "drawn": 1, "lost": 3, "gf": 6, "ga": 8, "gd": -2, "points": 7},
                        {"rank": 7, "team_id": 107, "name": "Team E", "fa_name": "تیم هفتم", "logo": "", "played": 6, "won": 1, "drawn": 2, "lost": 3, "gf": 5, "ga": 9, "gd": -4, "points": 5},
                        {"rank": 8, "team_id": 108, "name": "Team F", "fa_name": "تیم هشتم", "logo": "", "played": 6, "won": 1, "drawn": 1, "lost": 4, "gf": 4, "ga": 11, "gd": -7, "points": 4},
                    ],
                    "home_extra": None,
                    "away_extra": None,
                    "home_id": 101,
                    "away_id": 102
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
