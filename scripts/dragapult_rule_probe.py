"""通常版ドラパルトへ移植した一般ルール（2026-07-27）の発火プローブ。

戦績とは独立に「意図した振る舞いになっているか」を測る（ボム版 EXP-048 と同じ方法論。
勝率が動かなくても機構が動いていない場合と、動いた上で効かない場合を切り分ける）。

測るもの:
  - S-0!（DRA_DIVE_NOW）  : 候補として提示された回数 / 実際に採択された回数（採択率）
  - R-13+①（DISCARD保護） : 「即プレイできるので残す」判定が付いた候補の数
  - R-13+②（ハイパーボール）: 最後尾グッズとして打った回数 / 2枚未満で保留した回数
  - R-13+③（呼ぶ札）     : UB サーチで即プレイ可能札を選べた率
  - ルール12+（ポフィン）  : 常時即プレイで打った回数
  - ダイブ到達率 / 平均初回ターン（S-0! が狙う最終指標）

使い方（トグルは環境変数で切替 = OFF/ON をそのまま比較できる）:
  DRA_DIVE_NOW=1 DRA_PLAYABLE_NOW=1 DRA_CANDY_HOLD=1 DRA_POFFIN_ALWAYS=1 \
      python scripts/dragapult_rule_probe.py
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck, reset_agent      # noqa: E402
from gauntlet import read_field, build_opponent   # noqa: E402
from train_ppo import GameSampler                 # noqa: E402
from cg import api, game as cg_game               # noqa: E402
from cg.api import LogType                        # noqa: E402

ATK_PHANTOM_DIVE = 154
GAMES = 60
OPPONENTS = ["archaludon", "alakazam", "froslass_starmie", "marnie"]

# reason 断片 → カウンタ名（提示側）
PRESENT = {
    "S-0!": "s0_present",
    "R-13+: keep": "keep_present",
    "S-4/R-13+: Ultra Ball": "ub_last_present",
    "Ultra Ball: hold (fewer": "ub_hold_present",
    "rule12+: Poffin": "poffin_always_present",
}
# reason 断片 → カウンタ名（採択側 = selected に入った）
ADOPT = {
    "S-0!": "s0_adopt",
    "S-4/R-13+: Ultra Ball": "ub_last_adopt",
    "rule12+: Poffin": "poffin_always_adopt",
}


def probe(sampler, opp_mod, opp_deck, n):
    first_mod = sampler.target_mod
    policy = sampler.policy
    stat = Counter()
    dive_turns = []
    games = 0
    for _ in range(n):
        reset_agent(first_mod)
        reset_agent(opp_mod)
        obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
        if obs is None:
            continue
        games += 1
        dived = False
        first_dive_turn = None
        for _ in range(sampler.max_steps):
            typed = api.to_observation_class(obs)
            cur = typed.current
            if cur is not None and cur.result != -1:
                break
            if cur is not None and cur.yourIndex == 0:
                policy.decision_log = []
                action = first_mod.agent(obs)
                for rec in (policy.decision_log or []):
                    sel = set(rec.get("selected") or [])
                    for o in rec["options"]:
                        reason = o.get("reason") or ""
                        for frag, key in PRESENT.items():
                            if frag in reason:
                                stat[key] += 1
                        if o["i"] in sel:
                            for frag, key in ADOPT.items():
                                if frag in reason:
                                    stat[key] += 1
                policy.decision_log = None
            else:
                action = opp_mod.agent(obs)
            for log in (typed.logs or []):
                if log.type == LogType.ATTACK and log.attackId == ATK_PHANTOM_DIVE:
                    if not dived:
                        dived = True
                        stat["dive_games"] += 1
                        first_dive_turn = getattr(cur, "turn", 0) if cur else 0
            obs = cg_game.battle_select(action)
        try:
            cg_game.battle_finish()
        except Exception:
            pass
        if first_dive_turn:
            dive_turns.append(first_dive_turn)
    avg_dive = sum(dive_turns) / len(dive_turns) if dive_turns else 0
    return stat, avg_dive, games


def main():
    field = read_field(ROOT / "research/meta/2026-07-20_uniform_field.csv")
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_rb",
                          read_deck(ROOT / "decks/fleet/popular_4_dragapult.csv"),
                          field, 600, seed=17)
    total = Counter()
    total_games = 0
    for arch in OPPONENTS:
        opp_mod, opp_deck = build_opponent(rows[arch])
        stat, avg_dive, n = probe(sampler, opp_mod, opp_deck, GAMES)
        total.update(stat)
        total_games += n
        rate = stat["s0_adopt"] / stat["s0_present"] if stat["s0_present"] else 0
        print(f"\n=== vs {arch} ({n}戦) ===")
        print(f"  S-0!      提示 {stat['s0_present']/n:.2f}/試合  "
              f"採択 {stat['s0_adopt']/n:.2f}/試合  採択率 {rate:.0%}")
        print(f"  R-13+①    残す判定 {stat['keep_present']/n:.2f}/試合")
        print(f"  R-13+②    UB最後尾で打つ {stat['ub_last_adopt']/n:.2f}/試合  "
              f"2枚未満で保留 {stat['ub_hold_present']/n:.2f}/試合")
        print(f"  ルール12+  ポフィン即打ち {stat['poffin_always_adopt']/n:.2f}/試合")
        print(f"  ダイブ到達 {stat['dive_games']/n:.0%}  平均初回 T{avg_dive:.1f}")
    print(f"\n=== 合計 {total_games}戦 ===")
    rate = total["s0_adopt"] / total["s0_present"] if total["s0_present"] else 0
    print(f"  S-0! 提示 {total['s0_present']/total_games:.2f}/試合 "
          f"採択 {total['s0_adopt']/total_games:.2f}/試合 採択率 {rate:.0%}")
    print(f"  ダイブ到達 {total['dive_games']/total_games:.0%}")


if __name__ == "__main__":
    main()
