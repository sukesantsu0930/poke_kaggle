# 学習コード置き場

学習用コードをここに置きます。**現状は未実装**（構想のみ）。

実装するときの推奨する分け方:

- `training/train_policy.py`: 学習の入口
- `training/features.py`: 特徴量抽出
- `training/evaluate_policy.py`: オフライン評価

学習済みパラメータは `submission/` ではなく `models/` に出力してください。

Kaggle提出zipには、推論時に必要なファイルだけを入れます。

- `main.py`
- `deck.csv`
- `cg/`
- `--extra` で追加した `models/` 内のファイルや補助モジュール
