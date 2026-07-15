"""メタ加重ガントレット — 対象エージェントをシェア加重の相手プールと対戦させる。

フィールド定義CSV（既定: research/meta/2026-07-14_field.csv、正本は同名 .md）を読み、
各アーキタイプの相手役（既存エージェント資産 or GenericPolicy+デッキ）と席入替で対戦。
マッチアップ別勝率 + シェア加重勝率（= 制圧度）+ 最弱マッチアップ一覧を出力する。

設計参照: ptcg-abc の cabt_gauntlet（無ライセンスのためコードは新規実装。
対戦ループ・エージェント隔離は scripts/ab_battle.py の load_agent/reset_agent/run_battles を再利用）。

使い方:
  PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/gauntlet.py ^
      --agent agents/dragapult_rb --deck decks/fleet/popular_4_dragapult.csv ^
      [--games 40] [--field research/meta/2026-07-14_field.csv] [--only marnie,okidogi] [--out results.csv] ^
      [--styles tuned,generic,frozen]

--styles（P-11 ピロットスタイル多様性）: 同一相手デッキのピロットを
  tuned（フィールド定義の自作エージェント）/ generic（GenericPolicy）/
  frozen（experiments/frozen_agents/ の凍結旧版）で差し替えて勝率のブレを測る。
  無いスタイルは skip（generic 行に tuned は無い等）。スタイル間ブレ >15pt は警告
  =「特定ピロットの癖に勝っている」疑い（その勝率を根拠にしたルールは【暫定】扱い）。

注意（P-03）: 40戦は±10pt級のブレを含む。個別マッチアップの結論は80戦以上で。
"""
import argparse
import csv
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from ab_battle import get_policy, load_agent, read_deck, run_battles  # noqa: E402


def _freeze_opponent_theta(mod):
    """プール凍結（p=0 運用）: 相手役は常に手書き基準 θ=0 で指す。

    build_opponent はライブの agents/<deck>_rb/ をロードするため、θ を採用して
    theta.json を置いた瞬間に「相手プールの同デッキも強化される」= 目的関数が
    こちらの採用判断で動く裏口があった。場は外生の固定モデルなので相手側の θ は
    常時空にする（正典: docs/strategy/エージェントアーキテクチャと実験計画.md §4。
    将来ラダーの強化を織り込む場合は field CSV に別行として明示的に足す）。"""
    policy = get_policy(mod)
    if policy is not None:
        policy.theta = {}
        policy.net_enabled = False   # 方策ネットも同じ理由で凍結（プールは θ=0・ネット無し）


def read_field(path: Path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "archetype": row["archetype"].strip(),
                "share": float(row["share"]),
                "agent_or_deck": row["agent_or_deck"].strip(),
                "deck": row["deck"].strip(),
            })
    return rows


def build_opponent(row):
    """フィールド行 → (module-like, deck_ids)。generic は GenericPolicy が操縦する。"""
    deck = read_deck(ROOT / row["deck"])
    if row["agent_or_deck"] == "generic":
        import generic_policy
        agent_fn = generic_policy.make_generic_agent(deck, name=row["archetype"])
        return SimpleNamespace(agent=agent_fn), deck
    mod = load_agent(ROOT / row["agent_or_deck"])
    _freeze_opponent_theta(mod)
    return mod, deck


def find_frozen(agent_or_deck: str):
    """agents/xxx_rb → experiments/frozen_agents/xxx_rb*（凍結旧版）。無ければ None。"""
    if agent_or_deck == "generic":
        return None
    name = Path(agent_or_deck).name
    base = ROOT / "experiments" / "frozen_agents"
    if not base.exists():
        return None
    cands = sorted(d for d in base.iterdir()
                   if d.is_dir() and d.name.startswith(name) and (d / "main.py").exists())
    return cands[-1] if cands else None


def build_opponent_style(row, style):
    """フィールド行 × スタイル → (module-like, deck) or None（そのスタイルの実装が無い）。"""
    deck = read_deck(ROOT / row["deck"])
    if style == "generic":
        import generic_policy
        return SimpleNamespace(agent=generic_policy.make_generic_agent(deck, name=row["archetype"])), deck
    if style == "tuned":
        if row["agent_or_deck"] == "generic":
            return None
        mod = load_agent(ROOT / row["agent_or_deck"])
        _freeze_opponent_theta(mod)
        return mod, deck
    if style == "frozen":
        frozen = find_frozen(row["agent_or_deck"])
        if frozen is None:
            return None
        mod = load_agent(frozen)
        _freeze_opponent_theta(mod)
        return mod, deck
    raise SystemExit(f"unknown style: {style}（tuned/generic/frozen）")


def run_styles(args, field, target_deck):
    """P-11: 相手ピロットのスタイルを差し替えて勝率のブレ（感度）を測る。"""
    styles = [s.strip() for s in args.styles.split(",") if s.strip()]
    results = []
    t0 = time.perf_counter()
    for row in field:
        for style in styles:
            # マッチアップ毎に対象エージェントをロードし直す（モジュール隔離）
            target_mod = load_agent(ROOT / args.agent)
            inject_target_theta(target_mod, args.theta)
            inject_target_search(target_mod, args.search, target_deck)
            inject_target_net(target_mod, args.net)
            try:
                built = build_opponent_style(row, style)
            except SystemExit:
                raise
            except Exception as e:
                print(f"SKIP {row['archetype']}[{style}]: opponent load failed "
                      f"({type(e).__name__}: {e})")
                continue
            if built is None:
                print(f"skip {row['archetype']}[{style}]: そのスタイルの実装なし")
                continue
            opp_mod, opp_deck = built
            label = f"{Path(args.agent).name} vs {row['archetype']}[{style}]"
            w, l, d, u = run_matchup(target_mod, target_deck, opp_mod, opp_deck,
                                     args.games, args.max_steps, label)
            decided = w + l
            wr = w / decided if decided else 0.0
            print(f"==> {label}: {w}-{l} ({wr:.1%})\n")
            results.append({**row, "style": style, "wins": w, "losses": l, "draws": d,
                            "unfinished": u, "winrate": wr})

    if not results:
        raise SystemExit("no matchups run")

    print(f"\n=== gauntlet --styles: {args.agent} ({args.games} games/style/matchup) ===")
    print(f"{'archetype':>16} {'share%':>7} "
          + " ".join(f"{s:>8}" for s in styles) + f" {'spread':>7}")
    by_arch = {}
    for r in results:
        by_arch.setdefault(r["archetype"], {})[r["style"]] = r
    warned = []
    for arch, per in by_arch.items():
        share = next(iter(per.values()))["share"]
        cells, wrs = [], []
        for s in styles:
            if s in per:
                cells.append(f"{per[s]['winrate'] * 100:>7.1f}%")
                wrs.append(per[s]["winrate"])
            else:
                cells.append(f"{'-':>8}")
        spread = (max(wrs) - min(wrs)) * 100 if len(wrs) >= 2 else 0.0
        mark = "  <-- WARN >15pt" if spread > 15 else ""
        if spread > 15:
            warned.append(arch)
        print(f"{arch:>16} {share:>7.1f} " + " ".join(cells) + f" {spread:>6.1f}{mark}")
    if warned:
        print(f"\nWARN（P-11）: スタイル間ブレ >15pt: {', '.join(warned)} — "
              "特定ピロットの癖に勝っている疑い。この勝率を根拠にしたルールは【暫定】扱い。")
    else:
        print("\nスタイル間ブレ >15pt のマッチアップなし（P-11 感度チェック通過）")
    _print_throughput(results, time.perf_counter() - t0)

    if args.out:
        out = ROOT / args.out
        exists = out.exists()
        with open(out, "a", newline="", encoding="utf-8") as f:
            wcsv = csv.writer(f)
            if not exists:
                wcsv.writerow(["agent", "deck", "archetype", "share", "games",
                               "wins", "losses", "draws", "unfinished", "winrate"])
            for r in results:
                wcsv.writerow([args.agent, args.deck, f"{r['archetype']}[{r['style']}]",
                               r["share"], args.games, r["wins"], r["losses"], r["draws"],
                               r["unfinished"], f"{r['winrate']:.4f}"])
        print(f"appended -> {out}")


def _print_throughput(results, elapsed):
    """L1 実験予算の根拠となるスループット実測（P-03: 80/320試合が何分かを知る）。"""
    total = sum(r["wins"] + r["losses"] + r["draws"] + r["unfinished"] for r in results)
    if total and elapsed > 0:
        print(f"throughput: {total} games / {elapsed:.0f}s = "
              f"{total / elapsed * 60:.1f} games/min ({elapsed / total:.2f} s/game)")


def inject_target_theta(mod, theta_arg):
    """対象機の θ を上書きする（候補θの L1 計測用）。
    theta_arg: None = そのまま（agent dir の theta.json = 採用済みθ）/
    'zero' = θ空（手書き基準のベースライン計測）/ パス = その JSON を注入。"""
    if theta_arg is None:
        return
    policy = get_policy(mod)
    if policy is None:
        raise SystemExit("--theta: BasePolicy エージェントではない（theta 注入不可）")
    if theta_arg == "zero":
        policy.theta = {}
        return
    raw = json.loads((ROOT / theta_arg).read_text(encoding="utf-8"))
    policy.theta = {str(k): float(v) for k, v in raw.items() if v}


def inject_target_search(mod, search_arg, deck):
    """対象機のターン内探索を上書きする（A/B 用）。
    ローカル対戦ではデッキ選択手番が来ない（run_battles がデッキを直接渡す）ため、
    探索の決定化に必要な自デッキリストもここで注入する。"""
    if search_arg is None:
        return
    policy = get_policy(mod)
    if policy is None:
        raise SystemExit("--search: BasePolicy エージェントではない（注入不可）")
    policy.my_deck_list = list(deck)
    if search_arg == "off":
        policy.search_enabled = False
    else:
        policy.search_enabled = True
        policy.SEARCH_MODE = search_arg


def inject_target_net(mod, net_arg):
    """対象機の方策ネットを上書きする（PPO 候補の L2 A/B 用）。
    net_arg: None = そのまま（agent dir の policy_net.npz。現状どの機にも無い = ネット無し）/
    'off' = ネット無効（ベースライン計測）/ パス = その npz を注入。"""
    if net_arg is None:
        return
    policy = get_policy(mod)
    if policy is None:
        raise SystemExit("--net: BasePolicy エージェントではない（ネット注入不可）")
    if net_arg == "off":
        policy.net_enabled = False
        return
    import importlib
    pn = importlib.import_module("policy_net")
    net = pn.PolicyNet.load(str(ROOT / net_arg))
    if net is None:
        raise SystemExit(f"--net: ロード失敗（版不一致か破損）: {net_arg}")
    policy._net = net
    policy._net_load_tried = True


def run_matchup(target_mod, target_deck, opp_mod, opp_deck, games, max_steps, label):
    """席入替つき対戦。target 視点の (wins, losses, draws, unfinished) を返す。"""
    half = games // 2
    w1 = run_battles(half, target_mod, target_deck, opp_mod, opp_deck,
                     max_steps, f"{label} [target=p0]")
    w2 = run_battles(games - half, opp_mod, opp_deck, target_mod, target_deck,
                     max_steps, f"{label} [target=p1]")
    wins = w1[0] + w2[1]
    losses = w1[1] + w2[0]
    draws = w1[2] + w2[2]
    unfinished = w1[-1] + w2[-1] + w1["start_failed"] + w2["start_failed"]
    return wins, losses, draws, unfinished


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True, help="対象エージェントdir（agents/xxx_rb）")
    parser.add_argument("--deck", required=True, help="対象デッキCSV")
    parser.add_argument("--field", default="research/meta/2026-07-14_field.csv")
    parser.add_argument("--games", type=int, default=40, help="1マッチアップあたりのゲーム数")
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--only", help="アーキタイプ名のカンマ区切り（部分再計測用）")
    parser.add_argument("--exclude",
                        help="除外するアーキタイプのカンマ区切り（CEM の学習プールと同じ条件で"
                             "測るとき holdout をここに指定）")
    parser.add_argument("--theta",
                        help="対象機に注入する θ: theta.json のパス、または 'zero'（θ空 = 手書き基準）。"
                             "省略時は agent dir の theta.json（採用済みθ）。候補θの L1 計測用")
    parser.add_argument("--search", choices=["off", "rollout", "value"],
                        help="対象機のターン内探索を注入（A/B 用。省略時はクラス既定 = 現状全機 OFF）。"
                             "相手プールは常に探索なし。探索ONは1試合が数十秒になる点に注意")
    parser.add_argument("--net",
                        help="対象機に注入する方策ネット: policy_net.npz のパス、または 'off'"
                             "（ネット無効 = ルール基準）。省略時は agent dir の policy_net.npz"
                             "（現状どの機にも無い = ネット無し）。PPO 候補の L2 A/B 用")
    parser.add_argument("--out", help="結果を CSV 追記するパス（省略時は表示のみ）")
    parser.add_argument("--styles",
                        help="P-11 感度チェック: 相手スタイルのカンマ区切り（tuned,generic,frozen）。"
                             "指定時はスタイル別勝率とブレを出す（制圧度は出さない）")
    args = parser.parse_args()

    field = read_field(ROOT / args.field)
    if args.only:
        names = {n.strip() for n in args.only.split(",")}
        field = [r for r in field if r["archetype"] in names]
        missing = names - {r["archetype"] for r in field}
        if missing:
            raise SystemExit(f"unknown archetypes: {sorted(missing)}")
    if args.exclude:
        names = {n.strip() for n in args.exclude.split(",")}
        missing = names - {r["archetype"] for r in field}
        if missing:
            raise SystemExit(f"--exclude: unknown archetypes: {sorted(missing)}")
        field = [r for r in field if r["archetype"] not in names]

    target_deck = read_deck(ROOT / args.deck)
    if args.styles:
        run_styles(args, field, target_deck)
        return
    results = []
    t0 = time.perf_counter()
    for row in field:
        # マッチアップ毎に対象エージェントをロードし直す（モジュール隔離・状態持越し防止）
        target_mod = load_agent(ROOT / args.agent)
        inject_target_theta(target_mod, args.theta)
        inject_target_search(target_mod, args.search, target_deck)
        inject_target_net(target_mod, args.net)
        try:
            opp_mod, opp_deck = build_opponent(row)
        except Exception as e:
            print(f"SKIP {row['archetype']}: opponent load failed ({type(e).__name__}: {e})")
            continue
        label = f"{Path(args.agent).name} vs {row['archetype']}"
        w, l, d, u = run_matchup(target_mod, target_deck, opp_mod, opp_deck,
                                 args.games, args.max_steps, label)
        decided = w + l
        wr = w / decided if decided else 0.0
        results.append({**row, "wins": w, "losses": l, "draws": d,
                        "unfinished": u, "winrate": wr})
        print(f"==> {label}: {w}-{l} ({wr:.1%}) share={row['share']}%\n")

    if not results:
        raise SystemExit("no matchups run")

    print(f"\n=== gauntlet: {args.agent} ({args.games} games/matchup) ===")
    print(f"{'archetype':>16} {'share%':>7} {'W-L':>7} {'WR%':>6}")
    weighted_num = weighted_den = 0.0
    for r in sorted(results, key=lambda x: -x["share"]):
        print(f"{r['archetype']:>16} {r['share']:>7.1f} "
              f"{r['wins']:>3}-{r['losses']:<3} {r['winrate']*100:>5.1f}")
        weighted_num += r["share"] * r["winrate"]
        weighted_den += r["share"]
    if weighted_den:
        print(f"{'-'*40}")
        print(f"制圧度（シェア加重勝率）: {weighted_num / weighted_den * 100:.1f}%"
              f"  (covered share {weighted_den:.1f}%)")
    weakest = sorted(results, key=lambda x: x["winrate"])[:3]
    print("最弱マッチアップ: " + ", ".join(
        f"{r['archetype']} {r['winrate']:.0%}" for r in weakest))
    _print_throughput(results, time.perf_counter() - t0)

    if args.out:
        out = ROOT / args.out
        exists = out.exists()
        with open(out, "a", newline="", encoding="utf-8") as f:
            wcsv = csv.writer(f)
            if not exists:
                wcsv.writerow(["agent", "deck", "archetype", "share", "games",
                               "wins", "losses", "draws", "unfinished", "winrate"])
            for r in results:
                wcsv.writerow([args.agent, args.deck, r["archetype"], r["share"],
                               args.games, r["wins"], r["losses"], r["draws"],
                               r["unfinished"], f"{r['winrate']:.4f}"])
        print(f"appended -> {out}")


if __name__ == "__main__":
    main()
