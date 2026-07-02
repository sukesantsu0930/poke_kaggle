import argparse
import json
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from export_visualizer_json import load_agent, read_deck, run_game  # noqa: E402


DEFAULT_AGENT = "agents/cubchoo_ogerpon_rb"
DEFAULT_DECK = "decks/candidates/2026-06-30_top5/winrate_1_cubchoo_ogerpon.csv"
DEFAULT_OUTPUT = "experiments/visualizer/latest_replay.json"
DEFAULT_AGENT_LOG = "experiments/visualizer/latest_agent_log.json"


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_inside_root(path: Path) -> bool:
    try:
        path.resolve().relative_to(ROOT.resolve())
        return True
    except ValueError:
        return False


def resolve_workspace_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    if not is_inside_root(path):
        raise ValueError(f"workspace外のパスは使えません: {value}")
    return path


def discover_agents() -> list[str]:
    agents = []
    agent_root = ROOT / "agents"
    for path in sorted(agent_root.iterdir()):
        if path.is_dir() and (path / "main.py").exists():
            agents.append(rel(path))
        elif path.is_file() and path.suffix == ".py" and path.name != "__init__.py" and "template" not in path.stem:
            agents.append(rel(path))
    return agents


def discover_decks() -> list[str]:
    return [rel(path) for path in sorted((ROOT / "decks").rglob("*.csv"))]


def generate_replay(config: dict) -> dict:
    agent0 = config.get("agent0") or DEFAULT_AGENT
    deck0_path = config.get("deck0") or DEFAULT_DECK
    agent1 = config.get("agent1") or DEFAULT_AGENT
    deck1_path = config.get("deck1") or DEFAULT_DECK
    seed = int(config.get("seed") or 0)
    max_steps = int(config.get("maxSteps") or 1000)

    random.seed(seed)
    suffix = str(int(time.time() * 1000))
    agent0_module = load_agent(resolve_workspace_path(agent0), f"visualizer_agent0_{suffix}")
    agent1_module = load_agent(resolve_workspace_path(agent1), f"visualizer_agent1_{suffix}")
    deck0 = read_deck(resolve_workspace_path(deck0_path))
    deck1 = read_deck(resolve_workspace_path(deck1_path))

    visualizer_payload, meta, action_log = run_game(agent0_module, agent1_module, deck0, deck1, max_steps)

    output_path = resolve_workspace_path(DEFAULT_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(visualizer_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    agent_log_path = resolve_workspace_path(DEFAULT_AGENT_LOG)
    agent_log_path.parent.mkdir(parents=True, exist_ok=True)
    agent_log_path.write_text(json.dumps(action_log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "meta": meta,
        "output": rel(output_path),
        "agentLog": rel(agent_log_path),
        "visualizer": visualizer_payload,
    }


HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Replay JSON / Official Visualizer</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      margin: 24px;
      line-height: 1.5;
      color: #222;
    }
    h1 {
      font-size: 22px;
      margin: 0 0 16px;
    }
    .grid {
      display: grid;
      grid-template-columns: 160px minmax(320px, 760px);
      gap: 10px 12px;
      align-items: center;
    }
    label {
      font-weight: bold;
    }
    select, input {
      width: 100%;
      box-sizing: border-box;
      padding: 8px;
      font-size: 14px;
    }
    .actions {
      display: flex;
      gap: 10px;
      margin-top: 18px;
      flex-wrap: wrap;
    }
    button {
      font-size: 15px;
      padding: 10px 18px;
      cursor: pointer;
    }
    button:disabled {
      opacity: 0.5;
      cursor: not-allowed;
    }
    #status {
      margin-top: 14px;
      font-weight: bold;
      white-space: pre-wrap;
    }
    .ok {
      color: #116b2f;
    }
    .error {
      color: #a40000;
    }
    .path {
      font-family: Consolas, monospace;
    }
  </style>
</head>
<body>
  <h1>Replay JSON / Official Visualizer</h1>

  <div class="grid">
    <label for="agent0">Agent 0</label>
    <select id="agent0"></select>

    <label for="deck0">Deck 0</label>
    <select id="deck0"></select>

    <label for="agent1">Agent 1</label>
    <select id="agent1"></select>

    <label for="deck1">Deck 1</label>
    <select id="deck1"></select>

    <label for="seed">Seed</label>
    <input id="seed" type="number" value="0" min="0" step="1">

    <label for="maxSteps">Max steps</label>
    <input id="maxSteps" type="number" value="1000" min="1" step="1">
  </div>

  <div class="actions">
    <button id="generateButton" type="button">Generate Replay JSON</button>
    <button id="openButton" type="button" disabled>Open Official Visualizer</button>
  </div>

  <div id="status">Loading options...</div>

  <script>
    let visualizerJson = "";
    const ids = ["agent0", "deck0", "agent1", "deck1"];
    const status = document.getElementById("status");
    const generateButton = document.getElementById("generateButton");
    const openButton = document.getElementById("openButton");

    function setStatus(message, className) {
      status.textContent = message;
      status.className = className || "";
    }

    function fillSelect(id, values, preferred) {
      const select = document.getElementById(id);
      select.innerHTML = "";
      values.forEach(value => {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        if (value === preferred) {
          option.selected = true;
        }
        select.appendChild(option);
      });
    }

    async function loadOptions() {
      const res = await fetch("/api/options");
      const data = await res.json();
      fillSelect("agent0", data.agents, data.defaults.agent);
      fillSelect("agent1", data.agents, data.defaults.agent);
      fillSelect("deck0", data.decks, data.defaults.deck);
      fillSelect("deck1", data.decks, data.defaults.deck);
      setStatus("Select agents/decks, then generate replay JSON.", "");
    }

    async function generate() {
      visualizerJson = "";
      openButton.disabled = true;
      generateButton.disabled = true;
      setStatus("Generating replay JSON...", "");

      const payload = {
        agent0: document.getElementById("agent0").value,
        deck0: document.getElementById("deck0").value,
        agent1: document.getElementById("agent1").value,
        deck1: document.getElementById("deck1").value,
        seed: document.getElementById("seed").value,
        maxSteps: document.getElementById("maxSteps").value,
      };

      try {
        const res = await fetch("/api/generate", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "generation failed");
        }
        visualizerJson = JSON.stringify(data.visualizer);
        openButton.disabled = false;
        setStatus(
          "DONE\n" +
          "Replay: " + data.output + "\n" +
          "Agent log: " + data.agentLog + "\n" +
          "Result: " + data.meta.result + " / Steps: " + data.meta.steps,
          "ok"
        );
      } catch (error) {
        setStatus("ERROR: " + error.message, "error");
      } finally {
        generateButton.disabled = false;
      }
    }

    function openOfficialVisualizer() {
      if (!visualizerJson) {
        setStatus("ERROR: Generate replay JSON first.", "error");
        return;
      }

      const input = document.createElement("input");
      input.type = "hidden";
      input.name = "json";
      input.value = visualizerJson;

      const form = document.createElement("form");
      form.method = "POST";
      form.action = "https://ptcgvis.heroz.jp/Visualizer/Replay/0";
      form.target = "_blank";
      form.appendChild(input);

      document.body.appendChild(form);
      form.submit();
      form.remove();
    }

    generateButton.addEventListener("click", generate);
    openButton.addEventListener("click", openOfficialVisualizer);

    loadOptions().catch(error => setStatus("ERROR: " + error.message, "error"));
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_bytes(HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif parsed.path == "/api/options":
            self.send_json(
                {
                    "agents": discover_agents(),
                    "decks": discover_decks(),
                    "defaults": {"agent": DEFAULT_AGENT, "deck": DEFAULT_DECK},
                }
            )
        else:
            self.send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/generate":
            self.send_json({"ok": False, "error": "not found"}, status=404)
            return
        try:
            body = self.read_json()
            self.send_json(generate_replay(body))
        except Exception as exc:
            self.send_json({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, status=400)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def send_json(self, value, status=200):
        self.send_bytes(json.dumps(value, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8", status)

    def send_bytes(self, data: bytes, content_type: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        print(format % args)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Replay visualizer workflow: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
