"""
scene_builder.py

هر صحنه‌ی ویدیو دقیقاً از روی زمان‌بندی صدا ساخته می‌شه (نه تایمر ثابت).
شناسه‌ی صحنه:
    title | outro | momentum | compare | shots | prediction | table
    goal:N | card:N | stat:Key | player:N | news:N
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

    def _target_for(self, event):
        if not event:
            return None
        shots = (self.summary.get("home_key_shots") or []) + (self.summary.get("away_key_shots") or [])
        for sh in shots:
            if sh.get("outcome") == "Goal" and sh.get("playerName") == event.get("player"):
                return sh.get("goalTarget")
        return None

    def _player_by_name(self, name):
        for p, team in self.all_players:
            if p.get("name") == name:
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

        # اضافه شدن صحنه‌ی جدول رده‌بندی همراه با اطلاعات کامل تیم‌ها
            if kind == "table":
            tc = s.get("table_context")
            if not tc:
                return self._compare()
            return {"type": "table", **teams, "table_context": tc}

        if kind == "goal":
            event = self._get(self.goal_events, ref, sid)
            v = variant % 3
            if v == 0:
                return {"type": "goal_pitch", "event": event, **teams}
            if v == 1:
                return {"type": "goal", "event": event, "target": self._target_for(event)}
            p, team = self._player_by_name(event.get("player"))
            if p:
                return {"type": "player_card", "player": p, "team": team}
            return {"type": "goal", "event": event, "target": self._target_for(event)}

        if kind == "card":
            return {"type": "card_or_sub", "event": self._get(self.card_sub_events, ref, sid)}

        if kind == "stat":
            v = variant % 3
            if v == 1:
                return self._compare()
            if v == 2 and self.all_players:
                p, team = self.all_players[0]
                return {"type": "player_card", "player": p, "team": team}
            
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
            return {"type": "news", "headline": self._get(self.news, ref, sid)}

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
            n = min(3, int(dur // 4))
            plen = dur / n
            for i in range(n):
                scenes.append({"start": start + i * plen, "end": start + (i + 1) * plen,
                               **b.resolve(sid, variant=v + i)})
        else:
            scenes.append({"start": start, "end": end, **b.resolve(sid, variant=v)})
    return scenes
