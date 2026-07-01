import argparse
import csv
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
if str(SUBMISSION) not in sys.path:
    sys.path.insert(0, str(SUBMISSION))

from cg.api import (  # noqa: E402
    AreaType,
    Card,
    CardType,
    Log,
    Observation,
    Option,
    OptionType,
    Pokemon,
    SelectContext,
    SelectType,
    State,
    all_attack,
    all_card_data,
    to_observation_class,
)
from cg.game import battle_finish, battle_select, battle_start  # noqa: E402
from deck_validation import validate_deck_file  # noqa: E402


CARD_DATA = {card.cardId: card for card in all_card_data()}
ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}
JP_CARD_NAMES = {}
JP_CARD_DATA = ROOT / "JP_Card_Data.csv"
if JP_CARD_DATA.exists():
    with JP_CARD_DATA.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            JP_CARD_NAMES.setdefault(int(row["カード ID"]), row["カード名"])
CARD_IMAGE_DIR = ROOT / "card_images" / "jp"
CARD_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

AREA_LABELS = {
    AreaType.DECK: "山札",
    AreaType.HAND: "手札",
    AreaType.DISCARD: "トラッシュ",
    AreaType.ACTIVE: "バトル場",
    AreaType.BENCH: "ベンチ",
    AreaType.PRIZE: "サイド",
    AreaType.STADIUM: "スタジアム",
    AreaType.ENERGY: "エネルギー",
    AreaType.TOOL: "ポケモンのどうぐ",
    AreaType.PRE_EVOLUTION: "進化前",
    AreaType.PLAYER: "プレイヤー",
    AreaType.LOOKING: "見ているカード",
}

OPTION_LABELS = {
    OptionType.NUMBER: "数を選ぶ",
    OptionType.YES: "はい",
    OptionType.NO: "いいえ",
    OptionType.CARD: "カードを選ぶ",
    OptionType.TOOL_CARD: "どうぐを選ぶ",
    OptionType.ENERGY_CARD: "エネルギーを選ぶ",
    OptionType.ENERGY: "エネルギーを選ぶ",
    OptionType.PLAY: "手札から使う",
    OptionType.ATTACH: "エネルギーをつける",
    OptionType.EVOLVE: "進化する",
    OptionType.ABILITY: "特性を使う",
    OptionType.DISCARD: "トラッシュする",
    OptionType.RETREAT: "にげる",
    OptionType.ATTACK: "ワザを使う",
    OptionType.END: "番を終わる",
}

CONTEXT_LABELS = {
    SelectContext.MAIN: "行動を選ぶ",
    SelectContext.SETUP_ACTIVE_POKEMON: "最初のバトルポケモンを選ぶ",
    SelectContext.SETUP_BENCH_POKEMON: "最初にベンチへ出すポケモンを選ぶ",
    SelectContext.SWITCH: "入れ替えるポケモンを選ぶ",
    SelectContext.TO_ACTIVE: "バトル場に出すカードを選ぶ",
    SelectContext.TO_BENCH: "ベンチに出すカードを選ぶ",
    SelectContext.TO_FIELD: "場に出すカードを選ぶ",
    SelectContext.TO_HAND: "手札に加えるカードを選ぶ",
    SelectContext.DISCARD: "トラッシュするカードを選ぶ",
    SelectContext.TO_DECK: "山札に戻すカードを選ぶ",
    SelectContext.TO_DECK_BOTTOM: "山札の下に戻すカードを選ぶ",
    SelectContext.TO_PRIZE: "サイドに置くカードを選ぶ",
    SelectContext.NOT_MOVE: "動かさないカードを選ぶ",
    SelectContext.DAMAGE_COUNTER: "ダメカンをのせるポケモンを選ぶ",
    SelectContext.DAMAGE_COUNTER_ANY: "ダメカンをのせるポケモンを選ぶ",
    SelectContext.DAMAGE: "ダメージを与えるポケモンを選ぶ",
    SelectContext.REMOVE_DAMAGE_COUNTER: "ダメカンを取り除くポケモンを選ぶ",
    SelectContext.HEAL: "回復するポケモンを選ぶ",
    SelectContext.EVOLVES_FROM: "進化元を選ぶ",
    SelectContext.EVOLVES_TO: "進化先を選ぶ",
    SelectContext.DEVOLVE: "退化するポケモンを選ぶ",
    SelectContext.ATTACH_FROM: "つけるカードを選ぶ",
    SelectContext.ATTACH_TO: "つけ先のポケモンを選ぶ",
    SelectContext.DETACH_FROM: "はがすカードを選ぶ",
    SelectContext.LOOK: "見るカードを選ぶ",
    SelectContext.EFFECT_TARGET: "効果の対象を選ぶ",
    SelectContext.DISCARD_ENERGY_CARD: "トラッシュするエネルギーを選ぶ",
    SelectContext.DISCARD_TOOL_CARD: "トラッシュするどうぐを選ぶ",
    SelectContext.SWITCH_ENERGY_CARD: "入れ替えるエネルギーを選ぶ",
    SelectContext.DISCARD_CARD_OR_ATTACHED_CARD: "トラッシュするカードを選ぶ",
    SelectContext.DISCARD_ENERGY: "トラッシュするエネルギーを選ぶ",
    SelectContext.TO_HAND_ENERGY: "手札に戻すエネルギーを選ぶ",
    SelectContext.TO_DECK_ENERGY: "山札に戻すエネルギーを選ぶ",
    SelectContext.SWITCH_ENERGY: "入れ替えるエネルギーを選ぶ",
    SelectContext.SKILL_ORDER: "効果の順番を選ぶ",
    SelectContext.ATTACK: "使うワザを選ぶ",
    SelectContext.DISABLE_ATTACK: "使えなくするワザを選ぶ",
    SelectContext.EVOLVE: "進化を選ぶ",
    SelectContext.DRAW_COUNT: "引く枚数を選ぶ",
    SelectContext.DAMAGE_COUNTER_COUNT: "のせるダメカンの数を選ぶ",
    SelectContext.REMOVE_DAMAGE_COUNTER_COUNT: "取り除くダメカンの数を選ぶ",
    SelectContext.IS_FIRST: "先攻にするか選ぶ",
    SelectContext.MULLIGAN: "引き直すか選ぶ",
    SelectContext.ACTIVATE: "効果を使うか選ぶ",
    SelectContext.FIRST_EFFECT: "先に処理する効果を選ぶ",
    SelectContext.MORE_DEVOLVE: "さらに退化するか選ぶ",
    SelectContext.COIN_HEAD: "オモテを選ぶか決める",
    SelectContext.AFFECT_SPECIAL_CONDITION: "特殊状態を選ぶ",
    SelectContext.RECOVER_SPECIAL_CONDITION: "回復する特殊状態を選ぶ",
}


class ManualBattle:
    def __init__(self):
        self.obs_dict = None
        self.started = False
        self.step = 0
        self.deck0_name = None
        self.deck1_name = None

    def reset(self):
        if self.started:
            try:
                battle_finish()
            except Exception:
                pass
        self.obs_dict = None
        self.started = False
        self.step = 0
        self.deck0_name = None
        self.deck1_name = None

    def start(self, deck0_path: Path, deck1_path: Path):
        self.reset()
        deck0 = read_deck(deck0_path)
        deck1 = read_deck(deck1_path)
        obs, start_data = battle_start(deck0, deck1)
        if obs is None:
            raise ValueError(
                f"battle_start failed: errorPlayer={start_data.errorPlayer} "
                f"errorType={start_data.errorType}"
            )
        self.obs_dict = obs
        self.started = True
        self.step = 0
        self.deck0_name = deck0_path.name
        self.deck1_name = deck1_path.name

    def select(self, indexes: list[int]):
        if not self.started or self.obs_dict is None:
            raise ValueError("Battle is not started.")
        obs = to_observation_class(self.obs_dict)
        if obs.select is None:
            raise ValueError("Current observation has no selectable options.")
        validate_selection(indexes, obs)
        self.obs_dict = battle_select(indexes)
        self.step += 1


BATTLE = ManualBattle()


def read_deck(path: Path) -> list[int]:
    values = [line.strip() for line in path.read_text().splitlines() if line.strip()]
    if len(values) != 60:
        raise ValueError(f"{path} must contain 60 card IDs, got {len(values)}.")
    return [int(value) for value in values]


def deck_files() -> list[Path]:
    return sorted((ROOT / "decks").rglob("*.csv"))


def deck_path_from_name(name: str) -> Path:
    candidates = {str(path.relative_to(ROOT)): path for path in deck_files()}
    if name not in candidates:
        raise ValueError(f"Unknown deck: {name}")
    return candidates[name]


def validate_selection(indexes: list[int], obs: Observation):
    select = obs.select
    if len(indexes) < select.minCount or len(indexes) > select.maxCount:
        raise ValueError(f"Select {select.minCount} to {select.maxCount} options.")
    if len(set(indexes)) != len(indexes):
        raise ValueError("Duplicate option indexes are not allowed.")
    for index in indexes:
        if index < 0 or index >= len(select.option):
            raise ValueError(f"Option index out of range: {index}")


def card_name(card_id: int | None, *, generic_energy: bool = True) -> str:
    if card_id is None:
        return ""
    if generic_energy and is_energy_card(card_id):
        return "エネルギー"
    jp_name = JP_CARD_NAMES.get(card_id)
    if jp_name is not None:
        return f"{jp_name} (ID {card_id})"
    card = CARD_DATA.get(card_id)
    if card is None:
        return f"#{card_id}"
    return f"{card.name} (ID {card_id})"


def is_energy_card(card_id: int | None) -> bool:
    if card_id is None:
        return False
    card = CARD_DATA.get(card_id)
    return card is not None and card.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY)


def card_from_option(option: Option, obs: Observation) -> Card | None:
    if option.cardId is not None:
        return Card(id=option.cardId, serial=option.serial or -1, playerIndex=option.playerIndex or -1)
    if option.type == OptionType.PLAY:
        return card_from_hand_index(option, obs)
    return card_from_area_option(option, obs)


def card_from_hand_index(option: Option, obs: Observation) -> Card | None:
    current = obs.current
    if current is None or option.index is None:
        return None
    player_index = option.playerIndex
    if player_index is None:
        player_index = current.yourIndex
    if player_index < 0 or player_index >= len(current.players):
        return None
    hand = current.players[player_index].hand
    if hand is None or option.index < 0 or option.index >= len(hand):
        return None
    return hand[option.index]


def card_from_area_option(option: Option, obs: Observation) -> Card | None:
    current = obs.current
    if current is None:
        return None
    player_index = option.playerIndex
    if player_index is None:
        player_index = current.yourIndex
    if player_index < 0 or player_index >= len(current.players):
        return None
    player = current.players[player_index]
    if option.area == AreaType.HAND and player.hand is not None and option.index is not None:
        if 0 <= option.index < len(player.hand):
            return player.hand[option.index]
    if option.area == AreaType.DISCARD and option.index is not None:
        if 0 <= option.index < len(player.discard):
            return player.discard[option.index]
    if option.area == AreaType.ACTIVE and option.index is not None:
        if 0 <= option.index < len(player.active):
            pokemon = player.active[option.index]
            if pokemon is not None:
                return Card(id=pokemon.id, serial=-1, playerIndex=player_index)
    if option.area == AreaType.BENCH and option.index is not None:
        if 0 <= option.index < len(player.bench):
            pokemon = player.bench[option.index]
            return Card(id=pokemon.id, serial=-1, playerIndex=player_index)
    if option.area == AreaType.STADIUM and option.index is not None:
        if 0 <= option.index < len(current.stadium):
            return current.stadium[option.index]
    if option.area == AreaType.LOOKING and current.looking is not None and option.index is not None:
        if 0 <= option.index < len(current.looking):
            return current.looking[option.index]
    return None


def option_label(index: int, option: Option, obs: Observation) -> str:
    if option.type == OptionType.YES:
        return f"{index}: はい"
    if option.type == OptionType.NO:
        return f"{index}: いいえ"
    if option.type == OptionType.END:
        return f"{index}: 番を終わる"
    if option.type == OptionType.RETREAT:
        return f"{index}: にげる"

    action = OPTION_LABELS.get(option.type, enum_name(option.type))
    card = card_from_option(option, obs)
    card_text = card_name(card.id) if card is not None else ""
    target_text = target_label(option, obs)

    if option.type == OptionType.NUMBER:
        number = option.number if option.number is not None else "?"
        return f"{index}: {number}を選ぶ"

    if option.attackId is not None:
        attack = ATTACK_DATA.get(option.attackId)
        if attack is not None:
            damage = f" / {attack.damage}ダメージ" if attack.damage else ""
            return f"{index}: ワザ「{attack.name}」を使う{damage}"
        return f"{index}: ワザを使う"

    if option.type == OptionType.PLAY and card_text:
        return f"{index}: {card_text}を手札から使う"
    if option.type == OptionType.ATTACH and card_text:
        suffix = f" -> {target_text}" if target_text else ""
        return f"{index}: {card_text}をつける{suffix}"
    if option.type == OptionType.EVOLVE and card_text:
        suffix = f" -> {target_text}" if target_text else ""
        return f"{index}: {card_text}に進化する{suffix}"
    if option.type == OptionType.ABILITY and card_text:
        return f"{index}: {card_text}の特性を使う"
    if option.type == OptionType.DISCARD and card_text:
        return f"{index}: {card_text}をトラッシュする"
    if option.type in (OptionType.CARD, OptionType.TOOL_CARD, OptionType.ENERGY_CARD) and card_text:
        area = area_label(option.area)
        area_text = f"（{area}）" if area else ""
        return f"{index}: {card_text}{area_text}を選ぶ"
    if option.type == OptionType.ENERGY:
        count = f"{option.count}個分" if option.count is not None else ""
        return f"{index}: {energy_label(option)}{count}を選ぶ"

    details = []
    if card_text:
        details.append(card_text)
    if target_text:
        details.append(f"対象: {target_text}")
    if option.area is not None:
        details.append(area_label(option.area))
    if option.number is not None:
        details.append(f"{option.number}")
    suffix = " / ".join(detail for detail in details if detail)
    return f"{index}: {action}" + (f" - {suffix}" if suffix else "")


def area_label(area) -> str:
    if area is None:
        return ""
    return AREA_LABELS.get(area, enum_name(area))


def target_label(option: Option, obs: Observation) -> str:
    if option.inPlayArea is None or option.inPlayIndex is None:
        return ""
    current = obs.current
    if current is None:
        return ""
    player_index = option.playerIndex
    if player_index is None:
        player_index = current.yourIndex
    if player_index < 0 or player_index >= len(current.players):
        return ""
    player = current.players[player_index]
    if option.inPlayArea == AreaType.ACTIVE and 0 <= option.inPlayIndex < len(player.active):
        pokemon = player.active[option.inPlayIndex]
        if pokemon is not None:
            return f"バトル場（{card_name(pokemon.id)}）"
        return "バトル場"
    if option.inPlayArea == AreaType.BENCH and 0 <= option.inPlayIndex < len(player.bench):
        bench_no = option.inPlayIndex + 1
        return f"ベンチ{bench_no}（{card_name(player.bench[option.inPlayIndex].id)}）"
    return f"{area_label(option.inPlayArea)} {option.inPlayIndex}"


def energy_label(option: Option) -> str:
    if option.area is not None:
        return area_label(option.area)
    return "エネルギー"


def enum_name(value) -> str:
    if value is None:
        return ""
    return getattr(value, "name", str(value))


def pokemon_summary(pokemon: Pokemon | None):
    if pokemon is None:
        return {"hidden": True}
    return {
        "id": pokemon.id,
        "name": card_name(pokemon.id),
        "imageUrl": card_image_url(pokemon.id),
        "hp": pokemon.hp,
        "maxHp": pokemon.maxHp,
        "energies": [enum_name(energy) for energy in pokemon.energies],
        "energyCards": [card_summary(card) for card in pokemon.energyCards],
        "tools": [card_summary(card) for card in pokemon.tools],
        "preEvolution": [card_summary(card) for card in pokemon.preEvolution],
    }


def card_summary(card: Card | None):
    if card is None:
        return {"hidden": True}
    return {
        "id": card.id,
        "name": card_name(card.id),
        "serial": card.serial,
        "imageUrl": card_image_url(card.id),
    }


def card_image_path(card_id: int) -> Path | None:
    for ext in CARD_IMAGE_EXTENSIONS:
        path = CARD_IMAGE_DIR / f"{card_id}{ext}"
        if path.exists():
            return path
    return None


def card_image_url(card_id: int) -> str | None:
    if card_image_path(card_id) is None:
        return None
    return f"/card-image/{card_id}"


def state_summary(state: State | None):
    if state is None:
        return None
    players = []
    for player in state.players:
        players.append(
            {
                "active": [pokemon_summary(pokemon) for pokemon in player.active],
                "bench": [pokemon_summary(pokemon) for pokemon in player.bench],
                "benchMax": player.benchMax,
                "deckCount": player.deckCount,
                "discardCount": len(player.discard),
                "prizeCount": len(player.prize),
                "handCount": player.handCount,
                "hand": [card_summary(card) for card in player.hand] if player.hand is not None else None,
                "conditions": {
                    "poisoned": player.poisoned,
                    "burned": player.burned,
                    "asleep": player.asleep,
                    "paralyzed": player.paralyzed,
                    "confused": player.confused,
                },
            }
        )
    return {
        "turn": state.turn,
        "turnActionCount": state.turnActionCount,
        "yourIndex": state.yourIndex,
        "firstPlayer": state.firstPlayer,
        "supporterPlayed": state.supporterPlayed,
        "stadiumPlayed": state.stadiumPlayed,
        "energyAttached": state.energyAttached,
        "retreated": state.retreated,
        "result": state.result,
        "players": players,
        "stadium": [card_summary(card) for card in state.stadium],
    }


def log_label(log: Log) -> str:
    parts = [enum_name(log.type)]
    for field in (
        "playerIndex",
        "cardId",
        "cardIdActive",
        "cardIdBench",
        "cardIdBefore",
        "cardIdAfter",
        "cardIdTarget",
        "attackId",
        "value",
        "result",
        "reason",
        "head",
    ):
        value = getattr(log, field, None)
        if value is not None:
            if field.startswith("cardId"):
                parts.append(f"{field}={card_name(value)}")
            elif field == "attackId":
                attack = ATTACK_DATA.get(value)
                parts.append(f"attack={attack.name if attack else value}")
            else:
                parts.append(f"{field}={value}")
    return " | ".join(parts)


def observation_payload():
    if not BATTLE.started or BATTLE.obs_dict is None:
        return {"started": False, "decks": available_decks_payload()}
    obs = to_observation_class(BATTLE.obs_dict)
    select = obs.select
    return {
        "started": True,
        "step": BATTLE.step,
        "deck0": BATTLE.deck0_name,
        "deck1": BATTLE.deck1_name,
        "current": state_summary(obs.current),
        "select": None
        if select is None
        else {
            "type": enum_name(select.type),
            "context": enum_name(select.context),
            "contextLabel": CONTEXT_LABELS.get(select.context, enum_name(select.context)),
            "minCount": select.minCount,
            "maxCount": select.maxCount,
            "remainDamageCounter": select.remainDamageCounter,
            "remainEnergyCost": select.remainEnergyCost,
            "options": [
                {"index": index, "label": option_label(index, option, obs)}
                for index, option in enumerate(select.option)
            ],
        },
        "logs": [log_label(log) for log in obs.logs],
        "decks": available_decks_payload(),
    }


def available_decks_payload():
    payload = []
    for path in deck_files():
        validation = validate_deck_file(path)
        relative_path = str(path.relative_to(ROOT))
        payload.append(
            {
                "name": relative_path,
                "path": relative_path,
                "ok": validation.ok,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "cardCount": validation.card_count,
                "basicPokemonCount": validation.basic_pokemon_count,
                "aceSpecCount": validation.ace_spec_count,
            }
        )
    return payload


def safe_json(value):
    def default(obj):
        if is_dataclass(obj):
            return asdict(obj)
        if hasattr(obj, "name"):
            return obj.name
        raise TypeError(type(obj).__name__)

    return json.dumps(value, default=default).encode("utf-8")


HTML = r"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PTCG 手動プレイ</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f6f8;
      --panel: #ffffff;
      --line: #d6dae1;
      --text: #1b1f27;
      --muted: #5d6675;
      --accent: #0b6bcb;
      --danger: #b42318;
      --ok: #067647;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    header {
      padding: 14px 18px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }
    h1 { font-size: 20px; margin: 0; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 14px;
      padding: 14px;
    }
    section, aside {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
    }
    h2 { font-size: 16px; margin: 0 0 10px; }
    h3 { font-size: 14px; margin: 12px 0 6px; }
    label { display: block; font-size: 12px; color: var(--muted); margin: 8px 0 4px; }
    select, button {
      width: 100%;
      min-height: 36px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 6px 8px;
      font: inherit;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 600;
    }
    button.secondary { background: #fff; color: var(--text); border-color: var(--line); }
    button:disabled { opacity: .45; cursor: not-allowed; }
    .stack { display: grid; gap: 8px; }
    .meta {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
      font-size: 13px;
    }
    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      background: #fafbfc;
      white-space: nowrap;
    }
    .players {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .player {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fcfcfd;
    }
    .active-player { border-color: var(--accent); box-shadow: inset 0 0 0 1px var(--accent); }
    .zone {
      display: grid;
      gap: 6px;
      margin-top: 8px;
    }
    .mon, .card, .option {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px;
      background: #fff;
      overflow-wrap: anywhere;
    }
    .card, .mon {
      display: grid;
      grid-template-columns: 56px 1fr;
      gap: 8px;
      align-items: start;
    }
    .card-img {
      width: 56px;
      aspect-ratio: 63 / 88;
      object-fit: cover;
      border-radius: 4px;
      border: 1px solid var(--line);
      background: #eef1f5;
    }
    .card-img.placeholder {
      display: grid;
      place-items: center;
      color: var(--muted);
      font-size: 11px;
      text-align: center;
    }
    .mon strong, .card strong { display: block; font-size: 13px; }
    .small { font-size: 12px; color: var(--muted); }
    .options {
      max-height: 48vh;
      overflow: auto;
      display: grid;
      gap: 8px;
      padding-right: 4px;
    }
    .option {
      display: grid;
      grid-template-columns: 24px 1fr;
      align-items: start;
      gap: 8px;
    }
    .logs {
      max-height: 160px;
      overflow: auto;
      font-family: Consolas, monospace;
      font-size: 12px;
      background: #111827;
      color: #f9fafb;
      border-radius: 6px;
      padding: 8px;
      white-space: pre-wrap;
    }
    .error { color: var(--danger); font-weight: 600; }
    .ok { color: var(--ok); font-weight: 600; }
    @media (max-width: 920px) {
      main { grid-template-columns: 1fr; }
      .players { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <header>
    <h1>PTCG 手動プレイ</h1>
    <div class="small">両プレイヤーを人間が操作するローカル検証用GUI</div>
  </header>
  <main>
    <aside class="stack">
      <section>
        <h2>対戦開始</h2>
        <label>Player 0 デッキ</label>
        <select id="deck0"></select>
        <label>Player 1 デッキ</label>
        <select id="deck1"></select>
        <div style="height:8px"></div>
        <button id="start">開始 / リセット</button>
      </section>
      <section>
        <h2>選択</h2>
        <div id="selectMeta" class="small">対戦を開始してください。</div>
        <div id="options" class="options"></div>
        <div style="height:8px"></div>
        <button id="submit" disabled>選択を送信</button>
        <div style="height:8px"></div>
        <button id="empty" class="secondary" disabled>何も選ばない</button>
        <p id="message" class="small"></p>
      </section>
      <section>
        <h2>直近ログ</h2>
        <div id="logs" class="logs"></div>
      </section>
    </aside>
    <section>
      <h2>盤面</h2>
      <div id="status" class="meta"></div>
      <div style="height:12px"></div>
      <div id="players" class="players"></div>
    </section>
  </main>
  <script>
    let state = null;

    async function api(path, body) {
      const res = await fetch(path, {
        method: body ? 'POST' : 'GET',
        headers: body ? {'Content-Type': 'application/json'} : {},
        body: body ? JSON.stringify(body) : undefined
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || res.statusText);
      return data;
    }

    function esc(s) {
      return String(s ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[c]));
    }

    async function refresh() {
      state = await api('/api/state');
      renderDecks();
      renderState();
    }

    function renderDecks() {
      const decks = state.decks || [];
      for (const id of ['deck0', 'deck1']) {
        const el = document.getElementById(id);
        const current = el.value;
        el.innerHTML = decks.map(d => {
          const label = `${d.ok ? 'OK' : 'NG'} | ${d.name} | ${d.cardCount}枚 | たね${d.basicPokemonCount}`;
          return `<option value="${esc(d.name)}" ${d.ok ? '' : 'disabled'}>${esc(label)}</option>`;
        }).join('');
        if (current) el.value = current;
      }
      renderDeckValidation(decks);
    }

    function renderDeckValidation(decks) {
      let box = document.getElementById('deckValidation');
      if (!box) {
        box = document.createElement('div');
        box.id = 'deckValidation';
        box.className = 'small';
        document.querySelector('aside section').appendChild(box);
      }
      const rows = decks.map(d => {
        const problems = [...(d.errors || []), ...(d.warnings || [])];
        const msg = problems.length ? problems.join(' / ') : '問題なし';
        return `<div class="${d.ok ? 'ok' : 'error'}">${esc(d.name)}: ${esc(msg)}</div>`;
      }).join('');
      box.innerHTML = `<h3>デッキ検証</h3>${rows || '<div>デッキがありません</div>'}`;
    }

    function renderState() {
      document.getElementById('message').textContent = '';
      const status = document.getElementById('status');
      const players = document.getElementById('players');
      const options = document.getElementById('options');
      const logs = document.getElementById('logs');
      if (!state.started) {
        status.innerHTML = '<span class="pill">未開始</span>';
        players.innerHTML = '';
        options.innerHTML = '';
        logs.textContent = '';
        document.getElementById('submit').disabled = true;
        document.getElementById('empty').disabled = true;
        return;
      }
      const cur = state.current || {};
      const finished = cur.result !== -1 && cur.result !== undefined;
      status.innerHTML = [
        `step ${state.step}`,
        `turn ${cur.turn}`,
        `選択中 Player ${cur.yourIndex}`,
        `先攻 Player ${cur.firstPlayer}`,
        finished ? `結果 ${cur.result}` : '進行中'
      ].map(x => `<span class="pill">${esc(x)}</span>`).join('');
      players.innerHTML = (cur.players || []).map((p, i) => renderPlayer(p, i, cur.yourIndex)).join('');
      renderOptions(finished);
      logs.textContent = (state.logs || []).join('\n');
    }

    function renderPlayer(p, i, active) {
      const activeCls = i === active ? ' active-player' : '';
      const hand = p.hand
        ? p.hand.map(renderCard).join('')
        : `<div class="small">手札は現在の選択プレイヤーのみ表示</div>`;
      return `<div class="player${activeCls}">
        <h3>Player ${i}</h3>
        <div class="meta">
          <span class="pill">山札 ${p.deckCount}</span>
          <span class="pill">手札 ${p.handCount}</span>
          <span class="pill">サイド ${p.prizeCount}</span>
          <span class="pill">トラッシュ ${p.discardCount}</span>
        </div>
        <h3>バトル場</h3>
        <div class="zone">${(p.active || []).map(renderPokemon).join('') || '<div class="small">なし</div>'}</div>
        <h3>ベンチ</h3>
        <div class="zone">${renderBench(p)}</div>
        <h3>見えている手札</h3>
        <div class="zone">${hand}</div>
      </div>`;
    }

    function renderBench(p) {
      const cards = p.bench || [];
      const slots = [];
      for (let i = 0; i < 5; i++) {
        slots.push(renderPokemon(cards[i] || null, `ベンチ${i + 1}`));
      }
      return slots.join('');
    }

    function renderPokemon(mon, slotLabel) {
      const label = slotLabel ? `<div class="small">${esc(slotLabel)}</div>` : '';
      if (!mon) return `<div class="mon">${label}<strong>空き</strong></div>`;
      if (mon.hidden) return '<div class="mon"><strong>非公開</strong></div>';
      return `<div class="mon">
        ${renderImage(mon)}
        <div>
          ${label}
          <strong>${esc(mon.name)}</strong>
          <span class="small">HP ${esc(mon.hp)} / ${esc(mon.maxHp)} | エネルギー ${esc((mon.energies || []).join(', ') || 'なし')}</span>
        </div>
      </div>`;
    }

    function renderCard(c) {
      return `<div class="card">
        ${renderImage(c)}
        <div>
          <strong>${esc(c.name)}</strong>
        </div>
      </div>`;
    }

    function renderImage(c) {
      if (c && c.imageUrl) {
        return `<img class="card-img" src="${esc(c.imageUrl)}" alt="">`;
      }
      return `<div class="card-img placeholder">画像なし</div>`;
    }

    function renderOptions(finished) {
      const meta = document.getElementById('selectMeta');
      const options = document.getElementById('options');
      const submit = document.getElementById('submit');
      const empty = document.getElementById('empty');
      if (finished) {
        meta.innerHTML = `<span class="ok">対戦終了: winner/result ${esc(state.current.result)}</span>`;
        options.innerHTML = '';
        submit.disabled = true;
        empty.disabled = true;
        return;
      }
      if (!state.select) {
        meta.textContent = '選択肢なし';
        options.innerHTML = '';
        submit.disabled = true;
        empty.disabled = true;
        return;
      }
      const s = state.select;
      meta.textContent = `${s.contextLabel || '選択してください'} / ${s.minCount}から${s.maxCount}個選択`;
      options.innerHTML = s.options.map(o => `<label class="option">
        <input type="checkbox" value="${o.index}">
        <span>${esc(o.label)}</span>
      </label>`).join('');
      submit.disabled = false;
      empty.disabled = s.minCount !== 0;
    }

    async function startBattle() {
      const deck0 = document.getElementById('deck0').value;
      const deck1 = document.getElementById('deck1').value;
      state = await api('/api/start', {deck0, deck1});
      renderState();
    }

    async function submitSelection(indexes) {
      try {
        state = await api('/api/select', {indexes});
        renderState();
      } catch (err) {
        document.getElementById('message').innerHTML = `<span class="error">${esc(err.message)}</span>`;
      }
    }

    document.getElementById('start').addEventListener('click', startBattle);
    document.getElementById('submit').addEventListener('click', () => {
      const indexes = [...document.querySelectorAll('#options input:checked')].map(x => Number(x.value));
      submitSelection(indexes);
    });
    document.getElementById('empty').addEventListener('click', () => submitSelection([]));

    refresh().catch(err => {
      document.getElementById('message').innerHTML = `<span class="error">${esc(err.message)}</span>`;
    });
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/state":
            self.send_json(observation_payload())
            return
        if path.startswith("/card-image/"):
            self.send_card_image(path.removeprefix("/card-image/"))
            return
        self.send_error(404)

    def do_POST(self):
        try:
            path = urlparse(self.path).path
            body = self.read_json()
            if path == "/api/start":
                deck0 = deck_path_from_name(body["deck0"])
                deck1 = deck_path_from_name(body["deck1"])
                BATTLE.start(deck0, deck1)
                self.send_json(observation_payload())
                return
            if path == "/api/select":
                indexes = body.get("indexes", [])
                if not isinstance(indexes, list):
                    raise ValueError("indexes must be a list.")
                BATTLE.select([int(index) for index in indexes])
                self.send_json(observation_payload())
                return
            if path == "/api/finish":
                BATTLE.reset()
                self.send_json(observation_payload())
                return
            self.send_error(404)
        except Exception as exc:
            self.send_json({"error": str(exc)}, status=400)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, value, status=200):
        self.send_bytes(safe_json(value), "application/json; charset=utf-8", status=status)

    def send_bytes(self, payload: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def send_card_image(self, raw_card_id: str):
        try:
            card_id = int(raw_card_id)
        except ValueError:
            self.send_error(404)
            return
        path = card_image_path(card_id)
        if path is None:
            self.send_error(404)
            return
        content_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".webp": "image/webp",
        }
        content_type = content_types.get(path.suffix.lower(), "application/octet-stream")
        self.send_bytes(path.read_bytes(), content_type)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(ROOT)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Manual play GUI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    finally:
        BATTLE.reset()


if __name__ == "__main__":
    main()
