"""方策ネットの BC（模倣）事前学習 — 「現行ルールエージェント = 初期値」から
上位ピロットの選択へ向けて MLP 残差だけを教師あり学習する。

位置づけ（実験計画 §4「模倣で初期化 → RL で仕上げ」の前段）:
  - 初期化は policy_net.init_net の残差型（MLP 出力ゼロ + beta×ルールスコア）
    → epoch 0 の argmax は現行ルールと完全一致。BC は上位ピロットとの差分だけを学ぶ。
  - EXP-002（模倣θの直接デプロイで −18pt）の教訓: BC 出力は直接デプロイせず、
    train_ppo.py --resume の初期値にする（プール相手の PPO で仕上げ）。
    採否ゲートは L0（holdout 日の一致率）と L4（実ラダー）。プール制圧度は参考値
    （ユーザー指示 2026-07-15）。
  - beta（ルールスコア項）は凍結。学習対象は W0/b0/W1/b1 のみ。

使い方:
  uv run python training/train_bc.py \
      --data "data/imitation/alakazam_bc/*.npz" \
      --eval-days 2026-07-13 --out models/bc_alakazam_v1.npz
  （--eval-days の日は学習に使わず holdout 一致率の物差しにする = P-10）
"""
import argparse
import glob
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

import policy_net as pn  # noqa: E402
import value_model as vm  # noqa: E402


def load_datasets(patterns):
    """抽出 npz 群 → 決定リスト [(X_base(K,D0), k, reasons(K,), day)]。"""
    rows = []
    for pat in patterns.split(","):
        for fp in sorted(glob.glob(str(ROOT / pat.strip()))):
            z = np.load(fp, allow_pickle=False)
            if int(z["pn_version"][0]) != pn.PN_VERSION:
                raise SystemExit(f"{fp}: PN_VERSION 不一致（再抽出が必要）")
            if int(z["vm_feature_version"][0]) != vm.FEATURE_VERSION:
                raise SystemExit(f"{fp}: FEATURE_VERSION 不一致（再抽出が必要）")
            X = z["X"]
            off = z["offsets"]
            k = z["k"]
            reasons = z["reasons"]
            day = z["day"]
            r0 = 0
            for i in range(len(k)):
                a, b = off[i], off[i + 1]
                rows.append((X[a:b], int(k[i]), reasons[r0:r0 + (b - a)], str(day[i])))
                r0 += b - a
    if not rows:
        raise SystemExit("データ0件")
    return rows


def expand_vocab(X_base, reasons, vocab_index, n_vocab):
    """語彙なし特徴（末尾 OOV 1枠）→ 本語彙 one-hot に展開（extract_features と一致）。"""
    K, D0 = X_base.shape
    body = D0 - 1                        # OOV 1枠を落とす
    X = np.zeros((K, body + n_vocab + 1), dtype=np.float64)
    X[:, :body] = X_base[:, :body]
    for r in range(K):
        ri = vocab_index.get(str(reasons[r]), n_vocab)
        X[r, body + ri] = 1.0
    return X


def forward(net, Xp, mask):
    pre = Xp @ net.W0 + net.b0
    h = np.maximum(pre, 0.0)
    logits = net.beta * Xp[:, :, vm.N_FEATURES] + (h @ net.W1)[:, :, 0] + net.b1[0]
    logits = np.where(mask, logits, -1e9)
    z = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(z) * mask
    p = e / e.sum(axis=1, keepdims=True)
    return pre, h, p


def accuracy(net, decisions):
    hit = 0
    for Xf, k in decisions:
        Xp = Xf[None, :, :]
        mask = np.ones((1, Xf.shape[0]), dtype=bool)
        _pre, _h, p = forward(net, Xp, mask)
        if int(np.argmax(p[0])) == k:
            hit += 1
    return hit / len(decisions)


class Adam:
    def __init__(self, shapes, b1=0.9, b2=0.999, eps=1e-8):
        self.m = [np.zeros(s) for s in shapes]
        self.v = [np.zeros(s) for s in shapes]
        self.t = 0
        self.b1, self.b2, self.eps = b1, b2, eps

    def step(self, params, grads, lr):
        self.t += 1
        out = []
        for i, (p, g) in enumerate(zip(params, grads)):
            self.m[i] = self.b1 * self.m[i] + (1 - self.b1) * g
            self.v[i] = self.b2 * self.v[i] + (1 - self.b2) * g * g
            mh = self.m[i] / (1 - self.b1 ** self.t)
            vh = self.v[i] / (1 - self.b2 ** self.t)
            out.append(p - lr * mh / (np.sqrt(vh) + self.eps))
        return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="抽出 npz の glob（カンマ区切り可）")
    ap.add_argument("--eval-days", default="",
                    help="holdout にする日（カンマ区切り。学習から除外 = P-10）")
    ap.add_argument("--hidden", type=int, default=64)
    ap.add_argument("--vocab-size", type=int, default=64)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--minibatch", type=int, default=256)
    ap.add_argument("--beta", type=float, default=1.0)
    ap.add_argument("--l2", type=float, default=1e-4, help="重み減衰（過学習抑制）")
    ap.add_argument("--patience", type=int, default=10,
                    help="holdout 一致率が改善しない epoch 数で早期終了")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="models/bc_policy.npz")
    args = ap.parse_args()

    rows = load_datasets(args.data)
    eval_days = {d.strip() for d in args.eval_days.split(",") if d.strip()}
    train_rows = [r for r in rows if r[3] not in eval_days]
    eval_rows = [r for r in rows if r[3] in eval_days]
    if not train_rows:
        raise SystemExit("学習データ0件（--eval-days が全日を除外していないか）")
    print(f"decisions: train={len(train_rows)} "
          f"({sorted({r[3] for r in train_rows})}) / "
          f"eval={len(eval_rows)} ({sorted(eval_days)})")

    # 語彙は学習データの reason 頻度上位（train_ppo.build_vocab と同じ思想）
    counts = Counter()
    for _X, _k, reasons, _d in train_rows:
        counts.update(str(r) for r in reasons)
    vocab = [r for r, _c in counts.most_common(args.vocab_size)]
    vocab_index = {r: i for i, r in enumerate(vocab)}
    nv = len(vocab)
    print(f"vocab: {nv} reasons (from {sum(counts.values())} candidate-reasons)")

    train = [(expand_vocab(X, rs, vocab_index, nv), k) for X, k, rs, _d in train_rows]
    evals = [(expand_vocab(X, rs, vocab_index, nv), k) for X, k, rs, _d in eval_rows]

    net = pn.init_net(vocab, hidden=args.hidden, seed=args.seed, beta=args.beta)
    base_train = float(np.mean([1.0 if k == 0 else 0.0 for _x, k in train]))
    base_eval = float(np.mean([1.0 if k == 0 else 0.0 for _x, k in evals])) if evals else float("nan")
    print(f"rule-argmax baseline: train {base_train:.1%} / eval {base_eval:.1%}")
    assert abs(accuracy(net, train[:200]) -
               float(np.mean([1.0 if k == 0 else 0.0 for _x, k in train[:200]]))) < 1e-9, \
        "残差初期化の不変条件（epoch0 = ルール一致）が壊れている"

    rng = np.random.RandomState(args.seed)
    opt = Adam([net.W0.shape, net.b0.shape, net.W1.shape, net.b1.shape])
    best_eval = -1.0
    best_state = None
    stale = 0
    for epoch in range(1, args.epochs + 1):
        order = rng.permutation(len(train))
        losses = []
        for s in range(0, len(order), args.minibatch):
            idx = order[s:s + args.minibatch]
            kmax = max(train[i][0].shape[0] for i in idx)
            d = train[idx[0]][0].shape[1]
            Xp = np.zeros((len(idx), kmax, d))
            mask = np.zeros((len(idx), kmax), dtype=bool)
            kk = np.zeros(len(idx), dtype=np.int64)
            for r, i in enumerate(idx):
                Xf, k = train[i]
                Xp[r, :Xf.shape[0]] = Xf
                mask[r, :Xf.shape[0]] = True
                kk[r] = k
            pre, h, p = forward(net, Xp, mask)
            B, K = mask.shape
            rows_i = np.arange(B)
            losses.append(float(-np.mean(np.log(np.maximum(p[rows_i, kk], 1e-12)))))
            # dL/dlogits = (p - onehot)/B（マスク外は p=0 で自然に 0）
            dlogits = p.copy()
            dlogits[rows_i, kk] -= 1.0
            dlogits /= B
            dlogits = np.where(mask, dlogits, 0.0)
            # MLP へ逆伝搬（beta 項は X 経由なので学習対象外）
            dW1 = np.einsum("bkh,bk->h", h, dlogits)[:, None] + args.l2 * net.W1
            db1 = np.array([dlogits.sum()])
            dh = dlogits[:, :, None] * net.W1[None, None, :, 0]
            dpre = dh * (pre > 0)
            dW0 = np.einsum("bkd,bkh->dh", Xp, dpre) + args.l2 * net.W0
            db0 = dpre.sum(axis=(0, 1))
            net.W0, net.b0, net.W1, net.b1 = opt.step(
                [net.W0, net.b0, net.W1, net.b1], [dW0, db0, dW1, db1], args.lr)
        tr_acc = accuracy(net, train)
        ev_acc = accuracy(net, evals) if evals else float("nan")
        print(f"epoch {epoch:3d}: loss {np.mean(losses):.4f} "
              f"train_acc {tr_acc:.1%} eval_acc {ev_acc:.1%}")
        score = ev_acc if evals else tr_acc
        if score > best_eval:
            best_eval = score
            best_state = (net.W0.copy(), net.b0.copy(), net.W1.copy(), net.b1.copy())
            stale = 0
        else:
            stale += 1
            if stale >= args.patience:
                print(f"early stop (patience {args.patience})")
                break

    if best_state is not None:
        net.W0, net.b0, net.W1, net.b1 = best_state
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    pn.PolicyNet(net.W0, net.b0, net.W1, net.b1, net.beta, vocab).save(out)
    print(f"\nbest holdout acc {best_eval:.1%} "
          f"(baseline {base_eval if evals else base_train:.1%}) -> saved {out}")
    print("次: train_ppo.py --resume でこの npz を初期値に PPO 仕上げ（サーバー）。"
          "直接デプロイはしない（EXP-002）")


if __name__ == "__main__":
    main()
