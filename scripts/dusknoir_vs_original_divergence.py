"""カースドボム版 vs 通常版ドラパルトの決定差分マイニング（2026-07-26）。

背景: 対オーロンゲで、同一デッキ・死に札ゼロの条件でも 通常版 26.0% / ボム版 21.0%
（各1280戦・3.0σ）の差がある。個別ルールを推測で切る単発A/Bは9連続で空振り
（DUSK_STREAMS / R-29 / 分散禁止 / 開幕ロック / ボム照準 / 廃墟 / ボムライン非展開 …）。
= 差は「単一の穴」ではなく細かいルールの積み上げ。よって推測をやめ、**どの決定が
どれだけ食い違うか**を機械的に列挙する（EXP-013 の divergence mining と同じ構え。
教師を人間リプレイでなく通常版エージェントに置き換えたもの）。

やり方: 通常版が実際に対局を進め、その全決定点でボム版にも同じ obs を渡して比較する。
食い違った決定を「文脈 × 通常版が選んだ札 × ボム版が選んだ札 × ボム版の理由」で集計。
上位クラスタがそのままルール改修の候補リストになる。

使い方:
  PROBE_DECK_CSV=<deck> DUSK_DECK_CSV=<deck> python scripts/dusknoir_vs_original_divergence.py \
      --teacher <通常版dir> --deck <共通デッキ> --games 40
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import load_agent, read_deck, reset_agent, get_policy  # noqa: E402
from gauntlet import read_field, build_opponent                      # noqa: E402
from cg import api, game as cg_game                                  # noqa: E402
from policy_base import option_card                                  # noqa: E402
from cg.api import SelectContext, OptionType                          # noqa: E402

FIELD = ROOT / "research/meta/2026-07-20_uniform_field.csv"

NAMES = {}
try:
    with open(ROOT / "JP_Card_Data.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            NAMES.setdefault(int(r["カード ID"]), r["カード名"])
except Exception:
    pass


def _enum_name(enum_cls, value, prefix=""):
    try:
        return enum_cls(int(value)).name
    except Exception:
        return f"{prefix}{value}"


def label(typed, opt):
    """選択肢を『種別:カード名』に落とす（集計キー）。typed は to_observation_class 済み。"""
    if opt is None:
        return "None"
    t = _enum_name(OptionType, opt.type, "opt")
    try:
        card = option_card(typed, opt)
    except Exception:
        card = None
    if card is None:
        return t
    return f"{t}:{NAMES.get(card.id, card.id)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--teacher", required=True, help="教師（通常版）エージェントdir")
    ap.add_argument("--student", default="agents/dragapult_dusknoir_rb")
    ap.add_argument("--deck", required=True, help="共通デッキ CSV")
    ap.add_argument("--opponent", default="marnie")
    ap.add_argument("--games", type=int, default=40, help="1席あたりの試合数")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    teacher = load_agent(Path(args.teacher))
    student = load_agent(ROOT / args.student)
    spol = get_policy(student)
    deck = read_deck(Path(args.deck))
    row = {r["archetype"]: r for r in read_field(FIELD)}[args.opponent]

    total = Counter()
    diff = Counter()
    reasons = Counter()
    by_turn = Counter()

    for seat in (0, 1):
        opp_mod, opp_deck = build_opponent(row)
        for g in range(args.games):
            reset_agent(teacher)
            reset_agent(student)
            reset_agent(opp_mod)
            decks = (deck, opp_deck) if seat == 0 else (opp_deck, deck)
            obs, _ = cg_game.battle_start(list(decks[0]), list(decks[1]))
            if obs is None:
                continue
            try:
                for _ in range(args.max_steps):
                    typed = api.to_observation_class(obs)
                    cur = typed.current
                    if cur is None or cur.result != -1:
                        break
                    if cur.yourIndex != seat:
                        obs = cg_game.battle_select(opp_mod.agent(obs))
                        continue
                    ctx = typed.select.context if typed.select is not None else None
                    ctx_name = _enum_name(SelectContext, ctx, "ctx") if ctx is not None else "None"
                    t_act = teacher.agent(obs)
                    spol.decision_log = []
                    s_act = student.agent(obs)
                    s_reason = ""
                    for rec in (spol.decision_log or []):
                        sel = rec.get("selected") or []
                        s_reason = next((o["reason"] for o in rec["options"]
                                         if sel and o["i"] == sel[0]), "")
                    spol.decision_log = None
                    total[ctx_name] += 1
                    if list(t_act) != list(s_act):
                        opts = typed.select.option if typed.select is not None else []
                        t_lab = label(typed, opts[t_act[0]]) if t_act and t_act[0] < len(opts) else "?"
                        s_lab = label(typed, opts[s_act[0]]) if s_act and s_act[0] < len(opts) else "?"
                        diff[(ctx_name, t_lab, s_lab)] += 1
                        reasons[(ctx_name, s_reason)] += 1
                        by_turn[getattr(cur, "turn", -1)] += 1
                    obs = cg_game.battle_select(t_act)
            finally:
                try:
                    cg_game.battle_finish()
                except Exception:
                    pass

    n_tot = sum(total.values())
    n_dif = sum(diff.values())
    print(f"=== 決定差分（教師=通常版が進行 / {args.games*2}戦・{args.opponent}）===")
    print(f"総決定 {n_tot}  不一致 {n_dif} = {n_dif/max(1,n_tot):.1%}\n")
    print("--- 文脈別の不一致率 ---")
    for ctx, t in sorted(total.items(), key=lambda kv: -kv[1]):
        d = sum(v for (c, _, _), v in diff.items() if c == ctx)
        if t:
            print(f"  {ctx:<24}{d:>5}/{t:<6} = {d/t:5.1%}")
    print("\n--- 差分クラスタ上位（文脈 / 通常版の選択 → ボム版の選択） ---")
    for (ctx, tl, sl), c in diff.most_common(args.top):
        print(f"  {c:>4}  [{ctx}] {tl}  →  {sl}")
    print("\n--- ボム版が差分時に出した理由 上位 ---")
    for (ctx, rsn), c in reasons.most_common(args.top):
        print(f"  {c:>4}  [{ctx}] {rsn}")
    print("\n--- 差分が出たターン分布 ---")
    print("  " + str(dict(sorted(by_turn.items()))))


if __name__ == "__main__":
    main()
