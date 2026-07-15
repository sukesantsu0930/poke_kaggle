"""ガブリアス（Cynthia's Garchomp ex）ルールベースエージェント — フルスクラッチ

7/6メタの新興上位（レート1000+帯シェア11.1%）。BasePolicy 純粋3フックの2例目。
設計文書: docs/planning/デッキ設計_ガブリアス.md（S-x/E-x/未決事項）

コンセプト:
  素進化 Gible→Gabite→Garchomp ex。Gabite の Champion's Call（毎ターン、シロナのポケモンを
  サーチ）がエンジン = サブゴールは「場のガブリアスexがエネ1枚以上」。
  以後 Corkscrew Dive 100+30n（+手札6枚までドロー）を連打し、大物は Draconic Buster 260+30n。
  ロズレイドの Cheer On to Glory（+30/体）が全アタッカーの打点を底上げする。
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

from cg.api import CardType, OptionType, SelectContext

import meta_tables as mt
from policy_base import (
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    damage_on,
    energy_count,
    get_card,
    has_tool,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    payable_attacks,
    read_deck_csv as _read_deck_csv,
    retreat_cost,
)

# ── カードID（デッキ設計_ガブリアス.md のリスト） ──

ROSELIA = 341         # シロナのロゼリア HP70 {G}
ROSERADE = 342        # シロナのロズレイド HP130（Cheer On to Glory: 技+30/体）
GIBLE = 379           # シロナのフカマル HP70
GABITE = 380          # シロナのガバイト HP100（Champion's Call: 毎ターン、シロナのポケモンをサーチ）
GARCHOMP_EX = 381     # シロナのガブリアスex HP330 にげる0
SPIRITOMB = 387       # シロナのミカルゲ HP70（Raging Curse: ベンチのダメカン×10）

UNFAIR_STAMP = 1080   # ACE SPEC: KOされた返しに 自分5枚/相手2枚
POFFIN = 1086
NIGHT_STRETCHER = 1097
FIGHTING_GONG = 1142  # 基本{F}エネ or たね{F}ポケモンをサーチ
POKE_PAD = 1152
POWER_WEIGHT = 1173   # シロナのポケモン HP+70
XEROSIC = 1197
SURFER = 1203
HILDA = 1225          # 進化ポケモン+エネをサーチ
LILLIE = 1227         # 手札を戻して6ドロー（サイド残6ちょうどなら8）
FOREST_OF_VITALITY = 1261   # {G}=ロゼリアが出したターンに進化できる
F_ENERGY = 6
ROCK_F_ENERGY = 20    # {F}供給 + 相手の技の効果を防ぐ

ATK_SPIKE_STING = 475     # Roselia {C} 20
ATK_LEAF_STEP = 476       # Roserade {G}{C}{C} 80（{G}エネ不採用のため実質撃てない）
ATK_ROCK_HURL = 529       # Gible {F} 20
ATK_DRAGONSLICE = 530     # Gabite {F} 40
ATK_CORKSCREW_DIVE = 531  # Garchomp {F} 100 + 手札6枚までドロー
ATK_DRACONIC_BUSTER = 532 # Garchomp {F}{F} 260 + エネ全トラッシュ
ATK_RAGING_CURSE = 540    # Spiritomb {C} ベンチのシロナのポケモンのダメカン×10（弱点なし）

GARCHOMP_LINE = {GIBLE, GABITE, GARCHOMP_EX}
ROSE_LINE = {ROSELIA, ROSERADE}
CYNTHIA_POKEMON = GARCHOMP_LINE | ROSE_LINE | {SPIRITOMB}
ENERGY_CARDS = {F_ENERGY, ROCK_F_ENERGY}


class GarchompPolicy(BasePolicy):
    DECK_NAME = "cynthia_garchomp"
    GO_FIRST = True            # R-21 確定（2026-07-07 実測: nasuo445 の IS_FIRST 22/22 が先攻）
    TAKE_MULLIGAN = True       # R-22【ハード・プロジェクト決定】マリガンは常にマックス引く
    ATTACKER_IDS = {GARCHOMP_EX, SPIRITOMB, GABITE}
    ENERGY_IDS = ENERGY_CARDS
    LINE_PROTECT_IDS = GARCHOMP_LINE | ROSE_LINE   # R-13
    ATTACK_ENERGY_TYPE = 6     # 闘

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
        bench_free = ms.benchMax - len([b for b in ms.bench if b])
        stadium_id = 0
        for c in obs.current.stadium:
            stadium_id = c.id
        my_prize = len(ms.prize)
        # R-11: 山札切れガード（リーサル確定時は解除）
        safe_draws = ms.deckCount - my_prize - 1
        hand_energy = hc[F_ENERGY] + hc[ROCK_F_ENERGY]
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "bench_free": bench_free,
            "stadium_id": stadium_id, "safe_draws": safe_draws,
            "hand_energy": hand_energy,
            "chomp_line": fc[GIBLE] + fc[GABITE] + fc[GARCHOMP_EX],
            "rose_line": fc[ROSELIA] + fc[ROSERADE],
            "opp_hand": opp_state(obs).handCount,
        }

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場の Garchomp ex が Corkscrew Dive を払える（エネ1枚以上）。"""
        return any(p.id == GARCHOMP_EX and energy_count(p) >= 1
                   for p in all_my_pokemon(obs))

    def attack_damage(self, obs, attacker, attack_id):
        # Cheer On to Glory: 場のロズレイド1体につき技+30（相手バトル場対象。弱点計算前）
        bonus = 30 * sum(1 for p in all_my_pokemon(obs) if p.id == ROSERADE)
        if attack_id == ATK_RAGING_CURSE:
            # 自分のベンチのシロナのポケモンのダメカン×10（デッキは全員シロナ）
            counters = sum(damage_on(p) // 10 for p in my_state(obs).bench if p)
            return counters * 10 + bonus
        return attack_base_damage(attack_id) + bonus

    def _corkscrew_kills_active(self, obs):
        """E-2 の条件判定: バトル場の Garchomp の Corkscrew Dive で相手バトル場を倒せるか。"""
        opp = opp_state(obs)
        opp_act = opp.active[0] if opp.active else None
        active = active_pokemon(obs)
        if opp_act is None or active is None or active.id != GARCHOMP_EX:
            return False
        dmg = self.guard_damage(
            self.attack_damage(obs, active, ATK_CORKSCREW_DIVE), active, opp_act)
        return dmg >= opp_act.hp

    def _gabite_call_pending(self, obs):
        """div-G14 の条件: このターンまだ使える Gabite の Champion's Call が
        選択肢に残っているか（＝先にガブへ進化させるとサーチ口が1つ消える状態）。"""
        yi = obs.current.yourIndex
        for o in (obs.select.option or []):
            if o.type == OptionType.ABILITY:
                c = get_card(obs, o.area, o.index, yi)
                if c is not None and c.id == GABITE:
                    return True
        return False

    def _buster_setup(self, obs, chomp):
        """div-G11 の条件: Draconic Buster なら相手バトル場を KO できるが
        Corkscrew Dive では KO できない（= 2エネ目を張る価値がある）。"""
        opp = opp_state(obs)
        opp_act = opp.active[0] if opp.active else None
        if opp_act is None:
            return False
        cork = self.guard_damage(
            self.attack_damage(obs, chomp, ATK_CORKSCREW_DIVE), chomp, opp_act)
        bust = self.guard_damage(
            self.attack_damage(obs, chomp, ATK_DRACONIC_BUSTER), chomp, opp_act)
        return bust >= opp_act.hp > cork

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # div-G1: リード順は Gible > Roselia > Spiritomb（上位ピロット実測 5/5）
            table = {GIBLE: 10, ROSELIA: 5, SPIRITOMB: 3}
            return table.get(cid, 0), "S-1: setup active"
        # div-G1（2026-07-07 divergence 実測）: 上位ピロットはセットアップでベンチ展開しない
        # （0/20 が全部 human=(none)。展開はポフィン/手貼りでターン中に行う）
        # → SETUP_BENCH は BasePolicy デフォルト（-10000）に任せる
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    # ═══════════════ 優先則（純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex

        # ── ABILITY 帯（R-04 最上位） ──
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == GABITE:
                # S-4: Champion's Call は毎ターン起動（サーチ先は TO_HAND 側）
                # R-11: 山札はサーチでも1枚減る。山札切れ圏では止める（solo 実測: デッキアウト負け）
                if self._safe_draws() < 1:
                    return -1, "R-11: deck thin (Champion's Call)"
                # div-G5（2026-07-08 divergence 実測・7/7 nasuo445）: 上位ピロットは
                # ポフィン/グング/素出し/進化を済ませてから Champion's Call を起動する
                # （欠け駒を確認した後にサーチ）。ABILITY 最上帯 27000 → アイテム帯の下 13500
                return 13500, "div-G5: Champion's Call (after items)"
            if cid in CYNTHIA_POKEMON:
                return 26000, "generic own ability"
            # div-G2（2026-07-07 divergence 実測）: 相手スタジアム（スパイクタウンジム等）の
            # 特性は押さない（自デッキに対象がなく空振り。上位ピロットは一度も使わない）
            return -1, "div-G2: skip foreign ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid == GARCHOMP_EX:
                # div-G14【ソフト・暫定 2026-07-11。07-08/09 実測】: 未使用の Champion's Call が
                # 残っている間はガブ進化を「同ターン内で」後回しにする（先に Gabite を進化させると
                # そのターンのサーチ口が消える。human=ABILITY/ours=EVOLVE が 07-08 24件・07-09 8件+）。
                # 13400 = Champion's Call 13500 の直下。ATTACK(≤2200)/RETREAT(2600)/END(0) より
                # 上なので進化自体は必ず同ターンに実行される = div-G12 の艦隊構築は弱めない
                if self._safe_draws() >= 1 and self._gabite_call_pending(obs):
                    return 13400, "div-G14: evolve Garchomp after Champion's Call"
                chomps = [pk for pk in all_my_pokemon(obs) if pk.id == GARCHOMP_EX]
                if not chomps:
                    return 25000, "S-3: evolve Garchomp ex (subgoal)"
                # div-G12【ユーザー指示 2026-07-11・LB上位ガブ実装の移植・暫定】:
                # 2体目以降も積極的に立てる（ローテーション艦隊）。div-G3(a) の遅延を上書き —
                # 被弾ガブはベンチで Raging Curse の弾になるため、ベンチ2進化exの
                # ボス2枚取りリスクより回転継続を優先する
                return 23000, "div-G12: build Garchomp fleet"
            if cid == GABITE:
                return 24500, "S-3: evolve Gabite (Champion's Call online)"
            if cid == ROSERADE:
                # 詰み回避（solo 実測）: バトル場のロゼリアを優先的に進化させない
                # （エネ0のロズレイドは技も退却も払えず置物になる）。ベンチのロゼリア優先
                tgt = option_target(obs, opt)
                ms = my_state(obs)
                if tgt is not None and ms.active and tgt is ms.active[0]:
                    return 8500, "S-3: evolve Roserade (active, less preferred)"
                return 9000, "S-3: evolve Roserade (+30)"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            active = active_pokemon(obs)
            aid = active.id if active else None
            if aid == GARCHOMP_EX:
                # div-G10【ユーザー指示 2026-07-11・LB上位ガブ実装の移植・暫定】:
                # 次ターン被KO圏（相手最大打点 ≥ 残りHP = 部分リーサル判定）のガブリアスは
                # タダにげ（にげる0）でベンチへ下げ、より無傷のガブに交代して攻撃を続ける。
                # 被弾ガブはベンチに蓄積して Raging Curse の火力になる
                hp_left = getattr(active, "hp", 0) or 0
                if self.opp_max_damage(obs) >= hp_left > 0:
                    fresh = any(pk.id == GARCHOMP_EX and energy_count(pk) >= 1
                                and (getattr(pk, "hp", 0) or 0) > hp_left
                                for pk in my_state(obs).bench if pk)
                    if fresh:
                        return 2600, "div-G10: rotate threatened Garchomp"
                # div-G3（2026-07-07 divergence 実測）: 傷んだガブリアスはタダにげ（にげる0）で
                # ベンチへ下げ、ミカルゲの Raging Curse の弾に変える（上位ピロットの定跡）
                tomb_ready = any(pk.id == SPIRITOMB and energy_count(pk) >= 1
                                 for pk in my_state(obs).bench if pk)
                if tomb_ready and damage_on(active) > 0:
                    curse = self.attack_damage(obs, active, ATK_RAGING_CURSE) + damage_on(active)
                    if curse >= 100:
                        return 2500, "div-G3: rotate worn Garchomp behind Spiritomb"
                return -5000, "keep Garchomp active"
            ready = any(pk.id in self.ATTACKER_IDS and payable_attacks(pk)
                        for pk in my_state(obs).bench if pk)
            if ready:
                return 2000, "retreat to promote attacker"
            return -100, "avoid retreat"

        if opt.type == OptionType.ATTACK:
            return self._score_attack(obs, opt, combat)

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

    # ── ATTACK（E-1/E-2/E-3） ──

    def _score_attack(self, obs, opt, combat):
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        opp = opp_state(obs)
        opp_act = opp.active[0] if opp.active else None
        dmg = self.attack_damage(obs, active, aid) if active else 0
        eff = self.guard_damage(dmg, active, opp_act) if opp_act is not None else dmg
        kills = opp_act is not None and eff >= opp_act.hp

        if aid == ATK_CORKSCREW_DIVE:
            # E-1: デフォルト攻撃（打点+手札6枚まで補充）
            return (2000 if kills else 1500), "E-1: Corkscrew Dive"
        if aid == ATK_DRACONIC_BUSTER:
            # E-2: エネ全トラッシュの経済性 — Corkscrew で倒せない相手だけ
            if kills and not self._corkscrew_kills_active(obs):
                return 2200, "E-2: Draconic Buster (KO only it can take)"
            return 400, "E-2: save energy (Buster wasteful)"
        if aid == ATK_RAGING_CURSE:
            # E-3: 非exの1枚交換アタッカー（ベンチのダメカン×10）
            return 1000 + dmg, "E-3: Raging Curse"
        return 1000 + dmg, "attack"

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
            if cid == GIBLE:
                score += 500 if fc[GIBLE] + fc[GABITE] + fc[GARCHOMP_EX] < 3 else 100
            elif cid == ROSELIA:
                score += 400 if p["rose_line"] < 2 else 50
            elif cid == SPIRITOMB:
                score += 300 if fc[SPIRITOMB] < 1 else -300
            # R-03/R-24 ベンチ規律
            bench_empty = len([b for b in my_state(obs).bench if b]) == 0
            if bench_empty:
                score += 5000   # ドンク回避: とにかくベンチを作る
            elif p["bench_free"] <= 1:
                score -= 5000   # ベンチ1枠空け
            return score, reason

        # スタジアム
        if cid == FOREST_OF_VITALITY:
            if p["stadium_id"] == FOREST_OF_VITALITY:
                return -1, "forest already up"
            # ロゼリアの即進化が待っている時に価値が出る
            if hc[ROSELIA] >= 1 and (hc[ROSERADE] >= 1 or p["rose_line"] < 2):
                return 19500, "S-3: Forest (same-turn Roserade)"
            if p["stadium_id"] != 0:
                return 2500, "Forest: replace opp stadium"
            # div-G7（2026-07-08 divergence 実測・7/7）: 用が無い時は張らずに温存
            # （human=END / ours=PLAY Forest ×6。相手スタジアムへの上書き弾として取っておく）
            return -1, "div-G7: hold Forest (no immediate use)"

        # グッズ
        if cid == POFFIN:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Poffin)"
            need = (fc[GIBLE] < 2) or (p["rose_line"] < 1) or (fc[SPIRITOMB] < 1)
            if not combat:
                return (18000 if need else 8000), "S-2: Poffin"
            return (12000 if need else -1), "Poffin: rebuild"
        if cid == POKE_PAD:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Pad)"
            return (17000 if not combat else 12000), "S-4: Poke Pad"
        if cid == FIGHTING_GONG:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Gong)"
            if p["hand_energy"] == 0 and not obs.current.energyAttached:
                return 16000, "S-4: Fighting Gong (energy)"
            if fc[GIBLE] + hc[GIBLE] < 2:
                return 14000, "S-4: Fighting Gong (Gible)"
            return (6000 if not combat else -1), "Fighting Gong: spare"
        if cid == NIGHT_STRETCHER:
            dcc = p["dc"]
            if dcc[GARCHOMP_EX] + dcc[GABITE] + dcc[GIBLE] + dcc[ROSERADE] >= 1:
                return 13000, "Night Stretcher: recover line"
            if (dcc[F_ENERGY] >= 1 and p["hand_energy"] == 0
                    and not obs.current.energyAttached):
                return 11000, "Night Stretcher: recover energy"
            return -1, "Night Stretcher: nothing"
        if cid == UNFAIR_STAMP:
            # E-4: KOされた返し限定（それ以外は選択肢に出ない）。手札妨害+リフレッシュ
            if p["hand_size"] <= 6:
                return 15000, "E-4: Unfair Stamp"
            return -1, "save Unfair Stamp (big hand)"
        if cid == POWER_WEIGHT:
            if any(pk.id in (GARCHOMP_EX, GABITE, GIBLE) and not has_tool(pk)
                   for pk in all_my_pokemon(obs)):
                return 13500, "play Power Weight"
            return -1, "save Power Weight"

        # サポート（択一）
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == HILDA:
            # E-5: 進化パーツ欠損時のピンポイントサーチ
            missing_chomp = (hc[GARCHOMP_EX] == 0 and fc[GARCHOMP_EX] == 0
                             and fc[GABITE] + fc[GIBLE] >= 1)
            missing_gabite = (hc[GABITE] == 0 and fc[GABITE] == 0 and fc[GIBLE] >= 1)
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Hilda)"
            return (5000 if (missing_chomp or missing_gabite) else 3500), "E-5: Hilda"
        if cid == XEROSIC:
            if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                return 5200, "Xerosic vs Alakazam"
            if p["opp_hand"] >= 6:
                return 4500, "Xerosic (big hand)"
            return -1, "save Xerosic"
        if cid == LILLIE:
            # E-5: メインドロー（手札を山に戻すので R-11 は実質安全側だが薄い山では止める）
            if self._safe_draws() < 4:
                return -1, "R-11: deck thin (Lillie)"
            # div-G8（2026-07-08 divergence 実測・7/7）: 上位ピロットは Hilda/Xerosic より
            # リーリエを優先して切る（human=Lillie / ours=Hilda,Xerosic）。閾値も手札5枚に緩和
            return (5300 if p["hand_size"] <= 5 else -1), "div-G8: Lillie (main draw)"
        if cid == SURFER:
            # 詰み回避（solo 実測）: 置物アクティブ（技も退却も払えない）の救出に使う
            active = active_pokemon(obs)
            stuck = (active is not None and not payable_attacks(active)
                     and energy_count(active) < retreat_cost(active))
            ready = any(pk.id in self.ATTACKER_IDS and payable_attacks(pk)
                        for pk in my_state(obs).bench if pk)
            if stuck and ready:
                return 6000, "unstick: Surfer out of dead active"
            return -1, "save Surfer"
        if cid == mt.BOSS:
            # E-6: 非リーサルでは温存（リーサルは apply_protocol が昇格）
            return -1, "E-6: save Boss for lethal"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        if cid == POWER_WEIGHT:
            if has_tool(target):
                return -1, "target has tool"
            table = {GARCHOMP_EX: 13000, GABITE: 12500, GIBLE: 12000}
            if tid in table:
                return table[tid], "Power Weight (+70)"
            return -1, "save Power Weight"

        if cid not in ENERGY_CARDS:
            return -500, "skip non-energy"
        if obs.current.energyAttached:
            return -1, "already attached"

        # 詰み回避（solo 実測 2026-07-07）: 技を払えない置物アクティブ（エネ0のロズレイド等）は
        # 退却分のエネを張って交代可能にする（後続のガブリアスがベンチで腐るのを防ぐ）
        active = active_pokemon(obs)
        if (target is active and active is not None
                and not payable_attacks(active)
                and energy_count(active) < retreat_cost(active)
                and any(pk.id in self.ATTACKER_IDS and energy_count(pk) >= 1
                        for pk in my_state(obs).bench if pk)):
            return 8400, "unstick: energize active to retreat"

        e = energy_count(target)
        rock_bonus = 50 if (cid == ROCK_F_ENERGY and tid == GARCHOMP_EX) else 0
        if tid == GARCHOMP_EX:
            # div-G11【ユーザー指示 2026-07-11・LB上位ガブ実装の移植・暫定】:
            # ガブは基本1エネ運用（Corkscrew Dive 100）。2枚目は「Buster なら今の相手
            # バトル場を KO できる（Corkscrew では不可）」時だけ優先し、それ以外は
            # 次のガブ/ガバイト/ミカルゲへの分散を先にする
            if e < 1:
                score, reason = 8300 + rock_bonus, "S-5: fuel Garchomp"
            elif e < 2:
                if self._buster_setup(obs, target):
                    score, reason = 8280 + rock_bonus, "div-G11: 2nd energy for Buster KO"
                else:
                    score, reason = 6500, "div-G11: spread energy first"
            else:
                return -1, "R-10: Garchomp full (Buster=2)"
        elif tid == GABITE:
            score = 8200 if e < 1 else (5500 if e < 2 else -1)   # div-G11: 2枚目は分散の後
            reason = "S-5: pre-load Gabite"
        elif tid == GIBLE:
            score = 8000 if e < 1 else (5400 if e < 2 else -1)   # div-G11: 2枚目は分散の後
            reason = "S-5: pre-load Gible"
        elif tid == SPIRITOMB:
            score = 7500 if e < 1 else -1          # Raging Curse コスト1
            reason = "S-5: enable Raging Curse"
        else:
            return -1, "attach: wrong target"      # ロゼリア系は{G}コストで実質撃てない
        if score > 0 and self.is_threatened(target):
            score -= 2000   # R-08: 負け筋への追い銭防止
        return score, reason

    # ── NUMBER（Corkscrew Dive のドロー数など） ──

    def score_number(self, obs, opt):
        # R-11: 山札切れ圏ではドロー数を絞る
        n = opt.number or 0
        if n > self._safe_draws():
            return -100 - n, "R-11: cap draw count"
        return n, "number"

    # ── CARD/ENERGY 選択（サーチ先・前出し等） ──

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
                # div-G3（2026-07-07 divergence 実測）: 自発的な入替（SWITCH＝にげた後）は
                # ミカルゲの壁/Raging Curse を優先。KO後の建て直し（TO_ACTIVE）は
                # ガブリアス > ガバイト（次のアタッカー）> ミカルゲ
                curse_dmg = self.attack_damage(obs, None, ATK_RAGING_CURSE)
                opp_ps = opp_state(obs)
                opp_act = opp_ps.active[0] if opp_ps.active else None
                if cid == GARCHOMP_EX:
                    # div-G10: エネ付き・より無傷のガブを優先して前へ（ローテーション）
                    score = (15000 + (300 if energy_count(card) >= 1 else 0)
                             - damage_on(card) // 10)
                    reason = "div-G10: promote fresh Garchomp"
                elif cid == SPIRITOMB:
                    if (energy_count(card) >= 1 and opp_act is not None
                            and curse_dmg >= (getattr(opp_act, "hp", 0) or 999)):
                        # div-G13【ユーザー指示 2026-07-11・暫定】: 溜まった Raging Curse が
                        # 相手バトル場を KO できるならミカルゲを前へ（フィニッシャー起動）
                        score, reason = 16000, "div-G13: Spiritomb nuke (Curse KO)"
                    elif (ctx == SelectContext.SWITCH and energy_count(card) >= 1
                          and curse_dmg >= 60):
                        score, reason = 16000, "div-G3: Spiritomb wall (Raging Curse)"
                    else:
                        score, reason = 8000, "promote Spiritomb (1-prize)"
                elif cid == GABITE:
                    score, reason = 9500, "div-G3: promote Gabite (next attacker)"
                elif cid == GIBLE:
                    score, reason = 4000, "promote Gible"
                elif cid == ROSELIA:
                    score, reason = 3500, "promote Roselia"
                elif cid == ROSERADE:
                    score, reason = 3000, "protect Roserade (+30 engine)"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            return 1000, "opp switch"

        if ctx in (SelectContext.DAMAGE, getattr(SelectContext, "DAMAGE_COUNTER", SelectContext.DAMAGE)):
            if card is not None and pi != yi:
                hp = getattr(card, "hp", 999)
                if hp <= 30:
                    return 15000 + (500 - hp), "R-15: chip KO"
                return self.default_score_damage_target(obs, opt)   # R-15: 最低HP優先
            return 0, "damage none"

        if ctx == SelectContext.TO_HAND:
            # div-G4（2026-07-07 divergence 実測）: サーチ先は「いま進化がつながる駒」優先。
            # ガブリアスは場のガバイトに乗せられる時だけ最優先（先取りしない）。
            # エネはがんせきとう > 基本{F}（効果無効の保険）
            # div-G15【棄却 2026-07-11】ガブ囲い込み（fc[GABITE]>=1 で総数3まで 190 先取り）と
            # div-G16【棄却 2026-07-11】rose 系時条件（1体目ロズレイド限定 180 / ロゼリア補充 186）
            # を試したが、TO_HAND 77%→70%（07-08）/ 76%→68%（07-09）に悪化して差し戻し。
            # human=Garchomp 囲い込み盤面と human=ロゼリア/2枚目ロズレイド盤面が同じ φ 特徴
            # （fc/hc カウント）空間で重なる両方向クラスタで、一律の優先変更では分離できない
            # （プロトコル注意3・フーディン div-4 と同型）。詳細は設計md 第3弾の節を参照。
            # div-G17【棄却 2026-07-11】純グング択（基本F/フカマルのみ）のエネ固定優先も試したが、
            # 全決定分布（一致行込み）では human は Gible 32 / BasicF 25 の割れ（シグナル無し）。
            # 不一致行だけで適合させた過学習だった。既存の chomp_line 条件（div-G4）に戻す。
            if cid in (F_ENERGY, ROCK_F_ENERGY):
                menu = {c.id for c in (option_card(obs, o) for o in obs.select.option or [])
                        if c is not None}
                # div-G18【ソフト・暫定 2026-07-11。07-08/09 全決定分布 68件】: エネのみの択
                # （ヒルダ等）は常にがんせきとう（human の 79% = 54/68 が Rock。手札のエネ
                # 構成によらず一貫）。div-G4(b)「がんせきとう > 基本F」の趣旨を、base の
                # 重複ペナルティ（-40/枚）が壊していたのを、この択に限り固定スコアで守る
                if menu and menu <= ENERGY_CARDS and len(menu) == 2:
                    return ((140, "div-G18: take Rock (always)") if cid == ROCK_F_ENERGY
                            else (120, "div-G18: energy menu (Basic)"))
            base = 100 - hc.get(cid, 0) * 40
            if cid == GARCHOMP_EX:
                # div-G9（2026-07-08 divergence 実測・7/7）: ガブリアスの先取りを弱める。
                # 上位ピロットは Gabite/Roserade/Roselia を先に取る（human=Gabite ours=Garchomp が最多）
                path = fc[GABITE] >= 1 and hc[GARCHOMP_EX] == 0
                return base + (52 if path else 25), "div-G9: take Garchomp (later)"
            if cid == GABITE:
                need = fc[GIBLE] >= 1 and hc[GABITE] < fc[GIBLE]
                return base + (85 if need else 20), "div-G4: take Gabite (evolvable)"
            if cid == ROSERADE:
                return base + (58 if fc[ROSELIA] >= 1 else 15), "take Roserade"
            if cid == GIBLE:
                return base + (75 if p["chomp_line"] < 3 else -20), "div-G4: take Gible (pipeline)"
            if cid == ROSELIA:
                return base + (72 if p["rose_line"] < 2 else -20), "div-G4: take Roselia"
            if cid == SPIRITOMB:
                return base + (30 if fc[SPIRITOMB] < 1 else -30), "take Spiritomb"
            if cid == ROCK_F_ENERGY:
                return base + (58 if p["hand_energy"] == 0 else -5), "div-G4: take Rock energy"
            if cid == F_ENERGY:
                return base + (53 if p["hand_energy"] == 0 else -10), "take energy"
            if cid == POWER_WEIGHT:
                return base + 20, "take Power Weight"
            return base, "take other"

        if ctx == SelectContext.TO_BENCH:
            # div-G6 は棄却（2026-07-08: ライン充足でのベンチ抑制を試したが TO_BENCH 71%→67% に
            # 悪化して差し戻し。上位ピロットは3体目のロゼリアも普通に出す）
            if cid == GIBLE:
                return 100, "S-2: bench Gible"
            if cid == ROSELIA:
                return 80, "S-2: bench Roselia"
            if cid == SPIRITOMB:
                return (60 if fc[SPIRITOMB] < 1 else 20), "S-2: bench Spiritomb"
            return 10, "bench other"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            # div-G4（2026-07-07 divergence 実測）: このデッキの R-13 は逆向き —
            # ポケモンは Champion's Call/パッドで引き直せるので手放してよく、
            # エネ（9枚のみ・サーチはグング4だけ）と ACE SPEC を守る
            ids = [c.id for c in (my_state(obs).hand or []) if c]
            if cid == UNFAIR_STAMP:
                return -4000, "div-G4: keep Unfair Stamp (ACE SPEC)"
            if cid in ENERGY_CARDS:
                energy_in_hand = sum(1 for i in ids if i in ENERGY_CARDS)
                if energy_in_hand >= 3:
                    return 5000, "div-G4: discard surplus energy"
                return -3000, "div-G4: keep energy (scarce)"
            if cid in (POFFIN, POKE_PAD, FIGHTING_GONG) and ids.count(cid) > 1:
                return 12000, "div-G4: discard duplicate item"
            if cid in (HILDA, mt.BOSS, SURFER, XEROSIC, LILLIE):
                return 9000, "div-G4: discard supporter"
            if cid in CYNTHIA_POKEMON:
                return 8000, "div-G4: discard pokemon (re-searchable)"
            return 1000, "generic discard"

        if ctx == SelectContext.TO_DECK:
            if cid in GARCHOMP_LINE or cid == ROSERADE:
                return 100, "to deck line"
            return 10, "to deck other"

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(GarchompPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
