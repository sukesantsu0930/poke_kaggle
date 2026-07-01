from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ensure_kaggle_env(env: dict[str, str]) -> None:
    env["KAGGLE_CONFIG_DIR"] = str(ROOT / ".kaggle")
    token_path = ROOT / ".kaggle" / "access_token"
    if token_path.exists() and not env.get("KAGGLE_API_TOKEN"):
        env["KAGGLE_API_TOKEN"] = token_path.read_text(encoding="utf-8").strip()


def run_logged(command: list[str], log_path: Path, env: dict[str, str]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        log.write("$ " + " ".join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)
            log.flush()
        code = process.wait()
        if code != 0:
            raise subprocess.CalledProcessError(code, command)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Top Episodes の1000件抽出分析プロトコルを実行します。")
    parser.add_argument("--dataset-date", default="2026-06-30")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--dataset-prefix", default="kaggle/pokemon-tcg-ai-battle-episodes")
    args = parser.parse_args()

    run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    run_dir = ROOT / "research" / "episode_deck_analysis" / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset = f"{args.dataset_prefix}-{args.dataset_date}"
    episode_dir = ROOT / "downloads" / "episodes" / args.dataset_date
    manifest = run_dir / f"{args.dataset_date}_files_{args.limit}.csv"
    download_log = run_dir / "download.log"
    analysis_log = run_dir / "analysis.log"

    env = os.environ.copy()
    ensure_kaggle_env(env)

    print(f"Run directory: {run_dir}")
    print(f"Episode cache: {episode_dir}")
    print(f"Download log: {download_log}")
    print(f"Analysis log: {analysis_log}")

    run_logged(
        [
            sys.executable,
            "scripts/download_episode_sample.py",
            "--dataset",
            dataset,
            "--limit",
            str(args.limit),
            "--output-dir",
            str(episode_dir.relative_to(ROOT)),
            "--manifest",
            str(manifest.relative_to(ROOT)),
            "--log",
            str(download_log.relative_to(ROOT)),
        ],
        download_log,
        env,
    )

    common = [
        "--input-dir",
        str(episode_dir.relative_to(ROOT)),
        "--manifest",
        str(manifest.relative_to(ROOT)),
    ]
    run_logged(
        [
            sys.executable,
            "scripts/rank_episode_deck_winrates.py",
            *common,
            "--out",
            str((run_dir / "winrate_candidates.md").relative_to(ROOT)),
        ],
        analysis_log,
        env,
    )
    run_logged(
        [
            sys.executable,
            "scripts/analyze_episode_decks.py",
            *common,
            "--out",
            str((run_dir / "archetypes.md").relative_to(ROOT)),
        ],
        analysis_log,
        env,
    )
    run_logged(
        [
            sys.executable,
            "scripts/build_candidate_decks_from_episodes.py",
            *common,
            "--out-dir",
            str((run_dir / "decks").relative_to(ROOT)),
        ],
        analysis_log,
        env,
    )

    print("Done.")
    print(f"Open: {run_dir}")


if __name__ == "__main__":
    main()
