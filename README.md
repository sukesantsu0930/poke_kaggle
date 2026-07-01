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
- 初心者メンバーは Git から最新版を取り、公式サイトでデッキを作る
- デッキコードを `デッキコード登録.bat` に入れて、`OK` なら公式Visualizer用リプレイで確認する
- 良いデッキができたら、デッキコードを助友に直接送る

## 評価方法

全組み合わせを評価:

```bash
python scripts/batch_evaluate.py --games 50 --seed 1
```

特定の組み合わせを評価:

```bash
python scripts/batch_evaluate.py --agent agents/rb_001_baseline.py --deck decks/deck_001_sample.csv --games 100
```

## 公式Visualizer

競技運営から、非公式Replay Viewerは規約違反という案内が出ています。対戦の確認は公式Visualizerに統一します。

公式Notebook:

```text
https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
```

ローカル対戦JSONを作成:

```text
リプレイJSON作成.bat
```

実装担当向け:

```bash
python scripts/export_visualizer_json.py --output experiments/visualizer/latest_replay.json
```

`scripts/manual_play_server.py` は公式Viewerの代替として使いません。必要な場合も内部確認用に限定します。

## デッキ検証

`decks/` 内のコンパイル済みCSVを検証します。

```bash
python scripts/check_decks.py
```

公式デッキコードをCSVへ変換します。変換・検証に通った場合だけ `decks/local/` にCSVが出力され、ローカル評価やリプレイJSON作成で使えます。

友人向け:

```text
デッキコード登録.bat
```

実装担当向け:

```bash
python scripts/import_deck_code.py 4GGxYc-KmW2Iv-8c4c8c
```

## 提出zip作成

```bash
python scripts/build_submission.py --agent agents/rb_001_baseline.py --deck decks/deck_001_sample.csv
```
