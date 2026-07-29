"""カーズドボム診断 — ボムが実際に何と交換されているかを測る（2026-07-28）。

カーズドボムは **自分がKOされる = サイド1枚献上** と引き換えにダメカンを置く取引:
  ヨノワール(133) 13個=130 / サマヨール(132) 5個=50、いずれも自壊。
したがって唯一の評価軸は**サイド収支**であって、打点ではない。
EXP-048 の要因分解が「献上1.29 vs 収入1.08サイド = 赤字」と出した部分を、
機構レベルで分解する。

測るもの（1試合あたり）:
  - 発火回数（ヨノワール / サマヨール別）
  - **収支**: ボムで献上したサイド（= 発火回数）vs ボムがKOした相手のサイド
  - 的の内訳（何をKOしたか。ex を叩けているか、置物に撃っていないか）
  - 空撃ち: 撃ったのに相手が落ちなかった回数（mode2/3 の合算前提が崩れた回数）
  - 温存死: 場にボマーがいるまま試合終了した回数

使い方:
  DUSK_DECK_CSV=decks/fleet/dragapult_dusknoir_v2.csv PYTHONIOENCODING=utf-8 \
      python scripts/dusknoir_bomb_diag.py [--games 60]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent          # noqa: E402
from gauntlet import read_field, build_opponent       # noqa: E402
from train_ppo import GameSampler                     # noqa: E402
from policy_base import CARD_DB                       # noqa: E402
from cg import api, game as cg_game                   # noqa: E402
from cg.api import LogType                            # noqa: E402

DUSCLOPS, DUSKNOIR = 132, 133
FIELD = ROOT / "research/meta/2026-07-27_uniform_frozen.csv"


def nm(cid):
    d = CARD_DB.get(cid)
    return getattr(d, "name", None) or str(cid)


def prize_of(pk):
    d = CARD_DB.get(pk.id) if pk else None
    if d is None:
        return 1
    if getattr(d, "megaEx", False):
        return 3
    return 2 if getattr(d, "ex", False) else 1


def snapshot(ps):
    """相手盤面 {coord: (id, hp, prize, serial)}。

    KO でベンチが詰まると座標がずれるので、**同定は serial（カード固有ID）で行う**。
    座標だけで追うと「別の個体が同じ座標に来た」を KO と誤認/見逃す
    （2026-07-28 実測: 130ダメージで残HP130 が落ちないという矛盾で発覚）。"""
    out = {}
    for i, pk in enumerate(([ps.active[0]] if ps.active else [None]) + list(ps.bench)):
        if pk is not None:
            out[i] = (pk.id, pk.hp, prize_of(pk), getattr(pk, "serial", None))
    return out


def serials(board):
    return {v[3] for v in board.values() if v[3] is not None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--opponents", default="marnie,archaludon,alakazam,froslass_starmie")
    args = ap.parse_args()

    field = read_field(FIELD)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_dusknoir_rb",
                          read_deck(ROOT / "decks/fleet/dragapult_dusknoir_v2.csv"),
                          field, 600, seed=97)
    policy = sampler.policy
    tot = Counter()
    killed = Counter()
    games = 0

    for arch in args.opponents.split(","):
        opp_mod, opp_deck = build_opponent(rows[arch.strip()])
        for _ in range(args.games):
            reset_agent(sampler.target_mod)
            reset_agent(opp_mod)
            obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
            if obs is None:
                continue
            games += 1
            # 【計測は単一ループでターン境界を見る】入れ子でエージェントを駆動すると
            # 窓の切り方を必ず間違える（2026-07-28 に3度やった）。ターン開始時の盤面と
            # ターン終了時の盤面だけを比べる。
            cur_turn = None
            turn_start_board = {}
            bomb_this_turn = None      # (bomber, mode, coord, target_id, target_hp)
            atk_this_turn = []

            def settle():
                """ターンが終わった時点で、直前ターンのボムの収支を確定する。"""
                if bomb_this_turn is None:
                    return
                bomber, mode, coord, tid, thp, tser, tprize = bomb_this_turn
                tot["fire"] += 1
                tot[f"fire_{nm(bomber)}"] += 1
                tot[f"mode{mode}"] += 1
                tot["prize_give"] += 1
                gone = (tser is not None and tser not in serials(end_board))
                if gone:
                    tot["prize_gain"] += tprize
                    killed[nm(tid)] += 1
                else:
                    tot["whiff"] += 1
                    if mode in (2, 3) and 154 not in atk_this_turn:
                        tot["whiff_no_dive"] += 1
                    if tot["whiff"] <= 8:
                        print(f"    [空撃ち] mode={mode} 狙い={nm(tid)} 残HP={thp} "
                              f"観測攻撃={atk_this_turn}")

            while True:
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is None or cur.result != -1:
                    break
                for lg in (typed.logs or []):
                    if lg.type == LogType.ATTACK:
                        atk_this_turn.append(lg.attackId)
                # 【ターン境界は turn 番号で見る】yourIndex は自分の番中でも相手側に振れる
                # （こちらのボム自壊で相手が「サイドを取る」決定をするため）。それを
                # ターン終了と誤認すると**攻撃前の盤面で締めてしまう**（2026-07-28 実測、
                # 空撃ち19/21 の正体はこの計測バグだった）。
                t_now = getattr(cur, "turn", 0)
                if cur_turn is not None and t_now != cur_turn:
                    end_board = snapshot(cur.players[1 - cur.yourIndex]
                                         if cur.yourIndex == 1 else cur.players[1])
                    settle()
                    bomb_this_turn = None
                    atk_this_turn = []
                    cur_turn = None
                if cur.yourIndex != 0:
                    obs = cg_game.battle_select(opp_mod.agent(obs))
                    continue
                if cur_turn is None:
                    cur_turn = t_now
                    turn_start_board = snapshot(cur.players[1])
                policy.decision_log = []
                action = sampler.target_mod.agent(obs)
                for rec in (policy.decision_log or []):
                    sel = set(rec.get("selected") or [])
                    for o in rec["options"]:
                        if o["i"] in sel and "Cursed Blast" in (o.get("reason") or ""):
                            bp = dict(policy.bomb_plan or {})
                            c = bp.get("coord")
                            live = snapshot(cur.players[1])
                            tgt = live.get(c) or turn_start_board.get(c) or (0, 0, 1, None)
                            bomb_this_turn = (bp.get("bomber") or DUSKNOIR,
                                              bp.get("mode"), c, tgt[0], tgt[1],
                                              tgt[3], tgt[2])
                policy.decision_log = None
                obs = cg_game.battle_select(action)
            # 終局時に未確定のボムを締める
            t3 = api.to_observation_class(obs)
            if t3.current is not None and t3.current.players:
                end_board = snapshot(t3.current.players[1])
                settle()
                me = t3.current.players[0]
                for pk in ([me.active[0]] if me.active else []) + list(me.bench or []):
                    if pk is not None and pk.id in (DUSCLOPS, DUSKNOIR):
                        tot["stranded_bomber"] += 1
            try:
                cg_game.battle_finish()
            except Exception:
                pass

    g = max(1, games)
    print(f"=== カーズドボム診断（{games}戦）===")
    print(f"  発火 {tot['fire']/g:.2f}/試合  "
          f"（ヨノワール {tot['fire_'+nm(DUSKNOIR)]/g:.2f} / "
          f"サマヨール {tot['fire_'+nm(DUSCLOPS)]/g:.2f}）")
    print(f"  モード内訳 単体{tot['mode1']} / 正面合算{tot['mode2']} / ばら撒き合算{tot['mode3']}")
    print(f"  **サイド収支: 献上 {tot['prize_give']/g:.2f} vs 収入 {tot['prize_gain']/g:.2f} "
          f"= {(tot['prize_gain']-tot['prize_give'])/g:+.2f}/試合**")
    print(f"  空撃ち（撃ったが相手が落ちず） {tot['whiff']}/{tot['fire']}"
          f"  うち mode2/3 でダイブ不発 {tot['whiff_no_dive']}")
    print(f"  温存死（ボマーを場に残して終局） {tot['stranded_bomber']/g:.2f}/試合")
    print("\n  [ボムが落とした相手 top8]")
    for cid, c in killed.most_common(8):
        print(f"    {cid}: {c/g:.2f}/試合")


if __name__ == "__main__":
    main()
