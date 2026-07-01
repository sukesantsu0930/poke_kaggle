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
) -> list[str]:
    items = []
    for card_id, count in counter.most_common():
        if kind is not None and card_kind(card_rows, card_id) != kind:
            continue
        items.append(f"- {count} x {card_name(card_rows, card_id)} (ID {card_id})")
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

    archetypes: dict[str, dict[str, int]] = defaultdict(lambda: {"appearances": 0, "wins": 0, "losses": 0, "draws": 0})
    for group in groups.values():
        name = archetype_name(group["counter"], card_rows)
        archetypes[name]["appearances"] += len(group["appearances"])
        archetypes[name]["wins"] += group["wins"]
        archetypes[name]["losses"] += group["losses"]
        archetypes[name]["draws"] += group["draws"]

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
        "## ざっくりアーキタイプ分類",
        "",
    ]

    for name, values in sorted(archetypes.items(), key=lambda item: (-item[1]["appearances"], item[0])):
        lines.append(
            f"- {name}: {values['appearances']}回、{values['wins']}勝 {values['losses']}敗 {values['draws']}分"
        )

    lines.extend(
        [
            "",
        "## デッキ一覧",
        "",
        ]
    )

    sorted_groups = sorted(
        groups.values(),
        key=lambda g: (-len(g["appearances"]), -g["wins"], str(g["counter"])),
    )
    for deck_no, group in enumerate(sorted_groups, 1):
        counter: Counter[int] = group["counter"]
        main_pokemon = [
            card_name(card_rows, card_id)
            for card_id, _ in counter.most_common()
            if card_kind(card_rows, card_id) == "ポケモン"
        ][:4]
        title = " / ".join(main_pokemon) if main_pokemon else "ポケモン不明"
        lines.extend(
            [
                f"### Deck {deck_no}: {title}",
                "",
                f"- 推定アーキタイプ: {archetype_name(counter, card_rows)}",
                f"- 出現数: {len(group['appearances'])}",
                f"- 勝敗: {group['wins']}勝 {group['losses']}敗 {group['draws']}分",
                "- 使用者:",
            ]
        )
        for app in group["appearances"]:
            lines.append(
                f"  - Episode {app['episode_id']} P{app['player_index']}: {app['agent_name']} reward={app['reward']}"
            )

        for kind in ["ポケモン", "エネルギー", "トレーナーズ"]:
            lines.extend(["", f"{kind}:"])
            lines.extend(format_counter(counter, card_rows, kind=kind) or ["- なし"])
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
