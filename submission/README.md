# Kaggle提出テンプレート（エンジン置き場 + デフォルト入力）

このフォルダは、Kaggle Simulationの `sample_submission` を展開して使う場所です。

役割は2つです。

1. ゲームエンジン `cg/` の置き場。各スクリプト（`build_submission.py`、`evaluate_submission.py`、`manual_play_server.py` など）はここの `cg/` を参照します。
2. `main.py` と `deck.csv` は各スクリプトの「デフォルト入力」。実際の提出は `agents/` + `decks/` の組み合わせを `scripts\build_submission.py`（または `run/06_submit/提出.bat`）で指定して作ります。

ここにある `main.py` は汎用ベースライン（`agents/rb_001_baseline.py` と同一）、`deck.csv` はサンプルデッキ（`decks/deck_001_sample.csv` と同一）のまま維持します。**現在の提出内容を表すものではありません**（提出記録は `submissions/<日付>/` を参照）。

競技データや `cg` ライブラリ本体はGitHubに上げません。

初回セットアップでは、Kaggle APIでデータを取得し、`submission/cg/` と `submission/deck.csv` を復元してください。

ローカルで既に取得済みの場合は、このフォルダには以下が存在します。

- `main.py`
- `deck.csv`
- `cg/`

