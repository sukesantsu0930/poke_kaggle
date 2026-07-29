"""2エージェント対戦 A/B とシャドー比較。

通常モード: 席入替つき対戦（前半 A=p0、後半 B=p0）で勝率を測る。
  uv run python scripts\\ab_battle.py --agent-a agents\\archaludon_rb --deck-a decks\\...csv ^
      --agent-b experiments\\frozen_agents\\archaludon_rb_v1 --deck-b decks\\...csv --games 80

シャドーモード (--shadow): A のミラー対戦（A が両席を操作）で進行しつつ、全手番で B にも
同じ obs を問い合わせ、選択の一致率を SelectContext 別に集計する。挙動保存リファクタの
検証器（一致率100%が合格。P-03 の勝率A/Bより強い決定的シグナル）。
  uv run python scripts\\ab_battle.py --shadow --agent-a <旧> --agent-b <新> --deck-a <共通デッキ> --games 20

注意（モジュール隔離）: エージェントは policy_base/meta_tables を sibling import するため、
ロード毎に sys.modules を purge し一意なモジュール名で読み込む。これを怠ると2体目が
1体目の基盤コピーを掴む（キャッシュ事故）。
"""
import argparse
import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))

from cg import game  # noqa: E402
from cg import api  # noqa: E402

_PURGE = ("policy_base", "meta_tables", "main",
          "turn_search", "value_model", "opp_decks", "generic_policy", "policy_net")
_load_counter = 0


def load_agent(agent_dir: Path):
    """エージェントdirの main.py を一意なモジュール名で隔離ロードする。"""
    global _load_counter
    _load_counter += 1
    name = f"ab_agent_{_load_counter}"
    main_py = agent_dir / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(main_py)
    for m in _PURGE:
        sys.modules.pop(m, None)
    sys.path.insert(0, str(agent_dir))
    try:
        spec = importlib.util.spec_from_file_location(name, main_py)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(agent_dir))
        for m in _PURGE:
            sys.modules.pop(m, None)
    return mod


def get_policy(mod):
    """モジュールから BasePolicy インスタンスを取り出す（無ければ None）。
    デッキ main.py の `def agent` は R-25 対応の素ラッパーで .policy を持たないため、
    make_agent の返り値が入っている `_impl` 側も探す。"""
    return (getattr(getattr(mod, "agent", None), "policy", None)
            or getattr(getattr(mod, "_impl", None), "policy", None))


def reset_agent(mod):
    """ゲーム間で内部状態をリセット（新旧どちらの実装形式にも対応）。"""
    policy = get_policy(mod)
    if policy is not None and hasattr(policy, "reset_game"):
        policy.reset_game()
        return
    if hasattr(mod, "_opp_last_attack_id"):
        mod._opp_last_attack_id = None
    if hasattr(mod, "_cur_turn_logs"):
        try:
            mod._cur_turn_logs.clear()
        except Exception:
            pass


def read_deck(path: Path):
    lines = [l.strip() for l in path.read_text().split("\n")]
    return [int(l) for l in lines if l][:60]


def run_battles(games, first_mod, first_deck, second_mod, second_deck, max_steps, label):
    # R-32 前提の注入（2026-07-28 恒久修正）: ローカル対戦ではデッキ選択手番が来ない
    # （デッキを battle_start に直接渡す）ため、make_agent の my_deck_list 注入経路が
    # 通らず、基盤の自山カウンティングが初期化されない。旧コードは各機の
    # _visible_counts フォールバックで偶然生きていたが、R-32 一本化でフォールバックを
    # 撤去した際に**ガントレット系の全計測が全ゼロ勘定で走る事故**が起きた
    # （dragapult 制圧度 72.0→54.8 の崩壊。原因切り分けは 07-28 の関数二分探索）。
    # ここは全対戦ハーネスの唯一の隘路なので、両者へ常時注入する。
    for mod, dk in ((first_mod, first_deck), (second_mod, second_deck)):
        pol = get_policy(mod)
        if pol is not None and getattr(pol, "my_deck_list", None) in (None, []):
            pol.my_deck_list = list(dk)
    wins = Counter()
    for g in range(games):
        try:
            reset_agent(first_mod)
            reset_agent(second_mod)
            obs, start = game.battle_start(first_deck, second_deck)
            if obs is None:
                wins["start_failed"] += 1
                continue
            result = -1
            for _ in range(max_steps):
                typed = api.to_observation_class(obs)
                if typed.current is not None and typed.current.result != -1:
                    result = typed.current.result
                    break
                if typed.current is not None and typed.current.yourIndex == 0:
                    action = first_mod.agent(obs)
                else:
                    action = second_mod.agent(obs)
                obs = game.battle_select(action)
            wins[result] += 1
        finally:
            try:
                game.battle_finish()
            except Exception:
                pass
    print(f"{label}: p0={wins[0]} p1={wins[1]} draw={wins[2]} "
          f"unfinished={wins[-1]} start_failed={wins['start_failed']}")
    return wins


def run_shadow(games, a_dir, b_dir, deck, max_steps, show):
    ctx_total = Counter()
    ctx_agree = Counter()
    diffs = []
    # 席ごとに独立したモジュールインスタンス（内部状態の混線防止）
    a0, a1 = load_agent(a_dir), load_agent(a_dir)
    b0, b1 = load_agent(b_dir), load_agent(b_dir)
    for g in range(games):
        try:
            for m in (a0, a1, b0, b1):
                reset_agent(m)
            obs, start = game.battle_start(deck, list(deck))
            if obs is None:
                continue
            for step in range(max_steps):
                typed = api.to_observation_class(obs)
                if typed.current is not None and typed.current.result != -1:
                    break
                yi = typed.current.yourIndex if typed.current is not None else 0
                driver = a0 if yi == 0 else a1
                shadow = b0 if yi == 0 else b1
                action = driver.agent(obs)
                b_action = shadow.agent(obs)
                ctx = typed.select.context if typed.select is not None else None
                ctx_name = getattr(ctx, "name", str(ctx))
                ctx_total[ctx_name] += 1
                if list(action) == list(b_action):
                    ctx_agree[ctx_name] += 1
                elif len(diffs) < show:
                    diffs.append((g, step, ctx_name, list(action), list(b_action)))
                obs = game.battle_select(action)
        finally:
            try:
                game.battle_finish()
            except Exception:
                pass

    total = sum(ctx_total.values())
    agree = sum(ctx_agree.values())
    print(f"\nSHADOW: agree {agree}/{total} = {agree / total:.2%}" if total else "SHADOW: no decisions")
    for ctx_name in sorted(ctx_total, key=lambda c: -(ctx_total[c] - ctx_agree[c])):
        t, a = ctx_total[ctx_name], ctx_agree[ctx_name]
        mark = "" if a == t else "  <-- DIVERGE"
        print(f"  {ctx_name:>28}: {a}/{t}{mark}")
    for g, step, ctx_name, av, bv in diffs:
        print(f"  diff game={g} step={step} ctx={ctx_name} a={av} b={bv}")
    return agree == total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-a", required=True)
    parser.add_argument("--agent-b", required=True)
    parser.add_argument("--deck-a", required=True)
    parser.add_argument("--deck-b", help="通常モードのB側デッキ（省略時 deck-a と同じ）")
    parser.add_argument("--games", type=int, default=40)
    parser.add_argument("--max-steps", type=int, default=600)
    parser.add_argument("--shadow", action="store_true")
    parser.add_argument("--show", type=int, default=20, help="shadow: 表示する不一致の最大数")
    args = parser.parse_args()

    a_dir = ROOT / args.agent_a
    b_dir = ROOT / args.agent_b
    deck_a = read_deck(ROOT / args.deck_a)
    deck_b = read_deck(ROOT / (args.deck_b or args.deck_a))

    if args.shadow:
        ok = run_shadow(args.games, a_dir, b_dir, deck_a, args.max_steps, args.show)
        raise SystemExit(0 if ok else 1)

    mod_a = load_agent(a_dir)
    mod_b = load_agent(b_dir)
    half = args.games // 2
    w1 = run_battles(half, mod_a, deck_a, mod_b, deck_b, args.max_steps, "A(p0) vs B(p1)")
    w2 = run_battles(args.games - half, mod_b, deck_b, mod_a, deck_a, args.max_steps, "B(p0) vs A(p1)")
    a_wins = w1[0] + w2[1]
    b_wins = w1[1] + w2[0]
    decided = a_wins + b_wins
    if decided:
        print(f"TOTAL: A={a_wins} B={b_wins} (A win rate {a_wins / decided:.1%} of decided)")


if __name__ == "__main__":
    main()
