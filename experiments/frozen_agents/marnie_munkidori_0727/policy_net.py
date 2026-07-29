"""方策ネット π(a|s) — MAIN 候補の再ランク（特徴量抽出と numpy 推論の train/serve 共通正本）。

正本は agents/_base/policy_net.py。各エージェントdirへは scripts/sync_base.py で同期する。
訓練側（training/train_ppo.py）も**このモジュールを import する**（train/serve skew の排除。
value_model.py と同じ思想）。

役割:
  - PolicyNet: policy_net.npz の重みを読む numpy MLP。候補行列 X → 候補ロジット。
    ロジット = beta * 正規化ルールスコア + MLP(X)。MLP 出力ゼロ初期化 + argmax 運用なら
    「学習前 = 手書きルールの argmax と完全一致」（残差型。模倣θのような一律シフト事故がない）
  - extract_features(obs, cands, vocab_index, n_vocab): 決定1回ぶんの候補特徴行列
    （状態ブロックは value_model.extract_features を流用 = V(s) と同じ正本）
  - 依存は cg.api / numpy / value_model / policy_base のみ（提出環境で動く）

聖域との関係（policy_base._maybe_net が保証）:
  - リーサル成立時（R-07）は呼ばれない
  - 候補は MAIN・maxCount==1・正帯（0 <= score < 100_000）のみ = 負帯マスクの復活は構造上ない

特徴量を変えたら PN_VERSION を上げること。npz 側と不一致のモデルはロードを拒否する
（黙って壊れた方策を出すより、ネットなし＝ルール順位に落ちる方が安全。R-01 と同思想）。
"""
import os

import numpy as np

from cg.api import CardType, OptionType

import policy_base as pb
import value_model as vm

PN_VERSION = 2   # v2（2026-07-20）: 状態ブロックの相手アーキ one-hot をゼロマスク（相手盲目化）

# v2 相手盲目化: 相手適応は NN に焼き込まず、ルール（matchup 判定 → 対面ルール、
# 未知は generic フォールバック）だけが担う。EXP-030 の L2↔L4 逆転（プール分布への
# BR がラダーで逆噴射）への対策 = NN は相手が誰でも通用する普遍戦術のみ学ぶ。
# critic（value_model）は従来どおり条件付けを保持（価値推定はデプロイ挙動に出ない）。
_N_ARCH_BLOCK = len(vm.ARCH_LIST) + 1   # 相手 one-hot は状態ブロック末尾（unknown 枠込み）

# 候補ブロックのレイアウト（状態ブロック vm.N_FEATURES の後ろに続く）
N_OPT_TYPES = 17          # OptionType 0..16
N_CARD_TYPES = 7          # CardType 0..6
CAND_BASE = 3 + N_OPT_TYPES + (6 + N_CARD_TYPES) + 3 + 1   # 37
SCORE_SCALE = 10000.0     # 正帯 (< 100_000) → [0, 10]


def feature_dim(n_vocab):
    """候補1行の特徴次元。reason one-hot は語彙 n_vocab + OOV 1 枠。"""
    return vm.N_FEATURES + CAND_BASE + n_vocab + 1


def _card_block(card, in_play):
    """カード6特徴 + CardType one-hot。card は手札カード or 場のポケモン（None 可）。

    注意: MAIN の DISCARD/ABILITY 等が指す card は「場のポケモン」とは限らない
    （hp を持たない素の Card のことがある）。動的特徴（被ダメ・付きエネ）は
    hp 属性を持つ実体（= 場のポケモン）のときだけ読む。"""
    feats = [0.0] * (6 + N_CARD_TYPES)
    if card is None:
        return feats
    data = pb.CARD_DB.get(card.id)
    feats[0] = 1.0
    hp = getattr(data, "hp", 0) if data else 0
    feats[1] = min(float(hp or 0), 340.0) / 340.0
    if in_play and getattr(card, "hp", None) is not None:
        feats[2] = min(float(pb.damage_on(card)), 340.0) / 340.0
        feats[5] = min(pb.energy_count(card), 4) / 4.0
    feats[3] = 1.0 if pb.is_ex(card) else 0.0
    feats[4] = pb.prize_value(card) / 3.0
    if data is not None:
        ct = int(data.cardType)
        if 0 <= ct < N_CARD_TYPES:
            feats[6 + ct] = 1.0
    return feats


def extract_features(obs, cands, vocab_index, n_vocab):
    """決定1回ぶんの候補特徴行列 (K, feature_dim) を返す。

    cands: [(option_index, score, reason), ...] ルール順位の降順（正帯のみ）。
    状態ブロックは全行で共有（value_model.extract_features をそのまま流用）。"""
    state = vm.extract_features(obs, obs.current.yourIndex)
    state[vm.N_FEATURES - _N_ARCH_BLOCK:] = 0.0   # v2: 相手アーキ one-hot を遮断
    k = len(cands)
    X = np.zeros((k, feature_dim(n_vocab)), dtype=np.float32)
    X[:, :vm.N_FEATURES] = state
    base = vm.N_FEATURES
    for row, (oi, score, reason) in enumerate(cands):
        opt = obs.select.option[oi]
        X[row, base + 0] = min(max(score, 0.0), 100_000.0) / SCORE_SCALE
        X[row, base + 1] = 1.0 if row == 0 else 0.0
        X[row, base + 2] = row / 8.0
        ot = int(opt.type)
        if 0 <= ot < N_OPT_TYPES:
            X[row, base + 3 + ot] = 1.0
        # カードブロック: PLAY は手札カード、DISCARD/ABILITY 等は場のカードを指すことがある
        card = pb.option_card(obs, opt)
        in_play = opt.type != OptionType.PLAY
        cb = base + 3 + N_OPT_TYPES
        X[row, cb:cb + 6 + N_CARD_TYPES] = _card_block(card, in_play)
        # ターゲットブロック（ATTACH 先など）
        tb = cb + 6 + N_CARD_TYPES
        target = pb.option_target(obs, opt)
        if target is not None:
            X[row, tb + 0] = 1.0
            if getattr(target, "hp", None) is not None:
                X[row, tb + 1] = min(float(target.hp or 0), 340.0) / 340.0
                X[row, tb + 2] = min(float(pb.damage_on(target)), 340.0) / 340.0
        # 攻撃打点（基礎値）
        if opt.type == OptionType.ATTACK and getattr(opt, "attackId", None) is not None:
            X[row, tb + 3] = min(float(pb.attack_base_damage(opt.attackId)), 340.0) / 340.0
        # reason one-hot（語彙外は OOV 枠）
        ri = vocab_index.get(reason, n_vocab)
        X[row, base + CAND_BASE + ri] = 1.0
    return X


class PolicyNet:
    """npz 重みの候補スコアラ。logits = beta * X[:, idx_score] + MLP(X)。"""

    def __init__(self, W0, b0, W1, b1, beta, vocab):
        self.W0 = W0
        self.b0 = b0
        self.W1 = W1
        self.b1 = b1
        self.beta = float(beta)
        self.vocab = list(vocab)
        self.vocab_index = {r: i for i, r in enumerate(self.vocab)}
        self.idx_score = vm.N_FEATURES

    # ── train/serve 共通の入口 ──

    def features(self, obs, cands):
        return extract_features(obs, cands, self.vocab_index, len(self.vocab))

    def logits(self, X):
        h = np.maximum(X @ self.W0 + self.b0, 0.0)
        out = h @ self.W1 + self.b1
        return self.beta * X[:, self.idx_score] + out[:, 0]

    # ── 永続化 ──

    def save(self, path):
        vocab_arr = np.asarray(self.vocab, dtype="U") if self.vocab else \
            np.zeros((0,), dtype="U1")
        np.savez(
            path,
            pn_version=np.array([PN_VERSION]),
            vm_feature_version=np.array([vm.FEATURE_VERSION]),
            n_state=np.array([vm.N_FEATURES]),
            W0=self.W0, b0=self.b0, W1=self.W1, b1=self.b1,
            beta=np.array([self.beta], dtype=np.float64),
            vocab=vocab_arr,
        )

    @classmethod
    def load(cls, path):
        """npz からロード。版・次元の不一致や破損は None（ネットなしに縮退）。"""
        try:
            z = np.load(path, allow_pickle=False)
            if int(z["pn_version"][0]) != PN_VERSION:
                return None
            if int(z["vm_feature_version"][0]) != vm.FEATURE_VERSION:
                return None
            if int(z["n_state"][0]) != vm.N_FEATURES:
                return None
            vocab = [str(r) for r in z["vocab"]]
            net = cls(z["W0"], z["b0"], z["W1"], z["b1"],
                      float(z["beta"][0]), vocab)
            if net.W0.shape[0] != feature_dim(len(vocab)):
                return None
            return net
        except Exception:
            return None


def init_net(vocab, hidden=64, seed=7, beta=1.0):
    """訓練の初期ネット。MLP 出力層ゼロ → argmax はルール順位と完全一致（残差型）。"""
    rng = np.random.RandomState(seed)
    d = feature_dim(len(vocab))
    W0 = (rng.randn(d, hidden) * np.sqrt(2.0 / d)).astype(np.float64)
    b0 = np.zeros(hidden, dtype=np.float64)
    W1 = np.zeros((hidden, 1), dtype=np.float64)
    b1 = np.zeros(1, dtype=np.float64)
    return PolicyNet(W0, b0, W1, b1, beta, list(vocab))


def load_for_policy(policy):
    """policy_net.npz をポリシー自身の main モジュールの隣から読む。
    （ローカル評価のクロス dir import では本モジュールが他機の dir を指しうるため、
    ポリシー基準のパスを優先する。turn_search._load_value_model と同じイディオム。）"""
    import sys
    mod = sys.modules.get(policy.__class__.__module__)
    mod_file = getattr(mod, "__file__", None)
    if mod_file:
        path = os.path.join(os.path.dirname(os.path.abspath(mod_file)),
                            "policy_net.npz")
        if os.path.exists(path):
            return PolicyNet.load(path)
    return load_default()


def load_default():
    """このファイルの隣の policy_net.npz を読む。無ければ None。
    theta.json / value_model.npz と同じ配置規約。"""
    fp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_net.npz")
    return PolicyNet.load(fp) if os.path.exists(fp) else None
