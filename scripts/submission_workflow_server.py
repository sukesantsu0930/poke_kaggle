import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from prepare_submission import DEFAULT_AGENT, DEFAULT_DECK, DEFAULT_MESSAGE, prepare_submission  # noqa: E402
from visualizer_workflow_server import discover_agents, discover_decks  # noqa: E402


HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Submission Zip Builder</title>
  <style>
    body {
      color: #222;
      font-family: Arial, sans-serif;
      line-height: 1.5;
      margin: 24px;
    }
    h1 {
      font-size: 22px;
      margin: 0 0 16px;
    }
    .grid {
      align-items: center;
      display: grid;
      gap: 10px 12px;
      grid-template-columns: 140px minmax(320px, 760px);
    }
    label {
      font-weight: bold;
    }
    select, input {
      box-sizing: border-box;
      font-size: 14px;
      padding: 8px;
      width: 100%;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }
    button {
      cursor: pointer;
      font-size: 15px;
      padding: 10px 18px;
    }
    button:disabled {
      cursor: not-allowed;
      opacity: 0.5;
    }
    #status {
      font-weight: bold;
      margin-top: 14px;
      white-space: pre-wrap;
    }
    .ok {
      color: #116b2f;
    }
    .error {
      color: #a40000;
    }
    .warn {
      color: #8a5a00;
    }
  </style>
</head>
<body>
  <h1>Submission Zip Builder</h1>

  <div class="grid">
    <label for="agent">Agent</label>
    <select id="agent"></select>

    <label for="deck">Deck</label>
    <select id="deck"></select>

    <label for="message">Message</label>
    <input id="message" type="text">
  </div>

  <div class="actions">
    <button id="buildButton" type="button">Build Zip</button>
  </div>

  <div id="status">Loading options...</div>

  <script>
    const status = document.getElementById("status");
    const buildButton = document.getElementById("buildButton");

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
      fillSelect("agent", data.agents, data.defaults.agent);
      fillSelect("deck", data.decks, data.defaults.deck);
      document.getElementById("message").value = data.defaults.message;
      setStatus("Select agent/deck, then build zip.", "");
    }

    async function buildZip() {
      buildButton.disabled = true;
      setStatus("Building submission zip...", "");

      const payload = {
        agent: document.getElementById("agent").value,
        deck: document.getElementById("deck").value,
        message: document.getElementById("message").value,
      };

      try {
        const res = await fetch("/api/build", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok || !data.ok) {
          throw new Error(data.error || "build failed");
        }
        setStatus(
          "DONE\n" +
          "Zip: " + data.zip_relative + "\n" +
          "\n" +
          "Submit manually on Kaggle.\n" +
          "If using CLI manually, run:\n" +
          data.submit_command.join(" "),
          "ok"
        );
      } catch (error) {
        setStatus("ERROR: " + error.message, "error");
      } finally {
        buildButton.disabled = false;
      }
    }

    buildButton.addEventListener("click", buildZip);
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
                    "defaults": {
                        "agent": DEFAULT_AGENT,
                        "deck": DEFAULT_DECK,
                        "message": DEFAULT_MESSAGE,
                    },
                }
            )
        else:
            self.send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            body = self.read_json()
            if parsed.path == "/api/build":
                prepared = prepare_submission(
                    body.get("agent") or DEFAULT_AGENT,
                    body.get("deck") or DEFAULT_DECK,
                    body.get("message") or DEFAULT_MESSAGE,
                )
                self.send_json({"ok": True, **prepared})
                return
            self.send_json({"ok": False, "error": "not found"}, status=404)
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
    parser.add_argument("--port", type=int, default=8767)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Submission zip builder: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
