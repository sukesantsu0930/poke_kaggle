"""ブリジュラス（Archaludon ex + Cinderace）ルールベースエージェント v2 — BasePolicy 移行版

v1（自己完結、experiments/frozen_agents/archaludon_rb_v1/ に凍結）から共有基盤
policy_base.py へ汎用層を抽出し、このファイルはデッキ固有部分のみを持つ。
挙動は v1 と同一（shadow diff で検証）。

設計文書:
  - docs/planning/デッキ設計_ブリジュラス.md … S-x / E-x / 経路A・B
  - docs/planning/用語とターン手順.md / ルール抽出_オープン実装.md … 用語と R-xx
土台: Kaggle 公開 Notebook "A Sample Archaludon"（masamikobayashi、対 1300+ Starmie 74.4%）
"""

import os
import sys

# sys.path ブートストラップ（base import より前に必須。solo_evaluate は自dirを足さない）
try:
    ROOT = __file__
except NameError:
    ROOT = None
CG_PATH = "/kaggle_simulations/agent"
for p in ([os.path.dirname(os.path.abspath(ROOT))] if ROOT else []) + [CG_PATH]:
    if p and p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

from cg.api import AreaType, OptionType, SelectContext

import meta_tables as mt
from policy_base import (
    AttackPlan,
    BasePolicy,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    count_in_play,
    damage_on,
    discard_ids,
    energy_count,
    first_option_index,
    get_card,
    hand_ids,
    has_in_play,
    has_tool,
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
)

# ── カードID定数（デッキ設計_ブリジュラス.md のリスト） ──

DURALUDON = 169        # ジュラルドン HP130
ARCHALUDON_EX = 190    # ブリジュラス ex HP300
CINDERACE = 666        # エースバーン（Explosiveness 始動）
RELICANTH = 57         # ジーランス（Memory Dive）
METAL_ENERGY = 8

POKE_PAD = 1152
ULTRA_BALL = 1121
POKEGEAR = 1122
NIGHT_STRETCHER = 1097
JUMBO_ICE_CREAM = 1147
HERO_CAPE = 1159
BOSS = mt.BOSS
EXPLORER = 1185
LILLIE = 1227
FULL_METAL_LAB = 1244

RAGING_HAMMER = 224    # {M}{M}{C} 80+ダメカン×10
METAL_DEFENDER = 253   # {M}{M}{M} 220
_ATTACK_BASE_DMG = {METAL_DEFENDER: 220, 965: 50, 223: 30, 61: 30}

CRUSTLE = 345

# S-1: セットアップのアクティブ優先（経路A: エースバーン始動）
_SETUP_ACTIVE_PRIORITY = {
    CINDERACE: (100000, "S-1: Active Cinderace (Explosiveness)"),
    DURALUDON: (20000, "S-1: Active fallback Duraludon (経路B)"),
    RELICANTH: (5000, "S-1: Active fallback Relicanth"),
}

# E-3: 回復判定の閾値（グリッドサーチ実測値）
_ICE_CREAM_HP_THRESHOLD = {
    "lucario": 270,
    "starmie": 210,
    "crustle": 120,
    "hop": 220,
    "generic": 230,
}

ITEMS = {POKE_PAD, ULTRA_BALL, POKEGEAR, NIGHT_STRETCHER, JUMBO_ICE_CREAM, HERO_CAPE}


class ArchaludonPolicy(BasePolicy):
    DECK_NAME = "archaludon_cityleague"
    GO_FIRST = False           # R-21 暫定: 参照実装は後攻。上位ピロットのデータで要確認
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】常にマックス引く
                               # （参照実装・keidroid は NO だったが、ユーザー決定が優先。
                               #   注意: ラダーで凍結中の v1(879.7) は NO のまま）
    ATTACKER_IDS = {ARCHALUDON_EX, DURALUDON}
    ENERGY_IDS = {METAL_ENERGY}
    LINE_PROTECT_IDS = {ARCHALUDON_EX, DURALUDON}   # R-13
    ATTACK_ENERGY_TYPE = 8     # 鋼（弱点×2 計算用）

    # ═══════════════ 判定（デッキ固有） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: ブリジュラスが技をうてる（場に Archaludon ex がいてエネ3枚以上）。"""
        return any(p.id == ARCHALUDON_EX and energy_count(p) >= 3 for p in all_my_pokemon(obs))

    # ═══════════════ 攻撃計画（S-4/E-2: Assemble Alloy 連動の手書きルート） ═══════════════

    def _direct_route(self, obs, pokemon):
        e = energy_count(pokemon)
        if e >= 3:
            return True, False
        if e == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
            return True, True
        return False, False

    def _can_evolve_now(self, pokemon, obs):
        if pokemon is None or pokemon.id != DURALUDON:
            return False
        if ARCHALUDON_EX not in hand_ids(obs):
            return False
        return not getattr(pokemon, "appearThisTurn", True)

    def _alloy_route(self, obs, pokemon):
        # S-4: 進化時の Assemble Alloy（トラッシュから鋼2枚）込みでコスト充足を判定
        if not self._can_evolve_now(pokemon, obs):
            return False, False
        current = energy_count(pokemon)
        alloy = min(2, self._metal_in_discard(obs))
        total = current + alloy
        if total >= 3:
            return True, False
        if total == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
            return True, True
        return False, False

    def _energy_route(self, obs, pokemon):
        if pokemon is None:
            return False, False
        if pokemon.id == ARCHALUDON_EX:
            return self._direct_route(obs, pokemon)
        if pokemon.id == DURALUDON:
            ok, uses_attach = self._direct_route(obs, pokemon)
            if ok:
                return True, uses_attach
            return self._alloy_route(obs, pokemon)
        return False, False

    def _attack_route(self, obs):
        active = active_pokemon(obs)
        if active and active.id in {ARCHALUDON_EX, DURALUDON}:
            ok, uses_attach = self._energy_route(obs, active)
            if ok:
                return {"attacker": active, "uses_attach": uses_attach, "needs_retreat": False}
        if active is None or obs.current.retreated or energy_count(active) < retreat_cost(active):
            return None
        for pokemon in [p for p in my_state(obs).bench if p]:
            if pokemon.id not in {ARCHALUDON_EX, DURALUDON}:
                continue
            ok, uses_attach = self._energy_route(obs, pokemon)
            if ok:
                return {"attacker": pokemon, "uses_attach": uses_attach, "needs_retreat": True}
        return None

    def plan_attacks(self, obs):
        route = self._attack_route(obs)
        if route is None:
            return []
        attacker = route["attacker"]
        nr = route["needs_retreat"]
        ua = route["uses_attach"]
        plans = []
        if attacker.id == ARCHALUDON_EX:
            plans.append(AttackPlan(attacker, METAL_DEFENDER, 220, needs_retreat=nr, uses_attach=ua))
            if has_in_play(obs, RELICANTH):
                plans.append(AttackPlan(attacker, RAGING_HAMMER,
                                        80 + damage_on(attacker) // 10 * 10,
                                        needs_retreat=nr, uses_attach=ua))
        if attacker.id == DURALUDON:
            plans.append(AttackPlan(attacker, RAGING_HAMMER,
                                    80 + damage_on(attacker) // 10 * 10,
                                    needs_retreat=nr, uses_attach=ua))
            if self._can_evolve_now(attacker, obs):
                plans.append(AttackPlan(attacker, METAL_DEFENDER, 220,
                                        needs_retreat=nr, uses_attach=ua,
                                        requires={"evolve_from_hand": ARCHALUDON_EX}))
        return plans

    def best_attack_damage(self, obs, attack_id):
        if attack_id == RAGING_HAMMER:
            return 80 + damage_on(active_pokemon(obs)) // 10 * 10
        return _ATTACK_BASE_DMG.get(attack_id, 0)

    # ═══════════════ 盤面ヘルパー（デッキ固有） ═══════════════

    def _metal_in_discard(self, obs):
        return sum(1 for c in (my_state(obs).discard or []) if c and c.id == METAL_ENERGY)

    def _need_duraludon(self, obs):
        # S-3: ジュラルドン系統は常に2体構え（R-08 との接続点）
        return sum(1 for p in all_my_pokemon(obs) if p.id in {DURALUDON, ARCHALUDON_EX}) < 2

    def _need_archaludon(self, obs):
        has_dura, ex_count = False, 0
        for p in all_my_pokemon(obs):
            if p.id == DURALUDON:
                has_dura = True
            elif p.id == ARCHALUDON_EX:
                ex_count += 1
        return has_dura and ex_count < 2

    def _safe_discard_count(self, obs):
        ids = hand_ids(obs)
        mtd = self._metal_in_discard(obs)
        safe = 0
        for cid in ids:
            if cid == METAL_ENERGY and mtd + safe < 2:
                safe += 1
            elif cid == CINDERACE:
                safe += 1
        draw_in_hand = sum(1 for c in ids if c in (LILLIE, EXPLORER))
        if draw_in_hand >= 2:
            safe += draw_in_hand - 1
        return safe

    # ═══════════════ セットアップコンテキスト（S-1） ═══════════════

    def score_setup_context(self, obs, opt):
        if obs.select.context == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            return _SETUP_ACTIVE_PRIORITY.get(cid, (0, "unknown Active"))
        return super().score_setup_context(obs, opt)

    # ═══════════════ 優先則（フェーズ両方が同一ディスパッチャへ委譲 — v1 と同挙動） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    def _score_any(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.MAIN:
            if opt.type == OptionType.PLAY:
                return self.score_play(obs, opt)
            if opt.type == OptionType.EVOLVE:
                return self.score_evolve(obs, opt)
            if opt.type == OptionType.ATTACH:
                return self.score_attach(obs, opt)
            if opt.type == OptionType.RETREAT:
                return self.score_retreat(obs, opt)
            if opt.type == OptionType.ABILITY:
                return 1, "ability"
            if opt.type == OptionType.ATTACK:
                # R-04: ワザは最後（ターンを終わらせる行動）
                return self.best_attack_damage(obs, opt.attackId), "E-2: attack"
            if opt.type == OptionType.END:
                return 0, "end turn"
            return 500, "generic MAIN"
        if ctx == SelectContext.TO_HAND:
            return self.score_to_hand(obs, opt)
        if ctx in {SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD}:
            return self.score_discard(obs, opt)
        if ctx in {SelectContext.ATTACH_TO, SelectContext.TO_FIELD, SelectContext.TO_BENCH,
                   SelectContext.ATTACH_FROM, SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                   SelectContext.HEAL, SelectContext.DAMAGE}:
            return self.score_target(obs, opt)
        if ctx == SelectContext.ATTACK:
            return self.best_attack_damage(obs, opt.attackId), "E-2: attack"
        if opt.type == OptionType.CARD:
            return self.score_to_hand(obs, opt)
        if opt.type == OptionType.ENERGY:
            return 1000, "energy"
        if opt.type == OptionType.END:
            return 0, "end"
        return 100, "fallback"

    # ── E-3: 回復判定（R-08 の強制発動を先頭に追加済み） ──

    def should_skip_ice_cream(self, obs, active):
        if active.id != ARCHALUDON_EX:
            return True, "skip Ice Cream: not Archaludon ex"

        # R-08: 負け筋を回復で切れるなら最優先（リーサル時はターン手順上こちらに来ない）
        if self.t["lethal"] is None and self.is_threatened(active):
            ice_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id == JUMBO_ICE_CREAM)
            max_hp = getattr(active, "maxHp", active.hp)
            hp_after = min(max_hp, active.hp + ice_count * 80)
            if hp_after > self.opp_max_damage(obs):
                return False, "R-08: heal breaks lethal threat"

        # E-3: Raging Hammer KO ガード
        opp_act = opp_active_pokemon(obs)
        if opp_act and has_in_play(obs, RELICANTH):
            md_kills = self.guard_damage(220, active, opp_act) >= opp_act.hp
            if not md_kills:
                rh_dmg = 80 + damage_on(active) // 10 * 10
                rh_after = 80 + max(0, damage_on(active) - 80) // 10 * 10
                if (self.guard_damage(rh_dmg, active, opp_act) >= opp_act.hp
                        and self.guard_damage(rh_after, active, opp_act) < opp_act.hp):
                    return True, "skip Ice Cream: healing loses Raging Hammer KO"

        # E-3: 対アラカザム all-or-nothing（floor/ceiling 比較）
        matchup = self.t["matchup"]
        if matchup == "alakazam":
            opp = opp_state(obs)
            pokes = ([opp.active[0]] if opp.active else []) + list(opp.bench or [])
            floor, ceiling, _ = mt.estimate_alakazam(opp, pokes)
            opp_a = opp_active_pokemon(obs)
            plans = self.plan_attacks(obs)
            if opp_a and plans and any(
                    self.guard_damage(p.damage, p.attacker, opp_a) >= opp_a.hp for p in plans):
                _, ceiling, _ = mt.estimate_alakazam(opp, opp_bench_pokemon(obs))
            ice_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id == JUMBO_ICE_CREAM)
            max_hp = getattr(active, "maxHp", active.hp)
            hp_after_all = min(max_hp, active.hp + ice_count * 80)
            if hp_after_all <= active.hp:
                return True, "skip Ice Cream: no effective healing"
            if hp_after_all < floor:
                return True, f"skip Ice Cream: even {ice_count}x heal ({hp_after_all}) < floor {floor}"
            return False, f"use Ice Cream: {ice_count}x heal ({hp_after_all}) vs floor={floor} ceil={ceiling}"

        threshold = _ICE_CREAM_HP_THRESHOLD.get(matchup, 220)
        if active.hp > threshold:
            return True, f"skip Ice Cream: HP {active.hp} > {threshold} ({matchup})"
        return False, ""

    # ── PLAY（S-3/S-4/E-3 ボス多段） ──

    def score_play(self, obs, opt):
        card = option_card(obs, opt)
        cid = card.id if card else None
        ids = hand_ids(obs)

        if cid in {DURALUDON, RELICANTH}:
            return 18000, "S-3: play Pokemon"

        if cid == FULL_METAL_LAB:
            active = active_pokemon(obs)
            if active and active.id not in {DURALUDON, ARCHALUDON_EX}:
                return -200, "skip FML: Active not Metal"
            return 20000, "play Full Metal Lab"

        if cid in ITEMS:
            if cid == HERO_CAPE:
                if not any(p.id in {ARCHALUDON_EX, DURALUDON} and not has_tool(p)
                           for p in all_my_pokemon(obs)):
                    return -500, "save Hero's Cape: no target"
            if cid == JUMBO_ICE_CREAM:
                active = active_pokemon(obs)
                if active:
                    skip, reason = self.should_skip_ice_cream(obs, active)
                    if skip:
                        return -500, reason
            if cid == NIGHT_STRETCHER:
                disc = discard_ids(obs)
                has_urgent = (
                    (DURALUDON in disc and DURALUDON not in ids
                     and count_in_play(obs, DURALUDON) + count_in_play(obs, ARCHALUDON_EX) <= 1)
                    or (ARCHALUDON_EX in disc and ARCHALUDON_EX not in ids and has_in_play(obs, DURALUDON))
                    or (METAL_ENERGY in disc and not obs.current.energyAttached
                        and sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY) == 0
                        and any(p and p.id in (DURALUDON, ARCHALUDON_EX) and energy_count(p) == 2
                                for p in all_my_pokemon(obs)))
                )
                if not has_urgent:
                    return -500, "save Night Stretcher"
            if cid == ULTRA_BALL:
                bench_empty = len([p for p in my_state(obs).bench if p]) == 0
                if bench_empty:
                    return 300, "R-03: Ultra Ball bench empty (donk risk)"
                metal_in_hand = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)
                metal_in_trash = self._metal_in_discard(obs)
                if metal_in_trash == 0 and metal_in_hand >= 1:
                    return 20000, "S-4/経路B: Ultra Ball fuel Alloy"
                if self._safe_discard_count(obs) >= 2 and (self._need_archaludon(obs) or self._need_duraludon(obs)):
                    return 20000, "Ultra Ball: search line"
                return -1000, "skip Ultra Ball"
            return 20000, "play item"

        if cid == EXPLORER:
            if obs.current.supporterPlayed:
                return -1000, "Supporter already used"
            return 16000, "play Explorer"

        if cid == LILLIE:
            if obs.current.supporterPlayed:
                return -1000, "Supporter already used"
            if BOSS in ids and self.plan_attacks(obs):
                return -500, "save Lillie: Boss in hand with attacker ready"
            return 5000, "play Lillie"

        if cid == BOSS:
            # E-3 ボス多段: リーサルはターン手順が LETHAL_BAND に昇格済み。ここは温存/吊り出し/スタール
            if obs.current.supporterPlayed:
                return -1000, "Supporter already used"
            if self.t["matchup"] == "hop":
                active = active_pokemon(obs)
                opp_has_snorlax = any(p.id == mt.HOP_SNORLAX for p in opp_bench_pokemon(obs))
                if opp_has_snorlax and active:
                    if active.id == CINDERACE:
                        has_dura_bench = any(p.id in {DURALUDON, ARCHALUDON_EX}
                                             for p in my_state(obs).bench if p)
                        if has_dura_bench:
                            return 16500, "E-3: Boss pull Snorlax (Cinderace Turbo Flare)"
                    if active.id == ARCHALUDON_EX and active.hp > 220:
                        ok, _ = self._energy_route(obs, active)
                        if ok:
                            return 16500, "E-3: Boss pull Snorlax (tank Revenge)"
            if self.opp_last_attack_id == mt.MEGA_BRAVE:
                return -500, "E-3: save Boss (Mega Brave stuck)"
            plans = self.plan_attacks(obs)
            if not plans:
                return -500, "save Boss: no attacker"
            opp_act = opp_active_pokemon(obs)
            can_ko_active = opp_act and any(
                self.guard_damage(p.damage, p.attacker, opp_act) >= opp_act.hp for p in plans)
            if can_ko_active:
                return -500, "save Boss: can KO Active"
            best_score = -500
            best_reason = "save Boss"
            for target in opp_bench_pokemon(obs):
                for p in plans:
                    if self.guard_damage(p.damage, p.attacker, target) >= target.hp:
                        pv = prize_value(target)
                        s = 4000 + pv * 200 + energy_count(target) * 100
                        if s > best_score:
                            best_score = s
                            best_reason = "E-3: Boss pull bench target"
                        break
            if best_score <= 0:
                # E-3 ボススタール: 攻め手がない時、動けないベンチを引きずり出して時間を稼ぐ
                metal_total = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)
                metal_total += sum(energy_count(p) for p in all_my_pokemon(obs) if p)
                has_cind = has_in_play(obs, CINDERACE)
                draw_in_hand = any(c and c.id in (EXPLORER, LILLIE) for c in (my_state(obs).hand or []) if c)
                if metal_total <= 2 and not has_cind and not draw_in_hand:
                    from policy_base import CARD_DB, ATTACK_TABLE
                    best_stall = -500
                    stall_reason = "save Boss"
                    for target in opp_bench_pokemon(obs):
                        te = energy_count(target)
                        cd = CARD_DB.get(target.id)
                        rc = cd.retreatCost if cd else 0
                        min_atk = 99
                        if cd and cd.attacks:
                            for aid in cd.attacks:
                                atk = ATTACK_TABLE.get(aid)
                                if atk:
                                    min_atk = min(min_atk, len(atk.energies))
                        if min_atk == 99:
                            min_atk = 1
                        ss = 4000 + rc * 1000 + min_atk * 500 - te * 800
                        if ss > best_stall:
                            best_stall = ss
                            stall_reason = "E-3: Boss stall"
                    return best_stall, stall_reason
            return best_score, best_reason

        return 1000, "generic play"

    # ── EVOLVE（S-4: Assemble Alloy 連動） ──

    def score_evolve(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        cid = card.id if card else None
        tid = target.id if target else None
        if cid == ARCHALUDON_EX and tid == DURALUDON:
            target_is_active = opt.inPlayArea == AreaType.ACTIVE
            mc = self._metal_in_discard(obs)
            if target_is_active:
                if energy_count(target) >= 3 and not has_in_play(obs, ARCHALUDON_EX):
                    return 17000, "S-4: evolve Active 3-energy Duraludon"
                if mc >= 2:
                    return 28000 + mc * 2000, "S-4: evolve Active Duraludon (Alloy x2)"
                if mc == 1:
                    return 8000, "S-4: delay Active evolve (1 Metal)"
                return -500, "S-4: hold, no Metal in discard"
            if mc >= 2:
                return 14000 + mc * 1000, "S-4: evolve Bench Duraludon"
            return -1000, "S-4: hold, evolve Active first"
        return 10000, "generic evolution"

    # ── ATTACH（S-2/S-5 + R-10 相当 + R-08 追い銭防止） ──

    def attach_target_score(self, obs, target, area):
        if target is None:
            return 0
        cid = target.id
        e = energy_count(target)

        if e >= 3:
            return -5000   # R-10 相当（Metal Defender コスト3枚由来）
        if cid == CINDERACE and e >= 1:
            return -3000

        score = 0
        if cid == CINDERACE:
            score = 3000
            if e == 0:
                score += 7000 + (12000 if area == AreaType.ACTIVE else 5000)
        elif cid in {DURALUDON, ARCHALUDON_EX}:
            score = 6000 if cid == ARCHALUDON_EX else 5500
            score += {2: 12000, 1: 7000, 0: 4000}.get(e, -1000)
            score += 1000 if area == AreaType.ACTIVE else 500
        else:
            score = 1000 + (1000 if e == 0 else 0)

        if target.hp > 0:
            max_hp = getattr(target, "maxHp", target.hp)
            ratio = target.hp / max_hp if max_hp > 0 else 1
            if ratio <= 0.25:
                score -= 1500
            elif ratio <= 0.50:
                score -= 500
            else:
                score += min(1000, target.hp // 40 * 100)

        # R-08: 「取られたら負け」圏のポケモンにエネを注ぎ足さない
        if self.is_threatened(target):
            score -= 2000
        return score

    def score_attach(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        cid = card.id if card else None
        tid = target.id if target else None

        if cid == HERO_CAPE:
            if tid == ARCHALUDON_EX and target and not has_tool(target):
                return 11000, "Hero's Cape on Archaludon ex"
            if tid == DURALUDON and target and not has_tool(target) and energy_count(target) >= 1:
                return 8000, "Hero's Cape on Duraludon"
            return -1000, "save Hero's Cape"

        if cid != METAL_ENERGY:
            return -500, "skip non-Metal"
        if obs.current.energyAttached:
            return -1000, "already attached"

        return self.attach_target_score(obs, target, opt.inPlayArea), "S-5: attach Metal"

    # ── RETREAT ──

    def score_retreat(self, obs, opt):
        active = active_pokemon(obs)
        if active and active.id == ARCHALUDON_EX and has_tool(active) and active.hp > 200:
            return -5000, "don't retreat HP400 tank"
        route = self._attack_route(obs)
        if route and route["needs_retreat"]:
            return 13000, "retreat to attack-ready ex"
        return -100, "avoid retreat"

    # ── TO_HAND（S-3、Explorer effect 対応） ──

    def score_to_hand(self, obs, opt):
        card = option_card(obs, opt)
        cid = card.id if card else opt.cardId
        ids = hand_ids(obs)
        effect = getattr(obs.select, "effect", None)
        effect_id = effect.id if effect else None

        if effect_id == EXPLORER:
            has_ready = any(p and p.id in (DURALUDON, ARCHALUDON_EX) and energy_count(p) >= 3
                            for p in all_my_pokemon(obs))
            metal_in_hand = sum(1 for c in (my_state(obs).hand or []) if c and c.id == METAL_ENERGY)

            if cid == HERO_CAPE:
                has_target = any(p.id == ARCHALUDON_EX and not has_tool(p) for p in all_my_pokemon(obs))
                return (27000 if has_target else 22000), "Explorer: Hero's Cape"
            if cid == METAL_ENERGY:
                if has_ready or metal_in_hand > 0:
                    return 0, "Explorer: skip energy"
                if getattr(opt, 'index', 0) == first_option_index(obs, METAL_ENERGY):
                    return 25000, "Explorer: take 1st energy"
                return 0, "Explorer: skip 2nd energy"
            if cid == ARCHALUDON_EX and self._need_archaludon(obs):
                return 20000, "Explorer: take Archaludon ex"
            if cid == DURALUDON and self._need_duraludon(obs):
                return 18000, "Explorer: take Duraludon"
            if cid == RELICANTH and not has_in_play(obs, RELICANTH) and RELICANTH not in ids:
                return 15000, "Explorer: take Relicanth"
            sup_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id in (EXPLORER, LILLIE))
            if cid in (EXPLORER, LILLIE) and sup_count == 0:
                return 12000, "Explorer: take supporter"
            return 0, "Explorer: let discard"

        dura_ex_count = count_in_play(obs, DURALUDON) + count_in_play(obs, ARCHALUDON_EX)
        if cid == DURALUDON and DURALUDON not in ids and dura_ex_count <= 1:
            return 22000, "S-3: take Duraludon backup"
        if cid == ARCHALUDON_EX and self._need_archaludon(obs):
            return 20000, "take Archaludon ex"
        if cid == DURALUDON and self._need_duraludon(obs):
            return 18000, "take Duraludon"
        if cid == CINDERACE:
            return -2000, "skip Cinderace (Explosiveness only)"
        if cid == RELICANTH and not has_in_play(obs, RELICANTH):
            return 9000, "take Relicanth"
        if cid == METAL_ENERGY:
            return 8000, "take Metal Energy"
        if cid == EXPLORER and not obs.current.supporterPlayed:
            return 7500, "take Explorer"
        if cid == LILLIE and not obs.current.supporterPlayed:
            return 6500, "take Lillie"
        if cid == HERO_CAPE:
            has_target = any(p.id == ARCHALUDON_EX and not has_tool(p) for p in all_my_pokemon(obs))
            return (6000, "take Hero's Cape") if has_target else (1000, "generic take")
        if cid == FULL_METAL_LAB:
            return 5000, "take Full Metal Lab"
        if cid == BOSS:
            return 2500, "take Boss"
        return 1000, "generic take"

    # ── DISCARD（R-13、Ultra Ball effect 対応） ──

    def score_discard(self, obs, opt):
        card = option_card(obs, opt)
        cid = card.id if card else opt.cardId
        ids = hand_ids(obs)
        mtd = self._metal_in_discard(obs)
        effect = getattr(obs.select, "effect", None)
        effect_id = effect.id if effect else None

        if effect_id == ULTRA_BALL:
            mh = ids.count(METAL_ENERGY)
            if cid == METAL_ENERGY:
                if mtd < 2 and mh >= 1:
                    if getattr(opt, 'index', None) == first_option_index(obs, METAL_ENERGY):
                        return 20000, "S-4: UB discard 1st Metal (fuel Alloy)"
                    return 8000, "UB: 2nd Metal"
                return 8000, "UB: Metal"
            if cid == CINDERACE:
                return (18000, "UB: Cinderace") if (mtd >= 2 or mh == 0) else (14000, "UB: Cinderace")
            draw_count = ids.count(LILLIE) + ids.count(EXPLORER)
            if cid in (LILLIE, EXPLORER) and draw_count >= 2:
                return (12000 if cid == LILLIE else 11000), "UB: surplus supporter"
            if cid == ULTRA_BALL and ids.count(ULTRA_BALL) > 1:
                return 10000, "UB: duplicate"
            if cid in (LILLIE, EXPLORER) and draw_count <= 1:
                return -3000, "UB: keep last supporter"

        if cid == METAL_ENERGY:
            if mtd < 2:
                return 15000, "S-4: discard Metal (fuel Alloy)"
            return (12000, "discard extra Metal") if ids.count(METAL_ENERGY) > 1 else (-1000, "keep last Metal")
        if cid == CINDERACE:
            return 10000, "discard Cinderace"
        if cid in {BOSS, FULL_METAL_LAB, POKEGEAR}:
            return 8500, "discard utility"
        if cid in {LILLIE, EXPLORER} and ids.count(cid) > 1:
            return 8000, "discard duplicate supporter"
        if cid == RELICANTH and (has_in_play(obs, RELICANTH) or ids.count(RELICANTH) > 1):
            return 6500, "discard extra Relicanth"
        if cid == ARCHALUDON_EX:
            return -5000, "R-13: keep Archaludon ex"
        if cid == DURALUDON:
            return -4000, "R-13: keep Duraludon"
        return 1000, "generic discard"

    # ── ターゲット系（E-3 ボス対象 / R-08 前出しマスク / R-15） ──

    def score_target(self, obs, opt):
        card = option_card(obs, opt)
        cid = card.id if card else opt.cardId
        ctx = obs.select.context

        if ctx == SelectContext.ATTACH_TO:
            return (5000, "Metal") if cid == METAL_ENERGY else (1000, "attach")

        if ctx == SelectContext.ATTACH_FROM:
            if card and energy_count(card) >= 3:
                return -5000, "R-10相当: skip 3+ energy"
            if card and cid == CINDERACE and energy_count(card) >= 1:
                return -3000, "skip: Cinderace ready"
            return self.attach_target_score(obs, card, opt.area), "S-2: effect attach"

        if ctx in {SelectContext.TO_FIELD, SelectContext.TO_BENCH}:
            if cid == ARCHALUDON_EX:
                return 18000, "target Archaludon ex"
            if cid == DURALUDON:
                return 16000, "target Duraludon"
            if cid == CINDERACE:
                return 3000, "avoid Cinderace"

        if ctx == SelectContext.HEAL:
            return (20000 + damage_on(card), "heal Archaludon ex") if cid == ARCHALUDON_EX else (damage_on(card), "heal")

        if ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
            yi = obs.current.yourIndex
            pi = getattr(opt, 'playerIndex', yi)
            if pi != yi and card:
                # 相手側 = ボスの吊り出し対象 (E-3)。リーサル対象はターン手順が昇格させる
                if self.t["matchup"] == "hop" and cid == mt.HOP_SNORLAX and card:
                    active = active_pokemon(obs)
                    e = energy_count(card)
                    tools = len(getattr(card, 'tools', None) or [])
                    if active and active.id == CINDERACE:
                        return 30000 - e * 100 - tools * 50 + card.hp, "E-3: Boss Snorlax (immobile)"
                    return 30000 + e * 100 + tools * 50 + card.hp, "E-3: Boss Snorlax (biggest threat)"
                pv = prize_value(card)
                te = energy_count(card)
                killable = any(self.guard_damage(p.damage, p.attacker, card) >= card.hp
                               for p in self.plan_attacks(obs))
                if killable:
                    return 20000 + pv * 3000 + te * 100, "E-3: Boss KO"
                return 5000 + pv * 1000 + te * 200, "E-3: Boss drag"
            # 自分側 = 前出し選択（R-08 マスクは default_score_promote が適用）
            score, reason = 1000, "generic promote"
            if cid == CINDERACE:
                score, reason = 16000, "promote Cinderace (retreat 0)"
            elif cid == ARCHALUDON_EX:
                score, reason = 15000, "promote Archaludon ex"
            elif cid == DURALUDON:
                score, reason = 8000, "promote Duraludon"
            return self.default_score_promote(obs, opt, score, reason)

        if ctx == SelectContext.DAMAGE:
            return self.default_score_damage_target(obs, opt)   # R-15

        return 1000, "generic target"

    # ── マッチアップ上書き（E-3 クラッスル + R-11 低山札） ──

    def apply_overrides(self, obs, opt, score, reason):
        # R-11 系: 山札が薄い時のドロー封印
        if opt.type == OptionType.PLAY:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if my_state(obs).deckCount <= 10 and cid == EXPLORER:
                return -5000, "R-11: don't Explorer with low deck"

        if self.t["matchup"] != "crustle":
            return score, reason

        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, 'cardId', None)
        ctx = obs.select.context

        if opt.type == OptionType.EVOLVE and cid == ARCHALUDON_EX:
            return -10000, "Crustle: don't evolve to ex"

        if opt.type == OptionType.ATTACK:
            aid = getattr(opt, 'attackId', None)
            active = active_pokemon(obs)
            opp_act = opp_active_pokemon(obs)
            opp_has_spiky = bool(opp_act and any(
                getattr(c, 'id', None) == 14
                for c in (getattr(opp_act, 'energyCards', None) or [])))
            if (active and active.id == DURALUDON and active.hp == 130
                    and opp_act and opp_act.id == CRUSTLE and energy_count(opp_act) >= 2
                    and opp_has_spiky):
                return -3000, "Crustle: full HP Duraludon waits out Spiky"
            if aid == METAL_DEFENDER:
                return -5000, "Crustle: Metal Defender does 0"
            if aid == RAGING_HAMMER:
                return max(score, 200), "Crustle: Raging Hammer"

        if opt.type == OptionType.PLAY:
            if cid == RELICANTH:
                return -5000, "Crustle: skip Relicanth"
            dc = my_state(obs).deckCount
            if dc <= 10 and cid in (EXPLORER, LILLIE):
                if cid == LILLIE and dc <= 3 and my_state(obs).handCount >= dc + 6:
                    return 15000, "R-11: Lillie to refill deck"
                return -5000, "R-11: don't draw with low deck"
            if cid == LILLIE:
                has_metal = any(c and c.id == METAL_ENERGY for c in (my_state(obs).hand or []) if c)
                if not has_metal:
                    return score, "Crustle: Lillie OK (no energy in hand)"

        if opt.type == OptionType.ATTACH:
            target = option_target(obs, opt)
            tid = target.id if target else None
            if getattr(opt, 'inPlayArea', None) == AreaType.BENCH and tid == DURALUDON:
                return score + 10000, "Crustle: bench Duraludon energy priority"
            if getattr(opt, 'inPlayArea', None) == AreaType.ACTIVE:
                active = active_pokemon(obs)
                if active and energy_count(active) >= 2:
                    return score + 3000, "Crustle: Active 3rd energy"

        if ctx == SelectContext.TO_HAND and opt.type == OptionType.CARD and cid == ARCHALUDON_EX:
            return -3000, "Crustle: skip Archaludon ex"

        if ctx in {SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD}:
            if cid == ARCHALUDON_EX and score < 0:
                return 9000, "Crustle: discard Archaludon ex"

        return score, reason


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(ArchaludonPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
