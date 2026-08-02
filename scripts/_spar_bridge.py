"""別プロセスでエージェント1体を隔離ホストする（版非互換のzip同士を戦わせる用）。
argv[1]=展開済みエージェントdir。CWDをそこに移し（deck.csv相対読み）、main.py を
importして `agent(obs)->action` を stdin/stdout(JSON1行) で応答する。
標準出力はJSON応答専用にし、エージェントの print は stderr へ逃がす。
"""
import sys, os, json, importlib.util

agent_dir = os.path.abspath(sys.argv[1])
os.chdir(agent_dir)
sys.path.insert(0, agent_dir)

_real_stdout = sys.stdout
sys.stdout = sys.stderr  # import時/agent実行時の print を汚染源にしない

spec = importlib.util.spec_from_file_location("spar_agent_main", os.path.join(agent_dir, "main.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
agent = mod.agent

sys.stderr.write("READY\n"); sys.stderr.flush()

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    obs = json.loads(line)
    try:
        act = agent(obs)
    except Exception as e:
        sys.stderr.write(f"AGENT_ERR {type(e).__name__}: {e}\n"); sys.stderr.flush()
        act = None
    _real_stdout.write(json.dumps(act) + "\n"); _real_stdout.flush()
