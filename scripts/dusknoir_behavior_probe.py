"""カースドボム版の「意図した振る舞い」プローブ（2026-07-25 背骨組み直しの検証）。

戦績でなく振る舞いを測る（本流が立ち上がるまで戦績で判定しない = ユーザー方針）:
  - ムズムズ花粉を序盤(<=T4)に撃てた試合率（本流の立ち上げロック）
  - ドロンチ engine が回った試合率（場に Drakloak が同時2体以上に達したか）
  - ファントムダイブを撃てた試合率 / 平均初回ターン
  - マシマシラ(アドレナ)が online 以外で場に出た違反率（サブ従属の検証）
  - カーズドボム/アドレナを撃てた試合率（詰めの発火）
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import read_deck            # noqa: E402
from gauntlet import read_field, build_opponent  # noqa: E402
from train_ppo import GameSampler, play_game      # noqa: E402
from cg import api, game as cg_game        # noqa: E402
from cg.api import LogType                 # noqa: E402

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR, MUNKIDORI = 131, 132, 133, 112
ATK_ITCHY_POLLEN = 323
ATK_PHANTOM_DIVE = 154
GAMES = 40
OPPONENTS = ["marnie", "archaludon", "alakazam", "froslass_starmie"]


def probe(sampler, opp_row, opp_mod, opp_deck, n):
    first_mod = sampler.target_mod
    policy = sampler.policy
    stat = Counter()
    dive_turns = []
    for g in range(n):
        from ab_battle import reset_agent
        reset_agent(first_mod)
        reset_agent(opp_mod)
        obs, _ = cg_game.battle_start(sampler.deck, opp_deck)
        if obs is None:
            continue
        seen = {"itchy_early": False, "engine": False, "dive": False,
                "munki_bad": False, "bomb": False, "adrena": False}
        first_dive_turn = None
        for _ in range(sampler.max_steps):
            typed = api.to_observation_class(obs)
            cur = typed.current
            if cur is not None and cur.result != -1:
                break
            if cur is not None and cur.yourIndex == 0:
                # 自軍盤面（本流フェーズと engine 判定）
                me = cur.players[0]
                board = list(me.active or []) + list(me.bench or [])
                ids = [pk.id for pk in board if pk]
                drak = ids.count(DRAKLOAK)
                dex = ids.count(DRAGAPULT_EX)
                phase = "online" if dex >= 1 else ("priming" if drak >= 1 else "setup")
                if drak >= 2:
                    seen["engine"] = True
                if MUNKIDORI in ids and phase != "online" and len(cur.players[1].prize) > 3:
                    seen["munki_bad"] = True
                policy.decision_log = []
                action = first_mod.agent(obs)
                for rec in (policy.decision_log or []):
                    sel = rec.get("selected") or []
                    reason = next((o["reason"] for o in rec["options"]
                                   if sel and o["i"] == sel[0]), "")
                    if "Cursed Blast" in reason:
                        seen["bomb"] = True
                    if "Adrena-Brain" in reason:
                        seen["adrena"] = True
                policy.decision_log = None
            else:
                action = opp_mod.agent(obs)
            # 直前ログの攻撃を拾う
            for log in (typed.logs or []):
                if log.type == LogType.ATTACK:
                    t = getattr(cur, "turn", 0) if cur else 0
                    if log.attackId == ATK_ITCHY_POLLEN and t <= 4:
                        seen["itchy_early"] = True
                    if log.attackId == ATK_PHANTOM_DIVE:
                        seen["dive"] = True
                        if first_dive_turn is None:
                            first_dive_turn = t
            obs = cg_game.battle_select(action)
        try:
            cg_game.battle_finish()
        except Exception:
            pass
        for k, v in seen.items():
            if v:
                stat[k] += 1
        if first_dive_turn:
            dive_turns.append(first_dive_turn)
    avg_dive = sum(dive_turns) / len(dive_turns) if dive_turns else 0
    return stat, avg_dive, n


def main():
    field = read_field(ROOT / "research/meta/2026-07-20_uniform_field.csv")
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(ROOT / "agents/dragapult_dusknoir_rb",
                          read_deck(ROOT / "decks/fleet/dragapult_dusknoir_paper.csv"),
                          field, 600, seed=17)
    for arch in OPPONENTS:
        row = rows[arch]
        opp_mod, opp_deck = build_opponent(row)
        stat, avg_dive, n = probe(sampler, row, opp_mod, opp_deck, GAMES)
        print(f"\n=== vs {arch} ({n}戦) ===")
        print(f"  ムズムズ早期(<=T4): {stat['itchy_early']/n:.0%}  "
              f"ドロンチengine(2体+): {stat['engine']/n:.0%}")
        print(f"  ダイブ到達: {stat['dive']/n:.0%} (平均初回 T{avg_dive:.1f})  "
              f"ボム発火: {stat['bomb']/n:.0%}  アドレナ発火: {stat['adrena']/n:.0%}")
        print(f"  [違反] マシマシラが online 以外で場に: {stat['munki_bad']/n:.0%}")


if __name__ == "__main__":
    main()
