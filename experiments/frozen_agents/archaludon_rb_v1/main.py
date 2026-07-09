"""ブリジュラス（Archaludon ex + Cinderace）ルールベースエージェント v1

設計文書との対応（ルールタグをコード中のコメントに付す）:
  - docs/planning/用語とターン手順.md      … 判定/マスク/優先則/手順/サブゴール/フェーズ
  - docs/planning/ルール抽出_オープン実装.md … R-xx / P-xx
  - docs/planning/デッキ設計_ブリジュラス.md … S-x(セットアップ) / E-x(交戦) / 経路A・B

構成（用語に対応するセクション）:
  1. 判定    judge_subgoal / judge_lethal / judge_loss_threats / detect_matchup
  2. マスク  ロス手の抑制(R-08)・過剰エネ(R-10 相当)・山札切れ(R-11 系)
  3. 優先則  セットアップ期 S-1..S-5 / 交戦期 E-1..E-3（スコア帯 = 行動順序 R-04）
  4. 手順    score_option → 優先則 → マッチアップ上書き → プロトコル適用(リーサル昇格・ロス手マスク)
  5. 安全    agent() ラッパー(R-01/R-02)

土台: Kaggle 公開 Notebook "A Sample Archaludon"（masamikobayashi、対 1300+ Starmie 74.4%）の
優先則・マッチアップ上書きを移植し、ターン手順の層（リーサル判定・負け筋カットの常時実行）を追加。
スコアは (score, reason) で全採択理由を追跡できる (P-04)。

判定は毎手番・常時実行（閉形式のみ、探索なし）。時間はプール制(R-23)で v1 は探索を持たないため
時間管理は不要。探索版リーサル検証(R-07 交戦期)は次版。
"""

import os
import sys

try:
    ROOT = __file__
except NameError:
    ROOT = None
CG_PATH = "/kaggle_simulations/agent"
for p in ([os.path.dirname(os.path.abspath(ROOT))] if ROOT else []) + [CG_PATH]:
    if p and p not in sys.path and os.path.isdir(p):
        sys.path.insert(0, p)

from cg.api import (
    AreaType,
    LogType,
    OptionType,
    SelectContext,
    all_card_data,
    to_observation_class,
)

try:
    from cg.api import all_attack
    ALL_ATTACKS = {a.attackId: a for a in all_attack()}
except Exception:
    ALL_ATTACKS = {}

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
BOSS = 1182
EXPLORER = 1185
LILLIE = 1227
FULL_METAL_LAB = 1244

RAGING_HAMMER = 224    # {M}{M}{C} 80+ダメカン×10
METAL_DEFENDER = 253   # {M}{M}{M} 220
_ATTACK_BASE_DMG = {METAL_DEFENDER: 220, 965: 50, 223: 30, 61: 30}

# 相手アーキタイプ検出用 (R-20)
CRUSTLE_LINE = {344, 345, 532}
STARMIE_LINE = {1030, 1031}
LUCARIO_LINE = {677, 678}
HOP_LINE = {288, 289, 299, 304, 307, 308, 309, 310, 878, 879}
HOP_SNORLAX = 304
ALAKAZAM_LINE = {741, 742, 743}
MEGA_BRAVE = 983
CRUSTLE = 345          # 特性: ex/megaEx からのダメージ無効

# S-1: セットアップのアクティブ優先（経路A: エースバーン始動）
_SETUP_ACTIVE_PRIORITY = {
    CINDERACE: (100000, "S-1: Active Cinderace (Explosiveness)"),
    DURALUDON: (20000, "S-1: Active fallback Duraludon (経路B)"),
    RELICANTH: (5000, "S-1: Active fallback Relicanth"),
}

CARD_DB = {c.cardId: c for c in all_card_data()}

LETHAL_BAND = 1_000_000  # R-07: リーサル手の専用スコア帯（全優先則より上）

# 相手の前ターン技の追跡 (E-3: Mega Brave 硬直の利用)
_opp_last_attack_id = None
_cur_turn_logs = []

# ターン手順の判定結果（choose_options 冒頭で毎手番更新。判定は常時実行）
_T = {"phase": "setup", "lethal": None, "threats": [], "matchup": "generic"}


def _update_opp_attack_tracking(obs):
    global _opp_last_attack_id, _cur_turn_logs
    yi = obs.current.yourIndex
    for entry in obs.logs:
        if entry.type == LogType.TURN_END:
            for prev in _cur_turn_logs:
                if prev.type == LogType.ATTACK and getattr(prev, 'playerIndex', yi) != yi:
                    _opp_last_attack_id = prev.attackId
            _cur_turn_logs.clear()
        else:
            _cur_turn_logs.append(entry)


# ═══════════════════════════════ 盤面ヘルパー（判定の材料） ═══════════════════════════════

def read_deck_csv():
    # 空行・余剰行に頑健な読み込み（プロジェクト規約）
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


def metal_in_discard(obs):
    return sum(1 for c in (my_state(obs).discard or []) if c and c.id == METAL_ENERGY)


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


def need_duraludon(obs):
    # S-3: ジュラルドン系統は常に2体構え（1体目を狩られた時の保険 = R-08 との接続点）
    return sum(1 for p in all_my_pokemon(obs) if p.id in {DURALUDON, ARCHALUDON_EX}) < 2


def need_archaludon(obs):
    has_dura, ex_count = False, 0
    for p in all_my_pokemon(obs):
        if p.id == DURALUDON:
            has_dura = True
        elif p.id == ARCHALUDON_EX:
            ex_count += 1
    return has_dura and ex_count < 2


def safe_discard_count(obs):
    ids = hand_ids(obs)
    mt = metal_in_discard(obs)
    safe = 0
    for cid in ids:
        if cid == METAL_ENERGY and mt + safe < 2:
            safe += 1
        elif cid == CINDERACE:
            safe += 1
    draw_in_hand = sum(1 for c in ids if c in (LILLIE, EXPLORER))
    if draw_in_hand >= 2:
        safe += draw_in_hand - 1
    return safe


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


def best_attack_damage(obs, attack_id):
    if attack_id == RAGING_HAMMER:
        return 80 + damage_on(active_pokemon(obs)) // 10 * 10
    return _ATTACK_BASE_DMG.get(attack_id, 0)


def is_metal_weak(pokemon):
    if pokemon is None:
        return False
    data = CARD_DB.get(pokemon.id)
    w = getattr(data, "weakness", None) if data else None
    if w is None:
        return False
    return getattr(w, "value", w) == METAL_ENERGY


def effective_damage(base_damage, target):
    return base_damage * 2 if is_metal_weak(target) else base_damage


def guarded_damage(base_damage, attacker, target):
    # クラッスル特性: ex/megaEx からのダメージ無効（リーサル誤検出防止。strong-start の教訓）
    if target is not None and target.id == CRUSTLE and is_ex(attacker):
        return 0
    return effective_damage(base_damage, target)


def _first_option_index(obs, card_id):
    for o in obs.select.option:
        oc = option_card(obs, o)
        if oc and oc.id == card_id:
            return getattr(o, 'index', None)
    return None


# ── 攻撃ルート（S-4/E-2: Assemble Alloy 連動のエネ計算） ──

def direct_attack_energy_route(obs, pokemon):
    e = energy_count(pokemon)
    if e >= 3:
        return True, False
    if e == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
        return True, True
    return False, False


def can_evolve_to_archaludon_now(pokemon, obs):
    if pokemon is None or pokemon.id != DURALUDON:
        return False
    if ARCHALUDON_EX not in hand_ids(obs):
        return False
    return not getattr(pokemon, "appearThisTurn", True)


def alloy_attack_energy_route(obs, pokemon):
    # S-4: 進化時の Assemble Alloy（トラッシュから鋼2枚）込みでコスト充足を判定
    if not can_evolve_to_archaludon_now(pokemon, obs):
        return False, False
    current = energy_count(pokemon)
    alloy = min(2, metal_in_discard(obs))
    total = current + alloy
    if total >= 3:
        return True, False
    if total == 2 and not obs.current.energyAttached and METAL_ENERGY in hand_ids(obs):
        return True, True
    return False, False


def attack_energy_route(obs, pokemon):
    if pokemon is None:
        return False, False
    if pokemon.id == ARCHALUDON_EX:
        return direct_attack_energy_route(obs, pokemon)
    if pokemon.id == DURALUDON:
        ok, uses_attach = direct_attack_energy_route(obs, pokemon)
        if ok:
            return True, uses_attach
        return alloy_attack_energy_route(obs, pokemon)
    return False, False


def archaludon_ex_attack_route(obs):
    active = active_pokemon(obs)
    if active and active.id in {ARCHALUDON_EX, DURALUDON}:
        ok, uses_attach = attack_energy_route(obs, active)
        if ok:
            return {"attacker": active, "uses_attach": uses_attach, "needs_retreat": False}

    if active is None or obs.current.retreated or energy_count(active) < retreat_cost(active):
        return None
    ps = my_state(obs)
    for pokemon in [p for p in ps.bench if p]:
        if pokemon.id not in {ARCHALUDON_EX, DURALUDON}:
            continue
        ok, uses_attach = attack_energy_route(obs, pokemon)
        if ok:
            return {"attacker": pokemon, "uses_attach": uses_attach, "needs_retreat": True}
    return None


def planned_archaludon_attacks(obs):
    route = archaludon_ex_attack_route(obs)
    if route is None:
        return []
    attacker = route["attacker"]
    attacks = []
    if attacker.id == ARCHALUDON_EX:
        attacks.append({"damage": 220, "attack_id": METAL_DEFENDER, "attacker": attacker})
        if has_in_play(obs, RELICANTH):
            attacks.append({"damage": 80 + damage_on(attacker) // 10 * 10,
                            "attack_id": RAGING_HAMMER, "attacker": attacker})
    if attacker.id == DURALUDON:
        attacks.append({"damage": 80 + damage_on(attacker) // 10 * 10,
                        "attack_id": RAGING_HAMMER, "attacker": attacker})
        if can_evolve_to_archaludon_now(attacker, obs):
            attacks.append({"damage": 220, "attack_id": METAL_DEFENDER, "attacker": attacker})
    return attacks


# ═══════════════════════════════ 判定（predicates。常時実行・行動を選ばない） ═══════════════════════════════

def detect_matchup(obs):
    # R-20: 相手の場のカードID集合からアーキタイプ判定。以後の分岐キー
    opp = opp_state(obs)
    ids = {p.id for p in (opp.active + opp.bench) if p}
    if ids & CRUSTLE_LINE:
        return "crustle"
    if ids & HOP_LINE:
        return "hop"
    if ids & STARMIE_LINE:
        return "starmie"
    if ids & LUCARIO_LINE:
        return "lucario"
    if ids & ALAKAZAM_LINE:
        return "alakazam"
    return "generic"


_ALA_BOARD_GAIN = {66: 3, 742: 2, 305: 2, 65: 2, 741: 1}


def _estimate_alakazam_from_pokes(opp, pokes):
    # R-08 入力: 可変打点(Powerful Hand)の floor/ceiling 推定
    ids = [p.id for p in pokes if p]
    if not (ALAKAZAM_LINE & set(ids)):
        return 0, 0, 0
    base = opp.handCount + 1
    gain = sum(_ALA_BOARD_GAIN.get(i, 0) for i in ids)
    enriching_seen = (
        any(c and c.id == 13 for c in (opp.discard or []))
        or any(c and c.id == 13 for p in pokes if p for c in (getattr(p, "energyCards", None) or []))
    )
    if not enriching_seen:
        gain += 3
    if any(i == 140 for i in ids):
        gain += 3
    return base * 20, (base + gain + 2) * 20, (base + gain - 1) * 20


def _estimate_alakazam(obs):
    opp = opp_state(obs)
    pokes = ([opp.active[0]] if opp.active else []) + list(opp.bench or [])
    return _estimate_alakazam_from_pokes(opp, pokes)


def opp_max_damage(obs):
    # R-08 入力: マッチアップ別の相手最大打点テーブル（6月メタ由来。現メタ向け更新タスクあり）
    matchup = _T["matchup"]
    if matchup == "alakazam":
        _, ceiling, _ = _estimate_alakazam(obs)
        return ceiling
    if matchup == "crustle":
        return 120
    if matchup == "hop":
        return 220
    if matchup == "lucario":
        return 270
    if matchup == "starmie":
        return 210
    return 220


def judge_subgoal(obs):
    """S-0 サブゴール判定: ブリジュラスが技をうてる（場に Archaludon ex がいてエネ3枚以上）。
    フェーズはこの判定の現在値（状態を持たない → 全滅すれば自動でセットアップ期に戻る）。"""
    return any(p.id == ARCHALUDON_EX and energy_count(p) >= 3 for p in all_my_pokemon(obs))


def judge_lethal(obs):
    """R-07 リーサル判定（常時・閉形式）: この番で相手の残りサイドを取り切れるか。
    v1 の射程: 現在のアクティブ(または退却済みルート)の単発KO + ボス吊り出しKO。
    ばら撒き複数KO・退却込みの複合手は探索版(次版)で扱う。"""
    my_remaining = len(my_state(obs).prize)
    route = archaludon_ex_attack_route(obs)
    attacks = planned_archaludon_attacks(obs)
    if route is None or not attacks:
        return None
    needs_retreat = route["needs_retreat"]
    attacker = route["attacker"]
    # 経路1: アクティブ(または退却→前出し後)の攻撃で勝ち
    opp_act = opp_active_pokemon(obs)
    if opp_act and prize_value(opp_act) >= my_remaining:
        for atk in attacks:
            if guarded_damage(atk["damage"], atk["attacker"], opp_act) >= opp_act.hp:
                return {"route": "active", "attack_id": atk["attack_id"],
                        "attacker": attacker, "needs_retreat": needs_retreat}
    # 経路2: ボスで吊り出してKOで勝ち（サポート未使用 & ボスが手札）
    if BOSS in hand_ids(obs) and not obs.current.supporterPlayed:
        for target in opp_bench_pokemon(obs):
            if prize_value(target) < my_remaining:
                continue
            for atk in attacks:
                if guarded_damage(atk["damage"], atk["attacker"], target) >= target.hp:
                    return {"route": "boss", "target": target, "attack_id": atk["attack_id"],
                            "attacker": attacker, "needs_retreat": needs_retreat}
    return None


def judge_loss_threats(obs):
    """R-08 被リーサル判定（常時・閉形式・ボス想定）:
    「相手の手札にボスがある」前提で、次の相手番に取られると負ける自軍ポケモンの集合。
    ボス想定 → 露出はアクティブだけでなく全盤面。
    緩和: 相手トラッシュのボスが4枚（参照リスト基準の保守値）ならベンチ露出を解除。"""
    opp_remaining = len(opp_state(obs).prize)
    dmg = opp_max_damage(obs)
    if dmg <= 0:
        return []
    boss_used = sum(1 for c in (opp_state(obs).discard or []) if c and c.id == BOSS)
    boss_assumed = boss_used < 4  # R-08 緩和条件
    threats = []
    ps = my_state(obs)
    actives = [p for p in ps.active if p]
    for p in all_my_pokemon(obs):
        exposed = (p in actives) or boss_assumed
        if exposed and dmg >= p.hp and prize_value(p) >= opp_remaining:
            threats.append(p)
    return threats


# ═══════════════════════════════ 優先則（priors。スコア帯 = 行動順序 R-04） ═══════════════════════════════

def score_setup(obs, opt):
    card = option_card(obs, opt)
    cid = card.id if card else None
    ctx = obs.select.context

    if ctx == SelectContext.MULLIGAN:
        # R-22 暫定: 参照実装(1300+作者)と keidroid はともにマリガンNO。データ確認タスクあり
        return (10000, "R-22暫定: no mulligan") if opt.type == OptionType.NO else (0, "mulligan")
    if ctx == SelectContext.IS_FIRST:
        # R-21 暫定: 参照実装は後攻選択。上位ピロットのデータで要確認
        return (10000, "R-21暫定: choose second") if opt.type == OptionType.NO else (0, "go first")
    if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
        return _SETUP_ACTIVE_PRIORITY.get(cid, (0, "unknown Active"))
    if ctx == SelectContext.SETUP_BENCH_POKEMON:
        return -10000, "S-1: never bench during setup"
    return 0, "non-setup"


# E-3: 回復判定の閾値（グリッドサーチ実測値。Lucario=270 等）
_ICE_CREAM_HP_THRESHOLD = {
    "lucario": 270,
    "starmie": 210,
    "crustle": 120,
    "hop": 220,
    "generic": 230,
}


def should_skip_ice_cream(obs, active):
    """E-3 回復判定。R-08 の強制発動を先頭に追加:
    リーサルが無く、アクティブが「取られたら負け」圏で、回復すれば圏外に出るなら必ず使う。"""
    if active.id != ARCHALUDON_EX:
        return True, "skip Ice Cream: not Archaludon ex"

    # R-08: 負け筋を回復で切れるなら最優先（リーサル時はターン手順上こちらに来ない）
    if _T["lethal"] is None and any(p is active for p in _T["threats"]):
        ice_count = sum(1 for c in (my_state(obs).hand or []) if c and c.id == JUMBO_ICE_CREAM)
        max_hp = getattr(active, "maxHp", active.hp)
        hp_after = min(max_hp, active.hp + ice_count * 80)
        if hp_after > opp_max_damage(obs):
            return False, "R-08: heal breaks lethal threat"

    # E-3: Raging Hammer KO ガード（回復で自分のKOを消さない。220で取れるなら回復OK）
    opp_act = opp_active_pokemon(obs)
    if opp_act and has_in_play(obs, RELICANTH):
        md_kills = guarded_damage(220, active, opp_act) >= opp_act.hp
        if not md_kills:
            rh_dmg = 80 + damage_on(active) // 10 * 10
            rh_after = 80 + max(0, damage_on(active) - 80) // 10 * 10
            if (guarded_damage(rh_dmg, active, opp_act) >= opp_act.hp
                    and guarded_damage(rh_after, active, opp_act) < opp_act.hp):
                return True, "skip Ice Cream: healing loses Raging Hammer KO"

    # E-3: 対アラカザム all-or-nothing（floor/ceiling 比較）
    matchup = _T["matchup"]
    if matchup == "alakazam":
        floor, ceiling, _ = _estimate_alakazam(obs)
        opp_a = opp_active_pokemon(obs)
        attacks = planned_archaludon_attacks(obs)
        if opp_a and attacks and any(
                guarded_damage(a["damage"], a["attacker"], opp_a) >= opp_a.hp for a in attacks):
            _, ceiling, _ = _estimate_alakazam_from_pokes(opp_state(obs), opp_bench_pokemon(obs))
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


ITEMS = {POKE_PAD, ULTRA_BALL, POKEGEAR, NIGHT_STRETCHER, JUMBO_ICE_CREAM, HERO_CAPE}


def score_play(obs, opt):
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
            if not any(p.id in {ARCHALUDON_EX, DURALUDON} and not has_tool(p) for p in all_my_pokemon(obs)):
                return -500, "save Hero's Cape: no target"
        if cid == JUMBO_ICE_CREAM:
            active = active_pokemon(obs)
            if active:
                skip, reason = should_skip_ice_cream(obs, active)
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
            metal_in_trash = metal_in_discard(obs)
            if metal_in_trash == 0 and metal_in_hand >= 1:
                return 20000, "S-4/経路B: Ultra Ball fuel Alloy"
            if safe_discard_count(obs) >= 2 and (need_archaludon(obs) or need_duraludon(obs)):
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
        if BOSS in ids and planned_archaludon_attacks(obs):
            return -500, "save Lillie: Boss in hand with attacker ready"
        return 5000, "play Lillie"

    if cid == BOSS:
        # E-3 ボス多段: リーサルはターン手順が LETHAL_BAND に昇格済み。ここは温存/吊り出し/スタール
        if obs.current.supporterPlayed:
            return -1000, "Supporter already used"
        if _T["matchup"] == "hop":
            active = active_pokemon(obs)
            opp_has_snorlax = any(p.id == HOP_SNORLAX for p in opp_bench_pokemon(obs))
            if opp_has_snorlax and active:
                if active.id == CINDERACE:
                    has_dura_bench = any(p.id in {DURALUDON, ARCHALUDON_EX}
                                         for p in my_state(obs).bench if p)
                    if has_dura_bench:
                        return 16500, "E-3: Boss pull Snorlax (Cinderace Turbo Flare)"
                if active.id == ARCHALUDON_EX and active.hp > 220:
                    ok, _ = attack_energy_route(obs, active)
                    if ok:
                        return 16500, "E-3: Boss pull Snorlax (tank Revenge)"
        if _opp_last_attack_id == MEGA_BRAVE:
            return -500, "E-3: save Boss (Mega Brave stuck)"
        attacks = planned_archaludon_attacks(obs)
        if not attacks:
            return -500, "save Boss: no attacker"
        opp_act = opp_active_pokemon(obs)
        can_ko_active = opp_act and any(
            guarded_damage(atk["damage"], atk["attacker"], opp_act) >= opp_act.hp for atk in attacks)
        remaining = len(my_state(obs).prize)
        if can_ko_active:
            return -500, "save Boss: can KO Active"
        best_score = -500
        best_reason = "save Boss"
        for target in opp_bench_pokemon(obs):
            for atk in attacks:
                if guarded_damage(atk["damage"], atk["attacker"], target) >= target.hp:
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
                best_stall = -500
                stall_reason = "save Boss"
                for target in opp_bench_pokemon(obs):
                    te = energy_count(target)
                    cd = CARD_DB.get(target.id)
                    rc = cd.retreatCost if cd else 0
                    min_atk = 99
                    if cd and cd.attacks:
                        for aid in cd.attacks:
                            atk = ALL_ATTACKS.get(aid)
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


def score_evolve(obs, opt):
    # S-4: 進化は Assemble Alloy の弾（トラッシュの鋼エネ）と連動
    card = option_card(obs, opt)
    target = option_target(obs, opt)
    cid = card.id if card else None
    tid = target.id if target else None
    if cid == ARCHALUDON_EX and tid == DURALUDON:
        target_is_active = opt.inPlayArea == AreaType.ACTIVE
        mc = metal_in_discard(obs)
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


def attach_target_score(obs, target, area):
    # S-2/S-5: エネはジュラルドン系統へ集約。e>=3 は付けない（R-10 相当の過剰付与マスク:
    # Metal Defender コスト3枚由来。スコア -5000 で事実上ハード）
    if target is None:
        return 0
    cid = target.id
    e = energy_count(target)

    if e >= 3:
        return -5000
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

    # R-08: 「取られたら負け」圏のポケモンにエネを注ぎ足さない（負け筋への追い銭防止）
    if any(p is target for p in _T["threats"]):
        score -= 2000
    return score


def score_attach(obs, opt):
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

    return attach_target_score(obs, target, opt.inPlayArea), "S-5: attach Metal"


def score_retreat(obs, opt):
    active = active_pokemon(obs)
    if active and active.id == ARCHALUDON_EX and has_tool(active) and active.hp > 200:
        return -5000, "don't retreat HP400 tank"
    route = archaludon_ex_attack_route(obs)
    if route and route["needs_retreat"]:
        return 13000, "retreat to attack-ready ex"
    return -100, "avoid retreat"


def score_to_hand(obs, opt):
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
            if getattr(opt, 'index', 0) == _first_option_index(obs, METAL_ENERGY):
                return 25000, "Explorer: take 1st energy"
            return 0, "Explorer: skip 2nd energy"
        if cid == ARCHALUDON_EX and need_archaludon(obs):
            return 20000, "Explorer: take Archaludon ex"
        if cid == DURALUDON and need_duraludon(obs):
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
    if cid == ARCHALUDON_EX and need_archaludon(obs):
        return 20000, "take Archaludon ex"
    if cid == DURALUDON and need_duraludon(obs):
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


def score_discard(obs, opt):
    # R-13: 勝ち筋ライン(ブリジュラス/ジュラルドン)をハード保護、余剰エネ・重複から捨てる
    card = option_card(obs, opt)
    cid = card.id if card else opt.cardId
    ids = hand_ids(obs)
    mt = metal_in_discard(obs)
    effect = getattr(obs.select, "effect", None)
    effect_id = effect.id if effect else None

    if effect_id == ULTRA_BALL:
        mh = ids.count(METAL_ENERGY)
        if cid == METAL_ENERGY:
            if mt < 2 and mh >= 1:
                if getattr(opt, 'index', None) == _first_option_index(obs, METAL_ENERGY):
                    return 20000, "S-4: UB discard 1st Metal (fuel Alloy)"
                return 8000, "UB: 2nd Metal"
            return 8000, "UB: Metal"
        if cid == CINDERACE:
            return (18000, "UB: Cinderace") if (mt >= 2 or mh == 0) else (14000, "UB: Cinderace")
        draw_count = ids.count(LILLIE) + ids.count(EXPLORER)
        if cid in (LILLIE, EXPLORER) and draw_count >= 2:
            return (12000 if cid == LILLIE else 11000), "UB: surplus supporter"
        if cid == ULTRA_BALL and ids.count(ULTRA_BALL) > 1:
            return 10000, "UB: duplicate"
        if cid in (LILLIE, EXPLORER) and draw_count <= 1:
            return -3000, "UB: keep last supporter"

    if cid == METAL_ENERGY:
        if mt < 2:
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


def score_target(obs, opt):
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
        return attach_target_score(obs, card, opt.area), "S-2: effect attach"

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
            if _T["matchup"] == "hop" and cid == HOP_SNORLAX and card:
                active = active_pokemon(obs)
                e = energy_count(card)
                tools = len(getattr(card, 'tools', None) or [])
                if active and active.id == CINDERACE:
                    return 30000 - e * 100 - tools * 50 + card.hp, "E-3: Boss Snorlax (immobile)"
                return 30000 + e * 100 + tools * 50 + card.hp, "E-3: Boss Snorlax (biggest threat)"
            pv = prize_value(card)
            te = energy_count(card)
            killable = any(guarded_damage(a["damage"], a["attacker"], card) >= card.hp
                           for a in planned_archaludon_attacks(obs))
            if killable:
                return 20000 + pv * 3000 + te * 100, "E-3: Boss KO"
            return 5000 + pv * 1000 + te * 200, "E-3: Boss drag"
        # 自分側 = 前に出すポケモンの選択
        score, reason = 1000, "generic promote"
        if cid == CINDERACE:
            score, reason = 16000, "promote Cinderace (retreat 0)"
        elif cid == ARCHALUDON_EX:
            score, reason = 15000, "promote Archaludon ex"
        elif cid == DURALUDON:
            score, reason = 8000, "promote Duraludon"
        # R-08 マスク: 「取られたら負け」圏の個体は前に出さない（代替が無ければ
        # choose_options の minCount 充足で自動的に least-bad へ緩和 = 辞書式）
        if card is not None and any(p is card for p in _T["threats"]):
            return score - 15000, f"R-08: avoid promoting game-losing piece ({reason})"
        return score, reason

    if ctx == SelectContext.DAMAGE:
        # R-15: スナイプは低HP優先（エンジン駒潰し）
        hp = getattr(card, "hp", 999) if card else 999
        return 10000 - hp, "R-15: damage lowest HP"

    return 1000, "generic target"


# ═══════════════════════════════ マッチアップ上書き（E-3: 基礎スコア + 差分の2層） ═══════════════════════════════

def apply_overrides(obs, opt, score, reason):
    # R-11 系: 山札が薄い時のドロー封印
    if opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        cid = card.id if card else None
        if my_state(obs).deckCount <= 10 and cid == EXPLORER:
            return -5000, "R-11: don't Explorer with low deck"

    if _T["matchup"] != "crustle":
        return score, reason

    # クラッスル上書き（ex からのダメージ無効への対応一式）
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


# ═══════════════════════════════ ターン手順（protocol。判定 → 昇格/マスク の辞書式適用） ═══════════════════════════════

def apply_protocol(obs, opt, score, reason):
    """用語とターン手順.md のターン手順 1（リーサル）を優先則より上の帯へ昇格させる。
    手順 2（負け筋カット）のマスクは各優先則の中でタグ [R-08] 付きで適用済み。"""
    lethal = _T["lethal"]
    if lethal is None:
        return score, reason
    ctx = obs.select.context
    yi = obs.current.yourIndex

    # R-07: リーサル手を LETHAL_BAND に昇格（他の全優先則より上）
    if opt.type == OptionType.ATTACK and getattr(opt, 'attackId', None) == lethal["attack_id"]:
        return LETHAL_BAND, "R-07: LETHAL attack"
    if lethal["route"] == "boss" and opt.type == OptionType.PLAY:
        card = option_card(obs, opt)
        if card and card.id == BOSS:
            return LETHAL_BAND, "R-07: LETHAL Boss"
    if lethal["route"] == "boss" and ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE}:
        if getattr(opt, 'playerIndex', yi) != yi:
            card = option_card(obs, opt)
            if card is not None and card is lethal["target"]:
                return LETHAL_BAND, "R-07: LETHAL Boss target"

    # R-07: 退却はリーサル計画の一部か否かで扱いを分ける
    if lethal["needs_retreat"]:
        # 計画がベンチのアタッカー前提 → 退却と、そのアタッカーの前出しも計画の一部として昇格
        if opt.type == OptionType.RETREAT:
            return LETHAL_BAND - 1, "R-07: LETHAL retreat (bench attacker plan)"
        if ctx in {SelectContext.SWITCH, SelectContext.TO_ACTIVE} and getattr(opt, 'playerIndex', yi) == yi:
            card = option_card(obs, opt)
            if card is not None and card is lethal["attacker"]:
                return LETHAL_BAND - 1, "R-07: LETHAL promote attacker"
    else:
        # アクティブで勝てる計画 → 退却は計画を壊すのでマスク
        if opt.type == OptionType.RETREAT:
            return -100000, "R-07: don't break lethal (no retreat)"
    return score, reason


def score_option(obs, opt):
    ctx = obs.select.context

    if ctx in {SelectContext.IS_FIRST, SelectContext.MULLIGAN,
               SelectContext.SETUP_ACTIVE_POKEMON, SelectContext.SETUP_BENCH_POKEMON}:
        return score_setup(obs, opt)

    if opt.type in {OptionType.YES, OptionType.NO}:
        if ctx == SelectContext.ACTIVATE:
            # S-1 経路A: Explosiveness は常に使う
            return (100000, "S-1: Explosiveness") if opt.type == OptionType.YES else (-100000, "never decline")
        return (1, "yes") if opt.type == OptionType.YES else (0, "no")

    if opt.type == OptionType.NUMBER:
        return (opt.number or 0), "number"

    if ctx == SelectContext.MAIN:
        # R-04: スコア帯 = ターン内の行動順序（ワザは最後 = ターンを終わらせる行動）
        if opt.type == OptionType.PLAY:
            score, reason = score_play(obs, opt)
        elif opt.type == OptionType.EVOLVE:
            score, reason = score_evolve(obs, opt)
        elif opt.type == OptionType.ATTACH:
            score, reason = score_attach(obs, opt)
        elif opt.type == OptionType.RETREAT:
            score, reason = score_retreat(obs, opt)
        elif opt.type == OptionType.ABILITY:
            score, reason = 1, "ability"
        elif opt.type == OptionType.ATTACK:
            score, reason = best_attack_damage(obs, opt.attackId), "E-2: attack"
        elif opt.type == OptionType.END:
            score, reason = 0, "end turn"
        else:
            score, reason = 500, "generic MAIN"
    elif ctx == SelectContext.TO_HAND:
        score, reason = score_to_hand(obs, opt)
    elif ctx in {SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD}:
        score, reason = score_discard(obs, opt)
    elif ctx in {SelectContext.ATTACH_TO, SelectContext.TO_FIELD, SelectContext.TO_BENCH,
                 SelectContext.ATTACH_FROM, SelectContext.SWITCH, SelectContext.TO_ACTIVE,
                 SelectContext.HEAL, SelectContext.DAMAGE}:
        score, reason = score_target(obs, opt)
    elif ctx == SelectContext.ATTACK:
        score, reason = best_attack_damage(obs, opt.attackId), "E-2: attack"
    elif opt.type == OptionType.CARD:
        score, reason = score_to_hand(obs, opt)
    elif opt.type == OptionType.ENERGY:
        score, reason = 1000, "energy"
    elif opt.type == OptionType.END:
        score, reason = 0, "end"
    else:
        score, reason = 100, "fallback"

    score, reason = apply_overrides(obs, opt, score, reason)   # E-3: マッチアップ上書き
    return apply_protocol(obs, opt, score, reason)             # R-07: リーサル昇格


# ═══════════════════════════════ 選択と安全ラッパー ═══════════════════════════════

def choose_options(obs):
    # 判定は毎手番・常時実行（用語とターン手順.md: 判定は安いので常時、反応をフェーズで変える）
    _T["matchup"] = detect_matchup(obs)                        # R-20
    _T["phase"] = "combat" if judge_subgoal(obs) else "setup"  # S-0
    _T["lethal"] = judge_lethal(obs)                           # R-07
    _T["threats"] = judge_loss_threats(obs)                    # R-08

    scored = []
    for i, opt in enumerate(obs.select.option):
        try:
            score, reason = score_option(obs, opt)
        except Exception as e:
            score, reason = -999999, f"error {type(e).__name__}: {e}"
        scored.append((score, i, reason))

    scored.sort(key=lambda x: (x[0], -x[1]), reverse=True)

    # 負スコア = minCount 超過分では選ばない（マスクの表現）
    selected = []
    for score, i, reason in scored:
        if len(selected) >= obs.select.maxCount:
            break
        if score < 0 and len(selected) >= obs.select.minCount:
            continue
        selected.append(i)

    if len(selected) < obs.select.minCount:
        selected = [i for _, i, _ in scored[:obs.select.minCount]]

    return selected


def _legal_fallback(obs_dict):
    # R-01/R-02: 例外時は決定的な合法手（先頭 minCount 個）
    try:
        sel = obs_dict.get("select") or {}
        n = len(sel.get("option") or [])
        return list(range(min(max(0, sel.get("minCount", 0)), n)))
    except Exception:
        return []


def agent(obs_dict):
    # R-01: 例外 = 敗北。全体を包み、必ず合法手を返す
    try:
        obs = to_observation_class(obs_dict)
        if obs.select is None:
            global _opp_last_attack_id, _cur_turn_logs
            _opp_last_attack_id = None
            _cur_turn_logs.clear()
            return read_deck_csv()
        _update_opp_attack_tracking(obs)
        if not obs.select.option:
            return []
        return choose_options(obs)
    except Exception:
        return _legal_fallback(obs_dict)
