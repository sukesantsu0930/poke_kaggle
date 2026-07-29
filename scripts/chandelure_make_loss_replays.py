"""chandelure の負け試合リプレイJSONを採り直す（2026-07-27）。

観戦→ドクトリン化のワークフローは「今のコードの負け方」を見ないと意味がないので、
ルールを1件入れるたびにこれで採り直す（ユーザー方針 2026-07-26）。
`scripts/dusknoir_make_loss_replays.py` の chandelure 版。

dusknoir 版との違い:
- `--agent` に **提出zipを展開したdir** を渡せる（版どうしの負け方を直接比べるため。
  展開dirは policy_base.py 等を同梱しているので ab_battle.load_agent がそのまま隔離ロードする）
- 相手プールを 900-1100 帯フィールド（= 全対面が専用エージェント操縦）に合わせた。
  **generic 操縦は相手を過小評価する（EXP-056: 壁デッキで −57pt）ため、観戦相手は必ず専用機**
- `--summary` で勝敗と敗因（自山切れ / プライズ負け）の内訳だけを集計できる

出力は research/chandelure_replays/<prefix>N.json と <prefix>N_agentlog.json。

使い方:
  uv run python scripts/chandelure_make_loss_replays.py --opponent crustle_wall
  uv run python scripts/chandelure_make_loss_replays.py --agent <v7展開dir> --opponent crustle_wall
  uv run python scripts/chandelure_make_loss_replays.py --opponent crustle_wall --summary 200
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 相手プール = research/meta/2026-07-23_field_900_1100.csv（実シェア帯・全て専用エージェント）
OPP_AGENT = {
    "alakazam": ("agents/alakazam_rb",
                 "decks/opponents/band_900_1100_0723/01_alakazam_296x.csv"),
    "marnie_luca": ("agents/marnie_munkidori_rb",
                    "decks/opponents/band_900_1100_0723/02_marnie_206x.csv"),
    "marnie_main": ("agents/marnie_munkidori_rb",
                    "decks/opponents/band_900_1100_0723/03_marnie_174x.csv"),
    "crustle_wall": ("agents/crustle_rb",
                     "decks/opponents/band_900_1100_0723/04_crustle_wall_138x.csv"),
    "rocket": ("agents/rocket_rb",
               "decks/opponents/band_900_1100_0723/05_rocket_110x.csv"),
    "froslass_starmie": ("agents/froslass_starmie_rb",
                         "decks/fleet/froslass_starmie_taksai.csv"),
}


def _order(a0, a1, d0, d1, seat):
    """seat=0 なら自分が battle_start の第1引数側（先手側）、1 なら第2引数側（後手側）。"""
    if seat == 0:
        return a0, a1, list(d0), list(d1)
    return a1, a0, list(d1), list(d0)


def _count(v):
    return len(v) if isinstance(v, list) else v


def classify_loss(payload, seat=0):
    """負けの型を分ける。自山切れ（=LO自滅）か、プライズ取り切られか。

    payload は observation dict の **リスト**（visualize_data の出力）。最終要素の
    `current.players` は **絶対インデックス**なので players[seat] が自分。
    `prize` は残りサイドのリストなので長さを取る。シャンデラはミルデッキなので
    「相手を削り切る前に自分が先に山切れ」が直せる自滅型（EXP-055 の系統）。
    """
    try:
        if not isinstance(payload, list) or not payload:
            return "unknown", {}
        cur = payload[-1].get("current") or {}
        players = cur.get("players") or []
        if len(players) < 2:
            return "unknown", {}
        me, opp = players[seat], players[1 - seat]
        detail = {"my_deck": me.get("deckCount"), "opp_deck": opp.get("deckCount"),
                  "my_prize": _count(me.get("prize")),
                  "opp_prize": _count(opp.get("prize")),
                  "turn": cur.get("turn")}
        if me.get("deckCount") == 0:
            return "self_deckout", detail
        if detail["opp_prize"] == 0:
            return "prize_loss", detail
        return "other", detail
    except Exception:                                              # noqa: BLE001
        return "unknown", {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/chandelure_rb",
                    help="対象エージェントdir（提出zipの展開dirも可）")
    ap.add_argument("--deck", default="decks/fleet/chandelure_top.csv")
    ap.add_argument("--opponent", default="crustle_wall", choices=sorted(OPP_AGENT))
    ap.add_argument("--count", type=int, default=4, help="保存する負け試合の本数")
    ap.add_argument("--max-tries", type=int, default=60)
    ap.add_argument("--prefix", help="既定は <opponent>_loss")
    ap.add_argument("--outdir", default="research/chandelure_replays")
    ap.add_argument("--wins", action="store_true", help="負けでなく勝ち試合を保存する")
    ap.add_argument("--summary", type=int, default=0,
                    help="N戦回して勝敗と敗因の内訳だけ出す（リプレイは保存しない）")
    ap.add_argument("--seat", type=int, default=0, choices=(0, 1),
                    help="自分の席。0=先手側（battle_start の第1引数）/ 1=後手側。"
                         "gauntlet は席を入れ替えて測るが本ハーネスは片側固定なので、"
                         "席差が大きい対面（marnie は先手 59.5%% / 席入替 55.4%%）では"
                         "**負けが偏っている後手側も必ず採ること**")
    args = ap.parse_args()

    prefix = args.prefix or f"{args.opponent}_loss"

    for p in ["scripts", "submission", "agents/_base"]:
        sys.path.insert(0, str(ROOT / p))
    from export_visualizer_json import load_agent, read_deck, run_game  # noqa: E402
    from ab_battle import reset_agent                                   # noqa: E402

    opp_dir, opp_deck_path = OPP_AGENT[args.opponent]
    a0 = load_agent(ROOT / args.agent, "replay_agent0")
    a1 = load_agent(ROOT / opp_dir, "replay_agent1")
    d0 = read_deck(ROOT / args.deck)
    d1 = read_deck(ROOT / opp_deck_path)

    if args.summary:
        kinds = {}
        wins = 0
        for i in range(args.summary):
            reset_agent(a0)
            reset_agent(a1)
            try:
                payload, meta, _ = run_game(*_order(a0, a1, d0, d1, args.seat), 1000)
            except Exception as exc:                               # noqa: BLE001
                print(f"  skip ({type(exc).__name__}: {exc})")
                continue
            if meta["result"] == args.seat:
                wins += 1
                continue
            kind, _detail = classify_loss(payload, args.seat)
            kinds[kind] = kinds.get(kind, 0) + 1
        n = args.summary
        seat_label = "先手側" if args.seat == 0 else "後手側"
        print(f"--- {args.agent} vs {args.opponent}（{seat_label}）: "
              f"{n}戦 {wins}勝{n-wins}敗 ({wins/n:.1%}) ---")
        for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
            print(f"  {k:>14}: {v:>4} ({v/max(1, n-wins):.0%} of losses)")
        return

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    want = "勝ち" if args.wins else "負け"
    saved = tried = wins = 0
    while saved < args.count and tried < args.max_tries:
        tried += 1
        reset_agent(a0)
        reset_agent(a1)
        try:
            payload, meta, alog = run_game(*_order(a0, a1, d0, d1, args.seat), 1000)
        except Exception as exc:                                   # noqa: BLE001
            print(f"  skip ({type(exc).__name__}: {exc})")
            continue
        won = meta["result"] == args.seat
        wins += 1 if won else 0
        if won != args.wins:
            continue
        saved += 1
        name = f"{prefix}{saved}"
        (outdir / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        (outdir / f"{name}_agentlog.json").write_text(
            json.dumps(alog, ensure_ascii=False, indent=1), encoding="utf-8")
        kind, detail = classify_loss(payload, args.seat)
        print(f"  保存 {name}.json  (steps={meta['steps']}, {kind} {detail})")

    print(f"--- {tried}戦（{wins}勝{tried-wins}敗）から{want}試合 {saved}件を "
          f"{args.outdir} に保存 ---")
    if saved < args.count:
        print(f"  ※ {args.max_tries}戦で {args.count} 件に届きませんでした")


if __name__ == "__main__":
    main()
