"""提出ごとの「1試合単位のスコア推移」を Kaggle Episodes API から取得する。

3時間毎スナップショット（scripts/log_ladder_scores.py → scores.csv）と違い、
これは**各対戦の initialScore→updatedScore を全部**返す（サイトの試合履歴の裏側 API）。
最新スコア=最後の試合の updatedScore。JS もタスクスケジューラも不要、既存トークンで叩く。

使い方:
  uv run python scripts/fetch_submission_history.py --refs 55157134 55176338
  uv run python scripts/fetch_submission_history.py --gen7            # gen7 5デッキを自動解決
  ... --dump-dir research/ladder/episode_hist   # 試合単位CSVも保存
"""
from __future__ import annotations
import argparse, csv, json, os
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://www.kaggle.com/api/i/competitions.EpisodeService/ListEpisodes"


def token() -> str:
    t = os.environ.get("KAGGLE_API_TOKEN")
    if not t:
        t = (ROOT / ".kaggle/access_token").read_text(encoding="utf-8").strip()
    return t


def ref_to_filename() -> dict[int, str]:
    m: dict[int, str] = {}
    p = ROOT / "research/ladder/scores.csv"
    if p.exists():
        for r in csv.DictReader(p.open(encoding="utf-8-sig")):
            try:
                m[int(r["ref"])] = r["fileName"]
            except (ValueError, KeyError):
                continue
    return m


def list_episodes(sub_id: int, tok: str) -> dict:
    r = requests.post(API, headers={"Authorization": f"Bearer {tok}",
                                    "Content-Type": "application/json"},
                      json={"submissionId": sub_id}, timeout=30)
    r.raise_for_status()
    return r.json()


def trajectory(j: dict, sub_id: int) -> list[dict]:
    """(endTime順) 自分側の updatedScore・reward・相手名 のリスト。"""
    team_name = {t["id"]: t.get("teamName", "?") for t in j.get("teams", [])}
    sub_team = {s["id"]: s.get("teamId") for s in j.get("submissions", [])}
    rows = []
    for ep in j.get("episodes", []):
        mine = next((a for a in ep["agents"] if a.get("submissionId") == sub_id), None)
        if mine is None or mine.get("updatedScore") is None:
            continue
        opp = next((a for a in ep["agents"] if a.get("submissionId") != sub_id), None)
        opp_name = team_name.get(sub_team.get(opp.get("submissionId")) if opp else None, "?")
        rows.append({"endTime": ep.get("endTime"), "reward": mine.get("reward"),
                     "score": mine.get("updatedScore"), "opponent": opp_name})
    rows.sort(key=lambda x: x["endTime"] or "")
    return rows


def summarize(label: str, rows: list[dict]) -> None:
    if not rows:
        print(f"{label:52} 試合0（未対戦 or 取得不可）")
        return
    scores = [r["score"] for r in rows]
    w = sum(1 for r in rows if (r["reward"] or 0) > 0)
    l = sum(1 for r in rows if (r["reward"] or 0) < 0)
    print(f"{label:52} n={len(rows):3d}  初={scores[0]:6.1f} 最新={scores[-1]:6.1f} "
          f"min={min(scores):6.1f} max={max(scores):6.1f}  {w}勝{l}敗")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", type=int, nargs="*", default=[])
    ap.add_argument("--gen7", action="store_true", help="scores.csv から gen7 提出refを解決")
    ap.add_argument("--dump-dir", default="")
    args = ap.parse_args()

    tok = token()
    fn = ref_to_filename()
    refs = list(args.refs)
    if args.gen7:
        refs += [ref for ref, name in fn.items() if "gen7" in name.lower()]
    refs = sorted(set(refs))
    if not refs:
        raise SystemExit("--refs か --gen7 を指定")

    for ref in refs:
        label = f"{ref} {fn.get(ref, '?')[:40]}"
        try:
            rows = trajectory(list_episodes(ref, tok), ref)
        except Exception as e:
            print(f"{label:52} ERR {type(e).__name__}: {str(e)[:80]}")
            continue
        summarize(label, rows)
        if args.dump_dir and rows:
            out = ROOT / args.dump_dir / f"{ref}.csv"
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("w", encoding="utf-8", newline="") as f:
                wri = csv.DictWriter(f, fieldnames=["endTime", "reward", "score", "opponent"])
                wri.writeheader(); wri.writerows(rows)


if __name__ == "__main__":
    main()
