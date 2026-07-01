from dataclasses import dataclass
from typing import Callable, Iterable

from cg.api import Card, CardData, CardType, Option, OptionType


@dataclass(frozen=True)
class ActionChoice:
    source_index: int
    display_index: int
    option: Option
    equivalence_key: tuple | None


def collapse_equivalent_options(
    options: Iterable[Option],
    card_from_option: Callable[[Option], Card | None],
    card_data_by_id: dict[int, CardData],
) -> list[ActionChoice]:
    choices = []
    seen = set()
    for source_index, option in enumerate(options):
        key = option_equivalence_key(option, card_from_option(option), card_data_by_id)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        choices.append(
            ActionChoice(
                source_index=source_index,
                display_index=len(choices),
                option=option,
                equivalence_key=key,
            )
        )
    return choices


def option_equivalence_key(
    option: Option,
    card: Card | None,
    card_data_by_id: dict[int, CardData],
) -> tuple | None:
    if option.type != OptionType.ATTACH or card is None:
        return None

    energy_key = energy_equivalence_key(card.id, card_data_by_id)
    if energy_key is None:
        return None

    return (
        "attach-energy",
        energy_key,
        option.playerIndex,
        option.inPlayArea,
        option.inPlayIndex,
    )


def energy_equivalence_key(card_id: int | None, card_data_by_id: dict[int, CardData]) -> tuple | None:
    if card_id is None:
        return None
    card_data = card_data_by_id.get(card_id)
    if card_data is None:
        return None
    if card_data.cardType == CardType.BASIC_ENERGY:
        return ("basic", card_data.energyType)
    if card_data.cardType == CardType.SPECIAL_ENERGY:
        return ("special", card_id)
    return None


def is_energy_card(card_id: int | None, card_data_by_id: dict[int, CardData]) -> bool:
    return energy_equivalence_key(card_id, card_data_by_id) is not None
