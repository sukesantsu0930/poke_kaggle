"""提出前の最終ゲート — Kaggle の検証エピソードをローカルで忠実に再現する。

kaggle_environments の make('cabt') で「提出物 vs 自分ミラー」を1戦回す。
これは Kaggle が提出直後に行う Validation Episode と同じ経路（エージェントのロードも
get_last_callable = 「main.py の最後の callable」方式）なので、
evaluate_submission.py（cg 直叩き）では見えないローダー起因の事故（R-25 等）を検出できる。

使い方:
  uv run python scripts\\validate_episode.py --zip submissions\\2026-07-06\\xxx.zip
  uv run python scripts\\validate_episode.py --dir build\\submission_work

exit 0 = 検証合格（両者 DONE）/ 1 = INVALID/ERROR/TIMEOUT あり
"""
import argparse
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate(work_dir: Path) -> bool:
    from kaggle_environments import make

    main_py = work_dir / "main.py"
    if not main_py.exists():
        print(f"NG main.py not found in {work_dir}")
        return False
    # Kaggle 実行時は /kaggle_simulations/agent/deck.csv が読めるが、ローカルでは
    # CWD を提出物dirに合わせて deck.csv の相対読みを成立させる
    prev_cwd = os.getcwd()
    os.chdir(work_dir)
    try:
        env = make("cabt", debug=True)
        env.run([str(main_py), str(main_py)])
        statuses = [s.status for s in env.state]
        rewards = [s.reward for s in env.state]
        steps = len(env.steps)
    finally:
        os.chdir(prev_cwd)
    ok = all(st == "DONE" for st in statuses)
    print(f"statuses={statuses} rewards={rewards} steps={steps}")
    print("OK validation episode passed" if ok else "NG validation episode FAILED (Kaggle でも失敗する)")
    return ok


def main():
    parser = argparse.ArgumentParser()
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--zip", help="提出zipを展開して検証")
    g.add_argument("--dir", help="ビルド済みディレクトリを検証")
    args = parser.parse_args()

    if args.dir:
        ok = validate(ROOT / args.dir)
    else:
        # ignore_cleanup_errors: Windows では cg.dll がプロセス終了までロックされ
        # 削除に失敗する（検証結果とは無関係なので exit code を汚さない）
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
            work = Path(td) / "sub"
            with zipfile.ZipFile(ROOT / args.zip) as zf:
                zf.extractall(work)
            ok = validate(work)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
