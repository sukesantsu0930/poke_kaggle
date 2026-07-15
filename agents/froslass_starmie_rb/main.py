"""ユキメノコスターミー（Mega Froslass ex + Mega Starmie ex）ルールベースエージェント

LB プレイヤー taksai の実リスト（2026-07-11 エピソード12戦同一60枚）の模倣実装。
設計文書: docs/planning/デッキ設計_ユキメノコスターミー.md（効果の実測・S-x/E-x/未決事項）

コンセプト:
  たね（ユキワラシ/ヒトデマン）を並べ、素進化 or セイジ（山から直接のせる）で1進化メガを
  2〜3体立てる。エネは各アタッカー1枚（水9枚のみ）。なみのりビーチの無料ピボットで
  ジェットブロー 120+ベンチ50（デフォルト）と うらみぶし 50×相手手札（大物・対フーディン）を
  撃ち分け、傷んだメガはミツルの思いやりで全回復する。自軍メガはサイド3 = 2回取られたら負け。
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
    AttackPlan,
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    attack_cost,
    card_attack_ids,
    damage_on,
    energy_count,
    get_card,
    has_tool,
    is_ex,
    make_agent,
    my_state,
    opp_active_pokemon,
    opp_state,
    option_card,
    option_target,
    payable_attacks,
    read_deck_csv as _read_deck_csv,
    retreat_cost,
)

# ── カードID（デッキ設計_ユキメノコスターミー.md のリスト） ──

SNORUNT = 860         # ユキワラシ HP70 {W}
FROSLASS = 861        # メガユキメノコex HP310 megaEx（サイド3）にげ1 弱点鋼
STARYU = 1030         # ヒトデマン HP70 {W}
STARMIE = 1031        # メガスターミーex HP330 megaEx（サイド3）にげ2 弱点雷

ROTO_STICK = 1077     # 山上4枚からサポートを好きなだけ手札へ
POFFIN = 1086         # HP70以下のたね×2をベンチへ
HAND_TRIMMER = 1087   # 両者手札5枚までトラッシュ（相手から）
NIGHT_STRETCHER = 1097
MEGA_SIGNAL = 1145    # 山からメガシンカexを1枚手札へ
POKE_PAD = 1152       # 非ルール持ちポケモンをサーチ（= たね2種のみ）
HERO_CAPE = 1159      # 最大HP+100（1枚。taksai はユキメノコ 2/2）
SALVATORE = 1189      # セイジ: 山札から直接のせて進化（この番出したたねにも使える）
XEROSIC = 1197        # 相手手札を3枚に
CHEREN = 1224         # 3ドロー
HILDA = 1225          # トウコ: 進化ポケモン+エネをサーチ
LILLIE = 1227         # 手札を戻して6ドロー
WALLY = 1229          # ミツルの思いやり: メガex全回復+エネ手札戻し
SURF_BEACH = 1262     # なみのりビーチ: 番ごと1回、{W}同士の無料入替
W_ENERGY = 3

ATK_CHILLY = 1239         # Snorunt {W} 10
ATK_REFRAIN = 1240        # Froslass {W} 相手手札×50（実測: 手札6=300ちょうど）
ATK_ABS_SNOW = 1241       # Froslass {W}{C}{C} 150 + ねむり（taksai 使用0回）
ATK_WATER_GUN = 1486      # Staryu {W} 20
ATK_JET_BLOW = 1487       # Starmie {W} 120 + ベンチ1匹に50（弱点抵抗なし）
ATK_NEBULA = 1488         # Starmie {C}{C}{C} 210 弱点抵抗・相手バトル場の効果を無視

MEGAS = {FROSLASS, STARMIE}
BASICS = {SNORUNT, STARYU}
FROSLASS_LINE = {SNORUNT, FROSLASS}
STARMIE_LINE = {STARYU, STARMIE}
# E-4: ベンチ50スナイプで最低HPより優先するエンジン駒（taksai 実測: Spiritomb70 より Gabite100）
ENGINE_PIECES = {380, 742, 646, 647}   # Gabite / Kadabra / Impidimp / Morgrem


class FroslassStarmiePolicy(BasePolicy):
    DECK_NAME = "froslass_starmie"
    GO_FIRST = True            # R-21 確定（2026-07-11 実測: taksai の IS_FIRST 4/4 が YES）
    TAKE_MULLIGAN = True       # R-22【ハード・プロジェクト決定】
    ATTACKER_IDS = MEGAS
    ENERGY_IDS = {W_ENERGY}
    LINE_PROTECT_IDS = MEGAS   # R-13（DISCARD は独自実装。最後の1枚を守る）
    ATTACK_ENERGY_TYPE = 3     # 水

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
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size, "bench_free": bench_free,
            "stadium_id": stadium_id, "safe_draws": safe_draws,
            "hand_energy": hc[W_ENERGY],
            "fro_line": fc[SNORUNT] + fc[FROSLASS],
            "star_line": fc[STARYU] + fc[STARMIE],
            "opp_hand": opp_state(obs).handCount,
        }

    def _safe_draws(self):
        if self.t.get("lethal") is not None:
            return 999
        return self.p.get("safe_draws", 999)

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場のメガ（861/1031）のどれかがエネ1枚以上（= 主力技を払える）。"""
        return any(p.id in MEGAS and energy_count(p) >= 1 for p in all_my_pokemon(obs))

    def attack_damage(self, obs, attacker, attack_id):
        if attack_id == ATK_REFRAIN:
            # うらみぶし: 相手の手札×50（2026-07-11 実測: 手札6=300ちょうど）
            return 50 * opp_state(obs).handCount
        return attack_base_damage(attack_id)

    # ── E-1/E-2 の共通材料: そのポケモンの「最良技」ランク ──

    def _attack_rank(self, obs, pk, extra_energy):
        """(kills, jet_pref, dmg, aid)。extra_energy=1 で手張り1枚を仮定。
        KO できる技 > 最大打点。KO同士なら JetBlow 優先（ベンチ50が乗る。taksai 実測）。"""
        if pk is None:
            return (0, 0, -1, None)
        opp_act = opp_active_pokemon(obs)
        budget = energy_count(pk) + extra_energy
        best = (0, 0, -1, None)
        for aid in card_attack_ids(pk.id):
            cost = attack_cost(aid)
            if cost is None or budget < len(cost):
                continue
            dmg = self.attack_damage(obs, pk, aid)
            if opp_act is not None:
                dmg = self.guard_damage(dmg, pk, opp_act)
            kills = 1 if (opp_act is not None and dmg >= opp_act.hp) else 0
            jet = 1 if (kills and aid == ATK_JET_BLOW) else 0
            cand = (kills, jet, dmg, aid)
            if cand[:3] > best[:3]:
                best = cand
        return best

    def _extra_energy(self, obs):
        return 1 if (not obs.current.energyAttached
                     and self.p.get("hand_energy", 0) > 0) else 0

    def _beach_available(self, obs):
        """このターンまだ押せる なみのりビーチ の ABILITY が選択肢に残っているか。"""
        yi = obs.current.yourIndex
        try:
            for o in (obs.select.option or []):
                if o.type == OptionType.ABILITY:
                    c = get_card(obs, o.area, o.index, yi)
                    if c is not None and c.id == SURF_BEACH:
                        return True
        except Exception:
            pass
        return False

    def _desired_attacker(self, obs):
        """E-2: 今ターン攻撃させたいポケモン（identity）とそのランク。
        ベンチ候補は「前に出す手段がある」時だけ（ビーチ残 or 退却可能）。"""
        extra = self._extra_energy(obs)
        act = active_pokemon(obs)
        best_pk, best_rank = act, self._attack_rank(obs, act, extra)
        pivot_ok = (self._beach_available(obs)
                    or (act is not None and not obs.current.retreated
                        and energy_count(act) >= retreat_cost(act)))
        if not pivot_ok:
            return best_pk, best_rank
        for pk in my_state(obs).bench:
            if pk is None or pk.id not in MEGAS:
                continue
            # R-08: 前に出すと負け筋のメガは、KO が取れる時以外は候補にしない
            r = self._attack_rank(obs, pk, extra)
            if self.is_threatened(pk) and not r[0]:
                continue
            if r[:3] > best_rank[:3]:
                best_pk, best_rank = pk, r
        return best_pk, best_rank

    def plan_attacks(self, obs):
        """base に加え、なみのりビーチ経由（退却コスト不要）のベンチメガ計画を足す。
        judge_lethal がビーチ・ピボット込みのリーサルを見えるようにする。"""
        plans = super().plan_attacks(obs)
        active = active_pokemon(obs)
        if active is None or not self._beach_available(obs):
            return plans
        if energy_count(active) >= retreat_cost(active):
            return plans          # base が既にベンチ計画を含めている
        for p in my_state(obs).bench:
            if p is None or p.id not in MEGAS:
                continue
            for aid in payable_attacks(p):
                plans.append(AttackPlan(p, aid, self.attack_damage(obs, p, aid),
                                        needs_retreat=True))
        return plans

    # ═══════════════ セットアップコンテキスト（S-1） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # S-1: taksai 実測はどちらも可（同時所持例なし）。スターミー線を優先
            table = {STARYU: 10, SNORUNT: 9}
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # S-1b: taksai はセットアップで出せるたねを出す（3/3 実測）→ base を上書き
            card = option_card(obs, opt)
            if card is not None and card.id in BASICS:
                return 100, "S-1b: setup bench basic (taksai 3/3)"
            return -10000, "setup: bench other"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    # ═══════════════ 優先則（純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        yi = obs.current.yourIndex

        # ── ABILITY 帯（なみのりビーチのピボットが実質唯一） ──
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == SURF_BEACH:
                return self._score_beach(obs)
            # 相手スタジアム等の特性は押さない（ガブ div-G2 と同型: 空振り防止）
            return -1, "skip foreign ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if cid in MEGAS:
                tgt = option_target(obs, opt)
                bonus = 0
                if tgt is not None and energy_count(tgt) >= 1:
                    bonus += 100      # エネ付きのたねを優先して進化（即攻撃圏）
                base = 25000 if cid == STARMIE else 24500
                return base + bonus, "S-3: evolve mega"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            return self._score_retreat(obs)

        if opt.type == OptionType.ATTACK:
            return self._score_attack(obs, opt)

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

    # ── なみのりビーチ ABILITY（E-2 ピボット） ──

    def _score_beach(self, obs):
        active = active_pokemon(obs)
        if active is None:
            return -1, "beach: no active"
        # リーサル計画のベンチアタッカーを無料で前に出す（apply_protocol は ABILITY を
        # 昇格しないため、ここで正帯最上位に置く。LETHAL_BAND 未満）
        lethal = self.t.get("lethal")
        if (lethal is not None and lethal.get("needs_retreat")
                and any(lethal["attacker"] is p for p in my_state(obs).bench if p)):
            return 90000, "R-07: beach pivot to lethal attacker"
        desired, rank = self._desired_attacker(obs)
        if desired is not None and desired is not active:
            # 8700 = 手張り（8500帯）の上: taksai はピボット→手張り→攻撃の順（div-F4改）
            return 8700, "E-2: pivot via Surfing Beach"
        # 詰み回避: 置物アクティブ（技を払えない）はベンチの撃てる駒と無料交代
        if not payable_attacks(active):
            ready = any(pk is not None and payable_attacks(pk)
                        for pk in my_state(obs).bench)
            if ready:
                return 8750, "unstick: beach out of dead active"
        return -1, "beach: keep current attacker"

    # ── RETREAT（ビーチが無い時の代替ピボット） ──

    def _score_retreat(self, obs):
        active = active_pokemon(obs)
        if active is None:
            return -100, "no active"
        desired, rank = self._desired_attacker(obs)
        if desired is not None and desired is not active:
            # ビーチ ABILITY（2800）があればそちらが先に選ばれる（エネ消費なし）
            return 1900, "E-2: retreat to promote better attacker"
        if not payable_attacks(active):
            ready = any(pk is not None and payable_attacks(pk)
                        for pk in my_state(obs).bench)
            if ready:
                return 2000, "unstick: retreat dead active"
        return -100, "avoid retreat"

    # ── ATTACK（E-1/E-3） ──

    def _score_attack(self, obs, opt):
        aid = getattr(opt, "attackId", None)
        active = active_pokemon(obs)
        opp_act = opp_active_pokemon(obs)
        dmg = self.attack_damage(obs, active, aid) if active else 0
        eff = self.guard_damage(dmg, active, opp_act) if opp_act is not None else dmg
        kills = opp_act is not None and eff >= opp_act.hp
        if kills:
            # E-1: KO > 最大打点。KO同士は JetBlow（ベンチ50）優先
            return 2400 + (20 if aid == ATK_JET_BLOW else 0), "E-1: KO attack"
        score = 1200 + min(eff, 800) // 2
        if aid == ATK_JET_BLOW:
            score += 40           # ベンチ50のチップ分
        elif aid == ATK_ABS_SNOW:
            score += 30           # ねむり分（taksai 未使用。実質ネビュラ以下）
        return score, "E-1: attack (max damage)"

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
            # div-F1（2026-07-12 divergence 実測）: taksai は余ったたねを手札に温存する
            # （human=END / ours=PLAY Staryu が最多クラスタ）。ライン2枚未満の時だけ出す
            bench_empty = len([b for b in my_state(obs).bench if b]) == 0
            if bench_empty:
                # 18950 = 手張り（19000帯）の直下: taksai は空ベンチでも手張りを先に行う
                return 18950, "play basic (empty bench, avoid donk)"
            if p["bench_free"] <= 1:
                return -5000, "R-24: keep bench slot"
            if cid == STARYU and p["star_line"] < 2:
                return 14500, "S-2: play Staryu (line need)"
            if cid == SNORUNT and p["fro_line"] < 2:
                return 14400, "S-2: play Snorunt (line need)"
            return -1, "div-F1: hold spare basic"

        # スタジアム
        if cid == SURF_BEACH:
            if p["stadium_id"] == SURF_BEACH:
                return -1, "beach already up"
            # div-F9（2026-07-12 divergence 実測）: taksai の設置は T3 以降 = メガが場に
            # 出てから（ピボット価値が生まれてから）。それまで温存（human=END/ATTACK）
            if fc[FROSLASS] + fc[STARMIE] >= 1:
                return 16000, "S-2: Surfing Beach (pivot engine)"
            return -1, "div-F9: hold beach until mega in play"

        # グッズ
        if cid == POFFIN:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Poffin)"
            need = (p["fro_line"] < 2) or (p["star_line"] < 2)
            if not combat:
                return (18000 if need else 8000), "S-2: Poffin"
            return (12000 if need else -1), "Poffin: rebuild"
        if cid == POKE_PAD:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Pad)"
            need = (fc[SNORUNT] + hc[SNORUNT] < 1) or (fc[STARYU] + hc[STARYU] < 1)
            if not combat:
                return (17000 if need else 7000), "S-4: Poke Pad"
            return (11000 if need else -1), "Poke Pad: rebuild"
        if cid == MEGA_SIGNAL:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Signal)"
            megas_in_hand = hc[FROSLASS] + hc[STARMIE]
            evolvable = fc[SNORUNT] + fc[STARYU] >= 1
            if megas_in_hand == 0 and evolvable:
                return 17200, "S-4: Mega Signal (mega missing)"
            # div-F3（2026-07-12 divergence 実測）: 用が無い時は温存（human=ATTACK/ours=Signal）
            return -1, "div-F3: hold Mega Signal"
        if cid == HAND_TRIMMER:
            # E-6: うらみぶし予定時は撃たない（自分の弾を減らす逆シナジー）
            _, rank = self._desired_attacker(obs)
            if (p["opp_hand"] >= 7 and p["hand_size"] <= 5
                    and rank[3] != ATK_REFRAIN):
                return 9000, "E-6: Hand Trimmer (disrupt big hand)"
            return -1, "save Hand Trimmer"
        if cid == NIGHT_STRETCHER:
            if dc[FROSLASS] + dc[STARMIE] + dc[SNORUNT] + dc[STARYU] >= 1:
                return 13000, "Night Stretcher: recover pokemon"
            if dc[W_ENERGY] >= 1 and p["hand_energy"] == 0:
                return 11000, "Night Stretcher: recover energy"
            return -1, "Night Stretcher: nothing"

        # サポート（択一）
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == SALVATORE:
            # S-3: 山から直接のせて進化（ポフィンで出したばかりのたねにも使える）
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Salvatore)"
            evolvable = fc[SNORUNT] + fc[STARYU] >= 1
            megas_known = (fc[FROSLASS] + hc[FROSLASS] + dc[FROSLASS]
                           + fc[STARMIE] + hc[STARMIE] + dc[STARMIE])
            if evolvable and megas_known < 6:
                return (16000 if not combat else 14000), "S-3: Salvatore (evolve from deck)"
            return -1, "Salvatore: no target"
        if cid == WALLY:
            # E-5: 傷んだメガを全回復（エネは1枚戻すだけ = 実質ノーコスト）
            bench_hurt = any(pk.id in MEGAS and damage_on(pk) >= 150
                             for pk in my_state(obs).bench if pk)
            active = active_pokemon(obs)
            active_hurt = (active is not None and active.id in MEGAS
                           and damage_on(active) >= 200)
            if active_hurt and not obs.current.energyAttached and p["hand_energy"] >= 1:
                # 手張り（8500帯）より先に回復してエネを戻し、その後張り直す
                return 8800, "E-5: Wally heal active (re-attach after)"
            if bench_hurt:
                return 5600, "E-5: Wally heal bench mega"
            return -1, "save Wally"
        if cid == LILLIE:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Lillie)"
            return (5300 if p["hand_size"] <= 5 else -1), "E-5: Lillie (main draw)"
        if cid == HILDA:
            if self._safe_draws() < 2:
                return -1, "R-11: deck thin (Hilda)"
            missing_mega = (hc[FROSLASS] + hc[STARMIE] == 0
                            and fc[SNORUNT] + fc[STARYU] >= 1
                            and fc[FROSLASS] + fc[STARMIE] < 2)
            if missing_mega:
                return 5000, "S-4: Hilda (mega + energy)"
            # div-F6（2026-07-12 divergence 実測）: エネ切れ目的は交戦期に撃たない（human=END）
            if p["hand_energy"] == 0 and not combat:
                return 4900, "S-4: Hilda (energy)"
            return -1, "save Hilda"
        if cid == CHEREN:
            if self._safe_draws() < 3:
                return -1, "R-11: deck thin (Cheren)"
            return (4800 if p["hand_size"] <= 4 else -1), "Cheren (filler draw)"
        if cid == XEROSIC:
            # div-F7（2026-07-12 divergence 実測）: 能動的には撃たない（閾値8/10とも
            # human=END の過発火。相手手札はうらみぶしの弾でもある）。temperance
            return -1, "div-F7: save Xerosic"
        if cid == ROTO_STICK:
            if self._safe_draws() < 1:
                return -1, "R-11: deck thin (Roto-Stick)"
            # div-F2（2026-07-12 divergence 実測）: taksai はポフィン/パッド/シグナルより後、
            # 交戦期は手札が細い時だけ（human=ATTACK / ours=Roto-Stick）
            if not combat:
                return 15500, "S-4: Roto-Stick (supporters)"
            return (12500 if p["hand_size"] <= 4 else -1), "Roto-Stick: thin hand only"
        if cid == mt.BOSS:
            # E-7: 非リーサルでは温存（リーサルは apply_protocol が昇格）
            return -1, "E-7: save Boss for lethal"
        return 1000, "generic play"

    # ── ATTACH（S-5 + R-08） ──

    def _score_attach(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        if cid == HERO_CAPE:
            if has_tool(target):
                return -1, "target has tool"
            table = {FROSLASS: 12800, STARMIE: 12000}   # taksai: ユキメノコ 2/2
            if tid in table:
                return table[tid], "Hero's Cape (+100)"
            return -1, "save Hero's Cape"

        if cid != W_ENERGY:
            return -500, "skip non-energy"
        if obs.current.energyAttached:
            return -1, "already attached"

        # 詰み回避: 技も退却も払えない置物アクティブに退却分を張る
        # （ビーチがあれば ABILITY 側で解決するのでここはビーチ無し時の保険）
        active = active_pokemon(obs)
        if (target is active and active is not None
                and p["stadium_id"] != SURF_BEACH
                and not payable_attacks(active)
                and energy_count(active) < retreat_cost(active)
                and any(pk.id in MEGAS and energy_count(pk) >= 1
                        for pk in my_state(obs).bench if pk)):
            return 8400, "unstick: energize active to retreat"

        # div-F4改（2026-07-12 divergence 実測・第3周）: taksai の手張りはターン後半
        # （スタジアム/グッズ/ビーチのピボットの後、攻撃の直前）→ 8000 帯に置く
        # div-F8（同・ATTACH 対象13件の実測）: バトル場を優先（+150）し、e1 への
        # 重ね張り（+60）を e0 への分散より好む
        e = energy_count(target)
        desired, rank = self._desired_attacker(obs)
        score, reason = -1, "attach: no target"
        if (target is desired and rank[3] is not None
                and e < len(attack_cost(rank[3]) or [1])):
            score, reason = 8500, "S-5: fuel desired attacker"
        elif tid in MEGAS:
            if e >= 3 or (tid == FROSLASS and e >= 2):
                return -1, "R-10: mega fueled"
            if tid == STARMIE and e >= 2:
                # ネビュラ 210 が現バトル場を KO でき JetBlow ではできない時だけ3枚目
                opp_act = opp_active_pokemon(obs)
                if opp_act is not None:
                    neb = self.guard_damage(210, target, opp_act)
                    jet = self.guard_damage(120, target, opp_act)
                    if neb >= opp_act.hp > jet:
                        return 8280, "S-5: 3rd energy for Nebula KO"
                return -1, "R-10: Starmie e2"
            # div-F8b（2026-07-12 divergence 実測・第4周）: 主力技（1エネ）を払える
            # バトル場には重ねない（taksai は次のアタッカーのベンチに先置きする）
            if target is active and e >= 1:
                return -1, "div-F8b: active fueled (pre-load bench)"
            score = (8180 + (30 if tid == STARMIE else 0)
                     + (150 if target is active else 0)
                     - (80 if e == 1 else 0))
            reason = "S-5: fuel mega (div-F8)"
        elif tid in BASICS:
            if target is active and e >= 1:
                return -1, "div-F8b: active fueled (pre-load bench)"
            if e < 1:
                score = (7900 - (10 if tid == SNORUNT else 0)
                         + (150 if target is active else 0))
                reason = "S-5: pre-load basic"
            elif e == 1 and tid == STARYU:
                score, reason = 7850, "S-5: stack Staryu (div-F8)"
            else:
                return -1, "R-10: basic fueled (evolves anyway)"
        else:
            return -1, "attach: wrong target"
        if score > 0 and self.is_threatened(target):
            score -= 2000   # R-08: 負け筋への追い銭防止
        return score, reason

    # （E-8 マッチアップ上書きは未実装。対ブリジュラスの「ユキメノコ封印」を
    #   A/B したが 100戦で 16% vs 19% = 効果なしのため撤去。未決事項1を参照）

    # ── NUMBER（R-11 キャップ） ──

    def score_number(self, obs, opt):
        n = opt.number or 0
        if n > self._safe_draws():
            return -100 - n, "R-11: cap draw count"
        return n, "number"

    # ── CARD/ENERGY 選択（サーチ先・前出し・スナイプ等） ──

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
                if card is None:
                    return 0, "promote none"
                extra = self._extra_energy(obs)
                rank = self._attack_rank(obs, card, extra)
                score = 8000 + rank[0] * 6000 + min(max(rank[2], 0), 990)
                if cid in MEGAS:
                    score += 500
                reason = "E-2: promote best attacker"
                if rank[0] or ctx == SelectContext.TO_ACTIVE:
                    # div-F5（2026-07-12 divergence 実測）: KO が取れる時と KO後の建て直しは
                    # R-08 を適用しない（taksai は被KO圏でもメガを前に出して攻撃を続ける。
                    # このデッキはメガ以外に打点が無く、たね壁はテンポ負け）
                    return score, "div-F5: promote attacker (skip R-08)"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            # 相手側（ボス吊り出し等）: 低HPを引きずり出す
            hp = getattr(card, "hp", 999) if card else 999
            return 10000 - hp, "boss: drag lowest HP"

        if ctx in (SelectContext.DAMAGE, SelectContext.DAMAGE_COUNTER):
            # E-4: JetBlow のベンチ50。HP50以下 = 即KO最優先 > エンジン駒 > 最低HP
            if card is not None and pi != yi:
                hp = getattr(card, "hp", 999)
                if hp <= 50:
                    return 20000 + (50 - hp), "E-4: bench snipe KO"
                score = 10000 - hp
                if cid in ENGINE_PIECES:
                    score += 35    # taksai 実測: Spiritomb70 より Gabite100
                if is_ex(card) and damage_on(card) > 0:
                    score += 25    # 傷んだ大物に蓄積
                return score, "E-4: bench snipe (R-15 lowest HP)"
            return 0, "damage none"

        if ctx == SelectContext.TO_HAND:
            base = 100 - hc.get(cid, 0) * 40
            if cid in MEGAS:
                line_basic = fc[SNORUNT] if cid == FROSLASS else fc[STARYU]
                line_mega = (fc[cid] + hc[cid])
                need = line_basic >= 1 and line_mega < 1
                bonus = 80 if need else 20
                if cid == STARMIE:
                    bonus += 2    # スターミー線がメイン打点
                return base + bonus, "S-4: take mega"
            if cid in BASICS:
                # 薄いラインのたねから取る（div: human=Snorunt/ours=Staryu の線数差）
                line = p["star_line"] if cid == STARYU else p["fro_line"]
                line += hc.get(cid, 0)
                return base + (62 - 15 * min(line, 3) if line < 2 else 10), "S-4: take basic"
            if cid == W_ENERGY:
                return base + (55 if p["hand_energy"] == 0 else 0), "take energy"
            # ロトりぼう等のサポート択（全部取ってよい: 正スコア維持）
            if cid == LILLIE:
                return base + 74, "take Lillie"
            if cid == SALVATORE:
                bonus = 70 if fc[SNORUNT] + fc[STARYU] >= 1 else 35
                return base + bonus, "take Salvatore"
            if cid == WALLY:
                hurt = any(pk.id in MEGAS and damage_on(pk) >= 100
                           for pk in all_my_pokemon(obs))
                return base + (64 if hurt else 30), "take Wally"
            if cid == HILDA:
                return base + 46, "take Hilda"
            if cid == CHEREN:
                return base + 44, "take Cheren"
            if cid == mt.BOSS:
                return base + 40, "take Boss"
            if cid == XEROSIC:
                return base + 30, "take Xerosic"
            return base, "take other"

        if ctx == SelectContext.TO_BENCH:
            # ポフィンのベンチ出し: ライン枚数の少ない方から
            if cid == STARYU:
                return 100 - 30 * p["star_line"], "S-2: bench Staryu"
            if cid == SNORUNT:
                return 95 - 30 * p["fro_line"], "S-2: bench Snorunt"
            return 10, "bench other"

        if ctx == SelectContext.EVOLVES_FROM:
            # セイジの進化元: エネ付き > バトル場 > たね
            if card is None:
                return 0, "evolve from none"
            score = 100
            if energy_count(card) >= 1:
                score += 50
            ms = my_state(obs)
            if ms.active and card is ms.active[0]:
                score += 30
            if cid == STARYU:
                score += 5     # スターミー線優先
            return score, "S-3: Salvatore target"

        if ctx == SelectContext.EVOLVES_TO:
            # セイジの進化先: 進化元がいてメガ未着手のラインを優先
            if cid == STARMIE:
                need = fc[STARYU] >= 1 and fc[STARMIE] < 1
                return (120 if need else 60), "S-3: Salvatore -> Starmie"
            if cid == FROSLASS:
                need = fc[SNORUNT] >= 1 and fc[FROSLASS] < 1
                return (115 if need else 55), "S-3: Salvatore -> Froslass"
            return 10, "evolve to other"

        if ctx == SelectContext.HEAL:
            # ミツルの思いやり: 一番傷んだメガ
            if card is None:
                return 0, "heal none"
            return damage_on(card) + (1000 if cid in MEGAS else 0), "E-5: heal most damaged"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            # R-13 の適用: エネ（9枚のみ）と最後のメガを守り、重複と余剰サポートから捨てる
            ids = [c.id for c in (my_state(obs).hand or []) if c]
            if cid == W_ENERGY:
                if ids.count(W_ENERGY) >= 3:
                    return 5000, "discard surplus energy"
                return -3000, "keep energy (9 only)"
            if cid in MEGAS:
                if ids.count(cid) > 1:
                    return 7000, "discard duplicate mega"
                return -4000, "R-13: keep last mega"
            if cid in (POFFIN, POKE_PAD, MEGA_SIGNAL, ROTO_STICK, SURF_BEACH,
                       HAND_TRIMMER, NIGHT_STRETCHER) and ids.count(cid) > 1:
                return 12000, "discard duplicate item/stadium"
            # div: taksai はリーリエ（メインドロー）の2枚目より先にチェレン等を捨てる
            if cid == XEROSIC:
                return 9600, "discard Xerosic"
            if cid == CHEREN:
                return 9550, "discard Cheren"
            if cid in (WALLY, HILDA) and ids.count(cid) > 1:
                return 9500, "discard duplicate supporter"
            if cid in (WALLY, HILDA):
                return 9100, "discard spare supporter"
            if cid == LILLIE:
                return (9400 if ids.count(cid) > 1 else 8900), "discard Lillie"
            if cid in BASICS and fc[cid] + ids.count(cid) > 2:
                return 8000, "discard extra basic (searchable)"
            if cid == mt.BOSS:
                return 2000, "discard Boss (last resort)"
            return 4000, "generic discard"

        if ctx == SelectContext.TO_DECK:
            return 10, "to deck"

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: def agent は必ずファイル末尾の callable にする。

_impl = make_agent(FroslassStarmiePolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
