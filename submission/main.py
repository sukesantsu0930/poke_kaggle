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

_CARD_DATA = None
_ATTACK_DATA = None

def read_deck_csv() -> list[int]:
    """Read deck.csv.
    
    Returns:
        list[int]: A list of card IDs in the deck.
    """
    file_path = "deck.csv"
    if not os.path.exists(file_path):
        file_path = "/kaggle_simulations/agent/" + file_path
    with open(file_path, "r") as file:
        csv = file.read().split("\n")
    deck = []
    for i in range(60):
        deck.append(int(csv[i]))
    return deck


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
    card = _card_data().get(card_id)
    if card is None:
        return 0
    score = card.hp
    if card.cardType == CardType.POKEMON:
        score += 100
        if card.basic:
            score += 30
        if card.ex:
            score += 20
        score += 10 * len(card.attacks)
    elif card.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY):
        score += 20
    return score


def _attack_score(option: Option) -> int:
    attack = _attack_data().get(option.attackId)
    if attack is None:
        return 0
    return attack.damage * 10 - len(attack.energies)


def _best_index(options: list[Option], indexes: list[int], reverse: bool = True) -> int:
    if not indexes:
        return 0
    key = lambda i: (_card_score(_option_card_id(options[i])), -i)
    return sorted(indexes, key=key, reverse=reverse)[0]


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
    return result[:select.maxCount]


def _choose_yes_no(obs: Observation) -> list[int]:
    select = obs.select
    yes = [i for i, option in enumerate(select.option) if option.type == OptionType.YES]
    no = [i for i, option in enumerate(select.option) if option.type == OptionType.NO]

    if select.context in (SelectContext.MULLIGAN, SelectContext.IS_FIRST):
        return _fill_selection(obs, no + yes)
    return _fill_selection(obs, yes + no)


def _choose_count(obs: Observation) -> list[int]:
    select = obs.select
    numbered = [
        (i, option.number if option.number is not None else -1)
        for i, option in enumerate(select.option)
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
    for option_type in (
        OptionType.ATTACH,
        OptionType.EVOLVE,
        OptionType.ABILITY,
        OptionType.PLAY,
    ):
        preferred.extend(by_type.get(option_type, []))

    attacks = by_type.get(OptionType.ATTACK, [])
    attacks.sort(key=lambda i: _attack_score(select.option[i]), reverse=True)
    preferred.extend(attacks)
    preferred.extend(by_type.get(OptionType.RETREAT, []))
    preferred.extend(by_type.get(OptionType.END, []))
    return _fill_selection(obs, preferred)


def _choose_cards(obs: Observation) -> list[int]:
    select = obs.select
    indexes = list(range(len(select.option)))

    discard_contexts = {
        SelectContext.DISCARD,
        SelectContext.DISCARD_CARD_OR_ATTACHED_CARD,
        SelectContext.DISCARD_ENERGY,
        SelectContext.DISCARD_ENERGY_CARD,
        SelectContext.DISCARD_TOOL_CARD,
    }
    reverse = select.context not in discard_contexts
    ranked = sorted(
        indexes,
        key=lambda i: (_card_score(_option_card_id(select.option[i])), -i),
        reverse=reverse,
    )
    return _fill_selection(obs, ranked)


def agent(obs_dict: dict) -> list[int]:
    """Implement Your Pokémon Trading Card Game Agent.

    Each element in the returned list must be >= 0 and < len(obs.select.option).
    The list length must be between obs.select.minCount and obs.select.maxCount (inclusive), with no duplicate elements.
    
    Returns:
        list[int]: A list of option index.
    """
    obs: Observation = to_observation_class(obs_dict)
    if obs.select == None:
        # In the initial selection, the obs.select is None, and it is necessary to return the deck.
        # The deck is a list of 60 card IDs.
        # The deck must comply with the Pokémon Trading Card Game rules.
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
