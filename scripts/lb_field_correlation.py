"""ローカル・フィールドを LB に較正する（Phase 1-4）。

考え方: エージェント i の「制圧度」= Σ_a w_a * winrate(i, a)（w = フィールドの share ベクトル）。
これを複数エージェントで並べ、実 LB スコアとの Spearman 順位相関を測る。相関が高い
share ベクトル = 「ローカル順位が LB 順位を予測できる」フィールド。

入力:
  --results  gauntlet --out で追記した CSV（列: agent,deck,archetype,share,games,
             wins,losses,draws,unfinished,winrate）を1本以上。各エージェントを全アーキに
             当てて winrate を取っておく（share 列は無視。ここで任意に再重み付けする）。
  --lb       agent,lb_score の CSV（各エージェントの代表 LB スコア。ペアリングは手動＝
             ルール改変で過去 zip の忠実再現は不可能なので、現行 HEAD で走るエージェントを
             その最新 LB とペアにする方針。相関は方向性の点検であり厳密較正ではない）。
  --fields   候補フィールド CSV をカンマ区切り（archetype,share,... 形式）。各々の share を
             使って相関を出す。省略時は results 中のアーキ均等 + 各 field を比較。

出力: 各候補フィールドの Spearman 相関と、エージェント別の (LB, 制圧度) 対。
"""
from __future__ import annotations

import argparse
import csv
import glob
from collections import defaultdict
from pathlib import Path


def load_results(paths: list[str]) -> dict[str, dict[str, float]]:
    """agent -> {archetype: winrate}。同一 (agent,archetype) は加重平均。"""
    acc: dict[tuple[str, str], list[tuple[float, int]]] = defaultdict(list)
    for p in paths:
        for f in glob.glob(p):
            with open(f, encoding="utf-8-sig", newline="") as fh:
                for r in csv.DictReader(fh):
                    try:
                        wr = float(r["winrate"])
                        g = int(r.get("games", 0)) or (int(r["wins"]) + int(r["losses"]) + int(r["draws"]))
                    except (KeyError, ValueError):
                        continue
                    acc[(r["agent"], r["archetype"])].append((wr, g))
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for (agent, arch), rows in acc.items():
        tot = sum(g for _, g in rows) or 1
        out[agent][arch] = sum(wr * g for wr, g in rows) / tot
    return out


def load_lb(path: str) -> dict[str, float]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {r["agent"]: float(r["lb_score"]) for r in csv.DictReader(f) if r.get("lb_score")}


def load_field_shares(path: str) -> dict[str, float]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        sh = {r["archetype"]: float(r["share"]) for r in csv.DictReader(f) if r.get("share")}
    tot = sum(sh.values()) or 1
    return {k: v / tot for k, v in sh.items()}


def dominance(winrates: dict[str, float], shares: dict[str, float]) -> float | None:
    num = den = 0.0
    for arch, w in shares.items():
        if arch in winrates:
            num += w * winrates[arch]
            den += w
    return num / den if den else None


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = ranks(xs), ranks(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx) ** 0.5
    vy = sum((b - my) ** 2 for b in ry) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True)
    ap.add_argument("--lb", required=True)
    ap.add_argument("--fields", nargs="+", required=True, help="候補フィールド CSV 群")
    args = ap.parse_args()

    winrates = load_results(args.results)
    lb = load_lb(args.lb)
    agents = [a for a in lb if a in winrates]
    print(f"agents with both LB and results: {len(agents)}")
    for a in agents:
        print(f"  {a}: LB={lb[a]:.1f} archetypes={len(winrates[a])}")

    print("\n=== field 候補ごとの Spearman(制圧度, LB) ===")
    for fp in args.fields:
        shares = load_field_shares(fp)
        pairs = [(lb[a], dominance(winrates[a], shares)) for a in agents]
        pairs = [(l, d) for l, d in pairs if d is not None]
        if len(pairs) < 3:
            print(f"{Path(fp).name}: サンプル不足 ({len(pairs)})")
            continue
        rho = spearman([d for _, d in pairs], [l for l, _ in pairs])
        print(f"{Path(fp).name}: rho={rho:+.3f}  (n={len(pairs)})  "
              f"archetypes={sorted(shares)}")


if __name__ == "__main__":
    main()
