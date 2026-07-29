"""ターン内全探索の実現可能性調査（2026-07-27 ユーザー指示）。

背景: ダイブ到達判定を手書きの経路リストで書いていたため穴が空いていた。
エンジンは search_begin / search_step / search_release で**分岐探索**を公開しているので、
行動モデルを手書きせず**エンジンを真値として自ターンを全展開**できるはず。
全エージェント共通の基盤能力にする前に、**規模と速度**を実測する。

測るもの:
  - 自ターン1回あたりの決定数（END までの深さ）と各決定の選択肢数（分岐因子）
  - 素朴な全展開の状態数（打ち切り無しだと何個になるか）
  - search_step 1回あたりの実測コスト（秒）
  - 深さ/状態数の上限を与えたときの到達率（＝実用的な打ち切りで足りるか）

使い方:
  PYTHONIOENCODING=utf-8 python scripts/turn_enumeration_survey.py [--games 20] [--cap 20000]
"""
import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent          # noqa: E402
from gauntlet import read_field, build_opponent       # noqa: E402
from train_ppo import GameSampler                     # noqa: E402
from cg import api, game as cg_game                   # noqa: E402
from cg.api import OptionType, SelectContext          # noqa: E402

FIELD = ROOT / "research/meta/2026-07-27_uniform_frozen.csv"


def determinize(policy, obs):
    """自山・サイド・相手側の予測を作る（R-32 の自山知識を使う）。

    自ターンの到達可能性を問うだけなので、相手の中身は当たっている必要が無い
    （こちらの手番中に相手は選択しない）。枚数さえ合っていればよい。"""
    st = obs.current
    yi = st.yourIndex
    me, opp = st.players[yi], st.players[1 - yi]
    # 自山: R-32 の上限（＝山+サイド）から実枚数ぶんを取り出す
    pool = []
    for cid in (policy.my_deck_list or []):
        pool.append(cid)
    # 見えている自分の札を引いて「山+サイド」の多重集合を作る
    unseen = Counter()
    for cid in set(pool):
        n = policy.deck_max(cid)
        if n is None:
            return None
        if n > 0:
            unseen[cid] = n
    prizes = []
    if policy.prizes_known():
        for cid in set(pool):
            k = policy.prized_count(cid) or 0
            prizes.extend([cid] * k)
    flat = [c for cid, n in unseen.items() for c in [cid] * n]
    need_deck = me.deckCount
    need_prize = len(me.prize or [])
    if len(prizes) != need_prize:
        prizes = flat[:need_prize]
        deck_pred = flat[need_prize:]
    else:
        rest = list(flat)
        for c in prizes:
            if c in rest:
                rest.remove(c)
        deck_pred = rest
    if len(deck_pred) < need_deck:
        deck_pred = (deck_pred + flat)[:need_deck]
    deck_pred = deck_pred[:need_deck]
    # 相手側: 枚数だけ合わせる（中身は自ターンの到達可能性に影響しない）
    filler = deck_pred[0] if deck_pred else (pool[0] if pool else 1)
    opp_deck = [filler] * opp.deckCount
    opp_prize = [filler] * len(opp.prize or [])
    opp_hand = [filler] * opp.handCount
    opp_active = []
    act = opp.active
    if act and act[0] is None:
        opp_active = [119]        # 場に伏せがある場合だけ、たねを1枚predict
    return deck_pred, prizes, opp_deck, opp_prize, opp_hand, opp_active


def pk_sig(pk):
    """ポケモン1体の正準署名（順序違いを潰すため multiset は sorted）。"""
    if pk is None:
        return None
    return (pk.id,
            getattr(pk, "hp", 0),
            tuple(sorted(c.id for c in (pk.energyCards or []) if c is not None)),
            tuple(sorted(c.id for c in (pk.tools or []) if c is not None)),
            tuple(sorted(c.id for c in (pk.preEvolution or []) if c is not None)),
            bool(getattr(pk, "appearThisTurn", False)))


def state_key(o, yi):
    """到達盤面の正準キー。**手の順序ではなく結果**で同一視する。

    ここが効く理由: ポフィン→パッド と パッド→ポフィン は別ノードだが到達盤面は同じ。
    素朴な展開は可換な手の順列を全部踏むので、深さ16〜29 で状態数が爆発していた。
    効果の途中（ハイパーボールの捨て札選択など）は context/effect で区別する必要がある。"""
    st = o.current
    if st is None:
        return None
    me = st.players[yi]
    opp = st.players[1 - yi]
    sel = o.select
    eff = getattr(sel, "effect", None)
    eff_id = getattr(eff, "id", None) if eff is not None else None
    return (
        int(getattr(sel, "context", -1)), eff_id,
        int(getattr(sel, "minCount", 0)), int(getattr(sel, "maxCount", 0)),
        pk_sig(me.active[0] if me.active else None),
        tuple(sorted(x for x in (pk_sig(b) for b in (me.bench or [])) if x)),
        tuple(sorted(c.id for c in (me.hand or []) if c is not None)),
        tuple(sorted(c.id for c in (me.discard or []) if c is not None)),
        me.deckCount, len(me.prize or []),
        bool(st.energyAttached), bool(st.supporterPlayed),
        pk_sig(opp.active[0] if opp.active else None),
        tuple(sorted(x for x in (pk_sig(b) for b in (opp.bench or [])) if x)),
        len(opp.prize or []),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=12)
    ap.add_argument("--cap", type=int, default=20000)
    ap.add_argument("--budget", type=float, default=2.0, help="1ターンあたりの秒上限")
    args = ap.parse_args()

    field = read_field(FIELD)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_rb",
                          read_deck(ROOT / "decks/fleet/popular_4_dragapult.csv"),
                          field, 600, seed=71)
    policy = sampler.policy
    opp_mod, opp_deck_list = build_opponent(rows["archaludon"])

    agg = Counter()
    times = []
    node_counts = []
    depth_max = Counter()
    branch_all = Counter()
    turns_measured = 0
    turns_capped = 0

    for g in range(args.games):
        reset_agent(sampler.target_mod)
        reset_agent(opp_mod)
        obs, _ = cg_game.battle_start(sampler.deck, opp_deck_list)
        if obs is None:
            continue
        while True:
            typed = api.to_observation_class(obs)
            cur = typed.current
            if cur is None or cur.result != -1:
                break
            if cur.yourIndex != 0:
                obs = cg_game.battle_select(opp_mod.agent(obs))
                continue
            if int(typed.select.context) == int(SelectContext.MAIN):
                preds = determinize(policy, typed)
                if preds is not None:
                    n, dmax, bh, el, done, dh = enumerate_turn(
                        typed, preds, args.cap, args.budget)
                    agg["dedup_hits"] += dh
                    if n > 0:
                        turns_measured += 1
                        node_counts.append(n)
                        times.append(el)
                        depth_max[dmax] += 1
                        branch_all.update(bh)
                        if not done:
                            turns_capped += 1
                    else:
                        agg["enum_failed"] += 1
            obs = cg_game.battle_select(sampler.target_mod.agent(obs))
        try:
            cg_game.battle_finish()
        except Exception:
            pass

    print(f"=== ターン内全探索 調査（{args.games}試合 / 自ターン {turns_measured} 本）===")
    if node_counts:
        node_counts.sort()
        times.sort()
        n = len(node_counts)
        print(f"  展開ノード数  中央値 {node_counts[n//2]:,} / "
              f"90%点 {node_counts[int(n*0.9)]:,} / 最大 {node_counts[-1]:,}")
        print(f"  所要時間      中央値 {times[n//2]*1000:.0f}ms / "
              f"90%点 {times[int(n*0.9)]*1000:.0f}ms / 最大 {times[-1]*1000:.0f}ms")
        tot_steps = sum(node_counts)
        tot_time = sum(times)
        print(f"  search_step   実測 {tot_steps/max(tot_time,1e-9):,.0f} step/秒")
        print(f"  打ち切り      {turns_capped}/{turns_measured} 本 "
              f"(cap={args.cap} / {args.budget}s)")
        print(f"  深さの分布    {dict(sorted(depth_max.items()))}")
        top = branch_all.most_common(8)
        print(f"  分岐因子分布  {top}")
    for k in sorted(agg):
        print(f"  {k}: {agg[k]}")


def enumerate_turn(typed, preds, cap, budget):
    """自ターンを素朴に全展開。(ノード数, 最大深さ, 分岐ヒスト, 所要秒, 完走したか)"""
    t0 = time.time()
    deadline = t0 + budget
    nodes = 0
    dmax = 0
    branch = Counter()
    try:
        root = api.search_begin(typed, *preds)
    except Exception:
        return 0, 0, branch, 0.0, False, 0
    yi = typed.current.yourIndex
    seen = set()
    dedup_hits = 0
    try:
        stack = [(root, 0)]
        while stack:
            if nodes >= cap or time.time() > deadline:
                return nodes, dmax, branch, time.time() - t0, False, dedup_hits
            st, depth = stack.pop()
            o = st.observation
            if o.select is None or not o.select.option:
                continue
            if o.current is None or o.current.yourIndex != yi:
                continue          # 相手手番に入ったら打ち切り（自ターンの探索）
            opts = o.select.option
            branch[len(opts)] += 1
            dmax = max(dmax, depth)
            for i in range(len(opts)):
                if nodes >= cap or time.time() > deadline:
                    return nodes, dmax, branch, time.time() - t0, False, dedup_hits
                try:
                    nxt = api.search_step(st.searchId, [i])
                except Exception:
                    continue
                nodes += 1
                if opts[i].type == OptionType.END:
                    api.search_release(nxt.searchId)
                    continue
                k = state_key(nxt.observation, yi)
                if k is not None and k in seen:
                    dedup_hits += 1
                    api.search_release(nxt.searchId)   # 同一盤面 = 展開不要
                    continue
                if k is not None:
                    seen.add(k)
                stack.append((nxt, depth + 1))
    finally:
        api.search_end()
    return nodes, dmax, branch, time.time() - t0, True, dedup_hits


if __name__ == "__main__":
    main()
