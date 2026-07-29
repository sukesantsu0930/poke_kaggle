"""ハイパーボール診断 — 「打てるのに打っていない」が実在するかを測る（2026-07-27）。

背景: 07-27 の一般ルール移植で、集計をノイズ以上に動かしたのは R-13+②
（ハイパーボールの発火条件の置換）だけだった（−3.6pt）。本デッキで唯一の無条件サーチ
なので、打つ/打たないの線引きがセットアップ速度をそのまま決める＝支点になっている。
ここでは**現行の既定設定が実際に握り込んでいるのか**を、勝率でなく挙動で測る。

出力:
  - 提示: ハイパーボールが選択肢に出た回数（打てる状態だった回数）
  - 発火/保留: そのうち実際に打った回数 / `negative_hand<2` で見送った回数
  - 保留中の手札: 見送った瞬間に手札に何があったか（握っている札の正体）
  - 死蔵: 試合終了時に手札へ残ったハイパーボールの枚数
  - 捨てた札: 実際に打ったとき、コストとして何を切ったか

使い方（トグルを変えて比較できる）:
  PYTHONIOENCODING=utf-8 python scripts/dragapult_ultraball_diag.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent      # noqa: E402
from gauntlet import read_field, build_opponent   # noqa: E402
from train_ppo import GameSampler                 # noqa: E402
from policy_base import CARD_DB, option_card      # noqa: E402
from cg import api, game as cg_game               # noqa: E402
from cg.api import SelectContext                  # noqa: E402

ULTRA_BALL = 1121
GAMES = 60
OPPONENTS = ["archaludon", "alakazam", "froslass_starmie", "marnie"]
FIELD = ROOT / "research/meta/2026-07-27_uniform_frozen.csv"


def name_of(cid):
    d = CARD_DB.get(cid)
    return getattr(d, "name", None) or str(cid)


def hand_ids(typed, yi):
    me = typed.current.players[yi]
    return [c.id for c in (me.hand or []) if c is not None]


def diag(sampler, opp_mod, opp_deck, n):
    mod, policy = sampler.target_mod, sampler.policy
    stat = Counter()
    held_with = Counter()      # 保留時に手札にあった札
    fetched = Counter()        # サーチで実際に持ってきた札
    discarded = Counter()      # 発火時にコストで切った札
    games = 0
    for _ in range(n):
        reset_agent(mod)
        reset_agent(opp_mod)
        obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
        if obs is None:
            continue
        games += 1
        last_hand = []
        while True:
            typed = api.to_observation_class(obs)
            cur = typed.current
            if cur is None or cur.result != -1:
                break
            if cur.yourIndex != 0:
                obs = cg_game.battle_select(mod.agent(obs) if False
                                            else opp_mod.agent(obs))
                continue
            yi = cur.yourIndex
            ctx = int(typed.select.context)
            opts = list(typed.select.option or [])
            hand = hand_ids(typed, yi)
            last_hand = hand
            policy.decision_log = []
            action = mod.agent(obs)
            for rec in (policy.decision_log or []):
                sel = set(rec.get("selected") or [])
                for o in rec["options"]:
                    reason = o.get("reason") or ""
                    picked = o["i"] in sel
                    # トグルで reason 文字列が変わる（"S-4: Ultra Ball" /
                    # "S-4/R-13+: Ultra Ball (last item...)" / "Ultra Ball: hold (...)"）
                    # ので、含有判定で拾う
                    if "Ultra Ball" not in reason:
                        continue
                    stat["present"] += 1
                    if "hold" in reason:
                        stat["held"] += 1
                        for c in hand:
                            if c != ULTRA_BALL:
                                held_with[c] += 1
                    elif picked:
                        stat["fired"] += 1
                # 何を持ってきたか（TO_HAND で実際に選ばれた札）。
                # ハイパーボールの利得が「2枚捨てる価値」に見合うかの判定材料。
                if (ctx == int(SelectContext.TO_HAND)
                        and (policy.p or {}).get("effect_id") == ULTRA_BALL):
                    for i in sel:
                        if i < len(opts):
                            c0 = option_card(typed, opts[i])
                            cid0 = c0.id if c0 is not None else getattr(
                                opts[i], "cardId", None)
                            if cid0 is not None:
                                fetched[cid0] += 1
                # 発火時のコスト（DISCARD で実際に選ばれた札）
                if ctx in (int(SelectContext.DISCARD),
                           int(SelectContext.DISCARD_CARD_OR_ATTACHED_CARD)):
                    for i in sel:
                        if i < len(opts):
                            idx = getattr(opts[i], "index", None)
                            if idx is not None and idx < len(hand):
                                discarded[hand[idx]] += 1
            policy.decision_log = None
            obs = cg_game.battle_select(action)
        stat["stranded"] += last_hand.count(ULTRA_BALL)
        try:
            cg_game.battle_finish()
        except Exception:
            pass
    return stat, held_with, discarded, fetched, games


def main():
    field = read_field(FIELD)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_rb",
                          read_deck(ROOT / "decks/fleet/popular_4_dragapult.csv"),
                          field, 600, seed=17)
    tot, tot_held, tot_disc, tot_fet, tot_g = Counter(), Counter(), Counter(), Counter(), 0
    for arch in OPPONENTS:
        opp_mod, opp_deck = build_opponent(rows[arch])
        stat, held, disc, fet, n = diag(sampler, opp_mod, opp_deck, GAMES)
        tot.update(stat)
        tot_held.update(held)
        tot_disc.update(disc)
        tot_fet.update(fet)
        tot_g += n
        rate = stat["fired"] / stat["present"] if stat["present"] else 0
        print(f"\n=== vs {arch} ({n}戦) ===")
        print(f"  提示 {stat['present']/n:.2f}/試合  発火 {stat['fired']/n:.2f}  "
              f"保留 {stat['held']/n:.2f}  発火率 {rate:.0%}")
        print(f"  終了時に手札へ死蔵 {stat['stranded']/n:.2f}枚/試合")
    print(f"\n=== 合計 {tot_g}戦 ===")
    rate = tot["fired"] / tot["present"] if tot["present"] else 0
    print(f"  提示 {tot['present']/tot_g:.2f}/試合  発火 {tot['fired']/tot_g:.2f}  "
          f"保留 {tot['held']/tot_g:.2f}  **発火率 {rate:.0%}**")
    print(f"  終了時に手札へ死蔵 {tot['stranded']/tot_g:.2f}枚/試合")
    print("\n  [保留した瞬間に握っていた札 top10]")
    for cid, c in tot_held.most_common(10):
        print(f"    {name_of(cid):28s} {c/tot_g:.2f}/試合")
    print("\n  [サーチで持ってきた札 top10]")
    for cid, c in tot_fet.most_common(10):
        print(f"    {name_of(cid):28s} {c/tot_g:.2f}/試合")
    print("\n  [発火時にコストで切った札 top10]")
    for cid, c in tot_disc.most_common(10):
        print(f"    {name_of(cid):28s} {c/tot_g:.2f}/試合")


if __name__ == "__main__":
    main()
