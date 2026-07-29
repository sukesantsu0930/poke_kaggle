"""序盤 KPI 計測器（F・2026-07-29 ユーザー採用）。

勝敗の実体は**初ダイブターン**（EXP-074 の観測: 勝ち T6.8 / 負け T9.7・到達率 98%/80%）。
勝率は 640戦で ±2pt の分解能しか無いのに対し、初ダイブTは 150戦程度でこの差が出る。
序盤ルールの A/B は、640戦ガントレットに掛ける**前に**ここで篩う。

出力:
  ① 初ダイブT（全体 / 勝ち / 負け）とダイブ到達率  ← 一次 KPI
  ② 機会損失イベント（サポート枠遊休・偵察指令未使用・ポフィン温存・進化可能未進化）
  ③ サポート遊休の**理由内訳**（A の設計材料。use_support が 0 か / 何が選ばれたか）
  ④ ベンチ構成（ドラメシヤ本数の分布・T1〜T6）
  ⑤ --trace で負け試合の序盤決定列

使い方:
  uv run python scripts/dusknoir_earlygame_kpi.py --games 25
  uv run python scripts/dusknoir_earlygame_kpi.py --games 50 --trace 3
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in ["scripts", "submission", "agents/_base", "training"]:
    sys.path.insert(0, str(ROOT / _p))

from ab_battle import read_deck, reset_agent          # noqa: E402
from gauntlet import read_field, build_opponent       # noqa: E402
from train_ppo import GameSampler                     # noqa: E402
from policy_base import CARD_DB, option_card          # noqa: E402
from cg import api, game as cg_game                   # noqa: E402
from cg.api import AreaType, LogType, OptionType      # noqa: E402

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, POFFIN, BOSS = 131, 1086, 1182
ATK_PHANTOM_DIVE = 154
EARLY = 6           # 「序盤」= T1〜T6 の自ターン
DIVE_CAP = 20       # 未到達は 20T として平均に算入（試合長の上限側）


def is_supporter(cid):
    d = CARD_DB.get(cid)
    return d is not None and int(getattr(d, "cardType", -1)) == 3


def run(agent_dir, deck_csv, field_csv, archetypes, games, seed, traces):
    field = read_field(field_csv)
    rows = {r["archetype"]: r for r in field}
    sampler = GameSampler(agent_dir, read_deck(deck_csv), field, 600, seed=seed)
    policy = sampler.policy

    W, L = Counter(), Counter()
    nw = nl = 0
    loss_traces = []

    for arch in archetypes:
        opp_mod, opp_deck = build_opponent(rows[arch])
        for _ in range(games):
            reset_agent(sampler.target_mod)
            reset_agent(opp_mod)
            obs, _unused = cg_game.battle_start(sampler.deck, opp_deck)
            if obs is None:
                continue
            ev = Counter()
            trace = []
            cur_turn = None
            ts = {}
            first_dive = None
            result = -1
            while True:
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is None or cur.result != -1:
                    result = cur.result if cur is not None else -1
                    break
                for lg in (typed.logs or []):
                    if (lg.type == LogType.ATTACK and lg.attackId == ATK_PHANTOM_DIVE
                            and first_dive is None):
                        first_dive = cur_turn or getattr(cur, "turn", 0)
                t_now = getattr(cur, "turn", 0)
                if cur_turn is not None and t_now != cur_turn:
                    _settle(ev, ts, cur_turn)
                    ts = {}
                    cur_turn = None
                if cur.yourIndex != 0:
                    obs = cg_game.battle_select(opp_mod.agent(obs))
                    continue
                cur_turn = t_now
                me = cur.players[0]
                if not ts:
                    ts = _open_turn(me, typed, t_now, ev)
                opts = list(typed.select.option or [])
                policy.decision_log = []
                action = sampler.target_mod.agent(obs)
                _observe(policy, opts, typed, ts, trace, cur_turn)
                policy.decision_log = None
                obs = cg_game.battle_select(action)
            if cur_turn is not None:
                _settle(ev, ts, cur_turn)

            won = (result == 0)
            tgt = W if won else L
            for k, v in ev.items():
                tgt[k] += v
            tgt["_dive_turn_sum"] += min(first_dive or DIVE_CAP, DIVE_CAP)
            tgt["_dive_reached"] += (1 if first_dive is not None else 0)
            if won:
                nw += 1
            else:
                nl += 1
                if len(loss_traces) < traces:
                    loss_traces.append((arch, trace[:26]))
            try:
                cg_game.battle_finish()
            except Exception:
                pass
    return W, L, nw, nl, loss_traces


def _open_turn(me, typed, t_now, ev):
    """自ターン開始時のスナップショット（機会の有無を記録する）。"""
    hand = [c.id for c in (me.hand or []) if c is not None]
    board = [pk for pk in ([me.active[0]] if me.active else []) + list(me.bench or [])
             if pk is not None]
    ts = {
        "mine": True, "sup_played": False, "recon_used": False,
        "poffin_played": False, "evolved": False, "chosen_support": None,
        "sup_in_hand": [c for c in hand if is_supporter(c)],
        "sup_offered": [],      # 実際に合法手として提示されたサポート（先攻T1 は提示されない）
        "recon_avail": any(pk.id == DRAKLOAK for pk in board),
        "poffin_in_hand": POFFIN in hand,
        "bench_room": len(me.bench or []) < 5,
        "evolve_avail": (DRAKLOAK in hand and any(
            pk.id == DREEPY and not getattr(pk, "appearThisTurn", False)
            for pk in board)),
    }
    if t_now <= EARLY:
        n_dreepy = sum(1 for pk in board if pk.id in (DREEPY, DRAKLOAK, DRAGAPULT_EX))
        ev[f"T{t_now}_line_{min(n_dreepy, 3)}"] += 1
    return ts


def _observe(policy, opts, typed, ts, trace, cur_turn):
    """1決定ぶんの実行結果を記録する（decision_log の selected を読む）。"""
    ts["chosen_support"] = getattr(policy, "use_support", 0) or ts["chosen_support"]
    for op in opts:
        if op.type == OptionType.PLAY:
            c = option_card(typed, op)
            if c is not None and is_supporter(c.id) and c.id not in ts["sup_offered"]:
                ts["sup_offered"].append(c.id)
    for rec in (policy.decision_log or []):
        sel = set(rec.get("selected") or [])
        for o in rec["options"]:
            if o["i"] not in sel or o["i"] >= len(opts):
                continue
            op = opts[o["i"]]
            if cur_turn <= EARLY:
                c = option_card(typed, op)
                nm = None
                if c is not None:
                    nm = getattr(CARD_DB.get(c.id), "name", c.id)
                trace.append(f"T{cur_turn} {str(op.type).split('.')[-1]}[{nm}] "
                             f"{(o.get('reason') or '')[:46]}")
            if op.type == OptionType.PLAY:
                c = option_card(typed, op)
                if c is not None:
                    if c.id == POFFIN:
                        ts["poffin_played"] = True
                    if is_supporter(c.id):
                        ts["sup_played"] = True
            elif op.type == OptionType.ABILITY:
                pk = _board_card(typed, op)
                if pk is not None and pk.id == DRAKLOAK:
                    ts["recon_used"] = True
            elif op.type == OptionType.EVOLVE:
                ts["evolved"] = True


def _board_card(typed, op):
    try:
        from policy_base import get_card
        return get_card(typed, op.area, op.index, 0)
    except Exception:
        return None


def _settle(ev, ts, turn):
    """自ターン締め: 機会があったのに使わなかったものを数える。"""
    if not ts or not ts.get("mine") or turn > EARLY:
        return
    if ts["sup_in_hand"] and not ts["sup_played"]:
        if not ts["sup_offered"]:
            # 合法手として提示されなかった（先攻T1 等）= 遊休ではない。真の遊休と分ける
            ev["（参考）サポート打てない番"] += 1
        else:
            ev["サポート枠を遊休"] += 1
            # A の設計材料: 遊休の理由内訳（提示されていた番だけ）
            if all(c == BOSS for c in ts["sup_offered"]):
                ev["  └ ボスのみ（的なし）"] += 1
            elif not ts["chosen_support"]:
                ev["  └ 選定が0（受け皿なし）"] += 1
            else:
                ev["  └ 選定済みだが未実行"] += 1
    if ts["recon_avail"] and not ts["recon_used"]:
        ev["偵察指令を未使用"] += 1
    if ts["poffin_in_hand"] and not ts["poffin_played"] and ts["bench_room"]:
        ev["ポフィン温存"] += 1
    if ts["evolve_avail"] and not ts["evolved"]:
        ev["進化可能なのに未進化"] += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/dragapult_dusknoir_rb")
    ap.add_argument("--deck", default="decks/fleet/dragapult_dusknoir_v2.csv")
    ap.add_argument("--field", default="research/meta/2026-07-27_uniform_frozen.csv")
    ap.add_argument("--archetypes", default="marnie,archaludon,froslass_starmie")
    ap.add_argument("--games", type=int, default=25, help="対面ごとの試合数")
    ap.add_argument("--seed", type=int, default=191)
    ap.add_argument("--trace", type=int, default=0, help="表示する負け試合トレース数")
    args = ap.parse_args()

    archs = [a.strip() for a in args.archetypes.split(",") if a.strip()]
    W, L, nw, nl, traces = run(ROOT / args.agent, ROOT / args.deck, ROOT / args.field,
                               archs, args.games, args.seed, args.trace)
    n = nw + nl
    print(f"=== 序盤 KPI（{n}戦: 勝ち {nw} / 負け {nl}・{','.join(archs)}）===")
    dive_all = (W["_dive_turn_sum"] + L["_dive_turn_sum"]) / max(1, n)
    reach_all = (W["_dive_reached"] + L["_dive_reached"]) / max(1, n)
    print(f"  ★初ダイブT（全体）  {dive_all:.2f}    ダイブ到達率 {reach_all:.0%}")
    print(f"     勝ち {W['_dive_turn_sum']/max(1,nw):.2f} ({W['_dive_reached']/max(1,nw):.0%})"
          f"  /  負け {L['_dive_turn_sum']/max(1,nl):.2f} ({L['_dive_reached']/max(1,nl):.0%})")
    print(f"  勝率 {nw/max(1,n):.1%}")
    print("  --- 機会損失（回/試合。勝ち / 負け）---")
    for k in sorted(set(W) | set(L)):
        if k.startswith("_") or k.startswith("T"):
            continue
        w, l = W[k] / max(1, nw), L[k] / max(1, nl)
        mark = " ★" if l > w * 1.3 and l - w > 0.15 else ""
        print(f"  {k:<22} {w:.2f} / {l:.2f}{mark}")
    print("  --- 序盤のドラパルトライン数（場・回/試合）---")
    for t in range(1, EARLY + 1):
        cells = [f"{i}本 {(W[f'T{t}_line_{i}']+L[f'T{t}_line_{i}'])/max(1,n):.2f}"
                 for i in range(4)]
        if any(float(c.split()[1]) > 0 for c in cells):
            print(f"  T{t}: " + "  ".join(cells))
    for arch, tr in traces:
        print(f"\n--- 負け例 vs {arch}（序盤の決定列）---")
        for t in tr:
            print(f"   {t}")


if __name__ == "__main__":
    main()
