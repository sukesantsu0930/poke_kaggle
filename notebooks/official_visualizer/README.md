# 公式Visualizer Notebook

このフォルダは Kaggle 公式 notebook のローカルコピーです。

```text
https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
```

## 何に使うか

対戦後に出力したリプレイ JSON を、公式 Visualizer で確認するために使います。

手動で 1 手ずつプレイする用途では、このプロジェクトの `GUI起動.bat` を使います。

## まず見るファイル

```text
how-to-output-local-battle-as-json-and-view.ipynb
```

この notebook に、リプレイ JSON の作成例と、公式 Visualizer に JSON を渡す HTML 例が入っています。

## このプロジェクトで JSON を作る

プロジェクト直下で次を実行します。

```text
リプレイJSON作成.bat
```

出力先:

```text
experiments\visualizer\latest_replay.json
```

## Kaggle から取り直す場合

Kaggle API の認証が済んでいる状態で、プロジェクト直下から次を実行します。

```powershell
$env:KAGGLE_CONFIG_DIR = "$PWD\.kaggle"
$env:KAGGLE_API_TOKEN = Get-Content .kaggle\access_token
kaggle kernels pull kiyotah/how-to-output-local-battle-as-json-and-view -p notebooks\official_visualizer -m
```

