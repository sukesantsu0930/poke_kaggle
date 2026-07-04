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


DREEPY = 119
DRAKLOAK = 120
DRAGAPULT_EX = 121
PHANTOM_DIVE = 154
FIRE_ENERGY = 2
PSYCHIC_ENERGY = 5

IMPORTANT_CARD_IDS = {
    DRAGAPULT_EX: 3000,
    DRAKLOAK: 2400,
    DREEPY: 2200,
    1079: 1800,  # Rare Candy
    1198: 1700,  # Akamatsu
    FIRE_ENERGY: 1600,
    PSYCHIC_ENERGY: 1600,
    1086: 1500,  # Buddy-Buddy Poffin
    1121: 1450,  # Ultra Ball
    1227: 1300,  # Lillie's Determination
    1152: 1200,  # PokePad
    1097: 1150,  # Night Stretcher
    1182: 1050,  # Boss's Orders
    235: 900,  # Budew
    140: 850,  # Fezandipiti ex
    184: 820,  # Latias ex
    1071: 780,  # Meowth ex
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
            score += 80
        if card.ex:
            score += 120
        score += min(card.hp, 350)
    elif card.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        score += 300
    else:
        score += 200
    return score


def _attack_score(option: Option) -> int:
    if option.attackId == PHANTOM_DIVE:
        return 100000
    attack = _attack_data().get(option.attackId)
    if attack is None:
        return 0
    return attack.damage * 10 - len(attack.energies) * 25


def _target_score(option: Option) -> int:
    if option.inPlayArea is None:
        return 0
    if option.inPlayIndex is None:
        return 0
    # Without full target card data on every option, prefer active/early targets.
    return 100 - option.inPlayIndex


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
        key=lambda i: (_card_score(_option_card_id(options[i])), _target_score(options[i]), -i),
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

    for option_type in (OptionType.EVOLVE, OptionType.ATTACH):
        ranked = sorted(
            by_type.get(option_type, []),
            key=lambda i: (_card_score(_option_card_id(select.option[i])), _target_score(select.option[i]), -i),
            reverse=True,
        )
        preferred.extend(ranked)

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

