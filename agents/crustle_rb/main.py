"""イワパレス壁ガルーラ（Crustle Wall + Mega Kangaskhan）ルールベース — フルスクラッチ

7/14メタのシェア2位ファミリー（イワパレス族 24%、うち壁ガルーラ型が主流）。
設計文書: docs/planning/デッキ設計_イワパレス.md（C-x 実測ドクトリン/E-x/未決事項）。
リスト = 系統B（懒惰的金枪鱼 1174.5 / MPGaming 最頻。decks/fleet/crustle_wall_top.csv）。

コンセプト:
  高耐久壁（イワパレス 150+20/+100・メガガルーラ 300/+100）を Switch で回し、
  ジャンボアイス80回復で打点レースを破綻させ、ゼロシキで相手の手札（特にフーディンの
  Powerful Hand = 手札×20）を潰す。イワパレスの特性 Mysterious Rock Inn は相手 ex/megaEx の
  技ダメージを無効（対 ex はほぼ詰み盤面を作れる）。打点は Superb Scissors 120（効果無視）と
  Rapid-Fire Combo 200。ガルーラは前にいる間 Run Errand 2ドロー/番のエンジンを兼ねる。
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
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    attack_cost,
    damage_on,
    energy_count,
    get_card,
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

# ── カードID（デッキ設計_イワパレス.md のリスト） ──

DWEBBLE = 344         # イシズマイ HP70（Ascension: 山から進化を乗せる）
CRUSTLE = 345         # イワパレス HP150（特性: 相手 ex/megaEx の技ダメージ無効）
KANGA = 756           # メガガルーラex HP300 megaEx（Run Errand: バトル場で2ドロー）
SHAYMIN = 343         # シェイミ HP80（系統Aのみ。特性: 非ルールボックスのベンチ保護）

G_ENERGY = 1          # 基本草
MIST = 11             # ミストエネルギー（技の効果無効。{C}供給）
SPIKY = 14            # とげとげエネルギー（殴った相手にダメカン2。{C}供給）
GROW = 18             # すくすくグラスエネルギー（{G}供給 + HP+20）

POFFIN = 1086         # なかよしポフィン（HP70以下のたね×2をベンチへ）
HAND_TRIMMER = 1087   # ハンドトリマー（お互い手札5枚まで捨てる。相手が先）
POKEGEAR = 1122       # ポケギア3.0（山上7枚からサポート）
SWITCH_ITEM = 1123    # 入れ替え
JUMBO = 1147          # ジャンボアイス（エネ3枚以上のアクティブを80回復）
HERO_CAPE = 1159      # ヒーローマント（ACE SPEC: +100HP）
XEROSIC = 1197        # ゼロシキ（相手手札を3枚に）
HILDA = 1225          # ヒルダ（進化+エネのサーチ）
LILLIE = 1227         # リーリエの決心（手札を山へ戻して6ドロー）
BATTLE_CAGE = 1264    # バトルケージ（ベンチへのダメカン配置無効）

ATK_ASCENSION = 478   # Dwebble {C} 0点（山から進化）
ATK_SCISSORS = 479    # Crustle {G}{C}{C} 120（相手バトル場への効果を無視）
ATK_RAPID_FIRE = 1092  # Kanga {C}{C}{C} 200+コイン×50
ATK_SMASH_KICK = 477  # Shaymin {C}{C} 30

WALL_IDS = {CRUSTLE, KANGA}
POKEMON_IDS = {DWEBBLE, CRUSTLE, KANGA, SHAYMIN}
ALL_ENERGY = {G_ENERGY, MIST, SPIKY, GROW}
G_PROVIDERS = {G_ENERGY, GROW}      # Superb Scissors の {G} を払えるエネ

# ── CR1: 「相手バトル場への効果を無視」する技（エンジン実測 2026-07-14: これらは
#    イワパレスの Mysterious Rock Inn を貫通する。診断: Nebula Beam が Crustle を21回削り
#    被KO 63回/23敗 = 対メガスターミー 22.5% の主因）。EN_Card_Data 全走査で列挙。 ──
PIERCE_ATTACK_IDS = {70, 148, 207, 316, 426, 479, 837, 901, 1226, 1305, 1488}
NEUTRAL_ZONE = 1247   # 相手スタジアム: ex/V → 非ルールボックスへのダメージ無効（CR2 で参照）

# ルールトグル（P-12 の A/B 用）
CR1 = os.environ.get("CRUSTLE_CR1", "1") != "0"   # 貫通ex対策（壁をガルーラへ切替）採用
CR2 = os.environ.get("CRUSTLE_CR2", "1") != "0"   # 対LO 山札規律 + NZ ダメージモデル 採用
# CR3【棄却 2026-07-15】: 壁切替を「場に壁で受けられる ex」へ広げる先回り。
# A/B 80戦: dragapult +6.2 / alakazam +1.2 / garchomp −10.0（ガブは非exアタッカーに
# 回されるとガルーラのドローを失うだけ）→ ネット±0 で不採用（既定 OFF）
CR3 = os.environ.get("CRUSTLE_CR3", "0") != "0"


def _energy_types(pokemon):
    """ポケモンに付いたエネのタイプ一覧（特殊エネも CARD_DB.energyType で解決。
    Mist/Spiky=COLORLESS(0)、Grow/基本草=GRASS(1)。cg 実測確認済み 2026-07-14）。"""
    cards = getattr(pokemon, "energyCards", None) or []
    types = []
    for ec in cards:
        d = CARD_DB.get(ec.id)
        types.append(getattr(d, "energyType", 0) if d else 0)
    if not types:
        types = list(getattr(pokemon, "energies", []) or [])
    return types


def _can_pay_colored(pokemon, attack_id):
    """色を見るコスト判定（Superb Scissors {G}CC は Grow/基本草が必須）。"""
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


class CrustleWallPolicy(BasePolicy):
    DECK_NAME = "crustle_wall"
    GO_FIRST = True            # C-1【ハード・R-21確定】上位10チーム 116/116 で先攻
    TAKE_MULLIGAN = True       # C-16/R-22【ハード・プロジェクト共通】（機会の実測データなし）
    ATTACKER_IDS = WALL_IDS
    ENERGY_IDS = ALL_ENERGY    # R-26 手張り先行が参照（特殊エネ3種を必ず含める）
    LINE_PROTECT_IDS = {DWEBBLE, CRUSTLE, HERO_CAPE}   # R-13

    def __init__(self):
        super().__init__()
        self.p = {}

    # ═══════════════ ターン分析（軽量: 枚数と旗だけ） ═══════════════

    def choose(self, obs):
        self.p = self._analyze(obs)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        opp = opp_state(obs)
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
        bench = [b for b in ms.bench if b]
        stadium_id = 0
        for c in obs.current.stadium:
            stadium_id = c.id
        my_prizes = len(ms.prize)
        safe_draws = ms.deckCount - my_prizes - 1     # R-11
        opp_pokes = [p for p in (opp.active + opp.bench) if p]
        opp_has_ex = any(is_ex(p) for p in opp_pokes)
        opp_act = opp.active[0] if opp.active else None
        # CR1: 相手の場に「イワパレスを一撃で抜く貫通技を持つ ex」がいるか。
        # 貫通でも打点がイワパレス実効HP(150+すくすく20=170)未満（デモリッシュ140等)なら
        # ジャンボ80回復の壁サイクルが受け切る → 発火しない（A/B 実測 2026-07-14:
        # 広い条件はプリズム型 62.5→31.2% の大惨事。狭めて再計測）
        opp_pierce_ex = any(
            is_ex(p) and any(aid in PIERCE_ATTACK_IDS and attack_base_damage(aid) >= 170
                             for aid in (getattr(CARD_DB.get(p.id), "attacks", None) or []))
            for p in opp_pokes)
        # CR3: 「イワパレス壁が受け止められる ex アタッカー」が相手の場にいるか。
        # 非貫通・基礎打点120以上の ex に限定（キチキギスex 100 のようなサポート駒への
        # 誤発火で、対フーディンのドロー役ガルーラを下げないため）
        opp_wallable_ex = any(
            is_ex(p) and any(aid not in PIERCE_ATTACK_IDS and attack_base_damage(aid) >= 120
                             for aid in (getattr(CARD_DB.get(p.id), "attacks", None) or []))
            for p in opp_pokes)
        # 山に残る進化ライン（Ascension/ポフィン/ヒルダの空振りガード）
        # 場のイワパレスは下にイシズマイを1枚ずつ消費している
        dwebble_used = fc[DWEBBLE] + fc[CRUSTLE] + hc[DWEBBLE] + dc[DWEBBLE]
        crustle_used = fc[CRUSTLE] + hc[CRUSTLE] + dc[CRUSTLE]
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "bench_n": len(bench),
            "bench_empty": len(bench) == 0,
            "stadium_id": stadium_id, "safe_draws": safe_draws,
            "opp_hand": opp.handCount, "opp_prizes": len(opp.prize),
            "my_prizes": my_prizes,
            "opp_has_ex": opp_has_ex,
            "opp_active_is_ex": is_ex(opp_act) if opp_act is not None else False,
            "opp_has_munki": any(p.id == 112 for p in opp_pokes),
            "opp_pierce_ex": opp_pierce_ex if CR1 else False,
            "opp_wallable_ex": opp_wallable_ex,
            "dwebble_in_deck": max(0, 4 - dwebble_used),
            "crustle_in_deck": max(0, 4 - crustle_used),
            "hand_energy": sum(hc[e] for e in ALL_ENERGY),
        }

    def _is_lo(self):
        """CR2: 相手が LO（山札切れ狙い）アーキタイプか（R-20 検出値）。"""
        return CR2 and self.t.get("matchup") in mt.LO_ARCHETYPES

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場の壁（イワパレス/ガルーラ）のどれかにエネ3枚以上
        （= 技が払え、ジャンボアイスが生きる = 壁完成）。"""
        return any(p.id in WALL_IDS and energy_count(p) >= 3
                   for p in all_my_pokemon(obs))

    def attack_damage(self, obs, attacker, attack_id):
        if attack_id == ATK_RAPID_FIRE:
            return 200                    # E-4: 保証値200（コインの+50nは上振れ扱い）
        return super().attack_damage(obs, attacker, attack_id)

    def guard_damage(self, base_damage, attacker, target):
        """弱点をアタッカー毎のタイプで計算（Crustle={G} / Kanga={C}）。
        ミラーの相手イワパレスへの ex 打点無効は基盤の IMMUNE_TO_EX_ACTIVE 判定を踏襲。"""
        if target is not None and target.id in mt.IMMUNE_TO_EX_ACTIVE and is_ex(attacker):
            return 0
        # CR2: ニュートラルゾーン下では ex → 非ルールボックスのダメージが0
        # （対シャンデラで自軍ガルーラの空振りリーサル誤検出を防ぐ）
        if (CR2 and self.p.get("stadium_id") == NEUTRAL_ZONE
                and is_ex(attacker) and target is not None and not is_ex(target)):
            return 0
        data = CARD_DB.get(attacker.id) if attacker is not None else None
        atype = getattr(data, "energyType", None) if data else None
        wv = weakness_value(target)
        if wv is not None and atype is not None and atype != 0 and wv == atype:
            return base_damage * 2
        return base_damage

    def plan_attacks(self, obs):
        """色を見るコスト判定版（Superb Scissors の {G} 必須を正しく扱う）。"""
        plans = []
        active = active_pokemon(obs)
        if active is not None:
            for aid in (CARD_DB.get(active.id).attacks if active.id in CARD_DB else []):
                if _can_pay_colored(active, aid):
                    plans.append(AttackPlan(active, aid, self.attack_damage(obs, active, aid)))
        # ベンチ: にげるが払えて未退却なら計画候補（実運用は Switch。リーサル判定用）
        if (active is not None and not obs.current.retreated
                and energy_count(active) >= retreat_cost(active)):
            for pk in my_state(obs).bench:
                if pk is None or pk.id not in WALL_IDS:
                    continue
                for aid in (CARD_DB.get(pk.id).attacks if pk.id in CARD_DB else []):
                    if _can_pay_colored(pk, aid):
                        plans.append(AttackPlan(pk, aid, self.attack_damage(obs, pk, aid),
                                                needs_retreat=True))
        return plans

    # ═══════════════ セットアップコンテキスト（C-2/C-3） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # C-2 実測（SETUP_ACTIVE: Kanga 105 > Dwebble 79 > Shaymin 11）
            table = {KANGA: 20, DWEBBLE: 12, SHAYMIN: 5}
            return table.get(cid, 0), "C-2: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # C-3 実測: 出せるたねはほぼ全部出す（73/80 で最大数選択。ガルーラ div-K1 と逆）
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {DWEBBLE: 10000, KANGA: 9000, SHAYMIN: 8000}
            return table.get(cid, 500), "C-3: bench during setup"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_number(self, obs, opt):
        # R-11: ドロー枚数の選択は山札切れガード内で最大
        n = opt.number or 0
        if obs.select.context == SelectContext.DRAW_COUNT and n > self._safe_draws():
            return -1000 - n, "R-11: cap draw count"
        return n, "number"

    # ═══════════════ 優先則（純粋フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        yi = obs.current.yourIndex

        # ── ABILITY 帯（R-04 最上位） ──
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == KANGA:
                # CR2: 対LOでは任意ドローが自傷（診断: 対シャンデラの負け18中14が
                # サイド0のまま山切れ）。山に余裕がある序盤だけ回す
                if self._is_lo() and self._safe_draws() < 15:
                    return -1, "CR2: decline Run Errand vs LO"
                # C-14: Run Errand は撃てる番の76%で発動（R-11 山薄ガードのみ）
                if self._safe_draws() >= 2:
                    return 29000, "C-14: Run Errand (draw 2)"
                return -1, "R-11: deck thin (Run Errand)"
            if cid in POKEMON_IDS:
                return 26000, "generic own ability"
            return -1, "skip foreign ability"

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            if card is not None and card.id == CRUSTLE:
                target = option_target(obs, opt)
                e = energy_count(target) if target is not None else 0
                # C-5: 手貼り進化が85%・T2 最頻。エネの乗った個体を先に壁化
                return 25000 + e * 100, "C-5: evolve Crustle"
            return 18000, "evolve other"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.RETREAT:
            # CR2: 拘束破り — 前が攻撃不能・手札に入れ替え無し・控えに壁がいるなら
            # エネを払ってでもにげる（対シャンデラのボス拘束→ミル負けの解毒）。
            # LO 対面限定（v1.1 で全対面発火になっており、対フーディン 63.7→53.8 の
            # 劣化容疑 → v1.1.1 で限定し A/B）
            active = active_pokemon(obs)
            if (self._is_lo() and active is not None
                    and not any(_can_pay_colored(active, aid)
                                for aid in (getattr(CARD_DB.get(active.id), "attacks", None) or []))
                    and self.p["hc"][SWITCH_ITEM] == 0
                    and any(pk.id in WALL_IDS for pk in my_state(obs).bench if pk)):
                return 3000, "CR2: retreat to break stall lock"
            # C-7: にげる宣言はしない（189回 Switch vs 25回。にげ3は資源損）
            return -5000, "C-7: never retreat (use Switch)"

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
            # C-3/C-12: 壁デッキはベンチを絞らない（ただし同名の重ね置きは軽く減点）
            if cid == DWEBBLE:
                score, reason = 20500 - fc[DWEBBLE] * 200, "C-3: bench Dwebble (wall line)"
            elif cid == KANGA:
                score, reason = 20200 - fc[KANGA] * 300, "C-3: bench Kangaskhan (engine/wall)"
            elif cid == SHAYMIN:
                score, reason = (19800 if fc[SHAYMIN] == 0 else 1000), "C-3: bench Shaymin"
            else:
                score, reason = 1000, "bench other"
            if p["bench_empty"]:
                score = max(score, 15000) + 5000
                reason = f"R-03: bench empty ({reason})"
            return score, reason

        # どうぐ（ヒーローマント。付け先の文脈は ATTACH/TO_FIELD 側）
        if data is not None and data.cardType == CardType.TOOL:
            if cid == HERO_CAPE:
                bare_wall = any(pk.id in WALL_IDS and not has_tool(pk)
                                for pk in all_my_pokemon(obs))
                if bare_wall:
                    return 13500, "C-15: Hero's Cape on wall"
                return -1, "save Hero's Cape"
            return -1, "hold tool"

        # スタジアム
        if cid == BATTLE_CAGE:
            if p["stadium_id"] == BATTLE_CAGE:
                return -1, "Battle Cage already up"
            if p["opp_has_munki"] or self.t["matchup"] in ("dragapult", "marnie"):
                return 19000, "E-1: Battle Cage (bench protection)"
            if p["stadium_id"] != 0:
                return 15000, "Battle Cage (stadium war)"
            return -1, "hold Battle Cage"

        # グッズ
        if cid == POFFIN:
            if self._is_lo() and p["fc"][DWEBBLE] + p["fc"][CRUSTLE] >= 2:
                return -1, "CR2: hold Poffin vs LO (deck = clock)"
            if p["dwebble_in_deck"] >= 1 and p["bench_n"] < my_state(obs).benchMax:
                return 18000, "C-3: Poffin (fetch Dwebble)"
            return -1, "Poffin: no target in deck"
        if cid == POKEGEAR:
            if self._is_lo() and my_state(obs).deckCount <= 25:
                return -1, "CR2: hold Pokegear vs LO (deck = clock)"
            return 14500, "Pokegear (dig supporter)"
        if cid == JUMBO:
            active = active_pokemon(obs)
            if active is None or energy_count(active) < 3:
                return -1, "Jumbo: needs 3-energy active"
            dmg = damage_on(active)
            if dmg >= 80:
                return 16000, "C-6/E-2: Jumbo Ice Cream (heal 80)"
            if dmg >= 50 and self.is_threatened(active):
                return 15500, "E-2: Jumbo (escape KO range)"
            return -1, "C-6: hold Jumbo (damage < 80)"
        if cid == SWITCH_ITEM:
            return self._score_switch_item(obs)
        if cid == HAND_TRIMMER:
            # E-3: 自傷なし（自分5枚以下）かつ相手手札が太い時だけ
            if p["opp_hand"] >= 7 and p["hand_size"] <= 5:
                return 12500, "E-3: Hand Trimmer (opp hand tax)"
            return -1, "hold Hand Trimmer"

        # サポート（択一）
        if data is not None and data.cardType == CardType.SUPPORTER:
            if obs.current.supporterPlayed:
                return -1, "Supporter already used"
            if cid == XEROSIC:
                # C-8: 相手手札の単調カーブ（6+で74-86%）。対フーディンは Powerful Hand
                # 直接減衰なので 4 枚から最優先（シャンデラ E-3 と同型）
                if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                    return 16900, "C-8: Xerosic vs Alakazam (cap Powerful Hand)"
                if p["opp_hand"] >= 6:
                    return 16800, "C-8: Xerosic (big hand)"
                if p["opp_hand"] >= 4 and combat:
                    return 5000, "C-8: Xerosic (mid hand)"
                return -1, "save Xerosic"
            if cid == HILDA:
                if (fc[CRUSTLE] < 2 and hc[CRUSTLE] == 0
                        and p["crustle_in_deck"] >= 1):
                    return 15800, "C-10: Hilda (fetch Crustle)"
                if p["hand_energy"] == 0 and any(
                        pk.id in WALL_IDS and energy_count(pk) < 3
                        for pk in all_my_pokemon(obs)):
                    return 15500, "C-10: Hilda (fetch energy)"
                return 4000, "Hilda (stock)"
            if cid == LILLIE:
                # R-11 近似ガード: 手札を山に戻して6ドロー後も山が細りすぎない
                ms = my_state(obs)
                if ms.deckCount + p["hand_size"] < 10:
                    return -1, "R-11: deck too thin for Lillie"
                # CR2: 対LOではリーリエ=山の回復装置（手札9枚以上でだけ打つと山が净増える）
                if self._is_lo():
                    if p["hand_size"] >= 9:
                        return 15200, "CR2: Lillie (deck recovery vs LO)"
                    return -1, "CR2: hoard hand vs LO"
                if p["hand_size"] <= 8:
                    return 15200, "C-9: Lillie (refresh)"
                return 4200, "C-9: Lillie (fat hand, hold)"
            if cid == mt.BOSS:
                return self._score_boss(obs, combat)
            return 1000, "generic supporter"

        return 1000, "generic play"

    def _score_switch_item(self, obs):
        """E-1 壁ローテ: Switch の発火条件（C-7: にげるの代わりに Switch を使う）。"""
        p = self.p
        active = active_pokemon(obs)
        if active is None:
            return -1, "no active"
        bench = [pk for pk in my_state(obs).bench if pk]
        bench_crustle = [pk for pk in bench if pk.id == CRUSTLE]
        bench_wall = [pk for pk in bench if pk.id in WALL_IDS]
        bench_kanga = [pk for pk in bench if pk.id == KANGA]
        # 前が壁でない（イシズマイ/シェイミが晒されている）→ 壁を立てる
        if active.id not in WALL_IDS and bench_wall:
            return 11000, "E-1: Switch fodder out, wall in"
        # CR1: 貫通ex（ネビュラビーム等）相手はイワパレス免疫が効かない →
        # 前のイワパレス(170)をガルーラ(300+マント)に差し替えて受ける
        if (p["opp_pierce_ex"] and active.id == CRUSTLE and bench_kanga):
            return 11000, "CR1: Kanga tank vs pierce ex"
        # 相手が ex 主体で前がガルーラ → イワパレス（ex 打点無効）に交代
        # （CR3: 条件を「相手バトル場が ex」から「相手の場に壁で受けられる ex アタッカー
        #  （非貫通・打点120+）がいる」へ拡大。ドラパルトがベンチで育つ間に先回りして
        #  壁を立てる。キチキギスex等のサポート駒には発火しない。貫通ex相手は除外）
        opp_ex_cond = (p["opp_wallable_ex"] if CR3 else p["opp_active_is_ex"])
        if (active.id == KANGA and opp_ex_cond and not p["opp_pierce_ex"]
                and bench_crustle):
            return 11000, "E-1: Switch to Crustle vs ex"
        # 前の壁が大破（ジャンボ圏外）で控えの壁が育っている → ローテ
        if (active.id in WALL_IDS and damage_on(active) >= 120
                and p["hc"][JUMBO] == 0
                and any(energy_count(pk) >= 3 for pk in bench_wall)):
            return 10500, "E-1: rotate broken wall"
        return -1, "hold Switch"

    def _score_boss(self, obs, combat):
        """C-11: ボスは温存気味（使用率13%）。スナイプ（低HPシステム札の取り切り）か
        拘束（エネ0・にげ重の吊り出し）が成立する時だけ。リーサルは基盤 R-07 が昇格する。"""
        if not combat:
            return -1, "save Boss (setup)"
        plans = self.plan_attacks(obs)
        max_dmg = max((pl.damage for pl in plans if not pl.needs_retreat), default=0)
        targets = opp_bench_pokemon(obs)
        if not targets:
            return -1, "Boss: no bench target"
        if max_dmg > 0 and any(
                self.guard_damage(max_dmg, active_pokemon(obs), t) >= t.hp for t in targets):
            return 5200, "C-11: Boss (snipe engine piece)"
        if any(energy_count(t) == 0 and retreat_cost(t) >= 2 for t in targets):
            return 4700, "C-11: Boss (stall lock)"
        return -1, "save Boss"

    # ── ATTACH（C-4 エネ張り分け + R-10） ──

    def _score_attach(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id
        data = CARD_DB.get(cid)
        # どうぐ（ヒーローマント）の付け先
        if data is not None and data.cardType == CardType.TOOL:
            if cid == HERO_CAPE and tid in WALL_IDS and not has_tool(target):
                # CR1: 貫通ex相手は主壁ガルーラ（300+100=400 でネビュラ210×2を受ける）
                if p["opp_pierce_ex"] and tid == KANGA:
                    return 13500, "CR1: Cape on Kangaskhan (pierce tank)"
                return 13000, "C-15: Cape on wall"
            return -1, "tool: wrong target"
        if cid not in ALL_ENERGY:
            return -500, "skip non-energy attach"
        if obs.select.context == SelectContext.MAIN and obs.current.energyAttached:
            return -1, "already attached"

        e = energy_count(target)
        attached_types = _energy_types(target)
        is_active = any(target is pk for pk in my_state(obs).active if pk)
        if tid == CRUSTLE:
            if e >= 3:
                return -1, "R-10: Crustle full (3)"
            # C-4: Grow は Crustle 最優先（{G}コスト供給 + HP+20）。{G}未確保なら更に優先
            base = {GROW: 8400, G_ENERGY: 8300, MIST: 8000, SPIKY: 7900}[cid]
            if cid in G_PROVIDERS and not any(t == 1 for t in attached_types):
                base += 200
            score, reason = base, "C-4: load Crustle"
        elif tid == KANGA:
            if e >= 3:
                return -1, "R-10: Kangaskhan full (3)"
            base = {MIST: 8200, SPIKY: 8100, GROW: 7800, G_ENERGY: 7800}[cid]
            if p["opp_pierce_ex"]:
                base += 700   # CR1: 貫通ex相手は主壁ガルーラを先に満載にする
            score, reason = base, "C-4: load Kangaskhan"
        elif tid == DWEBBLE:
            if e >= 3:
                return -1, "R-10: Dwebble full"
            base = {GROW: 7200, G_ENERGY: 7100, MIST: 6800, SPIKY: 6800}[cid]
            score, reason = base, "C-4: pre-load Dwebble (evolves to wall)"
        else:
            return -1, "attach: wrong target"
        if is_active:
            score += 150      # 前で受けている壁から満載にする（ジャンボ条件）
        if self.is_threatened(target):
            score -= 2000     # R-08: 負け筋への追い銭防止
        return score, reason

    # ── ATTACK ──

    def _score_attack(self, obs, opt, combat):
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        if active is None:
            return 0, "no active"
        p = self.p
        if aid == ATK_ASCENSION:
            # C-5: Ascension は「手札にイワパレスが無い」時の代替進化ルート（72%）
            if p["hc"][CRUSTLE] == 0 and p["crustle_in_deck"] >= 1:
                return 1600, "C-5: Ascension (fetch Crustle from deck)"
            return 900, "Ascension (line already secured)"
        dmg = self.attack_damage(obs, active, aid)
        opp_act = opp_active_pokemon(obs)
        score = 1000 + min(dmg, 900)
        if (opp_act is not None and dmg > 0
                and self.guard_damage(dmg, active, opp_act) >= opp_act.hp):
            score += 800      # KO 選好（取り切りは R-07 が昇格）
        return score, "E-4: attack"

    # ── CARD/ENERGY 選択（前出し・サーチ・DISCARD 等） ──

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
                if cid == CRUSTLE:
                    if p["opp_pierce_ex"]:
                        # CR1: 貫通ex相手では免疫ボーナス無し + ガルーラより下げる
                        score = 13000 + e * 400
                        reason = "CR1: Crustle not safe vs pierce ex"
                    else:
                        # v1.1.1: 条件を opp_has_ex に戻す（opp_wallable_ex 化は CR3 の
                        # 付随変更で、CR3 棄却後も残っていた。ベースライン挙動へ復帰）
                        score = 15000 + e * 400 + (2000 if p["opp_has_ex"] else 0)
                        reason = "C-13: promote Crustle (wall)"
                elif cid == KANGA:
                    score, reason = 14000 + e * 400, "C-13: promote Kangaskhan (engine)"
                    if p["opp_prizes"] <= 3:
                        score -= 6000   # R-09: 3枚駒を終盤に晒さない
                        reason = "R-09: avoid exposing 3-prize Kangaskhan"
                elif cid == DWEBBLE:
                    score, reason = 8000 + e * 200, "promote Dwebble"
                elif cid == SHAYMIN:
                    score, reason = 6000, "promote Shaymin"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            # 相手側（ボス吊り出し）: KO 圏はスナイプ、それ以外は拘束価値
            hp = getattr(card, "hp", 999) if card is not None else 999
            plans = self.plan_attacks(obs)
            max_dmg = max((pl.damage for pl in plans if not pl.needs_retreat), default=0)
            if card is not None and max_dmg > 0 and \
                    self.guard_damage(max_dmg, active_pokemon(obs), card) >= hp:
                return 15000 + (500 - hp), "R-15: snipe KO"
            e = energy_count(card) if card is not None else 0
            rc = retreat_cost(card) if card is not None else 0
            return 5000 + rc * 200 - e * 300, "C-11: drag stall target"

        if ctx == SelectContext.DAMAGE:
            return self.default_score_damage_target(obs, opt)   # R-15

        if ctx == SelectContext.TO_HAND:
            return self._score_to_hand(obs, cid)

        if ctx == SelectContext.TO_BENCH:
            table = {DWEBBLE: 100, SHAYMIN: 50, KANGA: 40}
            return table.get(cid, 10), "to bench"

        if ctx in (SelectContext.ATTACH_TO, SelectContext.TO_FIELD, SelectContext.ATTACH_FROM):
            if card is not None and hasattr(card, "energyCards"):
                e = energy_count(card)
                if cid == CRUSTLE and e < 3:
                    return 100, "C-4: Crustle first"
                if cid == KANGA and e < 3:
                    return 80, "C-4: Kangaskhan"
                if cid == DWEBBLE and e < 3:
                    return 60, "C-4: Dwebble (pre-load)"
                return 5, "attach-to other"
            return 500, "to field"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            return self._score_discard(obs, cid)

        if ctx == SelectContext.TO_DECK:
            if cid in POKEMON_IDS:
                return 100, "to deck pokemon"
            return 10, "to deck other"

        if opt.type == OptionType.ENERGY:
            return 500, "take energy"

        return 500, "generic card"

    # ── TO_HAND（ヒルダ/ポケギアのサーチ先） ──

    def _score_to_hand(self, obs, cid):
        p = self.p
        fc, hc = p["fc"], p["hc"]
        base = 100 - hc.get(cid, 0) * 40
        if cid == CRUSTLE:
            return base + (90 if fc[CRUSTLE] < 2 and hc[CRUSTLE] == 0 else 55), "take Crustle"
        if cid == DWEBBLE:
            return base + (70 if fc[DWEBBLE] + hc[DWEBBLE] == 0 else 40), "take Dwebble"
        if cid == KANGA:
            return base + (65 if fc[KANGA] + hc[KANGA] == 0 else 30), "take Kangaskhan"
        if cid == GROW:
            return base + 85, "take Grow Grass"
        if cid == G_ENERGY:
            return base + 80, "take G energy"
        if cid == MIST:
            return base + 70, "take Mist"
        if cid == SPIKY:
            return base + 65, "take Spiky"
        # ポケギアのサポート指名（C-8/C-10 の文脈ゲート）
        if cid == XEROSIC:
            return base + (88 if p["opp_hand"] >= 6 else 45), "take Xerosic"
        if cid == HILDA:
            return base + (82 if fc[CRUSTLE] < 2 and hc[CRUSTLE] == 0 else 50), "take Hilda"
        if cid == LILLIE:
            return base + (78 if p["hand_size"] <= 5 else 55), "take Lillie"
        if cid == mt.BOSS:
            return base + (60 if p["opp_prizes"] <= 3 else 30), "take Boss"
        return base, "take other"

    # ── DISCARD（R-13 + 壁デッキの捨て順） ──

    def _score_discard(self, obs, cid):
        p = self.p
        fc, hc = p["fc"], p["hc"]
        if cid == HERO_CAPE:
            return -5000, "R-13: keep Hero's Cape (ACE SPEC)"
        if cid == CRUSTLE:
            if fc[CRUSTLE] >= 2 or hc.get(CRUSTLE, 0) >= 2:
                return 6000, "discard surplus Crustle"
            return -3000, "R-13: keep Crustle line"
        if cid == DWEBBLE:
            if fc[DWEBBLE] + fc[CRUSTLE] >= 3 or hc.get(DWEBBLE, 0) >= 2:
                return 7000, "discard surplus Dwebble"
            return -2500, "R-13: keep Dwebble"
        if cid == JUMBO:
            return (7500 if hc.get(JUMBO, 0) >= 3 else -1500), "keep Jumbo (heal engine)"
        if cid == mt.BOSS:
            return (8600 if hc.get(mt.BOSS, 0) >= 2 else -2000), "keep last Boss"
        if cid in ALL_ENERGY:
            if p["hand_energy"] >= 3:
                return 9800, "discard surplus energy"
            return 2000, "discard energy (scarce)"
        if cid == BATTLE_CAGE:
            return 9000, "Battle Cage is fodder"
        if cid == HAND_TRIMMER:
            return 8900, "Hand Trimmer is fodder"
        if cid == XEROSIC and p["opp_hand"] <= 4:
            return 8500, "Xerosic idle (opp hand small)"
        if cid == POFFIN and p["dwebble_in_deck"] == 0:
            return 8800, "Poffin done its job"
        if cid == KANGA and fc[KANGA] >= 2:
            return 8400, "surplus Kangaskhan"
        if cid is not None and hc.get(cid, 0) > 1:
            return 8000, "discard duplicate"
        return 1000, "generic discard"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(CrustleWallPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
