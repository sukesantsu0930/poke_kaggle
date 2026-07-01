import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "scripts"))

from action_abstraction import collapse_equivalent_options, energy_equivalence_key  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
