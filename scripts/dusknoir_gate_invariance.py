"""対オーロンゲ特殊化の「ゲート不変条件」検証器（2026-07-26 ユーザー指示）。

要求（ユーザー 2026-07-26）:
  オーロンゲデッキ相手にオーロンゲと気づかずに指すのがおかしいのと同じく、
  **オーロンゲでない相手にオーロンゲ用の手を打つのもおかしい**。したがって対オーロンゲ
  パッケージの A/B で他対面の戦績が動いたら、それは勝ち負け以前に実装のバグである。

そこで戦績ではなく「決定そのもの」を突き合わせる:
  A = パッケージ OFF、B = パッケージ ON の2インスタンスを同時に走らせ、A が実際に対局を
  進めながら、**A の全決定点で B にも同じ obs を渡して行動を比較**する（ab_battle の
  shadow と同じ原理。ただし相手をフィールド全対面に広げ、席も入れ替える）。

  合格条件:
    ① 非オーロンゲ対面: 一致率 **100%**（1手でも割れたらゲート漏れ = バグ）
    ② オーロンゲ対面  : 一致率 < 100%（割れないなら検証器に検出力が無い＝テストが無意味）
    ③ 誤検出         : 非オーロンゲ対面で _grim_seen が立った試合 = 0

  ② を保証するため、実ルールがまだ無い段階では DUSK_GRIM_CANARY=1（対オーロンゲでのみ
  ダイブ閾値をパッシブに倒す既定OFFのカナリア）を B に与えて検出力を先に示す。
  実ルール実装後は --canary 0 で「実ルールによる差分」をそのまま計測できる。

使い方:
  python scripts/dusknoir_gate_invariance.py --games 20           # カナリアで検出力込み検証
  python scripts/dusknoir_gate_invariance.py --games 20 --canary 0  # 実ルールのゲート検証
"""
import argparse
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import load_agent, read_deck, reset_agent, get_policy  # noqa: E402
from gauntlet import read_field, build_opponent                      # noqa: E402
from cg import api, game as cg_game                                  # noqa: E402

AGENT_DIR = ROOT / "agents/dragapult_dusknoir_rb"
DECK = ROOT / "decks/fleet/dragapult_dusknoir_paper.csv"
FIELD = ROOT / "research/meta/2026-07-20_uniform_field.csv"
GRIM_ARCHETYPE = "marnie"          # オーロンゲ線 {646,647,648} を積むアーキタイプ名


def load_pair(canary: bool):
    """A=パッケージOFF / B=パッケージON を、環境変数を切り替えつつ別モジュールとしてロード。

    DUSK_* は main.py のモジュール定数（import 時に確定）なので、load_agent が毎回
    一意なモジュール名で再 exec することを利用して2世界を作る。"""
    os.environ["DUSK_GRIM"] = "0"
    os.environ["DUSK_GRIM_CANARY"] = "0"
    a = load_agent(AGENT_DIR)
    os.environ["DUSK_GRIM"] = "1"
    os.environ["DUSK_GRIM_CANARY"] = "1" if canary else "0"
    b = load_agent(AGENT_DIR)
    os.environ.pop("DUSK_GRIM", None)
    os.environ.pop("DUSK_GRIM_CANARY", None)
    return a, b


def run_matchup(a_mod, b_mod, our_deck, opp_mod, opp_deck, games, max_steps, seat):
    """seat=0 なら自軍が先手番側（battle_start の第1引数）。B は影として全決定で問い合わせる。"""
    stat = Counter()
    diffs = []
    grim_turns = []
    for g in range(games):
        reset_agent(a_mod)
        reset_agent(b_mod)
        reset_agent(opp_mod)
        decks = (our_deck, opp_deck) if seat == 0 else (opp_deck, our_deck)
        obs, _ = cg_game.battle_start(list(decks[0]), list(decks[1]))
        if obs is None:
            stat["start_failed"] += 1
            continue
        grim_turn = None
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
                    if len(diffs) < 5:
                        ctx = typed.select.context if typed.select is not None else None
                        diffs.append((g, getattr(ctx, "name", str(ctx)),
                                      list(action), list(b_action)))
                pol = get_policy(b_mod)
                if grim_turn is None and pol is not None and getattr(pol, "_grim_seen", False):
                    grim_turn = getattr(cur, "turn", -1)
                obs = cg_game.battle_select(action)
        finally:
            try:
                cg_game.battle_finish()
            except Exception:
                pass
        stat["games"] += 1
        if grim_turn is not None:
            stat["detected"] += 1
            grim_turns.append(grim_turn)
    return stat, diffs, grim_turns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=20, help="1対面・1席あたりの試合数")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--canary", type=int, default=1, help="1=カナリアで検出力込み検証")
    ap.add_argument("--field", default=str(FIELD))
    args = ap.parse_args()

    a_mod, b_mod = load_pair(bool(args.canary))
    our_deck = read_deck(DECK)
    field = read_field(Path(args.field))

    print(f"=== ゲート不変条件テスト（canary={args.canary}, {args.games}戦×2席/対面）===")
    header = f"{'対面':<18}{'決定数':>8}{'一致率':>9}{'不一致':>7}{'検出試合':>9}{'初検出T':>9}"
    print(header)
    print("-" * len(header.encode("utf-8")) // 2 * "-" if False else "-" * 62)

    failures = []
    grim_diff_seen = False
    for row in field:
        arch = row["archetype"]
        opp_mod, opp_deck = build_opponent(row)
        total, diffs, turns = Counter(), [], []
        for seat in (0, 1):
            s, d, t = run_matchup(a_mod, b_mod, our_deck, opp_mod, opp_deck,
                                  args.games, args.max_steps, seat)
            total.update(s)
            diffs.extend(d)
            turns.extend(t)
        n = total["decisions"] or 1
        rate = total["agree"] / n
        det = total["detected"]
        avg_t = f"T{sum(turns)/len(turns):.1f}" if turns else "-"
        print(f"{arch:<18}{total['decisions']:>8}{rate:>8.2%}{total['diff']:>7}"
              f"{det:>6}/{total['games']:<3}{avg_t:>9}")

        if arch == GRIM_ARCHETYPE:
            if total["diff"] == 0:
                failures.append(f"{arch}: 差分ゼロ = 検証器に検出力が無い（ゲートが死んでいる）")
            else:
                grim_diff_seen = True
            if det < total["games"]:
                failures.append(f"{arch}: 検出漏れ {total['games'] - det}/{total['games']} 試合")
        else:
            if total["diff"] != 0:
                failures.append(f"{arch}: 非オーロンゲ対面で {total['diff']} 手が割れた = ゲート漏れ")
                for g, ctx, av, bv in diffs[:3]:
                    failures.append(f"    game={g} ctx={ctx} A={av} B={bv}")
            if det != 0:
                failures.append(f"{arch}: 非オーロンゲ対面で誤検出 {det} 試合")

    print()
    if failures:
        print("NG:")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print("OK: 非オーロンゲ対面は決定一致率 100%・誤検出0"
          + ("／オーロンゲ対面では差分あり（検出力あり）" if grim_diff_seen else ""))


if __name__ == "__main__":
    main()
