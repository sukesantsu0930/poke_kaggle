import os

from cg.api import (
    CardType,
    Observation,
    Option,
    OptionType,
    SelectContext,
    SelectType,
    all_attack,
    all_card_data,
    to_observation_class,
)


CUBCHOO = 506
CORNERSTONE_OGERPON_EX = 117
ROCKET_ARTICUNO = 414
WATER_ENERGY = 3

IMPORTANT_CARD_IDS = {
    CUBCHOO: 2000,
    CORNERSTONE_OGERPON_EX: 1800,
    ROCKET_ARTICUNO: 1500,
    WATER_ENERGY: 900,
    1120: 850,  # クラッシュハンマー
    1081: 820,  # 改造ハンマー
    1182: 780,  # ボスの指令
    1227: 760,  # リーリエの決心
    1219: 740,  # ロケット団のラムダ
    1086: 700,  # なかよしポフィン
    1119: 690,  # エネルギー転送
    1097: 650,  # 夜のタンカ
    1123: 620,  # ポケモンいれかえ
    1264: 600,  # バトルコロシアム
    1256: 590,  # ロケット団の監視塔
}

_CARD_DATA = None
_ATTACK_DATA = None


def read_deck_csv() -> list[int]:
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        values = [line.strip() for line in file.read().splitlines() if line.strip()]
    return [int(value) for value in values[:60]]


def _card_data():
    global _CARD_DATA
    if _CARD_DATA is None:
        _CARD_DATA = {card.cardId: card for card in all_card_data()}
    return _CARD_DATA


def _attack_data():
    global _ATTACK_DATA
    if _ATTACK_DATA is None:
        _ATTACK_DATA = {attack.attackId: attack for attack in all_attack()}
    return _ATTACK_DATA


def _option_card_id(option: Option) -> int | None:
    return option.cardId


def _card_score(card_id: int | None) -> int:
    if card_id is None:
        return 0
    if card_id in IMPORTANT_CARD_IDS:
        return IMPORTANT_CARD_IDS[card_id]

    card = _card_data().get(card_id)
    if card is None:
        return 0

    score = 0
    if card.cardType == CardType.POKEMON:
        score += 500
        if card.basic:
            score += 100
        if card.ex:
            score += 120
        score += min(card.hp, 350)
    elif card.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        score += 300
    else:
        score += 200
    return score


def _attack_score(option: Option) -> int:
    attack = _attack_data().get(option.attackId)
    if attack is None:
        return 0
    return attack.damage * 10 - len(attack.energies) * 25


def _fill_selection(obs: Observation, preferred: list[int]) -> list[int]:
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


def _rank_by_card(obs: Observation, reverse: bool = True) -> list[int]:
    options = obs.select.option
    indexes = list(range(len(options)))
    return sorted(
        indexes,
        key=lambda i: (_card_score(_option_card_id(options[i])), -i),
        reverse=reverse,
    )


def _choose_yes_no(obs: Observation) -> list[int]:
    select = obs.select
    yes = [i for i, option in enumerate(select.option) if option.type == OptionType.YES]
    no = [i for i, option in enumerate(select.option) if option.type == OptionType.NO]

    if select.context in (SelectContext.MULLIGAN, SelectContext.IS_FIRST):
        return _fill_selection(obs, no + yes)
    return _fill_selection(obs, yes + no)


def _choose_count(obs: Observation) -> list[int]:
    numbered = [
        (i, option.number if option.number is not None else -1)
        for i, option in enumerate(obs.select.option)
        if option.type == OptionType.NUMBER
    ]
    numbered.sort(key=lambda item: item[1], reverse=True)
    return _fill_selection(obs, [i for i, _ in numbered])


def _choose_main(obs: Observation) -> list[int]:
    select = obs.select
    by_type = {}
    for i, option in enumerate(select.option):
        by_type.setdefault(option.type, []).append(i)

    preferred = []

    for option_type in (OptionType.ABILITY, OptionType.PLAY):
        ranked = sorted(
            by_type.get(option_type, []),
            key=lambda i: (_card_score(_option_card_id(select.option[i])), -i),
            reverse=True,
        )
        preferred.extend(ranked)

    preferred.extend(by_type.get(OptionType.ATTACH, []))
    preferred.extend(by_type.get(OptionType.EVOLVE, []))

    attacks = by_type.get(OptionType.ATTACK, [])
    attacks.sort(key=lambda i: _attack_score(select.option[i]), reverse=True)
    preferred.extend(attacks)

    preferred.extend(by_type.get(OptionType.RETREAT, []))
    preferred.extend(by_type.get(OptionType.END, []))
    return _fill_selection(obs, preferred)


def _choose_cards(obs: Observation) -> list[int]:
    discard_contexts = {
        SelectContext.DISCARD,
        SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
        SelectContext.DISCARD_ENERGY,
        SelectContext.DISCARD_ENERGY_CARD,
        SelectContext.DISCARD_TOOL_CARD,
    }
    reverse = obs.select.context not in discard_contexts
    return _fill_selection(obs, _rank_by_card(obs, reverse=reverse))


def agent(obs_dict: dict) -> list[int]:
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    if obs.select.type == SelectType.MAIN:
        return _choose_main(obs)
    if obs.select.type == SelectType.YES_NO:
        return _choose_yes_no(obs)
    if obs.select.type == SelectType.COUNT:
        return _choose_count(obs)
    if obs.select.type == SelectType.ATTACK:
        attacks = list(range(len(obs.select.option)))
        attacks.sort(key=lambda i: _attack_score(obs.select.option[i]), reverse=True)
        return _fill_selection(obs, attacks)

    return _choose_cards(obs)
