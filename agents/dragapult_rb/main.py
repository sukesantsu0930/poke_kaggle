"""ドラパルトex（Dragapult ex / Phantom Dive ばら撒き）ルールベースエージェント — 公式サンプル移植

土台: Kaggle 公式サンプル "A Sample Rule-Based Agent (Dragapult ex Deck)"（Apache-2.0 系譜。
research/external/kaggle_notebooks/a-sample-rule-based-agent-dragapult-ex-deck/main_reference.py）。
その方策の核 = `main_option_proc` の配分プラン DFS（「60 で取り切れる相手部分集合」だけを列挙する
枝刈り + prize_count/pokemon_score によるサイドペース採点）を BasePolicy のフックに移植し、
ptcg-abc の divergence 実測修正（Fez 降格 / EVOLVE 据え置き / Dragapult ex への ATTACH 強化）を適用。

設計文書: docs/planning/デッキ設計_ドラパルト.md（S-x/E-x/初期値表/移植ノート）
ルールタグ: R-07(配分プラン込みリーサル)/R-08/R-10(ライン最大コスト)/R-11(no_draw)/
R-15(ばら撒き先)/R-16(ボス温存)/R-18(サイド落ち推定 serial版)/R-21(先攻 div-D1)/R-22(マリガン引く)/
R-30(バトル場が今すぐ撃てるならバトル場優先＝資源節約)
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

# アタッカー運用ポケモン（S-7 配分探索用。research/meta/attacker_pokemon.md、
# extract_attacker_pokemon.py が 1761 エピソードから抽出。アタッカー度 = active滞在中に
# ATTACK宣言した試合率、閾値0.5で2値化。HP>120 のみ = 小粒は配分探索でHP判定するため不要）。
# 履歴だけでは Mega Kangaskhan ex(756) が 0.49 で漏れるため、_is_attacker では megaEx 属性を
# 無条件アタッカーとして OR する（メガ進化は定義上メインアタッカー）。
ATTACKER_IDS_LEARNED = frozenset({58, 63, 96, 108, 116, 117, 121, 169, 190, 245, 272,
                                  381, 401, 431, 648, 666, 674, 678, 743, 849, 861, 1031})

DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})

# DRA_CONCENTRATE（2026-07-24 ユーザー指示）: エネ集中の A/B トグル（既定 ON）
DRA_CONCENTRATE = os.environ.get("DRA_CONCENTRATE", "1") != "0"
# 「この番はまだドラパルト化が確定不可能ではない」判定に使う掘り札（ドロー/サーチ手段）。
# 手札にこれらが1枚でもあれば、ドラパルトを引き込む余地がある = エネ分散はまだ許可しない
DIG_OUT_IDS = frozenset({ULTRA_BALL, POKE_PAD, LILLIE, CRISPIN, BROCK, NIGHT_STRETCHER})

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


# ── S-7: 進化前提の最終形（evolvesFrom はカード名。generic_policy.py L299 と同じ規約） ──

_CHILDREN_MAP = None


def _children_map():
    """親カード名 → その名から進化する子カードのリスト（全カード固定なので1回だけ構築）。"""
    global _CHILDREN_MAP
    if _CHILDREN_MAP is None:
        _CHILDREN_MAP = defaultdict(list)
        for c in CARD_DB.values():
            ef = getattr(c, "evolvesFrom", None)
            if ef:
                _CHILDREN_MAP[ef].append(c)
    return _CHILDREN_MAP


def _final_form(card):
    """進化前提の最終形カードを返す（分岐は最大HPを取る。楽観仮定＝相手は進化する）。"""
    if card is None:
        return None
    cur = card
    seen = set()
    while getattr(cur, "cardId", None) not in seen:
        seen.add(cur.cardId)
        kids = _children_map().get(getattr(cur, "name", None), [])
        if not kids:
            break
        cur = max(kids, key=lambda k: getattr(k, "hp", 0) or 0)
    return cur


def _is_attacker(card):
    """アタッカー運用されるか（履歴テーブル OR megaEx 属性）。card は静的カードデータ。"""
    if card is None:
        return False
    return card.cardId in ATTACKER_IDS_LEARNED or getattr(card, "megaEx", False)


def _final_prize(card):
    """最終形のサイド数（進化前提）。megaEx=3 / ex=2 / その他=1。"""
    if card is None:
        return 1
    if getattr(card, "megaEx", False):
        return 3
    if getattr(card, "ex", False):
        return 2
    return 1


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
    # S-7【2026-07-13 採用】: Phantom Dive ばら撒き60 の配分を「最小攻撃回数でサイド取り切り」
    # の探索（_plan_spread）に委ねる。HPは現物・進化前提はアタッカー役割判定のみ（進化前提を
    # 全HPに適用した版は制圧度非改善で棄却）。gauntlet 80戦で旧配分 52.9% → 56.7%（+3.8pt、
    # 主因 marnie +11.3pt=120戦で+7.5pt確認）。既定 True。DRAGA_SPREAD=0 で旧配分に戻せる
    # （garchomp -12.5pt の比較調査用に旧ヒューリスティックを一旦残置）。
    USE_SPREAD_SEARCH = os.environ.get("DRAGA_SPREAD", "1") != "0"
    # ターン内探索（TurnSearcher）の時間予算。検証で gauntlet を回すため環境変数で短縮可能。
    # 探索の有効化自体は gauntlet --search rollout（search_enabled 注入）で行う。
    SEARCH_TIME_PER_DECISION = float(os.environ.get("DRAGA_SEARCH_TIME", "1.0"))

    def __init__(self):
        super().__init__()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False,
                      "can_main_attack": False, "active_route": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []
        self._deck_cache = None
        self.spread_plan = None

    def reset_game(self):
        super().reset_game()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False,
                      "can_main_attack": False, "active_route": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []
        self.spread_plan = None

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

        # S-7: ばら撒き配分の探索計画。DAMAGE_COUNTER_ANY の連続選択中は開始時点で1回だけ計算し
        # キャッシュ（目標残りHPは絶対値なので配置が進んでも不変。ここで毎回引き直すと現hpの
        # 減少でドリフトする）。他 context に移ったら破棄して次の攻撃で再計算。
        if self.USE_SPREAD_SEARCH and obs.select.context == SelectContext.DAMAGE_COUNTER_ANY:
            if self.spread_plan is None:
                self.spread_plan = self._plan_spread(obs)
        else:
            self.spread_plan = None

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
                          and not self.flags["active_route"]   # R-30: バトル場で撃てるなら退却しない
                          and (bench_attacker
                               or (active_id != BUDEW and fc[BUDEW] >= 1
                                   and obs.current.turn >= 2)))
        return p

    # ═══════════════ R-30: バトル場から今すぐ Phantom Dive を撃てるか（手番内ルート検証） ═══════════════

    def _active_dive_route(self, obs):
        """R-30【ハード・ユーザー決定 2026-07-15】: バトル場のポケモンが退却なしで
        この番 Phantom Dive を撃てるルートがあるか。考慮する手 = 場の Drakloak の進化
        （EVOLVE オプションの実在で合法性確認）+ 手張り1回（ATTACH オプションで確認。
        R-10 の上限があるため e<2 のときだけ）。Dreepy+アメ直行はアメの付け先選択を
        このフラグから保証できないため対象外（従来挙動に委ねる）。
        True のとき: EVOLVE はバトル場優先（ベンチ進化→退却=エネ破棄のルートを封じる）、
        do_switch を抑制。"""
        ms = my_state(obs)
        if ms.asleep or ms.paralyzed:
            return False
        active = active_pokemon(obs)
        if active is None:
            return False
        if active.id == DRAKLOAK:
            if not any(o.type == OptionType.EVOLVE and o.inPlayArea == AreaType.ACTIVE
                       for o in obs.select.option):
                return False
        elif active.id != DRAGAPULT_EX:
            return False
        ids = [c.id for c in (active.energyCards or [])]
        need = [color for color in (FIRE_ENERGY, PSYCHIC_ENERGY) if color not in ids]
        if not need:
            return True
        if len(need) > 1 or len(ids) >= 2:
            return False   # 手張り1回では {R}{P} が揃わない / R-10 上限で張れない
        for o in obs.select.option:
            if o.type != OptionType.ATTACH or o.inPlayArea != AreaType.ACTIVE:
                continue
            card = option_card(obs, o)
            if card is not None and card.id == need[0]:
                return True
        return False

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
        f["active_route"] = self._active_dive_route(obs)

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

    # ═══════════════ S-7: ばら撒き60 の配分探索（最小攻撃回数でサイド取り切り） ═══════════════

    def _bench_targets(self, obs):
        """相手ベンチを (coord, 現物残HP, need, サイド, アタッカー) に抽象化。
        coord = ベンチindex+1（plan_b['counter'] / _score_counter の座標系に一致）。
        取り切りは現物HP（今の盤面で削る対象。進化前に潰す＝現在HP版で実証済み・制圧度+3.8pt）。
        進化前提は「アタッカーか＝将来正面に来るか」の役割判定にのみ使う（HPには使わない）。
        （進化する/しないを p_evo で重み合成する進化分岐版は gauntlet 80戦 56.0% で現在HP版 56.7%
        を上回れず棄却。garchomp +10pt だが marnie -5pt で相殺。2026-07-14）"""
        osn = opp_state(obs)
        out = []
        for j, pk in enumerate(osn.bench):
            if pk is None:
                continue
            if _no_damage_counter(pk):
                continue   # ダメカン配置不可（特性 / Mist・Rock Fighting）
            static = CARD_DB.get(pk.id) or pk
            ff = _final_form(static)
            remain = max(10, pk.hp)                        # 現物の残HP（今削る対象）
            need = -(-remain // 10)                        # ceil(remain/10) = KOに要る個数
            out.append({
                "coord": j + 1, "remain": remain, "need": need,
                "prize": self._prize_count(pk, False),     # 現物のサイド
                "attacker": _is_attacker(ff),              # 役割のみ進化前提
            })
        return out

    def _plan_spread(self, obs):
        """ばら撒き6個の配分を {coord: 目標残りHP} で返す（USE_SPREAD_SEARCH 時に _score_counter が参照）。
        方針: ①ばら撒きで取り切れるベンチ集合をサイド最大で確保（無駄なく分割）→
        ②余った個を、次サイクルで取り切りに最も近づく1体へ布石（A=置物のベンチKO /
        B=アタッカーを正面200圏に押し込み）。相手は静止＋進化前提の楽観。"""
        targets = self._bench_targets(obs)
        target_hp = {}
        if not targets:
            return target_hp

        # ① 6個以内で取り切れるベンチ部分集合をサイド最大で選ぶ（ベンチ数は小さいので全列挙）
        best_subset, best_key = [], (-1, 0)
        n = len(targets)
        for mask in range(1 << n):
            used, prize, ok = 0, 0, True
            for i in range(n):
                if mask & (1 << i):
                    used += targets[i]["need"]
                    prize += targets[i]["prize"]
                    if used > 6:
                        ok = False
                        break
            if ok and used <= 6:
                key = (prize, -used)   # サイド最大 → 同点は消費個数最小
                if key > best_key:
                    best_key, best_subset = key, [i for i in range(n) if mask & (1 << i)]
        chosen = set(best_subset)
        used = sum(targets[i]["need"] for i in chosen)
        for i in chosen:
            target_hp[targets[i]["coord"]] = 0   # 取り切り

        # ② 余りを1体へ布石（A=置物のベンチKO / B=アタッカーを正面200圏へ押し込み）
        leftover = 6 - used
        if leftover > 0:
            best_i, best_val = None, -10 ** 9
            for i in range(n):
                if i in chosen:
                    continue
                t = targets[i]
                after = t["remain"] - leftover * 10
                if t["attacker"]:
                    if after <= 200:
                        val = t["prize"] * 1000 + 500      # 1発で正面200圏（B・優）
                    elif t["remain"] <= 320:
                        val = t["prize"] * 1000 + 200      # 2発で正面圏へ chip（B）
                    else:
                        val = t["prize"] * 1000 - 100      # 大型・非効率
                else:
                    need_after = -(-max(0, after) // 10)
                    if need_after <= 6:
                        val = t["prize"] * 1000 + 400      # 次1サイクルでベンチKO（A・2発圏）
                    else:
                        val = t["prize"] * 1000 - 200      # 遠い置物
                val -= t["remain"] * 0.1                   # 近いほど良い（tiebreak）
                if val > best_val:
                    best_val, best_i = val, i
            if best_i is not None:
                t = targets[best_i]
                target_hp[t["coord"]] = max(0, t["remain"] - leftover * 10)
        return target_hp

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
                # div-D3（2026-07-11 実測 07-07/07-08/07-09。旧: ptcg-abc 6月実測で 30000 据え置き）:
                # 7月上位ピロット（1080/1053）は Dreepy→Drakloak 進化をターン冒頭に行う
                # （進化したての Drakloak も同ターン Recon Directive を使えるため）。
                # precedence 実測（07-08, 32試合）: evo_drak が ability より先 228/84、
                # ハンマーより先 44/22、ポケパッドより先 55/29、Dreepy 展開より先 24/4。
                return 58000 + e, "div-D3: evolve Dreepy first"
            # R-30【ハード・ユーザー決定 2026-07-15】: バトル場の Drakloak を進化させれば
            # この番 Phantom Dive が撃てる（{R}{P} が場+手張り1回で揃う）なら、ベンチ進化→
            # 退却（エネ1枚破棄）より優先。div-D4（2体目温存）も「今すぐ撃てる」時は上書き。
            # 起点の観測: 両ドロンチにエネ1の盤面で 48000+e が同点 → インデックス順でベンチが
            # 進化し、退却でバトル場のエネを捨てていた（資源損）。
            if (opt.inPlayArea == AreaType.ACTIVE
                    and target is not None and target.id == DRAKLOAK
                    and self.flags.get("active_route")):
                return 48600 + e, "R-30: evolve active -> Phantom Dive this turn"
            if p["fc"][DRAGAPULT_EX] >= 1:
                # div-D4（2026-07-11 実測 07-08）: human の evolve->Dragapult 65回/32試合 ≒
                # 初回+KO後の補充のみ。「場に1体いる間は2体目に進化しない」（Drakloak を
                # Recon ドローエンジンとして温存 + ボス2枚取りの的を増やさない）。
                # 我々の evolve 選択のうち human が同ターン内に一度も行わなかったもの 110件。
                # 旧条件（fc>=2 or fc==1&&残りサイド<=2 で -1）を fc>=1 に拡大【ソフト・暫定】。
                return -1, "div-D4: hold 2nd Dragapult ex"
            # div-D4 順序側: 70000（アメ 75000 の直下）→ 48000。ability(56000) の後・
            # attach(<=45450) の前に進化する（precedence: ability が先 139/31 / attach より先 39/24。
            # Drakloak の Recon を使ってから進化しないと特性が無駄になる）。
            return 48000 + e, "S-3: evolve -> Dragapult ex"

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            if p["no_draw"]:
                return -1, "R-11: deck thin (ability)"
            if card is not None and card.id == LUMIOSE_CITY:
                return 1, "Lumiose City (low)"
            # div-D3（2026-07-11 実測 07-08）: Recon Directive はグッズ・エネ付けより先。
            # precedence: ability が attach より先 266/97、ハンマーより先 110/31、
            # ポケパッドより先 103/38、ハイパーボールより先 44/13、進化(Dragapult)より先 139/31。
            # 40000 → 56000（evo_drak 58000 の下・Dreepy 展開 54000 の上）。
            return 56000, "ability (Recon Directive etc.)"

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
            if (self.flags["active_route"] and p["active_id"] == DRAKLOAK
                    and hc[DRAGAPULT_EX] <= 1):
                # R-30: 手札のドラパルトが最後の1枚 → アメで別の Dreepy に進化させると
                # バトル場の「この番撃てる」ルートが消える。直接進化で済ませアメも温存。
                return -1, "R-30: hold candy (evolve active directly)"
            return 75000, "S-3: Rare Candy"
        if cid == UNFAIR_STAMP:
            # div-D8（2026-07-11 実測 07-08）: human はスタンプを Recon 特性より先に打つ
            # （precedence 34/18。相手の手札干渉+自分5ドローを先に済ませてから山を掘る）。
            # 15000 → 57000（evo_drak 58000 の下・ability 56000 の上）。
            # ハンマー→スタンプの precedence 8/4 とは非推移だが n=12 と薄く、34/18 を優先。
            return 57000, "E-5: Unfair Stamp"
        if cid == NIGHT_STRETCHER:
            if card_score >= 18000:
                return 42000, "Night Stretcher: recover"
            return -1, "Night Stretcher: nothing"
        if cid == CRUSHING_HAMMER:
            # div-D5（2026-07-11 実測 07-08。設計md 未決事項1の解消）: 40000 は毎ターン
            # 最優先グッズ級で過大。human は特性/進化/エネ付け/夜のタンカ/サポートの後に打つ
            # （precedence: attach が先 53/5、ability が先 110/31、night が先 16/4、
            # サポートが先 5/0。我々のハンマー選択のうち human 不実行 52件）。
            # 40000 → 17000（attach 帯 18000-45450 の下・Unfair Stamp 15000 の上。
            # ハンマー→スタンプの順は precedence 8/4）。
            return 17000, "E-4: Crushing Hammer"
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
        # div-D6（2026-07-11 実測 07-08）: リスト外カード（上位ピロットの変種デッキを
        # リプレイするときだけ発生。自デッキ60枚は全て上の分岐で採点済み）が 0 だと
        # END(0) と同点でインデックス順により先に選ばれていた（human=END / ours=PLAY/
        # Jamming Tower 等）。END より下げ「知らないカードは切らずにターンを終える」に揃える。
        return -0.5, "div-D6: unknown card (below END)"

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
        # DRA_CONCENTRATE（2026-07-24 ユーザー指示）: 常にファントムダイブ（{R}{P}×2）を
        # 狙う — 充電途中（e==1）のライン個体がいる間、別個体（e==0）への新規付与 =
        # **エネ分散を禁止**する。分散を許可するのは「この番のドラパルト化が確定不可能」
        # な時だけ: 手札にドラパルト無し ∧ 掘り札（DIG_OUT_IDS）も無し。リーリエ等が
        # 残っている手札はまだ確定しない（ユーザー観測の事故: 炎1のドロンチを横目に
        # 別ドロンチへ手張り = 従来は e==0 の +120 が e==1 継続の −120 に勝っていた）。
        # 場のドラパルト ex 本体への付与は常に「ダイブ狙い」なので対象外。
        if (DRA_CONCENTRATE and e == 0 and pokemon.id != DRAGAPULT_EX):
            charged = any(
                pk is not pokemon and pk.id in DRAGAPULT_LINE
                and len(pk.energies or []) == 1
                for pk in all_my_pokemon(obs))
            if charged:
                hc = p["hc"]
                not_final = (hc[DRAGAPULT_EX] >= 1
                             or any(hc[c] >= 1 for c in DIG_OUT_IDS))
                if not_final:
                    return -1   # 分散禁止（集中先が生きている間は手張りを温存してよい）
        score = 20000
        if e == 1:
            if pokemon.energyCards and attach_id == pokemon.energyCards[0].id:
                return -1   # 同色2枚目は不要（Phantom Dive は {R}{P} の2色）
            if pokemon.id == DRAGAPULT_EX:
                score += 250
            elif pokemon.id == DRAKLOAK:
                score -= 120   # div-D7: Drakloak > Dreepy（下記）
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
                elif pokemon.id == DRAKLOAK:
                    # div-D7（2026-07-11 実測 07-06/07-07/07-08/07-09 全日）: human の
                    # エネ手張り先は Drakloak > Dreepy（次ターン Dragapult ex になる個体へ
                    # 先行チャージ。human=ATTACH->Drakloak / ours=->Dreepy が4日間同方向）。
                    # 旧: Drakloak は else 束(+50) で Dreepy(+100) より下だった。
                    score += 120
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

    def _best_attach(self, obs, p, attach_id):
        """S-6: attach_id を場に付けるときの最良 S-5 価値（付け先だけ最適化した値）。"""
        ms = my_state(obs)
        best = -10000
        for pk in ms.active:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, True))
        for pk in ms.bench:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, False))
        return best

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
                score = self._best_attach(obs, p, cid) - 5000
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
                if cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
                    # S-6a（2026-07-13 リプレイ84790412）: 手札に取らなかった色（逆色）が
                    # 場に付く。逆色の最良付け先価値（S-5）が高い方を選ぶ。
                    # 逆色が山に残らない色を取ると付与自体が消滅するため降格。
                    other = PSYCHIC_ENERGY if cid == FIRE_ENERGY else FIRE_ENERGY
                    other_left = sum(1 for c in (obs.select.deck or [])
                                     if c is not None and c.id == other)
                    if other_left > 0:
                        score = 100000 + self._best_attach(obs, p, other)
                    else:
                        score = 50
                else:
                    # 変種デッキのリプレイ用フォールバック（旧: 逆順選択）
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

        if ctx == SelectContext.ATTACH_TO:
            # S-6b（2026-07-13）: アカマツ等「山から付けるエネ」の選択。自デッキの2色構成では
            # 常に同色のみが候補になるが、S-5 の最良付け先価値で採点しておく（変種リプレイの保険）
            if cid is None:
                return 0, "attach none"
            return self._take_band(self._best_attach(obs, p, cid)), "S-6b: attach energy pick"

        if ctx == SelectContext.ATTACH_FROM:
            # div-D2（2026-07-11 実測 06-30/07-06/07-07/07-08/07-09 全日）: Crispin 等の
            # 「付け先ポケモン選択」が未実装で全候補 10 の同点 → インデックス順になり
            # 一致 0/7(07-07)・7/27(07-08)・0/2(07-09) だった。S-5 の attach 採点に接続。
            # S-6c（2026-07-13）: contextCard に付けるカードが入る（Crispin ならエネの色が判明）
            # ため attach_id に実IDを渡す（旧: 0 固定）。同色2枚目回避 = {R}{P} 成立が効く。
            # （R-10 / Budew 除外は従来どおり。負値は TO_HAND と同じ (0,1) 帯圧縮で
            # 「必ずどれかを選ぶ」を保つ）。
            aid = p["context_card_id"]
            adata = CARD_DB.get(aid)
            if adata is None or adata.cardType not in (CardType.BASIC_ENERGY,
                                                       CardType.TOOL):
                aid = 0
            if card is not None and isinstance(card, Pokemon):
                score = self._attach_score(obs, p, aid, card,
                                           opt.area == AreaType.ACTIVE)
                return self._take_band(score), "div-D2/S-6c: attach target (S-5)"
            return 0, "div-D2: attach target none"

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
        if _no_damage_counter(card):
            return -1, "E-2: no-damage-counter guard"
        # DAMAGE_COUNTER_ANY = Phantom Dive の6個配分（座標系: cards[bench_index + 1]）
        if self.USE_SPREAD_SEARCH and self.spread_plan is not None:
            # S-7: 探索計画の「目標残りHP」まで削る。現hp が目標より上なら置く価値
            #（差が大きいほど優先）。目標に達したベンチは 0 帯へ落として次のベンチへ回す。
            tgt = self.spread_plan.get(opt.index + 1)
            if tgt is not None and hp > tgt:
                return score + 100000 + (hp - tgt), "S-7: spread plan target"
            return score, "S-7: spread plan (satisfied/other)"
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
        return score, reason


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」を呼ぶ。
# def agent は必ずファイル末尾の callable にする。

_impl = make_agent(DragapultPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
