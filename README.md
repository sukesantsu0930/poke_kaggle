# PTCG Kaggle作業場

ポケモンカードAI Battle Challenge用の作業場です。

## 共同作業で見るファイル

まず読む:

- `COLLABORATION_GUIDE.md`
- `GIT_MINIMUM.md`

デッキ案:

- `decks/`
- `research/deck_notes/`

ストラテジー・ルール研究:

- `research/strategy_notes/`
- `research/rule_findings/`
- `research/card_notes/`

評価結果:

- `experiments/`

## 実装担当が見るファイル

- `agents/`
- `scripts/`
- `submission/`
- `models/`
- `training/`
- `docker/`

## 注意

- `API.txt` は認証情報なので共有しない
- `downloads/`, `models/`, `submissions/`, `build/` は生成物なので基本的にGit管理しない
- 初心者メンバーは `decks/` と `research/` を中心に編集する。デッキCSV作成まで担当する

## 評価方法

全組み合わせを評価:

```bash
python scripts/batch_evaluate.py --games 50 --seed 1
```

特定の組み合わせを評価:

```bash
python scripts/batch_evaluate.py --agent agents/rb_001_baseline.py --deck decks/deck_001_sample.csv --games 100
```

## 手動プレイGUI

両プレイヤーを自分で操作して、デッキの動きを確認できます。

```bash
python scripts/manual_play_server.py --port 8765
```

起動後、ブラウザで開きます。

```text
http://127.0.0.1:8765
```

## デッキ検証

`decks/` 内のCSVを検証します。

```bash
python scripts/check_decks.py
```

## 提出zip作成

```bash
python scripts/build_submission.py --agent agents/rb_001_baseline.py --deck decks/deck_001_sample.csv
```
