from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from analyze_episode_decks import (
    archetype_name,
    card_kind,
    card_name,
    extract_decks,
    load_card_rows,
    signature,
)


def wilson_lower_bound(wins: int, games: int, z: float = 1.96) -> float:
    if games <= 0:
        return 0.0
    phat = wins / games
    denom = 1 + z * z / games
    center = phat + z * z / (2 * games)
    margin = z * ((phat * (1 - phat) + z * z / (4 * games)) / games) ** 0.5
    return (center - margin) / denom


def top_cards(counter: Counter[int], card_rows: dict[int, dict[str, str]], kind: str, limit: int) -> str:
    names = []
    for card_id, _ in counter.most_common():
        if card_kind(card_rows, card_id) == kind:
            names.append(card_name(card_rows, card_id))
        if len(names) >= limit:
            break
    return " / ".join(names) if names else "なし"


def load_manifest_paths(input_dir: Path, manifest: Path | None) -> list[Path]:
    if manifest is None:
        return sorted(input_dir.glob("*.json"))
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        names = [row["name"] for row in csv.DictReader(f)]
    return [input_dir / name for name in names if (input_dir / name).exists()]


def load_records(input_dir: Path, card_rows: dict[int, dict[str, str]], manifest: Path | None = None) -> list[dict]:
    records = []
    for path in load_manifest_paths(input_dir, manifest):
        episode = json.loads(path.read_text(encoding="utf-8"))
        decks = extract_decks(episode)
        agents = episode.get("info", {}).get("Agents", [])
        rewards = episode.get("rewards", [None, None])
        episode_id = episode.get("info", {}).get("EpisodeId", path.stem)
        deck_infos = []
        for player_index, deck_ids in enumerate(decks):
            counter = Counter(deck_ids)
            deck_infos.append(
                {
                    "signature": signature(deck_ids),
                    "counter": counter,
                    "archetype": archetype_name(counter, card_rows),
                    "player_index": player_index,
                    "agent_name": agents[player_index].get("Name", f"player{player_index}") if player_index < len(agents) else f"player{player_index}",
                    "reward": rewards[player_index] if player_index < len(rewards) else None,
                }
            )
        records.append(
            {
                "episode_id": episode_id,
                "path": path,
                "decks": deck_infos,
            }
        )
    return records


def summarize_exact_decks(records: list[dict], card_rows: dict[int, dict[str, str]]) -> list[dict]:
    groups: dict[tuple[tuple[int, int], ...], dict] = {}
    for record in records:
        for deck in record["decks"]:
            group = groups.setdefault(
                deck["signature"],
                {
                    "counter": deck["counter"],
                    "archetype": deck["archetype"],
                    "appearances": 0,
                    "wins": 0,
                    "losses": 0,
                    "examples": [],
                    "agents": Counter(),
                },
            )
            group["appearances"] += 1
            group["agents"][deck["agent_name"]] += 1
            if deck["reward"] is not None and deck["reward"] > 0:
                group["wins"] += 1
            elif deck["reward"] is not None and deck["reward"] < 0:
                group["losses"] += 1
            if len(group["examples"]) < 5:
                group["examples"].append((record["episode_id"], deck["player_index"], deck["agent_name"], deck["reward"]))

    summaries = []
    for group in groups.values():
        games = group["appearances"]
        wins = group["wins"]
        summaries.append(
            {
                **group,
                "win_rate": wins / games if games else 0.0,
                "wilson": wilson_lower_bound(wins, games),
                "main_pokemon": top_cards(group["counter"], card_rows, "ポケモン", 5),
                "main_trainers": top_cards(group["counter"], card_rows, "トレーナーズ", 6),
            }
        )
    return summaries


def summarize_archetypes(records: list[dict], card_rows: dict[int, dict[str, str]]) -> list[dict]:
    groups: dict[str, dict] = defaultdict(
        lambda: {
            "appearances": 0,
            "wins": 0,
            "losses": 0,
            "pokemon": Counter(),
            "trainers": Counter(),
            "examples": [],
            "agents": Counter(),
        }
    )
    for record in records:
        for deck in record["decks"]:
            group = groups[deck["archetype"]]
            group["appearances"] += 1
            group["agents"][deck["agent_name"]] += 1
            if deck["reward"] is not None and deck["reward"] > 0:
                group["wins"] += 1
            elif deck["reward"] is not None and deck["reward"] < 0:
                group["losses"] += 1
            for card_id, count in deck["counter"].items():
                kind = card_kind(card_rows, card_id)
                if kind == "ポケモン":
                    group["pokemon"][card_id] += count
                elif kind == "トレーナーズ":
                    group["trainers"][card_id] += count
            if len(group["examples"]) < 5:
                group["examples"].append((record["episode_id"], deck["player_index"], deck["agent_name"], deck["reward"]))

    summaries = []
    for name, group in groups.items():
        games = group["appearances"]
        wins = group["wins"]
        summaries.append(
            {
                "name": name,
                **group,
                "win_rate": wins / games if games else 0.0,
                "wilson": wilson_lower_bound(wins, games),
                "main_pokemon": top_cards(group["pokemon"], card_rows, "ポケモン", 5),
                "main_trainers": top_cards(group["trainers"], card_rows, "トレーナーズ", 6),
            }
        )
    return summaries


def summarize_matchups(records: list[dict]) -> list[dict]:
    matchups: dict[tuple[str, str], dict] = defaultdict(lambda: {"games": 0, "wins": 0})
    for record in records:
        left, right = record["decks"]
        left_name = left["archetype"]
        right_name = right["archetype"]
        if left_name == right_name:
            continue
        left_won = left["reward"] is not None and left["reward"] > 0
        for a, b, a_won in [(left_name, right_name, left_won), (right_name, left_name, not left_won)]:
            key = (a, b)
            matchups[key]["games"] += 1
            if a_won:
                matchups[key]["wins"] += 1

    rows = []
    for (a, b), values in matchups.items():
        games = values["games"]
        wins = values["wins"]
        rows.append(
            {
                "a": a,
                "b": b,
                "games": games,
                "wins": wins,
                "win_rate": wins / games if games else 0.0,
                "wilson": wilson_lower_bound(wins, games),
            }
        )
    return rows


def examples_to_lines(examples: list[tuple[int, int, str, int | None]]) -> list[str]:
    return [
        f"  - Episode {episode_id} P{player_index}: {agent_name} reward={reward} "
        f"(`downloads/episodes/2026-06-30/{episode_id}.json`)"
        for episode_id, player_index, agent_name, reward in examples
    ]


def build_report(input_dir: Path, card_csv: Path, min_exact: int, min_archetype: int, min_matchup: int, manifest: Path | None = None) -> str:
    card_rows = load_card_rows(card_csv)
    records = load_records(input_dir, card_rows, manifest)
    exact = summarize_exact_decks(records, card_rows)
    archetypes = summarize_archetypes(records, card_rows)
    matchups = summarize_matchups(records)

    lines = [
        "# 勝率候補デッキ探索",
        "",
        f"入力: `{input_dir}`",
        f"対象: {len(records)}試合、{len(records) * 2}プレイヤーデッキ",
        "",
        "## 探し方",
        "",
        "- まずアーキタイプ単位で、出現数が少なすぎる候補を落とす。",
        "- 単純勝率ではなく Wilson 信頼下限で並べる。少数の 1勝0敗 を過大評価しないため。",
        "- exact 60枚リストも見るが、ここではリストを保存せず主軸カードだけ表示する。",
        "- 最後に相性表を見る。全体勝率が普通でも、特定上位デッキに強い候補は残す。",
        "- 注意: 公開 episode はランダム実験ではないため、デッキ性能と操作者の強さが混ざっている。",
        "",
        "## アーキタイプ候補",
        "",
    ]

    filtered_archetypes = [row for row in archetypes if row["appearances"] >= min_archetype]
    for row in sorted(filtered_archetypes, key=lambda r: (-r["wilson"], -r["win_rate"], -r["appearances"], r["name"])):
        lines.extend(
            [
                f"### {row['name']}",
                "",
                f"- 出現数: {row['appearances']}",
                f"- 勝敗: {row['wins']}勝 {row['losses']}敗",
                f"- 勝率: {row['win_rate']:.1%}",
                f"- Wilson下限: {row['wilson']:.1%}",
                f"- 主軸ポケモン: {row['main_pokemon']}",
                f"- 主要トレーナーズ: {row['main_trainers']}",
                f"- 主な使用者: {', '.join(name for name, _ in row['agents'].most_common(4))}",
                "- 代表 episode:",
            ]
        )
        lines.extend(examples_to_lines(row["examples"]))
        lines.append("")

    lines.extend(["## exact 60枚リスト候補", ""])
    filtered_exact = [row for row in exact if row["appearances"] >= min_exact]
    for i, row in enumerate(sorted(filtered_exact, key=lambda r: (-r["wilson"], -r["win_rate"], -r["appearances"], r["main_pokemon"])), 1):
        lines.extend(
            [
                f"### Exact {i}: {row['archetype']}",
                "",
                f"- 出現数: {row['appearances']}",
                f"- 勝敗: {row['wins']}勝 {row['losses']}敗",
                f"- 勝率: {row['win_rate']:.1%}",
                f"- Wilson下限: {row['wilson']:.1%}",
                f"- 主軸ポケモン: {row['main_pokemon']}",
                f"- 主要トレーナーズ: {row['main_trainers']}",
                f"- 主な使用者: {', '.join(name for name, _ in row['agents'].most_common(4))}",
                "- 代表 episode:",
            ]
        )
        lines.extend(examples_to_lines(row["examples"]))
        lines.append("")

    lines.extend(["## 相性候補", ""])
    filtered_matchups = [row for row in matchups if row["games"] >= min_matchup]
    for row in sorted(filtered_matchups, key=lambda r: (-r["wilson"], -r["win_rate"], -r["games"], r["a"], r["b"]))[:20]:
        lines.append(
            f"- {row['a']} vs {row['b']}: {row['wins']}/{row['games']}勝、勝率{row['win_rate']:.1%}、Wilson下限{row['wilson']:.1%}"
        )
    if not filtered_matchups:
        lines.append("- 最低試合数を満たす相性データはありません。")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="downloads/episodes/2026-06-30")
    parser.add_argument("--card-csv", default="JP_Card_Data.csv")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--out", default="research/episode_deck_analysis/2026-06-30_winrate_candidates.md")
    parser.add_argument("--min-exact", type=int, default=3)
    parser.add_argument("--min-archetype", type=int, default=5)
    parser.add_argument("--min-matchup", type=int, default=3)
    args = parser.parse_args()

    report = build_report(
        Path(args.input_dir),
        Path(args.card_csv),
        args.min_exact,
        args.min_archetype,
        args.min_matchup,
        Path(args.manifest) if args.manifest else None,
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
