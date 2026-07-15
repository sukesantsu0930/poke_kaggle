# -*- coding: utf-8 -*-
"""R-26/R-28（_sequencing_override）の回帰テスト — 合成盤面で順序割り込みを検証する。

R-26: 手札リフレッシュ札（アンフェアスタンプ/リーリエ）の前に未使用のエネ手張りを済ませる。
R-28: ドロー札の前に山札圧縮アイテムを先行させる。相手が LO アーキタイプなら停止。
出所: リプレイ 85690212（2026-07-13。手張り権を残したままアンフェアスタンプ）。
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg.api import AreaType, OptionType, SelectContext  # noqa: E402

from policy_base import BasePolicy  # noqa: E402

STAMP, POFFIN, F_ENERGY = 1080, 1086, 6


class _DummyPolicy(BasePolicy):
    DECK_NAME = "test_sequencing"
    GO_FIRST = True
    TAKE_MULLIGAN = True
    ATTACKER_IDS = frozenset()
    ENERGY_IDS = frozenset({F_ENERGY})
    LINE_PROTECT_IDS = frozenset()

    def judge_subgoal(self, obs):
        return False

    def score_setup(self, obs, opt):
        return 0, "test"

    def score_combat(self, obs, opt):
        return 0, "test"


def _make_obs(energy_attached):
    hand = [NS(id=STAMP), NS(id=POFFIN), NS(id=F_ENERGY)]
    opts = [
        NS(type=OptionType.PLAY, index=0, playerIndex=None, area=AreaType.HAND,
           inPlayArea=None, inPlayIndex=None),          # 手札リフレッシュ（スタンプ）
        NS(type=OptionType.PLAY, index=1, playerIndex=None, area=AreaType.HAND,
           inPlayArea=None, inPlayIndex=None),          # 圧縮アイテム（ポフィン）
        NS(type=OptionType.ATTACH, index=2, playerIndex=None, area=AreaType.HAND,
           inPlayArea=AreaType.ACTIVE, inPlayIndex=0),  # エネ手張り
    ]
    return NS(
        current=NS(yourIndex=0, energyAttached=energy_attached,
                   players=[NS(hand=hand)]),
        select=NS(context=SelectContext.MAIN, maxCount=1, minCount=0, option=opts),
    )


# スタンプが最上位、下に正帯の手張りとポフィン（choose と同じソート済み降順）
_SCORED = [(15000, 0, "E-4: Unfair Stamp"), (8300, 2, "S-5: attach"), (8000, 1, "Poffin")]


def _run(matchup, energy_attached, lethal=None, scored=None):
    policy = _DummyPolicy()
    policy.t = {"phase": "combat", "lethal": lethal, "threats": [], "matchup": matchup}
    return policy._sequencing_override(_make_obs(energy_attached),
                                       list(scored or _SCORED))


class SequencingTest(unittest.TestCase):
    def test_r26_attach_before_hand_refresh(self):
        self.assertEqual(_run("generic", energy_attached=False),
                         (2, "R-26: attach before hand refresh"))

    def test_r28_thin_before_draw_after_attach(self):
        self.assertEqual(_run("generic", energy_attached=True),
                         (1, "R-28: thin deck before draw"))

    def test_r28_disabled_vs_lo_archetype(self):
        self.assertIsNone(_run("chandelure", energy_attached=True))

    def test_r26_survives_vs_lo_archetype(self):
        # 手張りは山札を消費しないので LO 相手でも先行させる
        self.assertEqual(_run("chandelure", energy_attached=False),
                         (2, "R-26: attach before hand refresh"))

    def test_frozen_when_lethal(self):
        self.assertIsNone(_run("generic", energy_attached=False,
                               lethal={"route": "active"}))

    def test_noop_when_top_is_not_draw_play(self):
        # 最上位がドロー札でなければ素通し（順序割り込みなし）
        scored = [(15000, 1, "Poffin"), (8300, 2, "S-5: attach"),
                  (5000, 0, "E-4: Unfair Stamp")]
        self.assertIsNone(_run("generic", energy_attached=False, scored=scored))


if __name__ == "__main__":
    unittest.main()
