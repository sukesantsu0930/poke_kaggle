"""ラダースコアの定点記録 — 提出物のスコア推移（収束カーブ）を CSV に追記する。

提出戦略.md の「泳がせ時間の較正」用。Windows タスクスケジューラから定期実行される想定
（Claude やセッション不要。PCが起動していれば動く）。手動実行も可:

  uv run python scripts\\log_ladder_scores.py

出力: research/ladder/scores.csv（logged_at, ref, fileName, status, publicScore）
タスク登録/解除:
  schtasks /Query  /TN poke_kaggle_ladder_log
  schtasks /Delete /TN poke_kaggle_ladder_log /F
"""
import csv
import io
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "ladder" / "scores.csv"
COMPETITION = "pokemon-tcg-ai-battle"


def main():
    token_file = ROOT / ".kaggle" / "access_token"
    env = dict(os.environ)
    if token_file.exists():
        env["KAGGLE_API_TOKEN"] = token_file.read_text().strip()

    python = ROOT / ".venv" / "Scripts" / "python.exe"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [str(python), "-m", "kaggle", "competitions", "submissions", COMPETITION, "--csv"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=env, timeout=120,
    )
    if result.returncode != 0:
        print(f"NG kaggle CLI failed: {result.stderr[:200]}")
        raise SystemExit(1)

    rows = list(csv.DictReader(io.StringIO(result.stdout)))
    if not rows:
        print("NG no submissions parsed")
        raise SystemExit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT.exists()
    logged_at = datetime.now().isoformat(timespec="seconds")
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["logged_at", "ref", "fileName", "status", "publicScore"])
        for r in rows:
            w.writerow([logged_at, r.get("ref", ""), r.get("fileName", ""),
                        r.get("status", "").replace("SubmissionStatus.", ""),
                        r.get("publicScore", "")])
    print(f"OK logged {len(rows)} rows at {logged_at} -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
