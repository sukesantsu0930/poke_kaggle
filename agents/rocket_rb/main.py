"""ロケット団（Team Rocket's Spidops + Mewtwo ex）ルールベースエージェント — 最小構成 v1

リスト = lolzpo emonga の 2026-07-15 実リスト（22戦 17-5 = 77.3%、当日勝率首位の急伸アーキ）。
設計文書: docs/planning/デッキ設計_ロケット団.md（センサス・カード効果・優先則の骨子）

コンセプト:
  ランス+アテナで盤面をロケット団で埋め、主砲ワナイダー（非ex・サイド1）が
  ロケットラッシュ = 場のロケット団×30（満面180）を2エネで連打。チャージアップが
  毎ターントラッシュから無料加速するので息切れしない。大物はミュウツーex 160。
  相手のex/メガ（サイド2〜3）とのプライズレース有利が勝ち筋。

v1 の割り切り（デッキ設計md「未決事項」）:
  - 上位ドクトリン採掘は未実施 = スコア数値は暫定
  - イレイザーボールの任意トラッシュ（+60×2）は常に選ばない（リーサルは160の保守値）
  - ミミッキュのほうせきごっこは撃たない（コピー打点の評価が要る）
  - サカキ吊り出しは v1.2 で統合済み（div-RK7: 9200 帯 + judge_lethal の route=="sakaki"）
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

from cg.api import AreaType, CardType, OptionType, SelectContext

import meta_tables as mt
from policy_base import (
    AttackPlan,
    BasePolicy,
    CARD_DB,
    DIAG,
    LETHAL_BAND,
    active_pokemon,
    all_my_pokemon,
    energy_count,
    get_card,
    hand_ids,
    has_tool,
    is_ex,
    make_agent,
    my_state,
    opp_active_pokemon,
    opp_bench_pokemon,
    opp_state,
    option_card,
    option_target,
    prize_value,
    read_deck_csv as _read_deck_csv,
    retreat_cost,
    weakness_value,
)

# ── カードID（デッキ設計_ロケット団.md のリスト） ──

TAROUNTULA = 400      # タマンチュラ HP50 {G} にげ1（→ワナイダー）
SPIDOPS = 401         # ワナイダー HP130 {G} にげ2。特性チャージアップ=トラッシュの基本エネを自分へ
ARTICUNO = 414        # フリーザー HP120 {W} にげ1。特性レジストヴェール=たねロケット団に技効果無効
MEWTWO = 431          # ミュウツーex HP280 にげ3。パワーセーバー=ロケット団4匹未満で技不可
MIMIKYU = 434         # ミミッキュ HP60 にげ0（無料ピボット枠）

BUG_CATCH = 1094      # むしとりセット: 山上7枚から草ポケ+草エネ2枚
HYPER_BALL = 1121     # ハイパーボール: 手札2捨て・何でもサーチ（ミュウツー唯一のサーチ）
RECEIVER = 1134       # レシーバー: ロケット団サポートをサーチ
POKE_PAD = 1152       # ポケパッド: 非ルール持ちポケモンをサーチ（ミュウツー不可）
HERO_CAPE = 1159      # ヒーローマント: +100HP（ACE SPEC）
BANGLE = 1175         # ブレイブバングル: 非ルール持ちの対exバトル場+30
ATHENA = 1216         # アテナ: 手札5枚（場が全ロケット団なら8枚）まで引く
APOLLO = 1217         # アポロ: 自分のロケット団きぜつの返しのみ。両者手札リセット 自5/相3
SAKAKI = 1218         # サカキ: 自分バトル場⇔ベンチ入替 + 相手ベンチ吊り出し（ボス代替）
LANCE = 1220          # ランス: たねロケット団を3枚までサーチ（先攻1ターン目でも使える）
LILLIE = 1227         # リーリエの決心: 手札を山に戻して6ドロー
FACTORY = 1257        # ファクトリー: ロケット団サポートを使った番に1回2ドロー

GRASS = 1
WATER = 3
ROCKET_E = 15         # ロケット団エネルギー: ロケット団専用・{P}{D} 2個ぶん

ATK_TAKE_DOWN = 559   # タマンチュラ {G} 30（自傷10）
ATK_ROCKET_RUSH = 560  # ワナイダー {G}C 場のロケット団×30
ATK_DARK_FROST = 583  # フリーザー {W}CC 60 +ロケットエネ付きなら+60
ATK_ERASURE = 608     # ミュウツー {P}{P}C 160 +任意ベンチエネトラッシュ×60（v1不使用）
ATK_MIMICRY = 612     # ミミッキュ {P}C コピー（v1不使用）

ROCKET_POKES = {TAROUNTULA, SPIDOPS, ARTICUNO, MEWTWO, MIMIKYU}
BASICS = {TAROUNTULA, ARTICUNO, MEWTWO, MIMIKYU}
ROCKET_SUPPORTERS = {ATHENA, APOLLO, SAKAKI, LANCE}

# ── Gate A 監査トグル（2026-07-17 rule_audit の div 連番。設計md「div記録」参照） ──
# 負帯の解錠 = BC 学習の被覆率回復が狙い。採用基準は L2 非劣化 ∧ check_agent 合格。
ROC_RK1A = os.environ.get("ROC_RK1A", "1") != "0"  # div-RK1a: タマンチュラ先行チャージ units<2（技コスト{G}C=2個ぶん整合）
ROC_RK3 = os.environ.get("ROC_RK3", "1") != "0"    # div-RK3: レシーバー在庫1枚（今番使えば枯れる）でも使用可
ROC_RK5A = os.environ.get("ROC_RK5A", "1") != "0"  # div-RK5a: チャージアップ満タン時も低帯で常時許可（無料アクション）
ROC_RK6 = os.environ.get("ROC_RK6", "1") != "0"    # div-RK6: ポケパッド combat 禁止閾値 rockets>=4 → >=6（盤面=打点）
# ── 第2弾（2026-07-18 rule_audit 第2サイクル。設計md v1.2 節参照） ──
# RK7 は挙動変更系（新しい行動価値の条件付き定義）= 単独 A/B。他は学習帯（低正帯の解錠）。
ROC_RK7 = os.environ.get("ROC_RK7", "1") != "0"    # div-RK7: サカキ吊り出しKO 9200 + リーサル統合
ROC_RK2A = os.environ.get("ROC_RK2A", "1") != "0"  # div-RK2a: 無料にげる（実効コスト0）1500
ROC_RK2B = os.environ.get("ROC_RK2B", "1") != "0"  # div-RK2b: 被KO圏×ベンチ撃てる時の脱出にげる 1300
ROC_RK4 = os.environ.get("ROC_RK4", "1") != "0"    # div-RK4: リーリエ死に手札リセット 300（end直上）
ROC_RK9 = os.environ.get("ROC_RK9", "1") != "0"    # div-RK9: ロケットエネ→タマンチュラ 7200（在庫条件）
ROC_RK10 = os.environ.get("ROC_RK10", "1") != "0"  # div-RK10: バングル非ルール持ち全般 低帯
# 自軍アタッカーの攻撃タイプ（弱点計算はアタッカー毎。クラス属性1本だと
# ミュウツーの超打点まで草弱点で2倍にしてしまう）
ATTACKER_TYPE = {TAROUNTULA: 1, SPIDOPS: 1, ARTICUNO: 3, MEWTWO: 5, MIMIKYU: 5}


def attached_ids(pk):
    return [c.id for c in (getattr(pk, "energyCards", None) or [])]


def eff_units(pk):
    """色を無視した実効エネ個数（ロケット団エネ=2個ぶん）。"""
    return sum(2 if i == ROCKET_E else 1 for i in attached_ids(pk))


class RocketPolicy(BasePolicy):
    DECK_NAME = "rocket"
    GO_FIRST = True            # R-21【暫定】展開デッキ+先攻ランス可（設計md参照）
    TAKE_MULLIGAN = True       # R-22【ハード・プロジェクト決定】
    ATTACKER_IDS = {SPIDOPS, MEWTWO, ARTICUNO}
    ENERGY_IDS = {GRASS, WATER, ROCKET_E}
    LINE_PROTECT_IDS = {SPIDOPS, MEWTWO}   # R-13: 最後の主砲/フィニッシャーを守る

    def __init__(self):
        super().__init__()
        self.p = {}

    # ═══════════════ ターン分析（軽量: 枚数と旗だけ） ═══════════════

    def choose(self, obs):
        self.p = self._analyze(obs)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        fc = defaultdict(int)
        hc = defaultdict(int)
        dc = defaultdict(int)
        for pk in (ms.active + ms.bench):
            if pk is not None:
                fc[pk.id] += 1
        for c in (ms.hand or []):
            if c is not None:
                hc[c.id] += 1
        for c in (ms.discard or []):
            if c is not None:
                dc[c.id] += 1
        hand_size = len(ms.hand) if ms.hand else ms.handCount
        stadium_id = 0
        for c in obs.current.stadium:
            stadium_id = c.id
        rockets = sum(1 for pk in (ms.active + ms.bench)
                      if pk is not None and pk.id in ROCKET_POKES)
        safe_draws = ms.deckCount - len(ms.prize) - 1
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "stadium_id": stadium_id,
            "safe_draws": safe_draws, "rockets": rockets,
            "hand_basics": sum(hc[i] for i in BASICS),
            "spid_line": fc[TAROUNTULA] + fc[SPIDOPS],
            "opp_hand": opp_state(obs).handCount,
        }

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ エネ勘定（ロケット団エネ=2個ぶん・色対応） ═══════════════

    def _payable(self, obs, pk):
        """色を考慮して実際に撃てる技のリスト。基盤の枚数ベース payable_attacks は
        ロケット団エネの2個ぶん勘定を数えられないため全面差し替え。"""
        if pk is None:
            return []
        ids = attached_ids(pk)
        units = sum(2 if i == ROCKET_E else 1 for i in ids)
        out = []
        if pk.id == TAROUNTULA and GRASS in ids:
            out.append(ATK_TAKE_DOWN)
        if pk.id == SPIDOPS and GRASS in ids and units >= 2:
            out.append(ATK_ROCKET_RUSH)
        if pk.id == ARTICUNO and WATER in ids and units >= 3:
            out.append(ATK_DARK_FROST)
        if (pk.id == MEWTWO and ROCKET_E in ids and units >= 3
                and self.p.get("rockets", 0) >= 4):    # パワーセーバー
            out.append(ATK_ERASURE)
        return out

    def attack_damage(self, obs, attacker, attack_id):
        if attack_id == ATK_ROCKET_RUSH:
            return 30 * sum(1 for pk in all_my_pokemon(obs) if pk.id in ROCKET_POKES)
        if attack_id == ATK_DARK_FROST:
            return 60 + (60 if ROCKET_E in attached_ids(attacker) else 0)
        if attack_id == ATK_ERASURE:
            return 160        # 任意トラッシュ+60×2 は v1 不使用（保守値）
        if attack_id == ATK_TAKE_DOWN:
            return 30
        return 0              # ほうせきごっこ等

    def guard_damage(self, base_damage, attacker, target):
        # 弱点はアタッカー毎のタイプで計算（ATTACK_ENERGY_TYPE 1本では
        # ミュウツーの超打点まで草弱点2倍になるため基盤実装を差し替え）
        if target is not None and target.id in mt.IMMUNE_TO_EX_ACTIVE and is_ex(attacker):
            return 0
        atype = ATTACKER_TYPE.get(attacker.id) if attacker is not None else None
        if atype is not None and target is not None and weakness_value(target) == atype:
            return base_damage * 2
        return base_damage

    def plan_attacks(self, obs):
        plans = []
        active = active_pokemon(obs)
        if active is not None:
            for aid in self._payable(obs, active):
                plans.append(AttackPlan(active, aid, self.attack_damage(obs, active, aid)))
        if (active is not None and not obs.current.retreated
                and energy_count(active) >= retreat_cost(active)):
            for p in my_state(obs).bench:
                if p is None or p.id not in self.ATTACKER_IDS:
                    continue
                for aid in self._payable(obs, p):
                    plans.append(AttackPlan(p, aid, self.attack_damage(obs, p, aid),
                                            needs_retreat=True))
        return plans

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 撃てるアタッカー（色対応の実効エネ勘定）が場に1体以上。"""
        return any(self._payable(obs, pk) for pk in all_my_pokemon(obs))

    # ── E-2: 今ターン攻撃させたいポケモン ──

    def _attack_rank(self, obs, pk):
        """(kills, dmg, aid)。KOできる技 > 最大打点。"""
        opp_act = opp_active_pokemon(obs)
        best = (0, -1, None)
        for aid in self._payable(obs, pk):
            dmg = self.attack_damage(obs, pk, aid)
            if opp_act is not None:
                dmg = self.guard_damage(dmg, pk, opp_act)
            kills = 1 if (opp_act is not None and dmg >= opp_act.hp) else 0
            if (kills, dmg) > best[:2]:
                best = (kills, dmg, aid)
        return best

    def _desired_attacker(self, obs):
        act = active_pokemon(obs)
        best_pk, best_rank = act, self._attack_rank(obs, act) if act else (0, -1, None)
        pivot_ok = (
            (act is not None and not obs.current.retreated
             and energy_count(act) >= retreat_cost(act))
            or (SAKAKI in [c.id for c in (my_state(obs).hand or []) if c]
                and not obs.current.supporterPlayed))
        if not pivot_ok:
            return best_pk, best_rank
        for pk in my_state(obs).bench:
            if pk is None or pk.id not in self.ATTACKER_IDS:
                continue
            r = self._attack_rank(obs, pk)
            if self.is_threatened(pk) and not r[0]:
                continue
            if r[:2] > best_rank[:2]:
                best_pk, best_rank = pk, r
        return best_pk, best_rank

    # ═══════════════ div-RK7: サカキ吊り出しKO（挙動変更系・単独A/B） ═══════════════
    # サカキ(1218)の自分側入替は必須（"If you do" = 吊り出しは入替の条件付きおまけ）。
    # → 入替後に撃てるのはベンチの撃てるアタッカーのみ。前提条件はベンチ側で判定する。

    def _sakaki_gust_ko(self, obs, min_prize=0):
        """(target, attacker, attack_id) or None。相手ベンチに
        「ベンチアタッカーの実効打点 >= 残HP」の個体が居るか（サイド価値→低HP順）。"""
        plans = [(pk, aid, self.attack_damage(obs, pk, aid))
                 for pk in my_state(obs).bench if pk is not None
                 for aid in self._payable(obs, pk)]
        if not plans:
            return None
        best = None
        for target in opp_bench_pokemon(obs):
            if prize_value(target) < min_prize:
                continue
            for pk, aid, dmg in plans:
                eff = self.guard_damage(dmg, pk, target)
                if eff >= target.hp:
                    key = (prize_value(target), -target.hp, eff)
                    if best is None or key > best[0]:
                        best = (key, target, pk, aid)
        if best is None:
            return None
        return best[1], best[2], best[3]

    def _active_ko_prize(self, obs):
        """サカキ無しで相手バトル場をKOできるならそのサイド価値、できなければ0。
        div-RK7 の温存ガード入力（同価値のKOが既にあるならサカキ3枚を温存）。"""
        opp_act = opp_active_pokemon(obs)
        if opp_act is None:
            return 0
        for plan in self.plan_attacks(obs):
            if self.guard_damage(plan.damage, plan.attacker, opp_act) >= opp_act.hp:
                return prize_value(opp_act)
        return 0

    def judge_lethal(self, obs):
        """R-07 に div-RK7 のサカキ吊りKO経路を追加（mt.BOSS 経路は基盤のまま）。"""
        lethal = super().judge_lethal(obs)
        if lethal is not None or not ROC_RK7:
            return lethal
        if obs.current.supporterPlayed or SAKAKI not in hand_ids(obs):
            return None
        ko = self._sakaki_gust_ko(obs, min_prize=len(my_state(obs).prize))
        if ko is None:
            return None
        target, attacker, aid = ko
        return {"route": "sakaki", "target": target, "attacker": attacker,
                "attack_id": aid, "needs_retreat": False}

    def apply_protocol(self, obs, opt, score, reason):
        """route=="sakaki" の昇格を追加（基盤の boss 経路と同型。ATTACK 昇格と
        RETREAT ブロックは基盤の共通処理がそのまま効く）。"""
        lethal = self.t.get("lethal")
        if lethal is not None and lethal.get("route") == "sakaki":
            yi = obs.current.yourIndex
            if opt.type == OptionType.ATTACK:
                # 基盤 R-07 の ATTACK 昇格（attackId 一致）を抑止。ワナイダーは4枚積みで
                # attackId を共有するため、サカキ未使用のうちにバトル場ワナイダーの通常攻撃
                # が LETHAL_BAND へ昇格し PLAY サカキと同点タイ（先頭 index 勝ち）→ 相手
                # バトル場を殴ってターン終了 = リーサル破棄の誤爆があった。サカキ解決後は
                # route が再計算で消える（サカキが手札を離れる）ので KO 攻撃は E-1 2400 で成立
                return score, reason
            if opt.type == OptionType.PLAY:
                card = option_card(obs, opt)
                if card is not None and card.id == SAKAKI:
                    return LETHAL_BAND, "div-RK7: LETHAL Sakaki"
            if obs.select.context in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
                card = option_card(obs, opt)
                if getattr(opt, "playerIndex", yi) != yi:
                    if card is not None and card is lethal["target"]:
                        return LETHAL_BAND, "div-RK7: LETHAL Sakaki target"
                elif card is not None and card is lethal["attacker"]:
                    return LETHAL_BAND - 1, "div-RK7: LETHAL promote attacker"
        return super().apply_protocol(obs, opt, score, reason)

    # ═══════════════ セットアップコンテキスト（S-1） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # タマンチュラ前 = T2 進化→即主砲。ミミッキュはにげ0で無料ピボット
            table = {TAROUNTULA: 10, MIMIKYU: 9, ARTICUNO: 8, MEWTWO: 7}
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # 盤面数=打点のデッキ: 出せるたねは全部出す（crustle C-3 と同型）
            card = option_card(obs, opt)
            if card is not None and card.id in BASICS:
                return 100, "S-1b: setup bench all rockets"
            return -10000, "setup: bench other"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    # ═══════════════ 優先則（純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        yi = obs.current.yourIndex

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == SPIDOPS:
                # チャージアップ: トラッシュの基本エネを自分へ（無料加速）
                if card is not None and eff_units(card) < 2:
                    return 28500, "S-5: Charge Up (fuel Spidops)"
                if ROC_RK5A and card is not None:
                    # div-RK5a: 満タンでも常時許可（無料・トラッシュの草回収は資源プラス。
                    # にげる原資/イレイザーボールの弾。lolzpo 純度100%シグナル）
                    return 2000, "div-RK5a: Charge Up (stockpile)"
                return -1, "R-10: Spidops fueled (Charge Up)"
            if cid == FACTORY:
                if self._safe_draws() >= 2:
                    return 28000, "Factory draw 2"
                return -1, "R-11: deck thin (Factory)"
            return -1, "skip foreign ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            if card is not None and card.id == SPIDOPS:
                tgt = option_target(obs, opt)
                bonus = 100 if (tgt is not None and energy_count(tgt) >= 1) else 0
                return 25000 + bonus, "S-3: evolve Spidops"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            return self._score_retreat(obs)

        if opt.type == OptionType.ATTACK:
            return self._score_attack(obs, opt)

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

    # ── RETREAT ──

    def _score_retreat(self, obs):
        active = active_pokemon(obs)
        if active is None:
            return -100, "no active"
        desired, _ = self._desired_attacker(obs)
        if desired is not None and desired is not active:
            # サカキ（8900）があればそちらが先に選ばれる（エネ消費なし+吊り出し付き）
            return 1900, "E-2: retreat to promote attacker"
        bench_ready = any(pk is not None and self._payable(obs, pk)
                          for pk in my_state(obs).bench)
        if not self._payable(obs, active) and bench_ready:
            return 2000, "unstick: retreat dead active"
        if ROC_RK2A and retreat_cost(active) == 0:
            # div-RK2a: 無料にげる（ミミッキュ等）— 設計mdの「無料ピボット枠」の実装。
            # エネを捨てないので資源損ゼロ。往復振動はエンジンの1ターン1回制限が抑止
            return 1500, "div-RK2a: free retreat (cost 0)"
        if (ROC_RK2B and bench_ready
                and self.opp_max_damage(obs) >= active.hp):
            # div-RK2b: 被KO圏の前をベンチの撃てるアタッカーへ退避（エネ支払いは許容。
            # 学習帯 = ピボット1900/詰み解消2000より下、攻撃1200帯より上）
            return 1300, "div-RK2b: escape KO range"
        return -100, "avoid retreat"

    # ── ATTACK（E-1） ──

    def _score_attack(self, obs, opt):
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        opp_act = opp_active_pokemon(obs)
        dmg = self.attack_damage(obs, active, aid) if active else 0
        eff = self.guard_damage(dmg, active, opp_act) if opp_act is not None else dmg
        if opp_act is not None and eff >= opp_act.hp:
            return 2400, "E-1: KO attack"
        return 1200 + min(eff, 800) // 2, "E-1: attack (max damage)"

    # ── PLAY ──

    def _score_play(self, obs, opt, combat):
        p = self.p
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        cid = card.id
        data = CARD_DB.get(cid)
        fc, hc = p["fc"], p["hc"]

        if data is not None and data.cardType == CardType.POKEMON:
            # 盤面数=打点（ロケットラッシュ×30・アテナ8枚・パワーセーバー解禁）→ 絞らない
            if cid in BASICS:
                table = {TAROUNTULA: 18100, MEWTWO: 17900, ARTICUNO: 17800, MIMIKYU: 17600}
                if cid == ARTICUNO and fc[ARTICUNO] >= 1:
                    return 17500, "S-2: bench 2nd Articuno"   # ヴェールは1体で全員有効
                base = table.get(cid, 17000)
                return (base if not combat else base - 4000), "S-2: bench rocket (board=damage)"
            return -5000, "play: unexpected pokemon"

        if cid == FACTORY:
            if p["stadium_id"] == FACTORY:
                return -1, "factory already up"
            return 13000, "S-2: Factory (draw engine)"

        # グッズ
        if cid == BUG_CATCH:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Bug Catch)"
            return (15800 if not combat else 12800), "S-4: Bug Catching Set"
        if cid == HYPER_BALL:
            need_mewtwo = (hc[MEWTWO] + fc[MEWTWO] == 0)
            if self._safe_draws() < 1 or p["hand_size"] < 3:
                return -1, "Hyper Ball: no fuel"
            if need_mewtwo:
                return (16800 if not combat else 12000), "S-4: Hyper Ball (find Mewtwo)"
            return -1, "save Hyper Ball"
        if cid == RECEIVER:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Receiver)"
            have = sum(hc[i] for i in ROCKET_SUPPORTERS)
            if have == 0:
                return (15500 if not combat else 11500), "S-4: Receiver (no rocket supporter)"
            if ROC_RK3 and have == 1:
                # div-RK3: 在庫1枚 = 今番使えば枯れる。翌番の弾込め+ファクトリー連続発動
                return 12000, "div-RK3: Receiver (restock last supporter)"
            return -1, "save Receiver"
        if cid == POKE_PAD:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Pad)"
            need = (fc[SPIDOPS] + hc[SPIDOPS] == 0) or (p["rockets"] < 4)
            if not combat:
                return (17000 if need else 7000), "S-4: Poke Pad"
            if need:
                return 11000, "S-4: Poke Pad"
            if ROC_RK6 and p["rockets"] < 6:
                # div-RK6: ロケットラッシュ=盤面×30。5〜6匹目(+30〜+60)を取りに行く。
                # 低帯 = 進化/手張りより下に置き干渉を避ける
                return 6500, "div-RK6: Poke Pad (fill board to 6)"
            return -1, "save Poke Pad (board full)"

        # サポート（択一）
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == LANCE:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Lance)"
            thin = p["rockets"] + p["hand_basics"] < 6
            if thin:
                return (16500 if not combat else 9000), "S-2: Lance (fetch 3 basics)"
            return 4700, "Lance: filler"
        if cid == ATHENA:
            draws = max(0, 8 - p["hand_size"])   # 場は常に全ロケット団 = 8枚まで
            if draws == 0 or self._safe_draws() < draws:
                return -1, "Athena: no draw / R-11"
            if p["hand_size"] <= 5:
                return (15000 if not combat else 5200), "E-5: Athena (main draw)"
            return -1, "Athena: hand big enough"
        if cid == SAKAKI:
            if ROC_RK7:
                ko = self._sakaki_gust_ko(obs)
                if ko is not None and self._active_ko_prize(obs) < prize_value(ko[0]):
                    # div-RK7: 吊り出しKOがバトル場KOよりサイド価値で上回る（or 唯一のKO）
                    # ときだけ 9200。同価値ならバトル場KO（E-1）を取りサカキ温存
                    return 9200, "div-RK7: Sakaki gust KO"
            desired, rank = self._desired_attacker(obs)
            active = active_pokemon(obs)
            if active is not None and desired is not None and desired is not active:
                return 8900, "E-2: Sakaki pivot + gust"
            if active is not None and not self._payable(obs, active) and rank[1] >= 0:
                return 8950, "unstick: Sakaki out of dead active"
            return -1, "save Sakaki"
        if cid == APOLLO:
            # 使える局面 = 自分のロケット団が前の相手番にきぜつ（エンジンが門番）
            if self._safe_draws() < 5:
                return -1, "R-11: deck thin (Apollo)"
            if p["hand_size"] <= 4 or p["opp_hand"] >= 5:
                return 5100, "E-6: Apollo (hand reset)"
            return -1, "save Apollo"
        if cid == LILLIE:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Lillie)"
            if p["hand_size"] <= 4:
                return 5300, "E-5: Lillie"
            if ROC_RK4:
                # div-RK4: 死に手札リセット — end(0) の直上 300。他の正帯（攻撃1200+・
                # にげる1300+・進化/手張り等）が1つでもあればそちらが勝つ = 「end 以外の
                # 正帯候補が無い番」だけ greedy で浮上する自己条件化。R-11 ガードは上で維持
                return 300, "div-RK4: Lillie (dead hand reset)"
            return -1, "E-5: Lillie"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10） ──

    def _score_attach(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        # どうぐ
        if cid == HERO_CAPE:
            if has_tool(target):
                return -1, "target has tool"
            table = {MEWTWO: 12800, SPIDOPS: 12000}
            if tid in table:
                return table[tid], "Hero's Cape (+100)"
            return -1, "save Hero's Cape"
        if cid == BANGLE:
            if has_tool(target):
                return -1, "target has tool"
            if tid == SPIDOPS:
                return 12400, "Brave Bangle on Spidops (+30 vs ex)"
            if ROC_RK10 and tid in ROCKET_POKES and tid != MEWTWO:
                # div-RK10: 非ルール持ち全般へ低帯拡張（ミュウツーex はルール持ち=効果対象外）。
                # フリーザー（ダークフロスト120→150）を微優先。序列は学習帯 = greedy では
                # ワナイダー12400が常に先勝ち、居ない盤面でのみ浮上
                return (600 if tid == ARTICUNO else 300), "div-RK10: Bangle non-rule-box"
            return -1, "save Bangle"

        if cid not in self.ENERGY_IDS:
            return -500, "skip non-energy"
        if obs.current.energyAttached:
            return -1, "already attached"

        ids = attached_ids(target)
        units = eff_units(target)
        desired, rank = self._desired_attacker(obs)

        if cid == GRASS:
            if tid == SPIDOPS:
                if GRASS not in ids or units < 2:
                    bonus = 100 if target is desired else 0
                    return 8500 + bonus, "S-5: grass -> Spidops"
                return -1, "R-10: Spidops fueled"
            # div-RK1a: 先行チャージ上限は技コスト{G}C=2個ぶんに一致させる
            # （units は eff_units = ロケットエネ2個ぶん勘定。序盤はトラッシュが
            #  空でチャージアップ不能 → 進化ターン即ロケットラッシュの唯一の手段）
            if tid == TAROUNTULA and units < (2 if ROC_RK1A else 1):
                return 8100, "S-5: pre-load Tarountula"
            return -1, "R-10: grass elsewhere"
        if cid == ROCKET_E:
            if tid == MEWTWO:
                if ROCKET_E not in ids:
                    return 8600, "S-5: Rocket Energy -> Mewtwo"
                if units < 3:
                    return 8550, "S-5: finish Mewtwo cost"
                return -1, "R-10: Mewtwo fueled"
            if tid == ARTICUNO and WATER in ids and ROCKET_E not in ids:
                return 8200, "S-5: Rocket Energy -> Articuno (+60)"
            if tid == SPIDOPS and GRASS in ids and units < 2:
                return 7400, "S-5: Rocket Energy fills colorless"
            if (ROC_RK9 and tid == TAROUNTULA and units == 0
                    and (self.p["hc"][ROCKET_E] >= 2
                         or self.p["fc"][MEWTWO] + self.p["hc"][MEWTWO] == 0)):
                # div-RK9: 1枚で2個ぶん（units は eff_units 勘定）= 進化ターン即ロケット
                # ラッシュ。在庫条件 = 手札に2枚目あり or ミュウツー不在（温存先が無い）。
                # 学習帯 7200 = 既存の全 正帯attach（7300〜8600）より下 = greedy 不変
                return 7200, "div-RK9: Rocket Energy -> Tarountula"
            return -1, "save Rocket Energy"
        if cid == WATER:
            if tid == ARTICUNO and WATER not in ids:
                return 8200, "S-5: water -> Articuno"
            if tid == SPIDOPS and GRASS in ids and units < 2:
                return 7300, "S-5: water fills colorless"
            return -1, "save water"
        return -1, "attach: no plan"

    # ── NUMBER（R-11 キャップ） ──

    def score_number(self, obs, opt):
        n = opt.number or 0
        if n > self._safe_draws():
            return -100 - n, "R-11: cap draw count"
        return n, "number"

    # ── CARD/ENERGY 選択（サーチ先・前出し・トラッシュ回収等） ──

    def _score_card(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex
        ctx = obs.select.context
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, "cardId", None)
        fc, hc = p["fc"], p["hc"]

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            if pi == yi:
                if card is None:
                    return 0, "promote none"
                kills, dmg, _ = self._attack_rank(obs, card)
                score = 8000 + kills * 6000 + min(max(dmg, 0), 990)
                if card.id == SPIDOPS:
                    score += 200      # 主砲（非ex・サイド1）を前に
                if kills:
                    return score, "E-2: promote killer (skip R-08)"
                return self.default_score_promote(obs, opt, score, "E-2: promote attacker")
            # 相手側（サカキ吊り出し）: 低HPのシステム札を引きずり出す
            hp = getattr(card, "hp", 999) if card else 999
            if ROC_RK7 and card is not None:
                # div-RK7: 今番の実効打点でKOできる吊り先を最優先（サイド価値→低HP。
                # judge_lethal の (prize, -hp) キーと同順 = リーサル経路と整合）
                best_eff = 0
                for pk in all_my_pokemon(obs):
                    for aid in self._payable(obs, pk):
                        eff = self.guard_damage(self.attack_damage(obs, pk, aid), pk, card)
                        best_eff = max(best_eff, eff)
                if best_eff >= hp:
                    return 20000 + prize_value(card) * 1000 - hp, "div-RK7: drag killable"
            return 10000 - hp, "Sakaki: drag lowest HP"

        if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER):
            return self.default_score_damage_target(obs, opt)

        if ctx == SelectContext.TO_HAND:
            # サーチ択（ランス最大3枚・レシーバー・ポケパッド・むしとり等）
            base = 100 - hc.get(cid, 0) * 40
            if cid == SPIDOPS:
                need = fc[TAROUNTULA] >= 1 and fc[SPIDOPS] + hc[SPIDOPS] == 0
                return base + (90 if need else 40), "S-4: take Spidops"
            if cid == TAROUNTULA:
                return base + (80 if p["spid_line"] < 2 else 45), "S-4: take Tarountula"
            if cid == MEWTWO:
                return base + (70 if fc[MEWTWO] + hc[MEWTWO] == 0 else 15), "S-4: take Mewtwo"
            if cid == ARTICUNO:
                return base + (60 if fc[ARTICUNO] == 0 else 10), "S-4: take Articuno"
            if cid == MIMIKYU:
                return base + 30, "S-4: take Mimikyu"
            if cid == LANCE:
                return base + (75 if p["rockets"] < 4 else 35), "take Lance"
            if cid == ATHENA:
                return base + 70, "take Athena"
            if cid == SAKAKI:
                return base + 45, "take Sakaki"
            if cid == APOLLO:
                return base + 25, "take Apollo"
            if cid == GRASS:
                return base + (55 if hc[GRASS] == 0 else 5), "take grass"
            if cid == WATER:
                return base + (30 if fc[ARTICUNO] >= 1 else 0), "take water"
            return base, "take other"

        if ctx == SelectContext.TO_BENCH:
            if cid in BASICS:
                return 100, "S-2: bench rocket"
            return 10, "bench other"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            # ハイパーボールのコスト等。R-13 は default（LINE_PROTECT）が守る
            ids = [c.id for c in (my_state(obs).hand or []) if c]
            if cid == ROCKET_E and ids.count(ROCKET_E) <= 1:
                return -2000, "keep last Rocket Energy (Mewtwo fuel)"
            if cid == GRASS and ids.count(GRASS) >= 3:
                return 11000, "discard surplus grass (Charge Up recycles)"
            return self.default_score_discard(obs, opt)

        # イレイザーボールの任意トラッシュ（自分ベンチの付きエネ）は選ばない（v1）
        if opt.type == OptionType.ENERGY and pi == yi and opt.area in (
                AreaType.ACTIVE, AreaType.BENCH):
            if ctx == SelectContext.DISCARD_CARD_OR_ATTACHED_CARD:
                return -50, "Erasure: keep own energy"
        if opt.area == AreaType.DISCARD and cid in (GRASS, WATER):
            # チャージアップの回収択: 草優先（主砲の色。水はフリーザー専用）
            return (100 if cid == GRASS else 40), "Charge Up: recover energy"

        if ctx == SelectContext.TO_DECK:
            return 10, "to deck"

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: def agent は必ずファイル末尾の callable にする。

_impl = make_agent(RocketPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
