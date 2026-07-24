"""共有基盤 BasePolicy — 全デッキエージェントが継承する単一の正本。

正本は agents/_base/policy_base.py。各エージェントdirへのコピーは scripts/sync_base.py で
同期する（コピーを直接編集禁止）。設計文書:
  - docs/planning/用語とターン手順.md   … 判定/マスク/優先則/手順/サブゴール/フェーズ
  - docs/planning/ルール抽出_オープン実装.md … R-xx/P-xx

ここに置くもの（= 全デッキ共通・コピペ禁止の層。P-05）:
  - ターン手順: choose()（判定を毎手番更新 → スコア → 辞書式選択）と
    apply_protocol()（R-07 リーサル昇格・退却の計画内/外の扱い）
  - 判定の汎用形: judge_lethal（plan_attacks フック駆動）/ judge_loss_threats（R-08 ボス想定）/
    detect_matchup（R-20、meta_tables 参照）
  - マスクの汎用形: R-10 エネ過剰付与（技コストから導出）/ R-11 山札切れ / R-13 勝ち筋保護
  - 安全: make_agent ラッパー（R-01/R-02）と DIAG カウンタ（check_agent が読む）

デッキ側 main.py の型:
    import os, sys
    ...sys.path ブートストラップ（自dir + /kaggle_simulations/agent。base import より前に必須）...
    from policy_base import BasePolicy, make_agent, read_deck_csv as _read_deck_csv
    class MyPolicy(BasePolicy):
        DECK_NAME = "..."; GO_FIRST = False; TAKE_MULLIGAN = False
        ATTACKER_IDS = {...}; ENERGY_IDS = {...}; LINE_PROTECT_IDS = {...}
        def judge_subgoal(self, obs): ...
        def score_setup(self, obs, opt): ...
        def score_combat(self, obs, opt): ...
    _impl = make_agent(MyPolicy)
    def read_deck_csv():
        return _read_deck_csv()
    def agent(obs_dict):            # literal def が build_submission の検査に必要
        return _impl(obs_dict)

    ⚠ R-25【ハード】: `def agent` は必ず main.py の「最後に定義される callable」にすること。
    Kaggle のローダー（kaggle_environments get_last_callable）はファイル末尾の callable を
    エージェントとして呼ぶ。agent の後に関数/クラス/callable 代入を書くと検証エピソードが
    INVALID で即死する（2026-07-07 の提出失敗の原因）。

コードの出所: agents/archaludon_rb v1（Apache-2.0 Kaggle Notebook 系譜）から抽出。
ptcg-abc は設計参照のみ（無ライセンスのためコード引用なし）。
"""
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from cg.api import (
    AreaType,
    CardType,
    LogType,
    OptionType,
    SelectContext,
    all_card_data,
    to_observation_class,
)

import meta_tables as mt

try:
    from cg.api import all_attack
    ATTACK_TABLE = {a.attackId: a for a in all_attack()}
except Exception:
    ATTACK_TABLE = {}

CARD_DB = {c.cardId: c for c in all_card_data()}

LETHAL_BAND = 1_000_000  # R-07: リーサル手の専用スコア帯（全優先則より上）

# R-30「使用可能なグッズは使用する」の A/B トグル（既定 ON。詳細 = _r30_default_item）
R30_ENABLED = os.environ.get("R30", "1") != "0"
# R-31「KO 後の前出しは、にげエネ0のベンチがいれば常にそれ」（既定 ON。詳細 = _r31_promote_free）
R31_ENABLED = os.environ.get("R31", "1") != "0"


def band_of(score):
    """スコアの粗い帯分類 — ロギング/アサーション専用。ソートキーには絶対に使わない。

    choose() の挙動と厳密に対応する境界のみを持つ:
      (1) score >= LETHAL_BAND-1 …… apply_protocol のリーサル昇格帯（1_000_000 / 999_999）
      (2) score == -999999      …… score_option の例外サンチネル（等値比較）
      (3) 符号                  …… 負 = minCount 超過分では選ばれない（マスクの表現）

    これ以上の細分類（ハードマスク帯/ソフト帯の分離など）は挙動と対応しないため行わない。
    既知の桁例外（2026-07-09 全デッキ調査。band 再割当を禁止する根拠）:
      - R-08 の -15000 加算はデッキにより「マスク」にも「ソフト差分」にもなる（基礎スコア依存）
      - mega_kangaskhan は score_combat 内から直接 LETHAL_BAND を返す（Prime Catcher 経路）
      - dragapult は独自スケール（5万〜20万、(0,1] の小数、UNNECESSARY=-10_000_000）
      - 1e5〜2e5 の正スコアが複数デッキに存在（ACTIVATE=100000 等）
      - ハード意図の -1 と -100000 が混在し、強制充足時は負値間の順序も意味を持つ
    """
    if score >= LETHAL_BAND - 1:
        return "lethal"
    if score == -999999:
        return "error"
    if score > 0:
        return "positive"
    if score == 0:
        return "zero"
    return "negative"


def load_theta():
    """学習済みルール強度 θ（reason 文字列 → スコア加算値）を theta.json から読む。

    置き場所は policy_base.py と同じディレクトリ（= エージェントdir。ローカルでも
    Kaggle の /kaggle_simulations/agent でも同じ相対関係）。ファイル不在・破損時は
    空 dict = θ なし = 手書きスコアのまま（挙動不変のフォールバック。R-01 と同思想）。"""
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "theta.json")
    try:
        with open(fp, encoding="utf-8") as f:
            raw = json.load(f)
        return {str(k): float(v) for k, v in raw.items() if v}
    except Exception:
        return {}

# R-01 検査用カウンタ（check_agent が main.DIAG 経由で読む）
DIAG = {"decisions": 0, "policy_ok": 0, "errors": 0, "option_errors": 0,
        "search_calls": 0, "search_used": 0, "search_errors": 0,
        "net_calls": 0, "net_used": 0, "net_errors": 0}


# ═══════════════════════════════ 盤面ヘルパー（判定の材料） ═══════════════════════════════

def read_deck_csv():
    import os
    fp = "deck.csv"
    if not os.path.exists(fp):
        fp = "/kaggle_simulations/agent/deck.csv"
    with open(fp) as f:
        lines = [l.strip() for l in f.read().split("\n")]
    return [int(l) for l in lines if l][:60]


def get_card(obs, area, index, player_index):
    if area is None or index is None:
        return None
    ps = obs.current.players[player_index]
    if area == AreaType.DECK and obs.select and obs.select.deck is not None:
        return obs.select.deck[index] if index < len(obs.select.deck) else None
    if area == AreaType.HAND and ps.hand is not None:
        return ps.hand[index] if index < len(ps.hand) else None
    if area == AreaType.DISCARD:
        return ps.discard[index] if index < len(ps.discard) else None
    if area == AreaType.ACTIVE:
        return ps.active[index] if index < len(ps.active) else None
    if area == AreaType.BENCH:
        return ps.bench[index] if index < len(ps.bench) else None
    if area == AreaType.PRIZE:
        return ps.prize[index] if index < len(ps.prize) else None
    if area == AreaType.STADIUM:
        return obs.current.stadium[index] if index < len(obs.current.stadium) else None
    if area == AreaType.LOOKING and obs.current.looking is not None:
        return obs.current.looking[index] if index < len(obs.current.looking) else None
    return None


def option_card(obs, opt):
    yi = obs.current.yourIndex
    pi = opt.playerIndex if opt.playerIndex is not None else yi
    if opt.type == OptionType.PLAY:
        return get_card(obs, AreaType.HAND, opt.index, pi)
    return get_card(obs, opt.area, opt.index, pi)


def option_target(obs, opt):
    if opt.inPlayArea is None or opt.inPlayIndex is None:
        return None
    return get_card(obs, opt.inPlayArea, opt.inPlayIndex, obs.current.yourIndex)


def my_state(obs):
    return obs.current.players[obs.current.yourIndex]


def opp_state(obs):
    return obs.current.players[1 - obs.current.yourIndex]


def active_pokemon(obs):
    ps = my_state(obs)
    return ps.active[0] if ps.active else None


def opp_active_pokemon(obs):
    ps = opp_state(obs)
    return ps.active[0] if ps.active else None


def opp_bench_pokemon(obs):
    return [p for p in opp_state(obs).bench if p]


def all_my_pokemon(obs):
    ps = my_state(obs)
    return [p for p in (ps.active + ps.bench) if p]


def hand_ids(obs):
    hand = my_state(obs).hand
    return [c.id for c in hand if c] if hand else []


def discard_ids(obs):
    return [c.id for c in (my_state(obs).discard or []) if c]


def energy_count(pokemon):
    if pokemon is None:
        return 0
    if getattr(pokemon, "energyCards", None) is not None:
        return len(pokemon.energyCards)
    return len(getattr(pokemon, "energies", []) or [])


def retreat_cost(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    return getattr(data, "retreatCost", 0) if data else 0


def damage_on(pokemon):
    if pokemon is None:
        return 0
    return max(0, getattr(pokemon, "maxHp", pokemon.hp) - pokemon.hp)


def has_tool(pokemon):
    return bool(getattr(pokemon, "tools", []) or [])


def count_in_play(obs, card_id):
    return sum(1 for p in all_my_pokemon(obs) if p.id == card_id)


def has_in_play(obs, card_id):
    return any(p.id == card_id for p in all_my_pokemon(obs))


def prize_value(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    if data and getattr(data, "megaEx", False):
        return 3
    if data and getattr(data, "ex", False):
        return 2
    return 1


def is_ex(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    return bool(data and (getattr(data, "ex", False) or getattr(data, "megaEx", False)))


def weakness_value(pokemon):
    data = CARD_DB.get(pokemon.id) if pokemon else None
    w = getattr(data, "weakness", None) if data else None
    if w is None:
        return None
    return getattr(w, "value", w)


def first_option_index(obs, card_id):
    for o in obs.select.option:
        oc = option_card(obs, o)
        if oc and oc.id == card_id:
            return getattr(o, 'index', None)
    return None


def legal_fallback_from_dict(obs_dict):
    # R-01/R-02: 例外時は決定的な合法手（先頭 minCount 個）
    try:
        sel = obs_dict.get("select") or {}
        n = len(sel.get("option") or [])
        return list(range(min(max(0, sel.get("minCount", 0)), n)))
    except Exception:
        return []


# ── R-10: エネルギー規律（技の実コストから導出。カード毎ハードコード禁止） ──

def attack_cost(attack_id):
    a = ATTACK_TABLE.get(attack_id)
    return list(getattr(a, "energies", None) or []) if a else None


def attack_base_damage(attack_id):
    a = ATTACK_TABLE.get(attack_id)
    return int(getattr(a, "damage", 0) or 0) if a else 0


def card_attack_ids(card_id):
    data = CARD_DB.get(card_id)
    return list(getattr(data, "attacks", None) or []) if data else []


def can_pay_count(pokemon, attack_id):
    """枚数ベースの簡易コスト判定（色は見ない）。ATTACK_TABLE 不在時は None（判定不能）。"""
    cost = attack_cost(attack_id)
    if cost is None:
        return None
    return energy_count(pokemon) >= len(cost)


def payable_attacks(pokemon):
    if pokemon is None:
        return []
    return [aid for aid in card_attack_ids(pokemon.id) if can_pay_count(pokemon, aid)]


# ═══════════════════════════════ AttackPlan ═══════════════════════════════

@dataclass
class AttackPlan:
    """判定 judge_lethal / 交戦優先則の共通言語。
    attacker は obs 内オブジェクト（identity 比較で apply_protocol が前出しを昇格する）。"""
    attacker: object
    attack_id: int
    damage: int
    needs_retreat: bool = False
    uses_attach: bool = False
    spread_damage: int = 0          # ばら撒き分（複数KO探索版の予約。v1 リーサルでは未使用）
    requires: dict = field(default_factory=dict)


# ═══════════════════════════════ BasePolicy ═══════════════════════════════

class BasePolicy(ABC):
    # ── 必須クラス属性（サブクラス定義時に検査） ──
    DECK_NAME: str = None
    GO_FIRST: bool = None            # R-21: デッキ固有。上位ピロットのデータから読む
    TAKE_MULLIGAN: bool = None       # R-22: 同上
    ATTACKER_IDS: set = None
    ENERGY_IDS: set = None
    LINE_PROTECT_IDS: set = None     # R-13: DISCARD でハード保護する勝ち筋ライン

    # ── 任意クラス属性 ──
    SELF_SCALING_ATTACK_IDS = frozenset()   # R-10 例外（エネ枚数で打点が伸びる技）
    ATTACK_ENERGY_TYPE = None               # 弱点計算に使う自軍の攻撃タイプ（EnergyType値）

    # ── ターン内探索（turn_search.py。既定 OFF = 挙動不変） ──
    SEARCH = False                    # マスタースイッチ（インスタンスは search_enabled）
    SEARCH_MODE = "rollout"           # "rollout"（基準線）| "value"（V(s) 葉。npz 必須）
    SEARCH_TIME_PER_DECISION = 1.0    # 秒/決定（rollout ≈30本、value は決定化8回で早期終了）
    SEARCH_GAME_BUDGET = 240.0        # 秒/試合の累計上限（R-23: 600秒プールへの安全マージン）
    SEARCH_MIN_OVERAGE = 120.0        # remainingOverageTime がこれ未満なら探索しない（R-23）
    SEARCH_MAX_CANDIDATES = 5         # 探索する候補手の数（ルールスコア上位から）
    SEARCH_MIN_CANDIDATES = 2         # 正帯の候補がこれ未満なら探索しない
    SEARCH_SKIP_MARGIN = 8000         # ルールの1位2位差がこれ以上なら探索しない（自明な手）

    # ── 方策ネット（policy_net.py。npz 不在 = 挙動不変） ──
    NET_MAX_CANDIDATES = 12           # 再ランクする候補手の数（ルールスコア上位から）

    _REQUIRED = ("DECK_NAME", "GO_FIRST", "TAKE_MULLIGAN",
                 "ATTACKER_IDS", "ENERGY_IDS", "LINE_PROTECT_IDS")

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        missing = [a for a in cls._REQUIRED if getattr(cls, a, None) is None]
        if missing:
            raise TypeError(
                f"{cls.__name__}: 必須クラス属性が未定義です: {missing} "
                f"(R-21/R-22/R-13 はデッキ毎に明示的に決める)")

    def __init__(self):
        # ターン手順の判定結果（choose() 冒頭で毎手番更新。判定は常時実行）
        self.t = {"phase": "setup", "lethal": None, "threats": [], "matchup": "generic"}
        # R-17: 相手の前ターン技の追跡
        self._opp_last_attack_id = None
        self._cur_turn_logs = []
        # 決定ログ（模倣学習の訓練データ受け皿）。None = 無効（デプロイ時の既定）。
        # ハーネスが `policy.decision_log = []` を代入して有効化し、drain/clear も
        # ハーネス側が管理する。reset_game() では触らない（ゲーム境界で消さない）。
        self.decision_log = None
        # 学習済みルール強度 θ（reason → 加算値）。theta.json 不在なら {} = 素通し。
        # 訓練ハーネスは policy.theta = candidate_dict の直接代入で差し替えられる。
        self.theta = load_theta()
        # ターン内探索（turn_search.py）。search_enabled は実行時に注入可能
        # （gauntlet --search が代入する。SEARCH=False のクラスでも A/B 可能）。
        self.search_enabled = bool(self.SEARCH)
        self.my_deck_list = None          # make_agent のデッキ選択時 or ハーネスが注入
        self.overage_remaining = None     # make_agent が obs_dict から毎手更新（R-23）
        self._search_time_used = 0.0
        self._searcher = None
        # 方策ネット（policy_net.py）。既定 = agent dir の policy_net.npz を遅延ロード
        # （不在なら None = 挙動不変）。訓練/評価ハーネスは以下を直接注入できる:
        #   policy._net = PolicyNet相当   … 重み差し替え（gauntlet --net / train_ppo）
        #   policy.net_enabled = False    … A/B の OFF 側
        #   policy.net_sample = True + policy.net_rng … softmax サンプリング（訓練時のみ）
        #   policy.net_log = []           … 遷移ログの受け皿（X/k/logp。訓練時のみ）
        self._net = None
        self._net_load_tried = False
        self.net_enabled = True
        self.net_sample = False
        self.net_rng = None
        self.net_log = None

    # ── ゲーム間リセット（obs.select is None = デッキ選択 = 新ゲーム） ──
    def reset_game(self):
        self._opp_last_attack_id = None
        self._cur_turn_logs = []
        self.t = {"phase": "setup", "lethal": None, "threats": [], "matchup": "generic"}
        self._search_time_used = 0.0
        if self._searcher is not None:
            for p in (self._searcher._pilot_self, self._searcher._pilot_opp):
                if p is not None:
                    p.reset_game()

    def track_logs(self, obs):
        # R-17: TURN_END で区切って相手の最終攻撃を記録
        yi = obs.current.yourIndex
        for entry in obs.logs:
            if entry.type == LogType.TURN_END:
                for prev in self._cur_turn_logs:
                    if prev.type == LogType.ATTACK and getattr(prev, 'playerIndex', yi) != yi:
                        self._opp_last_attack_id = prev.attackId
                self._cur_turn_logs.clear()
            else:
                self._cur_turn_logs.append(entry)

    @property
    def opp_last_attack_id(self):
        return self._opp_last_attack_id

    # ═══════════════ 判定（predicates。常時実行・行動を選ばない） ═══════════════

    @abstractmethod
    def judge_subgoal(self, obs) -> bool:
        """S-0 サブゴール判定。フェーズ = この判定の現在値（状態を持たない）。"""

    def detect_matchup(self, obs):
        # R-20: 相手の場のカードID集合からアーキタイプ判定
        opp = opp_state(obs)
        ids = {p.id for p in (opp.active + opp.bench) if p}
        for name, line in mt.ARCHETYPES.items():
            if ids & line:
                return name
        return "generic"

    def opp_max_damage(self, obs):
        # R-08 入力: 可変打点の推定器 > 静的テーブル
        matchup = self.t["matchup"]
        est = mt.OPP_DAMAGE_ESTIMATORS.get(matchup)
        if est is not None:
            return est(obs, opp_state(obs))
        return mt.OPP_MAX_DAMAGE.get(matchup, mt.OPP_MAX_DAMAGE["generic"])

    def effective_damage(self, base_damage, target):
        # 弱点×2（自軍の攻撃タイプが宣言されている場合のみ）
        if (self.ATTACK_ENERGY_TYPE is not None and target is not None
                and weakness_value(target) == self.ATTACK_ENERGY_TYPE):
            return base_damage * 2
        return base_damage

    def guard_damage(self, base_damage, attacker, target):
        # リーサル誤検出ガード: ex/megaEx 無効化アクティブ（Crustle 型）
        if target is not None and target.id in mt.IMMUNE_TO_EX_ACTIVE and is_ex(attacker):
            return 0
        return self.effective_damage(base_damage, target)

    def judge_lethal(self, obs):
        """R-07 リーサル判定（常時・閉形式）: この番で相手の残りサイドを取り切れるか。
        射程は「単発KO + ボス吊り出しKO」。複数KO複合手は探索版で扱う。"""
        my_remaining = len(my_state(obs).prize)
        plans = self.plan_attacks(obs)
        if not plans:
            return None
        opp_act = opp_active_pokemon(obs)
        if opp_act and prize_value(opp_act) >= my_remaining:
            for plan in plans:
                if self.guard_damage(plan.damage, plan.attacker, opp_act) >= opp_act.hp:
                    return {"route": "active", "attack_id": plan.attack_id,
                            "attacker": plan.attacker, "needs_retreat": plan.needs_retreat}
        if mt.BOSS in hand_ids(obs) and not obs.current.supporterPlayed:
            for target in opp_bench_pokemon(obs):
                if prize_value(target) < my_remaining:
                    continue
                for plan in plans:
                    if self.guard_damage(plan.damage, plan.attacker, target) >= target.hp:
                        return {"route": "boss", "target": target,
                                "attack_id": plan.attack_id, "attacker": plan.attacker,
                                "needs_retreat": plan.needs_retreat}
        return None

    def judge_loss_threats(self, obs):
        """R-08 被リーサル判定（常時・閉形式・ボス想定）。
        「相手の手札にボスがある」前提で、取られると負ける自軍ポケモンの集合。
        緩和: 相手トラッシュのボスがアーキタイプ既知枚数に達したらベンチ露出を解除。"""
        opp_remaining = len(opp_state(obs).prize)
        dmg = self.opp_max_damage(obs)
        if dmg <= 0:
            return []
        boss_used = sum(1 for c in (opp_state(obs).discard or []) if c and c.id == mt.BOSS)
        boss_limit = mt.OPP_BOSS_COUNTS.get(self.t["matchup"], mt.OPP_BOSS_COUNTS["generic"])
        boss_assumed = boss_used < boss_limit
        threats = []
        ps = my_state(obs)
        actives = [p for p in ps.active if p]
        for p in all_my_pokemon(obs):
            exposed = (p in actives) or boss_assumed
            if exposed and dmg >= p.hp and prize_value(p) >= opp_remaining:
                threats.append(p)
        return threats

    def is_threatened(self, pokemon):
        # R-08 判定結果への identity 参照（優先則から使う）
        return any(p is pokemon for p in self.t["threats"])

    # ═══════════════ 攻撃計画（judge_lethal と交戦優先則の共通入力） ═══════════════

    def plan_attacks(self, obs):
        """デフォルトの汎用ビルダー: 到達可能な攻撃者 × 払える技。
        手書きルート（進化・特殊加速込み）を持つデッキはオーバーライドする。
        ATTACK_TABLE 不在時は空リスト（judge_lethal → None、クラッシュさせない）。"""
        plans = []
        active = active_pokemon(obs)
        if active is not None:
            for aid in payable_attacks(active):
                plans.append(AttackPlan(active, aid, self.attack_damage(obs, active, aid)))
        # ベンチ: 退却が払えて未退却なら計画候補
        if (active is not None and not obs.current.retreated
                and energy_count(active) >= retreat_cost(active)):
            for p in my_state(obs).bench:
                if p is None or p.id not in self.ATTACKER_IDS:
                    continue
                for aid in payable_attacks(p):
                    plans.append(AttackPlan(p, aid, self.attack_damage(obs, p, aid),
                                            needs_retreat=True))
        return plans

    def attack_damage(self, obs, attacker, attack_id):
        """技の打点。可変打点（手札枚数・ダメカン依存等）のデッキはオーバーライド。"""
        return attack_base_damage(attack_id)

    # ═══════════════ 優先則（デッキ必須フック） ═══════════════

    @abstractmethod
    def score_setup(self, obs, opt):
        """セットアップ優先則（サブゴール未達。相手はほぼ無視、コンセプト実現に直進）。
        -> (score, reason)"""

    @abstractmethod
    def score_combat(self, obs, opt):
        """交戦優先則（サブゴール達成後。相手考慮の詰め）。 -> (score, reason)"""

    # ── 任意フック（デフォルト実装あり） ──

    def score_setup_context(self, obs, opt):
        """IS_FIRST / MULLIGAN / SETUP_ACTIVE / SETUP_BENCH のデフォルト。
        R-21/R-22 はクラス属性から。SETUP_ACTIVE はアタッカー優先。"""
        ctx = obs.select.context
        if ctx == SelectContext.MULLIGAN:
            want = OptionType.YES if self.TAKE_MULLIGAN else OptionType.NO
            return (10000, "R-22: mulligan choice") if opt.type == want else (0, "mulligan other")
        if ctx == SelectContext.IS_FIRST:
            want = OptionType.YES if self.GO_FIRST else OptionType.NO
            return (10000, "R-21: first/second choice") if opt.type == want else (0, "first other")
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid in self.ATTACKER_IDS:
                return 20000, "setup: attacker active"
            return 1000, "setup: other active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            return -10000, "setup: never bench during setup"
        return 0, "non-setup"

    def score_yes_no(self, obs, opt):
        """YES/NO のデフォルト。ACTIVATE（任意特性の発動）は原則 YES。"""
        if obs.select.context == SelectContext.ACTIVATE:
            return (100000, "activate ability") if opt.type == OptionType.YES else (-100000, "never decline")
        return (1, "yes") if opt.type == OptionType.YES else (0, "no")

    def score_number(self, obs, opt):
        return (opt.number or 0), "number"

    def mask_extra(self, obs, opt, score, reason):
        """デッキ固有の追加ハードマスク。デフォルトは素通し。"""
        return score, reason

    def apply_overrides(self, obs, opt, score, reason):
        """E-3: マッチアップ上書き差分（基礎スコア + 差分の2層）。デフォルトは素通し。"""
        return score, reason

    # ── 汎用の部品スコアラー（デッキの優先則から呼ぶ） ──

    def default_score_discard(self, obs, opt):
        """R-13: 勝ち筋ラインをハード保護、余剰エネ・重複から捨てる汎用形。"""
        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, "cardId", None)
        ids = hand_ids(obs)
        if cid in self.LINE_PROTECT_IDS:
            return -5000, "R-13: keep win-condition line"
        if cid in self.ENERGY_IDS and ids.count(cid) > 1:
            return 12000, "discard extra energy"
        if cid is not None and ids.count(cid) > 1:
            return 8000, "discard duplicate"
        return 1000, "generic discard"

    def default_score_damage_target(self, obs, opt):
        """R-15: スナイプ/ばら撒きは相手の低HPエンジン駒を優先。"""
        card = option_card(obs, opt)
        hp = getattr(card, "hp", 999) if card else 999
        return 10000 - hp, "R-15: damage lowest HP"

    def default_score_promote(self, obs, opt, base_score, reason):
        """自分側の前出し選択に R-08 マスクを適用する汎用形。
        代替が無ければ choose() の minCount 充足で自動的に least-bad へ緩和（辞書式）。"""
        card = option_card(obs, opt)
        if card is not None and self.is_threatened(card):
            return base_score - 15000, f"R-08: avoid promoting game-losing piece ({reason})"
        return base_score, reason

    # ═══════════════ ターン手順（手順。判定 → 昇格/マスクの辞書式適用） ═══════════════

    def apply_protocol(self, obs, opt, score, reason):
        """用語とターン手順.md の手順1（リーサル）を優先則より上の帯へ昇格させる。
        手順2（負け筋カット）のマスクは優先則の中で R-08 タグ付きで適用する。"""
        lethal = self.t["lethal"]
        if lethal is None:
            return score, reason
        ctx = obs.select.context
        yi = obs.current.yourIndex

        # R-07: リーサル手を LETHAL_BAND に昇格
        if opt.type == OptionType.ATTACK and getattr(opt, 'attackId', None) == lethal["attack_id"]:
            return LETHAL_BAND, "R-07: LETHAL attack"
        if lethal["route"] == "boss" and opt.type == OptionType.PLAY:
            card = option_card(obs, opt)
            if card and card.id == mt.BOSS:
                return LETHAL_BAND, "R-07: LETHAL Boss"
        if lethal["route"] == "boss" and ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
            if getattr(opt, 'playerIndex', yi) != yi:
                card = option_card(obs, opt)
                if card is not None and card is lethal["target"]:
                    return LETHAL_BAND, "R-07: LETHAL Boss target"

        # R-07: 退却はリーサル計画の一部か否かで扱いを分ける
        if lethal["needs_retreat"]:
            if opt.type == OptionType.RETREAT:
                return LETHAL_BAND - 1, "R-07: LETHAL retreat (bench attacker plan)"
            if (ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}
                    and getattr(opt, 'playerIndex', yi) == yi):
                card = option_card(obs, opt)
                if card is not None and card is lethal["attacker"]:
                    return LETHAL_BAND - 1, "R-07: LETHAL promote attacker"
        else:
            if opt.type == OptionType.RETREAT:
                return -100000, "R-07: don't break lethal (no retreat)"
        return score, reason

    def _apply_theta(self, score, reason):
        """学習済み強度 θ をバンド内加算として適用する（②選好スコアの学習の実体）。

        聖域ガード: 調整後のスコアが band_of() の帯を跨ぐ場合は適用しない。
        これにより θ は「正の選好同士の順位」「負のマスク同士の順位（強制充足時）」
        だけを動かせ、マスクの解除・新設・リーサル帯への昇格は構造的に不可能。
        apply_protocol の出力（R-07 系）には適用されない（呼び出し位置が手前のため）。"""
        theta = self.theta
        if not theta:
            return score
        adj = theta.get(reason)
        if not adj:
            return score
        band = band_of(score)
        if band == "lethal" or band == "error":
            # リーサル帯は帯内の順序（LETHAL_BAND と LETHAL_BAND-1 の関係）も守るため凍結。
            # kanga のように scorer から直接 LETHAL_BAND を出す経路があってもここで守られる。
            return score
        new = score + adj
        if band_of(new) != band:
            return score
        return new

    def score_option(self, obs, opt):
        ctx = obs.select.context

        if ctx in {SelectContext.IS_FIRST, SelectContext.MULLIGAN,
                   SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON}:
            score, reason = self.score_setup_context(obs, opt)
            return self._apply_theta(score, reason), reason

        if opt.type in {OptionType.YES, OptionType.NO}:
            score, reason = self.score_yes_no(obs, opt)
            return self._apply_theta(score, reason), reason

        if opt.type == OptionType.NUMBER:
            score, reason = self.score_number(obs, opt)
            return self._apply_theta(score, reason), reason

        # フェーズ分岐（S-0 の現在値で切替。判定は常時、反応をフェーズで変える）
        if self.t["phase"] == "combat":
            score, reason = self.score_combat(obs, opt)
        else:
            score, reason = self.score_setup(obs, opt)

        score, reason = self.mask_extra(obs, opt, score, reason)
        score, reason = self.apply_overrides(obs, opt, score, reason)
        score, reason = self._r30_default_item(obs, opt, score, reason)
        score, reason = self._r31_promote_free(obs, opt, score, reason)
        score = self._apply_theta(score, reason)
        return self.apply_protocol(obs, opt, score, reason)

    def _r31_promote_free(self, obs, opt, score, reason):
        """R-31（2026-07-24 一般ルール・ユーザー決定）: バトル場が空いた時（KO 後の
        強制前出し = TO_ACTIVE）、**にげエネ 0 のベンチがいれば常にそれを出す**。

        根拠: 自分の手番中はにげる（コスト0 = 無料）でいつでも本命に並べ替えられる
        ため、前出し時点で選択肢を一切失わない支配的な手 — 数少ないゲーム理論的に
        厳密な優先則（ユーザー命名）。デッキ毎の前出し表より上の帯 45000 で確定させる。
        ガード:
          - 自分側の選択のみ（相手側 TO_ACTIVE = ボス吊り先はデッキ則のまま）
          - 負帯（デッキの保護マスク）と R-08 敗北リーチ駒には適用しない
          - SWITCH（自発的な入れ替え先 = デッキの意図した本命選び）は対象外
          - クラス属性 R31_OPT_OUT = True のデッキは不適用（chandelure: 3標本一貫で
            −2pt 超 = 王者ゲート抵触。ミル即時性と自前の重力宝石がにげ0前提を崩す）"""
        if not R31_ENABLED or getattr(self, "R31_OPT_OUT", False) or score < 0:
            return score, reason
        if obs.select.context != SelectContext.TO_ACTIVE:
            return score, reason
        yi = obs.current.yourIndex
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        if pi != yi:
            return score, reason
        card = option_card(obs, opt)
        if card is None or retreat_cost(card) != 0 or self.is_threatened(card):
            return score, reason
        # にげ0候補が複数いる時はデッキの序列（元スコア）を 1/10 スケールで保存する
        # （v1 の 45000 均一はチャンデラの「エネ付き Comfey 優先」を壊して −2.1pt だった）
        return 45000 + max(0.0, score) / 10.0, "R-31: promote free-retreat"

    def _r30_default_item(self, obs, opt, score, reason):
        """R-30（2026-07-21 一般ルール・ユーザー決定）: **使用可能なグッズは使用する**。

        デッキが意見を持たなかった（score == 0 の素通し）PLAY のグッズ（CardType.ITEM）
        だけを低正帯 400 へ持ち上げる = 「グッズを握ったまま end」の枝を原則消す。
        Gate A 監査の最大ギャップ族（温存過剰: hold Switch 139 / Trimmer 66 / 死にポフィン
        69 …）の一般化。継承はコードパスで自動: デッキの明示スコア（正帯の意図・負帯の
        温存則）が常に先勝ちし、無意見の札だけが対象になる。

        ガード（2026-07-21 設計合意）:
          - ACE SPEC は対象外（1枚きり・不可逆はデッキの明示判断に委ねる）
          - 対 LO アーキでは発動しない（山札=寿命。R-28 と同じ停止条件）
          - 自分の山札 8 枚未満では発動しない（粗い R-11。精密な山札規律はデッキ側）
        帯 400 = 学習帯: end(0) には必ず勝ち、デッキが意図して並べた行動（進化・エネ・
        攻撃・1000 帯以上）は決して追い越さない。トグル = 環境変数 R30（既定 ON）。"""
        if not R30_ENABLED or score != 0:
            return score, reason
        if obs.select.context != SelectContext.MAIN or opt.type != OptionType.PLAY:
            return score, reason
        card = option_card(obs, opt)
        if card is None:
            return score, reason
        data = CARD_DB.get(card.id)
        if data is None or int(getattr(data, "cardType", -1)) != int(CardType.ITEM):
            return score, reason
        if getattr(data, "aceSpec", False):
            return score, reason
        if self.t["matchup"] in mt.LO_ARCHETYPES:
            return score, reason
        if getattr(my_state(obs), "deckCount", 99) < 8:
            return score, reason
        return 400, "R-30: use available item"

    def update_belief(self, obs):
        """判定4種の毎手番更新（状態推定＝belief の縫い目。推定器の差し替えはここ）。
        不変条件: matchup → phase → lethal → threats の順を崩さないこと
        （judge_loss_threats / opp_max_damage が self.t["matchup"] を読むため）。"""
        self.t["matchup"] = self.detect_matchup(obs)                       # R-20
        self.t["phase"] = "combat" if self.judge_subgoal(obs) else "setup"  # S-0
        self.t["lethal"] = self.judge_lethal(obs)                          # R-07
        self.t["threats"] = self.judge_loss_threats(obs)                   # R-08

    def _sequencing_override(self, obs, scored):
        """R-26/R-28（2026-07-13 新設）: ドロー系プレイの直前に「先に済ませるべき手」を
        割り込ませる。リプレイ 85690212 の一般不具合（手張り権を残したままアンフェア
        スタンプ）の対策。デッキ毎のスコア帯に依存しない「正帯同士の順序入れ替え」のみ:
        ドロー札は選ばれ損ねるのではなく、割り込んだ手の実行後の決定で再び最上位に残る。

          R-26 手張り先行: 手札リフレッシュ札（アンフェアスタンプ/リーリエ等 = 手札を
               山へ戻す）を打つ前に、未使用のエネ手張りを済ませる（戻すと手札のエネが
               山へ消える。先に張れば確実に1加速）。
          R-28 山札圧縮先行: ドロー札の前に山札圧縮アイテム（確定サーチ）を使い、
               山の質を上げる。手札リフレッシュの前は盤面直行サーチ（ポフィン等）のみ
               （手札行きサーチは戻されて無駄）。相手が LO アーキタイプと確認できたら
               （R-20）停止 — LO 相手では山札=寿命なので不要な山消費をしない。

        聖域との関係: リーサル成立時は発動しない（R-07 の昇格が常に勝つ）。対象も
        割り込み先も正帯のみ = マスク（負帯）の解除は構造上ない。"""
        if obs.select.context != SelectContext.MAIN or obs.select.maxCount != 1:
            return None
        if self.t["lethal"] is not None:
            return None
        if not scored:
            return None
        top_score, top_i, _ = scored[0]
        if not (0 < top_score < LETHAL_BAND - 1):
            return None
        top_opt = obs.select.option[top_i]
        if top_opt.type != OptionType.PLAY:
            return None
        card = option_card(obs, top_opt)
        if card is None:
            return None
        refresh = card.id in mt.HAND_REFRESH_IDS
        if not refresh and card.id not in mt.DRAW_SUPPORT_IDS:
            return None

        # R-26: エネ手張りが未使用なら先に張る（最上位の正帯 ATTACH エネを採用）
        if refresh and not obs.current.energyAttached:
            for s, i, _ in scored[1:]:
                if s <= 0:
                    break
                o = obs.select.option[i]
                if o.type == OptionType.ATTACH:
                    c = option_card(obs, o)
                    if c is not None and c.id in self.ENERGY_IDS:
                        return i, "R-26: attach before hand refresh"

        # R-28: 圧縮アイテムを先に使う（LO 相手と確認できたら停止）
        if self.t["matchup"] in mt.LO_ARCHETYPES:
            return None
        thin_ids = (mt.THIN_TO_BOARD_IDS if refresh
                    else (mt.THIN_TO_BOARD_IDS | mt.THIN_TO_HAND_IDS))
        for s, i, _ in scored[1:]:
            if s <= 0:
                break
            o = obs.select.option[i]
            if o.type == OptionType.PLAY:
                c = option_card(obs, o)
                if c is not None and c.id in thin_ids:
                    return i, "R-28: thin deck before draw"
        return None

    def _maybe_search(self, obs, scored):
        """ターン内探索の許可判定と実行。探索しない/できない/失敗 → None（ルール順位のまま）。

        聖域との関係: リーサル成立時（t["lethal"]）は探索しない = R-07 の昇格が常に勝つ。
        候補は正帯（score >= 0）のみ = マスク（負帯）を探索が復活させることは構造上ない。"""
        if not self.search_enabled:
            return None
        if self.t["lethal"] is not None:
            return None
        if obs.select.context != SelectContext.MAIN or obs.select.maxCount != 1:
            return None
        cands = [(i, s) for s, i, r in scored if 0 <= s < 100_000]
        cands = cands[:self.SEARCH_MAX_CANDIDATES]
        if len(cands) < self.SEARCH_MIN_CANDIDATES:
            return None
        if cands[0][1] - cands[1][1] >= self.SEARCH_SKIP_MARGIN:
            return None                   # ルールが確信している自明な手
        if self._search_time_used >= self.SEARCH_GAME_BUDGET:
            return None
        if (self.overage_remaining is not None
                and self.overage_remaining < self.SEARCH_MIN_OVERAGE):
            return None
        DIAG["search_calls"] += 1
        try:
            if self._searcher is None:
                # 遅延 import（起動時の失敗を探索時に局所化 = R-01）。ローカル評価で複数
                # エージェントを同一プロセスに載せると sys.path 順で他機の copy に解決される
                # ことがあるが、sync_base がハッシュ同一を保証しているため無害。
                import turn_search
                self._searcher = turn_search.TurnSearcher(self)
            best = self._searcher.choose_root(obs, cands)
        except Exception:
            DIAG["search_errors"] += 1
            import traceback
            DIAG["last_search_error"] = traceback.format_exc(limit=5)
            return None
        if best is None:
            return None
        DIAG["search_used"] += 1
        return best

    def _ensure_net(self):
        """policy_net.npz の遅延ロード（1回だけ試す）。訓練/評価ハーネスが self._net を
        直接注入している場合はそれを使う。不在・版不一致・例外 → None = ルール順位。"""
        if self._net is not None or self._net_load_tried:
            return self._net
        self._net_load_tried = True
        try:
            # 遅延 import（turn_search と同じ。他機 dir の copy に解決されても
            # sync_base がハッシュ同一を保証。npz はポリシー基準のパスから読む）
            import policy_net
            self._net = policy_net.load_for_policy(self)
        except Exception:
            self._net = None
        return self._net

    def _maybe_net(self, obs, scored):
        """方策ネットによる候補再ランク。対象外/不在/失敗 → None（ルール順位のまま）。

        聖域との関係は探索と同一: リーサル成立時は呼ばない（R-07 の昇格が常に勝つ）、
        候補は正帯（0 <= score < 100_000）のみ = マスク（負帯）の復活は構造上ない。
        デプロイは argmax（決定的）。net_sample はハーネス専用（訓練時の探索）。"""
        if not self.net_enabled:
            return None
        if self.t["lethal"] is not None:
            return None
        if obs.select.context != SelectContext.MAIN or obs.select.maxCount != 1:
            return None
        cands = [(i, s, r) for s, i, r in scored if 0 <= s < 100_000]
        cands = cands[:self.NET_MAX_CANDIDATES]
        if len(cands) < 2:
            return None
        net = self._ensure_net()
        if net is None:
            return None
        DIAG["net_calls"] += 1
        try:
            import numpy as np
            X = net.features(obs, cands)
            logits = net.logits(X)
            z = logits - logits.max()
            p = np.exp(z)
            p /= p.sum()
            if self.net_sample and self.net_rng is not None:
                k = int(self.net_rng.choice(len(p), p=p))
            else:
                k = int(np.argmax(logits))
            if self.net_log is not None:
                self.net_log.append({
                    "X": X,
                    "k": k,
                    "logp": float(np.log(max(float(p[k]), 1e-12))),
                    "cand_idx": [i for i, _, _ in cands],
                    "reasons": [r for _, _, r in cands],
                    "scores": [s for _, s, _ in cands],
                    "turn": getattr(obs.current, "turn", None),
                })
        except Exception:
            DIAG["net_errors"] += 1
            import traceback
            DIAG["last_net_error"] = traceback.format_exc(limit=5)
            return None
        DIAG["net_used"] += 1
        return cands[k][0]

    def choose(self, obs):
        # 判定は毎手番・常時実行（安いので常時。反応の強弱はフェーズと優先則側で制御）
        self.update_belief(obs)

        scored = []
        for i, opt in enumerate(obs.select.option):
            try:
                score, reason = self.score_option(obs, opt)
            except Exception as e:
                DIAG["option_errors"] += 1
                score, reason = -999999, f"error {type(e).__name__}: {e}"
            scored.append((score, i, reason))

        scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

        # R-26/R-28: ドロー系プレイの前の順序割り込み（決定的ルール = 探索/ネットより先）
        seq = self._sequencing_override(obs, scored)
        if seq is not None:
            selected = [seq[0]]
            if self.decision_log is not None:
                rec = self._decision_record(obs, scored, selected, False)
                rec["sequencing"] = seq[1]
                self.decision_log.append(rec)
            return selected

        # ターン内探索（許可条件を満たす MAIN のみ。失敗は必ずルール順位に縮退 = R-01）
        best_search = self._maybe_search(obs, scored)
        if best_search is not None:
            selected = [best_search]
            if self.decision_log is not None:
                self.decision_log.append(
                    self._decision_record(obs, scored, selected, False))
            return selected

        # 方策ネット（探索と同じ許可条件。npz 不在なら常に None = 挙動不変）
        best_net = self._maybe_net(obs, scored)
        if best_net is not None:
            selected = [best_net]
            if self.decision_log is not None:
                self.decision_log.append(
                    self._decision_record(obs, scored, selected, False))
            return selected

        # 負スコア = minCount 超過分では選ばない（マスクの表現）
        selected = []
        for score, i, reason in scored:
            if len(selected) >= obs.select.maxCount:
                break
            if score < 0 and len(selected) >= obs.select.minCount:
                continue
            selected.append(i)

        forced_fill = False
        if len(selected) < obs.select.minCount:
            selected = [i for _, i, _ in scored[:obs.select.minCount]]
            forced_fill = True

        if self.decision_log is not None:
            self.decision_log.append(
                self._decision_record(obs, scored, selected, forced_fill))

        return selected

    def _decision_record(self, obs, scored, selected, forced_fill):
        """決定ログ1件（JSONプリミティブのみ）。scored はソート済みタプル列を読むだけで
        score_option の再評価はしない（オプション評価の左→右順序依存を壊さないため）。
        options は元のオプション順（index 昇順）で出力する。sorted() は新リストを返すので
        scored 自体は不変（in-place の .sort() は選択順を壊すため禁止）。
        ここで例外を出すと make_agent の R-01 がフォールバックに落として挙動が変わるため、
        フィールド取得は防御的に書く（context は素の int のことがある — .name 直読み禁止）。"""
        ctx_i = int(obs.select.context)
        try:
            ctx_name = SelectContext(ctx_i).name
        except ValueError:
            ctx_name = str(ctx_i)
        return {
            "deck": self.DECK_NAME,
            "turn": getattr(obs.current, "turn", None),
            "ctx": ctx_i,
            "ctx_name": ctx_name,
            "phase": self.t["phase"],
            "matchup": self.t["matchup"],
            "lethal_route": (self.t["lethal"] or {}).get("route"),
            "n_threats": len(self.t["threats"]),
            "min_count": obs.select.minCount,
            "max_count": obs.select.maxCount,
            "forced_fill": forced_fill,
            "options": [
                {"i": i, "score": s, "reason": r, "band": band_of(s)}
                for s, i, r in sorted(scored, key=lambda x: x[1])
            ],
            "selected": list(selected),
        }


# ═══════════════════════════════ 安全ラッパー（R-01/R-02） ═══════════════════════════════

def make_agent(policy_cls):
    """永続ポリシーインスタンス + 絶対にクラッシュしない agent() を生成する。"""
    policy = policy_cls()

    def agent(obs_dict):
        DIAG["decisions"] += 1
        try:
            try:
                policy.overage_remaining = obs_dict.get("remainingOverageTime")
            except AttributeError:
                policy.overage_remaining = getattr(
                    obs_dict, "remainingOverageTime", None)
            obs = to_observation_class(obs_dict)
            if obs.select is None:
                policy.reset_game()
                deck = read_deck_csv()
                policy.my_deck_list = list(deck)   # 探索の決定化に使う自リスト
                return deck
            policy.track_logs(obs)
            if not obs.select.option:
                return []
            out = policy.choose(obs)
            DIAG["policy_ok"] += 1
            return out
        except Exception:
            DIAG["errors"] += 1
            return legal_fallback_from_dict(obs_dict)

    agent.policy = policy
    agent.diag = DIAG
    return agent
