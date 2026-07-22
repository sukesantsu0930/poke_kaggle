"""勝敗×ルール決定性の分布監査（EXP-036 の計器。ユーザー提案 2026-07-21）。

普通にプール対戦を回し、decision_log から各決定の「首位と2位のスコア差（margin）」を
取って、勝ち試合 vs 負け試合で分布を比較する。margin==0 は index タイブレーク =
実質ランダム。負け試合で tie/weak（<1000）が集中する reason クラスタ =
次に書くべきルール（特に SELECT 系の対象選択・順序・数量）。

使い方:
  uv run python scripts/decisiveness_audit.py \
      --agent agents/rocket_rb --deck decks/fleet/rocket_lolzpo_0715.csv \
      [--field research/meta/2026-07-20_uniform_field.csv] [--games 140] [--top 12]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck            # noqa: E402
from gauntlet import read_field            # noqa: E402
from train_ppo import GameSampler          # noqa: E402


def game_decisions(policy):
    """decision_log → [(margin, chosen_reason, ctx)]（選択肢2つ以上・単一選択のみ）。"""
    out = []
    for rec in policy.decision_log:
        opts = rec["options"]
        if len(opts) < 2 or rec["max_count"] != 1:
            continue
        if rec.get("lethal_route") is not None:
            out.append((10 ** 9, "LETHAL", rec["ctx_name"]))
            continue
        scores = sorted((o["score"] for o in opts), reverse=True)
        sel = rec.get("selected") or []
        reason = next((o["reason"] for o in opts if sel and o["i"] == sel[0]), "?")
        out.append((float(scores[0] - scores[1]), reason, rec["ctx_name"]))
    return out


def bucket(margin):
    if margin >= 10 ** 8:
        return "lethal"
    if margin == 0:
        return "tie"
    if margin < 1000:
        return "weak"
    return "decisive"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--deck", required=True)
    ap.add_argument("--field", default="research/meta/2026-07-20_uniform_field.csv")
    ap.add_argument("--games", type=int, default=140)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--seed", type=int, default=23)
    args = ap.parse_args()

    field = read_field(ROOT / args.field)
    sampler = GameSampler(ROOT / args.agent, read_deck(ROOT / args.deck),
                          field, args.max_steps, seed=args.seed)
    policy = sampler.policy
    policy._net = None
    policy._net_load_tried = True      # 純ルール動作（ネット非介入で計測）

    stats = {"win": Counter(), "loss": Counter()}
    n_games = {"win": 0, "loss": 0}
    thin = {"win": Counter(), "loss": Counter()}
    loss_arch = Counter()
    for _ in range(args.games):
        policy.decision_log = []
        outcome, arch = sampler.play_one()
        decs = game_decisions(policy)
        policy.decision_log = None
        if outcome is None or outcome == 0.5:
            continue
        side = "win" if outcome == 1.0 else "loss"
        n_games[side] += 1
        if side == "loss":
            loss_arch[arch] += 1
        for margin, reason, ctx in decs:
            b = bucket(margin)
            stats[side][b] += 1
            if b in ("tie", "weak"):
                thin[side][f"{reason} [{ctx}]"] += 1

    print(f"=== {args.agent}  (win {n_games['win']} / loss {n_games['loss']}) ===")
    for side in ("win", "loss"):
        c = stats[side]
        tot = sum(c.values()) or 1
        print(f"  {side:<4} 決定 {tot:>6}: tie {c['tie'] / tot:.1%} / weak {c['weak'] / tot:.1%}"
              f" / decisive {c['decisive'] / tot:.1%} / lethal {c['lethal'] / tot:.1%}")
    print(f"  負け対面: {dict(loss_arch.most_common(5))}")
    print(f"  負け試合の tie/weak 決定 上位{args.top}:")
    for r, cnt in thin["loss"].most_common(args.top):
        print(f"    {cnt:>5}  {r}")


if __name__ == "__main__":
    main()
