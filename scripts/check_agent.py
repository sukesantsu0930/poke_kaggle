"""エージェント不変条件チェッカー — デッキ毎の退行をシステマティックに検知する（P-05 の防波堤）。

検査項目:
  1. 基盤同期     : policy_base.py / meta_tables.py が agents/_base/ の正本と一致（SHA-256）
  2. ビルド可能   : build_submission で実物の提出物が組める（deck検証・literal def 検査込み）
  3. 違法手ゼロ   : 範囲外/重複/個数逸脱の選択が無い（R-02）
  4. クラッシュゼロ: DIAG の errors / option_errors が 0（R-01。旧式エージェントは外形のみ）
  5. R-10 警告    : 既に技コストを払えるポケモンへの追加エネ付与（自己スケール技は除外）

使い方:
  uv run python scripts\\check_agent.py --agent agents\\archaludon_rb --deck decks\\fleet\\archaludon_cityleague.csv [--games 20]

exit 0 = 合格 / 1 = 違反あり
"""
import argparse
import hashlib
import importlib.util
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
# policy_net/turn_search の遅延 import 用（load_agent はエージェントdirを import 後に
# sys.path から外すため、ここに無いと npz があってもネットが黙ってルール縮退し、
# DIAG の net_calls が常に 0 になる。2026-07-15 PPO 評価で発覚）
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg import game  # noqa: E402
from cg import api  # noqa: E402

from build_submission import build_submission  # noqa: E402

BASE_FILES = ("policy_base.py", "meta_tables.py")
_PURGE = ("policy_base", "meta_tables", "main", "policy_net")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_base_sync(agent_dir: Path) -> list[str]:
    problems = []
    base_dir = ROOT / "agents" / "_base"
    for name in BASE_FILES:
        copy = agent_dir / name
        if not copy.exists():
            continue
        if sha256(copy) != sha256(base_dir / name):
            problems.append(f"base-sync: {copy.name} is stale (run scripts/sync_base.py)")
    return problems


def load_built_agent(work_dir: Path):
    for m in _PURGE:
        sys.modules.pop(m, None)
    sys.path.insert(0, str(work_dir))
    try:
        spec = importlib.util.spec_from_file_location("check_agent_target", work_dir / "main.py")
        mod = importlib.util.module_from_spec(spec)
        sys.modules["check_agent_target"] = mod
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(work_dir))
        for m in _PURGE:
            sys.modules.pop(m, None)
    return mod


def random_agent(obs_dict):
    obs = api.to_observation_class(obs_dict)
    if obs.select is None or not obs.select.option:
        return []
    n = len(obs.select.option)
    k = max(obs.select.minCount, min(1, obs.select.maxCount))
    return random.sample(range(n), min(k, n))


# ── R-10: エネ過剰付与の外形検査（進化ライン考慮。policy_base のコスト導出を利用） ──

def make_overfill_checker(work_dir: Path, mod, deck_ids):
    try:
        for m in _PURGE:
            sys.modules.pop(m, None)
        sys.path.insert(0, str(work_dir))
        import policy_base as pb
        sys.path.remove(str(work_dir))
        for m in _PURGE:
            sys.modules.pop(m, None)
    except Exception:
        return None

    self_scaling = set()
    policy = getattr(getattr(mod, "agent", None), "policy", None)
    if policy is not None:
        self_scaling = set(getattr(policy, "SELF_SCALING_ATTACK_IDS", set()) or set())

    def line_attack_ids(card_id):
        """対象の技 + デッキ内でそこから進化するカードの技（ライン全体）。
        進化前へのエネ先置きを偽陽性にしないため（ptcg-abc の教訓）。"""
        base = pb.CARD_DB.get(card_id)
        if base is None:
            return []
        names = {base.name}
        attack_ids = list(getattr(base, "attacks", None) or [])
        changed = True
        while changed:
            changed = False
            for cid in set(deck_ids):
                c = pb.CARD_DB.get(cid)
                if (c is not None and getattr(c, "evolvesFrom", None) in names
                        and c.name not in names):
                    names.add(c.name)
                    attack_ids += list(getattr(c, "attacks", None) or [])
                    changed = True
        return attack_ids

    def line_max_cost(card_id):
        costs = []
        for aid in line_attack_ids(card_id):
            if aid in self_scaling:
                return None  # 自己スケール技持ちラインは対象外
            cost = pb.attack_cost(aid)
            if cost is not None:
                costs.append(len(cost))
        return max(costs, default=0)

    from cg.api import CardType

    def _is_energy_card(card):
        data = pb.CARD_DB.get(getattr(card, "id", None))
        return data is not None and getattr(data, "cardType", None) in (
            CardType.BASIC_ENERGY, CardType.SPECIAL_ENERGY)

    def is_overfill(obs, action):
        """MAIN での「エネルギー」ATTACH が「ライン最大コストを既に満たす」ポケモンへの
        付与なら True（どうぐの装着は対象外）。"""
        try:
            if obs.select is None or obs.select.context != pb.SelectContext.MAIN:
                return False
            for idx in action:
                if not 0 <= idx < len(obs.select.option):
                    continue
                opt = obs.select.option[idx]
                if opt.type != pb.OptionType.ATTACH:
                    continue
                card = pb.option_card(obs, opt)
                if card is None or not _is_energy_card(card):
                    continue
                target = pb.option_target(obs, opt)
                if target is None:
                    continue
                max_cost = line_max_cost(target.id)
                if max_cost and pb.energy_count(target) >= max_cost:
                    return True
            return False
        except Exception:
            return False

    return is_overfill


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", required=True)
    parser.add_argument("--deck", required=True)
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--max-steps", type=int, default=600)
    args = parser.parse_args()

    agent_dir = ROOT / args.agent
    problems = check_base_sync(agent_dir)

    with tempfile.TemporaryDirectory() as td:
        work_dir = Path(td) / "work"
        zip_path = Path(td) / "check.zip"
        try:
            build_submission(agent_dir, ROOT / args.deck, zip_path, work_dir)
        except Exception as e:
            problems.append(f"build: {type(e).__name__}: {e}")
            _report(problems, None, 0, 0)
            raise SystemExit(1)

        mod = load_built_agent(work_dir)
        # R-25: Kaggle ローダー忠実検査 — モジュール名前空間の「最後の callable」が agent か
        # （kaggle_environments get_last_callable と同じ選び方で確認）
        callables = [v for v in vars(mod).values() if callable(v)]
        if callables and callables[-1] is not getattr(mod, "agent", None):
            name = getattr(callables[-1], "__name__", repr(callables[-1]))
            problems.append(f"R-25: last callable in main.py is {name!r}, not 'agent' "
                            "(Kaggle would call the wrong function)")
        deck = [int(l) for l in (work_dir / "deck.csv").read_text().split() if l.strip()]
        overfill_check = make_overfill_checker(work_dir, mod, deck)

        illegal = 0
        overfill = 0
        decisions = 0
        wins = 0
        for g in range(args.games):
            try:
                policy = getattr(getattr(mod, "agent", None), "policy", None)
                if policy is not None and hasattr(policy, "reset_game"):
                    policy.reset_game()
                obs, start = game.battle_start(deck, list(deck))
                if obs is None:
                    problems.append(f"game {g}: start_failed")
                    continue
                result = -1
                for _ in range(args.max_steps):
                    typed = api.to_observation_class(obs)
                    if typed.current is not None and typed.current.result != -1:
                        result = typed.current.result
                        break
                    if typed.current is not None and typed.current.yourIndex == 0:
                        action = mod.agent(obs)
                        decisions += 1
                        sel = typed.select
                        n = len(sel.option) if sel and sel.option else 0
                        mn = max(0, min(sel.minCount, n)) if sel else 0
                        mx = min(sel.maxCount, n) if sel else 0
                        ok = (isinstance(action, list)
                              and len(set(action)) == len(action)
                              and all(isinstance(i, int) and 0 <= i < n for i in action)
                              and mn <= len(action) <= mx)
                        if not ok:
                            illegal += 1
                        if overfill_check and overfill_check(typed, action):
                            overfill += 1
                    else:
                        action = random_agent(obs)
                    obs = game.battle_select(action)
                if result == 0:
                    wins += 1
            finally:
                try:
                    game.battle_finish()
                except Exception:
                    pass

        diag = getattr(mod, "DIAG", None) or getattr(getattr(mod, "agent", None), "diag", None)
        if illegal:
            problems.append(f"illegal selections: {illegal} (R-02)")
        if overfill:
            problems.append(f"energy over-fill: {overfill} (R-10)")
        if diag is not None:
            if diag.get("errors"):
                problems.append(f"agent-level exceptions: {diag['errors']} (R-01)")
            if diag.get("option_errors"):
                problems.append(f"per-option exceptions: {diag['option_errors']} (R-01)")
        _report(problems, diag, decisions, wins, args.games)
        raise SystemExit(1 if problems else 0)


def _report(problems, diag, decisions, wins, games=0):
    print(f"decisions={decisions} wins={wins}/{games}")
    if diag is not None:
        print(f"DIAG={diag}")
    else:
        print("DIAG unavailable (legacy agent) — external invariants only")
    if problems:
        for p in problems:
            print(f"NG {p}")
    else:
        print("OK all invariants pass")


if __name__ == "__main__":
    main()
