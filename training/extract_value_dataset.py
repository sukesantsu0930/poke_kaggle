"""V(s)/脅威分類器の訓練データ抽出 — エピソード → (特徴量, ラベル) の npz。

エピソード（downloads/episodes/<day>/*.json）は両プレイヤーの観測列と最終 reward を持つ。
各ステップ × 各プレイヤー視点を1行とし、特徴量は agents/_base/value_model.py の
extract_features を**そのまま**使う（train/serve skew の排除）。

ラベル:
  y_win    = その視点プレイヤーが最終的に勝ったか（V(s) の教師。引き分けは行ごと除外）
  y_threat = 相手の残りサイドが「今から2プレイヤーターン以内」に減ったか
             （= この盤面を渡すと直近で1枚以上取られる。脅威分類器の教師）

出力: data/value/<day>.npz  (X, y_win, y_threat, episode_id, turn, to_move)
      data/ は gitignore 済み。抽出をやり直すには npz を消して再実行。

使い方:
  uv run python training/extract_value_dataset.py [--days 2026-07-07,2026-07-06]
      [--episodes-root downloads/episodes] [--out-root data/value] [--max-episodes N]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))
sys.path.insert(0, str(ROOT / "agents" / "_base"))

from cg import api  # noqa: E402
import value_model as vm  # noqa: E402


def episode_rows(ep_path: Path):
    """1エピソード → 行のリスト。壊れたエピソードは空を返す。"""
    try:
        ep = json.loads(ep_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rewards = ep.get("rewards") or []
    if (len(rewards) != 2 or any(r is None for r in rewards)
            or rewards[0] == rewards[1]):
        return []                          # 引き分け・エラー対局（None）・異常は除外
    winner = 0 if rewards[0] > rewards[1] else 1
    steps = ep.get("steps") or []
    # episode id は UUID のことがある → ファイル名 or id 文字列のハッシュで安定 int 化
    raw_id = str(ep.get("id") or ep_path.stem)
    try:
        ep_id = int(raw_id)
    except ValueError:
        import hashlib
        ep_id = int(hashlib.sha256(raw_id.encode()).hexdigest()[:15], 16)

    parsed = []                            # [(step_idx, player, typed_obs)]
    for si, step in enumerate(steps):
        for p in (0, 1):
            try:
                obs_dict = step[p].get("observation")
                if not obs_dict or obs_dict.get("current") is None:
                    continue
                typed = api.to_observation_class(obs_dict)
            except Exception:
                continue
            parsed.append((si, p, typed))

    rows = []
    for k, (si, p, typed) in enumerate(parsed):
        st = typed.current
        if st is None:
            continue
        try:
            x = vm.extract_features(typed, p)
        except Exception:
            continue
        # 脅威ラベル: 相手の残りサイドが2プレイヤーターン以内に減るか
        base_opp_prize = len(st.players[1 - p].prize)
        horizon_turn = st.turn + 2
        threat = 0
        for si2, p2, typed2 in parsed[k + 1:]:
            st2 = typed2.current
            if st2 is None or st2.turn > horizon_turn:
                break
            if len(st2.players[1 - p].prize) < base_opp_prize:
                threat = 1
                break
        rows.append((x, 1 if winner == p else 0, threat, ep_id, st.turn,
                     1 if st.yourIndex == p else 0))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes-root", default="downloads/episodes")
    parser.add_argument("--days", help="カンマ区切り（省略時は全日次dir）")
    parser.add_argument("--out-root", default="data/value")
    parser.add_argument("--max-episodes", type=int, help="日次あたりの上限（デバッグ用）")
    args = parser.parse_args()

    ep_root = ROOT / args.episodes_root
    days = (args.days.split(",") if args.days
            else sorted(d.name for d in ep_root.iterdir() if d.is_dir()))
    out_root = ROOT / args.out_root
    out_root.mkdir(parents=True, exist_ok=True)

    for day in days:
        day_dir = ep_root / day.strip()
        if not day_dir.is_dir():
            print(f"SKIP {day}: not found")
            continue
        out = out_root / f"{day.strip()}.npz"
        if out.exists():
            print(f"skip {day} (exists: {out.name})")
            continue
        files = sorted(day_dir.glob("*.json"))
        if args.max_episodes:
            files = files[:args.max_episodes]
        X, yw, yt, eid, turn, tomove = [], [], [], [], [], []
        for i, f in enumerate(files):
            for x, w, t, e, tn, tm in episode_rows(f):
                X.append(x); yw.append(w); yt.append(t)
                eid.append(e); turn.append(tn); tomove.append(tm)
            if (i + 1) % 50 == 0:
                print(f"  {day}: {i+1}/{len(files)} episodes, {len(X)} rows")
        if not X:
            print(f"SKIP {day}: no rows")
            continue
        np.savez_compressed(
            out,
            X=np.stack(X).astype(np.float32),
            y_win=np.array(yw, dtype=np.int8),
            y_threat=np.array(yt, dtype=np.int8),
            episode_id=np.array(eid, dtype=np.int64),
            turn=np.array(turn, dtype=np.int16),
            to_move=np.array(tomove, dtype=np.int8),
            feature_version=np.array([vm.FEATURE_VERSION]),
        )
        print(f"wrote {out} ({len(X)} rows from {len(files)} episodes, "
              f"win率 {np.mean(yw):.3f} / threat率 {np.mean(yt):.3f})")


if __name__ == "__main__":
    main()
