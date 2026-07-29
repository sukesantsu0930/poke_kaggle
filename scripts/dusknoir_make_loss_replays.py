"""現在のコードで負け試合のリプレイJSONを採り直す（2026-07-26）。

観戦→ドクトリン化のワークフローは「今のコードの負け方」を見ないと意味がないので、
ルールを1件入れるたびにこれで採り直す（ユーザー方針 2026-07-26）。

出力は research/dusknoir_replays/<prefix>N.json（既定 prefix は run/03_play の
バッチが既定値にしているファイル名に合わせてあるので、そのまま上書き更新される）。
併せて <prefix>N_agentlog.json に自分の行動系列も出す。

使い方（既定 = カースドボム版 v2 リストで対オーロンゲ）:
  uv run python scripts/dusknoir_make_loss_replays.py
  uv run python scripts/dusknoir_make_loss_replays.py --count 4 --opponent archaludon
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OPP_AGENT = {
    # 2026-07-27: winrate_2 は削除済みのため金圏正本に差し替え。marnie 側の観戦用に
    # 主要な苦手対面（chandelure / 同型 mainstream / crustle_wall / garchomp）を追加した
    "marnie": ("agents/marnie_munkidori_rb", "decks/fleet/marnie_gold_luca_0723.csv"),
    "marnie_main": ("agents/marnie_munkidori_rb", "decks/fleet/marnie_mainstream_0718.csv"),
    "alakazam": ("agents/alakazam_rb", "decks/fleet/alakazam_top_0710.csv"),
    "archaludon": ("agents/archaludon_rb", "decks/fleet/archaludon_cityleague.csv"),
    "froslass_starmie": ("agents/froslass_starmie_rb", "decks/fleet/froslass_starmie_taksai.csv"),
    "chandelure": ("agents/chandelure_rb", "decks/fleet/chandelure_top.csv"),
    "crustle_wall": ("agents/crustle_rb",
                     "decks/opponents/band_900_1100_0723/04_crustle_wall_138x.csv"),
    "garchomp": ("agents/cynthia_garchomp_rb", "decks/fleet/cynthia_garchomp_top.csv"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/dragapult_dusknoir_rb")
    ap.add_argument("--deck", default="decks/fleet/dragapult_dusknoir_v2.csv")
    ap.add_argument("--opponent", default="marnie", choices=sorted(OPP_AGENT))
    ap.add_argument("--count", type=int, default=4, help="保存する負け試合の本数")
    ap.add_argument("--max-tries", type=int, default=60)
    ap.add_argument("--prefix", default="v2_vs_grimmsnarl_loss")
    ap.add_argument("--outdir", default="research/dusknoir_replays")
    ap.add_argument("--wins", action="store_true", help="負けでなく勝ち試合を保存する")
    args = ap.parse_args()

    # main.py は import 時に環境変数を読むので、エージェントをロードする前に設定する
    # （自デッキ勘定 = R-18 のサイド落ち推定が対象デッキと一致していないと嘘になる）。
    # DUSK_DECK_CSV は dusknoir 専用フックなので対象機が dusknoir のときだけ設定する
    if "dusknoir" in args.agent:
        os.environ.setdefault("DUSK_DECK_CSV", args.deck)

    for p in ["scripts", "submission", "agents/_base"]:
        sys.path.insert(0, str(ROOT / p))
    from export_visualizer_json import load_agent, read_deck, run_game  # noqa: E402
    from ab_battle import reset_agent                                   # noqa: E402

    opp_dir, opp_deck_path = OPP_AGENT[args.opponent]
    a0 = load_agent(ROOT / args.agent, "replay_agent0")
    a1 = load_agent(ROOT / opp_dir, "replay_agent1")
    d0 = read_deck(ROOT / args.deck)
    d1 = read_deck(ROOT / opp_deck_path)

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    want = "勝ち" if args.wins else "負け"
    saved = tried = wins = 0
    while saved < args.count and tried < args.max_tries:
        tried += 1
        reset_agent(a0)
        reset_agent(a1)
        try:
            payload, meta, alog = run_game(a0, a1, list(d0), list(d1), 1000)
        except Exception as exc:                                   # noqa: BLE001
            print(f"  skip ({type(exc).__name__}: {exc})")
            continue
        won = meta["result"] == 0
        wins += 1 if won else 0
        if won != args.wins:
            continue
        saved += 1
        name = f"{args.prefix}{saved}"
        (outdir / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (outdir / f"{name}_agentlog.json").write_text(
            json.dumps(alog, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  保存 {name}.json  (steps={meta['steps']})")

    print(f"--- {tried}戦（{wins}勝{tried-wins}敗）から{want}試合 {saved}件を "
          f"{args.outdir} に保存 ---")
    if saved < args.count:
        print(f"  ※ {args.max_tries}戦で {args.count} 件に届きませんでした")


if __name__ == "__main__":
    main()
