"""
scene_builder.py (نسخه‌ی جدید)

برچسب صحنه می‌تونه این شکل‌ها باشه:
    title | outro | momentum | shots | prediction | compare
    goal:N    (N = شماره‌ی گل، از ۰)
    card:N    (کارت/تعویض شماره‌ی N)
    stat:Key  (مثلاً stat:Possession)
    player:N  (بازیکن شماره‌ی N)
    news:N
برچسب‌های قدیمی بدون شماره (goal, card_or_sub, stat_bar, ...) هم هنوز کار می‌کنن.

وقتی یه بلوک طولانیه و چند تکه می‌شه، تکه‌ها تصویر متفاوتِ هم‌موضوع نشون می‌دن، نه یه عکس تکراری.
"""

STAT_CYCLE = [
    ("Possession", "مالکیت توپ", "percent"),
    ("Total passes", "تعداد کل پاس‌ها", "number"),
    ("Shots on target", "شوت در چارچوب", "number"),
    ("Expected Goals", "کیفیت موقعیت‌های گلزنی", "decimal"),
    ("Big Chances Created", "موقعیت‌های بزرگ", "number"),
    ("Corners", "کرنر", "number"),
]
STAT_BY_KEY = {k: (k, label, fmt) for k, label, fmt in STAT_CYCLE}

MAX_SCENE_SECONDS = 6


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
        self._cursor = {}

    # --- کمکی‌ها
    def _cycle(self, key, items):
        """بعدی‌ترین آیتم؛ اول از ندیده‌ها."""
        if not items:
            return None, None
        i = self._cursor.get(key, 0)
        self._cursor[key] = i + 1
        return i % len(items), items[i % len(items)]

    def _pick(self, key, items, ref):
        if not items:
            return None, None
        try:
            i = int(ref)
            if 0 <= i < len(items):
                return i, items[i]
        except (TypeError, ValueError):
            pass
        return self._cycle(key, items)

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

    # --- ساخت محتوای هر صحنه
    def resolve(self, scene, part=0):
        s = self.summary
        kind, _, ref = str(scene or "momentum").partition(":")
        base_teams = {"home_team": s["home_team"], "away_team": s["away_team"]}

        if kind == "title":
            if part > 0:  # معرفی طولانی: بعد از تیتر، مقایسه‌ی دو تیم
                return self._compare()
            return {"type": "title", **base_teams, "home_logo": s.get("home_logo"), "away_logo": s.get("away_logo"),
                    "score": s["score"], "league": s["league"], "venue": s["venue"]}

        if kind in ("goal",):
            idx, event = self._pick("goal", self.goal_events, ref)
            target = self._target_for(event)
            variant = part % 3
            if variant == 0:
                return {"type": "goal_pitch", "event": event, **base_teams}
            if variant == 1:
                return {"type": "goal", "event": event, "target": target}
            p, team = self._player_by_name(event.get("player")) if event else (None, None)
            if p:
                return {"type": "player_card", "player": p, "team": team}
            return {"type": "goal", "event": event, "target": target}

        if kind in ("card", "card_or_sub"):
            _, event = self._pick("card", self.card_sub_events, ref)
            return {"type": "card_or_sub", "event": event}

        if kind in ("stat", "stat_bar"):
            if part % 2 == 1:
                return self._compare()
            if kind == "stat" and ref in STAT_BY_KEY:
                key, label, fmt = STAT_BY_KEY[ref]
            else:
                _, (key, label, fmt) = self._cycle("stat", STAT_CYCLE)
            return {"type": "stat_bar", "label": label, "format": fmt,
                    "home_value": (s.get("home_stats") or {}).get(key),
                    "away_value": (s.get("away_stats") or {}).get(key), **base_teams}

        if kind in ("shots", "shot_map"):
            return {"type": "shot_map", **base_teams, "home_shots": s.get("home_key_shots") or [],
                    "away_shots": s.get("away_key_shots") or []}

        if kind in ("player", "player_card"):
            idx, picked = self._pick("player", self.all_players, ref)
            if not picked:
                return {"type": "player_card", "player": None, "team": None}
            return {"type": "player_card", "player": picked[0], "team": picked[1]}

        if kind == "prediction":
            if not s.get("prematch_prediction"):
                return self._compare()
            return {"type": "prediction", "prediction": s.get("prematch_prediction"), **base_teams, "score": s["score"]}

        if kind == "news":
            _, item = self._pick("news", self.news, ref)
            if item is None:
                return self._compare()
            return {"type": "news", "headline": item}

        if kind == "compare":
            return self._compare()

        if kind == "outro":
            return {"type": "outro", **base_teams, "score": s["score"]}

        # momentum و هر چیز ناشناخته
        if part % 2 == 1:
            return self._compare()
        return {"type": "momentum", "events": s.get("events") or [], **base_teams}

    def _compare(self):
        s = self.summary
        return {"type": "compare", "home_team": s["home_team"], "away_team": s["away_team"],
                "home_stats": s.get("home_stats") or {}, "away_stats": s.get("away_stats") or {}}


def build_scenes(summary, timeline):
    builder = SceneBuilder(summary)
    scenes = []
    for block in timeline:
        duration = block["end"] - block["start"]
        n_parts = max(1, int(duration // MAX_SCENE_SECONDS) + 1)
        part_len = duration / n_parts
        for i in range(n_parts):
            start = block["start"] + i * part_len
            content = builder.resolve(block["scene"], part=i)
            scenes.append({"start": start, "end": start + part_len, **content})
    return scenes


if __name__ == "__main__":
    import sys
    import json

    match_dir = sys.argv[1]
    with open(f"{match_dir}/summary.json", "r", encoding="utf-8") as f:
        summary = json.load(f)
    with open(f"{match_dir}/timing.json", "r", encoding="utf-8") as f:
        timeline = json.load(f)
    scenes = build_scenes(summary, timeline)
    with open(f"{match_dir}/scenes.json", "w", encoding="utf-8") as f:
        json.dump(scenes, f, ensure_ascii=False, indent=2)
    print(f"{len(scenes)} صحنه ساخته شد")
    print([s["type"] for s in scenes])
