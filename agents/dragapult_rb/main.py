"""ドラパルトex（Dragapult ex / Phantom Dive ばら撒き）ルールベースエージェント — 公式サンプル移植

土台: Kaggle 公式サンプル "A Sample Rule-Based Agent (Dragapult ex Deck)"（Apache-2.0 系譜。
research/external/kaggle_notebooks/a-sample-rule-based-agent-dragapult-ex-deck/main_reference.py）。
その方策の核 = `main_option_proc` の配分プラン DFS（「60 で取り切れる相手部分集合」だけを列挙する
枝刈り + prize_count/pokemon_score によるサイドペース採点）を BasePolicy のフックに移植し、
ptcg-abc の divergence 実測修正（Fez 降格 / EVOLVE 据え置き / Dragapult ex への ATTACH 強化）を適用。

設計文書: docs/planning/デッキ設計_ドラパルト.md（S-x/E-x/初期値表/移植ノート）
ルールタグ: R-07(配分プラン込みリーサル)/R-08/R-10(ライン最大コスト)/R-11(no_draw)/
R-15(ばら撒き先)/R-16(ボス温存)/R-18(サイド落ち推定 serial版)/R-21(先攻 div-D1)/R-22(マリガン引く)
"""

import os
import sys
from collections import defaultdict

# sys.path ブートストラップ（base import より前に必須）
try:
    _ROOT = __file__
except NameError:
    _ROOT = None
_CG_PATH = "/kaggle_simulations/agent"
for _p in ([os.path.dirname(os.path.abspath(_ROOT))] if _ROOT else []) + [_CG_PATH]:
    if _p and _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from cg.api import AreaType, CardType, LogType, OptionType, Pokemon, SelectContext

import meta_tables as mt
from policy_base import (
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    energy_count,
    get_card,
    hand_ids,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    read_deck_csv as _read_deck_csv,
)

# ── カードID（デッキ設計_ドラパルト.md のリスト） ──

DREEPY = 119            # ドラメシヤ HP70
DRAKLOAK = 120          # ドロンチ HP90（Recon Directive: 上2枚見て1枚）
DRAGAPULT_EX = 121      # ドラパルトex HP320（Phantom Dive 200+ベンチ60配分）
FEZANDIPITI_EX = 140    # Flip the Script / Cruel Arrow
LATIAS_EX = 184         # Skyliner（たねのにげる0）
BUDEW = 235             # Itchy Pollen（相手グッズロック）
MEOWTH_EX = 1071        # Last-Ditch Catch（サポートサーチ）
RARE_CANDY = 1079
UNFAIR_STAMP = 1080     # ACE SPEC
POFFIN = 1086
NIGHT_STRETCHER = 1097
CRUSHING_HAMMER = 1120
ULTRA_BALL = 1121
POKE_PAD = 1152
LUCKY_HELMET = 1156
BOSS = mt.BOSS          # 1182
CRISPIN = 1198
BROCK = 1210
LILLIE = 1227
WATCHTOWER = 1256       # ロケット団の監視塔（{C}特性消し）
FIRE_ENERGY = 2
PSYCHIC_ENERGY = 5

ATK_JET_HEADBUTT = 153      # {C} 70
ATK_PHANTOM_DIVE = 154      # {R}{P} 200 + ダメカン6個配分
ATK_ITCHY_POLLEN = 323      # Budew（相手は次の番グッズ不可）

# 相手側の特殊ID（サンプル準拠）
NO_DAMAGE_DEX = frozenset({158, 207, 330, 345})   # Drednaw/Milotic ex/Sylveon/Crustle（ex打点無効）
NO_DAMAGE_COUNTER_IDS = frozenset({28, 199, 203, 207, 362, 1136})  # ダメカン配置不可
GUARD_ENERGY_IDS = frozenset({11, 20})   # Mist / Rock Fighting（装着でダメカン配置不可）
LEGACY_ENERGY = 12
LILLIES_PEARL = 1172
LOW_VALUE_TARGETS = frozenset({173, 174, 190, 1071})  # Noctowl/Fan Rotom/Archaludon ex/Meowth ex
MUNKIDORI = 112
BONUS_COUNTER_TARGETS = frozenset({133, 351})   # Dusknoir/Rapidash（サンプル準拠の優先スナイプ）
LUMIOSE_CITY = 1267

DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})

# R-10: ライン最大コスト（技の実コストから確認済み: Phantom Dive=2 / Cruel Arrow・Eon Blade・Tuck Tail=3）
LINE_MAX_COST = {DREEPY: 2, DRAKLOAK: 2, DRAGAPULT_EX: 2,
                 FEZANDIPITI_EX: 3, LATIAS_EX: 3, MEOWTH_EX: 3, BUDEW: 0}

UNNECESSARY = -10_000_000

# デッキリスト（popular_4_dragapult.csv と同一。deck.csv 不在時のフォールバック）
DECK_FALLBACK = (
    [DREEPY] * 4 + [DRAKLOAK] * 4 + [DRAGAPULT_EX] * 3
    + [FEZANDIPITI_EX, LATIAS_EX] + [BUDEW] * 2 + [MEOWTH_EX]
    + [RARE_CANDY] * 2 + [UNFAIR_STAMP] + [POFFIN] * 4 + [NIGHT_STRETCHER] * 2
    + [CRUSHING_HAMMER] * 4 + [ULTRA_BALL] * 4 + [POKE_PAD] * 3 + [LUCKY_HELMET]
    + [BOSS] * 3 + [CRISPIN] * 4 + [BROCK] * 2 + [LILLIE] * 4 + [WATCHTOWER] * 2
    + [FIRE_ENERGY] * 4 + [PSYCHIC_ENERGY] * 4
)


def _no_damage_counter(pokemon):
    """Phantom Dive のダメカン配置を防ぐ対象（特性 or Mist/Rock Fighting エネ）。"""
    if pokemon is None:
        return True
    if pokemon.id in NO_DAMAGE_COUNTER_IDS:
        return True
    for card in (pokemon.energyCards or []):
        if card.id in GUARD_ENERGY_IDS:
            return True
    return False


class DragapultPolicy(BasePolicy):
    DECK_NAME = "dragapult"
    GO_FIRST = True            # div-D1（2026-07-08 A/B実測・R-21 更新）: 7/8フィールド（マリィ34%のアグロ
                               # 環境）では先攻のセットアップ1ターン先取りが優位。対マリィ 49.5%(220戦)→58.0%(200戦)。
                               # 旧値 False は ptcg-abc 6月メタ（Trevenant環境）の実測。上位ドラパルトピロットが
                               # エピソードに現れたら divergence で再検証（7/6 は2試合のみで YES/NO 割れ）
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】
    ATTACKER_IDS = {DRAGAPULT_EX, LATIAS_EX, FEZANDIPITI_EX}
    ENERGY_IDS = {FIRE_ENERGY, PSYCHIC_ENERGY}
    LINE_PROTECT_IDS = DRAGAPULT_LINE | {RARE_CANDY}   # R-13
    ATTACK_ENERGY_TYPE = None  # サンプル準拠: 弱点計算は使わない

    def __init__(self):
        super().__init__()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False, "can_main_attack": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []
        self._deck_cache = None

    def reset_game(self):
        super().reset_game()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False, "can_main_attack": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []

    # ═══════════════ ログ追跡（pre_ko / no_item の材料。サンプルの pre_turn_log） ═══════════════

    def track_logs(self, obs):
        for entry in obs.logs:
            self._log_buf.append(entry)
            if entry.type == LogType.TURN_END:
                self._pre_logs = self._log_buf
                self._log_buf = []
        super().track_logs(obs)   # R-17（相手最終攻撃）

    # ═══════════════ R-18: サイド落ち推定（サンプルの serial ベース簡易版） ═══════════════

    def _deck_list(self):
        if self._deck_cache is None:
            try:
                self._deck_cache = _read_deck_csv()
            except Exception:
                self._deck_cache = list(DECK_FALLBACK)
        return self._deck_cache

    def _subtract_visible(self, counts, serials, card, my_index):
        if card is None:
            return
        if isinstance(card, Pokemon) or card.playerIndex == my_index:
            if card.serial not in serials:
                counts[card.id] -= 1
                serials.add(card.serial)
        if isinstance(card, Pokemon):
            for c in (card.energyCards or []):
                self._subtract_visible(counts, serials, c, my_index)
            for c in (card.tools or []):
                self._subtract_visible(counts, serials, c, my_index)
            for c in (card.preEvolution or []):
                self._subtract_visible(counts, serials, c, my_index)

    def _visible_counts(self, obs):
        """自デッキ60枚 − 全可視ゾーン。select.deck をさらに引けばサイド集合になる。"""
        counts = defaultdict(int)
        serials = set()
        for cid in self._deck_list():
            counts[cid] += 1
        yi = obs.current.yourIndex
        ms = my_state(obs)
        for zone in (ms.hand or []), (ms.discard or []), ms.bench, ms.active:
            for card in zone:
                self._subtract_visible(counts, serials, card, yi)
        for card in obs.current.stadium:
            self._subtract_visible(counts, serials, card, yi)
        if obs.current.looking is not None:
            for card in obs.current.looking:
                self._subtract_visible(counts, serials, card, yi)
        self._subtract_visible(counts, serials, obs.select.effect, yi)
        return counts

    # ═══════════════ ターン分析（サンプル agent() 冒頭の会計を毎手番再現） ═══════════════

    def choose(self, obs):
        self.p = self._analyze(obs)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        osn = opp_state(obs)
        yi = obs.current.yourIndex

        # R-18: 山札閲覧（select.deck）が来たらサイド集合を確定
        if obs.select.deck is not None:
            counts = self._visible_counts(obs)
            for card in obs.select.deck:
                if card is not None:
                    counts[card.id] -= 1
            self._prize_ids = [cid for cid, n in counts.items() for _ in range(max(0, n))]
        deck_counts = self._visible_counts(obs)
        for cid in self._prize_ids:
            deck_counts[cid] -= 1

        fc = defaultdict(int)
        hc = defaultdict(int)
        dc = defaultdict(int)
        active_id = 0
        bench_attacker = False
        can_evolve_dreepy = False
        evolve_dreepy_count = 0
        can_evolve_drakloak = False
        for card in ms.active:
            if card is None:
                continue
            active_id = card.id
            fc[card.id] += 1
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
        for card in ms.bench:
            if card is None:
                continue
            fc[card.id] += 1
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
            if card.id == DRAGAPULT_EX and len(card.energies) >= 2:
                bench_attacker = True
        for card in (ms.discard or []):
            if card is not None:
                dc[card.id] += 1

        stadium_id = 0
        for card in obs.current.stadium:
            stadium_id = card.id

        # 前の相手番のイベント（Unfair Stamp / Fez / グッズロックの材料）
        pre_ko = False
        no_item = False
        for log in self._pre_logs:
            if log.type == LogType.ATTACK and log.attackId == ATK_ITCHY_POLLEN:
                no_item = True
            elif (log.type == LogType.MOVE_CARD and log.playerIndex == yi
                  and log.fromArea in (AreaType.BENCH, AreaType.ACTIVE)
                  and log.toArea == AreaType.DISCARD):
                pre_ko = True

        p = {
            "fc": fc, "hc": hc, "dc": dc, "deck_counts": deck_counts,
            "active_id": active_id, "bench_attacker": bench_attacker,
            "can_evolve_dreepy": can_evolve_dreepy,
            "evolve_dreepy_count": evolve_dreepy_count,
            "can_evolve_drakloak": can_evolve_drakloak,
            "main_pokemon_count": fc[DREEPY] + fc[DRAKLOAK] + fc[DRAGAPULT_EX],
            "no_more_dex": fc[DRAGAPULT_EX] * 2 >= len(osn.prize),
            "stadium_id": stadium_id,
            "prize_diff": len(ms.prize) - len(osn.prize),
            "pre_ko": pre_ko, "no_item": no_item,
            "no_draw": ms.deckCount <= 8,   # R-11（サンプル準拠の簡易閾値）
            "effect_id": obs.select.effect.id if obs.select.effect is not None else 0,
            "context_card_id": obs.select.contextCard.id if obs.select.contextCard is not None else 0,
            "support_count": 0, "hand_scores": [], "negative_hand": 0,
        }

        # MAIN でだけ: 配分プラン（DFS）+ 使うサポートの択一
        if obs.select.context == SelectContext.MAIN:
            self._main_option_proc(obs, p)
            self.use_support = 0
            if not obs.current.supporterPlayed:
                best = 0
                for o in obs.select.option:
                    if o.type != OptionType.PLAY:
                        continue
                    card = get_card(obs, AreaType.HAND, o.index, yi)
                    data = CARD_DB.get(card.id) if card is not None else None
                    if data is not None and data.cardType == CardType.SUPPORTER:
                        s = self._hand_score(obs, p, card.id, True)
                        if best < s:
                            best = s
                            self.use_support = card.id

        # 手札スコア（PLAY 採点の材料。走査しながら同名カウントを進める = サンプル準拠）
        for card in (ms.hand or []):
            s = self._hand_score(obs, p, card.id, False) if card is not None else 0
            p["hand_scores"].append(s)
            if s < 0:
                p["negative_hand"] += 1
            if card is not None:
                hc[card.id] += 1
                data = CARD_DB.get(card.id)
                if data is not None and data.cardType == CardType.SUPPORTER and card.id != BOSS:
                    p["support_count"] += 1

        p["do_switch"] = (not self.flags["can_main_attack"]
                          and (bench_attacker
                               or (active_id != BUDEW and fc[BUDEW] >= 1
                                   and obs.current.turn >= 2)))
        return p

    # ═══════════════ 配分プラン（サンプル main_option_proc の移植 = 枝刈り DFS） ═══════════════

    def _main_option_proc(self, obs, p):
        select = obs.select
        ms = my_state(obs)
        osn = opp_state(obs)
        f = self.flags
        f["can_switch"] = False
        f["can_attack"] = False
        f["can_main_attack"] = False
        for o in select.option:
            if o.type == OptionType.RETREAT:
                f["can_switch"] = True
            elif o.type == OptionType.ATTACK:
                f["can_attack"] = True
                if o.attackId == ATK_PHANTOM_DIVE:
                    f["can_main_attack"] = True

        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        if not f["can_main_attack"] and not (p["bench_attacker"] and f["can_switch"]):
            return
        if not osn.active or osn.active[0] is None:
            return

        # cards[0]=相手アクティブ, cards[1..]=相手ベンチ（インデックスは plan の座標系）
        cards = [osn.active[0]] + list(osn.bench)
        HUGE = 10 ** 9

        def counter_hp(pk):
            # ダメカン配置不可の対象は「取り切れない」扱いで DFS から除外（移植ノート1）
            if pk is None or _no_damage_counter(pk):
                return HUGE
            return pk.hp

        # DFS: 「残り60で完全に取り切れる部分集合」だけを列挙（サンプル準拠の枝刈り）
        counter_indices = []
        ci = [0]
        remain = 60
        while ci:
            index = ci[-1]
            hp = counter_hp(cards[index])
            if remain >= hp:
                counter_indices.append(ci.copy())
                if index < len(cards) - 1:
                    remain -= hp
                    ci.append(index + 1)
                    continue
            if index == len(cards) - 1:
                ci.pop()
                if ci:
                    remain += counter_hp(cards[ci[-1]])
            if ci:
                ci[-1] += 1
        counter_indices.append([])

        remain_prize = len(ms.prize)
        damage = attack_base_damage(ATK_PHANTOM_DIVE) or 200
        plan_score = 0
        for i, pokemon in enumerate(cards):
            if pokemon is None:
                continue
            base_prize = 0
            base_score = self._pokemon_score(pokemon, True)
            active_damage = 0 if pokemon.id in NO_DAMAGE_DEX else damage
            if pokemon.hp <= active_damage:
                base_prize += self._prize_count(pokemon, True)
            else:
                base_score *= active_damage / pokemon.hp
            best_ci = []
            best_prizes = base_prize
            max_score = base_score
            if remain_prize <= base_prize:
                max_score = 50000
            else:
                for indices in counter_indices:
                    if i in indices:
                        continue
                    prize = base_prize
                    score = base_score
                    for index in indices:
                        prize += self._prize_count(cards[index], False)
                        score += self._pokemon_score(cards[index], False)
                    if remain_prize <= prize:
                        score = 50000   # 取り切り = リーサルマーカー
                    else:
                        if prize >= 2:
                            if remain_prize <= 4:
                                score -= 1200   # サイド先行のペース管理（R-09 相当）
                        elif prize == 1:
                            score -= 300
                        else:
                            score += 1200       # 温存配分
                    if max_score < score:
                        max_score = score
                        best_ci = indices
                        best_prizes = prize
            if plan_score < max_score:
                plan_score = max_score
                self.plan_a = {"attack": i, "counter": list(best_ci), "prizes": best_prizes}
            if i == 0:
                # plan_b = 「アクティブを攻撃する前提」の最良（DAMAGE_COUNTER_ANY が参照）
                self.plan_b = {"attack": self.plan_a["attack"],
                               "counter": list(self.plan_a["counter"]),
                               "prizes": self.plan_a["prizes"]}

    def _prize_count(self, pokemon, is_attack_damage):
        data = CARD_DB.get(pokemon.id)
        count = 3 if (data is not None and getattr(data, "megaEx", False)) else \
            2 if (data is not None and getattr(data, "ex", False)) else 1
        if is_attack_damage:
            for card in (pokemon.energyCards or []):
                if card.id == LEGACY_ENERGY:
                    count -= 1
            for card in (pokemon.tools or []):
                if card.id == LILLIES_PEARL and data is not None and "Lillie" in data.name:
                    count -= 1
        return max(0, count)

    def _pokemon_score(self, pokemon, is_attack_damage):
        """相手ポケモンを対象に取る戦術価値（サンプル準拠のヒューリスティック）。"""
        data = CARD_DB.get(pokemon.id)
        score = self._prize_count(pokemon, is_attack_damage) * 1000
        score += len(pokemon.energies) * 150
        score += len(pokemon.tools) * 100
        if data is not None and getattr(data, "stage2", False):
            score += 250
        elif data is not None and getattr(data, "stage1", False):
            score += 130
        if pokemon.id in LOW_VALUE_TARGETS:
            score -= 200
        if pokemon.id == MUNKIDORI and len(pokemon.energies) >= 1:
            score += 300
        score += pokemon.hp
        return score

    # ═══════════════ 判定（S-0 / R-07 探索版） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場の Dragapult ex が Phantom Dive を払える（エネ2枚以上）。"""
        return any(pk.id == DRAGAPULT_EX and energy_count(pk) >= 2
                   for pk in all_my_pokemon(obs))

    def plan_attacks(self, obs):
        plans = super().plan_attacks(obs)
        for plan in plans:
            if plan.attack_id == ATK_PHANTOM_DIVE:
                plan.spread_damage = 60
        return plans

    def judge_lethal(self, obs):
        """R-07 探索版: 配分プラン（アクティブKO + counter部分集合KO）で残りサイドを
        取り切れるなら昇格。単発KO・ボス単発は base に委譲。"""
        spread = self._spread_lethal(obs)
        if spread is not None:
            return spread
        return super().judge_lethal(obs)

    def _spread_lethal(self, obs):
        plan = self.plan_a
        if plan["attack"] < 0 or plan["prizes"] < len(my_state(obs).prize):
            return None
        if not self.flags.get("can_main_attack"):
            return None   # Phantom Dive を今すぐ払えるときだけ（ベンチ経由は昇格しない）
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return None
        if plan["attack"] == 0:
            return {"route": "active", "attack_id": ATK_PHANTOM_DIVE,
                    "attacker": active, "needs_retreat": False}
        # ボスで釣り出してから取り切る計画（base apply_protocol の boss 経路に乗せる）
        if BOSS in hand_ids(obs) and not obs.current.supporterPlayed:
            osn = opp_state(obs)
            cards = ([osn.active[0]] if osn.active else [None]) + list(osn.bench)
            idx = plan["attack"]
            if idx < len(cards) and cards[idx] is not None:
                return {"route": "boss", "target": cards[idx],
                        "attack_id": ATK_PHANTOM_DIVE, "attacker": active,
                        "needs_retreat": False}
        return None

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            return self._score_promote(obs, opt)
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if obs.current.yourIndex != obs.current.firstPlayer and cid == DREEPY:
                return 100, "S-2: bench Dreepy (going second)"
            return -1, "S-2: no extra bench at setup"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_yes_no(self, obs, opt):
        # R-11: 山札が薄いときは任意ドロー特性を辞退（サンプルの no_draw をACTIVATEにも適用）
        if (obs.select.context == SelectContext.ACTIVATE and self.p.get("no_draw")
                and self.t.get("lethal") is None):
            return (1, "R-11: decline activate (deck thin)") if opt.type == OptionType.NO \
                else (0, "R-11: deck thin")
        return super().score_yes_no(obs, opt)

    # ═══════════════ 優先則（3フック。サンプルの一枚岩スコアラーを移植） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    def _score_any(self, obs, opt):
        p = self.p
        yi = obs.current.yourIndex

        if opt.type == OptionType.CARD:
            return self._score_card(obs, opt)

        if opt.type in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            # クラッシュハンマー等の相手エネ / 自分の退却コスト
            pi = opt.playerIndex if opt.playerIndex is not None else yi
            if pi != yi:
                score = 20 if opt.area == AreaType.BENCH else 10
                card = get_card(obs, opt.area, opt.index, pi)
                data = CARD_DB.get(card.id) if card is not None else None
                if data is not None and data.cardType == CardType.SPECIAL_ENERGY:
                    score += 1
                return score, "E-4: opp energy (bench first, special first)"
            return 0, "own energy (retreat cost)"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt)

        if opt.type == OptionType.ATTACH:
            card = option_card(obs, opt)
            target = option_target(obs, opt)
            if card is None or target is None:
                return 0, "attach none"
            score = self._attach_score(obs, p, card.id, target,
                                       opt.inPlayArea == AreaType.ACTIVE)
            return score, "S-5: attach"

        if opt.type == OptionType.EVOLVE:
            target = option_target(obs, opt)
            e = len(getattr(target, "energies", []) or []) if target is not None else 0
            if target is not None and target.id == DREEPY:
                # ptcg-abc 実測: EVOLVE は 30000 据え置き（上げると divergence 悪化）
                return 30000 + e, "S-3: evolve Dreepy"
            if (p["fc"][DRAGAPULT_EX] >= 2
                    or (p["fc"][DRAGAPULT_EX] == 1 and len(opp_state(obs).prize) <= 2)):
                return -1, "S-3: enough Dragapult ex"
            return 70000 + e, "S-3: evolve -> Dragapult ex"

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            if p["no_draw"]:
                return -1, "R-11: deck thin (ability)"
            if card is not None and card.id == LUMIOSE_CITY:
                return 1, "Lumiose City (low)"
            return 40000, "ability (Recon Directive etc.)"

        if opt.type == OptionType.RETREAT:
            if p["do_switch"]:
                return 10000, "retreat (bench attacker / Budew lock)"
            return -1, "no retreat"

        if opt.type == OptionType.ATTACK:
            # E-1: ワザ間の選好は attackId 準拠（Phantom Dive 154 > Jet Headbutt 153）
            return (opt.attackId or 0), "E-1: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        return 0, "fallback"

    # ── PLAY（サンプルの帯 + ptcg-abc 実測修正） ──

    def _score_play(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        cid = card.id
        hand_scores = p["hand_scores"]
        card_score = hand_scores[opt.index] if opt.index < len(hand_scores) else 0
        fc, hc, deck = p["fc"], p["hc"], p["deck_counts"]

        if cid == DREEPY:
            return 54000, "S-2: play Dreepy (ptcg-abc: 51000->54000)"
        if cid == FEZANDIPITI_EX:
            if card_score > 0:
                return 35000, "play Fez (ptcg-abc: 53000->35000)"
            return -1, "Fez: not needed"
        if cid == LATIAS_EX:
            if p["active_id"] not in (DRAKLOAK, DRAGAPULT_EX):
                return 51000, "play Latias (Skyliner)"
            return -1, "Latias: not needed"
        if cid == BUDEW:
            if fc[BUDEW] == 0 and fc[DRAGAPULT_EX] == 0:
                return 52000, "play Budew (item lock)"
            return -1, "Budew: not needed"
        if cid == MEOWTH_EX:
            if obs.current.supporterPlayed or p["stadium_id"] == WATCHTOWER:
                return -1, "Meowth: blocked"
            if p["support_count"] == 0:
                return 50000, "play Meowth ex (fetch supporter)"
            if p["support_count"] == hc[BOSS] and not self.plan_a["attack"] <= 0:
                return 50000, "play Meowth ex (fetch non-Boss)"
            return -1, "Meowth: hold"
        if cid == RARE_CANDY:
            if p["no_more_dex"]:
                return -1, "Rare Candy: enough dex"
            return 75000, "S-3: Rare Candy"
        if cid == UNFAIR_STAMP:
            return 15000, "E-5: Unfair Stamp"
        if cid == NIGHT_STRETCHER:
            if card_score >= 18000:
                return 42000, "Night Stretcher: recover"
            return -1, "Night Stretcher: nothing"
        if cid == CRUSHING_HAMMER:
            return 40000, "E-4: Crushing Hammer"
        if cid == BOSS:
            if cid == self.use_support:
                return 35000, "R-16: Boss (plan target)"
            return -1, "R-16: hold Boss"
        if cid == LILLIE:
            if cid == self.use_support:
                return 14000, "Lillie (chosen supporter)"
            return -1, "Lillie: other supporter"
        if cid == WATCHTOWER:
            if p["stadium_id"] > 0 or obs.current.turn == 1:
                return 80000, "play Watchtower"
            return -1, "Watchtower: hold"
        if p["no_draw"]:
            return -1, "R-11: deck thin (draw item/supporter)"
        if cid == POFFIN:
            if deck[DREEPY] > 0:
                return 46000, "S-2: Poffin"
            return -1, "Poffin: no target"
        if cid == ULTRA_BALL:
            if p["negative_hand"] >= 2:
                return 44000, "S-4: Ultra Ball"
            return -1, "Ultra Ball: hold"
        if cid == POKE_PAD:
            if deck[DREEPY] + deck[DRAKLOAK] > 0:
                return 45000, "S-4: Poke Pad"
            return -1, "Poke Pad: no target"
        if cid in (CRISPIN, BROCK):
            if cid == self.use_support:
                return 35000, "S-4/S-5: chosen supporter"
            return -1, "supporter: not chosen"
        return 0, "play other"

    # ── ATTACH（S-5 + R-10 + ptcg-abc 修正④） ──

    def _attach_score(self, obs, p, attach_id, pokemon, active):
        data = CARD_DB.get(attach_id)
        if data is not None and data.cardType == CardType.TOOL:
            return 60000 + (1000 if active else 0)

        # エネルギー付与
        e = len(pokemon.energies or [])
        if e >= LINE_MAX_COST.get(pokemon.id, 2):
            return -1   # R-10【ハード】: ライン最大コストを満たしたら付与禁止
        f = self.flags
        ms = my_state(obs)
        if pokemon.id == BUDEW:
            return -1
        if pokemon.id in (MEOWTH_EX, FEZANDIPITI_EX, LATIAS_EX):
            if active and not f["can_switch"] and not ms.asleep and not ms.paralyzed:
                return 22000 if (p["bench_attacker"] or p["fc"][BUDEW] >= 1) else 18000
            return -1
        if active and f["can_main_attack"]:
            return -1
        score = 20000
        if e == 1:
            if pokemon.energyCards and attach_id == pokemon.energyCards[0].id:
                return -1   # 同色2枚目は不要（Phantom Dive は {R}{P} の2色）
            if pokemon.id == DRAGAPULT_EX:
                score += 250
            elif pokemon.id == DREEPY:
                score -= 150
            else:
                score -= 200
            if active:
                score += 200
        else:   # e == 0
            if active:
                if p["bench_attacker"]:
                    score += 400
            else:
                if pokemon.id == DRAGAPULT_EX:
                    score += 150
                elif pokemon.id == DREEPY:
                    score += 100
                else:
                    score += 50
                if p["bench_attacker"]:
                    score -= 200
        if pokemon.id == DRAGAPULT_EX and e < 2:
            score += 25000   # ptcg-abc 実測修正④: Phantom Dive 起動を最速化
        if p["no_more_dex"] and pokemon.id in (DREEPY, DRAKLOAK):
            score -= 500
        return score

    # ── 手札価値（サンプル hand_score の移植。PLAY/サーチ/DISCARD の共通材料） ──

    def _hand_score(self, obs, p, cid, ignore_count):
        fc, hc, deck, dc = p["fc"], p["hc"], p["deck_counts"], p["dc"]
        f = self.flags
        osn = opp_state(obs)
        score = 0
        if cid == DREEPY:
            score = 1000 if p["main_pokemon_count"] >= 3 else 18000
        elif cid == DRAKLOAK:
            score = 20000 if p["can_evolve_dreepy"] else 3000
        elif cid == DRAGAPULT_EX:
            if p["no_more_dex"]:
                score = UNNECESSARY
            elif p["can_evolve_dreepy"] and hc[RARE_CANDY] >= 1 and not p["no_item"]:
                score = 40000
            elif p["can_evolve_drakloak"]:
                score = 30000 if fc[DRAGAPULT_EX] == 0 else \
                    10000 if fc[DRAGAPULT_EX] == 1 else 50
            else:
                score = 50 if fc[DRAGAPULT_EX] >= 2 else 2000
        elif cid == FEZANDIPITI_EX:
            if p["pre_ko"]:
                score = 15000   # ptcg-abc 実測修正②: 50000->15000
            elif p["prize_diff"] <= -2:
                score = 5
            elif len(osn.prize) == 1:
                score = UNNECESSARY
        elif cid == LATIAS_EX:
            if p["active_id"] in (FEZANDIPITI_EX, MEOWTH_EX, DREEPY):
                score = 28000 if fc[DRAKLOAK] + fc[DRAGAPULT_EX] == 0 else 15000
            else:
                score = 10
        elif cid == BUDEW:
            if fc[BUDEW] + fc[DRAKLOAK] + fc[DRAGAPULT_EX] >= 1:
                score = UNNECESSARY
            elif obs.current.turn >= 2:
                score = 30000
        elif cid == MEOWTH_EX:
            if p["support_count"] > hc[BOSS] or p["stadium_id"] == WATCHTOWER:
                score = 5
            elif obs.current.supporterPlayed:
                score = 40
            else:
                score = 35000
        elif cid == RARE_CANDY:
            if p["no_more_dex"]:
                score = UNNECESSARY
            elif p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1:
                score = 40000
        elif cid == UNFAIR_STAMP:
            if p["pre_ko"]:
                score = 80000
            elif len(osn.prize) == 1:
                score = UNNECESSARY
            else:
                score = 80
        elif cid == POFFIN:
            count = deck[DREEPY]
            if count == 0:
                score = UNNECESSARY
            else:
                if obs.current.turn <= 2 and fc[BUDEW] == 0 and deck[BUDEW] >= 1:
                    count += 1
                if count >= 2:
                    score = 35000
        elif cid == NIGHT_STRETCHER:
            for i in list(dc.keys()):
                if dc[i] >= 1:
                    data = CARD_DB.get(i)
                    if data is not None and data.cardType in (CardType.POKEMON,
                                                              CardType.BASIC_ENERGY):
                        score = max(score, self._hand_score(obs, p, i, ignore_count))
        elif cid == CRUSHING_HAMMER:
            score = 20
        elif cid == ULTRA_BALL:
            score = 70 if (p["main_pokemon_count"] <= 2 or fc[DREEPY] >= 1) else 5
        elif cid == POKE_PAD:
            score = max(self._hand_score(obs, p, DREEPY, ignore_count),
                        self._hand_score(obs, p, DRAKLOAK, ignore_count))
        elif cid == LUCKY_HELMET:
            score = 15
        elif cid == BOSS:
            if self.plan_a["attack"] > 0:
                score = 60000   # R-16: 配分プランが吊り出しを要求するときだけ
        elif cid == CRISPIN:
            if not ignore_count or p["support_count"] == 0:
                # 移植ノート3: サンプルのデッド代入を elif に解釈（山にエネ無し -> 10）
                if deck[FIRE_ENERGY] == 0 or deck[PSYCHIC_ENERGY] == 0:
                    score = 10
                elif (not f["can_main_attack"] and not p["bench_attacker"]
                        and fc[DRAGAPULT_EX] >= 1):
                    score = 55000
                else:
                    score = 25000
        elif cid == BROCK:
            if not ignore_count or p["support_count"] == 0:
                if obs.current.turn == 2 and fc[BUDEW] + fc[LATIAS_EX] == 0:
                    score = 50000
                else:
                    score = 30000
        elif cid == LILLIE:
            if not ignore_count or p["support_count"] == 0:
                score = 45000
        elif cid == WATCHTOWER:
            if p["stadium_id"] != 0 and p["stadium_id"] != WATCHTOWER:
                score = 4000
        elif cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
            if f["can_main_attack"] and (len(osn.prize) <= 2
                                         or (p["bench_attacker"] and len(osn.prize) <= 4)):
                score = UNNECESSARY
            else:
                ms = my_state(obs)
                best = -10000
                for pk in ms.active:
                    if pk is not None:
                        best = max(best, self._attach_score(obs, p, cid, pk, True))
                for pk in ms.bench:
                    if pk is not None:
                        best = max(best, self._attach_score(obs, p, cid, pk, False))
                score = best - 5000
                if f["can_main_attack"] or p["bench_attacker"]:
                    score /= 10
        if not ignore_count and hc[cid] > 0:
            if cid == DRAKLOAK and hc[cid] < p["evolve_dreepy_count"]:
                score -= 10
            elif cid == DREEPY:
                score -= 100
            else:
                score -= 100000   # 同名2枚目の価値を大きく割引（R-13 の順序側）
        return score

    # ── CARD 選択（前出し・サーチ先・配分・DISCARD 等） ──

    def _score_promote(self, obs, opt):
        """SWITCH / TO_ACTIVE / SETUP_ACTIVE の共通形（サンプルの CARD 分岐移植）。"""
        yi = obs.current.yourIndex
        ctx = obs.select.context
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        card = option_card(obs, opt)
        if card is None:
            return 0, "promote none"
        e = len(getattr(card, "energies", []) or [])
        hp = getattr(card, "hp", 0)
        if pi == yi:
            score = 0
            cid = card.id
            if cid == DREEPY:
                score += 10000
            elif cid == DRAKLOAK:
                score += 20000 if e >= 1 else -10000
            elif cid == DRAGAPULT_EX:
                score += 50000
            elif cid == BUDEW:
                if ctx != SelectContext.SWITCH:
                    score += 100000
                elif not self.p.get("bench_attacker"):
                    score += 30000
            elif cid == FEZANDIPITI_EX:
                score -= 1000
            elif cid == MEOWTH_EX:
                score -= 2000
            score += e * 1000 + hp
            return self.default_score_promote(obs, opt, score, "S-1: promote")   # R-08
        # 相手側の吊り出し（ボスの対象）: 配分プランの対象を最優先
        if self.plan_a["attack"] == opt.index + 1:
            return 100000 + e * 1000 + hp, "R-16: pull plan target"
        return e * 1000 + hp, "pull: energy/hp heuristic"

    @staticmethod
    def _take_band(score):
        """移植ノート4: TO_HAND の負スコアを (0,1) 帯へ圧縮（サーチは常に何か取る）。"""
        if score >= 0:
            return min(score, 900000)
        return (200000 + max(score, -200000)) / 200000.0

    def _score_card(self, obs, opt):
        p = self.p
        ctx = obs.select.context
        card = option_card(obs, opt)
        cid = card.id if card is not None else getattr(opt, "cardId", None)

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            return self._score_promote(obs, opt)

        if ctx in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
            if cid is None:
                return 0, "take none"
            score = self._hand_score(obs, p, cid, False)
            p["hc"][cid] += 1
            if p["effect_id"] == CRISPIN:
                # Crispin: 付けない方（手札に取る方）は逆順で選ぶ
                score = 100000 - self._hand_score(obs, p, cid, True)
            if ctx == SelectContext.TO_HAND:
                return self._take_band(score), "S-4: take to hand"
            return min(score, 900000), "S-2: take to bench"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            if cid is None:
                return 0, "discard none"
            p["hc"][cid] -= 1
            data = CARD_DB.get(cid)
            if data is not None and data.cardType == CardType.SUPPORTER:
                p["support_count"] -= 1
            score = -self._hand_score(obs, p, cid, False)
            return min(score, 900000), "R-13: discard lowest value"

        if ctx in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
            return self._score_counter(obs, opt, card, ctx)

        if ctx == SelectContext.DAMAGE:
            return self.default_score_damage_target(obs, opt)   # R-15（Cruel Arrow 等）

        return 10, "generic card"

    def _score_counter(self, obs, opt, card, ctx):
        """E-2: ダメカン配分（サンプル準拠 + 配分プラン参照）。"""
        if card is None or getattr(card, "hp", 0) <= 0:
            return 0, "counter none"
        hp = card.hp
        score = 100000 - 10 * hp + self._pokemon_score(card, False)
        if ctx == SelectContext.DAMAGE_COUNTER:
            if 210 <= hp <= 230:
                score += 20000 + hp * 20
                if opt.area == AreaType.ACTIVE:
                    score += 10000
            elif 40 <= hp <= 90:
                score += 10000 + hp * 20
            elif hp <= 30:
                score += -10000 + hp * 20
            if card.id in BONUS_COUNTER_TARGETS:
                score += 30000
            return score, "E-2: counter (zone heuristic)"
        # DAMAGE_COUNTER_ANY = Phantom Dive の6個配分（座標系: cards[bench_index + 1]）
        if opt.index + 1 in self.plan_b["counter"]:
            score += 100000
            reason = "E-2: plan counter target"
        else:
            remain = (obs.select.remainDamageCounter or 0) * 10
            if 210 <= hp <= 200 + remain:
                score += 30000
            elif 20 <= hp <= 60 + remain:
                score += 10000
            elif hp == 10:
                score -= 100000
            reason = "E-2/R-15: spread heuristic"
        if _no_damage_counter(card):
            return -1, "E-2: no-damage-counter guard"
        return score, reason


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」を呼ぶ。
# def agent は必ずファイル末尾の callable にする。

_impl = make_agent(DragapultPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
