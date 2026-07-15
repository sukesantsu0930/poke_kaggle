"""メガガルーラex（Mega Kangaskhan ex カラーレス・ツールボックス）ルールベース — フルスクラッチ

7/6メタの新興上位アーキタイプ（レート1000+帯シェア 4.6%→10%、勝率56.8%）。
設計文書: docs/planning/デッキ設計_ガルーラ.md（S-x/E-x/未決事項）

コンセプト:
  ガルーラをバトル場に置いて Run Errand 2ドロー/ターン、ベンチのオーガポンで
  Teal Dance（{G}加速+1ドロー）。手張り+クリスピン+エネつけかえで色不問3エネを集め、
  Rapid-Fire Combo 200+50n を連打（HP300タンク、Skyliner でにげる0）。
  詰めはタケルライコ Bellowing Thunder（盤面エネ×70）とピッピ Full Moon Rondo（両ベンチ×20）。
"""

import os
import sys
from collections import Counter, defaultdict

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
    AttackPlan,
    BasePolicy,
    CARD_DB,
    DIAG,
    LETHAL_BAND,
    active_pokemon,
    all_my_pokemon,
    attack_cost,
    damage_on,
    energy_count,
    get_card,
    hand_ids,
    has_in_play,
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

# ── カードID（デッキ設計_ガルーラ.md のリスト） ──

KANGA = 756           # メガガルーラex HP300 megaEx（Run Errand: バトル場で2ドロー）
OGERPON_TEAL = 96     # オーガポンみどりのめんex HP210 テラスタル（Teal Dance: {G}加速+1ドロー）
OGERPON_WELL = 108    # オーガポンいどのめんex HP210 テラスタル
RAGING_BOLT = 63      # タケルライコex HP240（Bellowing Thunder: 盤面エネ×70）
LATIAS = 184          # ラティアスex HP210（Skyliner: たねポケモンにげる0）
CLEFAIRY = 272        # リーリエのピッピex HP190（Fairy Zone: 相手ドラゴンの弱点を{P}に）
FEZANDIPITI = 140     # キチキギスex HP210（Flip the Script: 被KO後3ドロー）
MEOWTH = 1071         # ニャースex HP170（Last-Ditch Catch: ベンチに出すとサポートサーチ）

PRIME_CATCHER = 1088  # プライムキャッチャー（ACE SPEC: 相手ベンチ吊り出し+自分入れ替え）
NIGHT_STRETCHER = 1097
GLASS_TRUMPET = 1098  # ガラスのラッパ（テラスタルが場: トラッシュのエネをベンチ{C}2体へ）
ENERGY_SWITCH = 1116
ULTRA_BALL = 1121
XEROSIC = 1197
CRISPIN = 1198        # クリスピン（基本エネ2種サーチ・1枚付ける）
CYRANO = 1205         # シアノ（ex3体サーチ）
AREA_ZERO = 1250      # エリアゼロの深淵（テラスタルが場: ベンチ8匹）

G_ENERGY = 1
W_ENERGY = 3
L_ENERGY = 4
P_ENERGY = 5
F_ENERGY = 6
ALL_ENERGY = {G_ENERGY, W_ENERGY, L_ENERGY, P_ENERGY, F_ENERGY}

ATK_RAPID_FIRE = 1092  # ガルーラ {C}{C}{C} 200+コイン表×50
ATK_MYRIAD = 120       # みどりオーガポン {G}{G}{G} 30+両バトル場エネ×30
ATK_SOB = 135          # いどオーガポン {C} 20
ATK_TORRENTIAL = 136   # いどオーガポン {W}{C}{C} 100+エネ3枚山戻しでベンチ120
ATK_BURST_ROAR = 71    # タケルライコ {C} 手札を捨てて6ドロー
ATK_BELLOWING = 72     # タケルライコ {L}{F} 基本エネ好きなだけトラッシュ×70
ATK_EON_BLADE = 243    # ラティアス {P}{P}{C} 200（次ターン攻撃不可）
ATK_FULL_MOON = 371    # ピッピ {P}{C} 20+両ベンチ×20
ATK_CRUEL_ARROW = 183  # キチキギス {C}{C}{C} 好きな相手1体に100
ATK_TUCK_TAIL = 1546   # ニャース {C}{C}{C} 60+自身を手札に戻す

POKEMON_IDS = {KANGA, OGERPON_TEAL, OGERPON_WELL, RAGING_BOLT, LATIAS,
               CLEFAIRY, FEZANDIPITI, MEOWTH}

# 強制エネトラッシュ（minCount>0）の移動元・優先度（高いほど捨ててよい）
_ENERGY_OWNER_PREF = {OGERPON_TEAL: 100, MEOWTH: 95, FEZANDIPITI: 90, CLEFAIRY: 80,
                      LATIAS: 70, OGERPON_WELL: 60, RAGING_BOLT: 50, KANGA: 10}

# div-K13（2026-07-11 divergence 実測・調整日 07-08/07-09 両日・10サンプル）:
# Bellowing Thunder の弾選びは上位ピロットの実測順に = タケルライコ自身のエネから燃やし、
# Teal Dance で毎ターン再生できるオーガポンのエネは最後まで守る
# （旧テーブルは Teal 最優先・RB/ガルーラ保護で真逆だった。
#  実測: human=(RB,RB)/(RB,RB,RB)/(RB,RB,Teal)/(Meowth,RB,RB,Teal,Teal)/(Kanga,RB,RB,Teal,Teal) 等）
_BT_OWNER_PREF = {RAGING_BOLT: 95, MEOWTH: 90, FEZANDIPITI: 85, CLEFAIRY: 80,
                  LATIAS: 70, OGERPON_WELL: 60, KANGA: 50, OGERPON_TEAL: 45}


def _energy_types(pokemon):
    """ポケモンに付いた基本エネのタイプ一覧（energyCards の cardId → energyType）。"""
    cards = getattr(pokemon, "energyCards", None) or []
    types = []
    for ec in cards:
        d = CARD_DB.get(ec.id)
        types.append(getattr(d, "energyType", 0) if d else 0)
    if not types:
        types = list(getattr(pokemon, "energies", []) or [])
    return types


def _can_pay_colored(pokemon, attack_id):
    """色を見るコスト判定（policy_base の枚数判定の厳密版。基本エネ前提）。"""
    cost = attack_cost(attack_id)
    if cost is None or pokemon is None:
        return False
    avail = Counter(_energy_types(pokemon))
    colorless = 0
    for req in cost:
        if req == 0:
            colorless += 1
        elif avail[req] > 0:
            avail[req] -= 1
        else:
            return False
    return sum(avail.values()) >= colorless


class MegaKangaskhanPolicy(BasePolicy):
    DECK_NAME = "mega_kangaskhan"
    GO_FIRST = True            # R-21 確定（7/6実測: レート1000+ピロットの IS_FIRST 選択 YES 20/20）
    TAKE_MULLIGAN = True       # R-22【ハード・プロジェクト共通】マリガンは常にマックス引く
    ATTACKER_IDS = {KANGA, OGERPON_TEAL, RAGING_BOLT, OGERPON_WELL, CLEFAIRY, LATIAS}
    ENERGY_IDS = ALL_ENERGY
    LINE_PROTECT_IDS = {KANGA, PRIME_CATCHER}                       # R-13（詳細は独自 discard）
    SELF_SCALING_ATTACK_IDS = frozenset({ATK_MYRIAD, ATK_BELLOWING})  # R-10 例外

    def __init__(self):
        super().__init__()
        self.p = {}
        self._prev_turn = None
        self._prev_opp_pz = 6
        self._ko_recent = False

    def reset_game(self):
        super().reset_game()
        self._prev_turn = None
        self._prev_opp_pz = 6
        self._ko_recent = False

    # ═══════════════ ターン分析（軽量: 枚数と旗だけ） ═══════════════

    def choose(self, obs):
        # 自分の前ターン以降に相手がサイドを取った = 自分の誰かが KO された
        # （Flip the Script / キチキギス素出しゲートの近似トリガー）
        turn = obs.current.turn
        opp_pz = len(opp_state(obs).prize)
        if turn != self._prev_turn:
            self._ko_recent = opp_pz < self._prev_opp_pz
            self._prev_turn = turn
            self._prev_opp_pz = opp_pz
        self.p = self._analyze(obs)
        self.p["ko_recent"] = self._ko_recent
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
        safe_draws = ms.deckCount - my_prize - 1     # R-11
        opp = opp_state(obs)
        opp_pokes = [p for p in (opp.active + opp.bench) if p]
        opp_has_dragon = any(
            getattr(CARD_DB.get(p.id), "energyType", None) == 9 for p in opp_pokes)
        # ガルーラのエネ不足（場の最良個体）
        kanga_need = None
        for pk in all_my_pokemon(obs):
            if pk.id == KANGA:
                need = max(0, 3 - energy_count(pk))
                kanga_need = need if kanga_need is None else min(kanga_need, need)
        donor_spare = sum(energy_count(pk) for pk in all_my_pokemon(obs) if pk.id != KANGA)
        hand_energy = sum(hc[e] for e in ALL_ENERGY)
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "bench_free": bench_free,
            "stadium_id": stadium_id, "safe_draws": safe_draws,
            "opp_hand": opp.handCount, "opp_prizes": len(opp.prize),
            "opp_has_dragon": opp_has_dragon,
            "tera_in_play": fc[OGERPON_TEAL] + fc[OGERPON_WELL] > 0,
            "clefairy_in_play": fc[CLEFAIRY] > 0,
            "kanga_need": kanga_need, "donor_spare": donor_spare,
            "hand_energy": hand_energy,
            "discard_energy": sum(dc[e] for e in ALL_ENERGY),
        }

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場のメガガルーラex が Rapid-Fire Combo を払える（エネ3枚以上・色不問）。"""
        return any(p.id == KANGA and energy_count(p) >= 3 for p in all_my_pokemon(obs))

    def attack_damage(self, obs, attacker, attack_id):
        if attack_id == ATK_RAPID_FIRE:
            return 200                    # E-1: 保証値200（コインの+50nは上振れ扱い）
        if attack_id == ATK_MYRIAD:
            opp_act = opp_active_pokemon(obs)
            return 30 + 30 * (energy_count(attacker) + energy_count(opp_act))
        if attack_id == ATK_BELLOWING:
            # E-2: 盤面の基本エネ全部を弾にした上限値（実際の消費は DISCARD_ENERGY_CARD 側で制御）
            total = sum(energy_count(pk) for pk in all_my_pokemon(obs))
            return 70 * total
        if attack_id == ATK_FULL_MOON:
            mine = [pk for pk in my_state(obs).bench if pk]
            mb = len(mine) - (1 if any(pk is attacker for pk in mine) else 0)
            ob = len(opp_bench_pokemon(obs))
            return 20 + 20 * (mb + ob)
        if attack_id in (ATK_CRUEL_ARROW, ATK_TORRENTIAL):
            return 100
        return super().attack_damage(obs, attacker, attack_id)

    def plan_attacks(self, obs):
        """色を見るコスト判定 + Skyliner（ラティアスが場: たねはにげる0）を織り込む。"""
        plans = []
        active = active_pokemon(obs)
        if active is not None:
            for aid in (CARD_DB.get(active.id).attacks if active.id in CARD_DB else []):
                if _can_pay_colored(active, aid):
                    plans.append(AttackPlan(active, aid, self.attack_damage(obs, active, aid)))
        skyliner = has_in_play(obs, LATIAS)
        cost = 0 if skyliner else retreat_cost(active) if active else 99
        if (active is not None and not obs.current.retreated
                and energy_count(active) >= cost):
            for pk in my_state(obs).bench:
                if pk is None or pk.id not in self.ATTACKER_IDS:
                    continue
                for aid in (CARD_DB.get(pk.id).attacks if pk.id in CARD_DB else []):
                    if _can_pay_colored(pk, aid):
                        plans.append(AttackPlan(pk, aid, self.attack_damage(obs, pk, aid),
                                                needs_retreat=True))
        return plans

    def judge_lethal(self, obs):
        """R-07 拡張: ボスの指令に加えてプライムキャッチャー（グッズ）でも吊り出しリーサルを見る。"""
        lethal = super().judge_lethal(obs)
        if lethal is not None:
            return lethal
        if PRIME_CATCHER not in hand_ids(obs):
            return None
        my_remaining = len(my_state(obs).prize)
        plans = self.plan_attacks(obs)
        if not plans:
            return None
        for target in opp_bench_pokemon(obs):
            if prize_value(target) < my_remaining:
                continue
            for plan in plans:
                if self.guard_damage(plan.damage, plan.attacker, target) >= target.hp:
                    return {"route": "boss", "via": "prime", "target": target,
                            "attack_id": plan.attack_id, "attacker": plan.attacker,
                            "needs_retreat": plan.needs_retreat}
        return None

    def guard_damage(self, base_damage, attacker, target):
        """弱点をアタッカー毎のタイプで計算（混成デッキ）+ Fairy Zone（相手ドラゴン弱点={P}）。"""
        if target is not None and target.id in mt.IMMUNE_TO_EX_ACTIVE and is_ex(attacker):
            return 0
        data = CARD_DB.get(attacker.id) if attacker is not None else None
        atype = getattr(data, "energyType", None) if data else None
        wv = weakness_value(target)
        tdata = CARD_DB.get(target.id) if target is not None else None
        if (self.p.get("clefairy_in_play") and tdata is not None
                and getattr(tdata, "energyType", None) == 9):
            wv = 5   # Fairy Zone: 相手の{N}ポケモンの弱点は{P}
        if wv is not None and atype is not None and wv == atype:
            return base_damage * 2
        return base_damage

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # S-1（実測 SETUP_ACTIVE: ガルーラ14 > ラティアス7 > オーガポン6）
            table = {KANGA: 20, LATIAS: 12, OGERPON_TEAL: 10, CLEFAIRY: 6,
                     RAGING_BOLT: 5, OGERPON_WELL: 4, FEZANDIPITI: 3, MEOWTH: 2}
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # div-K1（2026-07-07 divergence 実測）: 上位ピロットはセットアップで一切ベンチに
            # 出さない（30/30。ニャースの Last-Ditch Catch を MAIN で切るため手札に温存）
            return -10000, "div-K1: never bench during setup"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_number(self, obs, opt):
        # R-11: ドロー枚数の選択は山札切れガード内で最大
        n = opt.number or 0
        if obs.select.context == SelectContext.DRAW_COUNT and n > self._safe_draws():
            return -1000 - n, "R-11: cap draw count"
        return n, "number"

    # ═══════════════ 優先則（純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex

        # ── ABILITY 帯（R-04 最上位。ドロー系→加速の順） ──
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == FEZANDIPITI:
                if self._safe_draws() >= 3:
                    return 29500, "S-3: Flip the Script (draw 3)"
                return -1, "R-11: deck thin (Flip the Script)"
            if cid == KANGA:
                if self._safe_draws() >= 2:
                    return 29000, "S-3: Run Errand (draw 2)"
                return -1, "R-11: deck thin (Run Errand)"
            if cid == OGERPON_TEAL:
                # div-K10 は棄却（2026-07-08: Teal Dance を手張り帯の下へ下げたら MAIN 40%→35% に
                # 悪化して差し戻し。手張り→Teal Dance の順は situational で帯移動では表現できない）
                if self._safe_draws() >= 1:
                    return 28500, "S-3: Teal Dance (accel + draw)"
                return -1, "R-11: deck thin (Teal Dance)"
            if cid in POKEMON_IDS:
                return 26000, "generic own ability"
            # div-K11（2026-07-08 divergence 実測・7/7）: 相手スタジアム等の他所の特性は押さない
            # （human=ATTACK / ours=ABILITY Spikemuth ×3。div-G2 と同型）
            return -1, "div-K11: skip foreign ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.RETREAT:
            return self._score_retreat(obs)

        if opt.type == OptionType.ATTACK:
            return self._score_attack(obs, opt, combat)

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY, OptionType.ENERGY_CARD):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

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
            # div-K4（2026-07-07 divergence 実測）: 上位ピロットは**必要な駒だけ**素出しして
            # 残りは手札に温存する（我々の全部出しが MAIN 不一致の最大要因: ours=PLAY/Meowth ×230）。
            # （計測済み: 素出しを ABILITY 帯より上にすると MAIN 一致率 34%→21% に悪化 → 20000 帯）
            score, reason = -1, "div-K4: hold pokemon in hand"
            has_supporter_in_hand = any(
                hc[s] for s in (CRISPIN, CYRANO, mt.BOSS, XEROSIC))
            if cid == MEOWTH:
                # div-K16（2026-07-11 divergence 実測・07-08/07-09 両日）: div-K4 のゲートが
                # 強すぎた（human=PLAY/Meowth 17+10件 / ours=3+4件）。1体目は手札サポートの
                # 有無に関係なく出して次のサポートをストック。2体目以降のみ旧ゲート
                if fc[MEOWTH] == 0 or (not has_supporter_in_hand
                                       and not obs.current.supporterPlayed):
                    score, reason = 20500, "S-4/div-K16: Meowth (fetch supporter)"
            elif cid == OGERPON_TEAL:
                if fc[OGERPON_TEAL] == 0:
                    score, reason = 20450, "S-2: Ogerpon (Teal Dance)"
                elif fc[OGERPON_TEAL] == 1:
                    score, reason = 12000, "S-2: 2nd Ogerpon"
            elif cid == KANGA:
                if fc[KANGA] == 0:
                    score, reason = 20400, "S-2: Kangaskhan (attacker)"
                elif fc[KANGA] == 1:
                    # div-K16: 2体目は「1体目が負傷 or 直前に被KO」の時だけ（E-4 ローテ用。
                    # 上位ピロットは余剰ガルーラを手札温存→ボール/ロアーの捨て札にする。
                    # 実測 ours=PLAY/Mega 25+36件 / human=6+4件、DISCARD では余剰ガルーラを捨てる）
                    kanga_hurt = any(pk.id == KANGA and damage_on(pk) >= 100
                                     for pk in all_my_pokemon(obs))
                    if kanga_hurt or p.get("ko_recent"):
                        score, reason = 12500, "S-2/div-K16: backup Kangaskhan (rotate)"
            elif cid == CLEFAIRY:
                # div-K14（2026-07-11 divergence 実測・07-08/07-09 両日）: 上位ピロットは
                # Clefairy を対ドラゴン専用テックではなく Full Moon Rondo（20+両ベンチ×20、
                # エリアゼロ下で最大340）のメインアタッカーとして交戦期に素出しする
                # （human=PLAY/Clefairy 7+8件 / ours=0件、ATTACH→Clefairy 9+10件、Rondo 攻撃 5+2件）
                if fc[CLEFAIRY] == 0 and (p["opp_has_dragon"] or combat):
                    score, reason = 20350, "div-K14: Clefairy (Full Moon Rondo / Fairy Zone)"
            elif cid == LATIAS:
                if fc[LATIAS] == 0:
                    score, reason = 20300, "S-2: Latias (Skyliner)"
            elif cid == FEZANDIPITI:
                if p.get("ko_recent") and fc[FEZANDIPITI] == 0:
                    score, reason = 20200, "S-3: Fezandipiti (Flip the Script live)"
            elif cid == RAGING_BOLT:
                if combat and fc[RAGING_BOLT] == 0 and p["donor_spare"] >= 3:
                    score, reason = 12800, "E-2: Raging Bolt (Bellowing soon)"
            elif cid == OGERPON_WELL:
                if fc[OGERPON_TEAL] + fc[OGERPON_WELL] == 0:
                    score, reason = 20100, "S-6: Wellspring (Tera enabler)"
            # R-03: ベンチ0は最優先で解消（ドンク回避。ゲートより優先）
            bench_empty = len([b for b in my_state(obs).bench if b]) == 0
            if bench_empty:
                score = max(score, 15000) + 5000
                reason = f"R-03: bench empty ({reason})"
            elif score > 0 and p["bench_free"] <= 1:
                score -= 5000   # R-24
            return score, reason

        # スタジアム
        # div-K15（2026-07-11 divergence 実測・07-08/07-09 両日）: グッズ/スタジアムは
        # 「使うターンまで手札に温存」。上位ピロットは human=END で温存する局面で我々が
        # PLAY を連発していた（不一致実測: ours=AZ 19+26 / ES 33+22 / NS 21+20 / UB 20+37 に対し
        # human 側の実使用は各 2〜9 件。human=END 28+37 / ours=END 0+2）
        if cid == AREA_ZERO:
            if p["stadium_id"] == AREA_ZERO:
                return -1, "Area Zero already up"
            # div-K15: ベンチ枠が要る時（満杯近く）か Rondo プラン（Clefairy 在場）だけ置く
            if p["tera_in_play"] and (p["bench_free"] <= 1 or fc[CLEFAIRY] >= 1):
                return 19500, "S-6/div-K15: Area Zero (bench 8 needed)"
            return -1, "div-K15: hold Area Zero"

        # グッズ
        if cid == ULTRA_BALL:
            if p["hand_size"] < 3:
                return -1, "Ultra Ball: hand too thin"
            missing_core = ((fc[KANGA] == 0 and hc[KANGA] == 0)
                            or (fc[OGERPON_TEAL] == 0 and hc[OGERPON_TEAL] == 0))
            if missing_core:
                return 17000, "S-4: Ultra Ball"
            # div-K15: コアが揃っていれば薄い手札の掘り直しだけに使う
            if p["hand_size"] <= 4:
                return 9000, "S-4/div-K15: Ultra Ball (dig thin hand)"
            return -1, "div-K15: hold Ultra Ball"
        if cid == GLASS_TRUMPET:
            benched_c = any(pk.id in (KANGA, MEOWTH) and energy_count(pk) < 3
                            for pk in my_state(obs).bench if pk)
            if p["tera_in_play"] and p["discard_energy"] >= 1 and benched_c:
                return 15000, "S-5: Glass Trumpet (discard accel)"
            return -1, "Glass Trumpet: no value"
        if cid == ENERGY_SWITCH:
            # div-K15: 「ガルーラの3枚目が今ターン間に合う」時だけ（kanga_need==1。
            # 設計md S-5 の原義に戻す。human の実使用は 2+3 件のみ）
            if p["kanga_need"] == 1 and p["donor_spare"] >= 1:
                return 14000, "S-5/div-K15: Energy Switch -> Kangaskhan (3rd now)"
            return -1, "div-K15: hold Energy Switch"
        if cid == NIGHT_STRETCHER:
            dcc = p["dc"]
            # div-K15: コア回収は「場+手札のコアが尽きかけ（<2）」まで温存
            if (dcc[KANGA] + dcc[OGERPON_TEAL] >= 1
                    and fc[KANGA] + hc[KANGA] + fc[OGERPON_TEAL] + hc[OGERPON_TEAL] < 2):
                return 13000, "div-K15: Night Stretcher (core nearly out)"
            # div-K15: エネ回収は「今ガルーラに足りない」時だけ
            if (p["discard_energy"] >= 1 and p["hand_energy"] == 0
                    and (p["kanga_need"] or 0) >= 1):
                return 11000, "div-K15: Night Stretcher (fuel needed now)"
            return -1, "div-K15: hold Night Stretcher"
        if cid == PRIME_CATCHER:
            lethal = self.t.get("lethal")
            if lethal is not None and lethal.get("via") == "prime":
                return LETHAL_BAND, "R-07: LETHAL Prime Catcher"
            return -1, "save Prime Catcher (ACE SPEC)"

        # サポート（択一）
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        # div-K4: 上位ピロットはサポートを早いスコア帯で切る（Crispin 74回 = 最多 PLAY）
        if cid == CRISPIN:
            if p["hand_energy"] == 0 or (p["kanga_need"] or 0) >= 1:
                return 16000, "S-5: Crispin (energy toolbox)"
            return 5000, "Crispin (stock energy)"
        if cid == CYRANO:
            ex_stock = sum(fc[i] + hc[i] for i in POKEMON_IDS)
            return (15500 if ex_stock < 4 else 4500), "S-4: Cyrano (ex search)"
        if cid == mt.BOSS:
            return -1, "save Boss (lethal only, R-07)"
        if cid == XEROSIC:
            if p["opp_hand"] >= 6:
                return 4500, "E-3: Xerosic (big hand)"
            return -1, "save Xerosic"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id
        if cid not in ALL_ENERGY:
            return -500, "skip non-energy attach"
        if obs.select.context == SelectContext.MAIN and obs.current.energyAttached:
            return -1, "already attached"

        e = energy_count(target)
        etype = getattr(CARD_DB.get(cid), "energyType", 0)
        if tid == KANGA:
            score = 8300 if e < 3 else -1          # R-10: Rapid-Fire コスト3で打ち止め
            reason = "S-5: fuel Rapid-Fire Combo"
        elif tid == RAGING_BOLT:
            have = Counter(_energy_types(target))
            need_l = etype == 4 and have[4] == 0
            need_f = etype == 6 and have[6] == 0
            # R-10: 手張りはコスト2まで（Bellowing の弾はエネつけかえ/ラッパで足す）
            score = 8100 if (need_l or need_f) and e < 2 else -1
            reason = "S-5: Bellowing Thunder colors"
        elif tid == OGERPON_TEAL:
            # R-10: 手張りは Myriad コスト3まで（それ以上の積み増しは Teal Dance 側で行う）
            score = (7900 + e * 10) if e < 3 else -1
            reason = "S-5: Myriad scaling / Energy Switch fodder"
        elif tid == CLEFAIRY:
            # div-K14: Rondo コスト {P}{C} は色不問側を G 等でも払う（実測 human=ATTACH G→Clefairy
            # 9+10件。ドラゴンゲートは撤去し、P を微優先）
            score = (7950 if etype == 5 else 7925) if e < 2 else -1
            reason = "div-K14: fuel Full Moon Rondo"
        elif tid == OGERPON_WELL:
            score = 7600 if etype == 3 and e < 3 else -1
            reason = "S-5: fuel Torrential Pump"
        elif tid == LATIAS:
            score = 6000 if etype == 5 and e < 3 else -1
            reason = "S-5: fuel Eon Blade"
        else:
            return -1, "attach: wrong target"
        if score > 0 and self.is_threatened(target):
            score -= 2000   # R-08: 負け筋への追い銭防止
        return score, reason

    # ── RETREAT（Skyliner 前提のピボット） ──

    def _score_retreat(self, obs):
        active = active_pokemon(obs)
        if active is None:
            return -100, "no active"
        aid = active.id
        bench = [pk for pk in my_state(obs).bench if pk]
        bench_ready = any(pk.id == KANGA and energy_count(pk) >= 3 for pk in bench)
        bench_kanga = any(pk.id == KANGA for pk in bench)
        if aid == KANGA:
            if damage_on(active) >= 150 and bench_ready:
                return 2000, "E-4: rotate damaged Kangaskhan"
            return -5000, "keep Kangaskhan active (Run Errand)"
        # div-K6（2026-07-07 divergence 実測）: Run Errand は「バトル場にいれば」なので、
        # 非アタッカーが前にいるターンは**特性より先に**ガルーラへピボットする
        # （Skyliner でにげる0。上位ピロットの RETREAT 96回の主因）
        if bench_kanga and (aid in (LATIAS, MEOWTH, FEZANDIPITI, CLEFAIRY)
                            or energy_count(active) == 0):
            return 28800, "div-K6: pivot to Kangaskhan (Run Errand first)"
        if bench_ready:
            return 2500, "promote ready Kangaskhan"
        return -100, "avoid retreat"

    # ── ATTACK（R-04 最下帯。ダメージ優先 + 例外） ──

    def _score_attack(self, obs, opt, combat):
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        if active is None:
            return 0, "no active"
        if aid == ATK_BURST_ROAR:
            # 手札リフレッシュ（ターン終了と引き換え）。攻撃打点がある時は選ばない
            if self.p["hand_size"] <= 3 and self._safe_draws() >= 6:
                return 990, "Burst Roar (refresh thin hand)"
            return 200, "Burst Roar: save"
        dmg = self.attack_damage(obs, active, aid)
        if aid == ATK_BELLOWING and self.t.get("lethal") is None:
            # E-2: 非リーサル時はガルーラのエネを除いた「余剰エネ」だけを弾に数え、
            # それでも相手バトル場を倒せないなら 0（盤面エネの空焚き禁止 = 対ブリジュラス戦の敗因）
            spare = sum(energy_count(pk) for pk in all_my_pokemon(obs) if pk.id != KANGA)
            opp_act = opp_active_pokemon(obs)
            if opp_act is not None and 70 * spare >= opp_act.hp:
                dmg = min(70 * spare, 70 * ((opp_act.hp + 69) // 70))
            else:
                dmg = 0
        score = 1000 + min(dmg, 900)
        if aid == ATK_EON_BLADE:
            score -= 150   # 次ターン攻撃不可のペナルティ
        if aid == ATK_TUCK_TAIL:
            score = 850    # 実測使用0回。盤面から消える
        return score, "E-1: attack"

    # ── CARD/ENERGY 選択（サーチ先・移動元/先・前出し等） ──

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
                e = energy_count(card) if card is not None else 0
                # div-K1: エネの乗った駒を優先（攻撃継続性）
                if cid == KANGA:
                    score, reason = 15000 + e * 400, "promote Kangaskhan"
                    if p["opp_prizes"] <= 3:
                        score -= 6000   # E-4/R-09: megaEx=3枚を終盤に晒さない
                        reason = "R-09: avoid exposing 3-prize Kangaskhan"
                elif cid == LATIAS:
                    # div-K18（2026-07-11 divergence 実測・07-08/07-09 両日）: エネ付き Teal より
                    # 優先して前出し（実測 human=Latias / ours=Teal ×6。div-K9 の 9200 では
                    # Teal の e*400 に逆転されていた。SWITCH +2/+1・TO_ACTIVE 改善を確認）
                    score, reason = 9900 + e * 200, "div-K9/K18: promote Latias (Skyliner)"
                elif cid == OGERPON_TEAL:
                    score, reason = 9000 + e * 400, "promote Ogerpon"
                elif cid == CLEFAIRY:
                    # div-K14: エリアゼロ下の Rondo アタッカーとして前出し（実測 SWITCH/TO_ACTIVE
                    # human=Clefairy 2+2件。エネが乗り AZ が立っている時はラティアス級に昇格）
                    score = (6000 + e * 300
                             + (2500 if p["stadium_id"] == AREA_ZERO else 0)
                             + (2000 if p["opp_has_dragon"] else 0))
                    reason = "div-K14: promote Clefairy (Full Moon Rondo)"
                elif cid == OGERPON_WELL:
                    score, reason = 5500 + e * 200, "promote Wellspring"
                elif cid == RAGING_BOLT:
                    score, reason = 5000 + e * 300, "promote Raging Bolt"
                elif cid == FEZANDIPITI:
                    score, reason = 4000, "promote Fezandipiti (protect engine)"
                elif cid == MEOWTH:
                    score, reason = 3500, "promote Meowth (protect engine)"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            return self.default_score_damage_target(obs, opt)   # 吊り出し: R-15

        if ctx == SelectContext.DAMAGE:
            # E-5: Cruel Arrow / Torrential Pump 120 の対象
            if card is not None and pi != yi:
                hp = getattr(card, "hp", 999)
                if hp <= 120:
                    return 15000 + (500 - hp), "E-5/R-15: snipe KO"
                return self.default_score_damage_target(obs, opt)
            return 0, "damage own side"

        if ctx == SelectContext.TO_HAND:
            return self._score_to_hand(obs, cid)

        if ctx == SelectContext.TO_BENCH:
            table = {OGERPON_TEAL: 100, MEOWTH: 90, LATIAS: 80, KANGA: 70, FEZANDIPITI: 40}
            return table.get(cid, 10), "to bench"

        if ctx in (SelectContext.ATTACH_TO, SelectContext.TO_FIELD, SelectContext.ATTACH_FROM):
            # div-K2（2026-07-07 divergence 実測）: ATTACH_FROM も「付け先」選択
            # （クリスピン/ガラスのラッパ等。上位ピロットはエネ0のニャース等にも「弾込め」する）
            if card is not None and hasattr(card, "energyCards"):
                e = energy_count(card)
                if cid == KANGA and e < 3:
                    return 100, "S-5: Kangaskhan first"
                if cid == RAGING_BOLT and e < 2:
                    return 85, "div-K8: Bellowing colors first"
                if cid == OGERPON_TEAL and e < 3:
                    return 60, "S-5: Ogerpon (scaling/fodder)"
                if cid in (MEOWTH, FEZANDIPITI) and e == 0:
                    return 55, "div-K2: park energy (Bellowing fuel)"
                if cid == OGERPON_WELL and e < 3:
                    return 50, "S-5: Wellspring"
                if cid == CLEFAIRY and e < 2:
                    return 70, "div-K14: load Clefairy (Rondo)"
                if cid == LATIAS and e < 3:
                    return 40, "S-5: Latias"
                if cid == KANGA:
                    return 15, "Kangaskhan overflow"
                return 5, "attach-to other"
            return 500, "to field"

        if ctx == SelectContext.SWITCH_ENERGY_CARD:
            # エネつけかえの移動エネ選択（所有ポケモンで解決）= オーガポンのG最優先。
            # ガルーラの3枚は割らない
            owner = card
            oid = owner.id if owner else None
            if oid == KANGA:
                if energy_count(owner) > 3:
                    return 60, "move Kangaskhan overflow"
                return -1, "keep Kangaskhan's 3"
            table = {OGERPON_TEAL: 100, MEOWTH: 95, FEZANDIPITI: 90, CLEFAIRY: 80,
                     LATIAS: 70, OGERPON_WELL: 50, RAGING_BOLT: 30}
            return table.get(oid, 40), "energy source"

        if ctx == SelectContext.DISCARD_ENERGY_CARD:
            return self._score_energy_discard(obs, opt)

        if ctx == SelectContext.TO_DECK_ENERGY:
            return 100, "E-2: Torrential Pump boost (shuffle 3)"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            return self._score_discard(obs, opt)

        if ctx == SelectContext.TO_DECK:
            if cid in POKEMON_IDS:
                return 100, "to deck pokemon"
            return 10, "to deck other"

        if opt.type == OptionType.ENERGY:
            return 500, "take energy"

        return 500, "generic card"

    # ── TO_HAND（サーチ先。div-K3: 同名を重ねず核をばらけて取る） ──

    def _score_to_hand(self, obs, cid):
        p = self.p
        fc, hc = p["fc"], p["hc"]
        # div-K3（2026-07-07 divergence 実測）: シアノ等の複数サーチで上位ピロットは
        # (ガルーラ, オーガポン, ラティアス) のような異なる核を取る（同名スタックしない）。
        # 同一 cid の2枚目以降を採点のたびに減点していく
        seen = p.setdefault("_th_seen", {})
        dup_penalty = seen.get(cid, 0) * 60
        seen[cid] = seen.get(cid, 0) + 1
        base = 100 - hc.get(cid, 0) * 40 - dup_penalty
        # div-K17【棄却・2026-07-11】: シアノ指名の実測順（Latias 先取り・盤面済みコア2枚目の
        # 後回し・Crispin 恒常優先）をテーブル化したが TO_HAND 43%→40%（07-08）/ 57%→57%−1件
        # （07-09）と両日悪化して差し戻し（取得順は盤面文脈依存が強く一律表では写せない。
        # div-K7 と同型の教訓）
        if cid == OGERPON_TEAL:
            return base + (85 if fc[OGERPON_TEAL] == 0 else 65), "take Ogerpon"
        if cid == KANGA:
            return base + (80 if fc[KANGA] + hc[KANGA] == 0 else 60), "take Kangaskhan"
        if cid == MEOWTH:
            return base + 82, "take Meowth (supporter chain)"
        if cid == CRISPIN:
            return base + (75 if (p["kanga_need"] or 0) >= 1 or p["hand_energy"] == 0 else 40), "take Crispin"
        if cid == CYRANO:
            return base + 65, "take Cyrano"
        if cid == LATIAS:
            return base + (62 if fc[LATIAS] + hc[LATIAS] == 0 else 30), "take Latias"
        if cid == G_ENERGY:
            return base + (58 if hc[G_ENERGY] == 0 else 20), "take G energy (Teal Dance)"
        if cid == mt.BOSS:
            return base + (55 if p["opp_prizes"] <= 4 else 30), "take Boss"
        if cid == FEZANDIPITI:
            return base + 45, "take Fezandipiti"
        if cid == RAGING_BOLT:
            return base + 35, "take Raging Bolt"
        if cid == CLEFAIRY:
            # div-K14: Rondo アタッカーとしてサーチ対象（実測 Cyrano 3枚指名に Clefairy が入る）
            return base + (50 if p["opp_has_dragon"] else 42), "take Clefairy"
        if cid in (W_ENERGY, L_ENERGY, P_ENERGY, F_ENERGY):
            return base + 25, "take colored energy"
        if cid == OGERPON_WELL:
            return base + 15, "take Wellspring"
        if cid == XEROSIC:
            return base - 30, "take Xerosic"
        return base, "take other"

    # ── エネのトラッシュ（Bellowing Thunder = 必要枚数だけ / 強制コスト） ──

    def _score_energy_discard(self, obs, opt):
        p = self.p
        owner = option_card(obs, opt)
        oid = owner.id if owner else None
        if obs.select.minCount > 0:
            # 強制（にげるコスト等）: 捨ててよい順
            return _ENERGY_OWNER_PREF.get(oid, 40), "forced energy discard"
        # Bellowing Thunder: 必要枚数を owner 優先度つきで事前確定（E-2）
        if "bt_pick" not in p:
            opp_act = opp_active_pokemon(obs)
            hp = opp_act.hp if opp_act is not None else 0
            need = (hp + 69) // 70 if hp > 0 else 0
            if self.t.get("lethal") is None:
                # div-K13: KO に必要ならガルーラ/ライコ自身のエネも燃やす（上位ピロット実測。
                # 旧 spare 計算は非ガルーラのみで、human=3枚 / ours=0枚 の空振りが出ていた）。
                # 選択肢プール全体でも届かない時だけ空焚き禁止（0枚）を維持
                avail = min(len(obs.select.option), obs.select.maxCount)
                need = need if need <= avail else 0
            ranked = []
            for i, o in enumerate(obs.select.option):
                ow = option_card(obs, o)
                pref = _BT_OWNER_PREF.get(ow.id if ow else None, 40)
                ranked.append((pref, -i, id(o)))
            ranked.sort(reverse=True)
            p["bt_pick"] = {oid_ for _, _, oid_ in ranked[:min(need, obs.select.maxCount)]}
        if id(opt) in p["bt_pick"]:
            return 100 + _BT_OWNER_PREF.get(oid, 40), "div-K13/E-2: Bellowing fuel"
        return -1, "E-2: keep board energy"

    # ── 手札からのトラッシュ（ハイパーボール等。R-13 独自版） ──

    def _score_discard(self, obs, opt):
        # div-K12（2026-07-11 divergence 実測・調整日 07-08/07-09 両日で同方向・38サンプル）:
        # 上位ピロット zoroark190 の捨て順を写した優先表に全面書き換え。実測 =
        # エリアゼロ最優先（17件・単独でも捨てる）> 役目を終えた駒（ニャース/ガルーラ余剰/
        # ラティアス/キチキギス）> クセロシキ > 色エネ（単発でも捨てる）> シアノ >
        # ボール/エネつけかえ/タンカは後回し。同名スタック（Meowth×3, AZ×2, UB×2, G+G）が
        # 実測で多発しており、div-K5 の一律分散ペナルティ（-3000/枚）は撤廃【K5 は本則で置換】。
        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, "cardId", None)
        return self._score_discard_base(obs, cid)

    def _score_discard_base(self, obs, cid):
        p = self.p
        fc, hc = p["fc"], p["hc"]
        if cid == PRIME_CATCHER:
            return -5000, "R-13: keep Prime Catcher (ACE SPEC)"
        if cid == mt.BOSS:
            if hc.get(mt.BOSS, 0) >= 2:
                return 8600, "div-K12: discard extra Boss"
            if p["opp_prizes"] >= 5:
                return 6000, "div-K12: early Boss is fodder"
            return -4000, "R-13: keep last Boss"
        if cid == AREA_ZERO:
            return 11500, "div-K12: Area Zero is top fodder"
        if cid == MEOWTH and (fc.get(MEOWTH, 0) >= 1 or hc.get(MEOWTH, 0) >= 2):
            return 11000, "div-K12: Meowth done its job"
        if cid == KANGA and fc.get(KANGA, 0) >= 1:
            return 10800, "div-K12: surplus Kangaskhan"
        if cid == LATIAS and fc.get(LATIAS, 0) >= 1:
            return 10700, "div-K12: extra Latias (Skyliner up)"
        if cid == FEZANDIPITI and (fc.get(FEZANDIPITI, 0) >= 1
                                   or hc.get(FEZANDIPITI, 0) >= 2):
            return 10600, "div-K12: extra Fezandipiti"
        if cid == XEROSIC:
            return 10300, "div-K12: Xerosic is fodder"
        if cid == OGERPON_TEAL and fc.get(OGERPON_TEAL, 0) >= 2:
            return 10200, "div-K12: 3rd Ogerpon"
        if cid == G_ENERGY:
            if hc.get(G_ENERGY, 0) >= 3:
                return 10000, "discard surplus G energy"
            if hc.get(G_ENERGY, 0) == 2:
                return 9400, "div-K12: discard 2nd G energy"
            return 1500, "discard lone G energy"
        if cid in ALL_ENERGY:
            return 9800, "div-K12: colored energy is fodder (Crispin refetches)"
        if cid == RAGING_BOLT and (fc.get(RAGING_BOLT, 0) >= 1
                                   or hc.get(RAGING_BOLT, 0) >= 2):
            return 9700, "div-K12: extra Raging Bolt"
        if cid == CYRANO:
            return 9300, "div-K12: Cyrano is fodder"
        if cid == ULTRA_BALL:
            return (9000 if hc.get(ULTRA_BALL, 0) >= 2 else 8400), "div-K12: Ultra Ball late fodder"
        if cid == ENERGY_SWITCH:
            if hc.get(ENERGY_SWITCH, 0) >= 2 or not p["kanga_need"]:
                return 8700, "div-K12: idle Energy Switch"
            return 4000, "keep Energy Switch (Kangaskhan needs fuel)"
        if cid == NIGHT_STRETCHER:
            return 8300, "div-K12: Night Stretcher late fodder"
        if cid == GLASS_TRUMPET:
            return 8200, "div-K12: Glass Trumpet late fodder"
        if cid == CRISPIN and hc.get(CRISPIN, 0) >= 2:
            return 8100, "div-K12: discard extra Crispin"
        if cid is not None and hc.get(cid, 0) > 1:
            return 8000, "discard duplicate"
        if cid in POKEMON_IDS and fc.get(cid, 0) >= 1:
            return 2500, "discard pokemon already in play"
        if cid == KANGA or cid == OGERPON_TEAL:
            return -3000, "R-13: keep core line"
        return 1000, "generic discard"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(MegaKangaskhanPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
