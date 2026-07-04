from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from batch_evaluate import evaluate_pair  # noqa: E402
from solo_evaluate import run_solo_games, summarize_trials, write_outputs  # noqa: E402


def load_proposal(path: Path) -> dict:
    config_path = path / "proposal.yml" if path.is_dir() else path
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{config_path} must contain a mapping.")
    required = ["name", "deck", "agent", "concept", "protocol", "default_games", "max_steps"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ValueError(f"{config_path} is missing: {', '.join(missing)}")
    data["_proposal_dir"] = str(config_path.parent)
    return data


def resolve_from_root(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def resolve_protocol(proposal: dict) -> Path:
    protocol = Path(str(proposal["protocol"]))
    if protocol.is_absolute():
        return protocol
    return Path(proposal["_proposal_dir"]) / protocol


def default_output_dir(name: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return ROOT / "experiments" / "proposals" / name / stamp


def write_battle_csv(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "agent",
        "deck",
        "games",
        "seed",
        "wins",
        "losses",
        "draws",
        "unfinished",
        "start_failed",
        "win_rate",
        "mean_steps",
    ]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow({name: row.get(name) for name in fieldnames})


def format_percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def format_number(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_summary(
    *,
    output: Path,
    proposal: dict,
    agent: Path,
    deck: Path,
    protocol: Path,
    battle_summary: dict,
    solo_summary: dict,
    solo_trials_path: Path,
) -> None:
    unachieved = solo_summary.get("unachieved", 0)
    lines = [
        f"# {proposal['name']} 評価サマリ",
        "",
        f"- Deck: `{deck.relative_to(ROOT)}`",
        f"- Agent: `{agent.relative_to(ROOT)}`",
        f"- Protocol: `{protocol.relative_to(ROOT)}`",
        f"- Concept: {proposal['concept']}",
        "",
        "## 通常対戦評価",
        "",
        f"- Games: {battle_summary.get('games')}",
        f"- Win rate: {format_percent(battle_summary.get('win_rate'))}",
        f"- Wins/Losses/Draws: {battle_summary.get('wins')} / {battle_summary.get('losses')} / {battle_summary.get('draws')}",
        f"- Unfinished: {battle_summary.get('unfinished')}",
        f"- Mean steps: {format_number(battle_summary.get('mean_steps'))}",
        "",
        "## 一人回し評価",
        "",
        f"- Games: {solo_summary.get('games')}",
        f"- Achievement rate: {format_percent(solo_summary.get('achievement_rate'))}",
        f"- Achieved/Unachieved: {solo_summary.get('achieved')} / {unachieved}",
        f"- Mean achieved turn: {format_number(solo_summary.get('mean_first_achieved_turn'))}",
        f"- Mean score turn: {format_number(solo_summary.get('mean_score_turn'))}",
        f"- Passive opponent attacks: {solo_summary.get('passive_attacks')}",
        "",
        "## 次に見るべき失敗例",
        "",
    ]
    if unachieved:
        lines.extend(
            [
                f"- `{solo_trials_path.relative_to(ROOT)}` から `achieved=false` の試行を見る。",
                "- その試行で、コンセプトに必要なカードが引けていないのか、Agentが選べていないのかを分ける。",
            ]
        )
    else:
        lines.append("- 今回の一人回しでは未達成試行はありません。次は達成ターンの遅い試行を見ます。")
    lines.extend(
        [
            "",
            "## 出力",
            "",
            "- `battle_results.csv`",
            "- `solo_results.csv`",
            "- `solo_trials.jsonl`",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deck+agent proposal cycle.")
    parser.add_argument("--proposal", required=True)
    parser.add_argument("--games", type=int)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-dir")
    args = parser.parse_args()

    proposal_path = resolve_from_root(args.proposal)
    proposal = load_proposal(proposal_path)
    games = args.games if args.games is not None else int(proposal["default_games"])
    max_steps = args.max_steps if args.max_steps is not None else int(proposal["max_steps"])
    output_dir = resolve_from_root(args.output_dir) if args.output_dir else default_output_dir(str(proposal["name"]))
    output_dir.mkdir(parents=True, exist_ok=True)

    agent = resolve_from_root(str(proposal["agent"]))
    deck = resolve_from_root(str(proposal["deck"]))
    protocol = resolve_protocol(proposal)

    battle_summary = evaluate_pair(
        agent=agent,
        deck=deck,
        games=games,
        max_steps=max_steps,
        seed=args.seed,
        extras=[],
    )
    battle_row = {
        "agent": str(agent.relative_to(ROOT)),
        "deck": str(deck.relative_to(ROOT)),
        "seed": args.seed,
        **battle_summary,
    }
    battle_csv = output_dir / "battle_results.csv"
    write_battle_csv(battle_csv, battle_row)

    trials = run_solo_games(
        agent_path=agent,
        deck_path=deck,
        protocol_path=protocol,
        games=games,
        max_steps=max_steps,
        seed=args.seed,
    )
    solo_csv = output_dir / "solo_results.csv"
    solo_jsonl = output_dir / "solo_trials.jsonl"
    solo_summary = write_outputs(trials, solo_csv, solo_jsonl, max_steps)
    (output_dir / "proposal.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "solo_summary.json").write_text(json.dumps(solo_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_md = output_dir / "summary.md"
    write_summary(
        output=summary_md,
        proposal=proposal,
        agent=agent,
        deck=deck,
        protocol=protocol,
        battle_summary=battle_summary,
        solo_summary=solo_summary,
        solo_trials_path=solo_jsonl,
    )

    print(f"OK output={output_dir}")
    print(f"OK summary={summary_md}")


if __name__ == "__main__":
    main()

