# 学習済みモデル置き場

学習済みモデルや推論用の設定ファイルをここに置きます。**現状は空**（学習パイプライン未整備）。

置くときのファイル名の例:

- `policy_v001.pkl`
- `policy_v001.joblib`
- `policy_v001.npz`
- `policy_v001_config.json`

モデル本体はGit管理から除外しています。Kaggle提出zipに入れる場合は `--extra` を使います。

例:

```powershell
uv run python scripts\build_submission.py --agent agents\ml_agent_v001.py --deck decks\deck_v001.csv --extra models\policy_v001.pkl
```

エージェント側で固定ファイル名を期待する場合は `SRC=DEST` 形式を使います。

```powershell
uv run python scripts\build_submission.py --agent agents\ml_agent_v001.py --deck decks\deck_v001.csv --extra models\policy_v001.pkl=model.pkl
```
