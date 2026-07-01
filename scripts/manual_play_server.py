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
    EnergyType,
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
from action_abstraction import collapse_equivalent_options  # noqa: E402
from deck_validation import validate_deck_file  # noqa: E402


def clean_csv_value(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or text.lower() == "n/a":
        return ""
    return text


CARD_DATA = {card.cardId: card for card in all_card_data()}
ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}
JP_CARD_NAMES = {}
JP_ATTACK_ROWS_BY_CARD = {}
JP_SKILL_ROWS_BY_CARD = {}
JP_CARD_DATA = ROOT / "JP_Card_Data.csv"
if JP_CARD_DATA.exists():
    with JP_CARD_DATA.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            card_id = int(row["カード ID"])
            JP_CARD_NAMES.setdefault(card_id, row["カード名"])
            move_name = clean_csv_value(row.get("ワザ名"))
            if move_name.startswith("[特性]"):
                JP_SKILL_ROWS_BY_CARD.setdefault(card_id, []).append(row)
            elif move_name:
                JP_ATTACK_ROWS_BY_CARD.setdefault(card_id, []).append(row)
JP_ATTACK_DATA = {}
JP_SKILL_DATA = {}
for card_id, rows in JP_ATTACK_ROWS_BY_CARD.items():
    card = CARD_DATA.get(card_id)
    if card is None:
        continue
    for attack_id, row in zip(card.attacks, rows):
        JP_ATTACK_DATA[attack_id] = row
for card_id, rows in JP_SKILL_ROWS_BY_CARD.items():
    card = CARD_DATA.get(card_id)
    if card is None:
        continue
    for skill, row in zip(card.skills, rows):
        JP_SKILL_DATA[(card_id, skill.name)] = row
CARD_IMAGE_DIR = ROOT / "card_images" / "jp"
CARD_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")

ENERGY_TYPE_LABELS = {
    EnergyType.GRASS: "草",
    EnergyType.FIRE: "炎",
    EnergyType.WATER: "水",
    EnergyType.LIGHTNING: "雷",
    EnergyType.PSYCHIC: "超",
    EnergyType.FIGHTING: "闘",
    EnergyType.DARKNESS: "悪",
    EnergyType.METAL: "鋼",
    EnergyType.COLORLESS: "無色",
    EnergyType.DRAGON: "ドラゴン",
    EnergyType.RAINBOW: "全タイプ",
    EnergyType.TEAM_ROCKET: "ロケット団",
}

CARD_TYPE_LABELS = {
    CardType.POKEMON: "ポケモン",
    CardType.ITEM: "グッズ",
    CardType.TOOL: "ポケモンのどうぐ",
    CardType.SUPPORTER: "サポート",
    CardType.STADIUM: "スタジアム",
    CardType.BASIC_ENERGY: "基本エネルギー",
    CardType.SPECIAL_ENERGY: "特殊エネルギー",
}

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
    if generic_energy:
        energy_name = energy_card_name(card_id)
        if energy_name:
            return energy_name
    jp_name = JP_CARD_NAMES.get(card_id)
    if jp_name is not None:
        return f"{jp_name} (ID {card_id})"
    card = CARD_DATA.get(card_id)
    if card is None:
        return f"#{card_id}"
    return f"{card.name} (ID {card_id})"


def energy_card_name(card_id: int | None) -> str:
    if card_id is None:
        return ""
    card = CARD_DATA.get(card_id)
    if card is None:
        return ""
    if card.cardType == CardType.BASIC_ENERGY:
        energy_type = ENERGY_TYPE_LABELS.get(card.energyType, enum_name(card.energyType))
        return f"基本{energy_type}エネルギー"
    if card.cardType == CardType.SPECIAL_ENERGY:
        jp_name = JP_CARD_NAMES.get(card_id)
        if jp_name is not None:
            return jp_name
        return card.name
    return ""


def energy_type_label(energy_type) -> str:
    return ENERGY_TYPE_LABELS.get(energy_type, enum_name(energy_type))


def attack_summary(attack_id: int):
    attack = ATTACK_DATA.get(attack_id)
    jp_attack = JP_ATTACK_DATA.get(attack_id)
    if attack is None:
        return {"name": f"ワザ {attack_id}", "cost": "", "damage": "", "text": ""}
    if jp_attack is not None:
        return {
            "name": clean_csv_value(jp_attack.get("ワザ名")) or attack.name,
            "cost": clean_csv_value(jp_attack.get("コスト"))
            or " ".join(energy_type_label(energy) for energy in attack.energies),
            "damage": clean_csv_value(jp_attack.get("ダメージ")) or attack.damage,
            "text": clean_csv_value(jp_attack.get("効果の説明")),
        }
    return {
        "name": attack.name,
        "cost": " ".join(energy_type_label(energy) for energy in attack.energies),
        "damage": attack.damage,
        "text": attack.text,
    }


def skill_summary(card_id: int, skill):
    jp_skill = JP_SKILL_DATA.get((card_id, skill.name))
    if jp_skill is None:
        return {"name": skill.name.strip(), "text": skill.text}
    name = clean_csv_value(jp_skill.get("ワザ名")).removeprefix("[特性]").strip()
    return {
        "name": name or skill.name.strip(),
        "text": clean_csv_value(jp_skill.get("効果の説明")) or skill.text,
    }


def card_detail(card_id: int | None):
    card = CARD_DATA.get(card_id)
    if card is None:
        return {
            "cardType": "",
            "energyType": "",
            "retreatCost": "",
            "weakness": "",
            "resistance": "",
            "traits": [],
            "attacks": [],
            "skills": [],
        }
    traits = []
    if card.basic:
        traits.append("たね")
    if card.stage1:
        traits.append("1進化")
    if card.stage2:
        traits.append("2進化")
    if card.ex:
        traits.append("ex")
    if card.megaEx:
        traits.append("Mega ex")
    if card.tera:
        traits.append("テラスタル")
    return {
        "cardType": CARD_TYPE_LABELS.get(card.cardType, enum_name(card.cardType)),
        "energyType": energy_type_label(card.energyType),
        "retreatCost": card.retreatCost,
        "weakness": energy_type_label(card.weakness) if card.weakness is not None else "なし",
        "resistance": energy_type_label(card.resistance) if card.resistance is not None else "なし",
        "traits": traits,
        "attacks": [attack_summary(attack_id) for attack_id in card.attacks],
        "skills": [skill_summary(card_id, skill) for skill in card.skills],
    }


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
    if option.area == AreaType.DECK and obs.select is not None and obs.select.deck is not None and option.index is not None:
        if 0 <= option.index < len(obs.select.deck):
            card = obs.select.deck[option.index]
            if card is not None:
                return card
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
                attached = attached_card_from_pokemon(option, pokemon)
                if attached is not None:
                    return attached
                return Card(id=pokemon.id, serial=-1, playerIndex=player_index)
    if option.area == AreaType.BENCH and option.index is not None:
        if 0 <= option.index < len(player.bench):
            pokemon = player.bench[option.index]
            attached = attached_card_from_pokemon(option, pokemon)
            if attached is not None:
                return attached
            return Card(id=pokemon.id, serial=-1, playerIndex=player_index)
    if option.area == AreaType.STADIUM and option.index is not None:
        if 0 <= option.index < len(current.stadium):
            return current.stadium[option.index]
    if option.area == AreaType.LOOKING and current.looking is not None and option.index is not None:
        if 0 <= option.index < len(current.looking):
            return current.looking[option.index]
    return None


def attached_card_from_pokemon(option: Option, pokemon: Pokemon) -> Card | None:
    if option.type == OptionType.ENERGY_CARD and option.energyIndex is not None:
        if 0 <= option.energyIndex < len(pokemon.energyCards):
            return pokemon.energyCards[option.energyIndex]
    if option.type == OptionType.TOOL_CARD and option.toolIndex is not None:
        if 0 <= option.toolIndex < len(pokemon.tools):
            return pokemon.tools[option.toolIndex]
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
        if obs.select is not None and obs.select.context == SelectContext.DRAW_COUNT:
            return f"{index}: {number}枚引く"
        return f"{index}: {number}を選ぶ"

    if option.attackId is not None:
        attack = ATTACK_DATA.get(option.attackId)
        attack_text = attack_summary(option.attackId)
        if attack is not None:
            damage = f" / {attack_text['damage']}ダメージ" if attack_text["damage"] else ""
            return f"{index}: ワザ「{attack_text['name']}」を使う{damage}"
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
    if option.type == OptionType.ENERGY_CARD and card_text:
        location = target_label(option, obs) or area_label(option.area)
        energy_no = f"E{option.energyIndex + 1}: " if option.energyIndex is not None else ""
        location_text = f"（{location}）" if location else ""
        return f"{index}: {energy_no}{card_text}{location_text}を選ぶ"
    if option.type in (OptionType.CARD, OptionType.TOOL_CARD) and card_text:
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
    area = option.inPlayArea
    index = option.inPlayIndex
    if area is None and option.type in (OptionType.ENERGY_CARD, OptionType.TOOL_CARD, OptionType.ENERGY):
        area = option.area
        index = option.index
    if area is None or index is None:
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
    if area == AreaType.ACTIVE and 0 <= index < len(player.active):
        pokemon = player.active[index]
        if pokemon is not None:
            return f"バトル場（{card_name(pokemon.id)}）"
        return "バトル場"
    if area == AreaType.BENCH and 0 <= index < len(player.bench):
        bench_no = index + 1
        return f"ベンチ{bench_no}（{card_name(player.bench[index].id)}）"
    return f"{area_label(area)} {index}"


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
    detail = card_detail(pokemon.id)
    return {
        "id": pokemon.id,
        "name": card_name(pokemon.id),
        "imageUrl": card_image_url(pokemon.id),
        "hp": pokemon.hp,
        "maxHp": pokemon.maxHp,
        "cardType": detail["cardType"],
        "energyType": detail["energyType"],
        "retreatCost": detail["retreatCost"],
        "weakness": detail["weakness"],
        "resistance": detail["resistance"],
        "traits": detail["traits"],
        "attacks": detail["attacks"],
        "skills": detail["skills"],
        "energies": [energy_type_label(energy) for energy in pokemon.energies],
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
        "looking": visible_card_summary(state.looking, source_label="見ているカード") if state.looking is not None else [],
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
                attack = attack_summary(value)
                parts.append(f"attack={attack['name'] if attack else value}")
            else:
                parts.append(f"{field}={value}")
    return " | ".join(parts)


def display_options(select, obs: Observation) -> list[dict]:
    choices = collapse_equivalent_options(
        select.option,
        lambda option: card_from_option(option, obs),
        CARD_DATA,
        max_count=select.maxCount,
    )
    return [
        {
            "index": choice.source_index,
            "label": option_label(choice.display_index, choice.option, obs),
            "imageUrl": card_image_url(card.id) if (card := card_from_option(choice.option, obs)) is not None else None,
        }
        for choice in choices
    ]


def visible_card_summary(cards, selectable_indexes=None, source_label="見えているカード") -> list[dict]:
    if cards is None:
        return []
    if selectable_indexes is None:
        selectable_indexes = set()
    selectable_indexes = {
        index for index in selectable_indexes if index is not None
    }
    grouped = {}
    order = []
    for index, card in enumerate(cards):
        if card is None:
            key = ("hidden", index)
            name = "非公開"
            card_id = None
            image_url = None
        else:
            key = card.id
            name = card_name(card.id)
            card_id = card.id
            image_url = card_image_url(card.id)
        if key not in grouped:
            grouped[key] = {
                "id": card_id,
                "name": name,
                "count": 0,
                "selectableCount": 0,
                "imageUrl": image_url,
                "source": source_label,
            }
            order.append(key)
        grouped[key]["count"] += 1
        if index in selectable_indexes:
            grouped[key]["selectableCount"] += 1
    return sorted((grouped[key] for key in order), key=lambda item: (-item["selectableCount"], item["name"]))


def visible_deck_summary(select) -> list[dict]:
    if select.deck is None:
        return []
    selectable_indexes = {
        option.index for option in select.option if option.area == AreaType.DECK and option.index is not None
    }
    return visible_card_summary(select.deck, selectable_indexes=selectable_indexes, source_label="山札")


def context_label(select) -> str:
    label = CONTEXT_LABELS.get(select.context, enum_name(select.context))
    if select.context == SelectContext.DRAW_COUNT:
        return "マリガン追加ドローなど、引く枚数を選ぶ"
    return label


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
            "contextLabel": context_label(select),
            "minCount": select.minCount,
            "maxCount": select.maxCount,
            "remainDamageCounter": select.remainDamageCounter,
            "remainEnergyCost": select.remainEnergyCost,
            "options": display_options(select, obs),
            "visibleDeck": visible_deck_summary(select),
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
      grid-template-columns: minmax(340px, 440px) 1fr;
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
      min-height: 40px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #fff;
      color: var(--text);
      padding: 8px 10px;
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
    .active-mon {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      overflow-wrap: anywhere;
    }
    .active-head {
      display: grid;
      grid-template-columns: 96px 1fr;
      gap: 10px;
      align-items: start;
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
    .active-mon .card-img {
      width: 96px;
    }
    .card-img.placeholder {
      display: grid;
      place-items: center;
      color: var(--muted);
      font-size: 11px;
      text-align: center;
    }
    .mon strong, .card strong { display: block; font-size: 13px; }
    .attached {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 6px;
    }
    .tag {
      border: 1px solid var(--line);
      border-radius: 4px;
      padding: 3px 6px;
      background: #f6f8fa;
      font-size: 11px;
    }
    .energy-tag {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border-color: #7aa7d9;
      background: #eef6ff;
      color: #143a5f;
      font-weight: 600;
    }
    .energy-index {
      min-width: 20px;
      border-radius: 999px;
      padding: 1px 5px;
      background: #0b6bcb;
      color: #fff;
      text-align: center;
      font-size: 10px;
    }
    .details {
      margin-top: 6px;
      display: grid;
      gap: 6px;
      font-size: 12px;
    }
    .attack {
      border-top: 1px solid var(--line);
      padding-top: 6px;
      white-space: pre-wrap;
    }
    .info-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 4px 8px;
      margin-top: 4px;
      font-size: 12px;
    }
    .small { font-size: 12px; color: var(--muted); }
    .options {
      max-height: 58vh;
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
    .deck-list {
      max-height: 280px;
      overflow: auto;
      display: grid;
      gap: 6px;
    }
    .deck-row {
      display: grid;
      grid-template-columns: 40px 1fr auto;
      gap: 8px;
      align-items: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 6px;
      background: #fff;
      font-size: 12px;
    }
    .deck-row .card-img {
      width: 40px;
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
        <h2>見えているカード</h2>
        <div id="visibleCards" class="deck-list small">山札や山上など、見えているカードがあるときに表示します。</div>
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
      <section>
        <h3>スタジアム</h3>
        <div id="stadium" class="zone"></div>
      </section>
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
      const stadium = document.getElementById('stadium');
      const options = document.getElementById('options');
      const logs = document.getElementById('logs');
      const visibleCards = document.getElementById('visibleCards');
      if (!state.started) {
        status.innerHTML = '<span class="pill">未開始</span>';
        stadium.innerHTML = '<div class="small">なし</div>';
        players.innerHTML = '';
        options.innerHTML = '';
        visibleCards.textContent = '山札や山上など、見えているカードがあるときに表示します。';
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
      stadium.innerHTML = renderStadium(cur.stadium || []);
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
        <div class="zone">${(p.active || []).map(renderActivePokemon).join('') || '<div class="small">なし</div>'}</div>
        <h3>ベンチ</h3>
        <div class="zone">${renderBench(p)}</div>
        <h3>見えている手札</h3>
        <div class="zone">${hand}</div>
      </div>`;
    }

    function renderStadium(cards) {
      if (!cards.length) return '<div class="small">なし</div>';
      return cards.map(c => `<div class="card">
        ${renderImage(c)}
        <div>
          <div class="small">場に出ているスタジアム</div>
          <strong>${esc(c.name)}</strong>
        </div>
      </div>`).join('');
    }

    function renderBench(p) {
      const cards = p.bench || [];
      const slots = [];
      for (let i = 0; i < 5; i++) {
        slots.push(renderPokemon(cards[i] || null, `ベンチ${i + 1}`));
      }
      return slots.join('');
    }

    function renderActivePokemon(mon) {
      if (!mon) return '<div class="active-mon"><strong>空き</strong></div>';
      if (mon.hidden) return '<div class="active-mon"><strong>非公開</strong></div>';
      return `<div class="active-mon">
        <div class="active-head">
          ${renderImage(mon)}
          <div>
            <div class="small">バトル場</div>
            <strong>${esc(mon.name)}</strong>
            <div class="info-grid">
              <span>種類: ${esc(mon.cardType)}</span>
              <span>タイプ: ${esc(mon.energyType)}</span>
              <span>HP: ${esc(mon.hp)} / ${esc(mon.maxHp)}</span>
              <span>にげる: ${esc(mon.retreatCost)}</span>
              <span>弱点: ${esc(mon.weakness)}</span>
              <span>抵抗: ${esc(mon.resistance)}</span>
              <span>特徴: ${esc((mon.traits || []).join(', ') || 'なし')}</span>
            </div>
            ${renderAttachedEnergies(mon)}
          </div>
        </div>
        ${renderActiveDetails(mon)}
      </div>`;
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
          <span class="small">HP ${esc(mon.hp)} / ${esc(mon.maxHp)}</span>
          ${renderAttachedEnergies(mon)}
        </div>
      </div>`;
    }

    function renderAttachedEnergies(mon) {
      const cards = mon.energyCards || [];
      if (!cards.length) return '<div class="small">付いているエネルギー: なし</div>';
      return `<div class="small">付いているエネルギー</div>
        <div class="attached">${cards.map((c, i) => `<span class="tag energy-tag">
          <span class="energy-index">E${i + 1}</span>
          <span>${esc(c.name)}</span>
        </span>`).join('')}</div>`;
    }

    function renderActiveDetails(mon) {
      const skills = (mon.skills || []).map(skill => `<div class="attack">
        <strong>特性: ${esc(skill.name)}</strong>
        <div>${esc(skill.text)}</div>
      </div>`).join('');
      const attacks = (mon.attacks || []).map(attack => `<div class="attack">
        <strong>ワザ: ${esc(attack.name)}</strong>
        <div>必要エネルギー: ${esc(attack.cost || 'なし')} / ダメージ: ${esc(attack.damage || '-')}</div>
        <div>${esc(attack.text || '')}</div>
      </div>`).join('');
      return `<div class="details">${skills || '<div class="small">特性なし</div>'}${attacks || '<div class="small">ワザなし</div>'}</div>`;
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
      const cur = state.current || {};
      if (finished) {
        meta.innerHTML = `<span class="ok">対戦終了: winner/result ${esc(state.current.result)}</span>`;
        options.innerHTML = '';
        renderVisibleCards([]);
        submit.disabled = true;
        empty.disabled = true;
        return;
      }
      if (!state.select) {
        meta.textContent = '選択肢なし';
        options.innerHTML = '';
        renderVisibleCards(cur.looking || []);
        submit.disabled = true;
        empty.disabled = true;
        return;
      }
      const s = state.select;
      meta.textContent = `${s.contextLabel || '選択してください'} / ${s.minCount}から${s.maxCount}個選択`;
      options.innerHTML = s.options.map(o => `<label class="option">
        <input type="checkbox" value="${o.index}">
        <span>${renderOptionImage(o)}${esc(o.label)}</span>
      </label>`).join('');
      renderVisibleCards([...(s.visibleDeck || []), ...(cur.looking || [])]);
      submit.disabled = false;
      empty.disabled = s.minCount !== 0;
    }

    function renderOptionImage(option) {
      if (!option.imageUrl) return '';
      return `<img class="card-img" src="${esc(option.imageUrl)}" alt="" style="width:40px;float:left;margin:0 8px 4px 0">`;
    }

    function renderVisibleCards(cards) {
      const box = document.getElementById('visibleCards');
      if (!cards.length) {
        box.textContent = '山札や山上など、見えているカードがあるときに表示します。';
        return;
      }
      box.innerHTML = cards.map(card => `<div class="deck-row">
        ${renderImage(card)}
        <div>
          <strong>${esc(card.name)}</strong>
          <div class="small">${esc(card.source || '見えているカード')} / ${card.selectableCount ? `選択可 ${esc(card.selectableCount)}枚` : '今回は選択不可'}</div>
        </div>
        <strong>${esc(card.count)}枚</strong>
      </div>`).join('');
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
