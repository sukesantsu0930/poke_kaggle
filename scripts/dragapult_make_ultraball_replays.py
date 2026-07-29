"""ハイパーボールを使った試合のリプレイ JSON を採る（2026-07-27・ユーザー依頼）。

目視確認用。「打った番に何を切って何を持ってきたか」を人が読める形で添える。

出力（既定 research/dragapult_replays/）:
  <prefix>N.json           公式 Visualizer 用の対戦データ（run/03_play のバッチで開ける）
  <prefix>N_agentlog.json  自分の行動系列（既存の export_visualizer_json 形式）
  <prefix>N_ultraball.json ハイパーボール発火だけを抜いた要約
      = {turn, 切った2枚, 持ってきた札, 打った時点の手札, 判断理由}

トグルは環境変数でそのまま渡せる（既定 = 現行の提出物挙動）:
  PYTHONIOENCODING=utf-8 python scripts/dragapult_make_ultraball_replays.py
  DRA_UB_DEMAND=1 PYTHONIOENCODING=utf-8 python scripts/dragapult_make_ultraball_replays.py \
      --prefix u3_ub --count 3
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ULTRA_BALL = 1121
OPP_AGENT = {
    "marnie": ("agents/marnie_munkidori_rb", "decks/fleet/marnie_mainstream_0718.csv"),
    "alakazam": ("agents/alakazam_rb", "decks/fleet/alakazam_top_0710.csv"),
    "archaludon": ("agents/archaludon_rb", "decks/fleet/archaludon_cityleague.csv"),
    "froslass_starmie": ("agents/froslass_starmie_rb",
                         "decks/fleet/froslass_starmie_taksai.csv"),
    "chandelure": ("agents/chandelure_rb", "decks/fleet/chandelure_top.csv"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/dragapult_rb")
    ap.add_argument("--deck", default="decks/fleet/popular_4_dragapult.csv")
    ap.add_argument("--opponent", default="marnie", choices=sorted(OPP_AGENT))
    ap.add_argument("--count", type=int, default=4, help="保存する試合数")
    ap.add_argument("--max-tries", type=int, default=40)
    ap.add_argument("--min-fires", type=int, default=1,
                    help="この回数以上ハイパーボールを打った試合だけ保存する")
    ap.add_argument("--prefix", default="ultraball")
    ap.add_argument("--outdir", default="research/dragapult_replays")
    args = ap.parse_args()

    for p in ["scripts", "submission", "agents/_base"]:
        sys.path.insert(0, str(ROOT / p))
    from export_visualizer_json import load_agent, read_deck   # noqa: E402
    from ab_battle import get_policy, reset_agent              # noqa: E402
    from policy_base import CARD_DB, option_card               # noqa: E402
    from cg import api                                          # noqa: E402
    from cg.api import SelectContext                            # noqa: E402
    from cg.game import battle_finish, battle_select, battle_start, visualize_data  # noqa: E402

    def name_of(cid):
        d = CARD_DB.get(cid)
        return getattr(d, "name", None) or str(cid)

    opp_dir, opp_deck_path = OPP_AGENT[args.opponent]
    a0 = load_agent(ROOT / args.agent, "ub_agent0")
    a1 = load_agent(ROOT / opp_dir, "ub_agent1")
    d0 = read_deck(ROOT / args.deck)
    d1 = read_deck(ROOT / opp_deck_path)
    policy = get_policy(a0)

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    saved = tried = 0
    while saved < args.count and tried < args.max_tries:
        tried += 1
        reset_agent(a0)
        reset_agent(a1)
        obs, start = battle_start(list(d0), list(d1))
        if obs is None:
            continue
        events, pending = [], None
        result, steps = -1, 0
        try:
            for steps in range(1000):
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is not None and cur.result != -1:
                    result = cur.result
                    break
                if cur is not None and cur.yourIndex == 0:
                    ctx = int(typed.select.context)
                    opts = list(typed.select.option or [])
                    hand = [c.id for c in (cur.players[0].hand or []) if c is not None]
                    policy.decision_log = []
                    action = a0.agent(obs)
                    for rec in (policy.decision_log or []):
                        sel = set(rec.get("selected") or [])
                        # 打った瞬間
                        for o in rec["options"]:
                            reason = o.get("reason") or ""
                            if ("Ultra Ball" in reason and o["i"] in sel
                                    and "hold" not in reason):
                                pending = {
                                    "turn": getattr(cur, "turn", None),
                                    "step": steps,
                                    "reason": reason,
                                    "hand_before": [name_of(c) for c in hand],
                                    "discarded": [],
                                    "fetched": [],
                                }
                                events.append(pending)
                        # 支払い
                        if pending is not None and ctx in (
                                int(SelectContext.DISCARD),
                                int(SelectContext.DISCARD_CARD_OR_ATTACHED_CARD)):
                            for i in sel:
                                if i < len(opts):
                                    idx = getattr(opts[i], "index", None)
                                    if idx is not None and idx < len(hand):
                                        pending["discarded"].append(name_of(hand[idx]))
                        # サーチ先
                        if (pending is not None and ctx == int(SelectContext.TO_HAND)
                                and (policy.p or {}).get("effect_id") == ULTRA_BALL):
                            for i in sel:
                                if i < len(opts):
                                    c0 = option_card(typed, opts[i])
                                    cid0 = c0.id if c0 is not None else getattr(
                                        opts[i], "cardId", None)
                                    if cid0 is not None:
                                        pending["fetched"].append(name_of(cid0))
                    policy.decision_log = None
                else:
                    action = a1.agent(obs)
                obs = battle_select(action)
            raw = visualize_data()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw
        finally:
            battle_finish()

        if len(events) < args.min_fires:
            continue
        saved += 1
        name = f"{args.prefix}{saved}"
        (outdir / f"{name}.json").write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        summary = {
            "agent": args.agent, "deck": args.deck, "opponent": args.opponent,
            "result": ("win" if result == 0 else "loss" if result == 1 else "draw"),
            "steps": steps,
            "ultra_ball_uses": events,
        }
        (outdir / f"{name}_ultraball.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"保存 {name}.json  ({summary['result']}, ハイパーボール {len(events)}回)")
        for e in events:
            print(f"   T{e['turn']}: 切った {e['discarded']} → 取った {e['fetched']}")
    print(f"\n{saved}/{args.count} 本を {outdir} に保存（{tried} 試合試行）")


if __name__ == "__main__":
    main()
