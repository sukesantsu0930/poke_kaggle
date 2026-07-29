"""ドラパルトの「矛盾」検出器（2026-07-27 ユーザー指摘の4件）。

勝率ではなく**論理的な矛盾**を数える。矛盾は検出可能なので、ルールが正しければゼロになる。
エッジが小さすぎて勝率では判定できない（4480戦/腕で検出限界 2.7pt）領域を、
決定論的な不変条件で詰めるための計器。

  D1 ポケパッド死蔵    : サーチ先がいるのに、打てるポケパッドを持ったまま番を終えた
  D2 ハイパーボール矛盾: ハイパーボールで**捨てたカードで持ってこれた札**を持ってきた
                         （例: ポフィンを切ってドラメシヤ）。ユーザー曰く「3条件のどれかの違反」
  D3 リーリエで山に返す: リーリエ（手札を山へ戻す）を打つ時に、打てるグッズを手札に残していた
  D4 ラティアス不要    : スボミーがバトル場にいる（= 逃げコストを払う必要が無い）のに
                         ラティアスを場に出した / わざわざ持ってきた

使い方:
  PYTHONIOENCODING=utf-8 python scripts/dragapult_consistency_audit.py
  DRA_UB_DEMAND=1 PYTHONIOENCODING=utf-8 python scripts/dragapult_consistency_audit.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent          # noqa: E402
from gauntlet import read_field, build_opponent       # noqa: E402
from train_ppo import GameSampler                     # noqa: E402
from policy_base import CARD_DB, option_card          # noqa: E402
from cg import api, game as cg_game                   # noqa: E402
from cg.api import AreaType, OptionType, SelectContext  # noqa: E402

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
LATIAS_EX, BUDEW = 184, 235
POFFIN, POKE_PAD, ULTRA_BALL, BROCK, LILLIE = 1086, 1152, 1121, 1210, 1227
GAMES = 60
OPPONENTS = ["archaludon", "alakazam", "froslass_starmie", "marnie"]
FIELD = ROOT / "research/meta/2026-07-27_uniform_frozen.csv"


def name_of(cid):
    d = CARD_DB.get(cid)
    return getattr(d, "name", None) or str(cid)


def can_fetch(searcher, target):
    """searcher（手札のサーチ札）で target（ポケモン）を持ってこれるか。"""
    d = CARD_DB.get(target)
    if d is None or int(getattr(d, "cardType", -1)) != 0:   # 0 == POKEMON
        return False
    is_ex = bool(getattr(d, "ex", False) or getattr(d, "megaEx", False))
    basic = bool(getattr(d, "basic", False))
    hp = getattr(d, "hp", 0) or 0
    if searcher == POFFIN:
        return basic and hp <= 70
    if searcher == POKE_PAD:
        return not is_ex
    if searcher == BROCK:
        return True                 # たね2 or 進化1（サポート枠を使う）
    if searcher == ULTRA_BALL:
        return True
    return False


def audit(sampler, opp_mod, opp_deck, n):
    mod, policy = sampler.target_mod, sampler.policy
    v = Counter()
    detail = Counter()
    games = 0
    for _ in range(n):
        reset_agent(mod)
        reset_agent(opp_mod)
        obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
        if obs is None:
            continue
        games += 1
        pending_ub = None
        while True:
            typed = api.to_observation_class(obs)
            cur = typed.current
            if cur is None or cur.result != -1:
                break
            if cur.yourIndex != 0:
                obs = cg_game.battle_select(opp_mod.agent(obs))
                continue
            me = cur.players[0]
            ctx = int(typed.select.context)
            opts = list(typed.select.option or [])
            hand = [c.id for c in (me.hand or []) if c is not None]
            active_id = (me.active[0].id if me.active and me.active[0] else 0)
            policy.decision_log = []
            action = mod.agent(obs)
            p = policy.p or {}
            for rec in (policy.decision_log or []):
                sel = set(rec.get("selected") or [])
                chosen_types = {opts[i].type for i in sel if i < len(opts)}

                # ── D1 / D3: MAIN での「打てるのに打たない」──
                if ctx == int(SelectContext.MAIN):
                    playable_items = set()
                    for o in opts:
                        if o.type == OptionType.PLAY:
                            c = option_card(typed, o)
                            if c is not None and c.id in (POFFIN, POKE_PAD, ULTRA_BALL):
                                playable_items.add(c.id)
                    pad_live = (POKE_PAD in playable_items
                                and any((policy.deck_max(t) or 0) > 0
                                        for t in (DREEPY, DRAKLOAK, BUDEW)))
                    if OptionType.END in chosen_types:
                        if pad_live:
                            v["D1 パッド死蔵(番を終えた)"] += 1
                    for i in sel:
                        if i >= len(opts) or opts[i].type != OptionType.PLAY:
                            continue
                        c = option_card(typed, opts[i])
                        if c is None:
                            continue
                        # D3: リーリエで手札を山へ戻すのに、打てるグッズが残っている
                        if c.id == LILLIE:
                            left = playable_items - {LILLIE}
                            if left:
                                v["D3 リーリエで未使用グッズを山へ"] += 1
                                for x in left:
                                    detail[f"D3 {name_of(x)}"] += 1
                        # D4: スボミーが前にいるのにラティアスを出す
                        if c.id == LATIAS_EX and active_id == BUDEW:
                            v["D4 ラティアス不要出し(スボミー前)"] += 1

                # ── D2: ハイパーボールの支払いと取得の矛盾 ──
                if ctx in (int(SelectContext.DISCARD),
                           int(SelectContext.DISCARD_CARD_OR_ATTACHED_CARD)):
                    cut = []
                    for i in sel:
                        if i < len(opts):
                            idx = getattr(opts[i], "index", None)
                            if idx is not None and idx < len(hand):
                                cut.append(hand[idx])
                    if cut:
                        pending_ub = cut
                if (ctx == int(SelectContext.TO_HAND)
                        and p.get("effect_id") == ULTRA_BALL and pending_ub):
                    for i in sel:
                        if i >= len(opts):
                            continue
                        c0 = option_card(typed, opts[i])
                        got = c0.id if c0 is not None else getattr(opts[i], "cardId", None)
                        if got is None:
                            continue
                        for x in pending_ub:
                            if can_fetch(x, got):
                                v["D2 UB矛盾(切った札で取れた)"] += 1
                                detail[f"D2 {name_of(x)}→{name_of(got)}"] += 1
                    pending_ub = None
                # D4b: スボミーが前にいるのにラティアスをわざわざ持ってくる
                if ctx == int(SelectContext.TO_HAND) and active_id == BUDEW:
                    for i in sel:
                        if i < len(opts):
                            c0 = option_card(typed, opts[i])
                            if c0 is not None and c0.id == LATIAS_EX:
                                v["D4b ラティアスを持ってくる(スボミー前)"] += 1
            policy.decision_log = None
            obs = cg_game.battle_select(action)
        try:
            cg_game.battle_finish()
        except Exception:
            pass
    return v, detail, games


def main():
    field = read_field(FIELD)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_rb",
                          read_deck(ROOT / "decks/fleet/popular_4_dragapult.csv"),
                          field, 600, seed=41)
    tot, tot_d, tot_g = Counter(), Counter(), 0
    for arch in OPPONENTS:
        opp_mod, opp_deck = build_opponent(rows[arch])
        v, d, n = audit(sampler, opp_mod, opp_deck, GAMES)
        tot.update(v)
        tot_d.update(d)
        tot_g += n
    print(f"=== 矛盾検出 {tot_g}戦 ===")
    for k in sorted(tot):
        print(f"  {k}: {tot[k]/tot_g:.2f} 回/試合  (計 {tot[k]})")
    if not tot:
        print("  違反なし")
    print("\n  [内訳]")
    for k, c in tot_d.most_common(12):
        print(f"    {k}: {c/tot_g:.2f}/試合")


if __name__ == "__main__":
    main()
