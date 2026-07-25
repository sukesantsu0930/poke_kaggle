"""ファントムダイブ確率計算の較正（2026-07-25）。

各ターン開始時、バトル場ドラパルト ex が e==1（あと1色でダイブ）の局面で
policy._dive_prob_this_turn の予測 P を記録し、そのターン中に活性が e>=2 に到達
（= 不足色を取れた）したかを実測。予測 P を帯に分けて実際の到達率と並べ、
計算が現実と合っているかを検証する（ユーザー方針: 戦績でなくまず予測精度）。
"""
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent   # noqa: E402
from gauntlet import read_field, build_opponent  # noqa: E402
from train_ppo import GameSampler               # noqa: E402
from cg import api, game as cg_game             # noqa: E402

DRAGAPULT_EX = 121
FIRE, PSY = 2, 5
GAMES = 60
OPPONENTS = ["marnie", "archaludon", "alakazam", "froslass_starmie"]
BUCKETS = [(0.0, 0.01), (0.01, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 0.99), (0.99, 1.01)]


def bucket(p):
    for lo, hi in BUCKETS:
        if lo <= p < hi:
            return (lo, hi)
    return (0.99, 1.01)


def main():
    field = read_field(ROOT / "research/meta/2026-07-20_uniform_field.csv")
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_dusknoir_rb",
                          read_deck(ROOT / "decks/fleet/dragapult_dusknoir_paper.csv"),
                          field, 600, seed=29)
    policy = sampler.policy
    first_mod = sampler.target_mod
    hit = defaultdict(int)   # bucket -> 到達数
    tot = defaultdict(int)   # bucket -> 記録数
    for arch in OPPONENTS:
        opp_mod, opp_deck = build_opponent(rows[arch])
        for _ in range(GAMES):
            reset_agent(first_mod)
            reset_agent(opp_mod)
            obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
            if obs is None:
                continue
            cur_turn = -1
            pending = None    # (bucket) 記録済みのターンの予測帯
            done = False
            for _ in range(sampler.max_steps):
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is not None and cur.result != -1:
                    break
                if cur is not None and cur.yourIndex == 0:
                    if cur.turn != cur_turn:
                        if pending is not None:
                            tot[pending] += 1
                            if done:
                                hit[pending] += 1
                        cur_turn = cur.turn
                        pending = None
                        done = False
                    me = cur.players[0]
                    act = me.active[0] if me.active else None
                    if act is not None and act.id == DRAGAPULT_EX:
                        e = len(act.energyCards or [])
                        if e == 1 and pending is None:
                            policy.p = policy._analyze(typed)
                            try:
                                prob = policy._dive_prob_this_turn(typed)
                            except Exception:
                                prob = -1
                            if prob >= 0:
                                pending = bucket(prob)
                        if e >= 2 and pending is not None:
                            done = True
                    action = first_mod.agent(obs)
                else:
                    action = opp_mod.agent(obs)
                obs = cg_game.battle_select(action)
            if pending is not None:
                tot[pending] += 1
                if done:
                    hit[pending] += 1
            try:
                cg_game.battle_finish()
            except Exception:
                pass

    print("予測 P 帯 | 記録数 | 実際に e>=2 到達 | 実測率")
    for b in BUCKETS:
        t = tot[b]
        h = hit[b]
        rate = f"{h/t:.0%}" if t else "-"
        print(f"  [{b[0]:.2f},{b[1]:.2f}) | {t:5d} | {h:5d} | {rate}")


if __name__ == "__main__":
    main()
