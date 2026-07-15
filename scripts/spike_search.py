"""スパイク: cg エンジンの search_begin/search_step による決定化 rollout の実測。

検証項目（撤退条件の判定材料）:
  A. 実対戦の obs から search_begin が通るか（隠れ情報の予測を自前 counting で構成）
  B. rollout（終局まで、両側 BasePolicy 操縦）の壁時計
  C. 多数 rollout の安定性（時間ドリフト・エラー率）と search_end の後始末
  D. 探索後に実対戦が壊れず続行し、正常に終局するか
"""
import sys
import time
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg import game, api  # noqa: E402
from ab_battle import load_agent, get_policy, read_deck, reset_agent  # noqa: E402

MARNIE = ROOT / "agents" / "marnie_munkidori_rb"
CHAND = ROOT / "agents" / "chandelure_rb"
DECK0 = read_deck(ROOT / "decks" / "candidates" / "2026-06-30_top5" / "winrate_2_marnie_grimmsnarl.csv")
DECK1 = read_deck(ROOT / "decks" / "candidates" / "chandelure_top.csv")

rng = random.Random(7)


def visible_cards(ps):
    """PlayerState から見えている自軍カードの multiset。"""
    c = Counter()
    if ps.hand:
        for card in ps.hand:
            c[card.id] += 1
    for card in ps.discard:
        c[card.id] += 1
    for pk in list(ps.active) + list(ps.bench):
        if pk is None:
            continue
        c[pk.id] += 1
        for card in pk.energyCards:
            c[card.id] += 1
        for card in pk.tools:
            c[card.id] += 1
        for card in pk.preEvolution:
            c[card.id] += 1
    for card in ps.prize:
        if card is not None:
            c[card.id] += 1
    return c


def unknown_pool(decklist, ps, expected, stadium_ids):
    """decklist − 可視カード = 非公開ゾーンの multiset。expected 枚に一致するか検査。
    スタジアム（共有ゾーン・所有者不明）は枚数が 1 過剰なときだけ引く。"""
    unk = Counter(decklist)
    unk.subtract(visible_cards(ps))
    if any(v < 0 for v in unk.values()):
        raise ValueError(f"accounting negative: { {k: v for k, v in unk.items() if v < 0} }")
    pool = [cid for cid, n in unk.items() for _ in range(n)]
    if len(pool) == expected + 1:
        for sid in stadium_ids:
            if sid in pool:
                pool.remove(sid)
                break
    if len(pool) != expected:
        raise ValueError(f"accounting mismatch: pool={len(pool)} expected={expected}")
    rng.shuffle(pool)
    return pool


def build_predictions(typed):
    """obs から search_begin の 6 引数（隠れ情報のサンプル）を作る。"""
    st = typed.current
    yi = st.yourIndex
    me, opp = st.players[yi], st.players[1 - yi]
    stadium_ids = [c.id for c in st.stadium]
    my_deck_list, opp_deck_list = (DECK0, DECK1) if yi == 0 else (DECK1, DECK0)

    my_facedown_prize = sum(1 for c in me.prize if c is None)
    my_pool = unknown_pool(my_deck_list, me, me.deckCount + my_facedown_prize, stadium_ids)
    your_prize = my_pool[:my_facedown_prize]
    your_deck = my_pool[my_facedown_prize:]

    opp_facedown_prize = sum(1 for c in opp.prize if c is None)
    expected_opp = opp.deckCount + opp_facedown_prize + opp.handCount
    opp_pool = unknown_pool(opp_deck_list, opp, expected_opp, stadium_ids)
    opp_prize = opp_pool[:opp_facedown_prize]
    opp_hand = opp_pool[opp_facedown_prize:opp_facedown_prize + opp.handCount]
    opp_deck = opp_pool[opp_facedown_prize + opp.handCount:]

    opp_active = []
    if opp.active and opp.active[0] is None:
        basics = [cid for cid in opp_hand]  # 雑: 手札予測の先頭のたねを使う代わりに山から
        opp_active = [opp_deck_list[0]]  # スパイクでは到達しない想定（盤面確立後に探索する）
    return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active


def rollout(root, pilots, max_steps=800):
    """root SearchState から終局まで決定化プレイアウト。(result, steps, seconds)"""
    t0 = time.perf_counter()
    st = root
    for step in range(max_steps):
        obs = st.observation
        cur = obs.current
        if cur is not None and cur.result != -1:
            return cur.result, step, time.perf_counter() - t0
        if obs.select is None or not obs.select.option:
            return -2, step, time.perf_counter() - t0  # 想定外
        policy = pilots[cur.yourIndex]
        try:
            sel = policy.choose(obs)
        except Exception:
            sel = list(range(obs.select.minCount)) or [0]
        if not sel:
            sel = list(range(obs.select.minCount))
        st = api.search_step(st.searchId, sel)
    return -1, max_steps, time.perf_counter() - t0


def main():
    # 実対戦の操縦者と、rollout 専用の別インスタンス（状態混線の防止）
    p0, p1 = load_agent(MARNIE), load_agent(CHAND)
    r0, r1 = load_agent(MARNIE), load_agent(CHAND)
    pilots_by_index = {}

    reset_agent(p0), reset_agent(p1)
    obs, _ = game.battle_start(DECK0, DECK1)
    assert obs is not None, "battle_start failed"

    searched_turns = set()
    n_search_points = 0
    result = -1

    for step in range(1000):
        typed = api.to_observation_class(obs)
        if typed.current is not None and typed.current.result != -1:
            result = typed.current.result
            break

        yi = typed.current.yourIndex if typed.current is not None else 0

        # ── 探索テスト: p0(marnie) の MAIN、ターンごとに1回、3ターンぶん ──
        if (yi == 0 and typed.select is not None
                and typed.select.context == api.SelectContext.MAIN
                and len(typed.select.option) >= 3
                and typed.current.turn not in searched_turns
                and n_search_points < 3):
            searched_turns.add(typed.current.turn)
            n_search_points += 1
            print(f"\n=== 探索テスト {n_search_points} (turn {typed.current.turn}, "
                  f"候補 {len(typed.select.option)}) ===")
            try:
                t0 = time.perf_counter()
                preds = build_predictions(typed)
                t_pred = time.perf_counter() - t0
                t0 = time.perf_counter()
                root = api.search_begin(typed, *preds)
                t_begin = time.perf_counter() - t0
                print(f"search_begin OK: 予測構成 {t_pred*1000:.1f}ms + begin {t_begin*1000:.1f}ms")

                pilots = {0: get_policy(r0), 1: get_policy(r1)}
                N = 60
                results, times, steps_list, errors = Counter(), [], [], 0
                t_all = time.perf_counter()
                for i in range(N):
                    # 決定化を rollout ごとに引き直す（サイド/相手手札の不確実性を平均化）
                    if i % 10 == 0 and i > 0:
                        api.search_end()
                        preds = build_predictions(typed)
                        root = api.search_begin(typed, *preds)
                    res, nst, sec = rollout(root, pilots)
                    if res in (-2,):
                        errors += 1
                    results[res] += 1
                    times.append(sec)
                    steps_list.append(nst)
                elapsed = time.perf_counter() - t_all
                api.search_end()
                import statistics as stats
                print(f"rollout x{N}: {elapsed:.1f}s 計 "
                      f"({elapsed/N*1000:.0f}ms/rollout, 中央値 {stats.median(times)*1000:.0f}ms, "
                      f"steps中央値 {stats.median(steps_list):.0f})")
                print(f"  結果分布: p0勝 {results[0]} / p1勝 {results[1]} / "
                      f"打切 {results[-1]} / 異常 {results[-2]} (エラー扱い {errors})")
                w = results[0] + results[1]
                if w:
                    print(f"  この局面の推定勝率(p0): {results[0]/w:.0%}")
            except Exception as e:
                print(f"FAILED: {type(e).__name__}: {e}")

        # ── 実対戦を通常続行 ──
        action = (p0 if yi == 0 else p1).agent(obs)
        obs = game.battle_select(action)

    game.battle_finish()
    print(f"\n=== 実対戦の続行確認: result={result} "
          f"({'正常終局' if result in (0, 1, 2) else '異常'}) ===")


if __name__ == "__main__":
    main()
