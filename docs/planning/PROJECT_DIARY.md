# プロジェクト日記

このファイルは、次回作業を再開するときのための引き継ぎメモです。

毎回ディレクトリ全体を走査しなくても、まずここを読めば状況が分かるようにします。

## 2026-07-01

### 今日決めたこと

- 競技の中心タスクは「デッキ構築」と「エージェント開発」。
- ユーザー本人がデッキ構築とエージェント方針を主導する。
- Codex側は、提出準備、評価、集計、Docker/GPU環境、共同作業の土台、ドキュメント整備を担当する。
- 友人の安福・長谷川には、IT/AIの知識を前提にせず、公式サイトでのデッキ作成・カード調査・ストラテジー研究・ルール発見をお願いする。
- `docs/official/Competition_Rules.md` はKaggle公式ルール原文なので、英語のまま保持する。翻訳や要約で上書きしない。

### 今日作った土台

- Kaggle APIでSimulation側ファイルを取得した。
- `submission/` にKaggleサンプル提出一式を展開した。
- `agents/` と `decks/` を作り、複数エージェント・複数デッキを管理できるようにした。
- `scripts/build_submission.py` を作り、任意のAgentとDeckから提出zipを作れるようにした。
- `scripts/evaluate_submission.py` を作り、ローカル評価できるようにした。
- `scripts/batch_evaluate.py` を作り、複数Agentと複数Deckの組み合わせ評価をCSV出力できるようにした。
- `scripts/manual_play_server.py` を作り、両プレイヤーを人間が操作する手動プレイGUIを起動できるようにした。
- `scripts/export_visualizer_json.py` を作り、公式Visualizer用のローカル対戦JSONも出力できるようにした。
- `scripts/deck_validation.py` と `scripts/check_decks.py` を作り、デッキCSVの検証を共通化した。
- `scripts/import_deck_code.py` を作り、公式デッキコードを取得・変換・検証し、通ったものだけCSVへ出力する方式にした。
- `models/` と `training/` を作り、将来の機械学習Agent用の受け皿を用意した。
- Docker/GPUサーバー用に `Dockerfile`, `docker-compose.yml`, `docker/README.md` を追加した。
- 共同作業用に `README.md`, `docs/collaboration/COLLABORATION_GUIDE.md`, `docs/collaboration/GIT_MINIMUM.md`, `docs/collaboration/安福_長谷川向け.md` を作った。
- `research/` 配下に、デッキ研究・カード研究・戦略研究・ルール発見用のテンプレートを作った。

### 重要なファイル

- 公式ルール原文: `docs/official/Competition_Rules.md`
- 共同作業入口: `README.md`
- 友人向け案内: `docs/collaboration/安福_長谷川向け.md`
- 最低限Git説明: `docs/collaboration/GIT_MINIMUM.md`
- 共同作業ルール: `docs/collaboration/COLLABORATION_GUIDE.md`
- エージェント置き場: `agents/`
- デッキ置き場: `decks/`
- 研究メモ置き場: `research/`
- 実験結果置き場: `experiments/`
- 提出zip作成: `scripts/build_submission.py`
- バッチ評価: `scripts/batch_evaluate.py`
- 手動プレイGUI: `scripts/manual_play_server.py`
- 公式Visualizer用JSON出力: `scripts/export_visualizer_json.py`
- デッキ検証: `scripts/check_decks.py`
- Docker/GPU手順: `docker/README.md`

### 使うコマンド

特定のAgentとDeckを評価:

```powershell
uv run python scripts\batch_evaluate.py --agent agents\rb_001_baseline.py --deck decks\deck_001_sample.csv --games 50 --seed 1
```

全組み合わせを評価:

```powershell
uv run python scripts\batch_evaluate.py --games 50 --seed 1
```

提出zip作成:

```powershell
uv run python scripts\build_submission.py --agent agents\rb_001_baseline.py --deck decks\deck_001_sample.csv
```

手動プレイGUI:

```powershell
uv run python scripts\manual_play_server.py --port 8765
```

公式Visualizer用JSON出力:

```powershell
uv run python scripts\export_visualizer_json.py --output experiments\visualizer\latest_replay.json
```

デッキ検証:

```powershell
uv run python scripts\check_decks.py
```

GPUサーバーでDocker確認:

```bash
docker compose build
docker compose run --rm ptcg uv run python scripts/docker_gpu_check.py
```

### 次にやること

- Gitリポジトリとして正しく初期化されているか確認する。
- `API.txt` やKaggleデータ、生成zip、PDF、モデルファイルがGitに入らないことを確認する。
- GitHubに共有用リポジトリを作る。
- 安福・長谷川に `docs/collaboration/安福_長谷川向け.md` と `docs/collaboration/GIT_MINIMUM.md` を読んでもらう。
- 友人には公式サイトでデッキを作り、`run\02_deck\デッキコード登録.bat` で自分でコンパイルし、`run\03_play\GUI起動.bat` でプレイするループを回してもらう。
- 良いものだけデッキコードと気づいたことを助友に直接送ってもらう。
- Gitへの反映は助友が行う。友人側は基本的にGitHub Desktopで最新版を取ってシステムを使うだけにする。
- ユーザー本人が `agents/` と `decks/` を増やし、Codex側が評価・集計を回す。

### 注意

- `API.txt` は認証情報なので共有しない。
- `docs/official/Competition_Rules.md` は公式原文なので変更しない。
- 初心者メンバーは基本的に公式サイトのデッキコードをシステムに入れてGUIでプレイするだけ。CSVや実装ファイルは直接編集しない。
- 公式VisualizerはリプレイJSONを見る用途に分ける。手動で1手ずつ操作する用途はGUIを使う。
- `agents/`, `scripts/`, `submission/`, `models/`, `training/`, `docker/` は実装担当側で管理する。

### 行動空間削減の方針

- GUIの選択肢削減は、後段のエージェント開発における行動空間削減の土台として扱う。
- 同質な行動だけを畳む。見た目が似ているだけの行動は削除しない。
- 現時点では、同じ基本エネルギータイプを同じポケモンへつける選択肢だけを代表1つに畳む。
- 付け先が違う場合、基本エネルギーのタイプが違う場合、特殊エネルギーのカードIDが違う場合は別行動として残す。
- 手札から使う同名カードは、単一選択の場面では代表1つに畳む。
- 複数枚を同時に選ぶ場面では、同名カードでも必要枚数を選べなくなるため現時点では畳まない。
- 共通ロジックは `scripts/action_abstraction.py` に置き、GUIだけでなく将来のAgentからも参照できる形にする。
- 回帰テストは `tests/test_action_abstraction.py` に置く。
