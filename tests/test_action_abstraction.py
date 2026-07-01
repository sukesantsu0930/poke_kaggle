import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "scripts"))

from action_abstraction import card_name_equivalence_key, collapse_equivalent_options, energy_equivalence_key  # noqa: E402
from cg.api import AreaType, Card, CardType, EnergyType, Option, OptionType, all_card_data  # noqa: E402


CARD_DATA = {card.cardId: card for card in all_card_data()}


class ActionAbstractionTest(unittest.TestCase):
    def test_basic_energy_same_target_collapses(self):
        options = [
            Option(type=OptionType.ATTACH, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
            Option(type=OptionType.ATTACH, index=1, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
            Option(type=OptionType.END),
        ]
        cards = {
            0: Card(id=3, serial=101, playerIndex=0),
            1: Card(id=3, serial=102, playerIndex=0),
        }

        choices = collapse_equivalent_options(options, lambda option: cards.get(option.index), CARD_DATA)

        self.assertEqual([choice.source_index for choice in choices], [0, 2])

    def test_basic_energy_different_target_does_not_collapse(self):
        options = [
            Option(type=OptionType.ATTACH, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
            Option(type=OptionType.ATTACH, index=1, inPlayArea=AreaType.BENCH, inPlayIndex=0),
        ]
        cards = {
            0: Card(id=3, serial=101, playerIndex=0),
            1: Card(id=3, serial=102, playerIndex=0),
        }

        choices = collapse_equivalent_options(options, lambda option: cards.get(option.index), CARD_DATA)

        self.assertEqual([choice.source_index for choice in choices], [0, 1])

    def test_basic_energy_different_type_does_not_collapse(self):
        options = [
            Option(type=OptionType.ATTACH, index=0, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
            Option(type=OptionType.ATTACH, index=1, inPlayArea=AreaType.ACTIVE, inPlayIndex=0),
        ]
        cards = {
            0: Card(id=1, serial=101, playerIndex=0),
            1: Card(id=3, serial=102, playerIndex=0),
        }

        choices = collapse_equivalent_options(options, lambda option: cards.get(option.index), CARD_DATA)

        self.assertEqual([choice.source_index for choice in choices], [0, 1])

    def test_special_energy_uses_card_id_as_equivalence_key(self):
        self.assertEqual(energy_equivalence_key(3, CARD_DATA), ("basic", EnergyType.WATER))
        self.assertEqual(energy_equivalence_key(18, CARD_DATA), ("special", 18))
        self.assertEqual(CARD_DATA[18].cardType, CardType.SPECIAL_ENERGY)

    def test_same_name_play_from_hand_collapses_for_single_selection(self):
        options = [
            Option(type=OptionType.PLAY, index=0),
            Option(type=OptionType.PLAY, index=1),
            Option(type=OptionType.END),
        ]
        cards = {
            0: Card(id=722, serial=201, playerIndex=0),
            1: Card(id=722, serial=202, playerIndex=0),
        }

        choices = collapse_equivalent_options(
            options,
            lambda option: cards.get(option.index),
            CARD_DATA,
            max_count=1,
        )

        self.assertEqual([choice.source_index for choice in choices], [0, 2])

    def test_same_name_cards_do_not_collapse_for_multi_selection(self):
        options = [
            Option(type=OptionType.PLAY, index=0),
            Option(type=OptionType.PLAY, index=1),
        ]
        cards = {
            0: Card(id=722, serial=201, playerIndex=0),
            1: Card(id=722, serial=202, playerIndex=0),
        }

        choices = collapse_equivalent_options(
            options,
            lambda option: cards.get(option.index),
            CARD_DATA,
            max_count=2,
        )

        self.assertEqual([choice.source_index for choice in choices], [0, 1])

    def test_same_name_deck_cards_collapse_for_single_selection(self):
        options = [
            Option(type=OptionType.CARD, area=AreaType.DECK, index=7),
            Option(type=OptionType.CARD, area=AreaType.DECK, index=29),
            Option(type=OptionType.CARD, area=AreaType.DECK, index=37),
        ]
        cards = {
            7: Card(id=722, serial=301, playerIndex=0),
            29: Card(id=722, serial=302, playerIndex=0),
            37: Card(id=722, serial=303, playerIndex=0),
        }

        choices = collapse_equivalent_options(
            options,
            lambda option: cards.get(option.index),
            CARD_DATA,
            max_count=1,
        )

        self.assertEqual([choice.source_index for choice in choices], [0])

    def test_card_name_key_ignores_serial(self):
        self.assertEqual(card_name_equivalence_key(722, CARD_DATA), ("name", CARD_DATA[722].name))


if __name__ == "__main__":
    unittest.main()
