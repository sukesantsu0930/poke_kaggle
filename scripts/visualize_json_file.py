"""既存の visualizer JSON ファイルを、公式ビジュアライザ（ptcgvis.heroz.jp）で開く。

対戦を新規生成する visualizer_workflow_server と違い、**手元の JSON ファイルそのもの**
（research/dusknoir_replays/*.json や experiments/visualizer/*.json、export_visualizer_json
の出力など）を1手ずつ再生する用途。

使い方:
  uv run python scripts/visualize_json_file.py research/dusknoir_replays/rebuilt_vs_marnie_seed1.json

内部で、公式ビジュアライザへ POST 送信する小さな HTML を生成してブラウザで開く
（visualizer_workflow_server.py と同じ hidden field "json" → Replay/0 の方式）。
"""
import json
import sys
import tempfile
import webbrowser
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("usage: visualize_json_file.py <path-to-visualizer-json>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"ファイルが見つかりません: {path}")
        sys.exit(1)
    text = path.read_text(encoding="utf-8")
    try:
        json.loads(text)   # 妥当性チェック（壊れた JSON を送らない）
    except Exception as exc:
        print(f"JSON として読めません: {path}\n  {exc}")
        sys.exit(1)

    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>PTCG Visualizer 送信</title></head><body>"
        "<p>公式ビジュアライザ（ptcgvis.heroz.jp）に送信します。"
        "別タブが開かない場合は下のボタンを押してください。</p>"
        "<form id='f' method='POST' target='_blank' "
        "action='https://ptcgvis.heroz.jp/Visualizer/Replay/0'>"
        "<input type='hidden' name='json' id='j'>"
        "<button type='submit'>Open in Visualizer</button></form>"
        "<p style='color:#666'>file: " + str(path) + "</p>"
        "<script>document.getElementById('j').value = "
        + json.dumps(text)
        + "; document.getElementById('f').submit();</script>"
        "</body></html>"
    )
    out = Path(tempfile.gettempdir()) / "ptcg_visualize_file.html"
    out.write_text(page, encoding="utf-8")
    webbrowser.open(out.as_uri())
    print(f"ブラウザで開きました（{out}）。別タブに公式ビジュアライザが出ます。")


if __name__ == "__main__":
    main()
