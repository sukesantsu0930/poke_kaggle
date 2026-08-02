"""版非互換の2つの提出zipを直接対戦させる（各エージェントを別プロセスに隔離）。

同名モジュール(meta_tables/policy_base/policy_net)の別バージョンは1プロセスに同居できない
ため、各zipを展開して _spar_bridge.py の別プロセスでホストし、cabt審判(make("cabt"))から
obs→action をJSONで橋渡しする。座席は毎試合入替（先攻補正）。

使い方:
  uv run python scripts/spar_two_zips.py --a <zipA> --b <zipB> --games 40
"""
import argparse, json, os, subprocess, sys, tempfile, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Bridge:
    def __init__(self, agent_dir: Path, label: str):
        self.label = label
        self.p = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts/_spar_bridge.py"), str(agent_dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1)
        while True:
            line = self.p.stderr.readline()
            if not line:
                raise RuntimeError(f"[{label}] bridge died before READY")
            if "READY" in line:
                break

    def act(self, obs):
        self.p.stdin.write(json.dumps(obs, default=lambda o: dict(o) if hasattr(o, "keys") else o) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        if not line:
            raise RuntimeError(f"[{self.label}] bridge died mid-game")
        return json.loads(line)

    def close(self):
        try:
            self.p.terminate()
        except Exception:
            pass


def fn_of(bridge):
    def fn(obs):
        return bridge.act(obs)
    return fn


def extract(zip_path: Path, dest: Path) -> Path:
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="zip A（例: 現行gen7）")
    ap.add_argument("--b", required=True, help="zip B（例: 915）")
    ap.add_argument("--games", type=int, default=40)
    args = ap.parse_args()

    from kaggle_environments import make

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        dirA = extract(ROOT / args.a, Path(td) / "A")
        dirB = extract(ROOT / args.b, Path(td) / "B")
        A = Bridge(dirA, "A"); B = Bridge(dirB, "B")
        fnA, fnB = fn_of(A), fn_of(B)

        aw = bw = draw = err = 0
        for g in range(args.games):
            swap = (g % 2 == 1)  # 毎試合 座席入替
            agents = [fnB, fnA] if swap else [fnA, fnB]
            env = make("cabt", debug=False)
            try:
                env.run(agents)
                r = [s.reward for s in env.state]
                st = [s.status for s in env.state]
            except Exception as e:
                err += 1; print(f"  game {g}: ENV_ERR {type(e).__name__}: {str(e)[:80]}"); continue
            # A の席 index
            ai = 1 if swap else 0
            ra = r[ai]
            if ra is None or "DONE" not in st:
                err += 1
            elif ra > 0:
                aw += 1
            elif ra < 0:
                bw += 1
            else:
                draw += 1
            if (g + 1) % 5 == 0:
                print(f"  {g+1}/{args.games}: A {aw}-{bw} B (draw {draw}, err {err})", flush=True)

        A.close(); B.close()
        n = aw + bw
        print(f"\n=== 結果（{args.games}戦, 座席入替あり）===")
        print(f"A ({Path(args.a).name})")
        print(f"B ({Path(args.b).name})")
        print(f"A {aw}勝 - {bw}勝 B  引分{draw} エラー{err}")
        if n:
            print(f"A 勝率: {100*aw/n:.1f}%")


if __name__ == "__main__":
    main()
