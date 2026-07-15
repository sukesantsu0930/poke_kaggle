"""V(s) / 脅威分類器の学習 — numpy 単体の MLP（BCE + Adam）+ holdout 評価 + npz 出力。

依存を numpy に限定する理由: 推論（agents/_base/value_model.py）が提出環境で numpy しか
仮定できないため、学習も同じ前提に揃えて重みの互換問題を消す。データ規模（数万〜数十万行 ×
47次元）では CPU numpy で十分速い。

分割は **エピソード単位**（行単位は同一対局のラベル共有でリークする）。
評価は AUC / 精度 / ターン帯別 AUC / 較正表。合格の目安（L0）:
  - holdout AUC が「サイド差だけのロジスティック」ベースラインを明確に上回る
  - 終盤ほど AUC が高い（勝敗が盤面に書き込まれていくのが正しい挙動）

使い方:
  uv run python training/train_value.py [--data data/value] [--target win|threat]
      [--hidden 64] [--epochs 30] [--out models/value_v1.npz]

出力 npz は value_model.ValueModel.load 互換（W0,b0,W1,b1,mean,std,feature_version,n_layers）。
デプロイ: 提出 zip へは build_submission --extra models/value_v1.npz=value_model.npz、
ローカル評価へは agents/<deck>_rb/value_model.npz にコピーして gauntlet --search value。
"""
import argparse
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_base"))
sys.path.insert(0, str(ROOT / "submission"))

import value_model as vm  # noqa: E402


def auc(y, p):
    """rank ベースの AUC（依存なし）。"""
    order = np.argsort(p)
    rank = np.empty_like(order, dtype=np.float64)
    rank[order] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    if n1 == 0 or n0 == 0:
        return float("nan")
    return (rank[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def train_mlp(Xtr, ytr, Xva, yva, hidden, epochs, lr=1e-3, batch=512, seed=7, patience=5):
    rng = np.random.default_rng(seed)
    n, d = Xtr.shape
    if hidden > 0:
        W0 = rng.normal(0, np.sqrt(2.0 / d), (d, hidden)); b0 = np.zeros(hidden)
        W1 = rng.normal(0, np.sqrt(2.0 / hidden), (hidden, 1)); b1 = np.zeros(1)
        params = [W0, b0, W1, b1]
    else:
        W1 = np.zeros((d, 1)); b1 = np.zeros(1)
        params = [W1, b1]
    m = [np.zeros_like(p) for p in params]
    v = [np.zeros_like(p) for p in params]
    t_adam = 0

    def forward(X, ps):
        if hidden > 0:
            W0, b0, W1, b1 = ps
            h = np.maximum(X @ W0 + b0, 0.0)
            return h, h @ W1 + b1
        W1, b1 = ps
        return None, X @ W1 + b1

    def predict(X, ps):
        return 1.0 / (1.0 + np.exp(-forward(X, ps)[1][:, 0]))

    best_auc, best_params, bad = -1.0, [p.copy() for p in params], 0
    for ep in range(1, epochs + 1):
        idx = rng.permutation(n)
        for s in range(0, n, batch):
            bi = idx[s:s + batch]
            X, y = Xtr[bi], ytr[bi]
            h, z = forward(X, params)
            p = 1.0 / (1.0 + np.exp(-z[:, 0]))
            dz = ((p - y) / len(y))[:, None]
            grads = []
            if hidden > 0:
                W0, b0, W1, b1 = params
                gW1 = h.T @ dz; gb1 = dz.sum(0)
                dh = dz @ W1.T * (h > 0)
                gW0 = X.T @ dh; gb0 = dh.sum(0)
                grads = [gW0, gb0, gW1, gb1]
            else:
                grads = [X.T @ dz, dz.sum(0)]
            t_adam += 1
            for j, g in enumerate(grads):
                m[j] = 0.9 * m[j] + 0.1 * g
                v[j] = 0.999 * v[j] + 0.001 * g * g
                mh = m[j] / (1 - 0.9 ** t_adam)
                vh = v[j] / (1 - 0.999 ** t_adam)
                params[j] -= lr * mh / (np.sqrt(vh) + 1e-8)
        va = auc(yva, predict(Xva, params))
        marker = ""
        if va > best_auc:
            best_auc, best_params, bad, marker = va, [p.copy() for p in params], 0, "  *best"
        else:
            bad += 1
        print(f"  epoch {ep:>2}: valid AUC {va:.4f}{marker}")
        if bad >= patience:
            print(f"  early stop (patience {patience})")
            break
    return best_params, best_auc, (lambda X, ps=best_params: predict(X, ps))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/value")
    parser.add_argument("--target", choices=["win", "threat"], default="win")
    parser.add_argument("--hidden", type=int, default=64, help="0 でロジスティック回帰")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--holdout-frac", type=float, default=0.2)
    parser.add_argument("--out", default="models/value_v1.npz")
    args = parser.parse_args()

    files = sorted((ROOT / args.data).glob("*.npz"))
    if not files:
        raise SystemExit(f"no npz in {args.data}（先に extract_value_dataset.py）")
    Xs, ys, eids, turns = [], [], [], []
    for f in files:
        z = np.load(f)
        if int(z["feature_version"][0]) != vm.FEATURE_VERSION:
            raise SystemExit(f"{f.name}: feature_version 不一致（再抽出が必要）")
        Xs.append(z["X"]); ys.append(z[f"y_{args.target}"])
        eids.append(z["episode_id"]); turns.append(z["turn"])
        print(f"loaded {f.name}: {len(z['X'])} rows")
    X = np.concatenate(Xs).astype(np.float64)
    y = np.concatenate(ys).astype(np.float64)
    eid = np.concatenate(eids)
    turn = np.concatenate(turns)

    # エピソード単位の分割（行単位はリーク）
    va_mask = (eid % 100) < int(args.holdout_frac * 100)
    tr_mask = ~va_mask
    mean = X[tr_mask].mean(0)
    std = X[tr_mask].std(0) + 1e-6
    Xn = (X - mean) / std
    print(f"train {tr_mask.sum()} rows / valid {va_mask.sum()} rows "
          f"({len(np.unique(eid))} episodes, 陽性率 {y.mean():.3f})")

    # ベースライン: サイド差だけのロジスティック（V の合格下限）
    prize_diff = X[:, 42:43]   # extract_features の大局特徴の先頭（サイドレース差）
    pd_n = (prize_diff - prize_diff[tr_mask].mean()) / (prize_diff[tr_mask].std() + 1e-6)
    _, base_auc, _ = train_mlp(pd_n[tr_mask], y[tr_mask], pd_n[va_mask], y[va_mask],
                               hidden=0, epochs=5)
    print(f"baseline（サイド差のみ）: valid AUC {base_auc:.4f}\n")

    params, best_auc, predict = train_mlp(
        Xn[tr_mask], y[tr_mask], Xn[va_mask], y[va_mask],
        hidden=args.hidden, epochs=args.epochs)

    p_va = predict(Xn[va_mask])
    y_va, t_va = y[va_mask], turn[va_mask]
    print(f"\nholdout AUC {best_auc:.4f}（ベースライン {base_auc:.4f}）  "
          f"acc {(np.round(p_va) == y_va).mean():.4f}")
    for lo, hi, label in [(0, 4, "序盤 t≤4"), (5, 12, "中盤 5-12"), (13, 99, "終盤 13+")]:
        m = (t_va >= lo) & (t_va <= hi)
        if m.sum() > 100:
            print(f"  {label:>10}: AUC {auc(y_va[m], p_va[m]):.4f}  (n={m.sum()})")
    print("較正（予測decile → 実勝率）:")
    for d in range(10):
        m = (p_va >= d / 10) & (p_va < (d + 1) / 10)
        if m.sum() > 50:
            print(f"  [{d/10:.1f},{(d+1)/10:.1f}): pred {p_va[m].mean():.3f} "
                  f"actual {y_va[m].mean():.3f} (n={m.sum()})")

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    save = {"mean": mean, "std": std,
            "feature_version": np.array([vm.FEATURE_VERSION]),
            "n_layers": np.array([2 if args.hidden > 0 else 1])}
    if args.hidden > 0:
        save.update({"W0": params[0], "b0": params[1], "W1": params[2], "b1": params[3]})
    else:
        save.update({"W0": params[0], "b0": params[1]})
    np.savez(out, **save)
    print(f"\nwrote {out}")
    print("デプロイ: cp models/... agents/<deck>_rb/value_model.npz → gauntlet --search value")


if __name__ == "__main__":
    main()
