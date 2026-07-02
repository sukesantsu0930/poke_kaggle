import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from build_submission import build_submission


ROOT = Path(__file__).resolve().parents[1]
COMPETITION = "pokemon-tcg-ai-battle"
DEFAULT_AGENT = "agents/cubchoo_ogerpon_rb"
DEFAULT_DECK = "decks/candidates/2026-06-30_top5/winrate_1_cubchoo_ogerpon.csv"
DEFAULT_MESSAGE = "cubchoo_ogerpon_rb + winrate_1_cubchoo_ogerpon"


def safe_name(value: str) -> str:
    value = value.replace("\\", "/").rstrip("/")
    stem = Path(value).stem if Path(value).suffix else Path(value).name
    stem = re.sub(r"[^0-9A-Za-z_.-]+", "_", stem).strip("_")
    return stem or "submission"


def write_readme(out_dir: Path, zip_path: Path, agent: str, deck: str, message: str, command: list[str]):
    meta = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "competition": COMPETITION,
        "agent": agent,
        "deck": deck,
        "zip": str(zip_path.relative_to(ROOT)),
        "message": message,
        "submit_command": command,
    }
    (out_dir / "submission_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        f"# {datetime.now().strftime('%Y-%m-%d')} 提出メモ",
        "",
        "## Kaggle に提出するファイル",
        "",
        "```text",
        str(zip_path.relative_to(ROOT)),
        "```",
        "",
        "## Agent / Deck",
        "",
        f"- Agent: `{agent}`",
        f"- Deck: `{deck}`",
        "",
        "## Submit command",
        "",
        "```powershell",
        " ".join(f'"{item}"' if " " in item else item for item in command),
        "```",
        "",
        "このコンペでは `main.py`、`deck.csv`、`cg/` を含む zip を `-f` に指定します。",
    ]
    (out_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default=DEFAULT_AGENT)
    parser.add_argument("--deck", default=DEFAULT_DECK)
    parser.add_argument("--message", default=DEFAULT_MESSAGE)
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--submit", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    out_dir = ROOT / "submissions" / args.date
    agent_name = safe_name(args.agent)
    deck_name = safe_name(args.deck)
    zip_path = out_dir / f"{agent_name}__{deck_name}.zip"
    work_dir = ROOT / "build" / "submission_work"

    built = build_submission(
        ROOT / args.agent,
        ROOT / args.deck,
        zip_path,
        work_dir,
        extras=[],
    )

    command = [
        "kaggle",
        "competitions",
        "submit",
        "-c",
        COMPETITION,
        "-f",
        str(built),
        "-m",
        args.message,
    ]
    write_readme(out_dir, built, args.agent, args.deck, args.message, command)

    print(f"OK built={built}")
    print("submit_command=" + " ".join(f'"{item}"' if " " in item else item for item in command))

    if args.submit:
        result = subprocess.run(command, cwd=ROOT)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
