"""GenericPolicy — 任意の60枚リストを「そこそこ回せる相手役」にする汎用 BasePolicy。

用途: (1) ガントレット（scripts/gauntlet.py）の相手プール量産、
(2) ターン内探索（turn_search.py）の rollout での相手役パイロット。
(2) のため 2026-07-10 から sync_base の対象 = **Kaggle 提出物に入る**。

設計参照: ptcg-abc の GenericPolicy / make_generic_agent（無ライセンスのためコードは新規実装。
本実装は当プロジェクト BasePolicy の汎用プランビルダー + デフォルトスコアラーを土台にする）。

方針（プラン「ドラパルト制圧」Phase 1-1）:
  - クラス属性はデッキリストから自動導出:
      ATTACKER_IDS   = 攻撃持ちポケモン全部（ダメージ>0 の技を持つもの。無ければ技持ち全部）
      ENERGY_IDS     = リスト内のエネルギーカード
      LINE_PROTECT_IDS = 進化トップ + アタッカーラインの進化パーツ（R-13）
      LINE_MAX_COST  = ライン最大の技コスト（R-10 のエネ規律に使用）
  - 3フックは汎用実装: judge_subgoal =「payable な攻撃者が場にいる」、
    優先則 = R-04 帯の汎用スコア（展開 > 進化 > エネ > 攻撃）、既定 GO_FIRST=True / TAKE_MULLIGAN=True
  - トップピロットではなく「クラッシュせずデッキのゲームプランを一応実行する公平な相手」が目標。
"""
from collections import defaultdict

from cg.api import AreaType, CardType, OptionType, Pokemon, SelectContext

from policy_base import (
    BasePolicy,
    CARD_DB,
    active_pokemon,
    attack_base_damage,
    attack_cost,
    card_attack_ids,
    energy_count,
    hand_ids,
    has_tool,
    make_agent,
    my_state,
    opp_active_pokemon,
    option_card,
    option_target,
    payable_attacks,
    retreat_cost,
    all_my_pokemon,
)


def _payable_damage_attacks(pokemon):
    """今エネが足りていてダメージが出る技のリスト。"""
    return [aid for aid in payable_attacks(pokemon or None)
            if attack_base_damage(aid) > 0]


class GenericPolicy(BasePolicy):
    """汎用相手役。ファクトリ（make_generic_policy）がクラス属性を差し替えて使う。

    プレースホルダ値は __init_subclass__ の必須属性検査（非 None）を通すためのもの。
    直接このクラスを make_agent に渡さないこと（属性が空でまともに動かない）。
    """
    DECK_NAME = "generic"
    GO_FIRST = True             # R-21: 汎用既定（デッキ毎データが無い相手役のため一律）
    TAKE_MULLIGAN = True        # R-22【ハード・ユーザー決定 2026-07-07】
    ATTACKER_IDS = frozenset()
    ENERGY_IDS = frozenset()
    LINE_PROTECT_IDS = frozenset()

    # ── 追加の導出属性（ファクトリが設定） ──
    LINE_MAX_COST = {}          # card_id -> ライン最大技コスト（R-10）
    PREEVO_IDS = frozenset()    # デッキ内に進化先が存在するポケモン（サーチ優先の材料）

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0 汎用形: 場のどれかが「ダメージの出る技」を今払えるなら交戦期。"""
        return any(_payable_damage_attacks(pk) for pk in all_my_pokemon(obs))

    # ═══════════════ 優先則（R-04 帯の汎用スコア: 展開 > 進化 > エネ > 攻撃） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    def _deck_thin(self, obs):
        """R-11 簡易形: 山札僅少ならドロー系の行動を止める（リーサル確定時は解除）。"""
        if self.t.get("lethal") is not None:
            return False
        return my_state(obs).deckCount <= 6

    def _score_any(self, obs, opt):
        if opt.type == OptionType.ABILITY:
            # 特性は原則毎ターン起動（R-04 最上位帯）。山札僅少時のみ辞退
            if self._deck_thin(obs):
                return -1, "R-11: deck thin (ability)"
            return 26000, "generic: use ability"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            data = CARD_DB.get(card.id) if card else None
            bonus = 500 if data is not None and (getattr(data, "ex", False)
                                                 or getattr(data, "megaEx", False)) else 0
            return 18000 + bonus, "generic: evolve"

        if opt.type == OptionType.RETREAT:
            return self._score_retreat(obs)

        if opt.type == OptionType.ATTACK:
            active = active_pokemon(obs)
            dmg = self.attack_damage(obs, active, getattr(opt, "attackId", 0)) if active else 0
            score = 1000 + dmg
            opp_act = opp_active_pokemon(obs)
            if opp_act is not None and dmg > 0 and \
                    self.guard_damage(dmg, active, opp_act) >= opp_act.hp:
                score += 800   # KO 選好（取り切りは R-07 が LETHAL_BAND へ昇格する）
            return score, "generic: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY, OptionType.ENERGY_CARD):
            return self._score_card(obs, opt)

        return 10, "generic: fallback"

    # ── PLAY（展開 > トレーナーズ） ──

    def _score_play(self, obs, opt):
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        data = CARD_DB.get(card.id)
        if data is None:
            return 0, "play unknown"

        if data.cardType == CardType.POKEMON:
            ms = my_state(obs)
            n_in_play = sum(1 for pk in all_my_pokemon(obs) if pk.id == card.id)
            score = 20000 - 400 * n_in_play   # 同名の重ね置きを減点
            if card.id in self.ATTACKER_IDS or card.id in self.PREEVO_IDS:
                score += 300                   # ライン駒を優先展開
            bench_empty = not any(ms.bench)
            bench_free = ms.benchMax - len(ms.bench)
            if bench_empty:
                score += 5000                  # R-03: ドンク回避（ベンチ0を最優先で解消）
            elif bench_free <= 1:
                score -= 5000                  # R-24: ベンチ1枠は空けておく
            return score, "generic: bench basic"

        if data.cardType == CardType.SUPPORTER:
            if obs.current.supporterPlayed:
                return -1, "supporter used"
            if self._deck_thin(obs):
                return -1, "R-11: deck thin (supporter)"
            return 12000, "generic: supporter"

        if data.cardType == CardType.ITEM:
            if self._deck_thin(obs):
                return -1, "R-11: deck thin (item)"
            return 14000, "generic: item"

        if data.cardType == CardType.STADIUM:
            for c in obs.current.stadium:
                if c.id == card.id:
                    return -1, "stadium already up"
            return 9000, "generic: stadium"

        return 8000, "generic: trainer"

    # ── ATTACH（S-5 + R-10: ライン最大コスト到達で付与禁止） ──

    def _score_attach(self, obs, opt):
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        data = CARD_DB.get(card.id)

        if data is not None and data.cardType == CardType.TOOL:
            if has_tool(target):
                return -1, "tool: occupied"
            return (6500 if target.id in self.ATTACKER_IDS else 6000), "generic: tool"

        # エネルギー付与
        need = self.LINE_MAX_COST.get(target.id, 2)
        if need and energy_count(target) >= need:
            return -1, "R-10: line max cost reached"
        score = 8000
        if target.id in self.ATTACKER_IDS:
            score += 500          # アタッカー最優先
        elif target.id in self.PREEVO_IDS:
            score += 300          # ライン先置き
        if opt.inPlayArea == AreaType.ACTIVE:
            score += 100
        if self.is_threatened(target):
            score -= 2000         # R-08: 負け筋への追い銭防止
        return score, "S-5: attach energy"

    # ── RETREAT（攻撃不能アクティブ → 攻撃可能ベンチ） ──

    def _score_retreat(self, obs):
        active = active_pokemon(obs)
        if active is None:
            return -1, "no active"
        if _payable_damage_attacks(active):
            return -100, "active can attack"
        bench_ready = any(pk is not None and _payable_damage_attacks(pk)
                          for pk in my_state(obs).bench)
        if bench_ready and energy_count(active) >= retreat_cost(active):
            return 3000, "generic: retreat to attacker"
        return -100, "avoid retreat"

    # ── CARD/ENERGY 選択（前出し・サーチ・配分・DISCARD） ──

    def _score_card(self, obs, opt):
        ctx = obs.select.context
        yi = obs.current.yourIndex
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        card = option_card(obs, opt)
        cid = card.id if card is not None else getattr(opt, "cardId", None)

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            if pi == yi:
                score = 1000
                if card is not None:
                    if _payable_damage_attacks(card):
                        score = 15000        # 今すぐ殴れる駒を最優先で前へ
                    elif cid in self.ATTACKER_IDS:
                        score = 8000
                    score += energy_count(card) * 100 + getattr(card, "hp", 0)
                return self.default_score_promote(obs, opt, score, "generic: promote")  # R-08
            return self.default_score_damage_target(obs, opt)   # 吊り出しは R-15（低HP優先）

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            return self.default_score_discard(obs, opt)          # R-13

        if ctx in (SelectContext.DAMAGE,
                   getattr(SelectContext, "DAMAGE_COUNTER", SelectContext.DAMAGE),
                   getattr(SelectContext, "DAMAGE_COUNTER_ANY", SelectContext.DAMAGE)):
            return self.default_score_damage_target(obs, opt)    # R-15

        if ctx in (SelectContext.TO_HAND, SelectContext.TO_BENCH,
                   SelectContext.TO_FIELD, getattr(SelectContext, "ATTACH_TO", SelectContext.TO_FIELD)):
            return self._score_take(obs, opt, card, cid)

        if ctx == SelectContext.TO_DECK:
            return 10, "generic: to deck"

        return 10, "generic card"

    def _score_take(self, obs, opt, card, cid):
        """サーチ先・エネ加速先の汎用優先: アタッカーライン > エネ（手札に無ければ） > その他。"""
        # 場のポケモンが対象（エネ加速の付与先など）: R-10 と同じ規律で
        if isinstance(card, Pokemon):
            need = self.LINE_MAX_COST.get(cid, 2)
            if need and energy_count(card) >= need:
                return 1, "R-10: line max cost reached (accel)"
            score = 100
            if cid in self.ATTACKER_IDS:
                score += 90
            elif cid in self.PREEVO_IDS:
                score += 60
            return score, "generic: accel target"

        if cid is None:
            return 0, "take none"
        score = 100
        if cid in self.ATTACKER_IDS:
            score += 90
        elif cid in self.PREEVO_IDS:
            score += 70
        elif cid in self.ENERGY_IDS:
            has_energy = any(h in self.ENERGY_IDS for h in hand_ids(obs))
            score += 5 if has_energy else 50
        else:
            data = CARD_DB.get(cid)
            score += 30 if data is not None and data.cardType == CardType.POKEMON else 10
        score -= hand_ids(obs).count(cid) * 20   # 同名重複の割引
        return score, "generic: take"


# ═══════════════ ファクトリ（デッキリスト → クラス属性の自動導出） ═══════════════

def _derive_config(deck_ids):
    """60枚リストからクラス属性一式を導出する。"""
    ids = set(deck_ids)
    pokes = [cid for cid in ids
             if CARD_DB.get(cid) is not None and CARD_DB[cid].cardType == CardType.POKEMON]

    # デッキ内の進化関係（名前ベース: evolvesFrom はカード名）
    by_name = {}
    for cid in pokes:
        by_name.setdefault(CARD_DB[cid].name, cid)
    children = defaultdict(list)   # cid -> デッキ内でそこから進化するカード
    for cid in pokes:
        ev_from = getattr(CARD_DB[cid], "evolvesFrom", None)
        if ev_from and ev_from in by_name:
            children[by_name[ev_from]].append(cid)

    def line_ids(cid):
        out, stack = [cid], [cid]
        while stack:
            for ch in children.get(stack.pop(), []):
                if ch not in out:
                    out.append(ch)
                    stack.append(ch)
        return out

    # R-10: ライン最大コスト（自分+デッキ内の進化先の技コスト最大）
    line_max = {}
    for cid in pokes:
        costs = [0]
        for lc in line_ids(cid):
            for aid in card_attack_ids(lc):
                c = attack_cost(aid)
                if c is not None:
                    costs.append(len(c))
        line_max[cid] = max(costs)

    # ATTACKER_IDS = 攻撃持ちポケモン全部（ダメージ>0 の技を優先。無ければ技持ち全部）
    attackers = {cid for cid in pokes
                 if any(attack_base_damage(a) > 0 for a in card_attack_ids(cid))}
    if not attackers:
        attackers = {cid for cid in pokes if card_attack_ids(cid)}

    energies = {cid for cid in ids
                if CARD_DB.get(cid) is not None
                and CARD_DB[cid].cardType in (CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY)}

    # LINE_PROTECT = 進化トップ（誰も進化しない駒）+ アタッカーラインの進化パーツ（R-13）
    tops = {cid for cid in pokes if not children.get(cid)}
    protect = set(tops)
    for cid in pokes:
        if any(lc in attackers for lc in line_ids(cid)):
            protect.add(cid)

    preevo = {cid for cid in pokes if children.get(cid)}

    return {
        "ATTACKER_IDS": frozenset(attackers),
        "ENERGY_IDS": frozenset(energies),
        "LINE_PROTECT_IDS": frozenset(protect),
        "LINE_MAX_COST": dict(line_max),
        "PREEVO_IDS": frozenset(preevo),
    }


def make_generic_policy(deck_ids, name="generic"):
    """デッキリストから GenericPolicy のサブクラス（クラス属性導出済み）を作る。
    BasePolicy.__init_subclass__ の必須属性検査を通すため type() で属性込みで生成する。"""
    attrs = _derive_config(deck_ids)
    attrs.update({
        "DECK_NAME": f"generic_{name}",
        "GO_FIRST": True,        # 既定（プラン Phase 1-1）
        "TAKE_MULLIGAN": True,   # R-22
    })
    return type(f"GenericPolicy_{name}", (GenericPolicy,), attrs)


def make_generic_agent(deck_ids, name="generic"):
    """任意の60枚リスト → agent(obs_dict) 関数（R-01/R-02 の安全ラッパー込み）。"""
    return make_agent(make_generic_policy(deck_ids, name))
