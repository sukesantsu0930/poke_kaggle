from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def load_card_rows(path: Path) -> dict[int, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {int(row["カード ID"]): row for row in csv.DictReader(f)}


def card_name(card_rows: dict[int, dict[str, str]], card_id: int) -> str:
    row = card_rows.get(card_id)
    if not row:
        return f"Unknown ID {card_id}"
    return row["カード名"]


def card_kind(card_rows: dict[int, dict[str, str]], card_id: int) -> str:
    row = card_rows.get(card_id)
    if not row:
        return "不明"
    kind = row["ポケモンの進化の段階/エネルギー・トレーナーズの種類"]
    if kind.startswith("ポケモン/"):
        return "ポケモン"
    if "エネルギー" in kind:
        return "エネルギー"
    return "トレーナーズ"


def extract_decks(episode: dict) -> list[list[int]]:
    for step in episode.get("steps", []):
        for agent_step in step:
            for visual in agent_step.get("visualize", []) or []:
                action = visual.get("action")
                if (
                    isinstance(action, list)
                    and len(action) == 2
                    and all(isinstance(deck, list) and len(deck) == 60 for deck in action)
                ):
                    return [[int(card_id) for card_id in deck] for deck in action]
    raise ValueError("60-card deck lists were not found in visualize.action")


def signature(deck_ids: list[int]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted(Counter(deck_ids).items()))


def format_counter(
    counter: Counter[int],
    card_rows: dict[int, dict[str, str]],
    *,
    kind: str | None = None,
    limit: int | None = None,
) -> list[str]:
    items = []
    for card_id, count in counter.most_common():
        if kind is not None and card_kind(card_rows, card_id) != kind:
            continue
        items.append(f"- {card_name(card_rows, card_id)} (ID {card_id}): 延べ{count}枚")
        if limit is not None and len(items) >= limit:
            break
    return items


def archetype_name(counter: Counter[int], card_rows: dict[int, dict[str, str]]) -> str:
    names = {card_name(card_rows, card_id) for card_id in counter}
    if {"ジュラルドン", "ブリジュラスex"} <= names:
        return "ブリジュラスex鋼"
    if {"ヒトデマン", "メガスターミーex"} <= names:
        return "メガスターミーex水"
    if {"ケーシィ", "ユンゲラー", "フーディン"} <= names:
        return "フーディン超"
    if {"リオル", "メガルカリオex"} <= names:
        return "メガルカリオex闘"
    if {"ユキワラシ", "メガユキメノコex"} <= names:
        return "メガユキメノコex水"
    if "メガガルーラex" in names:
        return "メガガルーラex多色"
    if any(name.startswith("ナンジャモの") for name in names):
        return "ナンジャモ雷"
    if {"ドラメシヤ", "ドロンチ"} <= names:
        return "ドラパルト系"
    main_pokemon = [
        card_name(card_rows, card_id)
        for card_id, _ in counter.most_common()
        if card_kind(card_rows, card_id) == "ポケモン"
    ][:2]
    return " / ".join(main_pokemon) if main_pokemon else "不明"


def build_report(input_dir: Path, card_csv: Path) -> str:
    card_rows = load_card_rows(card_csv)
    json_paths = sorted(input_dir.glob("*.json"))
    groups: dict[tuple[tuple[int, int], ...], dict] = {}

    for path in json_paths:
        episode = json.loads(path.read_text(encoding="utf-8"))
        decks = extract_decks(episode)
        agents = episode.get("info", {}).get("Agents", [])
        rewards = episode.get("rewards", [None, None])
        episode_id = episode.get("info", {}).get("EpisodeId", path.stem)

        for player_index, deck_ids in enumerate(decks):
            sig = signature(deck_ids)
            group = groups.setdefault(
                sig,
                {
                    "counter": Counter(deck_ids),
                    "appearances": [],
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                },
            )
            reward = rewards[player_index] if player_index < len(rewards) else None
            if reward is not None and reward > 0:
                group["wins"] += 1
            elif reward is not None and reward < 0:
                group["losses"] += 1
            else:
                group["draws"] += 1
            agent_name = agents[player_index].get("Name", f"player{player_index}") if player_index < len(agents) else f"player{player_index}"
            group["appearances"].append(
                {
                    "episode_id": episode_id,
                    "player_index": player_index,
                    "agent_name": agent_name,
                    "reward": reward,
                }
        )

    archetypes: dict[str, dict] = defaultdict(
        lambda: {
            "appearances": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "pokemon": Counter(),
            "energy": Counter(),
            "trainers": Counter(),
            "examples": [],
        }
    )
    for group in groups.values():
        name = archetype_name(group["counter"], card_rows)
        archetypes[name]["appearances"] += len(group["appearances"])
        archetypes[name]["wins"] += group["wins"]
        archetypes[name]["losses"] += group["losses"]
        archetypes[name]["draws"] += group["draws"]
        for card_id, count in group["counter"].items():
            kind = card_kind(card_rows, card_id)
            weighted_count = count * len(group["appearances"])
            if kind == "ポケモン":
                archetypes[name]["pokemon"][card_id] += weighted_count
            elif kind == "エネルギー":
                archetypes[name]["energy"][card_id] += weighted_count
            elif kind == "トレーナーズ":
                archetypes[name]["trainers"][card_id] += weighted_count
        archetypes[name]["examples"].extend(group["appearances"])

    lines = [
        "# 最新エピソードのデッキ概観",
        "",
        f"入力: `{input_dir}`",
        f"対象 JSON: {len(json_paths)} 試合",
        f"復元したプレイヤーデッキ: {len(json_paths) * 2}",
        f"ユニークな 60 枚リスト: {len(groups)}",
        "",
        "## 読み取り上の注意",
        "",
        "- この Kaggle episode JSON では、`visualize.action` に両プレイヤーの 60 枚カード ID リストが入っていた。",
        "- したがって、今回取得したファイルについては 60 枚を復元できる。",
        "- ただし、これは `visualize` 付き公開 episode に依存する。別形式のログでは同じとは限らない。",
        "",
        "## アーキタイプ別の主軸カード",
        "",
    ]

    for name, values in sorted(archetypes.items(), key=lambda item: (-item[1]["appearances"], item[0])):
        win_rate = values["wins"] / values["appearances"] if values["appearances"] else 0.0
        lines.extend(
            [
                f"### {name}",
                "",
                f"- 出現数: {values['appearances']} / {len(json_paths) * 2}",
                f"- 勝敗: {values['wins']}勝 {values['losses']}敗 {values['draws']}分",
                f"- 勝率: {win_rate:.1%}",
                "- 代表 episode:",
            ]
        )
        for app in values["examples"][:5]:
            lines.append(
                f"  - Episode {app['episode_id']} P{app['player_index']}: {app['agent_name']} reward={app['reward']} "
                f"(`downloads/episodes/2026-06-30/{app['episode_id']}.json`)"
            )

        lines.extend(["", "主軸ポケモン:"])
        lines.extend(format_counter(values["pokemon"], card_rows, limit=8) or ["- なし"])
        lines.extend(["", "よく入るエネルギー:"])
        lines.extend(format_counter(values["energy"], card_rows, limit=5) or ["- なし"])
        lines.extend(["", "よく入るトレーナーズ:"])
        lines.extend(format_counter(values["trainers"], card_rows, limit=10) or ["- なし"])
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="downloads/episodes/2026-06-30")
    parser.add_argument("--card-csv", default="JP_Card_Data.csv")
    parser.add_argument("--out", default="research/episode_deck_analysis/2026-06-30_sample.md")
    args = parser.parse_args()

    report = build_report(Path(args.input_dir), Path(args.card_csv))
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
