from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
if str(SUBMISSION) not in sys.path:
    sys.path.insert(0, str(SUBMISSION))

from cg.api import OptionType, SelectContext, SelectType, to_observation_class  # noqa: E402
from cg.game import battle_finish, battle_select, battle_start  # noqa: E402


@dataclass
class SoloTrial:
    trial: int
    seed: int
    result: int | str
    steps: int
    achieved: bool
    first_achieved_turn: int | None
    first_achieved_step: int | None
    passive_attacks: int
    protocol_result: dict


def read_deck(path: Path) -> list[int]:
    values = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(values) != 60:
        raise ValueError(f"{path} must contain 60 card IDs, got {len(values)}.")
    return [int(value) for value in values]


def load_module(path: Path, module_name: str):
    if path.is_dir():
        path = path / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def load_agent(path: Path):
    module = load_module(path, "proposal_agent")
    if not hasattr(module, "agent"):
        raise ValueError(f"{path} does not define agent(obs_dict).")
    return module


def load_protocol(path: Path):
    module = load_module(path, "proposal_protocol")
    if hasattr(module, "create_protocol"):
        return module.create_protocol()
    if hasattr(module, "Protocol"):
        return module.Protocol()
    raise ValueError(f"{path} must define create_protocol() or Protocol.")


def _fill_selection(obs, preferred: list[int]) -> list[int]:
    select = obs.select
    if select is None or select.maxCount == 0:
        return []
    result = []
    for index in preferred:
        if index not in result and 0 <= index < len(select.option):
            result.append(index)
        if len(result) >= select.maxCount:
            break
    for index in range(len(select.option)):
        if len(result) >= select.minCount:
            break
        if index not in result:
            result.append(index)
    return result[: select.maxCount]


def passive_action(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        raise ValueError("Deck selection is handled before battle_start.")

    select = obs.select
    options = select.option
    by_type: dict[OptionType, list[int]] = {}
    for index, option in enumerate(options):
        by_type.setdefault(option.type, []).append(index)

    if select.type == SelectType.MAIN:
        preferred = by_type.get(OptionType.END, [])
        preferred += by_type.get(OptionType.NO, [])
        preferred += by_type.get(OptionType.RETREAT, [])
        # Avoid attacks, play, attach, evolve, and abilities unless forced.
        passive_forced = []
        for option_type in (OptionType.CARD, OptionType.NUMBER, OptionType.YES):
            passive_forced.extend(by_type.get(option_type, []))
        return _fill_selection(obs, preferred + passive_forced)

    if select.type == SelectType.YES_NO:
        yes = by_type.get(OptionType.YES, [])
        no = by_type.get(OptionType.NO, [])
        if select.context == SelectContext.MULLIGAN:
            return _fill_selection(obs, no + yes)
        return _fill_selection(obs, no + yes)

    if select.type == SelectType.COUNT:
        numbered = [
            (i, option.number if option.number is not None else 0)
            for i, option in enumerate(options)
            if option.type == OptionType.NUMBER
        ]
        numbered.sort(key=lambda item: item[1])
        return _fill_selection(obs, [i for i, _ in numbered])

    non_attacks = [i for i, option in enumerate(options) if option.type != OptionType.ATTACK]
    return _fill_selection(obs, non_attacks)


def run_solo_games(
    *,
    agent_path: Path,
    deck_path: Path,
    protocol_path: Path,
    games: int,
    max_steps: int,
    seed: int,
) -> list[SoloTrial]:
    random.seed(seed)
    agent = load_agent(agent_path)
    deck = read_deck(deck_path)
    trials = []

    for trial_index in range(games):
        protocol = load_protocol(protocol_path)
        obs, start = battle_start(deck, deck)
        if obs is None:
            trials.append(
                SoloTrial(
                    trial=trial_index,
                    seed=seed + trial_index,
                    result="start_failed",
                    steps=0,
                    achieved=False,
                    first_achieved_turn=None,
                    first_achieved_step=None,
                    passive_attacks=0,
                    protocol_result={"error": f"start_failed errorPlayer={start.errorPlayer} errorType={start.errorType}"},
                )
            )
            continue

        result: int | str = -1
        passive_attacks = 0
        step = 0
        try:
            for step in range(max_steps):
                typed = to_observation_class(obs)
                if typed.current is not None and typed.current.result != -1:
                    result = typed.current.result
                    break

                if typed.current is not None and typed.current.yourIndex == 0:
                    action = agent.agent(obs)
                    actor = "agent0"
                else:
                    action = passive_action(obs)
                    actor = "passive1"
                    if typed.select is not None:
                        for index in action:
                            if 0 <= index < len(typed.select.option):
                                passive_attacks += int(typed.select.option[index].type == OptionType.ATTACK)

                if hasattr(protocol, "observe_before_action"):
                    protocol.observe_before_action(typed, action, actor, step)
                previous = typed
                obs = battle_select(action)
                next_typed = to_observation_class(obs)
                if hasattr(protocol, "observe_after_action"):
                    protocol.observe_after_action(previous, action, next_typed, actor, step)

            protocol_result = protocol.trial_result() if hasattr(protocol, "trial_result") else {}
            trials.append(
                SoloTrial(
                    trial=trial_index,
                    seed=seed + trial_index,
                    result=result,
                    steps=step,
                    achieved=bool(protocol_result.get("achieved")),
                    first_achieved_turn=protocol_result.get("first_achieved_turn"),
                    first_achieved_step=protocol_result.get("first_achieved_step"),
                    passive_attacks=passive_attacks,
                    protocol_result=protocol_result,
                )
            )
        finally:
            battle_finish()

    return trials


def summarize_trials(trials: list[SoloTrial], max_steps: int) -> dict:
    total = len(trials)
    achieved = [trial for trial in trials if trial.achieved]
    achieved_turns = [trial.first_achieved_turn for trial in achieved if trial.first_achieved_turn is not None]
    score_turns = [trial.first_achieved_turn if trial.first_achieved_turn is not None else max_steps for trial in trials]
    return {
        "games": total,
        "achieved": len(achieved),
        "unachieved": total - len(achieved),
        "achievement_rate": len(achieved) / total if total else 0.0,
        "mean_first_achieved_turn": sum(achieved_turns) / len(achieved_turns) if achieved_turns else None,
        "mean_score_turn": sum(score_turns) / len(score_turns) if score_turns else None,
        "passive_attacks": sum(trial.passive_attacks for trial in trials),
    }


def write_outputs(trials: list[SoloTrial], output_csv: Path, output_jsonl: Path, max_steps: int) -> dict:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_trials(trials, max_steps)

    with output_csv.open("w", encoding="utf-8", newline="") as file:
        fieldnames = [
            "trial",
            "seed",
            "result",
            "steps",
            "achieved",
            "first_achieved_turn",
            "first_achieved_step",
            "passive_attacks",
        ]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for trial in trials:
            writer.writerow({name: getattr(trial, name) for name in fieldnames})

    with output_jsonl.open("w", encoding="utf-8") as file:
        for trial in trials:
            file.write(json.dumps(trial.__dict__, ensure_ascii=False) + "\n")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run solitaire-style concept evaluation.")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--deck", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output-csv", default="experiments/solo_results.csv")
    parser.add_argument("--output-jsonl", default="experiments/solo_trials.jsonl")
    args = parser.parse_args()

    trials = run_solo_games(
        agent_path=(ROOT / args.agent).resolve(),
        deck_path=(ROOT / args.deck).resolve(),
        protocol_path=(ROOT / args.protocol).resolve(),
        games=args.games,
        max_steps=args.max_steps,
        seed=args.seed,
    )
    summary = write_outputs(
        trials,
        (ROOT / args.output_csv).resolve(),
        (ROOT / args.output_jsonl).resolve(),
        args.max_steps,
    )
    print("summary", summary)


if __name__ == "__main__":
    main()

