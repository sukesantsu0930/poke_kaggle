# Kaggleデータ取得手順

各メンバーはKaggleでCompetition rulesを承認してから実行してください。

`API.txt` は共有しません。各自のKaggle API tokenを使います。

```powershell
$env:KAGGLE_API_TOKEN = "<自分のKaggle API token>"
$env:KAGGLE_CONFIG_DIR = ".kaggle"
kaggle competitions download -c pokemon-tcg-ai-battle -p downloads\simulation --force
Expand-Archive downloads\simulation\pokemon-tcg-ai-battle.zip -DestinationPath downloads\simulation\extracted -Force
Copy-Item downloads\simulation\extracted\sample_submission\sample_submission\* submission -Recurse -Force
```

取得後、次でデッキ検証や公式Visualizer用JSON出力が使えます。

```powershell
python scripts\check_decks.py
python scripts\export_visualizer_json.py --output experiments\visualizer\latest_replay.json
```
