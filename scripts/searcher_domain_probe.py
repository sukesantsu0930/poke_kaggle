"""サーチ札の「取得できる集合」を実測で導く（2026-07-27 ユーザー承認の方針）。

背景: ダイブ到達判定の穴は、私が「ポフィンはHP70以下のたね」「ポケパッドはルールボックス
無し」とカードテキストを読んで**手書きした表**に由来していた。エンジンがサーチ効果を
解決するときに提示する選択肢こそがその札の取得ドメインの真値なので、そこから導く。

出力: effect カードID → {context: 提示されたカードIDの集合}
  この表を meta_tables に固めれば、実行時の取得探索は数十µs のまま網羅性が保証される。

使い方:
  PYTHONIOENCODING=utf-8 python scripts/searcher_domain_probe.py \
      --agent agents/dragapult_rb --deck decks/fleet/popular_4_dragapult.csv --games 40
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent          # noqa: E402
from gauntlet import read_field, build_opponent       # noqa: E402
from train_ppo import GameSampler                     # noqa: E402
from policy_base import CARD_DB, option_card          # noqa: E402
from cg import api, game as cg_game                   # noqa: E402
from cg.api import SelectContext                      # noqa: E402

FIELD = ROOT / "research/meta/2026-07-27_uniform_frozen.csv"
FETCH_CTX = {
    int(SelectContext.TO_HAND): "TO_HAND",
    int(SelectContext.TO_BENCH): "TO_BENCH",
    int(SelectContext.ATTACH_TO): "ATTACH_TO",
    int(SelectContext.ATTACH_FROM): "ATTACH_FROM",
}


def name_of(cid):
    d = CARD_DB.get(cid)
    return getattr(d, "name", None) or str(cid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/dragapult_rb")
    ap.add_argument("--deck", default="decks/fleet/popular_4_dragapult.csv")
    ap.add_argument("--games", type=int, default=40)
    ap.add_argument("--opponents", default="archaludon,alakazam,marnie")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    field = read_field(FIELD)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / args.agent, read_deck(ROOT / args.deck),
                          field, 600, seed=83)
    policy = sampler.policy
    # effect_id -> context -> set(card_id)
    domain = defaultdict(lambda: defaultdict(set))
    seen_effects = defaultdict(int)

    for arch in args.opponents.split(","):
        opp_mod, opp_deck = build_opponent(rows[arch.strip()])
        for _ in range(args.games):
            reset_agent(sampler.target_mod)
            reset_agent(opp_mod)
            obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
            if obs is None:
                continue
            while True:
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is None or cur.result != -1:
                    break
                if cur.yourIndex != 0:
                    obs = cg_game.battle_select(opp_mod.agent(obs))
                    continue
                ctx = int(typed.select.context)
                action = sampler.target_mod.agent(obs)
                eff = (policy.p or {}).get("effect_id")
                if ctx in FETCH_CTX and eff:
                    seen_effects[eff] += 1
                    for o in (typed.select.option or []):
                        c = option_card(typed, o)
                        cid = c.id if c is not None else getattr(o, "cardId", None)
                        if cid is not None:
                            domain[eff][FETCH_CTX[ctx]].add(cid)
                obs = cg_game.battle_select(action)
            try:
                cg_game.battle_finish()
            except Exception:
                pass

    print(f"=== サーチ札の取得ドメイン（実測・{args.agent}）===")
    out = {}
    for eff in sorted(domain, key=lambda e: -seen_effects[e]):
        print(f"\n{name_of(eff)} (id={eff}, 解決 {seen_effects[eff]} 回)")
        out[eff] = {}
        for ctx, ids in sorted(domain[eff].items()):
            names = sorted(name_of(i) for i in ids)
            out[eff][ctx] = sorted(ids)
            print(f"  {ctx}: {len(ids)}種  {names}")
    if args.out:
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                  encoding="utf-8")
        print(f"\n保存 -> {args.out}")


if __name__ == "__main__":
    main()
