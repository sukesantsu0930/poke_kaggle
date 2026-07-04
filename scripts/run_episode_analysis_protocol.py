from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "research" / "episode_deck_analysis" / "runs"


def ensure_kaggle_env(env: dict[str, str]) -> None:
    env["KAGGLE_CONFIG_DIR"] = str(ROOT / ".kaggle")
    env.setdefault("PYTHONIOENCODING", "utf-8")
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
            safe_line = line.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
                sys.stdout.encoding or "utf-8"
            )
            print(safe_line, end="")
            log.write(line)
            log.flush()
        code = process.wait()
        if code != 0:
            raise subprocess.CalledProcessError(code, command)


def latest_run_dir() -> Path:
    candidates = [path for path in RUNS_DIR.glob("*") if path.is_dir()]
    if not candidates:
        raise FileNotFoundError(f"No analysis runs found under {RUNS_DIR}")
    return sorted(candidates)[-1]


def resolve_run_dir(value: str | None) -> Path:
    if value is None:
        run_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return RUNS_DIR / run_id
    if value == "latest":
        return latest_run_dir()
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def manifest_path(run_dir: Path, dataset_date: str, limit: int) -> Path:
    expected = run_dir / f"{dataset_date}_files_{limit}.csv"
    if expected.exists():
        return expected
    matches = sorted(run_dir.glob(f"{dataset_date}_files_*.csv"))
    if matches:
        return matches[-1]
    return expected


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def run_download(
    *,
    dataset: str,
    episode_dir: Path,
    manifest: Path,
    download_log: Path,
    limit: int,
    env: dict[str, str],
) -> None:
    run_logged(
        [
            sys.executable,
            "scripts/download_episode_sample.py",
            "--dataset",
            dataset,
            "--limit",
            str(limit),
            "--output-dir",
            relative(episode_dir),
            "--manifest",
            relative(manifest),
            "--log",
            relative(download_log),
        ],
        download_log,
        env,
    )


def run_meta_analysis(*, episode_dir: Path, manifest: Path, run_dir: Path, analysis_log: Path, env: dict[str, str]) -> None:
    common = [
        "--input-dir",
        relative(episode_dir),
        "--manifest",
        relative(manifest),
    ]
    run_logged(
        [
            sys.executable,
            "scripts/rank_episode_deck_winrates.py",
            *common,
            "--out",
            relative(run_dir / "winrate_candidates.md"),
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
            relative(run_dir / "archetypes.md"),
        ],
        analysis_log,
        env,
    )


def run_candidate_decks(*, episode_dir: Path, manifest: Path, run_dir: Path, analysis_log: Path, env: dict[str, str]) -> None:
    run_logged(
        [
            sys.executable,
            "scripts/build_candidate_decks_from_episodes.py",
            "--input-dir",
            relative(episode_dir),
            "--manifest",
            relative(manifest),
            "--out-dir",
            relative(run_dir / "decks"),
        ],
        analysis_log,
        env,
    )


def _first_matching_lines(path: Path, prefixes: tuple[str, ...], limit: int) -> list[str]:
    if not path.exists():
        return []
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if any(stripped.startswith(prefix) for prefix in prefixes):
            lines.append(stripped)
        if len(lines) >= limit:
            break
    return lines


def _first_sections(path: Path, level: str, limit: int) -> list[str]:
    if not path.exists():
        return []
    sections = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(level + " ") and not stripped.startswith(level + "#"):
            sections.append(stripped.removeprefix(level + " "))
        if len(sections) >= limit:
            break
    return sections


def build_next_actions(run_dir: Path, dataset_date: str, limit: int) -> Path:
    winrate_path = run_dir / "winrate_candidates.md"
    archetypes_path = run_dir / "archetypes.md"
    decks_readme_path = run_dir / "decks" / "README.md"
    output = run_dir / "next_actions.md"

    archetypes = _first_sections(winrate_path, "###", 5)
    exact_decks = _first_sections(decks_readme_path, "##", 6)
    exact_decks = [name for name in exact_decks if name != "一覧"][:5]
    deck_files = _first_matching_lines(decks_readme_path, ("- `",), 5)
    representative_episodes = _first_matching_lines(winrate_path, ("  - Episode",), 5)
    common_cards = _first_matching_lines(archetypes_path, ("- ",), 12)

    lines = [
        "# 次に見ること",
        "",
        f"- 実行ディレクトリ: `{relative(run_dir)}`",
        f"- 対象データ: `{dataset_date}` / 最大 {limit} episode",
        "",
        "## 読む順番",
        "",
        "1. `winrate_candidates.md` で強そうなアーキタイプと相性候補を見る。",
        "2. `archetypes.md` で環境に多い主軸カードと構築傾向を見る。",
        "3. `decks/README.md` でCSV化された exact 60枚候補を見る。",
        "4. 気になる候補を `decks/` や `decks/candidates/` に採用し、自分たちのAgent評価へ回す。",
        "",
        "## 注意",
        "",
        "- 公開episodeの勝率は、デッキ性能と操作者/Agent性能が混ざっています。",
        "- Wilson下限や出現数は候補を絞るための目安で、最終判断は自分たちの評価で確認します。",
        "",
        "## 注目アーキタイプ",
        "",
    ]
    lines.extend([f"- {name}" for name in archetypes] or ["- `winrate_candidates.md` を生成すると表示されます。"])
    lines.extend(["", "## exact 60枚候補", ""])
    lines.extend(deck_files or [f"- `{relative(decks_readme_path)}` を生成すると表示されます。"])
    if exact_decks:
        lines.extend(["", "候補名:", ""])
        lines.extend([f"- {name}" for name in exact_decks])
    lines.extend(["", "## 主軸カードを見る場所", ""])
    lines.extend(common_cards[:8] or ["- `archetypes.md` を生成すると表示されます。"])
    lines.extend(["", "## 代表episode", ""])
    lines.extend(representative_episodes or ["- `winrate_candidates.md` を生成すると表示されます。"])
    lines.extend(
        [
            "",
            "## 次の作業候補",
            "",
            "- 候補デッキを手動GUIで数試合動かし、事故り方と強い動きをメモする。",
            "- 候補デッキに合わせて、優先して使うカード・攻撃・進化先をAgentに入れる。",
            "- 代表episodeをVisualizerで見て、真似したい判断と警戒したい相手の動きを抜き出す。",
            "- 内部評価では、勝率だけでなくデッキコンセプトが何ターン目に動くかも記録する。",
            "",
        ]
    )
    output.write_text("\n".join(lines), encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily Top Episodes の1000件抽出分析プロトコルを実行します。")
    parser.add_argument("--dataset-date", default="2026-06-30")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--dataset-prefix", default="kaggle/pokemon-tcg-ai-battle-episodes")
    parser.add_argument(
        "--stage",
        choices=["all", "download", "analyze", "build-decks", "next-actions"],
        default="all",
        help="Run only one stage. Use --run-dir latest for stages after download.",
    )
    parser.add_argument(
        "--run-dir",
        help="Run directory to use. Omit for a new run, or pass 'latest' for the newest run.",
    )
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    dataset = f"{args.dataset_prefix}-{args.dataset_date}"
    episode_dir = ROOT / "downloads" / "episodes" / args.dataset_date
    manifest = manifest_path(run_dir, args.dataset_date, args.limit)
    download_log = run_dir / "download.log"
    analysis_log = run_dir / "analysis.log"

    env = os.environ.copy()
    ensure_kaggle_env(env)

    print(f"Run directory: {run_dir}")
    print(f"Episode cache: {episode_dir}")
    print(f"Download log: {download_log}")
    print(f"Analysis log: {analysis_log}")

    if args.stage in ("all", "download"):
        run_download(
            dataset=dataset,
            episode_dir=episode_dir,
            manifest=manifest,
            download_log=download_log,
            limit=args.limit,
            env=env,
        )

    if args.stage in ("all", "analyze"):
        run_meta_analysis(
            episode_dir=episode_dir,
            manifest=manifest,
            run_dir=run_dir,
            analysis_log=analysis_log,
            env=env,
        )

    if args.stage in ("all", "build-decks"):
        run_candidate_decks(
            episode_dir=episode_dir,
            manifest=manifest,
            run_dir=run_dir,
            analysis_log=analysis_log,
            env=env,
        )

    if args.stage in ("all", "next-actions"):
        next_actions = build_next_actions(run_dir, args.dataset_date, args.limit)
        print(f"Next actions: {next_actions}")

    print("Done.")
    print(f"Open: {run_dir}")


if __name__ == "__main__":
    main()
