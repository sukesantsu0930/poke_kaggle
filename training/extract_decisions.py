"""模倣学習データの一括抽出ドライバ（Phase 2）。

全デッキ × 全エピソード日次dirについて scripts/replay_divergence.py --dump-decisions を回し、
上位ピロットの決定ログ JSONL を data/imitation/<deck>/<day>.jsonl に集める。

エピソードの対象選定は「自分の候補デッキとの重なり枚数」（--min-overlap、多重度込み）。
アーキタイプタグより厳しく「ほぼ同じリストを使う上位ピロット」だけを模倣対象にする。

使い方:
  uv run python training/extract_decisions.py [--decks marnie,dragapult] [--min-score 1000]
      [--min-overlap 45] [--episodes-root downloads/episodes] [--out-root data/imitation]

出力: data/imitation/<deck>/<day>.jsonl（data/ は gitignore 済み）+ サマリ表
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# デッキ設定: name -> (agent dir, 候補デッキCSV)
DECKS = {
    "archaludon": ("agents/archaludon_rb", "decks/fleet/archaludon_cityleague.csv"),
    "alakazam": ("agents/alakazam_rb", "decks/fleet/alakazam_5th.csv"),
    "chandelure": ("agents/chandelure_rb", "decks/fleet/chandelure_top.csv"),
    "cynthia_garchomp": ("agents/cynthia_garchomp_rb", "decks/fleet/cynthia_garchomp_top.csv"),
    "kangaskhan": ("agents/mega_kangaskhan_rb", "decks/fleet/mega_kangaskhan_top.csv"),
    "dragapult": ("agents/dragapult_rb", "decks/fleet/popular_4_dragapult.csv"),
    "marnie": ("agents/marnie_munkidori_rb",
               "decks/fleet/marnie_mainstream_0718.csv"),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--decks", help="対象デッキ名のカンマ区切り（既定: 全デッキ）")
    parser.add_argument("--episodes-root", default="downloads/episodes")
    parser.add_argument("--out-root", default="data/imitation")
    parser.add_argument("--min-score", type=float, default=1000,
                        help="模倣対象ピロットの最低LBスコア（既定1000 = 上位帯のみ）")
    parser.add_argument("--min-overlap", type=int, default=45)
    parser.add_argument("--max-games", type=int, default=250)
    args = parser.parse_args()

    names = list(DECKS) if not args.decks else [n.strip() for n in args.decks.split(",")]
    unknown = [n for n in names if n not in DECKS]
    if unknown:
        raise SystemExit(f"unknown decks: {unknown}（候補: {list(DECKS)}）")

    day_dirs = sorted(d for d in (ROOT / args.episodes_root).iterdir() if d.is_dir())
    if not day_dirs:
        raise SystemExit(f"no episode day dirs under {args.episodes_root}")

    summary = []
    for name in names:
        agent_dir, deck_csv = DECKS[name]
        for day in day_dirs:
            out = ROOT / args.out_root / name / f"{day.name}.jsonl"
            cmd = [sys.executable, str(ROOT / "scripts" / "replay_divergence.py"),
                   "--episodes", str(day.relative_to(ROOT)),
                   "--agent", agent_dir,
                   "--match-deck", deck_csv,
                   "--min-overlap", str(args.min_overlap),
                   "--min-score", str(args.min_score),
                   "--max-games", str(args.max_games),
                   "--show", "0",
                   "--dump-decisions", str(out.relative_to(ROOT))]
            r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT,
                               encoding="utf-8", errors="replace")
            games = agree = total = dumped = warn = 0
            for line in (r.stdout or "").splitlines():
                if line.startswith("games="):
                    games = int(line.split()[0].split("=")[1])
                if line.startswith("TOTAL agree"):
                    frac = line.split("agree")[1].split("=")[0].strip()  # "a/b "
                    agree, total = (int(x) for x in frac.split("/"))
                if line.startswith("dumped"):
                    dumped = int(line.split()[1])
                    warn = int(line.rsplit("warn=", 1)[1].rstrip(")"))
            status = "OK" if r.returncode == 0 else f"FAIL rc={r.returncode}"
            summary.append((name, day.name, games, total, agree, dumped, warn, status))
            print(f"{name:>18} {day.name}: games={games} decisions={total} "
                  f"agree={agree} dumped={dumped} warn={warn} [{status}]")
            if r.returncode != 0:
                sys.stderr.write((r.stderr or "")[-800:] + "\n")

    print("\n=== summary（デッキ別合計） ===")
    print(f"{'deck':>18} {'games':>6} {'decisions':>10} {'agree%':>7} {'warn':>5}")
    for name in names:
        rows = [s for s in summary if s[0] == name]
        g = sum(s[2] for s in rows)
        t = sum(s[3] for s in rows)
        a = sum(s[4] for s in rows)
        w = sum(s[6] for s in rows)
        pct = f"{a / t:.1%}" if t else "-"
        print(f"{name:>18} {g:>6} {t:>10} {pct:>7} {w:>5}")
    print(f"\n出力: {args.out_root}/<deck>/<day>.jsonl（学習は training/fit_theta.py へ）")


if __name__ == "__main__":
    main()
