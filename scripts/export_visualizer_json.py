import argparse
import importlib.util
import json
import os
import random
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
if str(SUBMISSION) not in sys.path:
    sys.path.insert(0, str(SUBMISSION))

from cg.api import AreaType, CardType, OptionType, SelectContext, SelectType, all_attack, all_card_data, to_observation_class  # noqa: E402
from cg.game import battle_finish, battle_select, battle_start, visualize_data  # noqa: E402


CARD_DATA = {card.cardId: card for card in all_card_data()}
ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}


def read_deck(path: Path) -> list[int]:
    values = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(values) != 60:
        raise ValueError(f"{path} must contain 60 card IDs, got {len(values)}.")
    return [int(value) for value in values]


def load_agent(path: Path, module_name: str):
    if path.is_dir():
        path = path / "main.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load agent: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "agent"):
        raise ValueError(f"{path} does not define agent(obs).")
    return module


def card_name(card_id: int | None) -> str:
    if card_id is None:
        return ""
    card = CARD_DATA.get(card_id)
    if card is None:
        return f"ID {card_id}"
    return f"{card.name} (ID {card_id})"


def enum_label(value, enum_cls=None) -> str:
    if value is None:
        return ""
    if enum_cls is not None and not hasattr(value, "name"):
        try:
            return enum_cls(value).name
        except Exception:
            pass
    return getattr(value, "name", str(value))


def _player(obs, option):
    player_index = option.playerIndex
    if player_index is None:
        player_index = obs.current.yourIndex
    if player_index is None or player_index < 0 or player_index >= len(obs.current.players):
        return None
    return obs.current.players[player_index]


def card_id_from_option(obs, option) -> int | None:
    if option.cardId is not None:
        return option.cardId
    player = _player(obs, option)
    if player is None:
        return None
    if option.type == OptionType.PLAY and option.index is not None and player.hand is not None:
        if 0 <= option.index < len(player.hand):
            return player.hand[option.index].id
    if option.area == AreaType.HAND and option.index is not None and player.hand is not None:
        if 0 <= option.index < len(player.hand):
            return player.hand[option.index].id
    if option.area == AreaType.DISCARD and option.index is not None:
        if 0 <= option.index < len(player.discard):
            return player.discard[option.index].id
    if option.area == AreaType.DECK and obs.select is not None and obs.select.deck is not None and option.index is not None:
        if 0 <= option.index < len(obs.select.deck):
            return obs.select.deck[option.index].id
    if option.area == AreaType.ACTIVE and option.index is not None and 0 <= option.index < len(player.active):
        pokemon = player.active[option.index]
        if option.type == OptionType.ENERGY_CARD and option.energyIndex is not None:
            if 0 <= option.energyIndex < len(pokemon.energyCards):
                return pokemon.energyCards[option.energyIndex].id
        if pokemon is not None:
            return pokemon.id
    if option.area == AreaType.BENCH and option.index is not None and 0 <= option.index < len(player.bench):
        pokemon = player.bench[option.index]
        if option.type == OptionType.ENERGY_CARD and option.energyIndex is not None:
            if 0 <= option.energyIndex < len(pokemon.energyCards):
                return pokemon.energyCards[option.energyIndex].id
        return pokemon.id
    return None


def option_label(obs, index: int) -> str:
    option = obs.select.option[index]
    if option.type == OptionType.END:
        return f"{index}: end turn"
    if option.type == OptionType.YES:
        return f"{index}: yes"
    if option.type == OptionType.NO:
        return f"{index}: no"
    if option.type == OptionType.NUMBER:
        return f"{index}: number {option.number}"
    if option.type == OptionType.ATTACK:
        attack = ATTACK_DATA.get(option.attackId)
        if attack is None:
            return f"{index}: attack {option.attackId}"
        return f"{index}: attack {attack.name} damage={attack.damage}"

    name = card_name(card_id_from_option(obs, option))
    base = enum_label(option.type, OptionType).lower()
    details = []
    if name:
        details.append(name)
    if option.area is not None:
        details.append(f"area={enum_label(option.area, AreaType)}")
    if option.index is not None:
        details.append(f"index={option.index}")
    if option.inPlayArea is not None:
        details.append(f"target={enum_label(option.inPlayArea, AreaType)}:{option.inPlayIndex}")
    return f"{index}: {base}" + (f" {' / '.join(details)}" if details else "")


def build_action_record(step: int, obs_dict: dict, action: list[int], actor: str) -> dict:
    obs = to_observation_class(obs_dict)
    selected = []
    options = []
    if obs.select is not None:
        options = [option_label(obs, i) for i in range(len(obs.select.option))]
        selected = [option_label(obs, i) for i in action if 0 <= i < len(obs.select.option)]
    return {
        "step": step,
        "actor": actor,
        "your_index": obs.current.yourIndex if obs.current is not None else None,
        "turn": obs.current.turn if obs.current is not None else None,
        "select_type": enum_label(obs.select.type, SelectType) if obs.select is not None else None,
        "select_context": enum_label(obs.select.context, SelectContext) if obs.select is not None else None,
        "min_count": obs.select.minCount if obs.select is not None else None,
        "max_count": obs.select.maxCount if obs.select is not None else None,
        "action": action,
        "selected": selected,
        "options": options,
    }


def random_action(obs_dict: dict) -> list[int]:
    obs = to_observation_class(obs_dict)
    if obs.select is None:
        raise ValueError("Deck selection is handled before battle_start.")
    count = random.randint(obs.select.minCount, obs.select.maxCount)
    return random.sample(range(len(obs.select.option)), count)


def run_game(agent0_module, agent1_module, deck0: list[int], deck1: list[int], max_steps: int) -> tuple[object, dict, list[dict]]:
    obs, start = battle_start(deck0, deck1)
    if obs is None:
        raise RuntimeError(f"battle_start failed: errorPlayer={start.errorPlayer} errorType={start.errorType}")

    agent_modules = [agent0_module, agent1_module]
    try:
        result = -1
        steps = 0
        action_log = []
        for steps in range(max_steps):
            typed = to_observation_class(obs)
            if typed.current is not None and typed.current.result != -1:
                result = typed.current.result
                break
            if typed.current is not None and typed.current.yourIndex in (0, 1):
                player_index = typed.current.yourIndex
                action = agent_modules[player_index].agent(obs)
                action_log.append(build_action_record(steps, obs, action, f"agent{player_index}"))
            else:
                action = random_action(obs)
                action_log.append(build_action_record(steps, obs, action, "random"))
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
        }, action_log
    finally:
        battle_finish()


def main():
    parser = argparse.ArgumentParser(description="公式Visualizer用のローカル対戦JSONを出力します。")
    parser.add_argument("--agent0", default="agents/cubchoo_ogerpon_rb")
    parser.add_argument("--deck0", default="decks/candidates/2026-06-30_top5/winrate_1_cubchoo_ogerpon.csv")
    parser.add_argument("--agent1", default="agents/cubchoo_ogerpon_rb")
    parser.add_argument("--deck1", default="decks/candidates/2026-06-30_top5/winrate_1_cubchoo_ogerpon.csv")
    parser.add_argument("--output", default="experiments/visualizer/latest_replay.json")
    parser.add_argument("--agent-log", default="experiments/visualizer/latest_agent_log.json")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-steps", type=int, default=1000)
    args = parser.parse_args()

    random.seed(args.seed)
    agent0_module = load_agent((ROOT / args.agent0).resolve(), "local_agent0")
    agent1_module = load_agent((ROOT / args.agent1).resolve(), "local_agent1")
    deck0 = read_deck((ROOT / args.deck0).resolve())
    deck1 = read_deck((ROOT / args.deck1).resolve())
    visualizer_payload, meta, action_log = run_game(agent0_module, agent1_module, deck0, deck1, args.max_steps)

    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(visualizer_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    agent_log = (ROOT / args.agent_log).resolve()
    agent_log.parent.mkdir(parents=True, exist_ok=True)
    agent_log.write_text(json.dumps(action_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"OK output={output}")
    print(f"OK agent_log={agent_log}")
    print(f"result={meta['result']} steps={meta['steps']}")


if __name__ == "__main__":
    main()
