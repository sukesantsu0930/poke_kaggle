"""フーディン（Alakazam / Powerful Hand）ルールベースエージェント — BasePolicy 版

土台: Kaggle 公開 Notebook "Rule-based, not psychic: Alakazam"（sue124、最高LB5位、Apache-2.0系譜）。
その方策（手札純増モデル・3段ターゲット選択・Enhanced Hammer 会計・safe_draws 山札ガード）を
共有基盤 BasePolicy のフックに移植した。

設計文書: docs/planning/デッキ設計_フーディン.md（S-0/可変打点モデル/未決事項）
ルールタグ: R-07(リーサル)/R-08(負け筋)/R-11(山札切れ)/R-12(特性温存)/R-21・R-22(暫定)/
R-27(進化即死ガード: バトル場のケーシィ→ユンゲラー進化を返しの80点圏内で禁止)

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
    attack_base_damage,
    attack_cost,
    card_attack_ids,
    damage_on,
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
# ── 収束リスト（2026-07-10 メタ。LB2位 Majkel1337 / 4位 Yushin Ito / bono が同一リスト）──
# alakazam_top_0710.csv: IN Xerosic×3 / Nighttime Mine×3 / Alakazam+1 / Boss+1 / Lana's Aid
#                        OUT Battle Cage×4 / Lucky Helmet×3 / Genesect / Psyduck
# 旧カードのルールは温存（旧リストでも動く）。新カードは下記ルールが無いと
# 汎用 trainer 帯 10000 で乱発されるため、リスト採用にはルール追加が必須。
XEROSIC = 1197          # サポート: 相手の手札を3枚になるまで捨てさせる
NIGHTTIME_MINE = 1266   # スタジアム: 場のテラスタルの技コスト+1（フーディン側は非テラスタル）
LANAS_AID = 1184        # サポート: トラッシュから非ルールボックスPKM+基本エネ計3枚を手札へ

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

GRAVITY_GEMSTONE = 1166   # シャンデラの拘束どうぐ: バトル場のにげるコスト+1（両者）

# ── 対面別ルールパッケージのトグル（P-12 の A/B 用。2026-07-15 敗因診断起点） ──
# 診断（30戦/対面、scratchpad/diag_alakazam.py）:
#   chandelure 4W-26L: 全敗が自山切れ（手札14枚を抱えたまま・被KOゼロ）= ロック+ミル
#   crustle_wall 13W-17L: 山切れ12敗 = ジャンボ回復80+ゼロシキで打点レースが止まり長期戦
#   marnie 8W-22L: Alakazam被KO57回 + 餌ベンチ（ノコッチ/ケーシィ）へのばら撒きで先に6枚
ALA_LO = os.environ.get("ALA_LO", "1") != "0"          # 対LO 山札規律 + 拘束脱出
ALA_WALL = os.environ.get("ALA_WALL", "1") != "0"      # 対イワパレス壁 ハンマー/ゼロシキ
ALA_MARNIE = os.environ.get("ALA_MARNIE", "1") != "0"  # 対マリィ 餌ベンチ禁止
# div-21（Fez 素出しを被KO直後に限定）: L3 は +1.0pt 改善するが L2 制圧度が
# 44.0→40.2% と悪化（プール相手ではドローエンジンの遅着地が純損）→ 既定 OFF
ALA_DIV21 = os.environ.get("ALA_DIV21", "0") != "0"


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
        self._prev_opp_pz = 6            # div-21: 被KO検知（Flip the Script の発動条件）
        self._ko_recent = False
        self.p = {}

    def reset_game(self):
        super().reset_game()
        self._pre_turn = 0
        self._used_dudunsparce = False
        self._used_fezandipiti = False
        self._op_used_ace_spec = False
        self._prev_opp_pz = 6
        self._ko_recent = False
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
            # div-21: 相手サイドの減少 = 直前に我が方の誰かが KO された
            # （Flip the Script「前の相手番に被KO」の近似トリガー。ガルーラ実装と同型）
            opp_pz_now = len(os_.prize)
            self._ko_recent = opp_pz_now < self._prev_opp_pz
            self._prev_opp_pz = opp_pz_now

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
        op_has_tera = any(
            getattr(CARD_DB.get(p.id), "tera", False) for p in op_all)

        # R-27 の入力: 返しの相手番にユンゲラー（HP80）へ飛び得る最大打点。
        # 相手の場の各ポケモンについて「装着エネ枚数 ≥ 技コスト−1」なら
        # 次の番（手張り1枚込み）にその技が撃てるとみなす（色は見ない簡易判定）。
        # 弱点×2 は対ユンゲラー（超）に限り加味。可変打点技は基礎値のみ（保守的）。
        kadabra_data = CARD_DB.get(KADABRA)
        kadabra_weak = getattr(kadabra_data, "weakness", None)
        kadabra_weak = getattr(kadabra_weak, "value", kadabra_weak)
        op_threat_vs_kadabra = 0
        for pkmn in op_all:
            e_have = len(getattr(pkmn, "energyCards", None) or [])
            pd = CARD_DB.get(pkmn.id)
            p_type = getattr(pd, "energyType", None) if pd else None
            p_type = getattr(p_type, "value", p_type)
            for aid in card_attack_ids(pkmn.id):
                cost = attack_cost(aid)
                if cost is None:
                    continue
                if e_have >= len(cost) - 1:
                    dmg = attack_base_damage(aid)
                    if kadabra_weak is not None and p_type == kadabra_weak:
                        dmg *= 2
                    if dmg > op_threat_vs_kadabra:
                        op_threat_vs_kadabra = dmg

        # Lana's Aid の回収数（トラッシュの非ルールボックスPKM + 基本エネ、上限3）
        lana_recoverable = 0
        for card in (ms.discard or []):
            if card is None:
                continue
            data = CARD_DB.get(card.id)
            if data is None:
                continue
            if data.cardType == CardType.POKEMON and not data.ex and not data.megaEx:
                lana_recoverable += 1
            elif data.cardType == CardType.BASIC_ENERGY:
                lana_recoverable += 1
        lana_recoverable = min(3, lana_recoverable)

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
            if hand_counts[LANAS_AID] > 0 and lana_recoverable > 0:
                supporter_options.append(lana_recoverable - 1)   # 手札純増 = 回収数 − 打った1枚
            if hand_counts[XEROSIC] > 0:
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
        # ALA_LO 起点の一般修正（2026-07-15）: 重力宝石（バトル場のにげ+1・両者）を
        # コストに織り込む。従来は素の retreatCost で「もう払える」と誤判定し、
        # 2枚目のエネ付与（9500 経路）が発火せず拘束されたままミルされていた。
        gravity = any(
            t is not None and t.id == GRAVITY_GEMSTONE
            for side in (ms, os_) for pk in side.active if pk is not None
            for t in (getattr(pk, "tools", None) or []))
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
                    rc = CARD_DB[active.id].retreatCost + (1 if gravity else 0)
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

        # div-18（2026-07-12 実測）: 「現在手札の確定打点」で今すぐKOが取れるか
        # （勝ち切りでない中間KOを含む。R-07 リーサルの非最終版）。上位勢は KO が確定した
        # 時点で価値プレイ（Pad/Poffin/進化/特性）を切り上げて攻撃する
        # （human=ATTACK / ours=Pad,Poffin,evolve,div-11 が両日 50〜90件）。
        # ボス経路はボスのコスト（手札−1）込みで判定する。
        kill_now = False
        if target_pokemon is not None and target_can_kill and state.turn >= 2:
            if use_kadabra_finish:
                kill_now = active_id == KADABRA
            elif active_id == ALAKAZAM and active_has_psychic:
                cost = target_hammer_needed + (1 if target_use_boss else 0)
                boss_ok = (not target_use_boss
                           or (hand_counts[BOSS] > 0 and not state.supporterPlayed))
                kill_now = boss_ok and (hand_size - cost) * 20 >= target_pokemon.hp

        # R-11: 山札切れガード（勝ち切りターンは解除）
        can_win = target_can_kill and my_prize <= target_prize_gain
        safe_draws = ms.deckCount - my_prize - 1 if not can_win else 999

        # 対面別パッケージの発火判定（R-20。update_belief より前なのでここで直接検出）
        matchup = self.detect_matchup(obs)
        is_lo = ALA_LO and matchup in mt.LO_ARCHETYPES
        is_wall = ALA_WALL and matchup == "crustle"
        is_marnie = ALA_MARNIE and matchup == "marnie"
        # せいなるはい用: トラッシュのポケモン総数（対LOでは山の回復装置として積極使用）
        dis_pokemon = sum(
            n for cid, n in discard_counts.items()
            if (d := CARD_DB.get(cid)) is not None and d.cardType == CardType.POKEMON)

        return {
            "matchup": matchup, "is_lo": is_lo, "is_wall": is_wall,
            "is_marnie": is_marnie, "dis_pokemon": dis_pokemon,
            "ko_recent": self._ko_recent,
            "field_counts": field_counts, "hand_counts": hand_counts,
            "discard_counts": discard_counts, "my_field": my_field,
            "abra_line": abra_line_on_field, "dunsparce_line": dunsparce_line_on_field,
            "op_all": op_all, "op_has_duskull": op_has_duskull,
            "op_has_water_threat": op_has_water_threat, "op_has_dragapult": op_has_dragapult,
            "op_has_tera": op_has_tera, "op_hand_count": os_.handCount,
            "op_threat_vs_kadabra": op_threat_vs_kadabra,
            "lana_recoverable": lana_recoverable,
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
            "kill_now": kill_now,
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
        # ALA_LO: 対LOでは山札=寿命。手札が既に太い（打点200+相当）か山が細り始めたら
        # 任意ドロー（進化時ドロー等）を辞退する（診断: 手札14枚を抱えたまま山切れ負け）
        if (obs.select.context == SelectContext.ACTIVATE and self.p.get("is_lo")
                and (self.p.get("hand_size", 0) >= 10
                     or self.p.get("safe_draws", 999) < 10)):
            if opt.type == _OT.NO:
                return 100000, "ALA-LO: decline draw (deck is the clock)"
            return -1, "ALA-LO: don't activate"
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
                    # div-16（2026-07-11 実測。07-08/07-09 両日同方向）: **SWITCH（自発
                    # 交代）限定**で、攻撃準備のない駒でなくノコッチを壁として前に出す
                    # （human=Dunsparce/ours=Kadabra,Abra 等。SWITCH 66%→75% / 51%→69%）。
                    # TO_ACTIVE（きぜつ後の強制前出し）へ同じ表を適用したら 81%→45% /
                    # 82%→43% と大幅悪化（上位勢は次のアタッカーを出す）→ 従来表を維持。
                    if ctx == SelectContext.SWITCH:
                        has_psy = any(ec.id in PSYCHIC_ENERGY_IDS
                                      for ec in (getattr(card, "energyCards", None) or []))
                        if card.id == ALAKAZAM and has_psy:
                            score, reason = 100 + e_cnt * 10, "promote Alakazam"
                        elif card.id == KADABRA and p["op_active_hp"] <= 30:
                            score, reason = 90, "promote Kadabra (finish)"
                        elif card.id in DUNSPARCE_LINE:
                            score, reason = ((40 if card.id == DUNSPARCE else 35),
                                             "div-16: promote wall Dunsparce")
                        elif card.id == ABRA:
                            score, reason = 25, "div-16: promote Abra (cheap)"
                        elif card.id == ALAKAZAM:
                            score, reason = 20, "div-16: unready Alakazam"
                        elif card.id == KADABRA:
                            score, reason = 15, "div-16: keep Kadabra safe"
                        else:
                            score, reason = 1, "promote other"
                        return self.default_score_promote(obs, opt, score, reason)  # R-08
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
                    # div-23【暫定】（2026-07-15 対Yushin divergence、4件）: サーチのエネ指名は
                    # エンリッチング（付与時+3ドロー）をテレパスより先に取る
                    score += 35
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
                # div-22【暫定】（2026-07-15 対Yushin divergence、5件）: ノコッチライン未着手なら
                # ドローエンジン（ノコッチ→ノココッチ）をケーシィより先に確保（div-9 と同方向）
                if card.id == DUNSPARCE and p["dunsparce_line"] == 0:
                    return 110, "div-22: bench Dunsparce first (draw engine)"
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
                # div-14【棄却】（2026-07-11）: (a) DISCARD の保護+一律捨て可採点と
                # (b) TO_DECK の同名グループ整列（base - グループ先頭index）を試したが、
                # TO_DECK 52%→44%（07-08）/ 45%→38%（07-09）、DISCARD 4%→5% / 5%→3%
                # と両日悪化（複数選択の完全一致は順序も要求され、上位勢の順序は
                # グループ順仮説より雑多）。旧実装へ差し戻し。
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
                # div-17【棄却】（2026-07-12）: 「交戦期は基本ポケモンを一律温存（1200帯）」を
                # 試したが両日悪化（07-10 58.8→58.2% / 07-11 61.6→60.5%）。φ 実測では上位勢も
                # 交戦期の31%は基本を置いており（n=553）、二値の phase ゲートでは表現できない
                # （ターン内順序の問題）→ 差し戻し。
                # div-18 の付帯則: 確定KOターンに限り基本ポケモンを温存（手札−1 = 打点−20。
                # φ 実測: kill 立ち時の展開率 30% vs 非kill 64%）。攻撃 17000 より下・END より上
                if (p["kill_now"] and card.id in (ABRA, DUNSPARCE)
                        and state.turn > 2):
                    return 1200, "div-18: hold basics on KO turn"
                score, reason = 20000, "play pokemon"
                is_early = state.turn <= 2
                if card.id == ABRA:
                    if is_early:
                        score += 500
                    elif p["abra_line"] < 3:
                        score += 200
                    elif p["bench_free"] <= 1:
                        return -1, "R: bench full"
                    elif p["is_marnie"]:
                        # ALA_MARNIE（2026-07-15 診断起点）: マリィ側はボス不採用で、
                        # ベンチの余剰たねはシャドーバレット30+マシマシラの無料サイド。
                        # ライン完成後の余りは手札温存
                        return -1, "ALA-MARNIE: no fodder bench (free prizes)"
                    else:
                        score += 50
                elif card.id == DUNSPARCE:
                    if p["dunsparce_line"] < 1:
                        score += 400 if is_early else 100
                    elif p["dunsparce_line"] < 2:
                        score += 50
                    elif p["is_marnie"]:
                        return -1, "ALA-MARNIE: no fodder bench (free prizes)"
                    else:
                        # div-13（2026-07-11 実測。07-08/07-09 両日同方向）: 上位勢は
                        # ライン完成後も余りノコッチを壁/サイド緩衝としてベンチに出す
                        # （human=PLAY/Dunsparce を我々がブロック→END が 07-08 58件+）。
                        # 帯 800 = 攻撃(1500)より下・END(0)より上（human=ATTACK/ours=PLAY
                        # の逆方向 38件があるため攻撃は追い越さない）。fodder で最終枠は
                        # 埋めない（ベンチ1枠空けの規律はここでは -1 マスクで表現）。
                        if p["bench_free"] <= 1:
                            return -1, "div-13: fodder Dunsparce (bench full)"
                        return 800, "div-13: fodder Dunsparce"
                elif card.id == FEZANDIPITI_EX:
                    # div-21b（2026-07-15、ユーザー指摘で v1 を修正）: 「発動不能ターンは温存」
                    # だけでなく「発動可能ターン（被KO直後）には KO 計画と無関係に広く出して
                    # 3ドローを取る」が Yushin の実際の型。v1（温存のみ・展開は need_* 限定）は
                    # 温存したまま一度も出さない試合を作っていた（160戦A/B ON 37.6 vs OFF 39.4）
                    if ALA_DIV21:
                        if not p["ko_recent"]:
                            return -1, "div-21b: hold Fez (Flip the Script not live)"
                        return 20080, "div-21b: Fez on live turn (draw 3)"
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
                # ALA_LO: サーチ2枚 = 山−2。対LOは初動のライン形成分だけに絞る
                if p["is_lo"] and state.turn > 2 and p["abra_line"] >= 2:
                    return -1, "ALA-LO: hold Poffin (deck is the clock)"
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
                # ALA_LO: ライン健在なら山を消費しない
                if p["is_lo"] and state.turn > 2 and p["abra_line"] >= 3:
                    return -1, "ALA-LO: hold Pad (deck is the clock)"
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
                # ALA_LO: 対LOでは山+5 の回復装置として積極使用（ライン以外のポケモンでも戻す）
                if p["is_lo"] and p["dis_pokemon"] >= 2:
                    return 13500, "ALA-LO: Sacred Ash (deck recovery)"
                if dis_abra >= 2:
                    return 13500, "Sacred Ash"
                if dis_abra >= 1:
                    return 11000, "Sacred Ash (1)"
                return -1, "Sacred Ash: nothing"
            if card.id == ENHANCED_HAMMER:
                # ALA_WALL（2026-07-15 診断起点）: 壁の3エネはジャンボアイス（エネ3枚以上で
                # 回復80）と Superb Scissors（{G}コスト）の生命線。相手アクティブのエネを
                # 3→2 に割ればどちらも止まる → アイテム帯上位で即切る
                if p["is_wall"]:
                    act = opp_state(obs).active
                    act = act[0] if act else None
                    if (act is not None and len(getattr(act, "energyCards", []) or []) >= 3
                            and any(getattr(CARD_DB.get(ec.id), "cardType", None)
                                    == CardType.SPECIAL_ENERGY for ec in act.energyCards)):
                        return 12500, "ALA-WALL: Hammer breaks Jumbo/Scissors (3rd energy)"
                # div-20（2026-07-12 実測。narrow比 +0.1/+0.1 の微プラス + human=Hammer/
                # ours=no target が両日多数）: Mist/Rock 以外の特殊エネもテンポ剥がしで割る
                if p["target_hammer_needed"] > 0:
                    return 6500, "Hammer: clear target defense"
                if any(any(getattr(CARD_DB.get(ec.id), "cardType", None)
                           == CardType.SPECIAL_ENERGY
                           for ec in pk.energyCards)
                       for pk in p["op_all"]):
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
            # ── 収束リスト（alakazam_top_0710）の新カード。帯は divergence 実測で調整済み ──
            if card.id == XEROSIC:
                # ALA_WALL: 壁側の手札はジャンボアイス/リーリエ/ヒルダの貯蔵庫。
                # 対イワパレスでは Hilda/Dawn より優先して毎回切る（回復の弾を絞る）
                if (p["is_wall"] and p["op_hand_count"] >= 5
                        and not (p["target_use_boss"] and p["target_can_kill"])):
                    return 3150, "ALA-WALL: Xerosic strips Jumbo stock"
                # 相手の手札を3枚へ。相手の手札が肥えている時だけ（順位は Hilda/Dawn の下 =
                # 自分のドローが基本優先）。18500 への大幅昇格・Dawn 直上 3120 とも
                # 両日悪化で棄却（2026-07-12）。ボス経路の確定KO時はサポート枠をボスに譲る
                if (p["op_hand_count"] >= 5
                        and not (p["target_use_boss"] and p["target_can_kill"])):
                    return 2900, "Xerosic: strip big hand"
                return -1, "save Xerosic"
            if card.id == LANAS_AID:
                # 回収先が手札に入る = 打点+20/枚 かつライン復旧。回収3枚なら Dawn より上
                rec = p["lana_recoverable"]
                if rec >= 3:
                    return 3150, "Lana: recover 3 (+hand)"
                if rec == 2:
                    return 3050, "Lana: recover 2"
                return -1, "save Lana"
            if card.id == NIGHTTIME_MINE:
                # テラスタル課税（フーディン側は非テラスタルでノーコスト）。Battle Cage の
                # ゲート（19000/7000）と同型 + スタジアム不在なら無条件で置く
                # （div 実測: human=PLAY/Mine を我々が save でブロック。枠の先取りは実害なし）
                if p["stadium_id"] == NIGHTTIME_MINE:
                    return -1, "Mine already up"
                if p["op_has_tera"]:
                    return 19000, "Nighttime Mine: tera tax"
                if p["stadium_id"] != 0:
                    return 7000, "Nighttime Mine: replace stadium"
                return -1, "save Nighttime Mine"
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
            # div-19【棄却】（2026-07-12）: 進化の内部順序をドロー量順（Alakazam>Dudunsparce>
            # Candy>Kadabra）へ寄せたが両日悪化（07-10 59.4→59.2 / 07-11 61.5→60.9）。
            # クラスタは両方向あり、順序は文脈依存（φ 未特定）→ 従来の帯へ差し戻し
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
                # R-27（2026-07-13、リプレイ 85692247 起点）: 進化即死ガード【ハード】。
                # ユンゲラーは HP80（ダメカンは進化後も持ち越し）。返しの相手番に
                # 80点以上が飛ぶ盤面では**バトル場**のケーシィへは進化しない
                # （ベンチのケーシィの進化オプションは通常帯のまま = そちらが優先される。
                #  ベンチに居なければ手札に温存し、次のケーシィに使う）。
                # 例外: use_kadabra_finish（相手アクティブ HP≤30 を 30 で取り切る）は
                # 前で進化してサイドを取る方が得なので通す。
                if (opt.inPlayArea == AreaType.ACTIVE
                        and not p["use_kadabra_finish"]
                        and p["op_threat_vs_kadabra"]
                            >= CARD_DB[KADABRA].hp - damage_on(pokemon)):
                    return -1, "R-27: active Kadabra dies next turn (evolve bench Abra)"
                score += 100
                if len(pokemon.energies) == 0:
                    score += 50   # エネ無し Abra から進化（エネ付きは Rare Candy 用に温存）
                else:
                    score -= 20
                    if hc[RARE_CANDY] > 0 and hc[ALAKAZAM] > 0:
                        score -= 100
                return score, "evolve Kadabra"
            if card.id == DUDUNSPARCE:
                # div-12（2026-07-11 実測。07-08/07-09 両日同方向）: sd<2 ガードを撤去。
                # 上位勢は山薄でも Dudunsparce へ進化する（我々のブロック 07-08 186件 /
                # 07-09 202件、うち sd<2 が 180/199）。進化時ドローは任意（ACTIVATE）で
                # div-5 が山薄時の辞退を担保するため、進化自体に山札切れリスクはない。
                return score + 80, "evolve Dudunsparce"
            return score, "evolve other"

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            if card is None:
                return 0, "ability none"
            if card.id == DUDUNSPARCE:
                if p["need_dudunsparce_draw"] and p["safe_draws"] >= 3:
                    return 30000, "R-12: Dudunsparce draw (needed for KO)"
                # div-11（2026-07-11 実測。調整日 07-08/07-09 両日同方向）: 上位勢は
                # Run Away Draw を攻撃ターン限定でなく・アイテムより先に広く使う
                # （human=ABILITY/Dudunsparce を我々がブロック 07-08 249件 / 07-09 267件。
                #  山薄 sd<2 でもアタッカー準備済みなら攻撃前に使う = 07-09 158件）。
                # 旧 div-4（帯2000・Alakazam アクティブ+sd>=3 限定）はこれに統合。
                # 帯 16500 = Rare Candy(16000) より上・進化(17500+) より下。
                ready = (p["active_id"] == ALAKAZAM and p["active_has_psychic"])
                # ALA_LO: 対LOの広帯ドローは自傷（山3枚/回）。手札が細く山に余裕がある時だけ
                if p["is_lo"] and (p["hand_size"] >= 10 or p["safe_draws"] < 10):
                    return -1, "ALA-LO: save Run Away Draw (deck is the clock)"
                if p["safe_draws"] >= 3 or ready:
                    return 16500, "div-11: Run Away Draw broad (pre-items)"
                return -1, "R-11/R-12: save Dudunsparce (deck thin)"
            if card.id == FEZANDIPITI_EX:
                if (p["need_fez_draw"] or p["need_fez_setup"]) and p["safe_draws"] >= 3:
                    return 29000, "R-12: Flip the Script (needed)"
                # ALA_WALL: 壁側ゼロシキ（手札3枚化=打点60）を食らった後の再建。
                # 手札×20 の打点をジャンボ回復80より上へ戻すのが最優先
                if p["is_wall"] and p["hand_size"] <= 6 and p["safe_draws"] >= 3:
                    return 29000, "ALA-WALL: Flip the Script (rebuild after Xerosic)"
                # div-21b: 特性が提示されている = 発動条件成立。Yushin は KO 計画と無関係に
                # 広く発動する（+3ドロー = 打点+60）。山札ガードのみ（div-11 と同じ思想）
                if ALA_DIV21 and p["safe_draws"] >= 3:
                    return 16600, "div-21b: Flip the Script broad"
                return -1, "R-12: save Fezandipiti"
            if card.id == BATTLE_CAGE:
                return 1, "Battle Cage ability"
            # div-15（2026-07-11 実測。07-08/07-09 両日）: 相手スタジアム
            # （Spikemuth Gym 等）の特性を汎用 28000 で最優先発動していた
            # （ours=ABILITY/Spikemuth vs human=EVOLVE/ATTACK 等が多数）。
            # 上位勢が選ぶ場面は観測されず → 自発的には使わない。
            _cd = CARD_DB.get(card.id)
            if _cd is not None and _cd.cardType == CardType.STADIUM:
                return -1, "div-15: skip stadium ability"
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
            # div-18: 確定KOが立っているならアイテム/ポケモン展開を切り上げて攻撃する
            # （中間KO。勝ち切りは R-07 が LETHAL_BAND へ昇格するので別枠）。
            # 帯 17000 = 進化 17500+ より下（ドロー系はKOターンでも先に済ませる。
            # 手札は持ち越すので損しない）・div-11 16500 / Poffin再建 15000 / Pad 12000 より上
            if p["kill_now"] and not p["target_use_boss"]:
                if opt.attackId == (ATK_SUPER_PSY_BOLT if p["use_kadabra_finish"]
                                    else ATK_POWERFUL_HAND):
                    return 17000, "div-18: take the KO now"
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
