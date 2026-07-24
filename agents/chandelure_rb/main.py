"""シャンデラ（Chandelure コントロール / 山札切れ = ミル）ルールベースエージェント

7/6メタのレート1000+勝ち組（kidekikish 1065.5、実測17勝5敗=77.3%）の移植。
設計文書: docs/planning/デッキ設計_シャンデラ.md（S-x/E-x/実測データ/未決事項）

コンセプト:
  自分はほぼダメージを出さない。コンフィの Flower Shower（お互い3ドロー）と
  シャンデラの特性 Alluring Light（お互い1ドロー）で相手を山札切れに追い込み、
  自分の山はリーリエの決心（手札を山へ戻す）で回復してミルレースに勝つ。
  防御は NZ（ex攻撃無効）+ シェイミ（ベンチ保護）+ バトルケージ（ダメカン配置無効）、
  妨害はハンマー（エネ剥がし）+ クセロシキ/エリ（手札破壊）+ ボス+重力宝石（拘束）。
  シャンデラの Mind Ruler は炎コストで不発（エピソード実測で提示0回）= 純粋な特性ボディ。
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
    has_in_play,
    has_tool,
    is_ex,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    retreat_cost,
    read_deck_csv as _read_deck_csv,
)

# ── カードID（デッキ設計_シャンデラ.md のリスト） ──

COMFEY = 164          # コンフィ HP70（Flower Shower: お互い3ドロー = ミル主エンジン）
LITWICK = 97          # ヒトモシ HP60
LAMPENT = 494         # ランプラー HP80
CHANDELURE = 98       # シャンデラ HP130（特性 Alluring Light: お互い1ドロー）
SHAYMIN = 343         # シェイミ HP80（特性 Flower Curtain: 非ルールボックスのベンチ保護）

BASIC_P = 5           # 基本{P}エネ
TELEPATH = 19         # テレパスエネルギー（{P}に手張りで山からたね{P}を2枚ベンチへ）

POFFIN = 1086
POKE_PAD = 1152
RARE_CANDY = 1079
NIGHT_STRETCHER = 1097
ENERGY_SEARCH = 1119
CRUSHING_HAMMER = 1120
ENHANCED_HAMMER = 1081
SWITCH_ITEM = 1123
GRAVITY_GEMSTONE = 1166   # どうぐ: バトル場のにげるコスト+1（両者）= 拘束
LILLIE = 1227             # リーリエの決心: 手札を山へ戻して6ドロー = 山の回復装置
XEROSIC = 1197            # 相手手札を3枚に
HILDA = 1225              # 進化+エネのサーチ
DAWN = 1231               # たね+1進化+2進化のサーチ
ERI = 1186                # 相手手札のグッズを2枚まで破壊
NEUTRAL_ZONE = 1247       # NZ (ACE SPEC): ex/V→非ルールボックスのダメージ全無効
BATTLE_CAGE = 1264        # ベンチへのダメカン配置無効

ATK_FLOWER_SHOWER = 215   # Comfey {P} 0dmg お互い3ドロー
ATK_PLAY_ROUGH = 216      # Comfey {P} 20+コイン20

OPP_MUNKIDORI = 112       # 相手のマシマシラ（バトルケージの主対象）

# ── 決定性ラウンド トグル（EXP-036 第3ラウンド 2026-07-22） ──
# 決定性監査（scripts/decisiveness_audit.py 140戦・純ルール）で、負け試合の
# 無意見決定（首位-2位 margin が 0 or <1000）が SELECT 系に集中していると判明。
# 負け対面は froslass_starmie / marnie に集中し、敗因の型はプライズレース負け
# （相手山3〜6枚まで追い詰めての力尽き = ミルテンポの浪費が直接効く）。
#
# 【判定 2026-07-22 A/B 実測（80戦×7対面 + 160戦確定）】3つの挙動系トグルは
# 全構成で集計悪化（全ON −4.3pt / PROMOTE単 −5.2 / FUEL単 −2.9 / TAKE単 −4.3、
# 160戦確定 全ON −0.7 / プール240戦 −1.8pt）。本デッキの厳格基準
# 「集計 −1pt 超悪化は即 OFF（ルール王者 997.5 非劣化が絶対条件）」により既定 OFF。
# 代わりに CHA_MARGIN（挙動厳密不変のマージン拡幅のみ）を既定 ON で採用 —
# 監査の無意見クラスタ解消は挙動を変えずに達成する（詳細 デッキ設計_シャンデラ.md）。
CHA_MARGIN = os.environ.get("CHA_MARGIN", "1") != "0"            # 挙動不変のマージン拡幅（採用・既定ON）
CHA_PROMOTE = os.environ.get("CHA_PROMOTE", "0") != "0"          # 昇格順ドクトリン（棄却・既定OFF）
CHA_FUEL_TARGET = os.environ.get("CHA_FUEL_TARGET", "0") != "0"  # fuel対象+ミル手順序（棄却・既定OFF）
CHA_TAKE_ENERGY = os.environ.get("CHA_TAKE_ENERGY", "0") != "0"  # TO_HANDエネ使い分け（棄却・既定OFF）
# ── 第4弾（2026-07-24 ユーザー指示。判定は王者ゲート = A/B −1pt 超悪化で即 OFF） ──
CHA_BOSS_HEAVY = os.environ.get("CHA_BOSS_HEAVY", "1") != "0"    # にげ重ベンチの吊り出し（余裕時）
CHA_ERI_IDLE = os.environ.get("CHA_ERI_IDLE", "1") != "0"        # サポート枠が暇なら Eri（ビワ）
CHA_NC_HOLD = os.environ.get("CHA_NC_HOLD", "1") != "0"          # NZ は敗北リーチ可視まで温存
CHA_LILLIE_EARLY = os.environ.get("CHA_LILLIE_EARLY", "1") != "0"  # 後攻T1/先攻T2 はリーリエ優先

CHANDELURE_LINE = {LITWICK, LAMPENT, CHANDELURE}
ENERGY_CARDS = {BASIC_P, TELEPATH}


class ChandelurePolicy(BasePolicy):
    DECK_NAME = "chandelure_mill"
    GO_FIRST = True            # R-21 確定（2026-07-07 実測: kidekikish IS_FIRST 9/9 YES）
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】マリガンは常にマックス引く
    ATTACKER_IDS = {COMFEY}
    ENERGY_IDS = ENERGY_CARDS
    LINE_PROTECT_IDS = CHANDELURE_LINE | {RARE_CANDY, NEUTRAL_ZONE}   # R-13（NZは回収不能）
    ATTACK_ENERGY_TYPE = 5     # 超（弱点計算用。実質 Play Rough のみ）

    def __init__(self):
        super().__init__()
        self.p = {}

    # ═══════════════ ターン分析（軽量: 枚数と旗だけ） ═══════════════

    def choose(self, obs):
        self.p = self._analyze(obs)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        os_ = opp_state(obs)
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
        opp_pokes = [p for p in (os_.active + os_.bench) if p]
        # 相手のエネ事情（ハンマーの発動判定）
        opp_energy_total = sum(energy_count(p) for p in opp_pokes)
        opp_special_energy = any(
            getattr(CARD_DB.get(ec.id), "cardType", None) == CardType.SPECIAL_ENERGY
            for p in opp_pokes for ec in (getattr(p, "energyCards", None) or []))
        # 自軍のエネ需要（エネ0のコンフィ）
        comfey_need = sum(1 for p in all_my_pokemon(obs)
                          if p.id == COMFEY and energy_count(p) == 0)
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size,
            "bench_free": ms.benchMax - len([b for b in ms.bench if b]),
            "bench_used": len([b for b in ms.bench if b]),
            "stadium_id": stadium_id,
            "my_deck": ms.deckCount,
            "opp_deck": os_.deckCount,
            "opp_hand": os_.handCount,
            "opp_has_ex": any(is_ex(p) for p in opp_pokes),
            "opp_has_munki": any(p.id == OPP_MUNKIDORI for p in opp_pokes),
            "opp_energy_total": opp_energy_total,
            "opp_special_energy": opp_special_energy,
            "comfey_need": comfey_need,
            "energy_in_hand": hc[BASIC_P] + hc[TELEPATH],
            "line_in_play": fc[LITWICK] + fc[LAMPENT] + fc[CHANDELURE],
        }

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場のコンフィが Flower Shower を払える({P}1枚以上) かつ シャンデラが1体以上。"""
        comfey_ready = any(p.id == COMFEY and energy_count(p) >= 1
                           for p in all_my_pokemon(obs))
        return comfey_ready and has_in_play(obs, CHANDELURE)

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {COMFEY: 10, LITWICK: 5, SHAYMIN: 3}   # S-1 実測: 14/5/3
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # S-2: セットアップでもベンチ展開する（実測あり。ドンク回避も兼ねる）
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {LITWICK: 100, SHAYMIN: 80, COMFEY: 60}
            return table.get(cid, 10), "S-2: setup bench"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_number(self, obs, opt):
        # E-8/div-C4: DRAW_COUNT は 1 を選ぶ（自山温存。実測: 1,1,1,2 — 0 ではなく 1）
        if obs.select.context == SelectContext.DRAW_COUNT:
            return -abs((opt.number or 0) - 1), "E-8: draw one (preserve deck)"
        return super().score_number(obs, opt)

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
            if cid == CHANDELURE:
                # E-1: Alluring Light は毎ターン。E-1a: 自山2枚以上でのみ（実測: 山2使用/山1スキップ）
                # div-C8【棄却 2026-07-11】: 帯 29000→1500（攻撃直前）を試行 — human=Boss/EVOLVE/
                # Lillie→ours=ABILITY が両日17件（逆0件）だったが、実測は 07-08 68.4→63.0% /
                # 07-09 59.4→58.5% と大幅悪化。人間の特性使用位置はターン中盤に分散しており
                # 「最後」固定は「最初」固定より遠い。29000 に差し戻し
                if p["my_deck"] >= 2:
                    return 29000, "E-1: Alluring Light (mill 1)"
                return -1, "E-1a: deck too thin for Alluring Light"
            # div-C4（2026-07-07 divergence 実測）: 相手スタジアム等の汎用特性は
            # 自分の行動（ハンマー・手張り・サポート）を全て済ませた後に回す
            return 2000, "generic ability (late)"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid == CHANDELURE:
                return 25000, "S-3: evolve Chandelure (Alluring Light body)"
            if cid == LAMPENT:
                return 24000, "S-3: evolve Lampent"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            return -5000, "E-7: never retreat (use Switch item)"

        if opt.type == OptionType.ATTACK:
            aid = getattr(opt, "attackId", None)
            if aid == ATK_FLOWER_SHOWER:
                # E-1a【ハード・ミル版R-11】: 自山≤3 でのセルフデッキアウト禁止
                #（相手山≤3なら相手のターン開始ドローが先に尽きるので解除）
                if p["my_deck"] <= 3 and p["opp_deck"] > 3:
                    return -1, "E-1a: Flower Shower would deck us out"
                # 【2026-07-22 決定性監査】負け試合の最大無意見クラスタ（OFF監査117件）が
                # 「FS 1200 vs Play Rough 1020+dmg = margin 180」。選択自体は実測どおり
                # FS（106:1）で正しく、margin だけが薄い。
                # CHA_MARGIN【採用】: FS 1200→1950 / chip 1000+dmg→850+dmg。序列は全対全で
                # 厳密不変（FS > chip > 宝石700 > END のまま。(870,1200] 帯に他スコア無し —
                # generic play 1000 はこのデッキの60枚全てが明示ハンドラ持ちで不到達）。
                # margin 180→1080 = decisive。generic ability 2000 の下は維持。
                # CHA_FUEL_TARGET【棄却・opt-in】: FS 1750 / chip 150+dmg（chip vs 宝石の
                # 弱序列320を反転 = FS封印末期に宝石を張ってから殴る、まで踏み込む版）。
                if CHA_FUEL_TARGET:
                    return 1750, "E-1: Flower Shower (mill 3)"
                return (1950 if CHA_MARGIN else 1200), "E-1: Flower Shower (mill 3)"
            active = active_pokemon(obs)
            dmg = self.attack_damage(obs, active, aid) if active else 0
            if CHA_FUEL_TARGET:
                return 150 + dmg, "attack (chip damage)"
            return ((850 if CHA_MARGIN else 1000) + dmg), "attack (chip damage)"

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY):
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
        fc, hc, dc = p["fc"], p["hc"], p["dc"]

        if data is not None and data.cardType == CardType.POKEMON:
            score, reason = 20000, "play pokemon"
            if cid == LITWICK:
                score += 500 if p["line_in_play"] < 3 else 100
            elif cid == COMFEY:
                # div-C2: 2体目以降のコンフィ素出しは急がない（ベンチ=サイド献上。妨害が先）
                if fc[COMFEY] >= 1:
                    score, reason = 13800, "play spare Comfey (after items)"
                else:
                    score += 400
            elif cid == SHAYMIN:
                score += 300 if fc[SHAYMIN] == 0 else -300
            # R-03: ベンチ0は即死筋 → 最優先で解消 / R-24: 1枠空け
            if p["bench_used"] == 0:
                score += 5000
            elif p["bench_free"] <= 1:
                score -= 5000
            return score, reason

        # ── スタジアム（E-4: NZ が先、ケージは NZ 消滅後） ──
        if cid == NEUTRAL_ZONE:
            if p["stadium_id"] == NEUTRAL_ZONE:
                return -1, "NZ already up"
            # CHA_NC_HOLD v2（2026-07-24 ユーザー指示・同日改訂）: NZ は ACE SPEC ×1 で
            # 回収不能 — 早張りは貼り替えで剥がされ損なので、**次の相手番の敗北リーチが
            # 見えた時だけ**リーサルブロッカーとして張る。リーチは2系統:
            #   (a) R-08 threats = 取られるとサイド取り切りで負ける駒が存在
            #   (b) 盤面全滅リーチ = ベンチ0 ∧ バトル場が相手投影打点で落ちる
            #       （初版「相手サイド1-2枚」条件はこの序盤全滅パターンを守れなかった）
            if CHA_NC_HOLD:
                active = active_pokemon(obs)
                wipe_risk = (p["bench_used"] == 0 and active is not None
                             and self.opp_max_damage(obs) >= active.hp)
                if not self.t["threats"] and not wipe_risk:
                    return -1, "CHA: hold NZ until lethal visible"
            if p["opp_has_ex"]:
                return 19500, "E-4: Neutralization Zone (block ex damage)"
            return -1, "E-4: hold NZ (no rule-box threat yet)"
        if cid == BATTLE_CAGE:
            if p["stadium_id"] == NEUTRAL_ZONE:
                return -1, "E-4: never overwrite own NZ"
            if p["stadium_id"] == BATTLE_CAGE:
                return -1, "cage already up"
            if p["opp_has_munki"]:
                return 19000, "E-4: Battle Cage (block Adrena-Brain)"
            if p["stadium_id"] != 0:
                return 15000, "E-4: Battle Cage (stadium war)"
            return -1, "hold Battle Cage"

        # ── グッズ ──
        if cid == RARE_CANDY:
            if fc[LITWICK] >= 1 and hc[CHANDELURE] >= 1:
                return 19000, "S-3: Rare Candy -> Chandelure"
            return -1, "Rare Candy: no line"
        if cid == POFFIN:
            # div-C2（2026-07-07 divergence 実測）: 交戦期（エンジン完成後）は山を薄めず攻撃を優先
            if p["bench_free"] <= 0:
                return -1, "Poffin: bench full"
            if combat:
                return (8000 if fc[COMFEY] < 2 else -1), "div-C2: Poffin only to rebuild"
            need = (fc[COMFEY] < 2) or (p["line_in_play"] < 2)
            return (18000 if need else 8000), "S-2: Poffin"
        if cid == POKE_PAD:
            # S-4: シャンデラ堀り（TO_HAND 実測33回の主役）
            # div-C2: 使用は「欠けている駒がある時」だけ（上位勢は毎ターン掘らず攻撃を優先）
            if combat:
                if fc[CHANDELURE] < 2 and hc[CHANDELURE] == 0 and p["my_deck"] >= 10:
                    return 8000, "div-C2: Pad for 2nd Chandelure"
                return -1, "div-C2: preserve deck"
            need = (hc[CHANDELURE] + fc[CHANDELURE] == 0) or (fc[COMFEY] + hc[COMFEY] == 0)
            if need:
                return 17000, "S-4: Poke Pad (missing piece)"
            # div-C6【棄却→差し戻し 2026-07-11】: 「セットアップ期は山≥15なら欠け駒なしでも掘る」
            # （7/7 kidekikish ×4 由来の暫定）を新データで再計測 — 07-08 67.3→67.0%(+1手)、
            # 07-09 58.9→59.4%(−1手) と両日で逆方向のノイズ。新ピロット（Star-mine/Taimo）の
            # 支持なし + ミル型の自山温存原則（山を無駄に薄めない）に反するため差し戻し
            return -1, "S-4: hold Pad (no missing piece)"
        if cid == CRUSHING_HAMMER:
            # E-6: エネが見える限り毎ターン投げる（実測50回 = 最多プレイ）
            if p["opp_energy_total"] >= 1:
                return 14000, "E-6: Crushing Hammer"
            return -1, "Crushing Hammer: no target"
        if cid == ENHANCED_HAMMER:
            # div-C4: クラッシュハンマーが先（実測: 両方持ちはクラッシュから）
            if p["opp_special_energy"]:
                return 13500, "E-6: Enhanced Hammer (special energy)"
            return -1, "Enhanced Hammer: no special energy"
        if cid == NIGHT_STRETCHER:
            if (dc[BASIC_P] >= 1 and p["energy_in_hand"] == 0 and p["comfey_need"] >= 1):
                return 13000, "Night Stretcher: recover energy"
            # div-C11（2026-07-11 実測・調整日07-08/09）: ポケモン回収は「エンジン駒が実際に
            # 足りない時」だけ。トラッシュに駒があるだけで拾うのは山掘り（手数）の無駄で、
            # 上位勢はボス/パッド/攻撃を優先（human=Pad,Boss,Flower / ours=Stretcher が
            # 07-09 ×5 + 07-08 ×1、逆方向1件）
            need_comfey = (fc[COMFEY] < 2 and dc[COMFEY] >= 1)
            need_chand = (fc[CHANDELURE] + hc[CHANDELURE] == 0 and dc[CHANDELURE] >= 1)
            if need_comfey or need_chand:
                return 12000, "div-C11: Night Stretcher (rebuild engine)"
            return -1, "Night Stretcher: nothing"
        if cid == ENERGY_SEARCH:
            # div-C4: エネ確保はハンマーより先（上位勢はエネ→グッズの順）。
            # div-C10（2026-07-11 実測・調整日07-08/09）: div-C4 の「手張り済みでも先回り確保」を
            # 差し戻し、エネ0のコンフィが実在する時だけ使う。上位勢は不要な山掘りをしない
            # （human=Flower/Comfey/Lillie 等 / ours=Energy Search が 07-08 ×5 + 07-09 ×9、逆方向1件。
            #  ミル型は自山1枚の温存が勝敗に直結する）
            if p["energy_in_hand"] == 0 and p["comfey_need"] >= 1:
                return 14800, "div-C10: Energy Search (fuel needed)"
            return -1, "Energy Search: not needed"
        if cid == SWITCH_ITEM:
            active = active_pokemon(obs)
            ready = any(pk.id == COMFEY and energy_count(pk) >= 1
                        for pk in my_state(obs).bench if pk)
            if active is not None and active.id != COMFEY and ready:
                return 11000, "Switch: promote Comfey attacker"
            return -1, "save Switch"
        if cid == GRAVITY_GEMSTONE:
            # div-C1（2026-07-07 divergence 実測）: 攻撃より下の帯（埋め手）
            active = active_pokemon(obs)
            if active is not None and not has_tool(active):
                return 700, "E-5/div-C1: Gemstone (filler)"
            if any(pk.id == COMFEY and not has_tool(pk) for pk in all_my_pokemon(obs)):
                return 650, "E-5/div-C1: Gemstone (bench Comfey filler)"
            return -1, "save Gravity Gemstone"

        # ── サポート（択一） ──
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == XEROSIC:
            # E-3: 対アラカザムは Powerful Hand 減衰で最優先。通常は相手手札≥7（実測モード）
            if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                return 6000, "E-3: Xerosic vs Alakazam"
            if p["opp_hand"] >= 7:
                return 5500, "E-3: Xerosic (big hand)"
            if combat and p["opp_hand"] >= 4:
                return 4800, "E-3: Xerosic"
            return -1, "save Xerosic"
        if cid == LILLIE:
            # CHA_LILLIE_EARLY（2026-07-24 ユーザー指示）: 序盤はリーリエで攻める —
            # ベンチ展開・エネ堀りなどやりたいことが多い立ち上がりは、トウコ（Hilda 5000）
            # より手数の増えるリーリエを先に切る。対象は「後攻の自分1ターン目（global
            # turn 2）/ 先攻の自分2ターン目（global turn 3）」。帯 5600 = Hilda より上、
            # 山回復 6500・対アラカザム Xerosic 6000 より下（緊急時はそちらが先勝ち）
            if CHA_LILLIE_EARLY:
                st = obs.current
                first = (st.firstPlayer == st.yourIndex)
                if (first and st.turn == 3) or (not first and st.turn == 2):
                    return 5600, "CHA: Lillie (early tempo)"
            # E-2: 山の回復装置。山が薄い時は最優先、手札が太い時は山へ還流
            # div-C4: 手札≤6 のリフレッシュを許可（実測: 手札4〜6での使用が最多帯）
            if p["my_deck"] <= 6:
                return 6500, "E-2: Lillie (refill deck)"
            if p["hand_size"] <= 6:
                return 4500, "E-2: Lillie (refresh)"
            if p["hand_size"] >= 9 and p["my_deck"] <= 15:
                return 4200, "E-2: Lillie (bank fat hand)"
            return -1, "save Lillie"
        if cid == mt.BOSS:
            # CHA_BOSS_HEAVY（2026-07-24 ユーザー指示）: にげるコストの重い相手ベンチは
            # 余裕があれば吊り出して拘束（LO の勝ち筋 = 前を止めてミルの番数を稼ぐ）。
            # 帯 5800 = Lillie 山回復 6500 / 対アラカザム Xerosic 6000 より下（緊急時は
            # そちらが先勝ち）、通常 Xerosic 5500 より上。setup でも重い獲物がいれば 5000。
            # 吊り先の選択は既存の E-5 ターゲット則（にげ重×200 − エネ×300）がそのまま裁く
            if CHA_BOSS_HEAVY and any(
                    retreat_cost(b) >= 2 and energy_count(b) <= 1
                    for b in opp_state(obs).bench if b):
                return (5800 if combat else 5000), "CHA: Boss (heavy retreat trap)"
            # E-5: 拘束用。エネ0の相手ベンチがいる交戦期のみ
            if combat and any(energy_count(b) == 0 for b in opp_state(obs).bench if b):
                return 5200, "E-5: Boss (drag & trap)"
            # div-C5（2026-07-08 divergence 実測・7/7 kidekikish）: 上位ピロットはボスを
            # もっと自由に切る（human=Boss / ours=Crushing,NZ）。交戦期はベンチがいれば拘束に使う
            # 【確定昇格 2026-07-11】OFF 変異で調整日07-08/09 とも完全同値（フリップ0手・悪化なし）。
            # Boss 系不一致は依然 human=Boss 方向のみ（両日計8件、逆0）で新ピロット（Star-mine）も支持
            if combat and any(b for b in opp_state(obs).bench if b):
                return 4700, "div-C5: Boss (loose drag)"
            return -1, "save Boss"
        if cid == HILDA:
            need_evo = (fc[LITWICK] >= 1 and hc[LAMPENT] + hc[CHANDELURE] == 0)
            need_energy = (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1)
            if need_evo or need_energy:
                return (5000 if not combat else 4200), "S-4: Hilda"
            return -1, "save Hilda"
        if cid == DAWN:
            if p["line_in_play"] == 0 and hc[LITWICK] + hc[LAMPENT] + hc[CHANDELURE] == 0:
                return 4800, "S-4: Dawn (whole line)"
            return -1, "save Dawn"
        if cid == ERI:
            if combat and p["opp_hand"] >= 4:
                return 4000, "E-3: Eri"
            # CHA_ERI_IDLE（2026-07-24 ユーザー指示）: サポート枠が暇なら Eri（ビワ）を
            # 切る — 相手手札のグッズ破壊は LO では常にプラス方向。帯 400 = 学習帯級で、
            # 他のサポート・本命行動が全て沈黙した番だけ浮上する（end(0) にだけ勝つ）
            if CHA_ERI_IDLE:
                return 400, "CHA: Eri (idle supporter)"
            return -1, "save Eri"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
        p = self.p
        fc, hc, dc = p["fc"], p["hc"], p["dc"]
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        if cid == GRAVITY_GEMSTONE:
            # div-C1: 攻撃より下の帯 = 「攻撃できないターンの埋め手」（実測: 上位勢は
            # 宝石を持ったまま攻撃するターンが多く、装着は22試合で20回に留まる）
            if has_tool(target):
                return -1, "target has tool"
            active = active_pokemon(obs)
            if tid == COMFEY and active is not None and target is active:
                return 700, "E-5/div-C1: Gemstone on active Comfey (filler)"
            if tid == COMFEY:
                return 650, "E-5/div-C1: Gemstone on bench Comfey (filler)"
            if active is not None and target is active:
                return 600, "E-5: Gemstone on active (filler)"
            return -1, "save Gravity Gemstone"

        if cid not in ENERGY_CARDS:
            return -500, "skip non-energy attach"
        if obs.current.energyAttached:
            return -1, "already attached"

        if tid == COMFEY:
            if energy_count(target) >= 1:
                return -1, "R-10: Comfey already paid (cost 1)"
            active = active_pokemon(obs)
            # div-C4: 手張りはハンマー等のグッズより先（上位勢はエネ→グッズの順）
            # div-C12（2026-07-11 実測・調整日07-08/09）: 帯を 15500 → 19800 に引き上げ、
            # ポフィン(18000)/パッド(17000)/NZ(19500) より前に手張りを済ませる
            # （human=ATTACH ours=Poffin/Pad/NZ が 07-08 ×8 + 07-09 ×4、逆方向計6件。
            #  1ターン1回の権利を先に確実に消費する順序が上位勢の型）
            if CHA_FUEL_TARGET:
                # CHA_FUEL_TARGET【棄却・opt-in 2026-07-22】: S-5 の同点（負け試合 =
                # ベンチ間 m=0 / テレパス vs 基本 m=50 / アクティブ vs ベンチ m=100）に
                # 挙動を変える意見を与える版。A/B 実測で集計悪化のため既定 OFF。
                #   (1) アクティブ +3500（今番の FS 即撃ち）
                #   (2) ベンチ間は壁 +2000 — 注: コンフィ HP70 < 汎用打点想定 220 のため
                #       実質不発（発火はミラーの打点想定40のみ）
                #   (3) 両種所持時のみ種の使い分け +1000（連鎖生存→テレパス/死→基本）
                # 上限 19800+3500+1000=24300 は進化帯 24000 と交差しうる。
                bonus = 0
                if active is not None and target is active:
                    bonus += 3500
                elif target.hp > self.opp_max_damage(obs):
                    bonus += 2000
                if hc[BASIC_P] >= 1 and hc[TELEPATH] >= 1:
                    comfey_in_deck = 4 - fc[COMFEY] - hc[COMFEY] - dc[COMFEY]
                    chain_live = p["bench_free"] >= 2 and comfey_in_deck >= 1
                    preferred = TELEPATH if chain_live else BASIC_P
                    bonus += 1000 if cid == preferred else 0
            else:
                # CHA_MARGIN【採用 2026-07-22】: 既存の選好（アクティブ>ベンチ、テレパス>基本）
                # の順序はそのままに段差だけ 100→2100 / 50→1050 に拡幅 = 監査の decisive
                # 閾値 1000 を跨がせる（S-5 の m=50/m=100 クラスタ解消。ベンチ間同種 m=0 は
                # 実在の選好が無いため対象外）。序列検証: 上限 19800+3150=22950 は
                # EVOLVE 24000 の下・PLAY ポケモン帯 20000-20500 とは交差するが両者とも
                # 番を終えない手で同一ターン実行集合は不変（対戦ハーネスは PYTHONHASHSEED
                # 固定でも非決定的なため軌跡一致検証は不可 — 同一性の根拠は本注釈の全帯
                # 序列照合 + null A/B ±3pt 以内）。R-08 脅威対象は旧段差のまま
                # （拡幅すると 19800+3150-2000=20950 > ポフィン18000 となり「ポフィンで
                #  新コンフィを出してから張る」旧挙動の順序が壊れるため脅威時は旧式固定）。
                wide = CHA_MARGIN and not self.is_threatened(target)
                bonus = ((2100 if wide else 100)
                         if (active is not None and target is active) else 0)
                bonus += (1050 if wide else 50) if cid == TELEPATH else 0   # テレパスはベンチ連鎖付き
            score = 19800 + bonus
            if self.is_threatened(target):
                score -= 2000   # R-08: 負け筋への追い銭防止
            return score, "S-5: fuel Flower Shower"
        return -1, "S-5: energy only on Comfey"

    # ── CARD/ENERGY 選択（サーチ先・前出し・吊り出し等） ──

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
                # E-7: 前出しはコンフィ最優先（実測45/54）。シャンデラ/シェイミは守る
                if cid == COMFEY:
                    if CHA_PROMOTE and not self.is_threatened(card):
                        # CHA_PROMOTE【棄却・opt-in 2026-07-22】: promote Comfey 同点
                        # （m=0 / m=100）への挙動を変える意見（エネ付き +4000 > 壁 +2000 >
                        # 無傷 +1000 > 素。辞書式段差）。壁 +2000 はコンフィ HP70 < 打点
                        # 想定 220 で実質不発。A/B 実測で集計悪化のため既定 OFF。
                        # R-08 脅威駒は旧式のままにして、脅威コンフィがヒトモシ4500等を
                        # 追い越す事故を構造的に防ぐ。
                        bonus = 4000 if energy_count(card) >= 1 else 0
                        bonus += 2000 if card.hp > self.opp_max_damage(obs) else 0
                        bonus += 1000 if damage_on(card) == 0 else 0
                        score, reason = 15000 + bonus, "promote Comfey"
                    else:
                        # CHA_MARGIN【採用 2026-07-22】: 既存の「エネ付き優先」の段差だけ
                        # ×100→×1100 に拡幅（m=100 クラスタを decisive 化。順序厳密不変:
                        # コンフィ帯 [15000,16100+] は他候補 4500/4300/3000/2500 と交差せず、
                        # R-08 −15000 後の帯 [0,1100+] も同順序を保つ。同状態 m=0 は実在の
                        # 選好が無いため対象外）。
                        mult = 1100 if CHA_MARGIN else 100
                        score, reason = 15000 + energy_count(card) * mult, "promote Comfey"
                elif cid == LITWICK:
                    score, reason = 4500, "promote Litwick"
                elif cid == LAMPENT:
                    score, reason = 4300, "promote Lampent"
                elif cid == CHANDELURE:
                    score, reason = 3000, "protect Chandelure (engine)"
                elif cid == SHAYMIN:
                    score, reason = 2500, "protect Shaymin (wall)"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            # E-5: ボス吊り出し = 拘束（エネ0・にげる重い・NZ稼働中のex）
            # div-C7（2026-07-11 実測・調整日07-08）: マシマシラ+400 を除去。上位勢の吊り先は
            # 5/5 でユキメノコ > マシマシラ（Star-mine ×4 + kidekikish ×1 のクロスピロット）。
            # Adrena-Brain はベンチからでも機能するため吊っても止まらない = 拘束価値なし
            score = 5000 + retreat_cost(card) * 200 - energy_count(card) * 300
            if p["stadium_id"] == NEUTRAL_ZONE and is_ex(card):
                score += 800   # NZ 稼働中の ex は完全に無力
            return score, "E-5: drag & trap target"

        if ctx == SelectContext.DISCARD_ENERGY:
            # E-6: ハンマー対象。相手側のみ（自分側は minCount 充足の least-bad）
            if pi != yi and card is not None:
                score = 10000 + energy_count(card) * 100
                opp = opp_state(obs)
                if opp.active and card is opp.active[0]:
                    score += 500   # 前を乾かして攻撃を止める
                if cid == OPP_MUNKIDORI:
                    score += 300   # Adrena-Brain 停止
                return score, "E-6: hammer target"
            return -1000, "never discard own energy"

        if ctx == SelectContext.TO_HAND:
            # div-C4（2026-07-07 divergence 実測）: 上位勢の優先表
            # シャンデラ（無条件）> コンフィ > エネ > ヒトモシ > ランプラー
            # div-C9（2026-07-11 実測・調整日07-08/09）: 表を機能条件化 —
            #   (1) ラインの中間（ランプラー）が完全に欠けている時はシャンデラより先に取る
            #       （human=Lampent/ours=Chandelure が 07-08 ×5 + 07-09 ×1。進化はランプラー経由必須）
            #   (2) シャンデラの path 判定に手札のランプラーを含める（確保後はシャンデラ優先 07-09 実測）
            #   (3) 2枚目以降のシャンデラは減衰（human=Comfey/ours=Chandelure ×3。特性ボディは1体で十分）
            #   (4) 場にコンフィ0ならコンフィ最優先（S-0: エンジン無しではミルが始まらない）
            # CHA_MARGIN【採用 2026-07-22】: TO_HAND 表全体を ×50 に等倍スケール
            # （順序・符号は厳密に不変 = 挙動同一。実在する選好差、例えば
            # ランプラー92 vs シャンデラ90 の 2 が 100 になり、監査の絶対閾値 1000 に
            # 対して意見が計測可能になる下地）。同名カード同士の m=0 は論理的に解消不能。
            # CHA_TAKE_ENERGY【棄却・opt-in】: 選択肢に基本{P}とテレパスの両種が
            # 並ぶ時だけ使い分けの意見 +1000: テレパス連鎖が生きている（ベンチ2枠以上
            # ∧ 山にコンフィ残）ならテレパス、死んでいるなら基本（夜のタンカ/エネ転送で
            # 回収できる方を使い、連鎖価値のある特殊エネは温存しない場面を作らない）。
            # A/B 実測で集計悪化のため既定 OFF（TAKE 有効時はスケールも強制 = ±1000 が
            # 未スケール表を飲み込む事故を防ぐ）。
            sc = 50 if (CHA_MARGIN or CHA_TAKE_ENERGY) else 1
            base = (100 - hc.get(cid, 0) * 25) * sc
            if cid == CHANDELURE:
                path = fc[LITWICK] + fc[LAMPENT] + hc[LITWICK] + hc[LAMPENT] >= 1
                first = fc[CHANDELURE] + hc[CHANDELURE] == 0
                return base + ((90 if first else 65) if path else 55) * sc, "div-C4/C9: take Chandelure"
            if cid == COMFEY:
                if fc[COMFEY] == 0:
                    return base + 95 * sc, "div-C9: take Comfey (engine down)"
                return base + (70 if fc[COMFEY] + hc[COMFEY] < 4 else -20) * sc, "div-C4: take Comfey"
            if cid in ENERGY_CARDS:
                bonus = (60 if (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1) else 25) * sc
                if CHA_TAKE_ENERGY:
                    kinds = set()
                    for o in obs.select.option:
                        c2 = option_card(obs, o)
                        if c2 is not None and c2.id in ENERGY_CARDS:
                            kinds.add(c2.id)
                    if len(kinds) >= 2:
                        comfey_in_deck = 4 - fc[COMFEY] - hc[COMFEY] - p["dc"][COMFEY]
                        chain_live = p["bench_free"] >= 2 and comfey_in_deck >= 1
                        preferred = TELEPATH if chain_live else BASIC_P
                        bonus += 1000 if cid == preferred else 0
                    else:
                        bonus += 5 * sc if cid == TELEPATH else 0
                else:
                    bonus += 5 * sc if cid == TELEPATH else 0
                return base + bonus, "take energy"
            if cid == LITWICK:
                if p["line_in_play"] == 0:
                    return base + 75 * sc, "div-C4: take Litwick (start the line)"
                return base + (50 if p["line_in_play"] < 3 else -20) * sc, "take Litwick"
            if cid == LAMPENT:
                if fc[LAMPENT] + hc[LAMPENT] == 0 and fc[LITWICK] + hc[LITWICK] >= 1:
                    return base + 92 * sc, "div-C9: take Lampent (missing middle)"
                return base + (45 if fc[LITWICK] >= 1 else 10) * sc, "take Lampent"
            if cid == SHAYMIN:
                return base + (20 if fc[SHAYMIN] == 0 else -30) * sc, "take Shaymin"
            if cid == RARE_CANDY:
                return base + (40 if fc[LITWICK] >= 1 and hc[CHANDELURE] >= 1 else 0) * sc, "take Candy"
            return base, "take other"

        if ctx == SelectContext.TO_BENCH:
            # S-2/div-C3（2026-07-07 divergence 実測）: コンフィ最優先（57 vs 20）で常にヒトモシより上
            if p["bench_free"] <= 0:
                return -1, "bench full"
            if cid == COMFEY:
                return 120 - fc[COMFEY] * 10, "div-C3: bench Comfey first"
            if cid == LITWICK:
                return 70 - p["line_in_play"] * 15, "S-2: bench Litwick"
            if cid == SHAYMIN:
                return (60 if fc[SHAYMIN] == 0 else -30), "S-2: bench Shaymin"
            return 10, "bench other"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            return self.default_score_discard(obs, opt)   # R-13

        if ctx == SelectContext.TO_DECK:
            if cid in CHANDELURE_LINE:
                return 100, "to deck line"
            if cid == COMFEY:
                return 90, "to deck Comfey"
            return 10, "to deck other"

        if ctx in (SelectContext.DAMAGE, getattr(SelectContext, "DAMAGE_COUNTER", SelectContext.DAMAGE)):
            return self.default_score_damage_target(obs, opt)   # R-15

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(ChandelurePolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
