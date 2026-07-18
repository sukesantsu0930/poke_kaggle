"""マリィ（Marnie's Grimmsnarl ex + Munkidori）ルールベースエージェント — フルスクラッチ

7/3メタの実質勝ち組アーキタイプ。参照実装なし・BasePolicy 純粋3フックの最初の実装。
設計文書: docs/planning/デッキ設計_マリィ.md（S-x/E-x/未決事項）

コンセプト:
  ふしぎなアメ → Grimmsnarl ex 着地（Punk Up で闇エネ5枚一括加速）= サブゴール達成。
  以後 Shadow Bullet 180+ベンチ30 を連打しつつ、Munkidori の Adrena-Brain で
  自分のダメカンを相手に移す（タンク + 削りの両立）。

2026-07-18 主流形適応（decks/fleet/marnie_mainstream_0718.csv、MAR_* トグル）:
  ユキメノコ Freezing Shroud（特性持ち全員に毎チェックアップ1個）が Adrena-Brain の
  弾を自給する。ペトレル×4 のトレーナーズサーチ + ボス×2 + アンフェアスタンプ +
  ハンディファン×2。マント/ゼロシキ/ドドンパ線/モルペコは不採用（旧ルールは死文で残置）。
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
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    damage_on,
    energy_count,
    get_card,
    has_tool,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    read_deck_csv as _read_deck_csv,
)

# ── 主流形適応トグル（2026-07-18。艦隊リスト改訂: winrate_2 → marnie_mainstream_0718） ──
MAR_FROSLASS = os.environ.get("MAR_FROSLASS", "1") != "0"  # ユキワラシ/ユキメノコ線 + ポフィン条件修正
MAR_PETREL = os.environ.get("MAR_PETREL", "1") != "0"      # ロケット団のペトレル（トレーナーズサーチ）
MAR_STAMP = os.environ.get("MAR_STAMP", "1") != "0"        # アンフェアスタンプ（ACE SPEC）
MAR_FAN = os.environ.get("MAR_FAN", "1") != "0"            # ハンディファン（どうぐ）
MAR_BOSS = os.environ.get("MAR_BOSS", "1") != "0"          # ボスの指令（吊り出し）
# 学習帯解錠（2026-07-18 監査: 主流形教師の before 監査（outside 150手）の負帯クラスタを
# 150-800 で解錠。Lillie 44x / タンカ 18x / エネ付け先 22x / リトリート 11x。
# greedy はほぼ不変・BC の候補回復。検証後の final 監査で coverage 99.1%）
MAR_UNLOCK = os.environ.get("MAR_UNLOCK", "1") != "0"

# ── カードID（デッキ設計_マリィ.md のリスト） ──

IMPIDIMP = 646        # マリィのベロバー HP70（Filch: 1ドロー）
MORGREM = 647         # マリィのギモー HP100
GRIMMSNARL_EX = 648   # マリィのオーロンゲex HP320（Punk Up / Shadow Bullet 180+30）
MORPEKO = 649         # マリィのモルペコ（旧リスト。主流形では不採用 = 死文）
MUNKIDORI = 112       # マシマシラ（Adrena-Brain: ダメカン3個移動）
DUNSPARCE = 305       # 旧リスト（死文）
DUDUNSPARCE = 66      # 旧リスト（死文）
SNORUNT = 860         # ユキワラシ HP70（たね・水。Chilly {W}10 = 打点は使わない）
FROSLASS = 104        # ユキメノコ HP90（特性 Freezing Shroud: チェックアップ毎に
                      # 特性持ち全員へダメカン1（ユキメノコ以外・両者）→ Adrena-Brain の弾）

POFFIN = 1086
POKE_PAD = 1152
RARE_CANDY = 1079
NIGHT_STRETCHER = 1097
ENERGY_SEARCH = 1119    # 旧リスト（死文）
ENERGY_RECYCLER = 1139  # 旧リスト（死文）
HERO_CAPE = 1159        # 旧リスト（死文）
UNFAIR_STAMP = 1080     # ACE SPEC: 前の相手ターンに自分がきぜつ時のみ。両者手札を山へ・自分5枚/相手2枚ドロー
HANDHELD_FAN = 1161     # どうぐ: 装着者がバトル場で攻撃を受けた時、攻撃側のエネ1個を相手ベンチへ
LILLIE = 1227
DAWN = 1231
XEROSIC = 1197          # 旧リスト（死文）
PETREL = 1219           # ロケット団のペトレル: 山からトレーナーズ1枚サーチ
BOSS_ORDERS = 1182      # ボスの指令: 相手ベンチを吊り出し
SPIKEMUTH_GYM = 1259
DARK_ENERGY = 7

ATK_FILCH = 934           # Impidimp {C} 0dmg 1ドロー
ATK_SHADOW_BULLET = 937   # Grimmsnarl {D}{D} 180 + ベンチ30
ATK_SPIKY_WHEEL = 938     # Morpeko {C}{C}{C} 20 + {D}×40（自己スケール）

MARNIE_LINE = {IMPIDIMP, MORGREM, GRIMMSNARL_EX}
MARNIE_POKEMON = MARNIE_LINE | {MORPEKO}


class MarniePolicy(BasePolicy):
    DECK_NAME = "marnie_munkidori"
    GO_FIRST = True            # R-21 確定（2026-07-07 divergence 実測: 上位ピロット6/6が先攻）
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】マリガンは常にマックス引く
    ATTACKER_IDS = {GRIMMSNARL_EX, MORPEKO}
    ENERGY_IDS = {DARK_ENERGY}
    # R-13。MAR_FROSLASS: ユキメノコ（チップエンジン）も保護（ユキワラシは代替可なので外）
    LINE_PROTECT_IDS = (MARNIE_LINE | {MUNKIDORI, RARE_CANDY}
                        | ({FROSLASS} if MAR_FROSLASS else set()))
    SELF_SCALING_ATTACK_IDS = frozenset({ATK_SPIKY_WHEEL})     # R-10 例外
    ATTACK_ENERGY_TYPE = 7     # 悪

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
        bench_free = ms.benchMax - len(ms.bench)
        stadium_id = 0
        for c in obs.current.stadium:
            stadium_id = c.id
        my_prize = len(ms.prize)
        # R-11: 山札切れガード（リーサル確定時は解除）
        safe_draws = ms.deckCount - my_prize - 1
        own_damage = any(damage_on(pk) > 0 for pk in all_my_pokemon(obs))
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "bench_free": bench_free,
            "stadium_id": stadium_id, "safe_draws": safe_draws,
            "own_damage": own_damage,
            "marnie_line": fc[IMPIDIMP] + fc[MORGREM] + fc[GRIMMSNARL_EX],
            "opp_hand": opp_state(obs).handCount,
        }

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場の Grimmsnarl ex が Shadow Bullet を払える（エネ2枚以上）。"""
        return any(p.id == GRIMMSNARL_EX and energy_count(p) >= 2
                   for p in all_my_pokemon(obs))

    def attack_damage(self, obs, attacker, attack_id):
        if attack_id == ATK_SPIKY_WHEEL:
            dark = sum(1 for ec in (getattr(attacker, "energyCards", None) or [])
                       if ec.id == DARK_ENERGY)
            return 20 + dark * 40
        return super().attack_damage(obs, attacker, attack_id)

    def _max_active_damage_vs(self, obs, target):
        """バトル場の攻撃者が（リトリート無しで）target に出せる最大ダメージ。
        MAR_BOSS の吊り出しキル判定に使う。"""
        active = active_pokemon(obs)
        if active is None or target is None:
            return 0
        best = 0
        for plan in self.plan_attacks(obs):
            if plan.needs_retreat or plan.attacker is not active:
                continue
            d = self.guard_damage(plan.damage, plan.attacker, target)
            if d > best:
                best = d
        return best

    def _active_ko_by_attack_alone(self, obs):
        """E-2a の条件判定: 自分のバトル場ポケモンの攻撃ダメージだけで
        相手のバトル場を倒せるか（ダメカン移動を足さずに）。"""
        opp = opp_state(obs)
        opp_act = opp.active[0] if opp.active else None
        active = active_pokemon(obs)
        if opp_act is None or active is None:
            return False
        for plan in self.plan_attacks(obs):
            if plan.needs_retreat or plan.attacker is not active:
                continue
            if self.guard_damage(plan.damage, plan.attacker, opp_act) >= opp_act.hp:
                return True
        return False

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # MAR_FROSLASS: ユキワラシは安い前座（マシマシラ=エンジンより前に置く。div-1 準拠）
            table = {IMPIDIMP: 10, DUNSPARCE: 5, SNORUNT: (4 if MAR_FROSLASS else 0),
                     MUNKIDORI: 3, MORPEKO: 1}
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            fc = self.p.get("fc", {})
            if cid == IMPIDIMP:
                return (200 if fc.get(IMPIDIMP, 0) == 0 else 100), "S-2: setup bench Impidimp"
            if cid == DUNSPARCE:
                return 80, "S-2: setup bench Dunsparce"
            if cid == SNORUNT and MAR_FROSLASS:
                return 75, "MAR_FRO: setup bench Snorunt"
            if cid == MUNKIDORI:
                return 60, "S-2: setup bench Munkidori"
            return 0, "setup bench other"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    # ═══════════════ 優先則（フェーズを実際に分ける: 純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex
        ctx = obs.select.context

        # ── ABILITY 帯 ──
        # div-14（2026-07-11 実測・07-08/07-09 両日）: 上位勢のターン内順序は
        # プレイ/進化/サポーター/手張り → リトリート → ノココッチ → ジムサーチ →
        # アドレナ → 攻撃（H=Spikemuth/O=Adrena 196x、H=play/O=Spikemuth 152x、
        # H=play/O=Adrena 106x ほか全て一方向・逆方向 0x）。
        # 特性を R-04 最上位帯（26000-29000）から攻撃直前の帯（2500-3300）へ移す
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == SPIKEMUTH_GYM:
                # S-4: ジムサーチは毎ターン起動（対象選択は TO_HAND 側）
                return 3000, "S-4: Spikemuth Gym search"
            if cid == MUNKIDORI:
                # E-2: 自分の場にダメカンがある時だけ（回復+削り）。順序は最後（div-14）
                if p["own_damage"]:
                    return 2500, "E-2: Adrena-Brain (move counters)"
                return -1, "E-2: save Adrena-Brain (no damage)"
            if cid == DUDUNSPARCE:
                # div-15（2026-07-11 実測・両日）: 手札枚数の条件を撤廃（上位勢は手札が
                # 太くても進化後すぐ使う: H=save Run Away Draw が両日計 83x・逆方向 0x）。
                # R-11 の山札切れガード（safe_draws>=3）は維持
                if self._safe_draws() >= 3:
                    return 3300, "div-15: Run Away Draw"
                return -1, "save Run Away Draw"
            return 26000, "generic ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid == GRIMMSNARL_EX:
                # S-3: Punk Up が同時に発動 = サブゴール直行。最優先進化
                return 25000, "S-3: evolve Grimmsnarl ex (Punk Up)"
            if cid == MORGREM:
                return 9000, "S-3: evolve Morgrem"
            if cid == DUDUNSPARCE:
                return (8000, "evolve Dudunsparce") if self._safe_draws() >= 3 else (-1, "R-11")
            if cid == FROSLASS and MAR_FROSLASS:
                # Freezing Shroud 起動（毎チェックアップ、特性持ち全員に1個 → Adrena の弾）
                return 7500, "MAR_FRO: evolve Froslass (Freezing Shroud)"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            active = active_pokemon(obs)
            aid = active.id if active else None
            if aid == GRIMMSNARL_EX:
                return -5000, "keep tank active"
            ready = any(pk.id == GRIMMSNARL_EX and energy_count(pk) >= 2
                        for pk in my_state(obs).bench if pk)
            if ready and active is not None and energy_count(active) >= (CARD_DB[aid].retreatCost if aid in CARD_DB else 0):
                # div-14: 上位勢はジムサーチより先にリトリート（H=retreat/O=gym 15x・逆 0x）
                return 3500, "retreat to promote tank"
            # 監査 12x: タンク非準備時のリトリートも教師は指す（H=RETREAT/O=END の既知
            # 残存クラスタ）→ 学習帯 150 で解錠（END=0 しか無い手番でのみ greedy が変わる）
            if MAR_UNLOCK:
                return 150, "MAR_UNLOCK: retreat learn band"
            return -100, "avoid retreat"

        if opt.type == OptionType.ATTACK:
            # R-04: ワザは最後の帯。ワザ間の選好はダメージ + セットアップ期の Filch
            aid = getattr(opt, "attackId", None)
            active = active_pokemon(obs)
            dmg = self.attack_damage(obs, active, aid) if active else 0
            score = 1000 + dmg
            if not combat and aid == ATK_FILCH:
                score += 300   # S-1: 序盤の Filch ドローは価値が高い
            return score, "E-1: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        # ── CARD/ENERGY 系（サーチ・選択コンテキスト） ──
        if opt.type in (OptionType.CARD, OptionType.ENERGY):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

    # ── PLAY（フェーズで優先が入れ替わる中心） ──

    def _score_play(self, obs, opt, combat):
        p = self.p
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        cid = card.id
        data = CARD_DB.get(cid)
        fc, hc = p["fc"], p["hc"]

        if data is not None and data.cardType == CardType.POKEMON:
            score, reason = 20000, "play pokemon"
            if cid == IMPIDIMP:
                score += 500 if fc[IMPIDIMP] + fc[MORGREM] + fc[GRIMMSNARL_EX] < 2 else 100
            elif cid == MUNKIDORI:
                score += 400 if fc[MUNKIDORI] < 2 else 50
            elif cid == DUNSPARCE:
                score += 300 if fc[DUNSPARCE] + fc[DUDUNSPARCE] < 2 else -300
            elif cid == SNORUNT and MAR_FROSLASS:
                # 2-2線: 1体は必ず立てる。3体目は無い（2枚採用）
                score += 250 if fc[SNORUNT] + fc[FROSLASS] < 2 else -200
            elif cid == MORPEKO:
                score += 100 if combat else -100
            # R-03/ベンチ規律
            bench_empty = len([b for b in my_state(obs).bench if b]) == 0
            if bench_empty:
                score += 5000   # ドンク回避: とにかくベンチを作る
            elif p["bench_free"] <= 1:
                score -= 5000   # ベンチ1枠空け
            return score, reason

        # スタジアム
        if cid == SPIKEMUTH_GYM:
            if p["stadium_id"] == SPIKEMUTH_GYM:
                return -1, "gym already up"
            return 19500, "S-4: play Spikemuth Gym"

        # グッズ
        if cid == POFFIN:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Poffin)"
            # MAR_FROSLASS【条件のバグ修正】: 旧条件はドドンパ線（主流形に不在 → 恒真）を
            # 参照していた。ポフィンの対象（HP70以下のたね）を新リストに合わせる
            if MAR_FROSLASS:
                need = (fc[IMPIDIMP] < 2) or (fc[SNORUNT] + fc[FROSLASS] < 1)
            else:
                need = (fc[IMPIDIMP] < 2) or (fc[DUNSPARCE] + fc[DUDUNSPARCE] < 1)
            if not combat:
                return (18000 if need else 8000), "S-2: Poffin"
            return (12000 if need else -1), "Poffin: rebuild"
        if cid == POKE_PAD:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Pad)"
            return (17000 if not combat else 12000), "S-4: Poke Pad"
        if cid == RARE_CANDY:
            # S-3 本線: アメ → Grimmsnarl（進化可能な Impidimp は engine が判定）
            if fc[IMPIDIMP] >= 1 and hc[GRIMMSNARL_EX] >= 1:
                return 19000, "S-3: Rare Candy -> Grimmsnarl"
            return -1, "Rare Candy: no line"
        if cid == NIGHT_STRETCHER:
            dcc = p["dc"]
            # div-6（2026-07-08 divergence 実測・7/7）: 回収は「勝ち筋の駒が欠けている時」だけ
            # （human=ATTACK / ours=PLAY Night Stretcher ×6 — 盤面が足りているのに回収していた）
            line_missing = (fc[GRIMMSNARL_EX] == 0 or fc[MUNKIDORI] == 0
                            or p["marnie_line"] < 2)
            if line_missing and dcc[GRIMMSNARL_EX] + dcc[IMPIDIMP] + dcc[MORGREM] + dcc[MUNKIDORI] >= 1:
                return 13000, "div-6: recover missing line piece"
            if dcc[DARK_ENERGY] >= 1 and not obs.current.energyAttached and hc[DARK_ENERGY] == 0:
                return 11000, "Night Stretcher: recover energy"
            if MAR_UNLOCK:
                return 250, "MAR_UNLOCK: Stretcher learn band"
            return -1, "Night Stretcher: nothing"
        if cid == ENERGY_SEARCH:
            if hc[DARK_ENERGY] == 0 and not obs.current.energyAttached:
                return 12000, "Energy Search"
            return -1, "Energy Search: not needed"
        if cid == ENERGY_RECYCLER:
            if p["dc"][DARK_ENERGY] >= 3:
                return 9000, "Energy Recycler"
            return -1, "Energy Recycler: few targets"
        if cid == HERO_CAPE:
            if any(pk.id == GRIMMSNARL_EX and not has_tool(pk) for pk in all_my_pokemon(obs)):
                return 13500, "E-4: Hero's Cape (420 tank)"
            return -1, "save Hero's Cape"
        if cid == HANDHELD_FAN and MAR_FAN:
            # どうぐ: バトル場で被弾時、攻撃側のエネ1個を相手ベンチへ剥がす。
            # 本命はタンク（オーロンゲ）に装着。他への装着は学習帯で候補だけ残す
            if any(pk.id == GRIMMSNARL_EX and not has_tool(pk) for pk in all_my_pokemon(obs)):
                return 12800, "MAR_FAN: Fan for tank"
            if any(not has_tool(pk) for pk in all_my_pokemon(obs)):
                return 3200, "MAR_FAN: wide band (BC sorts)"
            return -1, "save Fan"
        if cid == UNFAIR_STAMP and MAR_STAMP:
            # ACE SPEC。合法時（前の相手ターンに自分がきぜつ）のみエンジンが提示。
            # 帯は推測（相手手札が肥えている時に潰すのが本命。BC 並べ替え前提）
            if self._safe_draws() < max(0, 5 - p["hand_size"]) + 1:
                return -1, "R-11: deck thin (Stamp)"
            if p["opp_hand"] >= 4:
                return 12500, "MAR_STAMP: strip opp refresh"
            if p["hand_size"] <= 4:
                return 8000, "MAR_STAMP: refresh own hand"
            return 3000, "MAR_STAMP: wide band (BC sorts)"

        # サポート（択一）
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == PETREL and MAR_PETREL:
            # トレーナーズ万能サーチ ×4 = 主流形の骨格。条件付きの帯は推測
            # （広い正帯 3000-5000。最適な使いどころは BC が並べ替える前提）
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Petrel)"
            if (hc[RARE_CANDY] == 0 and hc[GRIMMSNARL_EX] >= 1
                    and fc[IMPIDIMP] >= 1 and fc[GRIMMSNARL_EX] == 0):
                return 5000, "MAR_PET: fetch Candy line"
            if p["stadium_id"] != SPIKEMUTH_GYM and hc[SPIKEMUTH_GYM] == 0:
                return 4600, "MAR_PET: fetch gym"
            return 4200, "MAR_PET: fetch trainer (wide band)"
        if cid == DAWN:
            missing = (hc[GRIMMSNARL_EX] == 0 and fc[GRIMMSNARL_EX] == 0)
            if self._safe_draws() < 3:
                return -1, "R-11: deck thin (Dawn)"
            return (5000 if missing else 3500), "S-4: Dawn (line search)"
        if cid == XEROSIC:
            # E-3: 相手手札破壊。対アラカザムは Powerful Hand 打点を直接削る
            if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                return 5200, "E-3: Xerosic vs Alakazam"
            if p["opp_hand"] >= 6:
                return 4500, "E-3: Xerosic (big hand)"
            return -1, "save Xerosic"
        if cid == BOSS_ORDERS and MAR_BOSS:
            # 吊り出しキル: ベンチに「今の攻撃で倒せる」駒がいる時だけ自然帯。
            # それ以外は学習帯 400（縛り/妨害ボスの条件は φ に無い → BC が拾う）
            if combat:
                for pk in (opp_state(obs).bench or []):
                    if pk is None:
                        continue
                    rem = pk.hp - damage_on(pk)
                    if 0 < rem <= self._max_active_damage_vs(obs, pk):
                        return 5300, "MAR_BOSS: pull benched kill"
            return 400, "MAR_BOSS: save Boss (learn band)"
        if cid == LILLIE:
            if self._safe_draws() < 6:
                return -1, "R-11: deck thin (Lillie)"
            if p["hand_size"] <= 4:
                return 4000, "Lillie (refresh)"
            # 監査 44x: 主流形教師は手札>4でもリーリエを切る（ダーン−3・ゼロシキ0の
            # 主流形はドローサポートがリーリエに集中）→ 学習帯で解錠
            if MAR_UNLOCK:
                return 300, "MAR_UNLOCK: Lillie learn band"
            return -1, "Lillie (refresh)"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        if cid == HERO_CAPE:
            if tid == GRIMMSNARL_EX and not has_tool(target):
                return 13000, "E-4: Cape on Grimmsnarl"
            return -1, "save Cape"

        if cid == HANDHELD_FAN and MAR_FAN:
            if has_tool(target):
                return -1, "MAR_FAN: target has tool"
            if tid == GRIMMSNARL_EX:
                return 12800, "MAR_FAN: Fan on Grimmsnarl"
            # 他ターゲットは学習帯（バトル場の前座に付ける手を候補に残す）
            act = active_pokemon(obs)
            return (600 if target is act else 300), "MAR_FAN: learn band target"

        if cid != DARK_ENERGY:
            return -500, "skip non-dark"
        if obs.current.energyAttached:
            return -1, "already attached"

        e = energy_count(target)
        dark_on = sum(1 for ec in (getattr(target, "energyCards", None) or [])
                      if ec.id == DARK_ENERGY)
        # MAR_UNLOCK（監査 22x）: 対象外の −1 を学習帯 200 で解錠
        # （2枚目のマシマシラ / ユキ線への手張り等を候補に残す）。
        # ただしオーロンゲ線の3枚目は解錠しない【2026-07-18 修正】: ライン最大コストが
        # 悪2（Shadow Bullet [7,7]）なので check_agent の R-10 外形検査（over-fill）に
        # 抵触する（10戦で NG 1 を実測 → -1 に差し戻して合格）。マシマシラ（Mind Bend は
        # 超コストで悪エネでは永遠に払えない = R-10 検査対象外）とユキ線（水コスト・同上）
        # のみ解錠を維持
        _neg = 200 if MAR_UNLOCK else -1
        if tid == MUNKIDORI:
            score = 8300 if dark_on == 0 else _neg   # Adrena-Brain 起動には1枚で十分
            reason = "S-5: enable Adrena-Brain"
        elif tid == GRIMMSNARL_EX:
            score = 8200 if e < 2 else -1            # R-10: Shadow Bullet コスト2（解錠禁止）
            reason = "S-5: fuel Shadow Bullet"
        elif tid == MORGREM:
            # div-10 は棄却（2026-07-12 二分探索: 対旧版200戦 43.3%、div-9/10 除去で 52.5% に
            # 回復 = L3 は +3pt でも L2 の直接対決 −7pt の主因。L2改善∧L3非悪化を満たさず差し戻し）
            score = 8100 if e < 2 else -1            # R-10（解錠禁止）
            reason = "S-5: pre-load line"
        elif tid == IMPIDIMP:
            score = 8000 if e < 2 else -1            # ライン先置き（進化後コスト2まで・R-10）
            reason = "S-5: pre-load line"
        elif tid == MORPEKO:
            score = 7900 + dark_on * 10            # 自己スケール（R-10 例外）
            reason = "S-5: Spiky Wheel scaling"
        else:
            return _neg, "attach: wrong target"
        if score > 0 and self.is_threatened(target):
            score -= 2000   # R-08: 負け筋への追い銭防止
        return score, reason

    # ── CARD/ENERGY 選択（サーチ先・ダメカン移動先・前出し等） ──

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
                # div-1（2026-07-07 divergence 実測）: 上位勢はマシマシラを前に出さない
                # （エンジン駒の保護）。ライン駒 > マシマシラ の順に変更
                if cid == GRIMMSNARL_EX:
                    score, reason = 15000 + energy_count(card) * 100, "promote tank"
                elif cid == MORPEKO:
                    score, reason = 9000, "promote Morpeko (retreat 0)"
                elif cid == MORGREM:
                    score, reason = 4500, "promote Morgrem"
                elif cid == IMPIDIMP:
                    score, reason = 4000, "promote Impidimp"
                elif cid == SNORUNT and MAR_FROSLASS:
                    # 安い犠打（1進化素材だが2枚あり、ライン駒より軽い）
                    score, reason = 3800, "MAR_FRO: promote Snorunt (cheap sac)"
                elif cid == FROSLASS and MAR_FROSLASS:
                    # チップエンジンだが非ex1枚取り = マシマシラよりは前に出す
                    score, reason = 3100, "MAR_FRO: promote Froslass over Munkidori"
                elif cid == MUNKIDORI:
                    score, reason = 3000, "div-1: protect Munkidori (engine)"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            # 相手側の吊り出し先（ボスの指令）
            if MAR_BOSS and card is not None:
                hp = getattr(card, "hp", 0) or 0
                rem = hp - damage_on(card)
                dmg = self._max_active_damage_vs(obs, card)
                cdata = CARD_DB.get(cid)
                if 0 < rem <= dmg:
                    bonus = 2000 if (cdata is not None and getattr(cdata, "ex", False)) else 0
                    return 5000 + bonus - rem, "MAR_BOSS: pull kill target"
                # 非キル時: エネ無しの駒を縛る > 低残HP（相対順序のみの推測帯）
                stall = 200 if energy_count(card) == 0 else 0
                return 1000 + stall + max(0, 300 - rem) // 3, "MAR_BOSS: pull stall target"
            return 1000, "opp switch"

        if ctx in (SelectContext.DAMAGE, getattr(SelectContext, "DAMAGE_COUNTER", SelectContext.DAMAGE)):
            # E-2: Adrena-Brain の移動元/先 + Shadow Bullet のベンチ30
            if pi == yi and card is not None:
                # div-2（2026-07-07 divergence 実測）: 移動元はライン駒の回復を優先、
                # マシマシラ自身からは動かさない（上位勢の一貫パターン）
                score = damage_on(card) * 10
                if cid == GRIMMSNARL_EX:
                    score += 2000   # タンクの回復を最優先
                elif cid in (IMPIDIMP, MORGREM):
                    score += 1500   # 進化元を守って育てる
                elif cid == MUNKIDORI:
                    score -= 1000   # div-2: 他に傷があるならそちらを優先
                return score, "E-2: move counters from"
            if card is not None:
                opp = opp_state(obs)
                is_opp_active = bool(opp.active) and card is opp.active[0]
                # E-2a【ハード】: バトル場だけで相手バトル場を倒せるなら30点はベンチへ
                if is_opp_active and self._active_ko_by_attack_alone(obs):
                    return -1, "E-2a: active dies to attack alone -> send to bench"
                hp = getattr(card, "hp", 999)
                remaining = hp - damage_on(card)
                if remaining <= 30:
                    return 15000 + (500 - hp), "E-2/R-15: counter-move KO"
                # div-12【棄却】（2026-07-11）: 「ダメカンは大物（最大HP）に積む」を試したが
                # DAMAGE_COUNTER 69%→49%（07-08）/ 75%→57%（07-09）に悪化して差し戻し。
                # H=Okidogi/O=Solrock 等の不一致は残るが、条件（どの大物に積むか）が
                # 特定できず一律の反転はR-15より悪い（両方向クラスタ）
                return self.default_score_damage_target(obs, opt)   # R-15: 最低HP優先
            return 0, "damage none"

        if ctx == SelectContext.REMOVE_DAMAGE_COUNTER:
            # div-11 v2（2026-07-11 実測・07-08/07-09 両日）: Adrena-Brain の移動元は
            # 未実装で全て同点 500（インデックス順=バトル場が先頭）だった。
            # v1「傷ついたマシマシラを常に最優先」（H=Munkidori/O=Grimmsnarl 30x/32x に
            # 基づく）は逆流 H=Grimmsnarl/O=Munkidori 52x/47x を生み RDC 82→72/84→78 に
            # 悪化（両方向クラスタ）。v2: 重傷（60+）のマシマシラだけ救出し、
            # それ以外は従来の実効挙動（バトル場先頭）を明示化
            if card is None:
                return 0, "rdc none"
            dmg = damage_on(card)
            if cid == MUNKIDORI and dmg >= 60:
                return 3000 + dmg, "div-11: rescue heavily-hit Munkidori"
            if card is active_pokemon(obs):
                return 2000, "div-11: heal active first"
            return 1000 + dmg, "div-11: heal most damaged bench"

        if ctx == SelectContext.TO_HAND:
            # div-13（2026-07-11 実測・07-08/07-09 両日）: サーチ先テーブルの補正。
            # ギモーの取りすぎ（H=Dudunsparce/Impidimp/Munkidori 等 vs O=Morgrem が
            # 両日計 191x。アメ本線でギモーの価値は低い）、ノココッチ未実装（人間は 77x
            # 取る）、ベロバーのライン2本目（33x）、ノコッチ2本目線の取りすぎ（32x）
            base = 100 - hc.get(cid, 0) * 40
            if cid == GRIMMSNARL_EX:
                path = fc[MORGREM] >= 1 or (fc[IMPIDIMP] >= 1 and hc[RARE_CANDY] >= 1)
                return base + (90 if path else 40), "take Grimmsnarl"
            if cid == RARE_CANDY:
                return base + (85 if fc[IMPIDIMP] >= 1 else 0), "take Rare Candy"
            if cid == MORGREM:
                return base + 20, "take Morgrem"
            if cid == IMPIDIMP:
                return base + (60 if p["marnie_line"] < 2 else 25), "take Impidimp"
            if cid == MUNKIDORI:
                return base + (55 if fc[MUNKIDORI] < 2 else -20), "take Munkidori"
            if cid == DUDUNSPARCE:
                return base + (50 if fc[DUNSPARCE] >= 1 else -10), "div-13: take Dudunsparce"
            if cid == DUNSPARCE:
                return base + (40 if fc[DUNSPARCE] + fc[DUDUNSPARCE] < 1 else -30), "take Dunsparce"
            if cid == DARK_ENERGY:
                return base + (30 if hc[DARK_ENERGY] == 0 else -10), "take energy"
            if cid == HERO_CAPE:
                return base + 20, "take Cape"
            if MAR_FROSLASS and cid == SNORUNT:
                return base + (30 if fc[SNORUNT] + fc[FROSLASS] < 2 else -20), "MAR_FRO: take Snorunt"
            if MAR_FROSLASS and cid == FROSLASS:
                return base + (35 if fc[SNORUNT] >= 1 and fc[FROSLASS] == 0 else 0), "MAR_FRO: take Froslass"
            if MAR_PETREL and cid == SPIKEMUTH_GYM:
                return base + (75 if p["stadium_id"] != SPIKEMUTH_GYM else -20), "MAR_PET: take gym"
            if MAR_PETREL and cid == POFFIN:
                need_basics = fc[IMPIDIMP] < 2 or (fc[SNORUNT] + fc[FROSLASS] < 1)
                return base + (55 if (not combat and need_basics) else 5), "MAR_PET: take Poffin"
            if MAR_PETREL and cid == BOSS_ORDERS:
                return base + (35 if combat else 5), "MAR_PET: take Boss"
            if MAR_PETREL and cid == HANDHELD_FAN:
                bare = any(pk.id == GRIMMSNARL_EX and not has_tool(pk)
                           for pk in all_my_pokemon(obs))
                return base + (25 if bare else 0), "MAR_PET: take Fan"
            if MAR_PETREL and cid == UNFAIR_STAMP:
                return base + 15, "MAR_PET: take Stamp"
            if MAR_PETREL and cid == NIGHT_STRETCHER:
                return base + 10, "MAR_PET: take Stretcher"
            return base, "take other"

        if ctx == SelectContext.ATTACH_FROM:
            # div-4（2026-07-08 divergence 実測・7/7 上位10ピロット）: エネの付け先選択
            # （ATTACH_FROM）は未実装で全て同点 500 → 実質インデックス順だった。
            # 上位勢の実選択はオーロンゲ 241 > ベロバー 63 > ギモー 23 > モルペコ 21 > マシマシラ 11
            if card is not None and hasattr(card, "energyCards"):
                e = energy_count(card)
                dark_on = sum(1 for ec in (card.energyCards or []) if ec.id == DARK_ENERGY)
                if cid == GRIMMSNARL_EX:
                    # div-7（2026-07-11 実測・07-08/07-09 両日）: 満タン(e>=2)のオーロンゲには
                    # 足さず、次のライン駒へ回す。両日最大の不一致クラスタ
                    # （H: pre-load Impidimp(80) / O: Grimmsnarl first(100) が 91x/106x）
                    if e < 2:
                        return 150, "div-4: attach to Grimmsnarl first"
                    return 30, "div-7: Grimmsnarl charged -> spill to line"
                if cid == IMPIDIMP:
                    return (80 if e < 2 else 10), "div-4: pre-load Impidimp"
                if cid == MORGREM:
                    return (70 if e < 2 else 10), "div-4: pre-load Morgrem"
                if cid == MORPEKO:
                    return 60 + dark_on * 5, "div-4: Morpeko scaling"
                if cid == MUNKIDORI:
                    return (40 if dark_on == 0 else 5), "div-4: Munkidori last"
                return 5, "div-4: attach other"
            return 500, "attach from (non-pokemon)"

        if ctx == SelectContext.TO_BENCH:
            if cid == IMPIDIMP:
                return 100, "S-2: bench Impidimp"
            if cid == DUNSPARCE:
                return 80, "S-2: bench Dunsparce"
            if cid == SNORUNT and MAR_FROSLASS:
                return 75, "MAR_FRO: bench Snorunt"
            if cid == MUNKIDORI:
                return 70, "S-2: bench Munkidori"
            # div-5 は棄却（2026-07-08: 「リスト外の駒は出さない」を試したが 7/6 ホールドアウトで
            # TO_BENCH 59%→39% に悪化して差し戻し。変種リストの駒も上位勢は普通に出す）
            return 10, "bench other"

        if ctx in (SelectContext.ATTACH_TO, SelectContext.TO_FIELD):
            # div-3（2026-07-07 divergence 実測）: Punk Up のエネ取得は「必要枚数だけ」。
            # 上位勢は典型3枚（オーロンゲ2+マシマシラ1）。山の悪エネは次のオーロンゲの弾として残す
            if cid == DARK_ENERGY:
                if "energy_quota" not in p:
                    need = 0
                    preload = 0
                    for pk in all_my_pokemon(obs):
                        if pk.id == GRIMMSNARL_EX:
                            need += max(0, 2 - energy_count(pk))
                        elif pk.id == MUNKIDORI:
                            dark_on = sum(1 for ec in (getattr(pk, "energyCards", None) or [])
                                          if ec.id == DARK_ENERGY)
                            if dark_on == 0:
                                need += 1
                        elif pk.id in (IMPIDIMP, MORGREM):
                            # div-8（2026-07-11 実測・07-08/07-09 両日）: 上位勢は必要枚数より
                            # 1〜2枚多く取り、次のライン駒に先置きする（human 4-5枚 vs ours 2枚が
                            # 両日で 31x/28x。div-3 の「山に残す」は保守的すぎた）
                            preload += max(0, 2 - energy_count(pk))
                    p["energy_quota"] = max(1, min(5, need + min(2, preload)))
                if p["energy_quota"] > 0:
                    p["energy_quota"] -= 1
                    return 1000, "div-3: take needed energy"
                return -1, "div-3: leave energy in deck (next Punk Up)"
            # Punk Up の付与先（S-3）: Grimmsnarl 2 → Munkidori 各1 → Morpeko → ライン
            if card is not None and hasattr(card, "energyCards"):
                e = energy_count(card)
                dark_on = sum(1 for ec in (card.energyCards or []) if ec.id == DARK_ENERGY)
                if cid == GRIMMSNARL_EX and e < 2:
                    return 100, "Punk Up: Grimmsnarl first"
                if cid == MUNKIDORI and dark_on == 0:
                    return 90, "Punk Up: enable Adrena-Brain"
                if cid == MORPEKO:
                    return 60 + dark_on * 5, "Punk Up: Morpeko scaling"
                if cid in (MORGREM, IMPIDIMP) and e < 2:
                    return 50, "Punk Up: pre-load line"
                return 5, "Punk Up: overflow"
            return 1000, "to field"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            return self.default_score_discard(obs, opt)   # R-13

        if ctx == SelectContext.TO_DECK:
            if cid in MARNIE_LINE or cid == MUNKIDORI:
                return 100, "to deck line"
            return 10, "to deck other"

        if opt.type == OptionType.ENERGY:
            return 1000, "take energy (Punk Up)"

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(MarniePolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
