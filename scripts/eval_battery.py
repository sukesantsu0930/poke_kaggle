"""eval_battery — L1〜L3 を1コマンドで回し、日付付きレポートを research/eval/ に出す。

`docs/planning/評価方法.md` の実行器。既存3スクリプトを subprocess で呼ぶだけの薄いラッパー
（ロジックは再実装しない）:

  L1 check_agent       : 不変条件（既定10戦）
  L2 gauntlet          : フィールドCSV・シェア加重の制圧度（既定30戦/マッチ。P-03: ±10pt級ノイズ帯）
  L3 replay_divergence : ホールドアウト日エピソードの上位ピロット一致率（人間アンカー。P-09/P-10）

使い方:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/eval_battery.py ^
      --agent agents/marnie_munkidori_rb ^
      --deck decks/fleet/winrate_2_marnie_grimmsnarl.csv ^
      --archetype-cards 648,112 --holdout downloads/episodes/2026-07-05 ^
      [--games 30] [--check-games 10] [--div-max-games 60] [--min-score 900] [--only l1,l3]

出力: research/eval/<date>_<agent>.md（L1/L2/L3 の3セクション + サマリ）。
判定（L2改善∧L3非悪化）は人間が行い、結論はデッキ設計md / PROJECT_DIARY に転記する。
"""
import argparse
import datetime
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run_step(cmd, timeout=7200):
    """subprocess を UTF-8 で実行し (exit_code, output, elapsed_sec) を返す。"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), env=env, timeout=timeout,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = proc.stdout.decode("utf-8", errors="replace")
        code = proc.returncode
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"").decode("utf-8", errors="replace") + "\n[TIMEOUT]"
        code = -1
    return code, out, time.time() - t0


def grep1(pattern, text, default="(not found)"):
    m = re.search(pattern, text)
    return m.group(0) if m else default


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, help="対象エージェントdir（agents/xxx_rb）")
    parser.add_argument("--deck", required=True, help="対象デッキCSV")
    parser.add_argument("--archetype-cards", required=True,
                        help="L3: 対象デッキの識別カードID（カンマ区切り）")
    parser.add_argument("--holdout", required=True,
                        help="L3: ホールドアウト日のエピソードdir（downloads/episodes/<date>）")
    parser.add_argument("--games", type=int, default=30, help="L2: gauntlet の戦数/マッチ")
    parser.add_argument("--check-games", type=int, default=10, help="L1: check_agent の戦数")
    parser.add_argument("--div-max-games", type=int, default=60, help="L3: divergence の最大試合数")
    parser.add_argument("--min-score", type=float, default=900, help="L3: 対象ピロットの最低レート")
    parser.add_argument("--field", default="research/meta/2026-07-14_field.csv")
    parser.add_argument("--leaderboard", default="downloads/leaderboard")
    parser.add_argument("--only", help="実行層の絞り込み（例: l1,l3。省略時は全部）")
    parser.add_argument("--out-dir", default="research/eval")
    args = parser.parse_args()

    layers = {s.strip().lower() for s in args.only.split(",")} if args.only else {"l1", "l2", "l3"}
    agent_name = Path(args.agent).name
    date = datetime.date.today().isoformat()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date}_{agent_name}.md"
    n = 2
    while out_path.exists():
        out_path = out_dir / f"{date}_{agent_name}_{n}.md"
        n += 1

    steps = []
    if "l1" in layers:
        steps.append(("L1 check_agent（不変条件）",
                      [PY, "scripts/check_agent.py", "--agent", args.agent,
                       "--deck", args.deck, "--games", str(args.check_games)]))
    if "l2" in layers:
        steps.append(("L2 gauntlet（メタ加重プール対戦）",
                      [PY, "scripts/gauntlet.py", "--agent", args.agent,
                       "--deck", args.deck, "--field", args.field,
                       "--games", str(args.games)]))
    if "l3" in layers:
        steps.append(("L3 replay_divergence（人間アンカー・ホールドアウト日）",
                      [PY, "scripts/replay_divergence.py", "--episodes", args.holdout,
                       "--agent", args.agent, "--archetype-cards", args.archetype_cards,
                       "--leaderboard", args.leaderboard,
                       "--min-score", str(args.min_score),
                       "--max-games", str(args.div_max_games)]))

    results = []
    for title, cmd in steps:
        print(f"=== {title} ===", flush=True)
        print("$ " + " ".join(cmd), flush=True)
        code, out, sec = run_step(cmd)
        print(out, flush=True)
        results.append((title, cmd, code, out, sec))

    # ── サマリ抽出（表示用。数値の正本は各セクションの生ログ） ──
    summary = []
    for title, cmd, code, out, sec in results:
        if title.startswith("L1"):
            verdict = "合格" if code == 0 else "**不合格**"
            summary.append(f"- **L1**: {verdict}（exit={code}） — "
                           f"`{grep1(r'decisions=\d+ wins=\d+/\d+', out)}`")
        elif title.startswith("L2"):
            summary.append(f"- **L2**: {grep1(r'制圧度（シェア加重勝率）: [\d.]+%.*', out)} / "
                           f"{grep1(r'最弱マッチアップ: .*', out)}")
        elif title.startswith("L3"):
            summary.append(f"- **L3**: {grep1(r'TOTAL agree \d+/\d+ = [\d.]+%', out)} — "
                           f"`{grep1(r'games=\d+', out)}` holdout={args.holdout}")

    lines = [
        f"# eval_battery: {agent_name}（{date}）",
        "",
        f"- agent: `{args.agent}` / deck: `{args.deck}`",
        f"- L2: field=`{args.field}` games/マッチ={args.games}（P-03: ±10pt級ノイズ帯）",
        f"- L3: holdout=`{args.holdout}` cards={args.archetype_cards} "
        f"min-score={args.min_score} max-games={args.div_max_games}",
        f"- 判定規則: L2改善 ∧ L3非悪化（±3pt=ノイズ帯 / 5pt超低下=コンテキスト別に調査）。"
        f"正典: `docs/planning/評価方法.md`",
        "",
        "## サマリ",
        "",
        *summary,
        "",
    ]
    for title, cmd, code, out, sec in results:
        lines += [f"## {title}", "",
                  f"- cmd: `{' '.join(cmd[1:])}`（exit={code}, {sec:.0f}s）", "",
                  "```", out.rstrip(), "```", ""]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nreport -> {out_path}")


if __name__ == "__main__":
    main()
