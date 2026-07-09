"""フーディン（Alakazam / Powerful Hand）ルールベースエージェント — BasePolicy 版

土台: Kaggle 公開 Notebook "Rule-based, not psychic: Alakazam"（sue124、最高LB5位、Apache-2.0系譜）。
その方策（手札純増モデル・3段ターゲット選択・Enhanced Hammer 会計・safe_draws 山札ガード）を
共有基盤 BasePolicy のフックに移植した。

設計文書: docs/planning/デッキ設計_フーディン.md（S-0/可変打点モデル/未決事項）
ルールタグ: R-07(リーサル)/R-08(負け筋)/R-11(山札切れ)/R-12(特性温存)/R-21・R-22(暫定)

実装上の要点（設計mdより）: judge_lethal は「現在手札での確定打点」で判定する。
投影打点(max)での昇格は早撃ちを誘発するため、手札を増やす過程はスコア側
（ドロー系 > 攻撃）が担い、確定した時点でターン手順が発火する。
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
    get_card,
    make_agent,
    my_state,
    opp_state,
    option_card,
    read_deck_csv as _read_deck_csv,
)

# ── カードID（デッキ設計_フーディン.md のリスト） ──

ABRA = 741
KADABRA = 742
ALAKAZAM = 743
DUNSPARCE = 305
DUDUNSPARCE = 66
FEZANDIPITI_EX = 140
GENESECT = 142
PSYDUCK = 858
SHAYMIN = 343
RARE_CANDY = 1079
ENHANCED_HAMMER = 1081
POFFIN = 1086
NIGHT_STRETCHER = 1097
SACRED_ASH = 1129
POKE_PAD = 1152
LUCKY_HELMET = 1156
BOSS = mt.BOSS
HILDA = 1225
DAWN = 1231
BATTLE_CAGE = 1264
PSY_ENERGY = 5
TELEPATH_ENERGY = 19
ENRICHING_ENERGY = 13

# 相手の監視対象（テックカードの出場ゲート）
DUSKULL = 131
SLOWPOKE_IDS = (162, 327)
FROAKIE_IDS = (33, 945)
OGERPON_WELLSPRING = 108
N_DARUMAKA = 257
DRAGAPULT_LINE = (119, 120, 121)
MIST_ENERGY = 11
ROCK_FIGHTING_ENERGY = 20

# 技ID
ATK_TELEPORTATION = 1070   # Abra 10 {P}
ATK_SUPER_PSY_BOLT = 1071  # Kadabra 30 {P}
ATK_POWERFUL_HAND = 1072   # Alakazam 手札×20 {P}

ABRA_LINE = {ABRA, KADABRA, ALAKAZAM}
DUNSPARCE_LINE = {DUNSPARCE, DUDUNSPARCE}
PSYCHIC_ENERGY_IDS = {PSY_ENERGY, TELEPATH_ENERGY}


def _prize_count(pokemon):
    """参照実装版のサイド価値（Legacy Energy / Lillie's Pearl 補正付き）。"""
    data = CARD_DB[pokemon.id]
    count = 3 if data.megaEx else 2 if data.ex else 1
    for card in pokemon.energyCards:
        if card.id == 12:  # Legacy Energy
            count -= 1
    for card in pokemon.tools:
        if card.id == 1172 and "Lillie" in data.name:
            count -= 1
    return max(0, count)


def _special_defense_count(pokemon):
    return sum(1 for ec in pokemon.energyCards
               if ec.id in (MIST_ENERGY, ROCK_FIGHTING_ENERGY))


class AlakazamPolicy(BasePolicy):
    DECK_NAME = "alakazam_5th"
    GO_FIRST = True            # R-21 暫定: 参照実装は実質「先攻」選択。要データ確認
    TAKE_MULLIGAN = True       # R-22 暫定: 手札×20 デッキなので引き取る。Archaludon と逆（デッキ固有の実例）
    ATTACKER_IDS = ABRA_LINE
    ENERGY_IDS = {PSY_ENERGY, TELEPATH_ENERGY, ENRICHING_ENERGY}
    LINE_PROTECT_IDS = ABRA_LINE | DUNSPARCE_LINE   # R-13

    def __init__(self):
        super().__init__()
        self._pre_turn = 0
        self._used_dudunsparce = False   # R-12: ターン内の特性使用フラグ
        self._used_fezandipiti = False
        self._op_used_ace_spec = False   # logs はデルタなので永続化して追跡
        self.p = {}

    def reset_game(self):
        super().reset_game()
        self._pre_turn = 0
        self._used_dudunsparce = False
        self._used_fezandipiti = False
        self._op_used_ace_spec = False
        self.p = {}

    # ═══════════════ ターン分析（参照実装の計画部を毎手番実行） ═══════════════

    def choose(self, obs):
        self.p = self._analyze(obs)
        selected = super().choose(obs)
        # R-12: MAIN で特性を選んだらターン内フラグを立てる（参照実装と同じ）
        if obs.select.context == SelectContext.MAIN and selected:
            o = obs.select.option[selected[0]]
            if o.type == OptionType.ABILITY:
                card = get_card(obs, o.area, o.index, obs.current.yourIndex)
                if card is not None:
                    if card.id == DUDUNSPARCE:
                        self._used_dudunsparce = True
                    elif card.id == FEZANDIPITI_EX:
                        self._used_fezandipiti = True
        return selected

    def _analyze(self, obs):
        state = obs.current
        ms = my_state(obs)
        os_ = opp_state(obs)
        my_prize = len(ms.prize)

        if self._pre_turn != state.turn:
            self._pre_turn = state.turn
            self._used_dudunsparce = False
            self._used_fezandipiti = False

        field_counts = defaultdict(int)
        hand_counts = defaultdict(int)
        discard_counts = defaultdict(int)
        my_field = []
        for card in ms.active:
            if card is not None:
                field_counts[card.id] += 1
                my_field.append((0, card))
        for idx, card in enumerate(ms.bench):
            if card is not None:
                field_counts[card.id] += 1
                my_field.append((idx + 1, card))
        for card in (ms.hand or []):
            if card is not None:
                hand_counts[card.id] += 1
        for card in (ms.discard or []):
            if card is not None:
                discard_counts[card.id] += 1

        abra_line_on_field = field_counts[ABRA] + field_counts[KADABRA] + field_counts[ALAKAZAM]
        dunsparce_line_on_field = field_counts[DUNSPARCE] + field_counts[DUDUNSPARCE]

        op_all = [p for p in (os_.active + os_.bench) if p is not None]
        op_has_duskull = any(p.id == DUSKULL for p in op_all)
        op_has_water_threat = any(
            p.id in SLOWPOKE_IDS or p.id in FROAKIE_IDS
            or p.id == OGERPON_WELLSPRING or p.id == N_DARUMAKA
            for p in op_all)
        op_has_dragapult = any(p.id in DRAGAPULT_LINE for p in op_all)

        # 相手の ACE SPEC 使用検出（logs デルタ → 永続フラグ）
        for log in obs.logs:
            if getattr(log, 'cardId', None) is not None:
                cd = CARD_DB.get(log.cardId)
                if (cd and getattr(cd, 'aceSpec', False)
                        and getattr(log, 'playerIndex', None) == (1 - state.yourIndex)):
                    self._op_used_ace_spec = True

        stadium_id = 0
        for card in state.stadium:
            stadium_id = card.id

        bench_free = ms.benchMax - len(ms.bench)

        active = ms.active[0] if ms.active else None
        active_id = active.id if active else -1
        active_has_psychic = bool(active and any(
            ec.id in PSYCHIC_ENERGY_IDS for ec in active.energyCards))

        op_active = os_.active[0] if os_.active else None
        op_active_hp = op_active.hp if op_active else 9999

        hand_size = len(ms.hand) if ms.hand else ms.handCount

        # ── 可変打点モデル: 手札純増の min/max（設計md「可変打点モデル」） ──
        max_inc = 0
        for _, pk in my_field:
            if pk.id == ABRA and hand_counts[KADABRA] > 0:
                max_inc += 1
            elif pk.id == ABRA and hand_counts[RARE_CANDY] > 0 and hand_counts[ALAKAZAM] > 0:
                max_inc += 1
            elif pk.id == KADABRA and hand_counts[ALAKAZAM] > 0:
                max_inc += 2
            elif pk.id == DUNSPARCE and hand_counts[DUDUNSPARCE] > 0:
                max_inc += 1
            elif pk.id == DUDUNSPARCE:
                if not self._used_dudunsparce:
                    max_inc += 3
            elif pk.id == FEZANDIPITI_EX:
                if not self._used_fezandipiti:
                    max_inc += 3
        if hand_counts[FEZANDIPITI_EX] > 0 and bench_free > 0 and field_counts[FEZANDIPITI_EX] == 0:
            max_inc += 2
        supporter_options = []
        if not state.supporterPlayed:
            if hand_counts[HILDA] > 0:
                supporter_options.append(1)
            if hand_counts[DAWN] > 0:
                supporter_options.append(2)
            if hand_counts[BOSS] > 0:
                supporter_options.append(-1)
        if supporter_options:
            max_inc += max(supporter_options)
        if hand_counts[ENRICHING_ENERGY] > 0 and not state.energyAttached:
            if active_id == ALAKAZAM and active_has_psychic:
                max_inc += 3

        max_hand_size = hand_size + max_inc
        max_damage = max_hand_size * 20

        # ── 3段ターゲット選択（R-07 の実装形）+ ハンマー会計 ──
        target_idx = -1
        target_pokemon = None
        target_use_boss = False
        target_can_kill = False
        target_prize_gain = 0
        target_hammer_needed = 0
        use_kadabra_finish = False

        if state.turn >= 2 and op_active is not None:
            if op_active_hp <= 30 and (field_counts[KADABRA] >= 1 or active_id == KADABRA):
                target_idx = 0
                target_pokemon = op_active
                target_can_kill = True
                target_prize_gain = _prize_count(op_active)
                use_kadabra_finish = True
            else:
                all_op = [(0, op_active)]
                for bi, bp in enumerate(os_.bench):
                    if bp is not None:
                        all_op.append((bi + 1, bp))
                candidates = []
                for oi, pkmn in all_op:
                    pz = _prize_count(pkmn)
                    sp_e = _special_defense_count(pkmn)
                    eff_max_dmg = max_damage
                    hm_need = 0
                    if sp_e > 0:
                        if hand_counts[ENHANCED_HAMMER] >= sp_e:
                            hm_need = sp_e
                            eff_max_dmg = (max_hand_size - hm_need) * 20
                        else:
                            eff_max_dmg = 0
                    ck = pkmn.hp <= eff_max_dmg and eff_max_dmg > 0
                    candidates.append((oi, pkmn, pz, ck, hm_need))
                win_cands = [c for c in candidates if c[3] and my_prize <= c[2]]
                if win_cands:
                    best = min(win_cands, key=lambda x: (0 if x[0] == 0 else 1, -x[1].hp))
                    target_idx, target_pokemon, target_prize_gain, target_can_kill, target_hammer_needed = best
                    target_use_boss = target_idx != 0
                else:
                    killable = [c for c in candidates if c[3]]
                    if killable:
                        best = max(killable, key=lambda x: (x[2], x[1].hp))
                        target_idx, target_pokemon, target_prize_gain, target_can_kill, target_hammer_needed = best
                        target_use_boss = target_idx != 0
                    else:
                        target_idx = 0
                        target_pokemon = op_active
                        target_can_kill = False

        # R-12: 特性は KO に必要な時だけ
        need_dudunsparce_draw = False
        if target_pokemon is not None and target_can_kill:
            if (hand_size - target_hammer_needed) * 20 < target_pokemon.hp:
                need_dudunsparce_draw = True

        # にげる用のエネ付与が必要か
        need_retreat_energy = False
        if active is not None and state.turn >= 2:
            active_is_attacker = ((active_id == ALAKAZAM and active_has_psychic)
                                  or (use_kadabra_finish and active_id == KADABRA))
            if not active_is_attacker:
                has_bench_attacker = (
                    (use_kadabra_finish and field_counts[KADABRA] >= 1 and active_id != KADABRA)
                    or (field_counts[ALAKAZAM] >= 1 and active_id != ALAKAZAM)
                    or (field_counts[KADABRA] >= 1 and active_id != KADABRA))
                if has_bench_attacker:
                    rc = CARD_DB[active.id].retreatCost
                    if len(active.energies) < rc:
                        need_retreat_energy = True

        # R-12: Fez は打点必要時 or セットアップ欠け時のみ
        fez_contrib = 0
        if field_counts[FEZANDIPITI_EX] >= 1 and not self._used_fezandipiti:
            fez_contrib = 3
        elif hand_counts[FEZANDIPITI_EX] > 0 and bench_free > 0 and field_counts[FEZANDIPITI_EX] == 0:
            fez_contrib = 2
        need_fez_draw = False
        if target_pokemon is not None and target_can_kill and fez_contrib > 0:
            if (max_hand_size - fez_contrib - target_hammer_needed) * 20 < target_pokemon.hp:
                need_fez_draw = True
        need_fez_setup = False
        if target_pokemon is not None and target_can_kill and fez_contrib > 0 and not need_fez_draw:
            missing_boss = (target_use_boss and hand_counts[BOSS] == 0
                            and not state.supporterPlayed)
            has_ready = (active_id == ALAKAZAM and active_has_psychic)
            if not has_ready:
                for _, pk in my_field:
                    if pk.id == ALAKAZAM and any(ec.id in PSYCHIC_ENERGY_IDS for ec in pk.energyCards):
                        has_ready = True
                        break
            missing_attacker = False
            missing_energy = False
            if not has_ready:
                can_evolve = (field_counts[KADABRA] >= 1 and hand_counts[ALAKAZAM] >= 1)
                can_candy = (field_counts[ABRA] >= 1 and hand_counts[RARE_CANDY] >= 1
                             and hand_counts[ALAKAZAM] >= 1)
                if not can_evolve and not can_candy:
                    if field_counts[KADABRA] >= 1 and hand_counts[ALAKAZAM] == 0:
                        missing_attacker = True
                    elif field_counts[ABRA] >= 1 and (hand_counts[RARE_CANDY] == 0 or hand_counts[ALAKAZAM] == 0):
                        missing_attacker = True
                energy_in_hand = (hand_counts[PSY_ENERGY] + hand_counts[TELEPATH_ENERGY]
                                  + hand_counts[ENRICHING_ENERGY])
                if not state.energyAttached and energy_in_hand == 0:
                    has_energized = any(
                        pk.id in ABRA_LINE and any(ec.id in PSYCHIC_ENERGY_IDS for ec in pk.energyCards)
                        for _, pk in my_field)
                    if not has_energized:
                        missing_energy = True
            if missing_boss or missing_attacker or missing_energy:
                need_fez_setup = True

        # R-11: 山札切れガード（勝ち切りターンは解除）
        can_win = target_can_kill and my_prize <= target_prize_gain
        safe_draws = ms.deckCount - my_prize - 1 if not can_win else 999

        return {
            "field_counts": field_counts, "hand_counts": hand_counts,
            "discard_counts": discard_counts, "my_field": my_field,
            "abra_line": abra_line_on_field, "dunsparce_line": dunsparce_line_on_field,
            "op_all": op_all, "op_has_duskull": op_has_duskull,
            "op_has_water_threat": op_has_water_threat, "op_has_dragapult": op_has_dragapult,
            "stadium_id": stadium_id, "bench_free": bench_free,
            "active_id": active_id, "active_has_psychic": active_has_psychic,
            "op_active_hp": op_active_hp, "hand_size": hand_size,
            "max_hand_size": max_hand_size, "max_damage": max_damage,
            "target_idx": target_idx, "target_pokemon": target_pokemon,
            "target_use_boss": target_use_boss, "target_can_kill": target_can_kill,
            "target_prize_gain": target_prize_gain, "target_hammer_needed": target_hammer_needed,
            "use_kadabra_finish": use_kadabra_finish,
            "need_dudunsparce_draw": need_dudunsparce_draw,
            "need_retreat_energy": need_retreat_energy,
            "need_fez_draw": need_fez_draw, "need_fez_setup": need_fez_setup,
            "safe_draws": safe_draws, "my_prize": my_prize,
        }

    # ═══════════════ 判定（デッキ固有オーバーライド） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: Powerful Hand が撃てる（場の Alakazam に超エネが付いている）。"""
        for pk in (my_state(obs).active + my_state(obs).bench):
            if pk is not None and pk.id == ALAKAZAM and any(
                    ec.id in PSYCHIC_ENERGY_IDS for ec in pk.energyCards):
                return True
        return False

    def judge_lethal(self, obs):
        """R-07: 現在手札での確定打点でのみ発火（投影打点での早撃ち防止。設計md参照）。
        アクティブのアタッカーが今すぐ撃てる場合のみ。"""
        p = self.p
        if not p or p.get("target_pokemon") is None or not p["target_can_kill"]:
            return None
        target = p["target_pokemon"]
        if p["my_prize"] > p["target_prize_gain"]:
            return None  # 勝ち切りではない
        ms = my_state(obs)
        active = ms.active[0] if ms.active else None
        if active is None:
            return None
        # 現在確定打点で届くか
        if p["use_kadabra_finish"] and active.id == KADABRA:
            current_dmg = 30
            attack_id = ATK_SUPER_PSY_BOLT
        elif active.id == ALAKAZAM and p["active_has_psychic"]:
            current_dmg = (p["hand_size"] - p["target_hammer_needed"]) * 20
            attack_id = ATK_POWERFUL_HAND
        else:
            return None
        if current_dmg < target.hp:
            return None
        if p["target_use_boss"]:
            if BOSS in [c.id for c in (ms.hand or []) if c] and not obs.current.supporterPlayed:
                return {"route": "boss", "target": target, "attack_id": attack_id,
                        "attacker": active, "needs_retreat": False}
            return None
        return {"route": "active", "attack_id": attack_id,
                "attacker": active, "needs_retreat": False}

    def score_yes_no(self, obs, opt):
        # div-5（2026-07-07 divergence 実測）+ R-11: 山札が薄い時は任意ドロー特性
        # （進化時ドロー等の ACTIVATE）を辞退する。上位勢は human=NO を選んでいた
        from cg.api import OptionType as _OT
        # div-7 は棄却（2026-07-08: 「手札14枚以上なら辞退」を試したが ACTIVATE 95%→82% に
        # 悪化して差し戻し。上位勢の NO 18/337 は稀で、拡張条件は過発火する）
        if (obs.select.context == SelectContext.ACTIVATE
                and self.p.get("safe_draws", 999) < 3):
            if opt.type == _OT.NO:
                return 100000, "div-5: decline draw (deck thin)"
            return -1, "div-5: don't activate"
        return super().score_yes_no(obs, opt)

    # ═══════════════ セットアップコンテキスト（参照実装はセットアップでもベンチ展開する） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        p = self.p
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {ABRA: 10, DUNSPARCE: 5, PSYDUCK: 2, SHAYMIN: 1}
            return table.get(cid, 0), "setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid == ABRA:
                cur = p.get("abra_line", 0)
                return (200 if cur == 0 else 100 + (3 - cur) * 10), "setup bench Abra"
            if cid == DUNSPARCE:
                return (150 if p.get("dunsparce_line", 0) == 0 else 50), "setup bench Dunsparce"
            return 0, "setup bench other"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性から

    # ═══════════════ 優先則（両フェーズとも参照実装のスコアラーへ委譲） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    def _score_any(self, obs, opt):
        p = self.p
        state = obs.current
        yi = state.yourIndex
        ctx = obs.select.context

        if opt.type == OptionType.CARD:
            pi = opt.playerIndex if opt.playerIndex is not None else yi
            card = get_card(obs, opt.area, opt.index, pi)
            if card is None:
                return 0, "card none"
            e_cnt = len(getattr(card, "energies", []) or [])

            if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
                if pi == yi:
                    if card.id == ALAKAZAM:
                        score, reason = 100 + e_cnt * 10, "promote Alakazam"
                    elif card.id == KADABRA:
                        score, reason = (90 if p["op_active_hp"] <= 30 else 30), "promote Kadabra"
                    elif card.id == ABRA:
                        score, reason = 10, "promote Abra"
                    elif card.id in DUNSPARCE_LINE:
                        score, reason = 5, "promote Dunsparce line"
                    else:
                        score, reason = 1, "promote other"
                    return self.default_score_promote(obs, opt, score, reason)  # R-08
                # 相手側 = ボス対象（リーサル対象はターン手順が昇格）
                if p["target_use_boss"] and p["target_pokemon"] is not None:
                    if opt.index == p["target_idx"] - 1:
                        return 100, "Boss target (planned)"
                return 0, "opp switch other"

            if ctx == SelectContext.TO_HAND:
                # div-6（2026-07-07 divergence 実測）: サーチはケーシィ進化ライン > ノコッチ系
                score = 200 - p["hand_counts"].get(card.id, 0) * 50
                fc = p["field_counts"]
                # div-9（2026-07-08 divergence 実測・7/7）: 上位勢は Dudunsparce（ドローエンジン）を
                # Kadabra/Alakazam より先に取る（human=Dudunsparce / ours=Kadabra,Alakazam）
                if card.id == DUDUNSPARCE:
                    score += 80 if (fc[DUNSPARCE] >= 1 and fc[DUDUNSPARCE] == 0) else -50
                elif card.id == KADABRA:
                    score += 70 if fc[ABRA] >= 1 else -20
                elif card.id == ALAKAZAM:
                    score += 65 if (fc[KADABRA] >= 1 or fc[ABRA] >= 1) else -20
                elif card.id == ABRA:
                    score += 60 if p["abra_line"] < 3 else -50
                elif card.id == DUNSPARCE:
                    score += 30 if p["dunsparce_line"] < 2 else -50
                elif card.id in PSYCHIC_ENERGY_IDS:
                    score += 30 if not state.energyAttached else -10
                elif card.id == ENRICHING_ENERGY:
                    score += 20
                elif card.id == RARE_CANDY:
                    score += 40 if fc[ABRA] >= 1 else -10
                return score, "to hand"

            if ctx == SelectContext.ATTACH_FROM:
                if hasattr(card, "energyCards"):
                    if p["need_retreat_energy"] and opt.area == AreaType.ACTIVE:
                        return 150, "attach for retreat"
                    if len(card.energyCards) >= 1:
                        return -1, "no 2nd energy (規律)"
                    if card.id in ABRA_LINE:
                        score = 100 + {ALAKAZAM: 20, KADABRA: 10}.get(card.id, 0)
                        if opt.area == AreaType.ACTIVE:
                            score += 5
                        return score, "attach Abra line"
                    if card.id in DUNSPARCE_LINE:
                        return 50, "attach Dunsparce line"
                    return 10, "attach other"
                return 0, "attach from"

            if ctx == SelectContext.TO_BENCH:
                if card.id == ABRA:
                    return 100, "bench Abra"
                if card.id == DUNSPARCE:
                    return 80, "bench Dunsparce"
                if card.id == PSYDUCK:
                    return (60, "bench Psyduck (Duskull gate)") if p["op_has_duskull"] else (-1, "gate: no Duskull")
                if card.id == SHAYMIN:
                    return (40, "bench Shaymin (water gate)") if p["op_has_water_threat"] else (-1, "gate: no water threat")
                return 0, "bench other"

            if ctx == SelectContext.TO_DECK:
                if card.id in ABRA_LINE:
                    return 100, "to deck Abra line"
                if card.id in DUNSPARCE_LINE:
                    return 50, "to deck Dunsparce line"
                return 10, "to deck other"

            return 0, "card other ctx"

        if opt.type == OptionType.PLAY:
            card = get_card(obs, AreaType.HAND, opt.index, yi)
            if card is None:
                return 0, "play none"
            data = CARD_DB[card.id]
            fc = p["field_counts"]
            hc = p["hand_counts"]

            if data.cardType == CardType.POKEMON:
                score, reason = 20000, "play pokemon"
                is_early = state.turn <= 2
                if card.id == ABRA:
                    if is_early:
                        score += 500
                    elif p["abra_line"] < 3:
                        score += 200
                    elif p["bench_free"] <= 1:
                        return -1, "R: bench full"
                    else:
                        score += 50
                elif card.id == DUNSPARCE:
                    if p["dunsparce_line"] < 1:
                        score += 400 if is_early else 100
                    elif p["dunsparce_line"] < 2:
                        score += 50
                    else:
                        return -1, "enough Dunsparce"
                elif card.id == FEZANDIPITI_EX:
                    if p["need_fez_draw"] or p["need_fez_setup"]:
                        score += 80 if not is_early else 30
                    else:
                        return -1, "R-12: save Fezandipiti"
                elif card.id == GENESECT:
                    if not self._op_used_ace_spec and (hc[LUCKY_HELMET] > 0 or hc[POKE_PAD] > 0):
                        score += 100
                    else:
                        return -1, "gate: ACE SPEC used"
                elif card.id == PSYDUCK:
                    if p["op_has_duskull"]:
                        score += 300
                    else:
                        return -1, "gate: no Duskull"
                elif card.id == SHAYMIN:
                    if p["op_has_water_threat"]:
                        score += 300
                    else:
                        return -1, "gate: no water threat"
                if p["bench_free"] <= 1 and score > 0:
                    score -= 5000   # ベンチ1枠空け
                return score, reason

            score, reason = 10000, "play trainer"
            sd = p["safe_draws"]
            if card.id == POFFIN:
                if sd < 2:
                    return -1, "R-11: deck thin (Poffin)"
                if state.turn <= 2:
                    return (18000 if (p["abra_line"] < 3 or p["dunsparce_line"] < 1) else 8000), "Poffin"
                if p["abra_line"] < 3 or p["dunsparce_line"] < 2:
                    return 15000, "Poffin: rebuild"
                if p["target_can_kill"]:
                    return 8000, "Poffin: thin deck for kill"
                return -1, "Poffin: not needed"
            if card.id == POKE_PAD:
                if sd < 1:
                    return -1, "R-11: deck thin (Pad)"
                if state.turn <= 2:
                    return 17000, "Poke Pad early"
                return (14000 if p["abra_line"] < 3 else 12000), "Poke Pad"
            if card.id == RARE_CANDY:
                if fc[ABRA] >= 1 and hc[ALAKAZAM] >= 1 and sd >= 3:
                    return 16000, "Rare Candy -> Alakazam"
                return -1, "Rare Candy: no line / R-11"
            if card.id == NIGHT_STRETCHER:
                dc = p["discard_counts"]
                dis_abra = dc[ABRA] + dc[KADABRA] + dc[ALAKAZAM]
                if dis_abra >= 1:
                    return 13000, "Night Stretcher: recover line"
                if dc[PSY_ENERGY] + dc[TELEPATH_ENERGY] >= 1:
                    return 11000, "Night Stretcher: recover energy"
                return -1, "Night Stretcher: nothing"
            if card.id == SACRED_ASH:
                dc = p["discard_counts"]
                dis_abra = dc[ABRA] + dc[KADABRA] + dc[ALAKAZAM]
                if dis_abra >= 2:
                    return 13500, "Sacred Ash"
                if dis_abra >= 1:
                    return 11000, "Sacred Ash (1)"
                return -1, "Sacred Ash: nothing"
            if card.id == ENHANCED_HAMMER:
                if p["target_hammer_needed"] > 0:
                    return 6500, "Hammer: clear target defense"
                if any(_special_defense_count(pk) > 0 for pk in p["op_all"]):
                    return 5000, "Hammer: opportunistic"
                return -1, "Hammer: no target"
            if card.id == LUCKY_HELMET:
                return 7000, "Lucky Helmet (via ATTACH)"
            if card.id == BOSS:
                if p["target_use_boss"] and p["target_can_kill"]:
                    return 3200, "Boss: planned pull"
                return -1, "save Boss"
            if card.id == HILDA:
                return (3000, "Hilda") if sd >= 2 else (-1, "R-11: deck thin (Hilda)")
            if card.id == DAWN:
                return (3100, "Dawn") if sd >= 3 else (-1, "R-11: deck thin (Dawn)")
            if card.id == BATTLE_CAGE:
                if p["op_has_dragapult"]:
                    return 19000, "Battle Cage: Dragapult gate"
                if p["stadium_id"] != 0:
                    return 7000, "Battle Cage: replace stadium"
                return -1, "save Battle Cage"
            return score, reason

        if opt.type == OptionType.ATTACH:
            card = get_card(obs, AreaType.HAND, opt.index, yi)
            pokemon = get_card(obs, opt.inPlayArea, opt.inPlayIndex, yi)
            if card is None or pokemon is None:
                return 0, "attach none"
            if card.id == LUCKY_HELMET:
                score = 7000
                if pokemon.id == GENESECT and not self._op_used_ace_spec:
                    score += 300
                elif opt.inPlayArea == AreaType.ACTIVE:
                    score += 200
                else:
                    score += 50
                return score, "Lucky Helmet"
            if card.id in PSYCHIC_ENERGY_IDS:
                if p["need_retreat_energy"] and opt.inPlayArea == AreaType.ACTIVE:
                    return 9500, "attach: retreat energy"
                if len(pokemon.energyCards) >= 1:
                    return -1, "no 2nd energy (規律)"
                if pokemon.id in ABRA_LINE:
                    score = 8000 + {ALAKAZAM: 30, KADABRA: 20, ABRA: 10}.get(pokemon.id, 0)
                    if opt.inPlayArea == AreaType.ACTIVE:
                        score += 5
                    if card.id == TELEPATH_ENERGY and p["safe_draws"] < 2:
                        return -1, "R-11: deck thin (Telepath)"
                    return score, "attach psychic"
                return -1, "attach: wrong target"
            if card.id == ENRICHING_ENERGY:
                if p["need_retreat_energy"] and opt.inPlayArea == AreaType.ACTIVE:
                    return 9500, "attach: retreat energy"
                if len(pokemon.energyCards) >= 1:
                    return -1, "no 2nd energy (規律)"
                if pokemon.id in DUNSPARCE_LINE:
                    if p["safe_draws"] < 4:
                        return -1, "R-11: deck thin (Enriching)"
                    return 8500 + (10 if pokemon.id == DUDUNSPARCE else 0), "attach Enriching"
                return -1, "Enriching: wrong target"
            return 0, "attach other"

        if opt.type == OptionType.EVOLVE:
            card = get_card(obs, AreaType.HAND, opt.index, yi)
            pokemon = get_card(obs, opt.inPlayArea, opt.inPlayIndex, yi)
            if card is None or pokemon is None:
                return 0, "evolve none"
            # div-8（2026-07-08 divergence 実測・7/7）: このデッキの進化は進化時ドロー
            # （Kadabra+2/Alakazam+3/Dudunsparce系）そのものがドローエンジン。上位勢は
            # ポケパッド/アメより先に進化を切る（human=EVOLVE / ours=PLAY Pad,Candy が多発）
            score = 17500
            sd = p["safe_draws"]
            hc = p["hand_counts"]
            if card.id == ALAKAZAM:
                if sd < 3:
                    return -1, "R-11: deck thin (Alakazam draw 3)"
                score += 200 if opt.inPlayArea == AreaType.ACTIVE else 50
                score += len(pokemon.energies) * 10
                return score, "evolve Alakazam"
            if card.id == KADABRA:
                if sd < 2:
                    return -1, "R-11: deck thin (Kadabra draw 2)"
                score += 100
                if len(pokemon.energies) == 0:
                    score += 50   # エネ無し Abra から進化（エネ付きは Rare Candy 用に温存）
                else:
                    score -= 20
                    if hc[RARE_CANDY] > 0 and hc[ALAKAZAM] > 0:
                        score -= 100
                return score, "evolve Kadabra"
            if card.id == DUDUNSPARCE:
                if sd < 2:
                    return -1, "R-11: deck thin (Dudunsparce)"
                return score + 80, "evolve Dudunsparce"
            return score, "evolve other"

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            if card is None:
                return 0, "ability none"
            if card.id == DUDUNSPARCE:
                if p["need_dudunsparce_draw"]:
                    if p["safe_draws"] >= 3:
                        return 30000, "R-12: Dudunsparce draw (needed for KO)"
                    return -1, "R-11: deck thin"
                # div-4（2026-07-07 divergence 実測）: 上位勢は攻撃前の手札増強にも使う
                # （3ドロー=+60打点）。アイテム類の後・攻撃の前に発火する帯（2000）
                if (p["safe_draws"] >= 3 and p["active_id"] == ALAKAZAM
                        and p["active_has_psychic"]):
                    return 2000, "div-4: Run Away Draw before Powerful Hand"
                return -1, "R-12: save Dudunsparce"
            if card.id == FEZANDIPITI_EX:
                if (p["need_fez_draw"] or p["need_fez_setup"]) and p["safe_draws"] >= 3:
                    return 29000, "R-12: Flip the Script (needed)"
                return -1, "R-12: save Fezandipiti"
            if card.id == BATTLE_CAGE:
                return 1, "Battle Cage ability"
            return 28000, "generic ability"

        if opt.type == OptionType.RETREAT:
            fc = p["field_counts"]
            aid = p["active_id"]
            if aid == ALAKAZAM and p["active_has_psychic"]:
                return -1, "don't retreat ready Alakazam"
            if p["use_kadabra_finish"] and aid != KADABRA and fc[KADABRA] >= 1:
                return 2500, "retreat for Kadabra finish"
            if aid in (ABRA, DUNSPARCE, DUDUNSPARCE, PSYDUCK, SHAYMIN, GENESECT):
                if fc[ALAKAZAM] >= 1 or fc[KADABRA] >= 1:
                    return 2000, "retreat support pokemon"
                return -1, "no attacker to promote"
            return -1, "avoid retreat"

        if opt.type == OptionType.ATTACK:
            # R-04: ワザは最後（スコア帯最下位）。ワザ間の選好のみ表現
            score = 1000
            if opt.attackId == ATK_POWERFUL_HAND:
                score += 500
            elif opt.attackId == ATK_SUPER_PSY_BOLT:
                score += 600 if p["op_active_hp"] <= 30 else 100
            elif opt.attackId == ATK_TELEPORTATION:
                score += 50
            return score, "E: attack"

        if opt.type == OptionType.END:
            return 0, "end"
        return 0, "fallback"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(AlakazamPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
