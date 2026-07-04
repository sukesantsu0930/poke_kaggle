# 公式Visualizer Notebook

このフォルダは Kaggle 公式notebook のローカルコピーです。

```text
https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
```

## 何に使うか

対戦後に出力したリプレイJSONを、公式Visualizerで確認するために使います。
手動で1手ずつプレイする用途では、このプロジェクトの `run\03_play\GUI起動.bat` を使います。

## まず見るファイル

```text
how-to-output-local-battle-as-json-and-view.ipynb
```

この notebook に、リプレイJSONの作成例と、公式VisualizerにJSONを渡すHTML例が入っています。

## このプロジェクトでJSONを作る

プロジェクト直下で次を実行します。

```text
run\03_play\リプレイJSON作成.bat
```

出力先:

```text
experiments\visualizer\latest_replay.json
```

## Kaggleから取り直す場合

Kaggle API の認証が済んでいる状態で、プロジェクト直下から次を実行します。

```powershell
$env:KAGGLE_CONFIG_DIR = "$PWD\.kaggle"
$env:KAGGLE_API_TOKEN = Get-Content .kaggle\access_token
kaggle kernels pull kiyotah/how-to-output-local-battle-as-json-and-view -p notebooks\official_visualizer -m
```
