"""ドラパルトヨノワール（Dragapult ex + Dusknoir カーズドボム）ルールベースエージェント

土台: agents/dragapult_rb（公式サンプル移植 + div-D2〜D8 + S-7 ばら撒き配分探索）。
新デッキ = ユーザー持参の紙トーナメント実績リスト（decks/candidates/dragapult_dusknoir_paper.csv）。
ラダーに同型 0 件（1761 エピソード採掘）のため divergence 模倣は使えず、ユーザー決定ルールで作る。

設計文書: docs/planning/デッキ設計_ドラパルトヨノワール.md（ユーザー決定ルール 1〜7）
  1. カーズドボムは「KO を取り切れる時だけ」爆発【ハード】（①130単体 ②正面200合算 ③ばら撒き60合算）
  2. 悪エネはマシマシラ専用（貼る先）。再利用可能資源【ソフト】
  3. メイのはげまし = 「使えばドラパルトが技を打てる」局面でリーリエ超え【ソフト・条件付き】
  4. アカマツはドラパルトライン優先、余裕時のみマシマシラ【ソフト】
  5. Risky Ruins は攻撃の直前に張る【ソフト（順序）】
  6. ヒカリ: 基本リーリエ未満。「この番ファントムダイブが打てる ∧ 手札にエネあり」でリーリエ超え【ソフト】
  7. 偵察指令 = 不確定ドロー先・確定サーチ後。ポフィン →（リーリエ）→ 偵察指令 → ポケパッド【ソフト（順序）】

ルールタグ: R-07/R-08/R-10/R-11/R-13/R-15/R-16/R-18/R-21(先攻・旧型 div-D1 継承【暫定】)/R-22/R-26/R-28
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
    LETHAL_BAND,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    damage_on,
    energy_count,
    get_card,
    hand_ids,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    read_deck_csv as _read_deck_csv,
    retreat_cost,
)

# ── カードID（デッキ設計_ドラパルトヨノワール.md のリスト） ──

DREEPY = 119            # ドラメシヤ HP70
DRAKLOAK = 120          # ドロンチ HP90（Recon Directive: 上2枚見て1枚）
DRAGAPULT_EX = 121      # ドラパルトex HP320（Phantom Dive 200+ベンチ60配分）
DUSKULL = 131           # ヨマワル HP60
DUSCLOPS = 132          # サマヨール HP90（Cursed Blast: 5個=50 置いて自壊）
DUSKNOIR = 133          # ヨノワール HP160（Cursed Blast: 13個=130 置いて自壊）
MUNKIDORI = 112         # マシマシラ HP110（Adrena-Brain: 悪エネ付きで毎ターン3個移動）
FEZANDIPITI_EX = 140    # Flip the Script / Cruel Arrow
BUDEW = 235             # Itchy Pollen（相手グッズロック）
MEOWTH_EX = 1071        # Last-Ditch Catch（サポートサーチ）
RARE_CANDY = 1079
UNFAIR_STAMP = 1080     # ACE SPEC
POFFIN = 1086
NIGHT_STRETCHER = 1097
ULTRA_BALL = 1121
POKE_PAD = 1152
BOSS = mt.BOSS          # 1182
CRISPIN = 1198          # アカマツ
LILLIE = 1227           # リーリエの決心（手札を山へ戻して6ドロー）
DAWN = 1231             # ヒカリ（たね+1進化+2進化サーチ）
ROSA = 1240             # メイのはげまし（サイド負け時のみ・トラッシュから基本エネ2枚を2進化へ）
WATCHTOWER = 1256       # ロケット団の監視塔（{C}特性消し）
RISKY_RUINS = 1260      # 非{D}たねのベンチ着地に2個
FIRE_ENERGY = 2
PSYCHIC_ENERGY = 5
DARK_ENERGY = 7

BASIC_ENERGIES = (FIRE_ENERGY, PSYCHIC_ENERGY, DARK_ENERGY)

ATK_JET_HEADBUTT = 153      # {C} 70
ATK_PHANTOM_DIVE = 154      # {R}{P} 200 + ダメカン6個配分
ATK_ITCHY_POLLEN = 323      # Budew（相手は次の番グッズ不可）

# 相手側の特殊ID（dragapult_rb 準拠）
NO_DAMAGE_DEX = frozenset({158, 207, 330, 345})   # Drednaw/Milotic ex/Sylveon/Crustle（ex打点無効）
NO_DAMAGE_COUNTER_IDS = frozenset({28, 199, 203, 207, 362, 1136})  # ダメカン配置不可
GUARD_ENERGY_IDS = frozenset({11, 20})   # Mist / Rock Fighting（装着でダメカン配置不可）
LEGACY_ENERGY = 12
LILLIES_PEARL = 1172
LOW_VALUE_TARGETS = frozenset({173, 174, 190, 1071})  # Noctowl/Fan Rotom/Archaludon ex/Meowth ex
BONUS_COUNTER_TARGETS = frozenset({133, 351})   # 相手の Dusknoir/Rapidash（優先スナイプ）
LUMIOSE_CITY = 1267

# アタッカー運用ポケモン（S-7 配分探索用。research/meta/attacker_pokemon.md）
ATTACKER_IDS_LEARNED = frozenset({58, 63, 96, 108, 116, 117, 121, 169, 190, 245, 272,
                                  381, 401, 431, 648, 666, 674, 678, 743, 849, 861, 1031})

DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})
DUSKNOIR_LINE = frozenset({DUSKULL, DUSCLOPS, DUSKNOIR})

# R-10: ライン最大コスト。ボムライン=0（自壊要員にエネは張らない）【ハード】、
# マシマシラ=1（アドレナブレイン起動の悪エネ1枚のみ。ユーザールール2）【ハード】
LINE_MAX_COST = {DREEPY: 2, DRAKLOAK: 2, DRAGAPULT_EX: 2,
                 FEZANDIPITI_EX: 3, MEOWTH_EX: 3, BUDEW: 0,
                 MUNKIDORI: 1, DUSKULL: 0, DUSCLOPS: 0, DUSKNOIR: 0}

UNNECESSARY = -10_000_000

# ── 第3弾（2026-07-25 ユーザー観察ドクトリン。判定 = 全対面 A/B・最悪対面
#    marnie(10%)/archaludon(20%) を主計器に160戦確定。通常版は不可侵） ──
# 【160戦A/B結果】4件一括ONは非加算の悪相互作用で最悪対面 marnie −5.0（13.8 vs 18.8）と
# 崩壊。二分探索で切り分け: OPEN_BUDEW 単独は marnie 床 +5.0（18.8→23.8・均等ほぼ横ばい）の
# 明確な当たり = 既定 ON。MUNKI_LATE（marnie −2.6）と PAD（−0.7）は pool で報われず既定 OFF
# （ユーザードクトリンとして温存 = トグルで観察・ラダー検証可。generic 相手のプールは
#  「マシマシラ温存」の価値を測れていない可能性 → 実戦観察で再評価）。
DUSK_OPEN_BUDEW = os.environ.get("DUSK_OPEN_BUDEW", "1") != "0"      # 序盤 Poffin で Dreepy+Budew（T1 も）採用
DUSK_MUNKI_LATE = os.environ.get("DUSK_MUNKI_LATE", "0") != "0"      # マシマシラ終盤/余裕時のみ（温存OFF）
DUSK_PAD_DRAKLOAK = os.environ.get("DUSK_PAD_DRAKLOAK", "0") != "0"  # Pad→Drakloak 優先（温存OFF）
# 場のドラパルト線 max 3 は既存の main_pokemon_count>=3 ゲート（_hand_score DREEPY）で
# 既に成立（ユーザー「max 3匹でいい」と一致）。トグル不要 = 現状維持。

# デッキリスト（dragapult_dusknoir_paper.csv と同一。deck.csv 不在時のフォールバック）
DECK_FALLBACK = (
    [DREEPY] * 4 + [DRAKLOAK] * 4 + [DRAGAPULT_EX] * 3
    + [DUSKULL] * 2 + [DUSCLOPS] * 2 + [DUSKNOIR] * 2
    + [FEZANDIPITI_EX, MUNKIDORI, MEOWTH_EX, BUDEW]
    + [POFFIN] * 4 + [POKE_PAD] * 4 + [ULTRA_BALL] * 4 + [RARE_CANDY] * 3
    + [NIGHT_STRETCHER] * 2 + [UNFAIR_STAMP]
    + [LILLIE] * 4 + [BOSS] * 3 + [CRISPIN] * 2 + [DAWN, ROSA]
    + [WATCHTOWER, RISKY_RUINS]
    + [FIRE_ENERGY] * 3 + [PSYCHIC_ENERGY] * 3 + [DARK_ENERGY] * 2
)


def _counter_blocked_by_body(pokemon):
    """本体特性でダメカン配置を防ぐ対象（ボム・アドレナ等の特性由来にも効く想定）。"""
    if pokemon is None:
        return True
    return pokemon.id in NO_DAMAGE_COUNTER_IDS


def _no_damage_counter(pokemon):
    """ワザの効果によるダメカン配置（ばら撒き）を防ぐ対象。
    ルール9（2026-07-14 ユーザー）: ミスト装着体をばら撒きで指定しない【ハード】。
    Mist/Rock Fighting のテキストは「相手のワザの効果を防ぐ（Damage is not an effect）」
    — 特性（カーズドボム/アドレナブレイン）は防がれない点に注意（ガードを分離する理由）。
    Rock Fighting の防御は {F} ポケモンに付いている時だけ。"""
    if _counter_blocked_by_body(pokemon):
        return True
    for card in (pokemon.energyCards or []):
        if card.id == 11:      # Mist Energy
            return True
        if card.id == 20:      # Rock Fighting Energy（{F} 装着時のみ防御）
            data = CARD_DB.get(pokemon.id)
            if data is not None and getattr(data, "energyType", None) == 6:
                return True
    return False


# ── S-7: 進化前提の最終形（役割判定のみ。HP は現物） ──

_CHILDREN_MAP = None


def _children_map():
    global _CHILDREN_MAP
    if _CHILDREN_MAP is None:
        _CHILDREN_MAP = defaultdict(list)
        for c in CARD_DB.values():
            ef = getattr(c, "evolvesFrom", None)
            if ef:
                _CHILDREN_MAP[ef].append(c)
    return _CHILDREN_MAP


def _final_form(card):
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
    if card is None:
        return False
    return card.cardId in ATTACKER_IDS_LEARNED or getattr(card, "megaEx", False)


class DragapultDusknoirPolicy(BasePolicy):
    DECK_NAME = "dragapult_dusknoir"
    GO_FIRST = True            # R-21【暫定】: 旧型 dragapult_rb の div-D1（先攻優位の A/B 実測）を継承。
                               # 同型のラダー実測 0 件のため gauntlet で再検証する。
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定】
    ATTACKER_IDS = {DRAGAPULT_EX, FEZANDIPITI_EX}
    ENERGY_IDS = {FIRE_ENERGY, PSYCHIC_ENERGY, DARK_ENERGY}
    LINE_PROTECT_IDS = DRAGAPULT_LINE | {RARE_CANDY}   # R-13
    ATTACK_ENERGY_TYPE = None
    USE_SPREAD_SEARCH = os.environ.get("DRAGA_SPREAD", "1") != "0"
    # ルール8/R-29（捨て駒バトル場への投資禁止）の A/B トグル。DUSK_R29=0 で旧挙動
    USE_R29 = os.environ.get("DUSK_R29", "1") != "0"

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
        self.spread_plan = None
        self.bomb_plan = None       # ルール1: カーズドボムの計画（MAIN 毎に再計算）
        self._attach_tag = None     # _attach_score の特殊分岐ラベル（ログ用）
        self.stuck = False          # ルール10: 詰まり判定（MAIN 毎に再計算）

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
        self.spread_plan = None
        self.bomb_plan = None
        self.stuck = False

    # ═══════════════ ログ追跡（pre_ko / no_item） ═══════════════

    def track_logs(self, obs):
        for entry in obs.logs:
            self._log_buf.append(entry)
            if entry.type == LogType.TURN_END:
                self._pre_logs = self._log_buf
                self._log_buf = []
        super().track_logs(obs)   # R-17

    # ═══════════════ R-18: サイド落ち推定 ═══════════════

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

    # ═══════════════ ターン分析 ═══════════════

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
        can_evolve_duskull = False
        can_evolve_dusclops = False
        own_damage = False
        for card in ms.active:
            if card is None:
                continue
            active_id = card.id
            fc[card.id] += 1
            if damage_on(card) > 0:
                own_damage = True
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
                elif card.id == DUSKULL:
                    can_evolve_duskull = True
                elif card.id == DUSCLOPS:
                    can_evolve_dusclops = True
        for card in ms.bench:
            if card is None:
                continue
            fc[card.id] += 1
            if damage_on(card) > 0:
                own_damage = True
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
                elif card.id == DUSKULL:
                    can_evolve_duskull = True
                elif card.id == DUSCLOPS:
                    can_evolve_dusclops = True
            if card.id == DRAGAPULT_EX and len(card.energies) >= 2:
                bench_attacker = True
        for card in (ms.discard or []):
            if card is not None:
                dc[card.id] += 1

        stadium_id = 0
        for card in obs.current.stadium:
            stadium_id = card.id

        pre_ko = False
        no_item = False
        for log in self._pre_logs:
            if log.type == LogType.ATTACK and log.attackId == ATK_ITCHY_POLLEN:
                no_item = True
            elif (log.type == LogType.MOVE_CARD and log.playerIndex == yi
                  and log.fromArea in (AreaType.BENCH, AreaType.ACTIVE)
                  and log.toArea == AreaType.DISCARD):
                pre_ko = True

        energy_in_hand = sum(1 for c in (ms.hand or [])
                             if c is not None and c.id in BASIC_ENERGIES)

        p = {
            "fc": fc, "hc": hc, "dc": dc, "deck_counts": deck_counts,
            "active_id": active_id, "bench_attacker": bench_attacker,
            "can_evolve_dreepy": can_evolve_dreepy,
            "evolve_dreepy_count": evolve_dreepy_count,
            "can_evolve_drakloak": can_evolve_drakloak,
            "can_evolve_duskull": can_evolve_duskull,
            "can_evolve_dusclops": can_evolve_dusclops,
            "own_damage": own_damage,
            "energy_in_hand": energy_in_hand,
            "main_pokemon_count": fc[DREEPY] + fc[DRAKLOAK] + fc[DRAGAPULT_EX],
            "no_more_dex": fc[DRAGAPULT_EX] * 2 >= len(osn.prize),
            "stadium_id": stadium_id,
            "prize_diff": len(ms.prize) - len(osn.prize),
            "pre_ko": pre_ko, "no_item": no_item,
            "no_draw": ms.deckCount <= 8,   # R-11
            "effect_id": obs.select.effect.id if obs.select.effect is not None else 0,
            "context_card_id": obs.select.contextCard.id if obs.select.contextCard is not None else 0,
            "support_count": 0, "hand_scores": [], "negative_hand": 0,
        }

        # S-7: ばら撒き配分の探索計画（DAMAGE_COUNTER_ANY の連続選択中はキャッシュ）
        if self.USE_SPREAD_SEARCH and obs.select.context == SelectContext.DAMAGE_COUNTER_ANY:
            if self.spread_plan is None:
                self.spread_plan = self._plan_spread(obs)
        else:
            self.spread_plan = None

        # MAIN でだけ: 配分プラン（DFS）+ ボム計画 + 詰まり判定 + 使うサポートの択一
        if obs.select.context == SelectContext.MAIN:
            self._main_option_proc(obs, p)
            self.bomb_plan = self._plan_bomb(obs)   # flags 更新後に計算（②③は can_main_attack 前提）
            # ルール10（2026-07-14 ユーザー）: 詰まり判定 —
            # 「エネルギーが張れない または 進化できない」が成立する序盤の番は
            # ハイパーボール→ニャース（Last-Ditch Catch）→リーリエで前へ進む。
            # phase は前決定の値（1決定ラグ・同一ターン内なら実害なし）
            self.p = p   # _score_evolve が self.p を読むため先行代入
            can_attach_now = False
            can_evolve_now = False
            for o in obs.select.option:
                if o.type == OptionType.ATTACH and not can_attach_now:
                    c0 = option_card(obs, o)
                    t0 = option_target(obs, o)
                    if (c0 is not None and t0 is not None
                            and c0.id in BASIC_ENERGIES
                            and self._attach_score(obs, p, c0.id, t0,
                                                   o.inPlayArea == AreaType.ACTIVE) > 0):
                        can_attach_now = True
                elif o.type == OptionType.EVOLVE and not can_evolve_now:
                    if self._score_evolve(obs, o)[0] > 0:
                        can_evolve_now = True
            self.stuck = (self.t["phase"] == "setup"
                          and (not can_attach_now or not can_evolve_now))
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

        # 手札スコア（PLAY 採点の材料）
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

    # ═══════════════ 配分プラン（枝刈り DFS。dragapult_rb 移植） ═══════════════

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

        cards = [osn.active[0]] + list(osn.bench)
        HUGE = 10 ** 9

        def counter_hp(pk):
            if pk is None or _no_damage_counter(pk):
                return HUGE
            return pk.hp

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
                        score = 50000
                    else:
                        if prize >= 2:
                            if remain_prize <= 4:
                                score -= 1200
                        elif prize == 1:
                            score -= 300
                        else:
                            score += 1200
                    if max_score < score:
                        max_score = score
                        best_ci = indices
                        best_prizes = prize
            if plan_score < max_score:
                plan_score = max_score
                self.plan_a = {"attack": i, "counter": list(best_ci), "prizes": best_prizes}
            if i == 0:
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

    # ═══════════════ S-7: ばら撒き60 の配分探索（dragapult_rb 移植・現在HP版） ═══════════════

    def _bench_targets(self, obs):
        osn = opp_state(obs)
        out = []
        for j, pk in enumerate(osn.bench):
            if pk is None:
                continue
            if _no_damage_counter(pk):
                continue
            static = CARD_DB.get(pk.id) or pk
            ff = _final_form(static)
            remain = max(10, pk.hp)
            need = -(-remain // 10)
            # ルール13（2026-07-14 ユーザー）: 相手の投資度 = エネ枚数 + 進化済み(+2)。
            # 即殺候補が複数あるときの優先順位（同サイドなら投資済みを先に取る）
            evolved = bool(getattr(static, "stage1", False)
                           or getattr(static, "stage2", False))
            out.append({
                "coord": j + 1, "remain": remain, "need": need,
                "prize": self._prize_count(pk, False),
                "attacker": _is_attacker(ff),
                "invest": len(pk.energies or []) + (2 if evolved else 0),
            })
        return out

    def _plan_spread(self, obs):
        targets = self._bench_targets(obs)
        target_hp = {}
        if not targets:
            return target_hp

        best_subset, best_key = [], (-1, 0, 0)
        n = len(targets)
        for mask in range(1 << n):
            used, prize, invest, ok = 0, 0, 0, True
            for i in range(n):
                if mask & (1 << i):
                    used += targets[i]["need"]
                    prize += targets[i]["prize"]
                    invest += targets[i]["invest"]
                    if used > 6:
                        ok = False
                        break
            if ok and used <= 6:
                # ルール13: サイド最大 → 投資済み（エネ付き/進化後）優先 → 消費個数最小
                key = (prize, invest, -used)
                if key > best_key:
                    best_key, best_subset = key, [i for i in range(n) if mask & (1 << i)]
        chosen = set(best_subset)
        used = sum(targets[i]["need"] for i in chosen)
        for i in chosen:
            target_hp[targets[i]["coord"]] = 0

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
                        val = t["prize"] * 1000 + 500
                    elif t["remain"] <= 320:
                        val = t["prize"] * 1000 + 200
                    else:
                        val = t["prize"] * 1000 - 100
                else:
                    need_after = -(-max(0, after) // 10)
                    if need_after <= 6:
                        val = t["prize"] * 1000 + 400
                    else:
                        val = t["prize"] * 1000 - 200
                val -= t["remain"] * 0.1
                if val > best_val:
                    best_val, best_i = val, i
            if best_i is not None:
                t = targets[best_i]
                target_hp[t["coord"]] = max(0, t["remain"] - leftover * 10)
        return target_hp

    # ═══════════════ ルール1: カーズドボム計画 ═══════════════

    def _plan_bomb(self, obs):
        """爆発は「KO を取り切れる時だけ」【ハード】。
        ①130(50)単体 / ②正面200と合算（アクティブ） / ③ばら撒き60と合算（ベンチ）。
        自壊 = 相手にサイド1を渡すため、相手残りサイド1以下では絶対に撃たない【ハード】。
        サマヨール(50)は「基本は2進化を目指す」に従い、①でサイド2以上を取れる時だけ。
        戻り値: {"bomber", "dmg", "coord", "mode", "prize", "remain"} or None。"""
        osn = opp_state(obs)
        if len(osn.prize) <= 1:
            return None
        bombers = {pk.id for pk in all_my_pokemon(obs)} & DUSKNOIR_LINE
        if DUSKNOIR in bombers:
            bomber, dmg = DUSKNOIR, 130
        elif DUSCLOPS in bombers:
            bomber, dmg = DUSCLOPS, 50
        else:
            return None
        cards = ([osn.active[0]] if osn.active else [None]) + list(osn.bench)
        can_dive = self.flags.get("can_main_attack", False)
        best = None
        for i, pk in enumerate(cards):
            # ボムは特性 = ミストを貫通。除外は本体特性持ちのみ（ルール9の分離ガード）
            if pk is None or _counter_blocked_by_body(pk):
                continue
            remain = pk.hp
            prize = self._prize_count(pk, False)
            if remain <= dmg:
                mode = 1
            elif i == 0 and can_dive and pk.id not in NO_DAMAGE_DEX and remain <= 200 + dmg:
                mode = 2   # ボム→正面200 で取り切り（正面はダメージ=ミスト無関係）
            elif (i > 0 and can_dive and remain <= 60 + dmg
                    and not _no_damage_counter(pk)):
                mode = 3   # ボム→ばら撒き60 で取り切り（ばら撒き側はミストに阻まれる）
            else:
                continue
            if bomber == DUSCLOPS and not (mode == 1 and prize >= 2):
                continue
            waste = dmg - remain if mode == 1 else 0
            key = (1 if mode == 1 else 0, prize, -waste, -remain)
            if best is None or key > best["key"]:
                best = {"key": key, "bomber": bomber, "dmg": dmg, "coord": i,
                        "mode": mode, "prize": prize, "remain": remain}
        return best

    def _bomb_lethal_now(self, obs):
        """ボムを絡めた取り切り（ボム単体 or ボム+配分プラン）。成立ならボム特性を
        リーサル帯に昇格させる（ボム解決後は通常の R-07 機構が残りを拾う）。"""
        bp = self.bomb_plan
        if bp is None or bp["mode"] != 1:
            return False
        my_remaining = len(my_state(obs).prize)
        if bp["prize"] >= my_remaining:
            return True
        plan = self.plan_a
        if (self.flags.get("can_main_attack") and plan["attack"] >= 0
                and bp["coord"] != plan["attack"]
                and bp["coord"] not in plan["counter"]
                and bp["prize"] + plan["prizes"] >= my_remaining):
            return True
        return False

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
        spread = self._spread_lethal(obs)
        if spread is not None:
            return spread
        return super().judge_lethal(obs)

    def _spread_lethal(self, obs):
        plan = self.plan_a
        if plan["attack"] < 0 or plan["prizes"] < len(my_state(obs).prize):
            return None
        if not self.flags.get("can_main_attack"):
            return None
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return None
        if plan["attack"] == 0:
            return {"route": "active", "attack_id": ATK_PHANTOM_DIVE,
                    "attacker": active, "needs_retreat": False}
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
        return super().score_setup_context(obs, opt)

    def score_yes_no(self, obs, opt):
        # R-11: 山札が薄いときは任意ドロー特性を辞退（ボム/アドレナはドローでないため除外）
        if (obs.select.context == SelectContext.ACTIVATE and self.p.get("no_draw")
                and self.t.get("lethal") is None
                and self.p.get("effect_id") not in (DUSCLOPS, DUSKNOIR, MUNKIDORI)):
            return (1, "R-11: decline activate (deck thin)") if opt.type == OptionType.NO \
                else (0, "R-11: deck thin")
        return super().score_yes_no(obs, opt)

    # ═══════════════ 優先則（3フック） ═══════════════

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
            pi = opt.playerIndex if opt.playerIndex is not None else yi
            if pi != yi:
                score = 20 if opt.area == AreaType.BENCH else 10
                card = get_card(obs, opt.area, opt.index, pi)
                data = CARD_DB.get(card.id) if card is not None else None
                if data is not None and data.cardType == CardType.SPECIAL_ENERGY:
                    score += 1
                return score, "opp energy (bench first, special first)"
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
            return score, (self._attach_tag or "S-5: attach")

        if opt.type == OptionType.EVOLVE:
            return self._score_evolve(obs, opt)

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card is not None else 0
            if cid in (DUSCLOPS, DUSKNOIR):
                # ルール1【ハード】: KO を取り切れる時だけ爆発。取り切りに絡むなら
                # リーサル帯へ昇格（攻撃より先に解決しないとターンが終わるため）
                bp = self.bomb_plan
                if bp is None or bp["bomber"] != cid:
                    return -1, "B-1: hold Cursed Blast (no KO)"
                if self._bomb_lethal_now(obs):
                    return LETHAL_BAND + 1, "B-1: LETHAL Cursed Blast"
                return 2600, f"B-1: Cursed Blast mode{bp['mode']}"
            if cid == MUNKIDORI:
                # E-6: アドレナブレイン。自分の場にダメカンがある時だけ（回復+削り）。
                # 順序は攻撃直前帯（marnie div-14 準拠）
                if p["own_damage"]:
                    return 2500, "E-6: Adrena-Brain (move counters)"
                return -1, "E-6: save Adrena-Brain (no damage)"
            if p["no_draw"]:
                return -1, "R-11: deck thin (ability)"
            if cid == LUMIOSE_CITY:
                return 1, "Lumiose City (low)"
            # ルール7【ソフト（順序）】: 偵察指令は不確定ドロー先・確定サーチ後。
            # ポフィン46000 →（リーリエ45800）→ 偵察45700 → ポケパッド45000。
            # 旧型 div-D3 の 56000（特性最優先）をユーザー決定で置換
            return 45700, "S-4/rule7: Recon Directive (after thinning, before Poke Pad)"

        if opt.type == OptionType.RETREAT:
            if p["do_switch"]:
                return 10000, "retreat (bench attacker / Budew lock)"
            return -1, "no retreat"

        if opt.type == OptionType.ATTACK:
            return (opt.attackId or 0), "E-1: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        return 0, "fallback"

    # ── EVOLVE（S-3。進化カード側の id で分岐） ──

    def _score_evolve(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        cid = card.id if card is not None else 0
        e = len(getattr(target, "energies", []) or []) if target is not None else 0

        # ルール8b（2026-07-14 ユーザー）: 序盤のバトル場はいけにえ — 進化先はベンチ優先。
        # ドロンチはベンチのドラメシヤへ（バトル場のドラメシヤは捨て駒に進化を注がない）。
        # ベンチに対象が居なければ従来通り進化する（優先であって禁止ではない）。
        # -2100 は同一進化カードのベンチ対象を必ず上回らせつつ正帯に留める幅
        sac = 2100 if (self.USE_R29 and self.t["phase"] == "setup"
                       and opt.inPlayArea == AreaType.ACTIVE) else 0

        if cid == DRAKLOAK:
            return 58000 + e - sac, "div-D3/rule8b: evolve Dreepy (bench first)"
        if cid == DRAGAPULT_EX:
            if p["fc"][DRAGAPULT_EX] >= 1:
                return -1, "div-D4: hold 2nd Dragapult ex"
            return 48000 + e - sac, "S-3: evolve -> Dragapult ex"
        if cid == DUSCLOPS:
            return 47500 + e - sac, "S-3b: evolve Duskull -> Dusclops"
        if cid == DUSKNOIR:
            # 基本は2進化（ヨノワール）を目指す（ユーザー決定）。130ボムの装填
            return 49200 + e - sac, "S-3b: evolve -> Dusknoir (load bomb)"
        if target is not None and target.id == DREEPY:
            return 58000 + e - sac, "div-D3/rule8b: evolve Dreepy (bench first)"
        return 30000 + e - sac, "S-3: evolve (other)"

    # ── PLAY ──

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
            return 54000, "S-2: play Dreepy"
        if cid == DUSKULL:
            if fc[DUSKULL] + fc[DUSCLOPS] + fc[DUSKNOIR] < 2:
                return 53000, "S-2b: play Duskull (bomb line)"
            return -1, "Duskull: enough bomb line"
        if cid == MUNKIDORI:
            if fc[MUNKIDORI] == 0:
                return 49000, "S-2c: play Munkidori"
            return -1, "Munkidori: already in play"
        if cid == FEZANDIPITI_EX:
            if card_score > 0:
                return 35000, "play Fez"
            return -1, "Fez: not needed"
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
            dreepy_path = (p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1
                           and fc[DRAGAPULT_EX] == 0 and not p["no_more_dex"])
            duskull_path = p["can_evolve_duskull"] and hc[DUSKNOIR] >= 1
            if dreepy_path or duskull_path:
                return 75000, "S-3: Rare Candy"
            return -1, "Rare Candy: no path now"
        if cid == UNFAIR_STAMP:
            return 57000, "E-5: Unfair Stamp (div-D8)"
        if cid == NIGHT_STRETCHER:
            if card_score >= 18000:
                return 42000, "Night Stretcher: recover"
            return -1, "Night Stretcher: nothing"
        if cid == BOSS:
            if cid == self.use_support:
                return 35000, "R-16: Boss (plan target)"
            return -1, "R-16: hold Boss"
        if cid == LILLIE:
            if cid == self.use_support:
                # ルール7: 圧縮（ポフィン46000）→ リーリエ → 偵察指令45700 → ポケパッド45000。
                # 進化 47500+ はリーリエより先（手札の進化パーツを山へ戻さない）
                return 45800, "rule7: Lillie before Recon"
            return -1, "Lillie: other supporter"
        if cid == DAWN:
            if cid == self.use_support:
                return 30000, "S-4b: Dawn (chosen supporter)"
            return -1, "Dawn: other supporter"
        if cid == ROSA:
            if cid == self.use_support:
                return 35000, "S-5b: Rosa (energy from discard)"
            return -1, "Rosa: other supporter"
        if cid == CRISPIN:
            if cid == self.use_support:
                return 35000, "S-6: Crispin"
            return -1, "Crispin: not chosen"
        if cid == WATCHTOWER:
            # ルール11（2026-07-14 ユーザー）: スタジアムは温存しない。
            # 相手スタジアム置換 / T1 は即時（80000）。自分のスタジアムが出ている間だけ保持。
            # それ以外は攻撃前帯（正帯最下層）で必ず張る
            if p["stadium_id"] in (WATCHTOWER, RISKY_RUINS):
                return -1, "Watchtower: own stadium up"
            if p["stadium_id"] > 0 or obs.current.turn == 1:
                return 80000, "play Watchtower (replace/T1)"
            return 490, "rule11: play stadium before attack"
        if cid == RISKY_RUINS:
            # ルール5+11: 攻撃の直前に張る（全行動を済ませた後 = 正帯最下層。
            # ATTACK(154) と END(0) より上、他の全正帯より下）。攻撃できない番も温存しない
            if p["stadium_id"] in (RISKY_RUINS, WATCHTOWER):
                return -1, "Risky Ruins: own stadium up"
            return 500, "rule5/11: Risky Ruins before attack"
        if p["no_draw"]:
            return -1, "R-11: deck thin (draw item/supporter)"
        if cid == POFFIN:
            # ルール12（2026-07-14 ユーザー）: ポフィン/ポケパッドは温存しない・積極使用
            if deck[DREEPY] + deck[DUSKULL] + deck[BUDEW] > 0:
                return 46000, "S-2/rule12: Poffin"
            return -1, "Poffin: no target"
        if cid == ULTRA_BALL:
            # ルール10: 詰まり脱出 — ニャース経由でリーリエへ（手札を2枚切る価値あり）
            if (self.stuck and not obs.current.supporterPlayed
                    and p["stadium_id"] != WATCHTOWER
                    and hc[MEOWTH_EX] == 0 and deck[MEOWTH_EX] >= 1
                    and p["support_count"] <= hc[BOSS]):
                return 44500, "rule10: Ultra Ball -> Meowth -> Lillie (unstick)"
            if p["negative_hand"] >= 2:
                return 44000, "S-4: Ultra Ball"
            return -1, "Ultra Ball: hold"
        if cid == POKE_PAD:
            if (deck[DREEPY] + deck[DRAKLOAK] + deck[DUSKULL]
                    + deck[DUSCLOPS] + deck[DUSKNOIR] + deck[MUNKIDORI]
                    + deck[BUDEW]) > 0:
                return 45000, "S-4/rule7/rule12: Poke Pad (after Recon)"
            return -1, "Poke Pad: no target"
        return -0.5, "div-D6: unknown card (below END)"

    # ── ATTACH（S-5 + R-10 + ルール2） ──

    def _attach_score(self, obs, p, attach_id, pokemon, active):
        self._attach_tag = None
        data = CARD_DB.get(attach_id)
        if data is not None and data.cardType == CardType.TOOL:
            return 60000 + (1000 if active else 0)

        e = len(pokemon.energies or [])
        if e >= LINE_MAX_COST.get(pokemon.id, 2):
            return -1   # R-10【ハード】（ボムライン=0 / マシマシラ=1 もここで効く）
        # ルール2【ハード】: 悪エネはマシマシラ専用。他ポケモンには張らない。
        # マシマシラに悪以外も張らない（アドレナ起動の1枚だけで良い）
        if attach_id == DARK_ENERGY and pokemon.id != MUNKIDORI:
            return -1
        if pokemon.id == MUNKIDORI:
            if attach_id != DARK_ENERGY:
                return -1
            # DUSK_MUNKI_LATE（ユーザー 2026-07-25）: アドレナは終盤/余裕時のみ起動
            if DUSK_MUNKI_LATE and not self._munki_ok(obs, p):
                return -1
            return 8300   # アドレナブレイン起動（アカマツの「余裕があるとき」の受け皿）
        f = self.flags
        ms = my_state(obs)
        if pokemon.id == BUDEW:
            return -1
        # ルール8/R-29 候補（2026-07-14 ユーザー）: サブゴール前のバトル場は捨て駒。
        # 「ドラメシヤにエネを張って次の番に倒される」の対策 —
        #   ①逃げエネは容認（スボミーを前に出すための退却コスト。あと1枚で逃げられる時だけ）
        #   ②次の相手番に飛ばされる見込み（opp_max_damage ≥ 残HP）のバトル場には張らない
        # アタッカー（ドラパルトex/フェザン）は起動優先で例外。ベンチ育成は影響なし。
        if (self.USE_R29 and active and self.t["phase"] == "setup"
                and pokemon.id not in self.ATTACKER_IDS):
            rc = retreat_cost(pokemon)
            wants_escape = ((p["fc"][BUDEW] >= 1 and pokemon.id != BUDEW)
                            or p["bench_attacker"])
            if rc - e == 1 and wants_escape:
                self._attach_tag = "S-1b: escape energy (bring Budew forward)"
                return 21000
            if self.opp_max_damage(obs) >= pokemon.hp:
                self._attach_tag = "R-29: no invest in doomed active"
                return -1
        if pokemon.id in (MEOWTH_EX, FEZANDIPITI_EX):
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
            elif pokemon.id == DRAKLOAK:
                score -= 120
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
                    score += 120   # div-D7
                elif pokemon.id == DREEPY:
                    score += 100
                else:
                    score += 50
                if p["bench_attacker"]:
                    score -= 200
        if pokemon.id == DRAGAPULT_EX and e < 2:
            score += 25000   # Phantom Dive 起動の最速化
        if p["no_more_dex"] and pokemon.id in (DREEPY, DRAKLOAK):
            score -= 500
        return score

    def _best_attach(self, obs, p, attach_id):
        ms = my_state(obs)
        best = -10000
        for pk in ms.active:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, True))
        for pk in ms.bench:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, False))
        return best

    def _rosa_enables(self, obs, p):
        """ルール3の発火条件: 「使えないと技が打てない・使えばドラパルトが技を打てる」。
        アクティブの Dragapult ex のエネ不足を、トラッシュの基本エネで埋められるか。"""
        if self.flags.get("can_main_attack"):
            return False
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return False
        have = [c.id for c in (active.energyCards or [])]
        dc = p["dc"]
        need = []
        if FIRE_ENERGY not in have:
            need.append(FIRE_ENERGY)
        if PSYCHIC_ENERGY not in have:
            need.append(PSYCHIC_ENERGY)
        if not need or len(need) > 2:
            return False
        return all(dc[cid] >= 1 for cid in need)

    # ── 手札価値（PLAY/サーチ/DISCARD の共通材料） ──

    def _munki_ok(self, obs, p):
        """DUSK_MUNKI_LATE: マシマシラを出す/起動してよい「終盤 or かなり余裕」の局面か。
        余裕 = ダイブ主戦力が既に立っている（場のドラパルト ex >= 1）。
        終盤 = 相手の残サイド <= 3（詰めのダメカン移動が勝ち筋に直結）。"""
        return (p["fc"][DRAGAPULT_EX] >= 1
                or len(opp_state(obs).prize) <= 3)

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
        elif cid == DUSKULL:
            line = fc[DUSKULL] + fc[DUSCLOPS] + fc[DUSKNOIR]
            score = 15000 if line < 2 else 100
        elif cid == DUSCLOPS:
            score = 17000 if p["can_evolve_duskull"] else 2500
        elif cid == DUSKNOIR:
            if p["can_evolve_dusclops"]:
                score = 21000
            elif p["can_evolve_duskull"] and hc[RARE_CANDY] >= 1 and not p["no_item"]:
                score = 20000
            else:
                score = 1500
        elif cid == MUNKIDORI:
            # DUSK_MUNKI_LATE（ユーザー 2026-07-25）: マシマシラは終盤/余裕時のみ場に出す。
            # 余裕が出るまでは温存（40 = end より上・展開札より下でベンチ枠を主戦力に残す）
            if fc[MUNKIDORI] >= 1:
                score = 30
            elif DUSK_MUNKI_LATE and not self._munki_ok(obs, p):
                score = 40
            else:
                score = 12000
        elif cid == FEZANDIPITI_EX:
            if p["pre_ko"]:
                score = 15000
            elif p["prize_diff"] <= -2:
                score = 5
            elif len(osn.prize) == 1:
                score = UNNECESSARY
        elif cid == BUDEW:
            if fc[BUDEW] + fc[DRAKLOAK] + fc[DRAGAPULT_EX] >= 1:
                score = UNNECESSARY
            # DUSK_OPEN_BUDEW（ユーザー 2026-07-25）: 序盤 Poffin で Dreepy と一緒に
            # スボミーを盤面へ（先行T1=turn 1 も。旧 turn>=2 ゲートを解錠）
            elif DUSK_OPEN_BUDEW or obs.current.turn >= 2:
                score = 30000
        elif cid == MEOWTH_EX:
            if p["support_count"] > hc[BOSS] or p["stadium_id"] == WATCHTOWER:
                score = 5
            elif obs.current.supporterPlayed:
                score = 40
            else:
                score = 35000
        elif cid == RARE_CANDY:
            if p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1 and not p["no_more_dex"]:
                score = 40000
            elif p["can_evolve_duskull"] and hc[DUSKNOIR] >= 1:
                score = 38000
            elif p["no_more_dex"] and deck[DUSKNOIR] + hc[DUSKNOIR] == 0:
                score = UNNECESSARY
        elif cid == UNFAIR_STAMP:
            if p["pre_ko"]:
                score = 80000
            elif len(osn.prize) == 1:
                score = UNNECESSARY
            else:
                score = 80
        elif cid == POFFIN:
            count = deck[DREEPY] + (1 if deck[DUSKULL] >= 1 else 0)
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
        elif cid == ULTRA_BALL:
            score = 70 if (p["main_pokemon_count"] <= 2 or fc[DREEPY] >= 1) else 5
        elif cid == POKE_PAD:
            score = max(self._hand_score(obs, p, DREEPY, ignore_count),
                        self._hand_score(obs, p, DRAKLOAK, ignore_count),
                        self._hand_score(obs, p, DUSKULL, ignore_count),
                        self._hand_score(obs, p, DUSCLOPS, ignore_count),
                        self._hand_score(obs, p, DUSKNOIR, ignore_count),
                        self._hand_score(obs, p, MUNKIDORI, ignore_count),
                        self._hand_score(obs, p, BUDEW, ignore_count))
        elif cid == BOSS:
            if self.plan_a["attack"] > 0:
                score = 60000   # R-16
        elif cid == CRISPIN:
            if not ignore_count or p["support_count"] == 0:
                colors = [c for c in BASIC_ENERGIES if deck[c] > 0]
                if len(colors) < 2:
                    score = 10
                elif (not f["can_main_attack"] and not p["bench_attacker"]
                        and fc[DRAGAPULT_EX] >= 1):
                    score = 55000
                else:
                    score = 25000
        elif cid == LILLIE:
            if not ignore_count or p["support_count"] == 0:
                score = 45000
        elif cid == DAWN:
            # ルール6: 基本はリーリエ(45000)未満。「この番ファントムダイブが打てる ∧
            # 手札にエネあり」のときだけリーリエ超え（リフレッシュで手札のエネを
            # 山へ戻さず、進化パーツを取りに行く）
            if not ignore_count or p["support_count"] == 0:
                targets = (deck[DREEPY] + deck[DUSKULL] + deck[DRAKLOAK]
                           + deck[DUSCLOPS] + deck[DRAGAPULT_EX] + deck[DUSKNOIR])
                if targets == 0:
                    score = 20
                elif f["can_main_attack"] and p["energy_in_hand"] >= 1:
                    score = 46000
                else:
                    score = 43000
        elif cid == ROSA:
            # ルール3: 通常は温存（低帯）。「使えばドラパルトが技を打てる」局面で
            # リーリエ超え。エンジン条件（サイド負け時のみ）は engine 側が合法性で弾く
            if not ignore_count or p["support_count"] == 0:
                if p["prize_diff"] > 0 and self._rosa_enables(obs, p):
                    score = 47000
                else:
                    score = 200
        elif cid == WATCHTOWER:
            if p["stadium_id"] != 0 and p["stadium_id"] != WATCHTOWER:
                score = 4000
        elif cid == RISKY_RUINS:
            if p["stadium_id"] != RISKY_RUINS:
                score = 3000
        elif cid in BASIC_ENERGIES:
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
                score -= 100000   # 同名2枚目の割引（R-13 の順序側）
        return score

    # ── CARD 選択（前出し・サーチ先・配分・DISCARD 等） ──

    def _score_promote(self, obs, opt):
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
            elif cid == DUSKNOIR:
                score += 5000
            elif cid == DUSCLOPS:
                score += 4000
            elif cid == DUSKULL:
                score += 3000
            elif cid == MUNKIDORI:
                score += 2000
            elif cid == FEZANDIPITI_EX:
                score -= 1000
            elif cid == MEOWTH_EX:
                score -= 2000
            score += e * 1000 + hp
            return self.default_score_promote(obs, opt, score, "S-1: promote")   # R-08
        if self.plan_a["attack"] == opt.index + 1:
            return 100000 + e * 1000 + hp, "R-16: pull plan target"
        return e * 1000 + hp, "pull: energy/hp heuristic"

    @staticmethod
    def _take_band(score):
        if score >= 0:
            return min(score, 900000)
        return (200000 + max(score, -200000)) / 200000.0

    def _score_card(self, obs, opt):
        p = self.p
        ctx = obs.select.context
        yi = obs.current.yourIndex
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
                if cid in BASIC_ENERGIES:
                    # S-6a（3色対応）: 手札に取らなかった色が場に付く。残る色の
                    # 最良付け先価値（S-5）が最も高くなる色を手札に取る。
                    # 逆色が山に残らない色は付与消滅のため降格【ハード】
                    others = [o for o in BASIC_ENERGIES if o != cid
                              and any(c is not None and c.id == o
                                      for c in (obs.select.deck or []))]
                    if others:
                        score = 100000 + max(self._best_attach(obs, p, o) for o in others)
                    else:
                        score = 50
                else:
                    score = 100000 - self._hand_score(obs, p, cid, True)
            # ルール10: 詰まり脱出コンボの取得先を固定 —
            # ハイパーボールはニャースを掘り、ニャースのサポートサーチはリーリエへ
            if self.stuck and p["effect_id"] == ULTRA_BALL and cid == MEOWTH_EX:
                score = max(score, 46000)
            if self.stuck and p["effect_id"] == MEOWTH_EX and cid == LILLIE:
                score = max(score, 61000)   # ボス(60000)より上 = 詰まり時はリーリエ直行
            # DUSK_PAD_DRAKLOAK（ユーザー 2026-07-25）: ポケパッドで手札に取るとき、
            # 場にドラメシヤを用意できる（進化元が居る）ならドロンチを優先的に持ってくる
            # （Dusknoir 21000 の上に置く。ダイブ線の次ターン完成を最優先）
            if (DUSK_PAD_DRAKLOAK and ctx == SelectContext.TO_HAND
                    and p["effect_id"] == POKE_PAD and cid == DRAKLOAK
                    and p["can_evolve_dreepy"]):
                score = max(score, 33000)
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
            # E-6: アドレナブレインの移動元（自分側）/ 移動先（相手側）
            if p["effect_id"] == MUNKIDORI:
                pi = opt.playerIndex if opt.playerIndex is not None else yi
                if pi == yi:
                    return self._score_adrena_source(obs, card)
                return self._score_adrena_target(obs, opt, card)
            return self.default_score_damage_target(obs, opt)   # R-15

        if ctx == SelectContext.REMOVE_DAMAGE_COUNTER:
            # E-6: アドレナブレインの移動元（エンジン経路の別形）
            return self._score_adrena_source(obs, card)

        if ctx == SelectContext.ATTACH_TO:
            if cid is None:
                return 0, "attach none"
            return self._take_band(self._best_attach(obs, p, cid)), "S-6b: attach energy pick"

        if ctx == SelectContext.ATTACH_FROM:
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

    def _score_adrena_source(self, obs, card):
        """アドレナブレインの移動元: ドラパルトライン（タンク・進化元）の回復を優先。
        マシマシラ自身は重傷時のみ救出（marnie div-11 v2 準拠）。"""
        if card is None:
            return 0, "adrena source none"
        dmg = damage_on(card)
        cid = card.id
        if cid == MUNKIDORI and dmg >= 60:
            return 3000 + dmg, "E-6: rescue heavily-hit Munkidori"
        if cid == DRAGAPULT_EX:
            return 2200 + dmg, "E-6: heal Dragapult ex"
        if cid in (DREEPY, DRAKLOAK):
            return 1800 + dmg, "E-6: heal evolving line"
        if cid == MUNKIDORI:
            return -1000 + dmg, "E-6: keep Munkidori damage"
        return 1000 + dmg, "E-6: heal other"

    def _score_adrena_target(self, obs, opt, card):
        """アドレナブレインの移動先（相手側）: 取り切り最優先、次にボム/配分の布石。
        アドレナは特性 = ミストを貫通（除外は本体特性のみ）。"""
        if card is None:
            return 0, "adrena target none"
        if _counter_blocked_by_body(card):
            return -1, "E-6: body-ability guard"
        hp = getattr(card, "hp", 999)
        if hp <= 30:
            return 15000 + (500 - hp), "E-6: counter-move KO"
        if card.id in BONUS_COUNTER_TARGETS:
            return 12000 - hp, "E-6: priority snipe target"
        return self.default_score_damage_target(obs, opt)   # R-15

    def _score_counter(self, obs, opt, card, ctx):
        """E-2: ダメカン配分（S-7 探索計画 + カーズドボムの対象選択）。"""
        if card is None or getattr(card, "hp", 0) <= 0:
            return 0, "counter none"
        p = self.p
        hp = card.hp
        score = 100000 - 10 * hp + self._pokemon_score(card, False)
        if ctx == SelectContext.DAMAGE_COUNTER:
            # ボムの対象選択（effect = サマヨール/ヨノワール）は計画の対象に固定。
            # ボムは特性なのでミストを貫通（除外は本体特性のみ）
            if p["effect_id"] in (DUSCLOPS, DUSKNOIR):
                bp = self.bomb_plan
                coord = 0 if opt.area == AreaType.ACTIVE else (opt.index or 0) + 1
                if bp is not None and coord == bp["coord"]:
                    return 500000, "B-1: bomb plan target"
                if _counter_blocked_by_body(card):
                    return -1, "E-2: body-ability guard"
                return score, "B-1: bomb fallback (off-plan)"
            # ルール9【ハード】: ワザ効果の単発ダメカンもミスト装着体を指定しない
            if _no_damage_counter(card):
                return -1, "rule9: mist/no-counter guard"
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
        if self.USE_SPREAD_SEARCH and self.spread_plan is not None:
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
# R-25【ハード】: def agent は必ずファイル末尾の callable にする。

_impl = make_agent(DragapultDusknoirPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
