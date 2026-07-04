# 公式Visualizerメモ

公式Visualizerは、対戦後のリプレイJSONを見るためのものです。
手動で1手ずつ操作してデッキを試す用途では、プロジェクト内の手動GUIを使います。

## 公式Notebook

```text
https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
```

ローカルコピー:

```text
notebooks\official_visualizer\how-to-output-local-battle-as-json-and-view.ipynb
```

## 統合画面を開く

```text
run\03_play\公式Visualizerフォルダを開く.bat
```

この bat はローカル画面を開きます。画面上で Agent 0 / Deck 0 / Agent 1 / Deck 1 を選び、リプレイJSONを生成してから公式Visualizerを開きます。

## ローカル対戦JSONを作る

```text
run\03_play\リプレイJSON作成.bat
```

または:

```powershell
uv run python scripts\export_visualizer_json.py --agent0 agents\cubchoo_ogerpon_rb --deck0 decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv --agent1 agents\cubchoo_ogerpon_rb --deck1 decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv --output experiments\visualizer\latest_replay.json
```

出力先:

```text
experiments\visualizer\latest_replay.json
experiments\visualizer\latest_agent_log.json
```

`latest_replay.json` は公式Visualizer用です。
`latest_agent_log.json` は、P0/P1 の各ステップで選択肢一覧と選択結果を確認するためのローカル調査用ログです。

## 使い分け

- 手動でデッキを試す: `run\03_play\GUI起動.bat`
- AI同士のリプレイを見る: `run\03_play\リプレイJSON作成.bat` -> 公式Visualizer
- 画面から生成と表示をまとめて行う: `run\03_play\公式Visualizerフォルダを開く.bat`

非公式Replay Viewerとして公開・配布する用途では使いません。
