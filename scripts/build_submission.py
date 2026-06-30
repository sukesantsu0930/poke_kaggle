import argparse
import shutil
import zipfile
from pathlib import Path

from deck_validation import validate_deck_file


ROOT = Path(__file__).resolve().parents[1]


def _validate_deck(deck_path: Path) -> list[str]:
    lines = [line.strip() for line in deck_path.read_text().splitlines() if line.strip()]
    validation = validate_deck_file(deck_path)
    if not validation.ok:
        detail = "\n".join(f"- {error}" for error in validation.errors)
        raise ValueError(f"{deck_path} is not a valid deck:\n{detail}")
    return lines


def _validate_agent(agent_path: Path) -> str:
    text = agent_path.read_text()
    missing = []
    if "def agent(" not in text:
        missing.append("def agent(...)")
    if "def read_deck_csv(" not in text:
        missing.append("def read_deck_csv(...)")
    if missing:
        raise ValueError(f"{agent_path} is missing: {', '.join(missing)}")
    return text


def _parse_extra(extra: str) -> tuple[Path, Path | None]:
    if "=" not in extra:
        return Path(extra), None
    src, dest = extra.split("=", 1)
    if not src or not dest:
        raise ValueError(f"Invalid --extra value: {extra!r}. Use SRC or SRC=DEST.")
    return Path(src), Path(dest)


def _copy_extra(src: Path, dest: Path):
    if not src.exists():
        raise FileNotFoundError(src)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def build_submission(
    agent_path: Path,
    deck_path: Path,
    output_path: Path,
    work_dir: Path,
    extras: list[str] | None = None,
):
    agent_path = agent_path.resolve()
    deck_path = deck_path.resolve()
    output_path = output_path.resolve()
    work_dir = work_dir.resolve()

    _validate_agent(agent_path)
    deck_lines = _validate_deck(deck_path)

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    shutil.copytree(
        ROOT / "submission" / "cg",
        work_dir / "cg",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copy2(agent_path, work_dir / "main.py")
    (work_dir / "deck.csv").write_text("\n".join(deck_lines) + "\n")

    for extra in extras or []:
        src, dest = _parse_extra(extra)
        src = src.resolve()
        if dest is None:
            dest = Path(src.name)
        if dest.is_absolute() or ".." in dest.parts:
            raise ValueError(f"Unsafe --extra destination: {dest}")
        _copy_extra(src, work_dir / dest)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(work_dir.rglob("*")):
            if path.is_file():
                if "__pycache__" in path.parts or path.suffix == ".pyc":
                    continue
                zf.write(path, path.relative_to(work_dir))
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="submission/main.py")
    parser.add_argument("--deck", default="submission/deck.csv")
    parser.add_argument(
        "--extra",
        action="append",
        default=[],
        help="Additional file/dir to include. Use SRC or SRC=DEST. Can be repeated.",
    )
    parser.add_argument("--output")
    parser.add_argument("--work-dir", default="build/submission_work")
    args = parser.parse_args()

    agent_path = Path(args.agent)
    deck_path = Path(args.deck)
    if args.output:
        output_path = Path(args.output)
    else:
        output_name = f"{agent_path.stem}__{deck_path.stem}.zip"
        output_path = ROOT / "submissions" / output_name

    built = build_submission(agent_path, deck_path, output_path, ROOT / args.work_dir, args.extra)
    print(built)


if __name__ == "__main__":
    main()
