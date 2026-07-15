"""上位ピロットのエピソード → 方策ネット BC（模倣）用データセット抽出。

replay_divergence と同じ歩行（ACTIVE ステップ・off-by-one）で対象ピロットの決定を
リプレイし、**_maybe_net と同一のゲート**（MAIN・maxCount==1・リーサル不成立・
正帯候補 2〜12 件）を通る決定だけを、policy_net の特徴量つきで npz に落とす。

設計:
  - 候補集合とルールスコアは自エージェント（BasePolicy）の decision_log から再構成する
    = 学習前の初期方策（残差ネットの土台）と完全に同じ候補・同じ並び。
  - 特徴量は「語彙なし」（vocab={} / n_vocab=0 = reason は末尾 OOV 1枠に縮退）で保存し、
    reason 文字列を別配列で並置する。train_bc.py が訓練データから語彙を確定した後、
    OOV 枠を差し替えて one-hot を展開する（policy_net.extract_features と正確に一致）。
  - 教師ラベル k = 人間の選択が候補の何行目か。候補外（負帯・13位以下）を選んだ決定は
    skip して件数を報告する（ネットの行動空間の外 = BC では学べない）。

使い方:
  uv run python training/extract_bc_dataset.py \
      --episodes downloads/episodes/2026-07-13 \
      --agent agents/alakazam_rb --match-deck decks/fleet/alakazam_top_0710.csv \
      --min-overlap 55 --min-score 1180 --out data/imitation/alakazam_bc/2026-07-13.npz
"""
import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg.api import SelectContext, to_observation_class  # noqa: E402

from ab_battle import load_agent, read_deck  # noqa: E402
from replay_divergence import load_scores  # noqa: E402

import policy_net as pn  # noqa: E402

NET_MAX_CANDIDATES = 12   # policy_base.BasePolicy.NET_MAX_CANDIDATES と揃える


def gate_candidates(rec):
    """decision_log レコード → _maybe_net と同じ候補列 [(oi, score, reason)]。
    対象外（MAIN以外・複数選択・リーサル成立・正帯<2）は None。"""
    if rec["ctx_name"] != "MAIN" or rec["max_count"] != 1:
        return None
    if rec.get("lethal_route") is not None:
        return None
    opts = sorted(rec["options"], key=lambda o: (o["score"], -o["i"]), reverse=True)
    cands = [(o["i"], float(o["score"]), o["reason"])
             for o in opts if 0 <= o["score"] < 100_000]
    cands = cands[:NET_MAX_CANDIDATES]
    if len(cands) < 2:
        return None
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True,
                    help="エピソードdir（カンマ区切りで複数可）")
    ap.add_argument("--agent", required=True)
    ap.add_argument("--match-deck", required=True,
                    help="模倣対象のデッキCSV（重なり枚数で対象ピロットを絞る）")
    ap.add_argument("--min-overlap", type=int, default=55)
    ap.add_argument("--leaderboard", default="downloads/leaderboard")
    ap.add_argument("--min-score", type=float, default=1180)
    ap.add_argument("--max-games", type=int, default=500)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ref_deck = Counter(read_deck(ROOT / args.match_deck))
    scores = load_scores(ROOT / args.leaderboard)
    agent_mod = load_agent(ROOT / args.agent)
    policy = (getattr(getattr(agent_mod, "agent", None), "policy", None)
              or getattr(getattr(agent_mod, "_impl", None), "policy", None))
    if policy is None:
        raise SystemExit("BasePolicy エージェント（_impl.policy あり）専用")
    policy.decision_log = []

    X_rows = []           # 各決定の (K, D0) 行列
    k_arr = []            # 教師ラベル（候補行番号）
    reasons_flat = []     # 候補の reason（決定内の行順に flat）
    n_cands = []
    meta_day = []
    meta_team = []
    meta_episode = []
    stats = Counter()

    files = []
    for d in args.episodes.split(","):
        files.extend(sorted(glob.glob(str(ROOT / d.strip() / "*.json"))))
    games = 0
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
        day = Path(fp).parent.name
        for pi in (0, 1):
            try:
                deck = steps[1][pi]["action"]
            except Exception:
                continue
            if not (isinstance(deck, list) and len(deck) == 60):
                continue
            if sum((Counter(deck) & ref_deck).values()) < args.min_overlap:
                continue
            team = teams[pi] if pi < len(teams) else "?"
            if scores.get(team, 0) < args.min_score:
                continue
            games += 1
            policy.reset_game()
            for t in range(1, len(steps) - 1):
                try:
                    if steps[t][pi].get("status") != "ACTIVE":
                        continue
                    od = steps[t][pi]["observation"]
                    if not od.get("select"):
                        continue
                    human = steps[t + 1][pi]["action"]
                    if not isinstance(human, list) or len(human) != 1:
                        continue
                    policy.decision_log.clear()
                    agent_mod.agent(od)
                    if len(policy.decision_log) != 1:
                        stats["no_record"] += 1     # R-01 フォールバック等
                        continue
                    rec = policy.decision_log[0]
                    cands = gate_candidates(rec)
                    if cands is None:
                        stats["gated_out"] += 1
                        continue
                    oi_list = [oi for oi, _s, _r in cands]
                    if human[0] not in oi_list:
                        stats["human_outside_cands"] += 1
                        continue
                    obs = to_observation_class(od)
                    if int(obs.select.context) != int(SelectContext.MAIN):
                        continue
                    X = pn.extract_features(obs, cands, {}, 0)   # 語彙なし（OOV 1枠）
                    X_rows.append(X.astype(np.float32))
                    k_arr.append(oi_list.index(human[0]))
                    reasons_flat.extend(r for _oi, _s, r in cands)
                    n_cands.append(len(cands))
                    meta_day.append(day)
                    meta_team.append(team)
                    meta_episode.append(Path(fp).stem)
                    stats["kept"] += 1
                except Exception:
                    stats["error"] += 1
                    continue

    if not X_rows:
        raise SystemExit(f"抽出0件（stats={dict(stats)}）")
    offsets = np.cumsum([0] + [x.shape[0] for x in X_rows])
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        X=np.concatenate(X_rows, axis=0),
        offsets=offsets.astype(np.int64),
        k=np.asarray(k_arr, dtype=np.int64),
        n_cands=np.asarray(n_cands, dtype=np.int64),
        reasons=np.asarray(reasons_flat, dtype="U"),
        day=np.asarray(meta_day, dtype="U"),
        team=np.asarray(meta_team, dtype="U"),
        episode=np.asarray(meta_episode, dtype="U"),
        n_state=np.array([pn.vm.N_FEATURES]),
        vm_feature_version=np.array([pn.vm.FEATURE_VERSION]),
        pn_version=np.array([pn.PN_VERSION]),
    )
    base_acc = float(np.mean(np.asarray(k_arr) == 0))
    print(f"games={games} kept={stats['kept']} decisions "
          f"(gated_out={stats['gated_out']}, human_outside={stats['human_outside_cands']}, "
          f"no_record={stats['no_record']}, error={stats['error']})")
    print(f"rule-argmax baseline agreement（k==0 率）= {base_acc:.1%}")
    print(f"saved -> {out}")


if __name__ == "__main__":
    main()
