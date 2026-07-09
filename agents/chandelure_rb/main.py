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
                return 1200, "E-1: Flower Shower (mill 3)"
            active = active_pokemon(obs)
            dmg = self.attack_damage(obs, active, aid) if active else 0
            return 1000 + dmg, "attack (chip damage)"

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
            # div-C6（2026-07-08 divergence 実測・7/7）: セットアップ期は欠け駒が無くても
            # 山が厚ければ掘る（human=PLAY Pad / ours=END ×4）
            return (8000 if p["my_deck"] >= 15 else -1), "div-C6: Pad (setup dig)"
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
            if dc[COMFEY] + dc[CHANDELURE] + dc[LAMPENT] + dc[LITWICK] >= 1:
                return 12000, "Night Stretcher: recover pokemon"
            return -1, "Night Stretcher: nothing"
        if cid == ENERGY_SEARCH:
            # div-C4: エネ確保はハンマーより先（上位勢はエネ→グッズの順）。
            # 手張り済みでも手札エネ0なら次ターン分を確保しておく（実測に合わせ緩和）
            if p["energy_in_hand"] == 0:
                return 14800, "Energy Search"
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
            # E-5: 拘束用。エネ0の相手ベンチがいる交戦期のみ
            if combat and any(energy_count(b) == 0 for b in opp_state(obs).bench if b):
                return 5200, "E-5: Boss (drag & trap)"
            # div-C5（2026-07-08 divergence 実測・7/7 kidekikish）: 上位ピロットはボスを
            # もっと自由に切る（human=Boss / ours=Crushing,NZ）。交戦期はベンチがいれば拘束に使う
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
            return -1, "save Eri"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
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
            bonus = 100 if (active is not None and target is active) else 0
            bonus += 50 if cid == TELEPATH else 0   # テレパスはベンチ連鎖付き
            score = 15500 + bonus
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
                    score, reason = 15000 + energy_count(card) * 100, "promote Comfey"
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
            score = 5000 + retreat_cost(card) * 200 - energy_count(card) * 300
            if p["stadium_id"] == NEUTRAL_ZONE and is_ex(card):
                score += 800   # NZ 稼働中の ex は完全に無力
            if cid == OPP_MUNKIDORI:
                score += 400   # エンジン駒の拘束
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
            base = 100 - hc.get(cid, 0) * 25
            if cid == CHANDELURE:
                path = fc[LITWICK] + fc[LAMPENT] >= 1 or hc[LITWICK] >= 1
                return base + (90 if path else 55), "div-C4: take Chandelure"
            if cid == COMFEY:
                return base + (70 if fc[COMFEY] + hc[COMFEY] < 4 else -20), "div-C4: take Comfey"
            if cid in ENERGY_CARDS:
                bonus = 60 if (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1) else 25
                bonus += 5 if cid == TELEPATH else 0
                return base + bonus, "take energy"
            if cid == LITWICK:
                if p["line_in_play"] == 0:
                    return base + 75, "div-C4: take Litwick (start the line)"
                return base + (50 if p["line_in_play"] < 3 else -20), "take Litwick"
            if cid == LAMPENT:
                return base + (45 if fc[LITWICK] >= 1 else 10), "take Lampent"
            if cid == SHAYMIN:
                return base + (20 if fc[SHAYMIN] == 0 else -30), "take Shaymin"
            if cid == RARE_CANDY:
                return base + (40 if fc[LITWICK] >= 1 and hc[CHANDELURE] >= 1 else 0), "take Candy"
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
