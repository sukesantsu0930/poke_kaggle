"""ターン内探索 — 決定化 + 候補手評価（rollout 葉 / V(s) 葉）。

正本は agents/_base/turn_search.py。各エージェントdirへは scripts/sync_base.py で同期する。
設計の骨格（2026-07-10 決定）: 聖域（確定ルール）→ ターン内展開 → 葉 = rollout（基準線）
のち V(s)−λP(脅威)（本命）→ 伝搬。決定ログと A/B は EXP-007（スパイク）の実測が根拠。

構成:
  - Determinizer: 観測 + counting（デッキリスト − 可視カード）→ search_begin の隠れ情報予測。
    相手リストは R-20 の matchup 判定 → opp_decks.OPP_DECKS（不明時 DEFAULT）。
    枚数が合わない分は clamp + リストからの復元抽出でパッドする（相手が予測リストと
    違うカードを使っていても探索を止めない）。
  - TurnSearcher.choose_root(obs, candidates): 候補手（ルールで絞った正帯のみ）を評価し
    最良の option index を返す。評価は決定化ごとに全候補を同じ隠れ世界で測る
    （paired comparison — 隠れ情報由来の分散を差の比較から消す）。
      rollout モード: root 手 → 両側パイロットで終局まで → 勝敗の平均
      value  モード: root 手 → 自ターンの終わりまで貪欲展開 → V(葉盤面) の平均
  - 時間予算: 1決定あたり SEARCH_TIME_PER_DECISION 秒。1試合の累計が SEARCH_GAME_BUDGET を
    超えるか、remainingOverageTime が SEARCH_MIN_OVERAGE を切ったら探索しない（R-23）。

安全（R-01）: ここで投げた例外は policy_base 側が握って**ルール順位に縮退**する。
パイロットの例外は最小合法選択に縮退する。search_end は finally で必ず呼ぶ。
"""
import random
import time
from collections import Counter

from cg import api

import opp_decks
import value_model as vm


def _visible_cards(ps):
    """PlayerState から見えているカード id の multiset。"""
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


class Determinizer:
    """観測から search_begin の隠れ情報予測を作る。"""

    def __init__(self, my_deck_list, rng):
        self.my_deck_list = my_deck_list
        self.rng = rng

    def _pool(self, deck_list, ps, expected, stadium_ids):
        """非公開ゾーンの中身を予測リストから復元する。必ず expected 枚を返す。"""
        unk = Counter(deck_list)
        unk.subtract(_visible_cards(ps))
        pool = [cid for cid, n in unk.items() if n > 0 for _ in range(n)]
        # スタジアム（共有ゾーン・所有者不明）: 1枚過剰のときだけこの側の持ち物とみなす
        if len(pool) == expected + 1:
            for sid in stadium_ids:
                if sid in pool:
                    pool.remove(sid)
                    break
        self.rng.shuffle(pool)
        if len(pool) > expected:          # 予測リストと実デッキがズレている → 切り詰め
            pool = pool[:expected]
        while len(pool) < expected:       # 足りない → 予測リストから復元抽出でパッド
            pool.append(self.rng.choice(deck_list))
        return pool

    def build(self, obs, matchup):
        """→ (your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active)"""
        st = obs.current
        yi = st.yourIndex
        me, opp = st.players[yi], st.players[1 - yi]
        stadium_ids = [c.id for c in st.stadium]

        opp_deck_list = opp_decks.OPP_DECKS.get(
            matchup, opp_decks.OPP_DECKS[opp_decks.DEFAULT_ARCHETYPE])

        my_fd_prize = sum(1 for c in me.prize if c is None)
        my_pool = self._pool(self.my_deck_list, me, me.deckCount + my_fd_prize, stadium_ids)
        your_prize = my_pool[:my_fd_prize]
        your_deck = my_pool[my_fd_prize:]

        opp_fd_prize = sum(1 for c in opp.prize if c is None)
        expected = opp.deckCount + opp_fd_prize + opp.handCount
        opp_pool = self._pool(opp_deck_list, opp, expected, stadium_ids)
        opp_prize = opp_pool[:opp_fd_prize]
        opp_hand = opp_pool[opp_fd_prize:opp_fd_prize + opp.handCount]
        opp_deck = opp_pool[opp_fd_prize + opp.handCount:]

        opp_active = []
        if opp.active and opp.active[0] is None:   # 裏向きバトル場（セットアップ中のみ）
            basics = [cid for cid in opp_hand + opp_deck
                      if _card_is_basic_pokemon(cid)]
            opp_active = [basics[0] if basics else opp_deck_list[0]]
        return your_deck, your_prize, opp_deck, opp_prize, opp_hand, opp_active


_CARD_DB = {c.cardId: c for c in api.all_card_data()}


def _card_is_basic_pokemon(cid):
    card = _CARD_DB.get(cid)
    return (card is not None and card.cardType == api.CardType.POKEMON
            and getattr(card, "basic", False))


class TurnSearcher:
    """1つの BasePolicy インスタンスに紐づく探索器。"""

    MIN_SAMPLES = 3          # rollout モード: 候補あたり最低サンプル数（未満なら探索放棄）
    MIN_DETERMINIZATIONS = 2  # value モード: 最低決定化数
    MAX_ROLLOUT_STEPS = 700

    def __init__(self, policy):
        self.policy = policy
        self.rng = random.Random(20260710)
        self.det = None                   # my_deck_list が入ってから作る
        self._pilot_self = None
        self._pilot_opp = None
        self._pilot_opp_matchup = None
        self.value_model = None
        self._value_load_tried = False
        self.diag = Counter()

    # ── パイロット ──

    def _get_pilot_self(self):
        if self._pilot_self is None:
            p = self.policy.__class__()
            p.search_enabled = False      # 再帰探索の禁止
            self._pilot_self = p
        return self._pilot_self

    def _get_pilot_opp(self, matchup):
        if self._pilot_opp is None or self._pilot_opp_matchup != matchup:
            import generic_policy
            deck = opp_decks.OPP_DECKS.get(
                matchup, opp_decks.OPP_DECKS[opp_decks.DEFAULT_ARCHETYPE])
            # make_generic_policy はクラスを返す（make_agent に渡す想定のため）→ ここで実体化
            cls = generic_policy.make_generic_policy(deck, name=f"srch_{matchup}")
            self._pilot_opp = cls()
            self._pilot_opp.search_enabled = False
            self._pilot_opp_matchup = matchup
        return self._pilot_opp

    def _pilot_select(self, st, my_index):
        """探索状態1つぶんの選択。例外は最小合法選択に縮退。"""
        obs = st.observation
        pilot = (self._get_pilot_self() if obs.current.yourIndex == my_index
                 else self._get_pilot_opp(self.policy.t["matchup"]))
        try:
            sel = pilot.choose(obs)
        except Exception:
            self.diag["pilot_errors"] += 1
            import traceback
            self.last_pilot_error = traceback.format_exc(limit=4)
            sel = None
        if not sel:
            sel = list(range(obs.select.minCount))
        return sel

    # ── 葉評価 ──

    def _playout(self, st, my_index):
        """終局まで進めて勝敗を返す（rollout 葉）。勝ち1 / 負け0 / 引分・打切0.5。"""
        for _ in range(self.MAX_ROLLOUT_STEPS):
            cur = st.observation.current
            if cur is not None and cur.result != -1:
                if cur.result == my_index:
                    return 1.0
                return 0.5 if cur.result == 2 else 0.0
            if st.observation.select is None or not st.observation.select.option:
                return 0.5
            st = api.search_step(st.searchId, self._pilot_select(st, my_index))
        return 0.5

    def _greedy_to_turn_end(self, st, my_index, root_turn):
        """自ターンの終わりまで貪欲展開して (葉の状態, 最後に見えた自手札) を返す（value 葉）。
        葉は相手の選択番になり自手札が観測から消えるため、見えていた最後の手札を持ち越す
        （V の手札特徴の train/serve 一致のため）。"""
        last_hand = None
        for _ in range(80):
            cur = st.observation.current
            if cur is not None:
                hand = cur.players[my_index].hand
                if hand is not None:
                    last_hand = hand
            if cur is None or cur.result != -1 or cur.turn != root_turn:
                return st, last_hand
            if st.observation.select is None or not st.observation.select.option:
                return st, last_hand
            st = api.search_step(st.searchId, self._pilot_select(st, my_index))
        return st, last_hand

    def _leaf_value(self, st, my_index, hand_cards=None):
        """value モードの葉: 終局なら確定値、それ以外は V(盤面)。"""
        cur = st.observation.current
        if cur is not None and cur.result != -1:
            if cur.result == my_index:
                return 1.0
            return 0.5 if cur.result == 2 else 0.0
        x = vm.extract_features(st.observation, my_index, hand_cards=hand_cards)
        return self.value_model.predict(x)

    # ── 本体 ──

    def _ensure_ready(self, mode):
        if self.policy.my_deck_list is None:
            raise RuntimeError("my_deck_list unset (make_agent 経由でないか、注入漏れ)")
        if self.det is None:
            self.det = Determinizer(list(self.policy.my_deck_list), self.rng)
        if mode == "value" and self.value_model is None:
            if not self._value_load_tried:
                self._value_load_tried = True
                self.value_model = self._load_value_model()
            if self.value_model is None:
                self.diag["value_model_missing"] += 1
                return "rollout"          # V 不在 → rollout に自動縮退
        return mode

    def _load_value_model(self):
        """value_model.npz をポリシー自身の main モジュールの隣から読む。
        （vm.load_default() は vm モジュールの隣を見るが、ローカル評価のクロス dir
        import では他機の dir を指しうるため、ポリシー基準のパスを優先する。）"""
        import os
        import sys
        mod = sys.modules.get(self.policy.__class__.__module__)
        mod_file = getattr(mod, "__file__", None)
        if mod_file:
            path = os.path.join(os.path.dirname(os.path.abspath(mod_file)),
                                "value_model.npz")
            if os.path.exists(path):
                return vm.ValueModel.load(path)
        return vm.load_default()

    def choose_root(self, obs, candidates):
        """候補 option index 群を評価して最良を返す。評価不成立なら None（ルールに縮退）。

        candidates: [(option_index, rule_score)] スコア降順・正帯のみ・maxCount==1 前提。
        """
        mode = self._ensure_ready(self.policy.SEARCH_MODE)
        budget = float(self.policy.SEARCH_TIME_PER_DECISION)
        my_index = obs.current.yourIndex
        root_turn = obs.current.turn
        matchup = self.policy.t["matchup"]
        idxs = [i for i, _ in candidates]
        totals = {i: 0.0 for i in idxs}
        counts = {i: 0 for i in idxs}

        t0 = time.perf_counter()
        self.diag["calls"] += 1
        try:
            while time.perf_counter() - t0 < budget:
                # 1決定化 = 1つの隠れ世界。全候補を同じ世界で測る（paired）
                preds = self.det.build(obs, matchup)
                root = api.search_begin(obs, *preds)
                for i in idxs:
                    if time.perf_counter() - t0 > budget * 1.5:
                        break             # 世界の途中でも硬い上限で切る
                    st = api.search_step(root.searchId, [i])
                    if mode == "rollout":
                        v = self._playout(st, my_index)
                    else:
                        leaf, last_hand = self._greedy_to_turn_end(st, my_index, root_turn)
                        v = self._leaf_value(leaf, my_index, hand_cards=last_hand)
                    totals[i] += v
                    counts[i] += 1
                api.search_end()
                if mode == "value" and min(counts.values()) >= 8:
                    break                 # V は決定化ノイズだけなので少数で足りる
                # 予算内で最低サンプル数に届かない見込みなら候補を上位に絞る
                # （全候補を薄く測って全滅するより、上位2〜3個を濃く測る）
                elapsed_1 = time.perf_counter() - t0
                per_sample = elapsed_1 / max(1, sum(counts.values()))
                need = self.MIN_SAMPLES if mode == "rollout" else self.MIN_DETERMINIZATIONS
                remaining = budget - elapsed_1
                if remaining > 0 and counts[idxs[0]] < need:
                    affordable = max(2, int(remaining / (per_sample * max(1, need - counts[idxs[0]]))))
                    if affordable < len(idxs):
                        self.diag["trimmed"] += 1
                        idxs = idxs[:affordable]
        finally:
            try:
                api.search_end()
            except Exception:
                pass

        elapsed = time.perf_counter() - t0
        self.policy._search_time_used += elapsed
        need = self.MIN_SAMPLES if mode == "rollout" else self.MIN_DETERMINIZATIONS
        if min(counts[i] for i in idxs) < need:   # 刈られた候補は判定に含めない
            self.diag["insufficient"] += 1
            return None
        self.diag["ok"] += 1
        means = {i: totals[i] / counts[i] for i in idxs}
        best = max(idxs, key=lambda i: (means[i], -idxs.index(i)))
        self.last_report = {
            "mode": mode, "elapsed": round(elapsed, 3),
            "samples": dict(counts),
            "means": {i: round(m, 3) for i, m in means.items()},
            "picked": best, "rule_pick": idxs[0],
        }
        return best
