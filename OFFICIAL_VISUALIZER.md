# 公式Visualizerメモ

公式Visualizerは、対戦後のリプレイJSONを見るためのものです。

手動で1手ずつ操作してデッキを試す用途では、引き続きこのプロジェクトの手動GUIを使います。

## 公式Notebook

```text
https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
```

ローカルコピー:

```text
notebooks\official_visualizer\how-to-output-local-battle-as-json-and-view.ipynb
```

フォルダを開く:

```text
run\公式Visualizerフォルダを開く.bat
```

## ローカル対戦JSONを作る

```text
run\リプレイJSON作成.bat
```

または:

```powershell
python scripts\export_visualizer_json.py --output experiments\visualizer\latest_replay.json
```

出力先:

```text
experiments\visualizer\latest_replay.json
```

## 使い分け

- 手動でデッキを試す: `run\GUI起動.bat`
- AI同士またはAgent対Randomのリプレイを見る: `run\リプレイJSON作成.bat` -> 公式Visualizer

非公式Replay Viewerとして公開・配布する用途では使わない。
