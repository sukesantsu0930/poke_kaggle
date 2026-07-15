"""agents/_base/opp_decks.py を生成する — 探索の決定化で使う相手デッキリスト表。

field CSV（research/meta/*_field.csv）の archetype → deck CSV 対応から、
アーキタイプ別の60枚リストを埋め込んだ Python ファイルを生成する。
メタが動いて field CSV を更新したら再生成して sync_base を回す。

使い方:
  uv run python scripts/build_opp_decks.py [--field research/meta/2026-07-14_field.csv]
"""
import argparse
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HEADER = '''"""相手デッキリスト表（自動生成 — 直接編集禁止）。

生成: scripts/build_opp_decks.py --field {field}
用途: turn_search.py の決定化（R-20 のアーキタイプ判定 → 相手の非公開ゾーンの中身を予測）。
DEFAULT はシェア最大アーキタイプのリスト（判定不能時のフォールバック）。
"""

'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--field", default="research/meta/2026-07-14_field.csv")
    args = parser.parse_args()

    rows = list(csv.DictReader(open(ROOT / args.field, encoding="utf-8")))
    decks = {}
    best = (None, -1.0)
    for r in rows:
        name = r["archetype"].strip()
        deck_path = ROOT / r["deck"].strip()
        ids = [int(l.strip()) for l in deck_path.read_text().splitlines() if l.strip()][:60]
        if len(ids) != 60:
            print(f"SKIP {name}: {len(ids)} cards")
            continue
        decks[name] = ids
        if float(r["share"]) > best[1]:
            best = (name, float(r["share"]))

    out = ROOT / "agents" / "_base" / "opp_decks.py"
    with open(out, "w", encoding="utf-8") as f:
        f.write(HEADER.format(field=args.field))
        f.write("OPP_DECKS = {\n")
        for name, ids in sorted(decks.items()):
            f.write(f"    {name!r}: {ids},\n")
        f.write("}\n\n")
        f.write(f"DEFAULT_ARCHETYPE = {best[0]!r}\n")
    print(f"wrote {out} ({len(decks)} archetypes, default={best[0]})")


if __name__ == "__main__":
    main()
