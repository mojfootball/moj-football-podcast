STAT_CYCLE = [
    ("Possession", "مالکیت توپ", "percent"),
    ("Total passes", "تعداد کل پاس‌ها", "number"),
    ("Shots on target", "شوت در چارچوب", "number"),
    ("Expected Goals", "کیفیت موقعیت‌های گلزنی", "decimal"),
    ("Big Chances Created", "موقعیت‌های بزرگ", "number"),
    ("Corners", "کرنر", "number"),
]


class SceneBuilder:
    def __init__(self, summary):
        self.summary = summary
        self.goal_events = [e for e in summary["events"] if e["type"] == "Goal"]
        self.card_sub_events = [
            e for e in summary["events"] if e["type"] in ("Red Card", "Substitution")
        ]
        self.all_players = (
            [(p, summary["home_team"]) for p in summary["home_top_players"]]
            + [(p, summary["away_team"]) for p in summary["away_top_players"]]
        )
        self.news = summary.get("news_headlines", [])

        self._goal_i = 0
        self._card_sub_i = 0
        self._stat_i = 0
        self._player_i = 0
        self._news_i = 0

    def _next(self, items, counter_name):
        i = getattr(self, counter_name)
        if not items:
            return None
        item = items[i % len(items)]
        setattr(self, counter_name, i + 1)
        return item

    def resolve(self, scene_type):
        summary = self.summary

        if scene_type == "title":
            return {
                "type": "title",
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
                "home_logo": summary.get("home_logo"),
                "away_logo": summary.get("away_logo"),
                "score": summary["score"],
                "league": summary["league"],
                "venue": summary["venue"],
            }

        if scene_type == "goal":
            event = self._next(self.goal_events, "_goal_i")
            target = None
            if event:
                all_shots = summary["home_key_shots"] + summary["away_key_shots"]
                for sh in all_shots:
                    if sh.get("outcome") == "Goal" and sh.get("playerName") == event.get("player"):
                        target = sh.get("goalTarget")
                        break
            return {"type": "goal", "event": event, "target": target}

        if scene_type == "card_or_sub":
            event = self._next(self.card_sub_events, "_card_sub_i")
            return {"type": "card_or_sub", "event": event}

        if scene_type == "stat_bar":
            key, label, fmt = STAT_CYCLE[self._stat_i % len(STAT_CYCLE)]
            self._stat_i += 1
            return {
                "type": "stat_bar",
                "label": label,
                "format": fmt,
                "home_value": summary["home_stats"].get(key),
                "away_value": summary["away_stats"].get(key),
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
            }

        if scene_type == "shot_map":
            return {
                "type": "shot_map",
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
                "home_shots": summary["home_key_shots"],
                "away_shots": summary["away_key_shots"],
            }

        if scene_type == "player_card":
            picked = self._next(self.all_players, "_player_i")
            if not picked:
                return {"type": "player_card", "player": None, "team": None}
            player, team = picked
            return {"type": "player_card", "player": player, "team": team}

        if scene_type == "prediction":
            return {
                "type": "prediction",
                "prediction": summary.get("prematch_prediction"),
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
                "score": summary["score"],
            }

        if scene_type == "news":
            item = self._next(self.news, "_news_i")
            return {"type": "news", "headline": item}

        if scene_type == "momentum":
            return {
                "type": "momentum",
                "events": summary["events"],
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
            }

        if scene_type == "outro":
            return {
                "type": "outro",
                "home_team": summary["home_team"],
                "away_team": summary["away_team"],
                "score": summary["score"],
            }

        return {
            "type": "momentum",
            "events": summary["events"],
            "home_team": summary["home_team"],
            "away_team": summary["away_team"],
        }


MAX_SCENE_SECONDS = 12


def build_scenes(summary, timeline):
    builder = SceneBuilder(summary)
    scenes = []
    for block in timeline:
        duration = block["end"] - block["start"]
        n_parts = max(1, int(duration // MAX_SCENE_SECONDS) + 1)
        part_len = duration / n_parts

        for i in range(n_parts):
            start = block["start"] + i * part_len
            end = start + part_len
            content = builder.resolve(block["scene"])
            scenes.append({
                "start": start,
                "end": end,
                **content,
            })
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

    print(f"{len(scenes)} صحنه ساخته شد:\n")
    print(json.dumps(scenes, ensure_ascii=False, indent=2))
