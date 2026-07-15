"""上位プレイヤーのエピソードを自エージェントでリプレイし、選択の不一致を測る（P-02 の道具）。

各エピソードの対象プレイヤー（指定カードIDをデッキに含む・レート閾値以上）の全手番について、
同じ観測を自エージェントに与え、実際の選択と比較する。不一致は SelectContext 別に集計し、
カード名/技名にデコードして「上位ピロットは何を選び、我々は何を選んだか」を出す。

使い方:
  uv run python scripts\\replay_divergence.py --episodes downloads\\episodes\\2026-07-06 ^
      --agent agents\\marnie_munkidori_rb --archetype-cards 648,112 ^
      --leaderboard downloads\\leaderboard --min-score 900 [--show 30] [--max-games 60]

注意: エピソードの steps[t][pi].observation への答えは steps[t+1][pi].action（off-by-one）。
"""
import argparse
import csv
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "scripts"))
# policy_net の遅延 import 用（無いと agent dir の policy_net.npz が黙って無効化され、
# ネット込みの divergence を測ったつもりでルールのみを測ることになる）
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg.api import OptionType, SelectContext, all_attack, all_card_data, to_observation_class  # noqa: E402

from ab_battle import load_agent, reset_agent  # noqa: E402

CARD = {c.cardId: c for c in all_card_data()}
try:
    ATTACK = {a.attackId: a for a in all_attack()}
except Exception:
    ATTACK = {}
CTX_NAME = {int(c): c.name for c in SelectContext}
OPT_NAME = {int(o): o.name for o in OptionType}


def load_scores(lb_dir: Path):
    scores = {}
    for f in glob.glob(str(lb_dir / "*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            try:
                scores[r["TeamName"]] = float(r["Score"])
            except (KeyError, ValueError):
                pass
    return scores


def _get_card(obs, area, index, player_index):
    from cg.api import AreaType
    if area is None or index is None:
        return None
    try:
        ps = obs.current.players[player_index]
        if area == AreaType.DECK and obs.select and obs.select.deck is not None:
            return obs.select.deck[index] if index < len(obs.select.deck) else None
        pool = {AreaType.HAND: ps.hand, AreaType.DISCARD: ps.discard,
                AreaType.ACTIVE: ps.active, AreaType.BENCH: ps.bench,
                AreaType.PRIZE: ps.prize, AreaType.STADIUM: obs.current.stadium}.get(area)
        if pool is not None and index < len(pool):
            return pool[index]
    except Exception:
        pass
    return None


def describe_option(obs, opt):
    """option をカード名/技名つきの短い文字列に。"""
    from cg.api import AreaType
    parts = [OPT_NAME.get(int(opt.type), str(opt.type))]
    aid = getattr(opt, "attackId", None)
    if aid and aid in ATTACK:
        parts.append(ATTACK[aid].name)
    yi = obs.current.yourIndex if obs.current is not None else 0
    pi = opt.playerIndex if opt.playerIndex is not None else yi
    area = AreaType.HAND if opt.type == OptionType.PLAY else opt.area
    card = _get_card(obs, area, opt.index, pi)
    if card is not None and getattr(card, "id", None) in CARD:
        parts.append(CARD[card.id].name)
    if opt.inPlayArea is not None and opt.inPlayIndex is not None:
        tgt = _get_card(obs, opt.inPlayArea, opt.inPlayIndex, yi)
        if tgt is not None and getattr(tgt, "id", None) in CARD:
            parts.append("->" + CARD[tgt.id].name)
    return "/".join(parts)


def describe_action(obs, action):
    out = []
    for i in action or []:
        if obs.select and obs.select.option and 0 <= i < len(obs.select.option):
            out.append(f"[{i}]{describe_option(obs, obs.select.option[i])}")
        else:
            out.append(f"[{i}]?")
    return " ".join(out) if out else "(none)"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", required=True)
    parser.add_argument("--agent", required=True)
    parser.add_argument("--archetype-cards",
                        help="対象デッキの識別カードID（カンマ区切り、全て含むデッキが対象）")
    parser.add_argument("--match-deck",
                        help="デッキCSVパス。エピソードのデッキとの重なり枚数（多重度込み）で"
                             "対象を選ぶ（--archetype-cards の代替。模倣対象を自リスト近傍に絞る）")
    parser.add_argument("--min-overlap", type=int, default=45,
                        help="--match-deck 時の最小重なり枚数（60枚中。既定45）")
    parser.add_argument("--leaderboard", default="downloads/leaderboard")
    parser.add_argument("--min-score", type=float, default=900)
    parser.add_argument("--max-games", type=int, default=80)
    parser.add_argument("--show", type=int, default=30)
    parser.add_argument("--dump-decisions", default=None,
                        help="決定ログ JSONL の出力先（1決定=1行: 候補の score/reason/band + "
                             "上位者の選択。模倣学習の訓練データ。BasePolicy エージェント専用）")
    args = parser.parse_args()

    if not args.archetype_cards and not args.match_deck:
        raise SystemExit("--archetype-cards か --match-deck のどちらかを指定")
    want = {int(x) for x in args.archetype_cards.split(",")} if args.archetype_cards else None
    ref_deck = None
    if args.match_deck:
        from ab_battle import read_deck
        ref_deck = Counter(read_deck(ROOT / args.match_deck))
    scores = load_scores(ROOT / args.leaderboard)
    agent_mod = load_agent(ROOT / args.agent)

    # 決定ログの有効化（policy.decision_log はハーネス管理。reset_game では消えない）
    # 注: デッキ main.py の `def agent` は R-25 対応の素のラッパーで .policy を持たない。
    # make_agent の返り値（.policy 付き）は `_impl` に入っているのでそちらも探す。
    dump_f = None
    dump_warn = 0
    dump_count = 0
    policy = (getattr(getattr(agent_mod, "agent", None), "policy", None)
              or getattr(getattr(agent_mod, "_impl", None), "policy", None))
    if args.dump_decisions:
        if policy is None:
            raise SystemExit("--dump-decisions は BasePolicy エージェント（_impl/agent.policy あり）専用")
        policy.decision_log = []
        dump_path = ROOT / args.dump_decisions
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_f = open(dump_path, "w", encoding="utf-8")

    ctx_total = Counter()
    ctx_agree = Counter()
    pattern = Counter()          # (ctx, human_desc, our_desc) -> count
    firsts = Counter()           # IS_FIRST の実選択 (R-21)
    mulligans = Counter()        # MULLIGAN の実選択 (R-22)
    pilots = Counter()
    games = 0
    diffs_shown = []

    files = sorted(glob.glob(str(ROOT / args.episodes / "*.json")))
    for fp in files:
        if games >= args.max_games:
            break
        try:
            ep = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        steps = ep.get("steps", [])
        if len(steps) < 3:
            continue
        teams = (ep.get("info") or {}).get("TeamNames", ["?", "?"])
        # デッキ = steps[1][pi].action（60枚）
        for pi in (0, 1):
            try:
                deck = steps[1][pi]["action"]
            except Exception:
                continue
            if not (isinstance(deck, list) and len(deck) == 60):
                continue
            if want is not None and not (want <= set(deck)):
                continue
            if ref_deck is not None:
                overlap = sum((Counter(deck) & ref_deck).values())
                if overlap < args.min_overlap:
                    continue
            team = teams[pi] if pi < len(teams) else "?"
            score = scores.get(team, 0)
            if score < args.min_score:
                continue
            games += 1
            pilots[f"{team}({score:.0f})"] += 1
            reset_agent(agent_mod)
            # reset_agent は module.agent（素ラッパー）に .policy が無い現行形式では
            # no-op になる。リプレイは select=None のゲーム開始 obs を通らないため
            # make_agent 内の自動リセットも効かない → ここで明示的にリセットする
            # （R-17 の攻撃追跡やデッキ固有 self.p のゲーム間リークを防ぐ）。
            if policy is not None:
                policy.reset_game()
            for t in range(1, len(steps) - 1):
                try:
                    # INACTIVE 側の観測には前回の select が残留する（cabt.py は更新しない）ため
                    # ACTIVE ステップだけが「そのプレイヤーの手番」
                    if steps[t][pi].get("status") != "ACTIVE":
                        continue
                    od = steps[t][pi]["observation"]
                    if not od.get("select"):
                        continue
                    human = steps[t + 1][pi]["action"]
                    if not isinstance(human, list):
                        continue
                    obs = to_observation_class(od)
                    ctx = int(obs.select.context)
                    name = CTX_NAME.get(ctx, str(ctx))
                    if name == "IS_FIRST" and human:
                        opt = obs.select.option[human[0]]
                        firsts[OPT_NAME.get(int(opt.type), "?")] += 1
                    if name == "MULLIGAN" and human:
                        opt = obs.select.option[human[0]]
                        mulligans[OPT_NAME.get(int(opt.type), "?")] += 1
                    ours = agent_mod.agent(od)
                    agree_flag = list(ours) == list(human)
                    if dump_f is not None:
                        # agent() 1回につきレコード1件が正常。0件 = R-01 フォールバック発動
                        # か候補ゼロ（フック不良の検知にもなる）
                        if len(policy.decision_log) != 1:
                            dump_warn += 1
                        for rec in policy.decision_log:
                            rec.update({"episode": Path(fp).stem, "team": team,
                                        "pi": pi, "step": t,
                                        "human": list(human), "ours": list(ours),
                                        "agree": agree_flag})
                            dump_f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                            dump_count += 1
                        policy.decision_log.clear()
                    ctx_total[name] += 1
                    if agree_flag:
                        ctx_agree[name] += 1
                    else:
                        h = describe_action(obs, human)
                        o = describe_action(obs, ours)
                        pattern[(name, h.split(" ")[0], o.split(" ")[0])] += 1
                        if len(diffs_shown) < args.show:
                            diffs_shown.append((Path(fp).stem, team, name, h, o))
                except Exception:
                    continue

    total = sum(ctx_total.values())
    agree = sum(ctx_agree.values())
    print(f"games={games} pilots={dict(pilots)}")
    print(f"\nTOTAL agree {agree}/{total} = {agree / total:.1%}" if total else "no decisions")
    print("\n-- SelectContext別 一致率（不一致の多い順） --")
    for name in sorted(ctx_total, key=lambda c: -(ctx_total[c] - ctx_agree[c])):
        t, a = ctx_total[name], ctx_agree[name]
        print(f"  {name:>24}: {a}/{t} = {a / t:.0%}")
    print(f"\n-- R-21 IS_FIRST 上位ピロットの実選択: {dict(firsts)}")
    print(f"-- R-22 MULLIGAN 上位ピロットの実選択: {dict(mulligans)}")
    print("\n-- 不一致パターン上位（ctx / 人間の第1選択 / 我々の第1選択） --")
    for (name, h, o), n in pattern.most_common(20):
        print(f"  {n:3}x {name:>18}: human={h}  ours={o}")
    print("\n-- 不一致サンプル --")
    for ep_id, team, name, h, o in diffs_shown[:args.show]:
        print(f"  {ep_id} {team} {name}\n    human: {h}\n    ours : {o}")
    if dump_f is not None:
        dump_f.close()
        print(f"\ndumped {dump_count} decisions -> {ROOT / args.dump_decisions} (warn={dump_warn})")


if __name__ == "__main__":
    main()
