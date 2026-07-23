"""レート帯 × アーキタイプのラダーセンサス。

07-20 の使い捨て census.py（記録の正本: research/meta/ladder_band_census_0720.md）を
恒久スクリプト化したもの。エピソード JSON（visualize.action の 60 枚リスト）と
LB スナップショットから、レート帯ごとのサブタイプ構成・勝率・上位 exact リストを実測し、
フィールド csv（scripts/gauntlet.py read_field 互換）の材料を出力する。

方法論は 0720 と同一:
- デッキ抽出: visualize.action（analyze_episode_decks.extract_decks）
- アーキ判定: meta_tables.ARCHETYPES との一致 ID 種数最大
  - chandelure ガード: {97, 98, 494}（ヒトモシ系統）が無ければ不成立
  - crustle 亜種: 756 有→crustle_wall / 無→crustle_prism
  - starmie 亜種: {860, 861} 有→froslass_starmie / 無→megastarmie
- 帯割当は LB スナップショット時点のスコア（試合時点のレートではない）

使用例:
  uv run python scripts/ladder_band_census.py \
    --days 2026-07-19 2026-07-20 2026-07-21 \
    --lb-csv downloads/leaderboard/pokemon-tcg-ai-battle-publicleaderboard-2026-07-23T01_29_15.csv \
    --out research/meta/2026-07-23_band_census.md \
    --dump-band 1100+ --dump-dir decks/opponents/band_1100_0723 --dump-top 8
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

import analyze_episode_decks as aed  # noqa: E402
import meta_tables  # noqa: E402

CHANDELURE_LINE = {97, 98, 494}
CRUSTLE_WALL_ID = 756
FROSLASS_IDS = {860, 861}


def subtype_of(ids: set[int]) -> str:
    ranked = sorted(
        ((len(ids & key_ids), name) for name, key_ids in meta_tables.ARCHETYPES.items()),
        key=lambda t: -t[0],
    )
    for n, name in ranked:
        if n == 0:
            break
        if name == "chandelure" and not (ids & CHANDELURE_LINE):
            continue
        if name == "crustle":
            return "crustle_wall" if CRUSTLE_WALL_ID in ids else "crustle_prism"
        if name == "starmie":
            return "froslass_starmie" if ids & FROSLASS_IDS else "megastarmie"
        return name
    return "other"


def load_lb(lb_csv: Path) -> dict[str, float]:
    with lb_csv.open(encoding="utf-8-sig", newline="") as f:
        return {r["TeamName"]: float(r["Score"]) for r in csv.DictReader(f) if r.get("Score")}


def band_of(score: float | None, edges: list[float]) -> str:
    if score is None:
        return "unknown"
    labels = band_labels(edges)
    for edge, label in zip(edges, labels):
        if score < edge:
            return label
    return labels[-1]


def band_labels(edges: list[float]) -> list[str]:
    labels = [f"<{edges[0]:g}"]
    labels += [f"{a:g}-{b:g}" for a, b in zip(edges, edges[1:])]
    labels.append(f"{edges[-1]:g}+")
    return labels


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", nargs="+", required=True)
    ap.add_argument("--episodes-root", default="downloads/episodes")
    ap.add_argument("--lb-csv", required=True)
    ap.add_argument("--card-csv", default="JP_Card_Data.csv")
    ap.add_argument("--band-edges", default="900,1100")
    ap.add_argument("--out", required=True)
    ap.add_argument("--top-sigs", type=int, default=3, help="帯×サブタイプ毎に載せる exact リスト数")
    ap.add_argument("--dump-band", default=None, help="この帯の上位 exact リストを csv 化する")
    ap.add_argument("--dump-dir", default=None)
    ap.add_argument("--dump-top", type=int, default=8)
    args = ap.parse_args()

    edges = [float(x) for x in args.band_edges.split(",")]
    lb = load_lb(Path(args.lb_csv))
    card_rows = aed.load_card_rows(Path(args.card_csv))

    # (band, subtype) -> 集計。sig ごとに (count, 代表情報) も保持
    cells: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"sides": 0, "wins": 0, "losses": 0, "draws": 0,
                 "teams": Counter(), "sigs": Counter(), "sig_meta": {}}
    )
    n_episodes = 0
    n_failed = 0

    for day in args.days:
        day_dir = Path(args.episodes_root) / day
        for path in sorted(day_dir.glob("*.json")):
            try:
                ep = json.loads(path.read_text(encoding="utf-8"))
                decks = aed.extract_decks(ep)
            except Exception:
                n_failed += 1
                continue
            n_episodes += 1
            info = ep.get("info", {})
            teams = info.get("TeamNames") or [
                a.get("Name", f"player{i}") for i, a in enumerate(info.get("Agents", [{}, {}]))
            ]
            rewards = ep.get("rewards", [None, None])
            for pi, deck_ids in enumerate(decks):
                ids = set(deck_ids)
                sub = subtype_of(ids)
                team = teams[pi] if pi < len(teams) else f"player{pi}"
                band = band_of(lb.get(team), edges)
                cell = cells[(band, sub)]
                cell["sides"] += 1
                reward = rewards[pi] if pi < len(rewards) else None
                key = "wins" if (reward or 0) > 0 else ("losses" if (reward or 0) < 0 else "draws")
                cell[key] += 1
                cell["teams"][team] += 1
                sig = aed.signature(deck_ids)
                cell["sigs"][sig] += 1
                cell["sig_meta"].setdefault(sig, {"deck": list(deck_ids), "teams": Counter()})
                cell["sig_meta"][sig]["teams"][team] += 1

    labels = band_labels(edges) + ["unknown"]
    subtypes = sorted({sub for (_, sub) in cells}, key=lambda s: -sum(
        cells[(b, s)]["sides"] for b in labels if (b, s) in cells))

    def main_pokemon(deck: list[int], k: int = 4) -> str:
        cnt = Counter(deck)
        pokes = [(aed.card_name(card_rows, cid), n) for cid, n in cnt.most_common()
                 if aed.card_kind(card_rows, cid) == "ポケモン"]
        return " / ".join(f"{name}{n}" for name, n in pokes[:k]) or "(ポケモンなし)"

    lines = [
        f"# レート帯センサス — days: {', '.join(args.days)}",
        "",
        f"- LB スナップショット: `{args.lb_csv}`（帯割当は現在スコアであり試合時点のレートではない）",
        f"- エピソード: {n_episodes} 試合（読込失敗 {n_failed}）= {n_episodes * 2} プレイヤー側",
        f"- 生成: `scripts/ladder_band_census.py`",
        "",
        "## 帯 × サブタイプ（プレイヤー側の延べ数）",
        "",
        "| subtype | " + " | ".join(labels) + " | total |",
        "|---" * (len(labels) + 2) + "|",
    ]
    for sub in subtypes:
        row = [str(cells[(b, sub)]["sides"]) if (b, sub) in cells else "0" for b in labels]
        total = sum(int(x) for x in row)
        lines.append(f"| {sub} | " + " | ".join(row) + f" | {total} |")
    totals = [str(sum(cells[(b, s)]["sides"] for s in subtypes if (b, s) in cells)) for b in labels]
    lines.append("| **TOTAL** | " + " | ".join(f"**{t}**" for t in totals)
                 + f" | **{n_episodes * 2}** |")

    for band in labels:
        band_cells = {s: cells[(band, s)] for s in subtypes if (band, s) in cells}
        band_total = sum(c["sides"] for c in band_cells.values())
        if not band_total:
            continue
        lines += ["", f"## {band} 帯の構成（N={band_total} 側）", "",
                  "| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |",
                  "|---|---|---|---|---|"]
        for sub, c in sorted(band_cells.items(), key=lambda kv: -kv[1]["sides"]):
            decided = c["wins"] + c["losses"]
            win = f"{c['wins'] / decided:.1%}" if decided else "-"
            team_bits = " / ".join(
                f"{t} ({lb[t]:.0f}): {n}" if t in lb else f"{t} (?): {n}"
                for t, n in c["teams"].most_common(4))
            lines.append(
                f"| {sub} | {c['sides']} | {c['sides'] / band_total * 100:.1f} | {win} | {team_bits} |")

        lines += ["", f"### {band} 帯の exact リスト上位（サブタイプ毎 top{args.top_sigs}）", ""]
        for sub, c in sorted(band_cells.items(), key=lambda kv: -kv[1]["sides"]):
            for i, (sig, n) in enumerate(c["sigs"].most_common(args.top_sigs), 1):
                meta = c["sig_meta"][sig]
                pilots = " / ".join(f"{t}:{k}" for t, k in meta["teams"].most_common(3))
                lines.append(f"- **{sub} #{i}** ×{n} — {main_pokemon(meta['deck'])} — pilots: {pilots}")

    if args.dump_band and args.dump_dir:
        dump_dir = Path(args.dump_dir)
        dump_dir.mkdir(parents=True, exist_ok=True)
        pool = [
            (n, sub, sig, cells[(args.dump_band, sub)]["sig_meta"][sig])
            for sub in subtypes if (args.dump_band, sub) in cells
            for sig, n in cells[(args.dump_band, sub)]["sigs"].items()
        ]
        pool.sort(key=lambda t: -t[0])
        lines += ["", f"## dump: {args.dump_band} 帯 exact リスト上位 {args.dump_top} 件 → `{dump_dir}`", ""]
        for rank, (n, sub, sig, meta) in enumerate(pool[: args.dump_top], 1):
            out_csv = dump_dir / f"{rank:02d}_{sub}_{n}x.csv"
            out_csv.write_text("\n".join(str(c) for c in meta["deck"]) + "\n", encoding="utf-8")
            lines.append(f"- `{out_csv.name}` ×{n} — {main_pokemon(meta['deck'])}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
