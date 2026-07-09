"""模倣学習によるルール強度 θ の推定（Phase 2 = 条件付きロジット / Plackett-Luce）。

data/imitation/<deck>/*.jsonl（1決定=1行: 候補の score/reason/band + 上位者の選択）から、
θ[reason]（reason 別のスコア加算値）を上位者の選択尤度最大化で推定する。

モデル（デプロイの argmax(score + θ[reason]) と整合する平滑化）:
    u_i = (score_i + θ[r_i]) / T          T = 温度（スコアの桁を尤度に写すスケール）
    複数選択は Plackett-Luce: 選ばれた順に softmax → 除外 → softmax …
    損失 = -log尤度 + λ/2 · Σθ²          （ridge の中心は θ=0 = 手書きスコアそのまま）

聖域との整合（デプロイ側 _apply_theta と同じ制約を訓練にも掛ける）:
  - R-07 系 reason（apply_protocol の出力）はデプロイで θ が掛からないため学習から除外
  - band=lethal/error の候補の u は θ を掛けず固定
  - 検証時の argmax 評価は band ガード込みで行う

使い方:
  uv run python training/fit_theta.py --deck marnie [--temp 1000] [--l2 3.0]
      [--min-count 5] [--iters 300] [--out agents/marnie_munkidori_rb/theta.json]

出力: θ 上位の変化一覧 + held-out 一致率（θ=0 と適合後）+ theta.json（--out 指定時）
"""
import argparse
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

PROTOCOL_PREFIX = "R-07"          # apply_protocol の出力層（デプロイで θ 不可達）
FROZEN_BANDS = {"lethal", "error"}


def load_rows(deck_dir: Path):
    rows = []
    seen = set()
    for fp in sorted(deck_dir.glob("*.jsonl")):
        for line in open(fp, encoding="utf-8"):
            r = json.loads(line)
            key = (r["episode"], r["pi"], r["step"])   # 日次dir間の重複エピソードを除去
            if key in seen:
                continue
            seen.add(key)
            rows.append(r)
    return rows


def build_dataset(rows, min_count):
    """学習可能な reason の語彙を決め、決定を (scores, reason_idx, chosen順) に整形する。"""
    counts = Counter(o["reason"] for r in rows for o in r["options"])
    vocab = sorted(
        rea for rea, c in counts.items()
        if c >= min_count and not rea.startswith(PROTOCOL_PREFIX))
    idx = {rea: i for i, rea in enumerate(vocab)}

    data = []
    for r in rows:
        opts = sorted(r["options"], key=lambda o: o["i"])
        scores = np.array([float(o["score"]) for o in opts])
        # 語彙外/凍結帯は -1 = θ を掛けない
        ridx = np.array([
            idx.get(o["reason"], -1) if o["band"] not in FROZEN_BANDS else -1
            for o in opts], dtype=np.int64)
        pos = {o["i"]: k for k, o in enumerate(opts)}
        chosen = [pos[i] for i in r["human"] if i in pos]
        if not chosen or len(opts) < 2:
            continue
        data.append((scores, ridx, chosen, r))
    return vocab, data


def decision_nll_grad(theta, scores, ridx, chosen, temp):
    """Plackett-Luce の -log尤度と ∂/∂θ。選ばれた順に softmax → 除外。"""
    u = scores.copy()
    mask = ridx >= 0
    u[mask] += theta[ridx[mask]]
    u /= temp
    alive = np.ones(len(u), dtype=bool)
    nll = 0.0
    grad = np.zeros_like(theta)
    for k in chosen:
        z = u[alive] - u[alive].max()
        p = np.exp(z)
        p /= p.sum()
        full_p = np.zeros(len(u))
        full_p[alive] = p
        nll -= math.log(max(full_p[k], 1e-300))
        # ∂nll/∂u_j = (p_j - 1[j==k]) / temp → reason 次元へ散らす
        g = full_p / temp
        g[k] -= 1.0 / temp
        for j in np.nonzero(alive)[0]:
            if ridx[j] >= 0 and g[j] != 0.0:
                grad[ridx[j]] += g[j]
        alive[k] = False
        if not alive.any():
            break
    return nll, grad


def greedy_select(theta, scores, ridx, rec, temp=None):
    """デプロイと同じ選択（バンドガード込み argmax、辞書式 (score,-index)、minCount規則）。"""
    opts = sorted(rec["options"], key=lambda o: o["i"])
    adj = []
    for k, o in enumerate(opts):
        s = float(o["score"])
        if ridx[k] >= 0:
            t = theta[ridx[k]]
            new = s + t
            b = o["band"]
            nb = ("lethal" if new >= 999_999 else "error" if new == -999_999
                  else "positive" if new > 0 else "zero" if new == 0 else "negative")
            if b not in FROZEN_BANDS and nb == b:
                s = new
        adj.append(s)
    order = sorted(range(len(opts)), key=lambda k: (-adj[k], opts[k]["i"]))
    selected = []
    for k in order:
        if len(selected) >= rec["max_count"]:
            break
        if adj[k] < 0 and len(selected) >= rec["min_count"]:
            continue
        selected.append(opts[k]["i"])
    if len(selected) < rec["min_count"]:
        selected = [opts[k]["i"] for k in order[:rec["min_count"]]]
    return selected


def evaluate(theta, data, ridx_cache):
    agree = 0
    by_ctx = Counter()
    by_ctx_total = Counter()
    for scores, ridx, chosen, rec in data:
        sel = greedy_select(theta, scores, ridx, rec)
        ok = sel == rec["human"]
        agree += ok
        by_ctx_total[rec["ctx_name"]] += 1
        by_ctx[rec["ctx_name"]] += ok
    return agree / max(len(data), 1), by_ctx, by_ctx_total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deck", required=True, help="data/imitation/<deck> のデッキ名")
    parser.add_argument("--data-root", default="data/imitation")
    parser.add_argument("--temp", type=float, default=1000.0,
                        help="softmax 温度（ソフト帯の代表的スコア差の桁に合わせる）")
    parser.add_argument("--l2", type=float, default=3.0,
                        help="ridge 係数 λ（決定あたりに正規化して適用）")
    parser.add_argument("--min-count", type=int, default=5,
                        help="学習対象とする reason の最低出現回数")
    parser.add_argument("--iters", type=int, default=300)
    parser.add_argument("--lr", type=float, default=200.0, help="Adam 学習率（スコア単位）")
    parser.add_argument("--holdout", type=float, default=0.2,
                        help="held-out 比率（エピソード単位で分割）")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", help="theta.json の出力先（省略時は書かない）")
    parser.add_argument("--top", type=int, default=25, help="表示する θ 上位件数")
    args = parser.parse_args()

    rows = load_rows(ROOT / args.data_root / args.deck)
    if not rows:
        raise SystemExit(f"no data under {args.data_root}/{args.deck}")

    # エピソード単位で train/holdout 分割（決定単位だと同一試合がリークする）
    episodes = sorted({r["episode"] for r in rows})
    rng = np.random.default_rng(args.seed)
    held = set(rng.choice(episodes, size=max(1, int(len(episodes) * args.holdout)),
                          replace=False).tolist())
    train_rows = [r for r in rows if r["episode"] not in held]
    hold_rows = [r for r in rows if r["episode"] in held]

    vocab, train = build_dataset(train_rows, args.min_count)
    # hold は train 語彙で引き直す（hold にしか出ない reason は θ 対象外 = -1）
    idx = {rea: i for i, rea in enumerate(vocab)}
    hold = []
    for r in hold_rows:
        opts = sorted(r["options"], key=lambda o: o["i"])
        if len(opts) < 2 or not r["human"]:
            continue
        scores = np.array([float(o["score"]) for o in opts])
        ridx = np.array([
            idx.get(o["reason"], -1) if o["band"] not in FROZEN_BANDS else -1
            for o in opts], dtype=np.int64)
        hold.append((scores, ridx, [], r))

    print(f"deck={args.deck} rows={len(rows)} (train={len(train)} hold={len(hold)}) "
          f"episodes={len(episodes)} vocab={len(vocab)} reasons "
          f"(min_count={args.min_count}, R-07系は凍結)")

    theta = np.zeros(len(vocab))
    m = np.zeros_like(theta)
    v = np.zeros_like(theta)
    n = max(len(train), 1)
    for it in range(1, args.iters + 1):
        nll = 0.0
        grad = np.zeros_like(theta)
        for scores, ridx, chosen, _ in train:
            d_nll, d_grad = decision_nll_grad(theta, scores, ridx, chosen, args.temp)
            nll += d_nll
            grad += d_grad
        nll = nll / n + 0.5 * args.l2 * float(theta @ theta) / (n * args.temp**2)
        grad = grad / n + args.l2 * theta / (n * args.temp**2)
        m = 0.9 * m + 0.1 * grad
        v = 0.999 * v + 0.001 * grad**2
        mh = m / (1 - 0.9**it)
        vh = v / (1 - 0.999**it)
        theta -= args.lr * mh / (np.sqrt(vh) + 1e-12)
        if it % 50 == 0 or it == 1:
            print(f"  iter {it:>4}: train NLL/decision = {nll:.4f}")

    zero = np.zeros_like(theta)
    tr0, _, _ = evaluate(zero, train, None)
    tr1, _, _ = evaluate(theta, train, None)
    ho0, c0, ct = evaluate(zero, hold, None)
    ho1, c1, _ = evaluate(theta, hold, None)
    print(f"\n一致率（決定の完全一致）: train {tr0:.1%} -> {tr1:.1%} | "
          f"held-out {ho0:.1%} -> {ho1:.1%}")
    print("\n-- held-out の SelectContext 別（θ=0 -> θ、件数降順） --")
    for name in sorted(ct, key=lambda x: -ct[x])[:12]:
        print(f"  {name:>18}: {c0[name]}/{ct[name]} -> {c1[name]}/{ct[name]}")

    order = np.argsort(-np.abs(theta))
    print(f"\n-- |θ| 上位 {args.top}（reason: 加算値） --")
    for i in order[:args.top]:
        if abs(theta[i]) < 1:
            break
        print(f"  {theta[i]:>+9.0f}  {vocab[i]}")

    if args.out:
        out = ROOT / args.out
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {vocab[i]: round(float(theta[i]), 2)
                   for i in range(len(vocab)) if abs(theta[i]) >= 1}
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {len(payload)} thetas -> {out}")


if __name__ == "__main__":
    main()
