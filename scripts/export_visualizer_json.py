import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
if str(SUBMISSION) not in sys.path:
    sys.path.insert(0, str(SUBMISSION))

from cg.api import to_observation_class  # noqa: E402
from cg.game import battle_finish, battle_select, battle_start, visualize_data  # noqa: E402


def read_deck(path: Path) -> list[int]:
    values = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(values) != 60:
        raise ValueError(f"{path} must contain 60 card IDs, got {len(values)}.")
    return [int(value) for value in values]


def load_agent(path: Path):
    spec = importlib.util.spec_from_file_location("local_agent", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load agent: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["local_agent"] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "agent"):
        raise ValueError(f"{path} does not define agent(obs).")
    return module


def random_action(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        raise ValueError("Deck selection is handled before battle_start.")
    count = random.randint(obs.select.minCount, obs.select.maxCount)
    return random.sample(range(len(obs.select.option)), count)


def run_game(agent_module, deck0: list[int], deck1: list[int], max_steps: int) -> tuple[object, dict]:
    obs, start = battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: errorPlayer={start.errorPlayer} errorType={start.errorType}")

    try:
        result = -1
        steps = 0
        for steps in range(max_steps):
            typed = to_observation_class(obs)
            if typed.current is not None and typed.current.result != -1:
                result = typed.current.result
                break
            if typed.current is not None and typed.current.yourIndex == 0:
                action = agent_module.agent(obs)
            else:
                action = random_action(obs)
            obs = battle_select(action)

        raw = visualize_data()
        try:
            visualizer_payload = json.loads(raw)
        except json.JSONDecodeError:
            visualizer_payload = raw
        return visualizer_payload, {
            "result": result,
            "steps": steps,
            "max_steps": max_steps,
        }
    finally:
        battle_finish()


def main():
    parser = argparse.ArgumentParser(description="公式Visualizer用のローカル対戦JSONを出力します。")
    parser.add_argument("--agent", default="agents/rb_001_baseline.py")
    parser.add_argument("--deck0", default="decks/deck_001_sample.csv")
    parser.add_argument("--deck1", default="decks/deck_001_sample.csv")
    parser.add_argument("--output", default="experiments/visualizer/latest_replay.json")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args()

    random.seed(args.seed)
    agent_module = load_agent((ROOT / args.agent).resolve())
    deck0 = read_deck((ROOT / args.deck0).resolve())
    deck1 = read_deck((ROOT / args.deck1).resolve())
    visualizer_payload, meta = run_game(agent_module, deck0, deck1, args.max_steps)

    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(visualizer_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK output={output}")
    print(f"result={meta['result']} steps={meta['steps']}")


if __name__ == "__main__":
    main()
