"""共有基盤ファイルの同期 — agents/_base/ の正本を各エージェントdirへコピーする。

対象: main.py に `from policy_base import` を含む agents/*/ （自動発見・登録不要）
使い方:
  uv run python scripts\\sync_base.py            # 同期（コピー）
  uv run python scripts\\sync_base.py --check    # SHA-256 照合のみ（不一致で exit 1）
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "agents" / "_base"
BASE_FILES = ["policy_base.py", "meta_tables.py",
              "turn_search.py", "value_model.py", "opp_decks.py", "generic_policy.py",
              "policy_net.py"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_targets() -> list[Path]:
    targets = []
    for main_py in sorted((ROOT / "agents").glob("*/main.py")):
        if main_py.parent.name == "_base":
            continue
        try:
            text = main_py.read_text(encoding="utf-8")
        except Exception:
            continue
        if "from policy_base import" in text or "import policy_base" in text:
            targets.append(main_py.parent)
    return targets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="照合のみ（コピーしない）")
    args = parser.parse_args()

    for name in BASE_FILES:
        if not (BASE_DIR / name).exists():
            print(f"NG missing canonical file: {BASE_DIR / name}")
            raise SystemExit(1)

    targets = discover_targets()
    if not targets:
        print("no BasePolicy agents found (agents/*/main.py with 'from policy_base import')")
        return

    bad = 0
    for target in targets:
        for name in BASE_FILES:
            src = BASE_DIR / name
            dst = target / name
            same = dst.exists() and sha256(dst) == sha256(src)
            if args.check:
                status = "OK" if same else "STALE"
                if not same:
                    bad += 1
                print(f"{status} {dst.relative_to(ROOT)}")
            else:
                if same:
                    print(f"unchanged {dst.relative_to(ROOT)}")
                else:
                    shutil.copy2(src, dst)
                    print(f"synced    {dst.relative_to(ROOT)}")

    if args.check and bad:
        print(f"NG {bad} stale file(s). Run: uv run python scripts\\sync_base.py")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
