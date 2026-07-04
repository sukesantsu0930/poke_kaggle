from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from analyze_episode_decks import archetype_name, card_kind, card_name, extract_decks, load_card_rows, signature
from rank_episode_deck_winrates import wilson_lower_bound


POPULAR_ARCHETYPES = ["ブリジュラスex鋼", "フーディン超", "メガスターミーex水", "ドラパルト系"]
WINRATE_ARCHETYPES = ["クマシュン / オーガポン いしずえのめんex", "マリィのベロバー / マシマシラ"]

POPULAR_FILE_STEMS = ["archaludon_steel", "alakazam_psychic", "mega_starmie_water", "dragapult"]
WINRATE_FILE_STEMS = ["cubchoo_ogerpon", "marnie_grimmsnarl"]


def load_manifest_paths(input_dir: Path, manifest: Path | None) -> list[Path]:
    if manifest is None:
        return sorted(input_dir.glob("*.json"))
    with manifest.open(encoding="utf-8-sig", newline="") as f:
        names = [row["name"] for row in csv.DictReader(f)]
    return [input_dir / name for name in names if (input_dir / name).exists()]


def load_exact_groups(input_dir: Path, card_rows: dict[int, dict[str, str]], manifest: Path | None = None) -> dict[tuple[tuple[int, int], ...], dict]:
    groups: dict[tuple[tuple[int, int], ...], dict] = {}
    for path in load_manifest_paths(input_dir, manifest):
        episode = json.loads(path.read_text(encoding="utf-8"))
        decks = extract_decks(episode)
        agents = episode.get("info", {}).get("Agents", [])
        rewards = episode.get("rewards", [None, None])
        episode_id = episode.get("info", {}).get("EpisodeId", path.stem)
        for player_index, deck_ids in enumerate(decks):
            counter = Counter(deck_ids)
            sig = signature(deck_ids)
            group = groups.setdefault(
                sig,
                {
                    "deck_ids": deck_ids,
                    "counter": counter,
                    "archetype": archetype_name(counter, card_rows),
                    "appearances": 0,
                    "wins": 0,
                    "losses": 0,
                    "examples": [],
                    "agents": Counter(),
                },
            )
            group["appearances"] += 1
            agent_name = agents[player_index].get("Name", f"player{player_index}") if player_index < len(agents) else f"player{player_index}"
            group["agents"][agent_name] += 1
            reward = rewards[player_index] if player_index < len(rewards) else None
            if reward is not None and reward > 0:
                group["wins"] += 1
            elif reward is not None and reward < 0:
                group["losses"] += 1
            if len(group["examples"]) < 5:
                group["examples"].append((episode_id, player_index, agent_name, reward))
    return groups


def score_group(group: dict) -> tuple[float, float, int]:
    games = group["appearances"]
    wins = group["wins"]
    win_rate = wins / games if games else 0.0
    return (wilson_lower_bound(wins, games), win_rate, games)


def pick_representative(groups: dict[tuple[tuple[int, int], ...], dict], archetype: str) -> dict:
    candidates = [group for group in groups.values() if group["archetype"] == archetype]
    if not candidates:
        raise ValueError(f"No exact deck found for archetype: {archetype}")
    return sorted(candidates, key=score_group, reverse=True)[0]


def write_deck_csv(deck_ids: list[int], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(card_id) for card_id in deck_ids) + "\n", encoding="utf-8")


def format_cards(counter: Counter[int], card_rows: dict[int, dict[str, str]], kind: str, limit: int = 10) -> list[str]:
    lines = []
    for card_id, count in counter.most_common():
        if card_kind(card_rows, card_id) != kind:
            continue
        lines.append(f"- {count} x {card_name(card_rows, card_id)} (ID {card_id})")
        if len(lines) >= limit:
            break
    return lines or ["- なし"]


def build_summary(picks: list[tuple[str, str, dict, Path]], card_rows: dict[int, dict[str, str]]) -> str:
    lines = [
        "# 候補デッキ",
        "",
        "episode 解析から、指定した注目アーキタイプを exact 60枚で抜き出したものです。",
        "",
        "## 一覧",
        "",
    ]
    if not picks:
        lines.extend(
            [
                "- 条件に合う候補デッキは見つかりませんでした。",
                "- 少件数の動作確認では正常です。本番分析では取得件数を増やしてください。",
            ]
        )
        return "\n".join(lines) + "\n"

    for label, reason, group, path in picks:
        games = group["appearances"]
        wins = group["wins"]
        win_rate = wins / games if games else 0.0
        lines.append(f"- `{path.name}`: {label} / {reason} / {wins}勝{group['losses']}敗 / 勝率{win_rate:.1%} / 出現数{games}")

    for label, reason, group, path in picks:
        games = group["appearances"]
        wins = group["wins"]
        win_rate = wins / games if games else 0.0
        lines.extend(
            [
                "",
                f"## {path.name}",
                "",
                f"- アーキタイプ: {label}",
                f"- 選定理由: {reason}",
                f"- exact 出現数: {games}",
                f"- 勝敗: {wins}勝 {group['losses']}敗",
                f"- 勝率: {win_rate:.1%}",
                f"- Wilson下限: {wilson_lower_bound(wins, games):.1%}",
                f"- 主な使用者: {', '.join(name for name, _ in group['agents'].most_common(4))}",
                f"- ファイル: `{path}`",
                "",
                "ポケモン:",
            ]
        )
        lines.extend(format_cards(group["counter"], card_rows, "ポケモン"))
        lines.extend(["", "エネルギー:"])
        lines.extend(format_cards(group["counter"], card_rows, "エネルギー"))
        lines.extend(["", "トレーナーズ:"])
        lines.extend(format_cards(group["counter"], card_rows, "トレーナーズ", limit=15))
        lines.extend(["", "代表 episode:"])
        for episode_id, player_index, agent_name, reward in group["examples"]:
            lines.append(f"- Episode {episode_id} P{player_index}: {agent_name} reward={reward}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="episode解析から候補デッキ5種をCSV化します。")
    parser.add_argument("--input-dir", default="downloads/episodes/2026-06-30")
    parser.add_argument("--card-csv", default="JP_Card_Data.csv")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--out-dir", default="decks/candidates/2026-06-30_top5")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    card_rows = load_card_rows(Path(args.card_csv))
    groups = load_exact_groups(input_dir, card_rows, Path(args.manifest) if args.manifest else None)

    selected: list[tuple[str, str, dict, Path]] = []
    for index, archetype in enumerate(POPULAR_ARCHETYPES, 1):
        try:
            group = pick_representative(groups, archetype)
        except ValueError as exc:
            print(f"skip {archetype}: {exc}")
            continue
        path = Path(args.out_dir) / f"popular_{index}_{POPULAR_FILE_STEMS[index - 1]}.csv"
        write_deck_csv(group["deck_ids"], path)
        selected.append((archetype, "母数が多いデッキ", group, path))

    for index, archetype in enumerate(WINRATE_ARCHETYPES, 1):
        try:
            group = pick_representative(groups, archetype)
        except ValueError as exc:
            print(f"skip {archetype}: {exc}")
            continue
        path = Path(args.out_dir) / f"winrate_{index}_{WINRATE_FILE_STEMS[index - 1]}.csv"
        write_deck_csv(group["deck_ids"], path)
        selected.append((archetype, "勝率候補デッキ", group, path))

    summary_path = Path(args.out_dir) / "README.md"
    summary_path.write_text(build_summary(selected, card_rows), encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
