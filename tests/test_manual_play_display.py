import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import manual_play_server as gui  # noqa: E402


class ManualPlayDisplayTest(unittest.TestCase):
    def test_japanese_skill_row_is_not_used_as_attack_name(self):
        detail = gui.card_detail(140)  # キチキギスex

        self.assertEqual(detail["skills"][0]["name"], "さかてにとる")
        self.assertEqual(detail["attacks"][0]["name"], "クルーエルアロー")

    def test_japanese_skill_name_for_pokemon_with_attack(self):
        detail = gui.card_detail(190)  # ブリジュラスex

        self.assertEqual(detail["skills"][0]["name"], "ごうきんビルド")
        self.assertEqual(detail["attacks"][0]["name"], "メタルディフェンダー")


if __name__ == "__main__":
    unittest.main()
