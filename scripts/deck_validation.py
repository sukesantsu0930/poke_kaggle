from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission"
if str(SUBMISSION) not in sys.path:
    sys.path.insert(0, str(SUBMISSION))

from cg.api import CardType, all_card_data  # noqa: E402


@dataclass
class DeckValidation:
    path: str
    ok: bool
    errors: list[str]
    warnings: list[str]
    card_count: int
    basic_pokemon_count: int
    ace_spec_count: int
    unique_names: int


_CARD_BY_ID = None


def card_by_id():
    global _CARD_BY_ID
    if _CARD_BY_ID is None:
        _CARD_BY_ID = {card.cardId: card for card in all_card_data()}
    return _CARD_BY_ID


def read_deck_file(path: Path) -> tuple[list[int], list[str]]:
    errors = []
    deck = []
    for line_no, raw in enumerate(path.read_text().splitlines(), start=1):
        value = raw.strip()
        if not value:
            continue
        try:
            deck.append(int(value))
        except ValueError:
            errors.append(f"{line_no}行目: 整数のカードIDではありません: {value!r}")
    return deck, errors


def validate_deck_file(path: Path) -> DeckValidation:
    cards = card_by_id()
    errors = []
    warnings = []
    deck, parse_errors = read_deck_file(path)
    errors.extend(parse_errors)

    if len(deck) != 60:
        errors.append(f"デッキは60枚ちょうど必要です。現在は{len(deck)}枚です。")

    unknown = sorted({card_id for card_id in deck if card_id not in cards})
    if unknown:
        errors.append(f"存在しないカードIDがあります: {', '.join(map(str, unknown[:20]))}")

    known_cards = [cards[card_id] for card_id in deck if card_id in cards]
    basic_pokemon = [
        card
        for card in known_cards
        if card.cardType == CardType.POKEMON and card.basic
    ]
    if not basic_pokemon:
        errors.append("たねポケモンが1枚もありません。")

    ace_specs = [card for card in known_cards if card.aceSpec]
    if len(ace_specs) > 1:
        names = ", ".join(sorted({card.name for card in ace_specs}))
        errors.append(f"ACE SPECは1枚までです。現在は{len(ace_specs)}枚あります: {names}")

    name_counts = Counter(card.name for card in known_cards)
    for name, count in sorted(name_counts.items()):
        sample = next(card for card in known_cards if card.name == name)
        if sample.cardType == CardType.BASIC_ENERGY:
            continue
        if count > 4:
            errors.append(f"同名カードは基本エネルギー以外4枚までです: {name} が {count}枚")

    if len(deck) == 60 and len(known_cards) == 60:
        pokemon_count = sum(1 for card in known_cards if card.cardType == CardType.POKEMON)
        energy_count = sum(
            1
            for card in known_cards
            if card.cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY)
        )
        trainer_count = 60 - pokemon_count - energy_count
        if pokemon_count == 0:
            warnings.append("ポケモンが0枚です。通常は対戦開始できません。")
        if energy_count == 0:
            warnings.append("エネルギーが0枚です。攻撃できない可能性があります。")
        if trainer_count == 0:
            warnings.append("トレーナーズが0枚です。かなり単純なデッキです。")

    return DeckValidation(
        path=str(path),
        ok=not errors,
        errors=errors,
        warnings=warnings,
        card_count=len(deck),
        basic_pokemon_count=len(basic_pokemon),
        ace_spec_count=len(ace_specs),
        unique_names=len(name_counts),
    )


def validate_all_decks(deck_dir: Path) -> list[DeckValidation]:
    return [validate_deck_file(path) for path in sorted(deck_dir.rglob("*.csv"))]
