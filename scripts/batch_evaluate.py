import argparse
import csv
import datetime as dt
import tempfile
from pathlib import Path

from build_submission import build_submission
from evaluate_submission import run_games, summarize


ROOT = Path(__file__).resolve().parents[1]


def _collect(paths: list[str], directory: str, suffix: str) -> list[Path]:
    if paths:
        return [Path(path) for path in paths]
    base = ROOT / directory
    found = list(base.glob(f"*{suffix}"))
    if directory == "agents":
        found.extend(path.parent for path in base.glob("*/main.py"))
    return sorted(found)


def _default_output() -> Path:
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    return ROOT / "experiments" / f"batch_results_{stamp}.csv"


def evaluate_pair(agent: Path, deck: Path, games: int, max_steps: int, seed: int, extras: list[str]):
    temp_root = Path(tempfile.mkdtemp(prefix="ptcg_batch_"))
    submission_dir = temp_root / "submission"
    build_submission(agent, deck, temp_root / "submission.zip", submission_dir, extras)
    results, records = run_games(
        submission_dir.resolve(),
        games=games,
        max_steps=max_steps,
        seed=seed,
        verbose=False,
    )
    summary = summarize(results, games)
    if records:
        summary["mean_steps"] = sum(record.steps for record in records) / len(records)
    else:
        summary["mean_steps"] = 0.0
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", action="append", default=[])
    parser.add_argument("--deck", action="append", default=[])
    parser.add_argument("--extra", action="append", default=[])
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output")
    args = parser.parse_args()

    agents = _collect(args.agent, "agents", ".py")
    decks = _collect(args.deck, "decks", ".csv")
    output = Path(args.output) if args.output else _default_output()
    output.parent.mkdir(parents=True, exist_ok=True)

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

    with output.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for agent in agents:
            for deck in decks:
                try:
                    summary = evaluate_pair(
                        agent=agent,
                        deck=deck,
                        games=args.games,
                        max_steps=args.max_steps,
                        seed=args.seed,
                        extras=args.extra,
                    )
                    row = {
                        "agent": str(agent),
                        "deck": str(deck),
                        "seed": args.seed,
                        **summary,
                    }
                except Exception as exc:
                    row = {
                        "agent": str(agent),
                        "deck": str(deck),
                        "games": args.games,
                        "seed": args.seed,
                        "wins": 0,
                        "losses": 0,
                        "draws": 0,
                        "unfinished": 0,
                        "start_failed": args.games,
                        "win_rate": 0.0,
                        "mean_steps": 0.0,
                    }
                    print(f"failed agent={agent} deck={deck}: {type(exc).__name__}: {exc}")
                writer.writerow(row)
                print(
                    f"agent={agent.name} deck={deck.name} "
                    f"win_rate={float(row['win_rate']):.3f} "
                    f"wins={row['wins']}/{row['games']}"
                )

    print(output)


if __name__ == "__main__":
    main()
