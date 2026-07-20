"""方策ネット π(a|s) の PPO 学習（Phase 4 = RL段、方策勾配。実験計画 §4 段2）。

②選好スコアの学習を θ（reason 一律加算。EXP-006 で構造的限界）から
状態依存の NN スコアラへ引き上げる。設計の骨子:

  - 行動空間 = ルールが絞った MAIN・maxCount==1 の正帯候補（聖域は policy_base 側が構造保証）
  - 初期化 = 残差型（policy_net.init_net: MLP 出力ゼロ + beta*ルールスコア）
    → 学習前の greedy は手書きルールと完全一致（cold start ≈ 現行機。模倣θ不要）
  - 報酬 = 勝敗（win 1 / draw 0.5 / loss 0）。critic は models/value_v3.npz から初期化し、
    GAE の TD 誤差が V(s) 由来の密な信号を毎決定に配る（= potential shaping と等価な効果）
  - 相手 = gauntlet の凍結プール（θ=0・ネット無し、シェア加重サンプリング、holdout 除外）
    自己対戦はしない（正典 §7.2）。ミラー行の相手も凍結版なので非定常化しない
  - 敵対的サンプリング（2026-07-20 追加・任意）: --adv-tau > 0 で相手の抽選を
    「シェア比例」から「負けている相手ほど高頻度」（p ∝ exp((0.5−wr_ema)/τ)）へ切替。
    「こちらが方策・敵対者が相手を選ぶ」メタゲームの近似 = プール上の maximin（頑健）方策。
    AlphaStar の PFSP と同機構。プール自体は凍結のまま（サンプリング重みだけが動く）。
    EXP-030 の教訓（シェア加重 BR のラダー逆噴射）への対策で、目的は頑健エージェント
  - EXP-006 の教訓（winner's curse）: デプロイ候補は ema.npz（重みの指数移動平均）。
    latest.npz は継続用チェックポイント
  - 模倣正則化（2026-07-17 追加・任意）: --bc-data で抽出 npz（extract_bc_dataset の出力）を
    渡すと、PPO の各更新に教師決定の CE 勾配を λ 加重で混ぜる（DAPG / AlphaStar 型）。
    プール過適合で LB 挙動から漂流するのを模倣項が引き留める。λ は --bc-coef から
    --bc-coef-final へ線形減衰（勝利項が主、模倣項は錨）。--bc-eval-days の決定は
    学習に混ぜず、iter 毎の holdout 一致率として history.csv に記録（= L0 の連続計測）

依存は numpy のみ（サーバー Docker でも Windows でも同じに動く。torch 不使用）。

使い方（サーバー gs83 / Docker）:
  docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent agents/marnie_munkidori_rb \
      --deck decks/fleet/winrate_2_marnie_grimmsnarl.csv \
      --exclude okidogi,lopunny,rocket --iters 60 --games-per-iter 256 \
      --out build/ppo/marnie

  勾配実装の検証（エンジン不要・数秒）: uv run python training/train_ppo.py --self-test

出力: <out>/latest.npz（最新重み）/ ema.npz（デプロイ候補）/ iter_NNN.npz（--ckpt-every 毎）
      / history.csv（LEDGER 記入用）
評価: 学習中の勝率はサンプリング方策の参考値。採否は必ず gauntlet --net <npz> の
      L2 漏斗（80→320試合、+7pt 基準）で決める。
"""
import argparse
import csv
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))
sys.path.insert(0, str(ROOT / "training"))

from cg import api, game  # noqa: E402

from ab_battle import get_policy, load_agent, read_deck, reset_agent  # noqa: E402
from gauntlet import build_opponent, read_field  # noqa: E402

import policy_net as pn  # noqa: E402  (agents/_base の正本。特徴量・npz 形式を共有)
import value_model as vm  # noqa: E402

from train_bc import expand_vocab, load_datasets as load_bc_data  # noqa: E402


# ═══════════════════════════ 対戦生成 ═══════════════════════════

def play_game(first_mod, first_deck, second_mod, second_deck, max_steps):
    """1試合。返り値 result: 0/1 = 勝者席, 2 = draw, -1 = 未決着/開始失敗。"""
    try:
        reset_agent(first_mod)
        reset_agent(second_mod)
        obs, _start = game.battle_start(first_deck, second_deck)
        if obs is None:
            return -1
        for _ in range(max_steps):
            typed = api.to_observation_class(obs)
            if typed.current is not None and typed.current.result != -1:
                return typed.current.result
            if typed.current is not None and typed.current.yourIndex == 0:
                action = first_mod.agent(obs)
            else:
                action = second_mod.agent(obs)
            obs = game.battle_select(action)
        return -1
    finally:
        try:
            game.battle_finish()
        except Exception:
            pass


class GameSampler:
    """凍結プールからシェア加重で相手を引き、席入替しながら1試合ずつ回す。"""

    def __init__(self, agent_dir, deck, field_rows, max_steps, seed):
        self.target_mod = load_agent(agent_dir)
        self.policy = get_policy(self.target_mod)
        if self.policy is None:
            raise SystemExit(f"BasePolicy エージェントではない: {agent_dir}")
        self.policy.my_deck_list = list(deck)
        self.deck = deck
        self.max_steps = max_steps
        self.rng = np.random.RandomState(seed)
        self.opponents = []
        shares = []
        for row in field_rows:
            opp_mod, opp_deck = build_opponent(row)   # θ=0・ネット凍結済み
            self.opponents.append((row, opp_mod, opp_deck))
            shares.append(row["share"])
        self.p = np.asarray(shares, dtype=np.float64)
        self.p /= self.p.sum()
        self._game_count = 0

    def play_one(self):
        """1試合。返り値 (outcome, archetype)。outcome: 1/0.5/0、未決着は None。"""
        j = int(self.rng.choice(len(self.opponents), p=self.p))
        row, opp_mod, opp_deck = self.opponents[j]
        seat = self._game_count % 2
        self._game_count += 1
        if seat == 0:
            r = play_game(self.target_mod, self.deck, opp_mod, opp_deck, self.max_steps)
        else:
            r = play_game(opp_mod, opp_deck, self.target_mod, self.deck, self.max_steps)
        if r in (-1,) or r is None:
            return None, row["archetype"]
        if r == 2:
            return 0.5, row["archetype"]
        return (1.0 if r == seat else 0.0), row["archetype"]


# ═══════════════════════════ critic（V v3 初期化） ═══════════════════════════

class Critic:
    """状態特徴（value_model と同じ 71+ 次元）→ P(win)。BCE + Adam。"""

    def __init__(self, hidden=64, init_npz=None, seed=7):
        d = vm.N_FEATURES
        rng = np.random.RandomState(seed)
        self.mean = np.zeros(d)
        self.std = np.ones(d)
        self.W0 = rng.randn(d, hidden) * np.sqrt(2.0 / d)
        self.b0 = np.zeros(hidden)
        self.W1 = np.zeros((hidden, 1))
        self.b1 = np.zeros(1)
        self.init_from = "scratch"
        if init_npz and Path(init_npz).exists():
            try:
                z = np.load(init_npz, allow_pickle=False)
                if (int(z["feature_version"][0]) == vm.FEATURE_VERSION
                        and int(z["n_layers"][0]) == 2
                        and z["W0"].shape[0] == d):
                    self.mean = z["mean"].astype(np.float64)
                    self.std = z["std"].astype(np.float64)
                    self.W0 = z["W0"].astype(np.float64)
                    self.b0 = z["b0"].astype(np.float64).reshape(-1)
                    self.W1 = z["W1"].astype(np.float64)
                    self.b1 = z["b1"].astype(np.float64).reshape(-1)
                    self.init_from = str(init_npz)
            except Exception:
                pass
        self.params = [self.W0, self.b0, self.W1, self.b1]
        self.adam = AdamState(self.params)

    def _forward(self, S):
        xn = (S - self.mean) / self.std
        pre = xn @ self.W0 + self.b0
        h = np.maximum(pre, 0.0)
        logit = (h @ self.W1)[:, 0] + self.b1[0]
        return xn, pre, h, logit

    def predict(self, S):
        _, _, _, logit = self._forward(np.atleast_2d(S))
        return 1.0 / (1.0 + np.exp(-logit))

    def loss_grads(self, S, target):
        """BCE 損失と勾配。target ∈ [0,1]。"""
        xn, pre, h, logit = self._forward(S)
        p = 1.0 / (1.0 + np.exp(-logit))
        eps = 1e-7
        loss = -np.mean(target * np.log(p + eps) + (1 - target) * np.log(1 - p + eps))
        n = len(target)
        dlogit = (p - target) / n                      # (N,)
        dW1 = h.T @ dlogit[:, None]
        db1 = np.array([dlogit.sum()])
        dh = dlogit[:, None] * self.W1[:, 0]
        dpre = dh * (pre > 0)
        dW0 = xn.T @ dpre
        db0 = dpre.sum(axis=0)
        return loss, [dW0, db0, dW1, db1]

    def update(self, S, target, lr, epochs, minibatch, rng):
        losses = []
        n = len(target)
        for _ in range(epochs):
            order = rng.permutation(n)
            for lo in range(0, n, minibatch):
                idx = order[lo:lo + minibatch]
                loss, grads = self.loss_grads(S[idx], target[idx])
                self.adam.step(self.params, grads, lr)
                losses.append(loss)
        return float(np.mean(losses)) if losses else 0.0


class AdamState:
    def __init__(self, params, b1=0.9, b2=0.999, eps=1e-8):
        self.m = [np.zeros_like(p) for p in params]
        self.v = [np.zeros_like(p) for p in params]
        self.t = 0
        self.b1, self.b2, self.eps = b1, b2, eps

    def step(self, params, grads, lr):
        self.t += 1
        for p, g, m, v in zip(params, grads, self.m, self.v):
            m *= self.b1
            m += (1 - self.b1) * g
            v *= self.b2
            v += (1 - self.b2) * g * g
            mhat = m / (1 - self.b1 ** self.t)
            vhat = v / (1 - self.b2 ** self.t)
            p -= lr * mhat / (np.sqrt(vhat) + self.eps)


# ═══════════════════════════ PPO 本体 ═══════════════════════════

def pad_batch(X_list, k_arr, idx):
    """可変長候補をミニバッチでパディング。→ (Xp, mask, kk)"""
    kmax = max(X_list[i].shape[0] for i in idx)
    d = X_list[idx[0]].shape[1]
    Xp = np.zeros((len(idx), kmax, d), dtype=np.float64)
    mask = np.zeros((len(idx), kmax), dtype=bool)
    for r, i in enumerate(idx):
        k = X_list[i].shape[0]
        Xp[r, :k] = X_list[i]
        mask[r, :k] = True
    return Xp, mask, k_arr[idx]


def policy_forward(net, Xp, mask):
    """→ (pre, h, logits, p)。mask 外は p=0。"""
    pre = Xp @ net.W0 + net.b0
    h = np.maximum(pre, 0.0)
    logits = net.beta * Xp[:, :, vm.N_FEATURES] + (h @ net.W1)[:, :, 0] + net.b1[0]
    logits = np.where(mask, logits, -1e9)
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z) * mask
    p = e / e.sum(axis=1, keepdims=True)
    return pre, h, logits, p


def ppo_loss_grads(net, Xp, mask, kk, logp_old, adv, clip, ent_coef):
    """クリップ付き代理目的 + エントロピーボーナスの損失と解析勾配。

    L = -mean_b min(ratio*A, clip(ratio)*A) - ent_coef * mean_b H_b
    勾配は d/dlogits を組み立てて MLP に逆伝搬（--self-test が数値微分で検証）。"""
    B, K, _ = Xp.shape
    pre, h, logits, p = policy_forward(net, Xp, mask)
    rows = np.arange(B)
    logp_new = np.log(np.maximum(p[rows, kk], 1e-12))
    ratio = np.exp(logp_new - logp_old)
    unclipped = ratio * adv
    clipped = np.clip(ratio, 1 - clip, 1 + clip) * adv
    pg_loss = -np.mean(np.minimum(unclipped, clipped))
    logp_safe = np.where(mask, np.log(np.maximum(p, 1e-12)), 0.0)
    H = -(p * logp_safe).sum(axis=1)
    loss = pg_loss - ent_coef * H.mean()

    # d(pg)/dlogits: min の有効枝が unclipped のときだけ ratio 経由の勾配が流れる
    active = unclipped <= clipped                      # True → 勾配あり
    coef = np.where(active, ratio * adv, 0.0) / B      # (B,)
    onehot = np.zeros((B, K))
    onehot[rows, kk] = 1.0
    dlogits = -coef[:, None] * (onehot - p)
    # d(-ent_coef*mean H)/dlogits = ent_coef/B * p*(log p + H)
    dlogits += (ent_coef / B) * p * (logp_safe + H[:, None])
    dlogits *= mask

    # 逆伝搬
    dbeta = float((dlogits * Xp[:, :, vm.N_FEATURES]).sum())
    dW1 = np.einsum("bkh,bk->h", h, dlogits)[:, None]
    db1 = np.array([dlogits.sum()])
    dh = dlogits[:, :, None] * net.W1[:, 0]
    dpre = dh * (pre > 0)
    dW0 = np.einsum("bkd,bkh->dh", Xp, dpre)
    db0 = dpre.sum(axis=(0, 1))
    stats = {
        "pg_loss": float(pg_loss),
        "entropy": float(H.mean()),
        "approx_kl": float(np.mean(logp_old - logp_new)),
        "clip_frac": float(np.mean(np.abs(ratio - 1) > clip)),
    }
    return loss, [dW0, db0, dW1, db1, np.array([dbeta])], stats


# ═══════════════════════════ 模倣正則化（BC 混合） ═══════════════════════════
# プール自己対戦のみの PPO は凍結プールに過適合して LB 挙動から漂流し、
# BC 単独は不安定（EXP-002）。そこで PPO 勾配に教師決定の CE 勾配を λ 加重で
# 足し合わせる（DAPG / AlphaStar の教師正則化と同思想。勝利項が主、模倣項は錨）。


def pad_decisions(decisions):
    """[(Xf(K,D), k)] → (Xp, mask, kk)。pad_batch の決定リスト版。"""
    kmax = max(Xf.shape[0] for Xf, _k in decisions)
    d = decisions[0][0].shape[1]
    Xp = np.zeros((len(decisions), kmax, d), dtype=np.float64)
    mask = np.zeros((len(decisions), kmax), dtype=bool)
    kk = np.zeros(len(decisions), dtype=np.int64)
    for r, (Xf, k) in enumerate(decisions):
        Xp[r, :Xf.shape[0]] = Xf
        mask[r, :Xf.shape[0]] = True
        kk[r] = k
    return Xp, mask, kk


def bc_loss_grads(net, Xp, mask, kk):
    """教師決定の CE 損失と解析勾配（ppo_loss_grads と同じ5パラメタ並び、beta 含む）。"""
    B = Xp.shape[0]
    pre, h, _logits, p = policy_forward(net, Xp, mask)
    rows = np.arange(B)
    loss = float(-np.mean(np.log(np.maximum(p[rows, kk], 1e-12))))
    acc = float(np.mean(p.argmax(axis=1) == kk))
    dlogits = p.copy()
    dlogits[rows, kk] -= 1.0
    dlogits /= B
    dlogits = np.where(mask, dlogits, 0.0)
    dbeta = float((dlogits * Xp[:, :, vm.N_FEATURES]).sum())
    dW1 = np.einsum("bkh,bk->h", h, dlogits)[:, None]
    db1 = np.array([dlogits.sum()])
    dh = dlogits[:, :, None] * net.W1[:, 0]
    dpre = dh * (pre > 0)
    dW0 = np.einsum("bkd,bkh->dh", Xp, dpre)
    db0 = dpre.sum(axis=(0, 1))
    return loss, [dW0, db0, dW1, db1, np.array([dbeta])], acc


class BCMixer:
    """抽出 npz（train_bc と同形式）を PPO 側語彙に展開し、minibatch を払い出す。"""

    def __init__(self, patterns, eval_days, vocab, seed):
        rows = load_bc_data(patterns)
        vi = {r: i for i, r in enumerate(vocab)}
        nv = len(vocab)
        days = {d.strip() for d in eval_days.split(",") if d.strip()}
        self.train = [(expand_vocab(X, rs, vi, nv), int(k))
                      for X, k, rs, d in rows if d not in days]
        self.holdout = [(expand_vocab(X, rs, vi, nv), int(k))
                        for X, k, rs, d in rows if d in days]
        if not self.train:
            raise SystemExit("--bc-data: 学習に混ぜる決定が0件（--bc-eval-days が全日を除外?）")
        self.rng = np.random.RandomState(seed)

    def sample(self, m):
        idx = self.rng.randint(len(self.train), size=min(m, len(self.train)))
        return pad_decisions([self.train[i] for i in idx])

    def holdout_acc(self, net, chunk=512):
        """holdout 決定の greedy 一致率（= L0 の iter 毎連続計測）。データ無しは None。"""
        if not self.holdout:
            return None
        hit = 0
        for lo in range(0, len(self.holdout), chunk):
            Xp, mask, kk = pad_decisions(self.holdout[lo:lo + chunk])
            _pre, _h, _lg, p = policy_forward(net, Xp, mask)
            hit += int(np.sum(p.argmax(axis=1) == kk))
        return hit / len(self.holdout)


def compute_gae(values, outcome, gamma, lam):
    """1試合ぶんの GAE。報酬は終端のみ（= 勝敗）。values: (T,)。"""
    T = len(values)
    adv = np.zeros(T)
    last = 0.0
    for t in reversed(range(T)):
        v_next = values[t + 1] if t + 1 < T else 0.0
        r = outcome if t == T - 1 else 0.0
        delta = r + gamma * v_next - values[t]
        last = delta + gamma * lam * last
        adv[t] = last
    return adv, adv + values


# ═══════════════════════════ 学習ループ ═══════════════════════════

def _seq_games(sampler, games):
    """逐次収集: (outcome, archetype, steps) を1試合ずつ yield。"""
    policy = sampler.policy
    for _ in range(games):
        policy.net_log = []
        outcome, arch = sampler.play_one()
        steps = policy.net_log
        policy.net_log = None
        yield outcome, arch, steps


def build_batch(game_iter, gamma, lam, critic):
    """(outcome, arch, steps) の列 → フラットな遷移バッチと統計（collect の共通部）。"""
    X_list, k_list, logp_list, adv_list, ret_list, S_list = [], [], [], [], [], []
    outcomes, by_arch, wins_by_arch = [], Counter(), Counter()
    unfinished = 0
    for outcome, arch, steps in game_iter:
        if outcome is None:
            unfinished += 1
            continue
        outcomes.append(outcome)
        by_arch[arch] += 1
        wins_by_arch[arch] += outcome
        if not steps:
            continue
        S = np.stack([st["X"][0, :vm.N_FEATURES] for st in steps]).astype(np.float64)
        values = critic.predict(S)
        adv, ret = compute_gae(values, outcome, gamma, lam)
        for t, st in enumerate(steps):
            X_list.append(st["X"].astype(np.float64))
            k_list.append(st["k"])
            logp_list.append(st["logp"])
            adv_list.append(adv[t])
            ret_list.append(ret[t])
            S_list.append(S[t])
    batch = {
        "X": X_list,
        "k": np.asarray(k_list, dtype=np.int64),
        "logp": np.asarray(logp_list, dtype=np.float64),
        "adv": np.asarray(adv_list, dtype=np.float64),
        "ret": np.asarray(ret_list, dtype=np.float64),
        "S": np.stack(S_list) if S_list else np.zeros((0, vm.N_FEATURES)),
    }
    stats = {
        "games": len(outcomes),
        "unfinished": unfinished,
        "win_rate": float(np.mean(outcomes)) if outcomes else 0.0,
        "steps": len(X_list),
        "arch_games": dict(by_arch),
        "arch_wins": {a: float(w) for a, w in wins_by_arch.items()},
    }
    return batch, stats


def collect(sampler, games, gamma, lam, critic):
    """games 試合を回し、フラットな遷移バッチと統計を返す（逐次経路）。"""
    return build_batch(_seq_games(sampler, games), gamma, lam, critic)


# ═══════════════ 並列対局収集（--workers > 1。2026-07-15 追加） ═══════════════
# ボトルネックは cg エンジンの対局生成（CPU・逐次）なので、プロセスプールに撒く。
# spawn 起動で各ワーカーが自前の GameSampler（エージェント+凍結プール+DLL）を1回だけ
# 構築し、iter 毎に最新のネット重み（<100KB）を受け取って n 試合ぶんの遷移を返す。
# fork は使わない（親プロセスの cg DLL 内部状態を子が引き継ぐ事故を避ける）。

_W = {}   # ワーカープロセスの永続状態


def _worker_init(agent_dir, deck, field_rows, max_steps, seed):
    import os as _os
    wseed = (seed * 1000003 + _os.getpid()) % (2 ** 31 - 1)
    _W["sampler"] = GameSampler(Path(agent_dir), deck, field_rows, max_steps, wseed)
    _W["rng"] = np.random.RandomState((wseed * 7919 + 13) % (2 ** 31 - 1))


def _worker_play(job):
    weights, n_games, probs = job
    sampler = _W["sampler"]
    if probs is not None:   # 敵対的サンプリング: 今 iter の抽選分布を反映
        sampler.p = np.asarray(probs, dtype=np.float64)
    policy = sampler.policy
    net = pn.PolicyNet(weights["W0"], weights["b0"], weights["W1"], weights["b1"],
                       float(weights["beta"]), list(weights["vocab"]))
    policy._net = net
    policy._net_load_tried = True
    policy.net_sample = True
    policy.net_rng = _W["rng"]
    games = []
    for _ in range(n_games):
        policy.net_log = []
        outcome, arch = sampler.play_one()
        steps = policy.net_log
        policy.net_log = None
        # IPC 転送量を半減（float32）。build_batch 側で float64 に戻す
        slim = [{"X": st["X"].astype(np.float32), "k": st["k"], "logp": st["logp"]}
                for st in (steps or [])]
        games.append((outcome, arch, slim))
    return games


def collect_parallel(pool, workers, net, games, gamma, lam, critic, probs=None):
    """並列収集。バッチの中身・統計は collect と同一形式。"""
    weights = {"W0": net.W0, "b0": net.b0, "W1": net.W1, "b1": net.b1,
               "beta": net.beta, "vocab": net.vocab}
    probs_l = list(map(float, probs)) if probs is not None else None
    per = [games // workers + (1 if i < games % workers else 0) for i in range(workers)]
    jobs = [(weights, n, probs_l) for n in per if n > 0]

    def gen():
        for out in pool.imap_unordered(_worker_play, jobs):
            yield from out

    return build_batch(gen(), gamma, lam, critic)


def evaluate_greedy(sampler, games_per_matchup, max_steps):
    """greedy（argmax）でプール全行を回す簡易制圧度（参考値。確定は gauntlet で）。"""
    policy = sampler.policy
    saved = (policy.net_sample, policy.net_log)
    policy.net_sample = False
    policy.net_log = None
    num = den = 0.0
    try:
        for row, opp_mod, opp_deck in sampler.opponents:
            w = l = 0
            for g in range(games_per_matchup):
                if g % 2 == 0:
                    r = play_game(sampler.target_mod, sampler.deck, opp_mod, opp_deck, max_steps)
                    w += (r == 0)
                    l += (r == 1)
                else:
                    r = play_game(opp_mod, opp_deck, sampler.target_mod, sampler.deck, max_steps)
                    w += (r == 1)
                    l += (r == 0)
            wr = w / (w + l) if (w + l) else 0.0
            num += row["share"] * wr
            den += row["share"]
    finally:
        policy.net_sample, policy.net_log = saved
    return num / den if den else 0.0


def build_vocab(sampler, warmup_games, vocab_size, hidden, seed):
    """語彙ウォームアップ: ゼロ初期化ネット（greedy = ルールと同一挙動）で対局し、
    ネット対象決定の reason 頻度上位を語彙にする。副産物 = ベースライン勝率の参考値。"""
    policy = sampler.policy
    policy._net = pn.init_net([], hidden=hidden, seed=seed)
    policy._net_load_tried = True
    policy.net_sample = False
    counts = Counter()
    outcomes = []
    for _ in range(warmup_games):
        policy.net_log = []
        outcome, _arch = sampler.play_one()
        for st in policy.net_log:
            counts.update(st["reasons"])
        policy.net_log = None
        if outcome is not None:
            outcomes.append(outcome)
    vocab = [r for r, _c in counts.most_common(vocab_size)]
    base_wr = float(np.mean(outcomes)) if outcomes else 0.0
    return vocab, base_wr, counts


def save_net(path, net, vocab):
    obj = pn.PolicyNet(net.W0, net.b0, net.W1, net.b1, net.beta, vocab)
    obj.save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/marnie_munkidori_rb")
    ap.add_argument("--deck",
                    default="decks/fleet/winrate_2_marnie_grimmsnarl.csv")
    ap.add_argument("--field", default="research/meta/2026-07-14_field.csv")
    ap.add_argument("--exclude", default="okidogi,lopunny,rocket",
                    help="学習プールから外す holdout（CEM/EXP-009 と同じ既定）")
    ap.add_argument("--iters", type=int, default=60)
    ap.add_argument("--games-per-iter", type=int, default=256)
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--critic-lr", type=float, default=1e-3)
    ap.add_argument("--clip", type=float, default=0.2)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--minibatch", type=int, default=1024)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--gamma", type=float, default=1.0)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--target-kl", type=float, default=0.03,
                    help="epoch 途中で approx_kl がこれを超えたら当該 iter の更新を打ち切り")
    ap.add_argument("--bc-data", default="",
                    help="模倣正則化: 抽出 npz の glob（カンマ区切り可）。空 = 従来 PPO のみ")
    ap.add_argument("--bc-coef", type=float, default=0.3,
                    help="模倣項の初期係数 λ")
    ap.add_argument("--bc-coef-final", type=float, default=0.05,
                    help="最終 iter の λ（線形減衰。定数にするなら --bc-coef と同値）")
    ap.add_argument("--bc-minibatch", type=int, default=256)
    ap.add_argument("--bc-eval-days", default="",
                    help="この日の決定は学習に混ぜず holdout 一致率の計測のみ（P-10）")
    ap.add_argument("--adv-tau", type=float, default=0.0,
                    help="敵対的サンプリングの温度。0 = 従来のシェア加重。"
                         "推奨 0.15（p ∝ exp((0.5−wr)/τ) = soft maximin）")
    ap.add_argument("--adv-ema", type=float, default=0.3,
                    help="対面別勝率 EMA の更新率")
    ap.add_argument("--adv-floor", type=float, default=0.25,
                    help="重み計算時の wr 下限クリップ。構造的に勝てない対面（デッキ相性）へ"
                         "分布が集中暴走するのを防ぐ（EXP-031 rocket vs archaludon の教訓）")
    ap.add_argument("--adv-eps", type=float, default=0.25,
                    help="均等分布の混合率。勝ち対面の忘却防止とカバレッジ維持")
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--vocab-size", type=int, default=64)
    ap.add_argument("--warmup-games", type=int, default=32)
    ap.add_argument("--ema", type=float, default=0.9, help="デプロイ候補重みの EMA 減衰")
    ap.add_argument("--eval-every", type=int, default=10, help="0 = 学習中 greedy 評価なし")
    ap.add_argument("--eval-games", type=int, default=8, help="greedy 評価の試合数/マッチアップ")
    ap.add_argument("--ckpt-every", type=int, default=10)
    ap.add_argument("--critic-init", default="models/value_v3.npz")
    ap.add_argument("--resume", help="latest.npz から重み再開（Adam 状態は初期化）")
    ap.add_argument("--workers", type=int, default=1,
                    help="対局収集の並列プロセス数（1=従来の逐次。サーバーは物理コア-1 推奨）")
    ap.add_argument("--out", default="build/ppo/marnie")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--self-test", action="store_true",
                    help="勾配の数値微分チェックのみ（エンジン不要）")
    args = ap.parse_args()

    if args.self_test:
        self_test(args)
        return

    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(args.seed)

    field = read_field(ROOT / args.field)
    if args.exclude:
        names = {n.strip() for n in args.exclude.split(",") if n.strip()}
        missing = names - {r["archetype"] for r in field}
        if missing:
            raise SystemExit(f"--exclude: unknown archetypes: {sorted(missing)}")
        field = [r for r in field if r["archetype"] not in names]
    deck = read_deck(ROOT / args.deck)
    sampler = GameSampler(ROOT / args.agent, deck, field, args.max_steps, args.seed)
    print(f"pool: {[r['archetype'] for r in field]}")

    critic = Critic(hidden=args.hidden, init_npz=ROOT / args.critic_init, seed=args.seed)
    print(f"critic init: {critic.init_from}")

    # ── 語彙 + ネット初期化（or 再開） ──
    if args.resume:
        net = pn.PolicyNet.load(str(ROOT / args.resume))
        if net is None:
            raise SystemExit(f"--resume: ロード失敗: {args.resume}")
        vocab = net.vocab
        print(f"resumed from {args.resume} (vocab {len(vocab)})")
    else:
        t0 = time.perf_counter()
        vocab, base_wr, counts = build_vocab(
            sampler, args.warmup_games, args.vocab_size, args.hidden, args.seed)
        print(f"vocab: {len(vocab)} reasons (from {sum(counts.values())} candidate-reasons, "
              f"{time.perf_counter() - t0:.0f}s) / warmup greedy wr = {base_wr:.1%} (参考値)")
        net = pn.init_net(vocab, hidden=args.hidden, seed=args.seed)

    bc = None
    if args.bc_data:
        bc = BCMixer(args.bc_data, args.bc_eval_days, vocab, args.seed + 2)
        print(f"bc mix: train={len(bc.train)} / holdout={len(bc.holdout)} decisions, "
              f"lambda {args.bc_coef} -> {args.bc_coef_final}")

    # 訓練用にネットを注入（gauntlet の凍結とは逆に、対象機はこのネットで指す）
    policy = sampler.policy
    policy._net = net
    policy._net_load_tried = True
    policy.net_sample = True
    policy.net_rng = np.random.RandomState(args.seed + 1)

    pol_params = [net.W0, net.b0, net.W1, np.asarray(net.b1, dtype=np.float64),
                  np.array([net.beta])]
    adam = AdamState(pol_params)
    ema = [p.copy() for p in pol_params]

    # ── 並列収集プール（--workers > 1。spawn = cg DLL 状態の分離） ──
    pool = None
    if args.workers > 1:
        import multiprocessing as mp
        ctx = mp.get_context("spawn")
        t0 = time.perf_counter()
        pool = ctx.Pool(args.workers, initializer=_worker_init,
                        initargs=(str(ROOT / args.agent), deck, field,
                                  args.max_steps, args.seed))
        # 各ワーカーの初期化（エージェント+凍結プールのロード）を1件ジョブで待つ
        pool.map(_worker_play, [({"W0": net.W0, "b0": net.b0, "W1": net.W1,
                                  "b1": net.b1, "beta": net.beta,
                                  "vocab": net.vocab}, 0, None)] * args.workers)
        print(f"parallel pool: {args.workers} workers ready "
              f"({time.perf_counter() - t0:.0f}s)")

    # ── 敵対的サンプリング状態（--adv-tau > 0 のとき有効） ──
    arch_names = [r["archetype"] for r in field]
    wr_ema = np.full(len(field), 0.5)
    adv_probs = None
    if args.adv_tau > 0:
        adv_probs = np.full(len(field), 1.0 / len(field))   # 初期は均等
        print(f"adversarial sampling: tau={args.adv_tau} ema={args.adv_ema} "
              f"(uniform start, {len(field)} opponents)")

    hist_path = out / "history.csv"
    new_hist = not hist_path.exists()
    hist_f = open(hist_path, "a", newline="", encoding="utf-8")
    hist = csv.writer(hist_f)
    if new_hist:
        hist.writerow(["iter", "games", "unfinished", "win_rate", "steps",
                       "pg_loss", "v_loss", "entropy", "approx_kl", "clip_frac",
                       "beta", "eval_wr", "bc_loss", "bc_acc", "bc_holdout",
                       "bc_coef", "adv_minwr", "secs"])

    for it in range(1, args.iters + 1):
        t0 = time.perf_counter()
        if adv_probs is not None:
            sampler.p = adv_probs   # 逐次経路。並列経路はジョブ経由で渡す
        if pool is not None:
            batch, cstats = collect_parallel(
                pool, args.workers, net, args.games_per_iter,
                args.gamma, args.lam, critic, probs=adv_probs)
        else:
            batch, cstats = collect(sampler, args.games_per_iter,
                                    args.gamma, args.lam, critic)

        # ── 対面別勝率 EMA → 次 iter の敵対的抽選分布（soft maximin） ──
        adv_minwr = ""
        if adv_probs is not None:
            for i, a in enumerate(arch_names):
                g = cstats["arch_games"].get(a, 0)
                if g:
                    wr = cstats["arch_wins"].get(a, 0.0) / g
                    wr_ema[i] = (1 - args.adv_ema) * wr_ema[i] + args.adv_ema * wr
            # 飽和つき soft maximin + 均等混合（v2 2026-07-20）:
            # wr を floor でクリップ = 構造的に勝てない対面（デッキ相性）が分布を
            # 独占して学習可能な対面を飢えさせるのを防ぐ。ε-均等混合で勝ち対面の
            # 忘却も防ぐ（初版は rocket vs archaludon(〜10%) に14倍集中して暴走）
            w = np.exp((0.5 - np.maximum(wr_ema, args.adv_floor)) / args.adv_tau)
            adv_probs = (1 - args.adv_eps) * (w / w.sum()) + args.adv_eps / len(field)
            worst = int(np.argmin(wr_ema))
            adv_minwr = f"{wr_ema[worst]:.4f}"
            worst_name = arch_names[worst]
        n = len(batch["X"])
        if n == 0:
            print(f"iter {it}: no steps collected, skip")
            continue
        adv = batch["adv"]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)

        # 模倣項の係数（iter に対し線形減衰: 序盤は錨を強く、終盤は勝利項に主導権）
        bc_coef = 0.0
        if bc is not None:
            frac = (it - 1) / max(1, args.iters - 1)
            bc_coef = args.bc_coef + (args.bc_coef_final - args.bc_coef) * frac

        # ── policy update ──
        stats_acc = []
        stop = False
        for _ep in range(args.epochs):
            if stop:
                break
            order = rng.permutation(n)
            for lo in range(0, n, args.minibatch):
                idx = order[lo:lo + args.minibatch]
                Xp, mask, kk = pad_batch(batch["X"], batch["k"], idx)
                _loss, grads, st = ppo_loss_grads(
                    net, Xp, mask, kk, batch["logp"][idx], adv[idx],
                    args.clip, args.ent)
                if bc is not None:
                    bXp, bmask, bkk = bc.sample(args.bc_minibatch)
                    bloss, bgrads, st["bc_acc"] = bc_loss_grads(net, bXp, bmask, bkk)
                    st["bc_loss"] = bloss
                    grads = [g + bc_coef * bg for g, bg in zip(grads, bgrads)]
                adam.step(pol_params, grads, args.lr)
                net.beta = float(pol_params[4][0])
                net.b1 = pol_params[3]
                stats_acc.append(st)
                if st["approx_kl"] > args.target_kl:
                    stop = True
                    break

        # ── critic update ──
        v_loss = critic.update(batch["S"], np.clip(batch["ret"], 0.0, 1.0),
                               args.critic_lr, args.epochs, args.minibatch, rng)

        # ── EMA（デプロイ候補） ──
        for e, p in zip(ema, pol_params):
            e *= args.ema
            e += (1 - args.ema) * p

        def mean(k):
            vals = [s[k] for s in stats_acc if k in s]
            return float(np.mean(vals)) if vals else 0.0

        eval_wr = ""
        if args.eval_every and it % args.eval_every == 0:
            eval_wr = f"{evaluate_greedy(sampler, args.eval_games, args.max_steps):.4f}"
        bc_hold = ""
        if bc is not None:
            h_acc = bc.holdout_acc(net)
            if h_acc is not None:
                bc_hold = f"{h_acc:.4f}"
        secs = time.perf_counter() - t0
        bc_msg = ""
        if bc is not None:
            bc_msg = (f"bc={mean('bc_loss'):.3f}/acc={mean('bc_acc'):.1%}"
                      + (f"/hold={bc_hold}" if bc_hold else "")
                      + f"/l={bc_coef:.3f} ")
        adv_msg = ""
        if adv_probs is not None and adv_minwr:
            adv_msg = f"minwr={worst_name}:{adv_minwr} "
        print(f"iter {it:3d}: wr={cstats['win_rate']:.1%} steps={cstats['steps']} "
              f"H={mean('entropy'):.3f} kl={mean('approx_kl'):.4f} "
              f"clip={mean('clip_frac'):.2f} vloss={v_loss:.4f} beta={net.beta:.3f} "
              f"{bc_msg}{adv_msg}"
              f"{'eval=' + eval_wr if eval_wr else ''} ({secs:.0f}s)")
        hist.writerow([it, cstats["games"], cstats["unfinished"],
                       f"{cstats['win_rate']:.4f}", cstats["steps"],
                       f"{mean('pg_loss'):.5f}", f"{v_loss:.5f}",
                       f"{mean('entropy'):.4f}", f"{mean('approx_kl'):.5f}",
                       f"{mean('clip_frac'):.4f}", f"{net.beta:.4f}", eval_wr,
                       f"{mean('bc_loss'):.5f}" if bc is not None else "",
                       f"{mean('bc_acc'):.4f}" if bc is not None else "",
                       bc_hold,
                       f"{bc_coef:.4f}" if bc is not None else "",
                       adv_minwr,
                       f"{secs:.1f}"])
        hist_f.flush()

        save_net(out / "latest.npz", net, vocab)
        ema_net = pn.PolicyNet(ema[0], ema[1], ema[2], ema[3], float(ema[4][0]), vocab)
        ema_net.save(out / "ema.npz")
        if args.ckpt_every and it % args.ckpt_every == 0:
            save_net(out / f"iter_{it:03d}.npz", net, vocab)

    hist_f.close()
    if pool is not None:
        pool.close()
        pool.join()
    print(f"done. deploy candidate = {out / 'ema.npz'}  "
          f"(次: gauntlet --net {(out / 'ema.npz').relative_to(ROOT)} で L2 A/B)")


# ═══════════════════════════ 勾配の数値検証 ═══════════════════════════

def self_test(args):
    """解析勾配 vs 数値微分（エンジン不要）。方策とcriticの両方を検証する。"""
    rng = np.random.RandomState(0)
    B, K, H = 5, 4, 8
    vocab = [f"r{i}" for i in range(3)]
    d = pn.feature_dim(len(vocab))
    net = pn.init_net(vocab, hidden=H, seed=1)
    # ゼロ初期化のままだと W1 の勾配経路が退化するので乱数を入れる
    net.W1 = rng.randn(H, 1) * 0.1
    net.b1 = rng.randn(1) * 0.1
    net.beta = 0.7
    Xp = rng.randn(B, K, d) * 0.5
    mask = np.ones((B, K), dtype=bool)
    mask[0, 3] = False                       # 可変長候補を再現
    kk = np.array([0, 1, 2, 0, 1])
    adv = rng.randn(B)
    _, _, _, p = policy_forward(net, Xp, mask)
    logp_old = np.log(p[np.arange(B), kk]) + rng.randn(B) * 0.1   # ratio≠1 でクリップ枝も踏む

    params = [net.W0, net.b0, net.W1, net.b1, np.array([net.beta])]
    names = ["W0", "b0", "W1", "b1", "beta"]

    def loss_only():
        loss, _, _ = ppo_loss_grads(net, Xp, mask, kk, logp_old, adv, 0.2, 0.01)
        return loss

    _, grads, _ = ppo_loss_grads(net, Xp, mask, kk, logp_old, adv, 0.2, 0.01)
    eps = 1e-6
    worst = 0.0
    for name, p_arr, g in zip(names, params, grads):
        flat = p_arr.reshape(-1)
        gflat = np.asarray(g).reshape(-1)
        for _ in range(min(10, flat.size)):
            i = rng.randint(flat.size)
            old = flat[i]
            flat[i] = old + eps
            net.beta = float(params[4][0])
            lp = loss_only()
            flat[i] = old - eps
            net.beta = float(params[4][0])
            lm = loss_only()
            flat[i] = old
            net.beta = float(params[4][0])
            num = (lp - lm) / (2 * eps)
            err = abs(num - gflat[i]) / max(1e-8, abs(num) + abs(gflat[i]))
            worst = max(worst, err)
        print(f"policy {name}: ok (worst rel err so far {worst:.2e})")
    assert worst < 1e-4, f"policy gradient check failed: {worst}"

    # 模倣項（bc_loss_grads）も同じ数値微分で検証（kk を教師ラベルとして流用）
    def bc_only():
        loss, _, _ = bc_loss_grads(net, Xp, mask, kk)
        return loss

    _, bgrads, _ = bc_loss_grads(net, Xp, mask, kk)
    worst_b = 0.0
    for name, p_arr, g in zip(names, params, bgrads):
        flat = p_arr.reshape(-1)
        gflat = np.asarray(g).reshape(-1)
        for _ in range(min(10, flat.size)):
            i = rng.randint(flat.size)
            old = flat[i]
            flat[i] = old + eps
            net.beta = float(params[4][0])
            lp = bc_only()
            flat[i] = old - eps
            net.beta = float(params[4][0])
            lm = bc_only()
            flat[i] = old
            net.beta = float(params[4][0])
            num = (lp - lm) / (2 * eps)
            err = abs(num - gflat[i]) / max(1e-8, abs(num) + abs(gflat[i]))
            worst_b = max(worst_b, err)
        print(f"bc {name}: ok (worst rel err so far {worst_b:.2e})")
    assert worst_b < 1e-4, f"bc gradient check failed: {worst_b}"

    critic = Critic(hidden=H, init_npz=None, seed=2)
    critic.W1 = rng.randn(H, 1) * 0.1
    S = rng.randn(6, vm.N_FEATURES)
    y = rng.rand(6)
    _, grads = critic.loss_grads(S, y)
    cparams = [critic.W0, critic.b0, critic.W1, critic.b1]
    worst_c = 0.0
    for name, p_arr, g in zip(["W0", "b0", "W1", "b1"], cparams, grads):
        flat = p_arr.reshape(-1)
        gflat = np.asarray(g).reshape(-1)
        for _ in range(min(10, flat.size)):
            i = rng.randint(flat.size)
            old = flat[i]
            flat[i] = old + eps
            lp, _ = critic.loss_grads(S, y)
            flat[i] = old - eps
            lm, _ = critic.loss_grads(S, y)
            flat[i] = old
            num = (lp - lm) / (2 * eps)
            err = abs(num - gflat[i]) / max(1e-8, abs(num) + abs(gflat[i]))
            worst_c = max(worst_c, err)
        print(f"critic {name}: ok (worst rel err so far {worst_c:.2e})")
    assert worst_c < 1e-4, f"critic gradient check failed: {worst_c}"
    print(f"self-test PASS (policy {worst:.2e} / bc {worst_b:.2e} / critic {worst_c:.2e})")


if __name__ == "__main__":
    main()
