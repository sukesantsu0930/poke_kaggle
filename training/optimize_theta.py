"""θ の gauntlet 制圧度によるブラックボックス最適化（Phase 4 = RL段、CEM）。

模倣で初期化した θ（theta.json）を出発点に、Cross-Entropy Method で
シェア加重勝率（制圧度）を直接最大化する。依存は numpy のみ。

- 候補 θ は `policy.theta = dict` の直接注入（ファイル書き換え不要・高速）
- 対戦は scripts/ab_battle.run_battles（cg 直叩き）、相手プールは gauntlet の field CSV
- 聖域は実行時 _apply_theta の band ガードが常時保証（最適化がどんな値を出しても安全）

使い方:
  uv run python training/optimize_theta.py --agent agents/marnie_munkidori_rb \
      --deck decks/candidates/2026-06-30_top5/winrate_2_marnie_grimmsnarl.csv \
      --init agents/marnie_munkidori_rb/theta.json --top-k 24 \
      [--pop 12] [--elite 3] [--iters 20] [--games 8] [--sigma 2000] \
      [--only marnie,alakazam] [--out build/cem/marnie]

出力: 反復ごとの best/mean 制圧度 + <out>/theta_best.json（毎反復チェックポイント）
      + <out>/history.csv（LEDGER 記入用）
"""
import argparse
import contextlib
import csv
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from ab_battle import get_policy, load_agent, read_deck, run_battles  # noqa: E402
from gauntlet import build_opponent, read_field  # noqa: E402


def evaluate(target_mod, target_deck, opponents, games, max_steps):
    """制圧度（シェア加重勝率、0-1）。opponents = [(row, opp_mod, opp_deck)]。
    run_battles のマッチアップ毎 print は握りつぶす（CEM は数百回呼ぶため）。"""
    num = den = 0.0
    with contextlib.redirect_stdout(io.StringIO()):
        num, den = _evaluate_inner(target_mod, target_deck, opponents, games, max_steps)
    return num / den if den else 0.0


def _evaluate_inner(target_mod, target_deck, opponents, games, max_steps):
    num = den = 0.0
    for row, opp_mod, opp_deck in opponents:
        half = games // 2
        w1 = run_battles(half, target_mod, target_deck, opp_mod, opp_deck,
                         max_steps, f"eval vs {row['archetype']} [p0]")
        w2 = run_battles(games - half, opp_mod, opp_deck, target_mod, target_deck,
                         max_steps, f"eval vs {row['archetype']} [p1]")
        wins = w1[0] + w2[1]
        losses = w1[1] + w2[0]
        decided = wins + losses
        wr = wins / decided if decided else 0.0
        num += row["share"] * wr
        den += row["share"]
    return num, den


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--deck", required=True)
    parser.add_argument("--field", default="research/meta/2026-07-08_field.csv")
    parser.add_argument("--only", help="アーキタイプ名のカンマ区切り（高速スモーク用）")
    parser.add_argument("--init", help="初期 θ の theta.json（省略時は --keys 必須で 0 初期化）")
    parser.add_argument("--keys", help="最適化する reason のカンマ区切り（省略時は init の上位から）")
    parser.add_argument("--top-k", type=int, default=24,
                        help="init から |θ| 上位いくつを最適化対象にするか（次元制御）")
    parser.add_argument("--init-scale", type=float, default=1.0,
                        help="初期平均 = init値 × この係数。0 で「reason の選定だけ init から借り、"
                             "初期値は手書き基準(θ=0)」のコールドスタート（EXP-002 の教訓）")
    parser.add_argument("--pop", type=int, default=12)
    parser.add_argument("--elite", type=int, default=3)
    parser.add_argument("--iters", type=int, default=20)
    parser.add_argument("--games", type=int, default=8, help="1候補・1マッチアップの試合数")
    parser.add_argument("--sigma", type=float, default=2000.0, help="初期標準偏差（スコア単位）")
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="build/cem/run")
    args = parser.parse_args()

    init = {}
    if args.init:
        init = {str(k): float(v)
                for k, v in json.loads((ROOT / args.init).read_text(encoding="utf-8")).items()}
    if args.keys:
        keys = [k.strip() for k in args.keys.split(",")]
    elif init:
        keys = [k for k, _ in sorted(init.items(), key=lambda kv: -abs(kv[1]))[:args.top_k]]
    else:
        raise SystemExit("--init か --keys のどちらかを指定")
    fixed = {k: v for k, v in init.items() if k not in keys}   # 対象外の θ は固定値で保持

    field = read_field(ROOT / args.field)
    if args.only:
        names = {n.strip() for n in args.only.split(",")}
        field = [r for r in field if r["archetype"] in names]
    opponents = []
    for row in field:
        try:
            opp_mod, opp_deck = build_opponent(row)
            opponents.append((row, opp_mod, opp_deck))
        except Exception as e:
            print(f"SKIP {row['archetype']}: {type(e).__name__}: {e}")
    if not opponents:
        raise SystemExit("no opponents")

    target_mod = load_agent(ROOT / args.agent)
    policy = get_policy(target_mod)
    if policy is None:
        raise SystemExit("BasePolicy エージェントではない（theta 注入不可）")
    target_deck = read_deck(ROOT / args.deck)

    out_dir = ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    hist = open(out_dir / "history.csv", "w", newline="", encoding="utf-8")
    hcsv = csv.writer(hist)
    hcsv.writerow(["iter", "candidate", "control", "best", "mean", "elapsed_s"])

    rng = np.random.default_rng(args.seed)
    mean = np.array([init.get(k, 0.0) * args.init_scale for k in keys])
    sigma = np.full(len(keys), args.sigma)
    best_score = -1.0
    best_theta = dict(init)
    games_per_eval = args.games * len(opponents)
    print(f"CEM: dim={len(keys)} pop={args.pop} elite={args.elite} iters={args.iters} "
          f"games/eval={games_per_eval}（{len(opponents)} matchups × {args.games}）")

    for it in range(1, args.iters + 1):
        t0 = time.perf_counter()
        pop = mean + sigma * rng.standard_normal((args.pop, len(keys)))
        pop[0] = mean                       # 現在の平均も必ず評価（安全網）
        scores = []
        for c, vec in enumerate(pop):
            policy.theta = {**fixed, **{k: float(v) for k, v in zip(keys, vec)}}
            s = evaluate(target_mod, target_deck, opponents, args.games, args.max_steps)
            scores.append(s)
            hcsv.writerow([it, c, "", f"{s:.4f}", "", ""])
        scores = np.array(scores)
        elite_idx = np.argsort(-scores)[:args.elite]
        mean = pop[elite_idx].mean(axis=0)
        sigma = pop[elite_idx].std(axis=0) * 0.9 + 1e-3   # 収縮（+下限で退化防止）
        it_best = float(scores.max())
        if it_best > best_score:
            best_score = it_best
            best_theta = {**fixed,
                          **{k: float(v) for k, v in zip(keys, pop[int(np.argmax(scores))])}}
            (out_dir / "theta_best.json").write_text(
                json.dumps({k: round(v, 2) for k, v in best_theta.items() if abs(v) >= 1},
                           ensure_ascii=False, indent=1), encoding="utf-8")
        dt = time.perf_counter() - t0
        hcsv.writerow([it, "", "", f"{it_best:.4f}", f"{scores.mean():.4f}", f"{dt:.0f}"])
        hist.flush()
        print(f"iter {it:>3}: best={it_best:.1%} mean={scores.mean():.1%} "
              f"(all-time best={best_score:.1%}) [{dt:.0f}s]")

    hist.close()
    print(f"\nbest 制圧度 = {best_score:.1%} -> {out_dir / 'theta_best.json'}")
    print("採用は L1 確定（320試合・+7pt基準・holdout相手）を通してから "
          "agents/<deck>/theta.json へコピーする（実験計画 §5）")


if __name__ == "__main__":
    main()
