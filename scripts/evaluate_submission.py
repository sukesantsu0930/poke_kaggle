import argparse
import importlib
import json
import os
import random
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from build_submission import build_submission


@dataclass
class GameRecord:
    game: int
    result: int | str
    steps: int
    seed: int


def _load_submission(submission_dir: Path):
    os.chdir(submission_dir)
    sys.path.insert(0, str(submission_dir))
    main = importlib.import_module("main")
    game = importlib.import_module("cg.game")
    api = importlib.import_module("cg.api")
    return main, game, api


def _random_agent(obs_dict):
    api = importlib.import_module("cg.api")
    obs = api.to_observation_class(obs_dict)
    if obs.select is None:
        main = importlib.import_module("main")
        return main.read_deck_csv()
    count = random.randint(obs.select.minCount, obs.select.maxCount)
    return random.sample(range(len(obs.select.option)), count)


def run_games(
    submission_dir: Path,
    games: int,
    max_steps: int,
    seed: int,
    verbose: bool = True,
) -> tuple[Counter, list[GameRecord]]:
    random.seed(seed)
    main, game, api = _load_submission(submission_dir)

    results = Counter()
    records = []
    for game_index in range(games):
        obs = None
        try:
            deck = main.read_deck_csv()
            obs, start = game.battle_start(deck, deck)
            if obs is None:
                results["start_failed"] += 1
                records.append(
                    GameRecord(
                        game=game_index,
                        result="start_failed",
                        steps=0,
                        seed=seed,
                    )
                )
                if verbose:
                    print(
                        f"game={game_index} start_failed "
                        f"errorPlayer={start.errorPlayer} errorType={start.errorType}"
                    )
                continue

            result = -1
            step = 0
            for step in range(max_steps):
                typed = api.to_observation_class(obs)
                if typed.current is not None and typed.current.result != -1:
                    result = typed.current.result
                    break

                if typed.current is not None and typed.current.yourIndex == 0:
                    action = main.agent(obs)
                else:
                    action = _random_agent(obs)
                obs = game.battle_select(action)

            results[result] += 1
            records.append(GameRecord(game=game_index, result=result, steps=step, seed=seed))
            if verbose:
                print(f"game={game_index} result={result} steps={step}")
        finally:
            try:
                game.battle_finish()
            except Exception:
                pass
    return results, records


def summarize(results: Counter, games: int) -> dict:
    wins = results.get(0, 0)
    losses = results.get(1, 0)
    draws = results.get(2, 0)
    unfinished = results.get(-1, 0)
    start_failed = results.get("start_failed", 0)
    return {
        "games": games,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "unfinished": unfinished,
        "start_failed": start_failed,
        "win_rate": wins / games if games else 0.0,
    }


def main_cli():
    parser = argparse.ArgumentParser()
    parser.add_argument("--submission-dir", default="submission")
    parser.add_argument("--agent")
    parser.add_argument("--deck")
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Additional file/dir to include when --agent/--deck builds a temp submission.",
    )
    parser.add_argument("--games", type=int, default=50)
    parser.add_argument("--max-steps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--jsonl")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.agent or args.deck:
        agent = Path(args.agent or "submission/main.py")
        deck = Path(args.deck or "submission/deck.csv")
        temp_root = Path(tempfile.mkdtemp(prefix="ptcg_eval_"))
        submission_dir = temp_root / "submission"
        build_submission(agent, deck, temp_root / "submission.zip", submission_dir, args.extra)
    else:
        submission_dir = Path(args.submission_dir).resolve()

    results, records = run_games(
        submission_dir.resolve(),
        games=args.games,
        max_steps=args.max_steps,
        seed=args.seed,
        verbose=not args.quiet,
    )
    summary = summarize(results, args.games)
    print("summary", summary)

    if args.jsonl:
        output = Path(args.jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w") as file:
            for record in records:
                file.write(json.dumps(record.__dict__) + "\n")


if __name__ == "__main__":
    main_cli()
