"""盤面価値モデル V(s) — 特徴量抽出と numpy 推論（train/serve 共通の正本）。

正本は agents/_base/value_model.py。各エージェントdirへは scripts/sync_base.py で同期する。
訓練側（training/extract_value_dataset.py, train_value.py）も**このモジュールを import する**
（train/serve skew の排除。実験計画 §6-3 の「実装＝ロギング」と同じ思想）。

役割:
  - extract_features(obs, perspective): 観測 → 視点プレイヤー基準の特徴ベクトル
    （見えている情報のみ。エピソードの obs にも探索葉の obs にも同じ関数を当てる）
  - ValueModel.load(path): npz から重みを読む numpy MLP。predict(x) = P(視点プレイヤーが勝つ)
  - 依存は cg.api と numpy のみ（提出環境で動く）

特徴量を変えたら FEATURE_VERSION を上げること。npz 側の feature_version と一致しない
モデルはロードを拒否する（黙って壊れた予測を返すより、V なし＝rollout 継続に落ちる方が安全）。
"""
import os

import numpy as np

from cg.api import CardType, all_attack, all_card_data

import meta_tables as mt

FEATURE_VERSION = 3   # v2: 自手札の中身 / v3: 両者のアーキタイプ one-hot（条件付き V）

# アーキタイプ辞書（順序固定。meta_tables が増えたら FEATURE_VERSION を上げること）
ARCH_LIST = sorted(mt.ARCHETYPES.keys())

_CARD_DB = {c.cardId: c for c in all_card_data()}
_ATTACK_DB = {a.attackId: a for a in all_attack()}


def _attack_ids(card_id):
    card = _CARD_DB.get(card_id)
    return list(getattr(card, "attacks", None) or []) if card else []


def _attack_cost(attack_id):
    atk = _ATTACK_DB.get(attack_id)
    return len(getattr(atk, "energies", []) or []) if atk else 99


def _attack_damage(attack_id):
    atk = _ATTACK_DB.get(attack_id)
    return int(getattr(atk, "damage", 0) or 0) if atk else 0


def _best_payable_damage(pokemon):
    """エネが足りている技の最大打点（可変打点は基礎値）。"""
    if pokemon is None:
        return 0.0
    n_energy = len(pokemon.energies or [])
    best = 0
    for aid in _attack_ids(pokemon.id):
        if _attack_cost(aid) <= n_energy:
            best = max(best, _attack_damage(aid))
    return float(best)


def _pokemon_block(pk):
    """1体ぶんの特徴（8個）。不在は全ゼロ。"""
    if pk is None:
        return [0.0] * 8
    max_hp = float(pk.maxHp or 1)
    return [
        1.0,
        pk.hp / 340.0,
        (max_hp - pk.hp) / 340.0,            # 乗っているダメージ
        max_hp / 340.0,
        len(pk.energies or []) / 4.0,
        1.0 if pk.tools else 0.0,
        len(pk.preEvolution or []) / 2.0,     # 進化段階
        _best_payable_damage(pk) / 340.0,
    ]


def _side_block(ps):
    """片側プレイヤーの特徴（アクティブ8 + ベンチ集約6 + ゾーン5 + 状態異常2 = 21個）。"""
    feats = []
    active = ps.active[0] if ps.active else None
    feats += _pokemon_block(active)

    bench = [p for p in (ps.bench or []) if p is not None]
    n_bench = len(bench)
    feats += [
        n_bench / 5.0,
        sum(len(p.energies or []) for p in bench) / 8.0,
        sum(p.hp for p in bench) / 1000.0,
        sum((p.maxHp - p.hp) for p in bench) / 600.0,          # ベンチの被ダメ合計
        max((_best_payable_damage(p) for p in bench), default=0.0) / 340.0,
        sum(1 for p in bench if p.preEvolution) / 5.0,          # 進化済みベンチ数
    ]
    feats += [
        len(ps.prize) / 6.0,                                    # 残りサイド（少ないほど勝ちに近い）
        ps.deckCount / 60.0,
        ps.handCount / 10.0,
        len(ps.discard) / 60.0,
        sum(1 for c in ps.discard
            if (_CARD_DB.get(c.id) is not None
                and _CARD_DB[c.id].cardType in (CardType.BASIC_ENERGY,
                                                CardType.SPECIAL_ENERGY))) / 15.0,
        1.0 if (ps.poisoned or ps.burned) else 0.0,
        1.0 if (ps.asleep or ps.paralyzed or ps.confused) else 0.0,
    ]
    return feats


def _hand_block(ps, board_names):
    """視点プレイヤーの手札の中身（11個）。手札が見えない（相手視点の obs を自視点で
    評価しようとした等）場合は全ゼロ = 「情報なし」として扱う。

    board_names: 自分の場のポケモン名の集合（進化先を握っているかの判定に使う）。"""
    if not ps.hand:
        return [0.0] * 11
    n = {k: 0.0 for k in ("basic_pkm", "evo_pkm", "evo_match", "item", "tool",
                          "supporter", "stadium", "b_energy", "s_energy", "boss")}
    for card in ps.hand:
        data = _CARD_DB.get(card.id)
        if data is None:
            continue
        ct = data.cardType
        if ct == CardType.POKEMON:
            if getattr(data, "basic", False):
                n["basic_pkm"] += 1
            else:
                n["evo_pkm"] += 1
                if getattr(data, "evolvesFrom", None) in board_names:
                    n["evo_match"] += 1     # 場の進化元に今すぐ乗る進化先
        elif ct == CardType.ITEM:
            n["item"] += 1
        elif ct == CardType.TOOL:
            n["tool"] += 1
        elif ct == CardType.SUPPORTER:
            n["supporter"] += 1
        elif ct == CardType.STADIUM:
            n["stadium"] += 1
        elif ct == CardType.BASIC_ENERGY:
            n["b_energy"] += 1
        elif ct == CardType.SPECIAL_ENERGY:
            n["s_energy"] += 1
        if card.id == mt.BOSS:
            n["boss"] += 1                  # 呼び出し（ゲームを決める1枚なので専用枠）
    return [
        n["basic_pkm"] / 4.0, n["evo_pkm"] / 4.0, n["evo_match"] / 3.0,
        n["item"] / 5.0, n["tool"] / 2.0, n["supporter"] / 4.0, n["stadium"] / 2.0,
        n["b_energy"] / 4.0, n["s_energy"] / 2.0, n["boss"] / 2.0,
        1.0,                                # 手札可視フラグ（全ゼロ=不可視との区別）
    ]


def _board_names(ps):
    names = set()
    for pk in list(ps.active) + list(ps.bench):
        if pk is None:
            continue
        data = _CARD_DB.get(pk.id)
        if data is not None:
            names.add(data.name)
    return names


def _arch_onehot(ps):
    """盤面（場 + 進化元 + トラッシュ）からアーキタイプを判定して one-hot（12個）。
    R-20 と同じ「カードID集合との交差」方式。序盤で判定不能なら最後の枠（unknown）。
    訓練データもエージェント推論も**この同じ関数**を通る（train/serve 一致）。"""
    ids = set()
    for pk in list(ps.active) + list(ps.bench):
        if pk is None:
            continue
        ids.add(pk.id)
        for c in pk.preEvolution:
            ids.add(c.id)
    for c in ps.discard:
        ids.add(c.id)
    vec = [0.0] * (len(ARCH_LIST) + 1)
    for i, name in enumerate(ARCH_LIST):
        if ids & mt.ARCHETYPES[name]:
            vec[i] = 1.0
            return vec
    vec[-1] = 1.0   # unknown
    return vec


def extract_features(obs, perspective, hand_cards=None):
    """観測 → 視点 `perspective`（0/1）基準の特徴ベクトル (np.float32)。

    使う情報は視点プレイヤーから見えているものだけ。v2 で自手札の中身
    （カテゴリ別カウント + ボス + 場に乗る進化先）を追加。相手手札は枚数のみ。

    hand_cards: 手札の明示指定（Card のリスト）。探索の葉は相手の選択番で自手札が
    観測に載らないことがあるため、ターン内で最後に見えた手札を呼び出し側が渡す。
    None なら obs の hand をそのまま使う（訓練時は常にこちら）。"""
    st = obs.current
    me = st.players[perspective]
    opp = st.players[1 - perspective]
    if hand_cards is not None and not me.hand:
        import copy as _copy
        me = _copy.copy(me)
        me.hand = hand_cards
    feats = []
    feats += _side_block(me)
    feats += _side_block(opp)
    # 大局特徴
    my_prize = len(me.prize)
    opp_prize = len(opp.prize)
    feats += [
        (opp_prize - my_prize) / 6.0,          # サイドレース差（正 = 自分リード）
        min(st.turn, 30) / 30.0,
        1.0 if st.yourIndex == perspective else 0.0,   # 次に選択するのは自分か
        1.0 if st.firstPlayer == perspective else 0.0,
        1.0 if st.stadium else 0.0,
    ]
    feats += _hand_block(me, _board_names(me))   # v2: 自手札の中身
    feats += _arch_onehot(me)                    # v3: 自分のアーキタイプ（条件付け）
    feats += _arch_onehot(opp)                   # v3: 相手のアーキタイプ（条件付け）
    return np.asarray(feats, dtype=np.float32)


N_FEATURES = 21 * 2 + 5 + 11 + 12 * 2


class ValueModel:
    """npz 重みの MLP（隠れ層 relu、出力 sigmoid）。predict → P(視点プレイヤー勝ち)。"""

    def __init__(self, weights, mean, std):
        self.weights = weights      # [(W0,b0),(W1,b1),...] 最終層が出力
        self.mean = mean
        self.std = std

    @classmethod
    def load(cls, path):
        """npz からロード。feature_version 不一致・破損は None（V なしに縮退）。"""
        try:
            z = np.load(path, allow_pickle=False)
            if int(z["feature_version"][0]) != FEATURE_VERSION:
                return None
            n_layers = int(z["n_layers"][0])
            weights = [(z[f"W{i}"], z[f"b{i}"]) for i in range(n_layers)]
            if weights[0][0].shape[0] != N_FEATURES:
                return None
            return cls(weights, z["mean"], z["std"])
        except Exception:
            return None

    def predict(self, x):
        """x: (N_FEATURES,) or (n, N_FEATURES) → P(win) スカラー or (n,)"""
        h = (np.atleast_2d(x) - self.mean) / self.std
        for i, (W, b) in enumerate(self.weights):
            h = h @ W + b
            if i < len(self.weights) - 1:
                h = np.maximum(h, 0.0)
        p = 1.0 / (1.0 + np.exp(-h[:, 0]))
        return p if p.shape[0] > 1 else float(p[0])


def load_default():
    """エージェントdir（このファイルの隣）の value_model.npz を読む。無ければ None。
    theta.json と同じ配置規約（ローカルでも /kaggle_simulations/agent でも同じ相対関係）。"""
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "value_model.npz")
    return ValueModel.load(fp) if os.path.exists(fp) else None
