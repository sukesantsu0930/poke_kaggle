"""2つのエージェント版の「決定そのもの」を突き合わせる（2026-07-27・EXP-057）。

動機: リーダーボードで rules7 > rules9（5観測すべてで同じ向き・差 27〜65点）なのに、
ローカル 640戦/枠 × 6対面（n=3,840/版）では集計差 0.0pt で検出できない。
勝率で見えないなら **そのルールが何回・どの局面で決定を変えているのか** を数える。
発火が極小なら、コード差でスコア差を説明できない（＝別要因を疑うべき）と言い切れる。

方式は `scripts/dusknoir_gate_invariance.py` の影走行と同じ:
  A が実際に対局を進め、A の全決定点で **同じ obs を B にも渡して行動を比較**する。
  A/B は別 dir でよいので、提出zipを展開した版どうしを直接比べられる。

使い方:
  python scripts/chandelure_version_divergence.py --a <v7dir> --b <v9dir> --games 40
  python scripts/chandelure_version_divergence.py --a <v7dir> --b <v8dir> --games 40 \
      --field research/meta/2026-07-23_field_900_1100.csv
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import load_agent, read_deck, reset_agent      # noqa: E402
from gauntlet import read_field, build_opponent               # noqa: E402
from cg import api, game as cg_game                           # noqa: E402

DECK = ROOT / "decks/fleet/chandelure_top.csv"
FIELD = ROOT / "research/meta/2026-07-23_field_900_1100.csv"


def run_matchup(a_mod, b_mod, our_deck, opp_mod, opp_deck, games, max_steps, seat):
    """seat=0 なら自軍が battle_start の第1引数側。B は影として全決定で問い合わせる。"""
    stat = Counter()
    diffs = []
    for _g in range(games):
        reset_agent(a_mod)
        reset_agent(b_mod)
        reset_agent(opp_mod)
        decks = (our_deck, opp_deck) if seat == 0 else (opp_deck, our_deck)
        obs, _ = cg_game.battle_start(list(decks[0]), list(decks[1]))
        if obs is None:
            stat["start_failed"] += 1
            continue
        diverged_here = False
        try:
            for _ in range(max_steps):
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is not None and cur.result != -1:
                    break
                yi = cur.yourIndex if cur is not None else 0
                if yi != seat:
                    obs = cg_game.battle_select(opp_mod.agent(obs))
                    continue
                action = a_mod.agent(obs)
                b_action = b_mod.agent(obs)
                stat["decisions"] += 1
                if list(action) == list(b_action):
                    stat["agree"] += 1
                else:
                    stat["diff"] += 1
                    diverged_here = True
                    if len(diffs) < 8:
                        ctx = typed.select.context if typed.select is not None else None
                        diffs.append((getattr(cur, "turn", -1),
                                      getattr(ctx, "name", str(ctx)),
                                      list(action), list(b_action)))
                obs = cg_game.battle_select(action)
        finally:
            try:
                cg_game.battle_finish()
            except Exception:                                      # noqa: BLE001
                pass
        stat["games"] += 1
        if diverged_here:
            stat["games_diverged"] += 1
    return stat, diffs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="基準版のエージェントdir（実際に対局を進める側）")
    ap.add_argument("--b", required=True, help="比較版のエージェントdir（影）")
    ap.add_argument("--deck", default=str(DECK))
    ap.add_argument("--field", default=str(FIELD))
    ap.add_argument("--games", type=int, default=40, help="1対面・1席あたりの試合数")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--only", help="アーキタイプ名のカンマ区切り")
    args = ap.parse_args()

    a_mod = load_agent(Path(args.a))
    b_mod = load_agent(Path(args.b))
    our_deck = read_deck(Path(args.deck))
    field = read_field(Path(args.field))
    if args.only:
        names = {n.strip() for n in args.only.split(",")}
        field = [r for r in field if r["archetype"] in names]

    print(f"=== 決定不一致率  A={Path(args.a).name}  B={Path(args.b).name} "
          f"（{args.games}戦×2席/対面）===")
    header = f"{'対面':<18}{'決定数':>9}{'不一致':>8}{'不一致率':>10}{'割れた試合':>11}"
    print(header)
    print("-" * 62)

    grand = Counter()
    all_diffs = {}
    for row in field:
        arch = row["archetype"]
        opp_mod, opp_deck = build_opponent(row)
        total, diffs = Counter(), []
        for seat in (0, 1):
            s, d = run_matchup(a_mod, b_mod, our_deck, opp_mod, opp_deck,
                               args.games, args.max_steps, seat)
            total.update(s)
            diffs.extend(d)
        grand.update(total)
        all_diffs[arch] = diffs
        dec = total["decisions"] or 1
        gms = total["games"] or 1
        print(f"{arch:<18}{total['decisions']:>9}{total['diff']:>8}"
              f"{total['diff']/dec:>9.3%}{total['games_diverged']:>7}/{gms:<4}")

    dec = grand["decisions"] or 1
    gms = grand["games"] or 1
    print("-" * 62)
    print(f"{'合計':<18}{grand['decisions']:>9}{grand['diff']:>8}"
          f"{grand['diff']/dec:>9.3%}{grand['games_diverged']:>7}/{gms:<4}")
    print(f"\n割れた試合の割合: {grand['games_diverged']/gms:.1%} "
          f"（この割合を超えて勝率が動くことは機構上ありえない）")

    for arch, diffs in all_diffs.items():
        if not diffs:
            continue
        print(f"\n--- {arch}: 不一致サンプル（最大8件） ---")
        for turn, ctx, a_act, b_act in diffs:
            print(f"  T{turn:<3} {ctx:<14} A={a_act}  B={b_act}")


if __name__ == "__main__":
    main()
