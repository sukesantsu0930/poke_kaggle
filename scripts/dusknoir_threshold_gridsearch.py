"""カースドボム版 2×2 ダイブ閾値のグリッドサーチ（2026-07-25・サーバー用）。

【DEPRECATED 2026-07-26】この 2×2(safe×pain) は実測で勝率に無効（グリッド平坦）と判明し、
閾値は単一 DUSK_TH_DIVE（既定0.0=アグレッシブ）に統一済み（EXP-046e / 780b995）。
本スクリプトが振る旧4変数 DUSK_TH_* は agent 側でもう読まれない。再 tune するなら
DUSK_TH_DIVE 1本を振るように書き換えること。以下は当時の記録として残す。


DUSK_TH_{SAFE_PAIN,SAFE_NOPAIN,NOSAFE_PAIN,NOSAFE_NOPAIN} の格子を総当たりし、
均等フィールド gauntlet の「最悪対面勝率(maximin)」と「均等制圧度」で評価する。
最悪対面を主計器に、上位構成を報告（採否は別途 160戦確定）。

使い方（サーバー・軽め格子の例）:
  uv run python scripts/dusknoir_threshold_gridsearch.py \
      --grid 0.3,0.5,0.7 --games 40 --top 8
  （4次元 × |grid| 通り。|grid|=3 なら 81 構成 × 均等7対面。--coarse で対角のみ）
"""
import argparse
import itertools
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT = "agents/dragapult_dusknoir_rb"
DECK = "decks/fleet/dragapult_dusknoir_paper.csv"
FIELD = "research/meta/2026-07-20_uniform_field.csv"
KEYS = ["DUSK_TH_SAFE_PAIN", "DUSK_TH_SAFE_NOPAIN",
        "DUSK_TH_NOSAFE_PAIN", "DUSK_TH_NOSAFE_NOPAIN"]


def run_gauntlet(env, games):
    cmd = ["uv", "run", "python", "scripts/gauntlet.py",
           "--agent", AGENT, "--deck", DECK, "--field", FIELD,
           "--games", str(games), "--net", "off"]
    full = dict(os.environ)
    full.update({k: str(v) for k, v in env.items()})
    full["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=full)
    out = (r.stdout or "") + (r.stderr or "")
    worst = 1.0
    seiatsu = None
    for line in out.splitlines():
        if "==>" in line and "(" in line and "%)" in line:
            try:
                wr = float(line.split("(")[1].split("%")[0]) / 100.0
                worst = min(worst, wr)
            except Exception:
                pass
        if "制圧度" in line and "%" in line:
            try:
                seiatsu = float(line.split(":")[1].split("%")[0].strip())
            except Exception:
                pass
    return worst, seiatsu


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="0.3,0.5,0.7")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--top", type=int, default=8)
    ap.add_argument("--coarse", action="store_true",
                    help="4次元同値の対角のみ（|grid| 構成）に絞る")
    args = ap.parse_args()
    vals = [float(x) for x in args.grid.split(",")]
    combos = ([(v, v, v, v) for v in vals] if args.coarse
              else list(itertools.product(vals, repeat=4)))
    print(f"grid={vals} 構成数={len(combos)} games/構成={args.games}")
    results = []
    for i, combo in enumerate(combos, 1):
        env = dict(zip(KEYS, combo))
        worst, seiatsu = run_gauntlet(env, args.games)
        results.append((worst, seiatsu, combo))
        print(f"[{i}/{len(combos)}] {combo} -> 最悪 {worst:.1%} 均等 {seiatsu}")
    results.sort(key=lambda r: (-r[0], -(r[1] or 0)))
    print(f"\n=== 上位{args.top}（最悪対面 maximin 順）===")
    for worst, seiatsu, combo in results[:args.top]:
        print(f"  最悪 {worst:.1%} / 均等 {seiatsu} / "
              f"SAFE_PAIN={combo[0]} SAFE_NOPAIN={combo[1]} "
              f"NOSAFE_PAIN={combo[2]} NOSAFE_NOPAIN={combo[3]}")


if __name__ == "__main__":
    main()
