# プロジェクト日記

このファイルは、次回作業を再開するときのための引き継ぎメモです。

毎回ディレクトリ全体を走査しなくても、まずここを読めば状況が分かるようにします。

## 2026-07-08

### 7/7 フレッシュデータでの divergence 一斉アップグレード（上位ピロット限定・5資産）

- **データ**: Daily Episodes 2026-07-07 を250件取得（`downloads/episodes/2026-07-07/`）、
  リーダーボード更新（7/8 04:32 UTC 版）。国勢調査（レート1000+ ピロットの試合数/250件）:
  **マリィ108 / フーディン69 / ガブリアス32 / ガルーラ29 / シャンデラ12 → 5資産をアップグレード**。
  **ブリジュラス4・ドラパルト5 は上位ピロット不足でスキップ**（ユーザー制約: ラダー上位の参照必須。
  ブリジュラスの上位使い ShumpeiNomura 1098 は4試合、ドラパルトは @BigBugginnings 1080 の5試合のみ）。
- **手順**: 調整日=7/7・検証日=7/6（P-10。7/7 が最新公開日のため検証は前日で代用）。
  採用判定 = L2 非退行（gauntlet 60戦×2〜3資産）∧ L3 非悪化（両日の divergence）。
  ログ一式: `research/eval/div_logs/`。
- **結果（L3 調整日→ / ホールドアウト→）**:
  - **マリィ 採用**: div-4（ATTACH_FROM 未実装を発見・実装 50%→67%）/ div-6（タンカ温存）。
    64.8→**66.0%** / 63.6→**64.9%**。L2: 対フーディン 78.3%（+3.3）・対ブリジュラス 43.3%（+10）。
    div-5（ベンチ抑制）は棄却。**保留課題の決着: div-1/2/3 は 7/7 でも非悪化 → 確定維持**
  - **フーディン 採用**: div-8（進化帯をアイテムより上へ = 進化時ドローがエンジン）/ div-9（サーチ表再調整）。
    55.8→**57.7%** / 58.3→**58.9%**。L2: 対ブリジュラス 51.7%（+5）・対マリィ 21.7%（−5 ノイズ・天敵のまま）。
    **保留課題の決着（アブレーション）: div-6 は実効+0.9pt → 確定へ復帰、div-4 は効果±0 → 【暫定】のまま**。
    div-7（辞退拡張）は棄却
  - **ガブリアス 採用**: div-G5（Champion's Call をアイテム後へ）/ G7（森温存）/ G8（リーリエ優先）/
    G9（ガブ先取り抑制）。66.2→**67.4%** / 66.5→**68.3%**。L2: マリィ 58.3%・フーディン 53.3%・
    ブリジュラス 60.0%。G6 は棄却
  - **シャンデラ 【暫定】**: div-C5（ボス緩和）/ C6（セットアップPad掘り）。72.4→**72.5%** / 74.2→**74.8%**。
    L2: マリィ 48.3%・ブリジュラス 73.3%。サンプル12試合と薄く効果はノイズ帯（P-09）
  - **ガルーラ 【暫定】**: div-K8（ライコ弾込め）/ K9（ラティアス前出し）/ K11（他所の特性を押さない）。
    49.4→**49.6%** / 50.4→**51.1%**。L2: マリィ 45.0%・ブリジュラス 30.0%。K7/K10 は棄却。
    構造的上限: TO_HAND の大半がサイド取得（一致不能）+ bono の変種リスト
- **L1**: 5資産とも check_agent 全合格（errors=0）。**zip 再ビルド5本 + validate_episode 全合格**
  （`submissions/2026-07-08/`: marnie / alakazam / cynthia_garchomp / mega_kangaskhan / chandelure）。
  提出はユーザー判断（本作業では提出しない）。
- 詳細は各デッキ設計md の「divergence 第2弾」節。

### ドラパルト制圧プラン（メタ加重ガントレット + div-D1）

- **道具**: `agents/_base/generic_policy.py`（任意60枚を相手役化する GenericPolicy。_base 内で完結、
  提出物には入らない）+ `scripts/gauntlet.py`（フィールドCSVを読みシェア加重勝率=制圧度を計測）。
  フィールド正本 `research/meta/2026-07-08_field.{md,csv}`（友人調べ・11アーキ・97.4%）。
  既知ペア再現（ドラパ vs マリィ 53.3%/60戦）で健全性確認済み。生データ `research/meta/gauntlet_runs.csv`。
- **小粒デッキ5種を7/6エピソードから抽出**（全て最高レートの勝者リスト・check_decks 合格）:
  small_okidogi（btk15049 1053.5）/ small_comfey_yveltal（koga_poke 1099.0）/ small_lopunny（lmaffei 1026.8）/
  small_megastarmie（Yushin Ito 1122.0）/ small_rocket（kashiwashira 912.6）。
- **div-D1（対アグロ環境で先攻）**: 敗因診断で「対マリィ敗北の58%はダイブ0回のセットアップ崩壊、
  かつ GO_FIRST=False のため全戦後攻」を特定 → GO_FIRST=True を A/B（対マリィ 49.5%/220戦 → 58.0%/200戦、
  回帰なし）で採用。check_agent 合格・zip 再ビルド+validate_episode 合格（`submissions/2026-07-08/`）。
- **ドラパルト制圧度 58.2% → 63.8%**（11×60戦）。**合格基準（加重≥60% かつ 小粒5種≥50%）達成**。
  詳細は `デッキ設計_ドラパルト.md` の before/after 表。提出はユーザー判断（スカウト枠候補）。
- **7資産の制圧度ランキング（30戦/マッチアップ）**: ブリジュラス 70.3% > シャンデラ 64.5% >
  ガブリアス 58.4% ≈ ドラパルト 58.2%(div-D1 後 63.8%) > マリィ 56.0% > ガルーラ 49.8% > フーディン 37.2%。
  ブリジュラスが対マリィ 76.7% でこのフィールドの最強資産（E[max] 選定の材料）。
- 残課題: メガスターミー戦はサイドレース勝負（プール57.2%）で配分の override 候補あり（要A/B）。
  ブリジュラス戦 42.5% はドラパルト最弱のまま（シェア2%のため優先度低）。

## 2026-07-07

### 提出失敗と修正（R-25）

- 7/6 ビルドの3本が Kaggle の Validation Episode で failed（オーロンゲ・ブリジュラスで確認）。
- 原因: **Kaggle のローダー（kaggle_environments `get_last_callable`）は main.py の「最後に定義された callable」をエージェントとして呼ぶ**。v2系 main.py は `def agent` の後に `def read_deck_csv` を定義していたため、毎ステップ read_deck_csv（引数0個→co_argcount切詰めで無引数呼び出し）が呼ばれ、デッキ60枚が返って IS_FIRST で INVALID。
- 修正: 3エージェントとも `def agent` をファイル末尾に移動（R-25 として `ルール抽出_オープン実装.md` に登録）。
- 再発防止3層: build_submission の静的検査（最後のトップレベル def = agent）/ check_agent のローダー忠実検査 / **`scripts/validate_episode.py`（kaggle_environments 経由のミラー1戦 = Validation Episode の忠実再現）を提出前の必須ゲートに**。
- 修正版3本は `submissions/2026-07-07/` に再ビルド、全て検証エピソード合格（DONE/DONE）。7/6 の壊れたzipは `*.BROKEN-R25` にリネーム。
- 教訓: ローカルの cg 直叩き評価（evaluate_submission 等）はローダー層のバグを検出できない。提出物は必ず kaggle_environments 経由で1戦回す。

### 提出（R-25修正版、7/7 00:30 JST 頃ブラウザ提出）

- **マリィ v1.1（COMPLETE、初動458.3）とフーディン v1.1（COMPLETE、初動562.2）を提出** → アクティブ = この2体（スカウト2枚体制）。
- ブリジュラス v1 は**非アクティブ化、879.7 で凍結**（zipは温存。再提出すれば600から復帰可。最終評価に貯金は効かないので実害小）。
- スコア推移の定点記録: `scripts/log_ladder_scores.py` → `research/ladder/scores.csv`。タスクスケジューラ `poke_kaggle_ladder_log`（3時間毎、スリープ復帰時に追い付き実行）登録済み。

### divergence 分析とマリィ v1.2（7/7 夕）

- `scripts/replay_divergence.py` 新規作成（エピソードの上位ピロット手番を自エージェントでリプレイ、SelectContext別一致率+カード名デコード）。7/6 エピソード162件から上位14ピロット・60試合・5,197手で計測。
- **R-21 確定（先攻6/6）**、div-1（マシマシラ前出し禁止）、div-2（移動元はライン駒）、div-3（Punk Up 必要枚数だけ=山に弾を残す）を実装。R-22 マリガンマックスはユーザー決定で全デッキ適用。
- 効果: 一致率60.7→63.4%、対フーディン67.5→75%、対ブリジュラス20→33%（60戦）。v1.2 zip ビルド+検証済み。
- 残る深掘り: MAIN 52% / ATTACH_FROM 47% / DISCARD 0%。
- フーディンも同手法で実施（上位14名・LB4位含む・4,202手）: R-21確定（先攻33/33、既定と一致）、div-4（Run Away Draw を攻撃前に使う=+60打点）、div-5（山札薄なら任意ドロー辞退）、div-6（サーチはケーシィライン優先）。**対ブリジュラス 36.2%→46.7%**。v1.2 zip 検証合格済み。

### 資産拡張 Wave 1.5/2（7/7 深夜）: 資産7体体制

- サブエージェント並行実装で4体追加: **シャンデラ**（正体はミル=山札切れコントロール、kidekikish 77.3%リスト、先攻9/9）、**シロナのガブリアス**（nasuo445 リスト、Champion's Call エンジン、先攻22/22）、**ドラパルト**（公式サンプルの枝刈りDFS配分プラン移植=ダメカンばら撒きの制御に成功、後攻、ptcg-abc操縦初期値）、**メガガルーラ**（zoroark190 リスト、先攻20/20、プール内は弱め=ピロット改善余地）。
- **meta_tables 7月更新**: marnie/chandelure/garchomp/kangaskhan/dragapult/archaludon の ARCHETYPES・OPP_MAX_DAMAGE・OPP_BOSS_COUNTS を一括追加 → sync → 全7エージェント check_agent 合格。
- **7×7 マトリクス完成**（60-80戦/ペア、行=勝率）: プール内順位は シャンデラ64.2% > ブリジュラス60.0% > ドラパルト53.1% > マリィ49.2% > ガブリアス48.3% > フーディン40.8% > ガルーラ30.6%。三すくみ: ドラパルト>シャンデラ>ブリジュラス>ドラパルト。
- 新資産4体の提出zip すべて validate_episode 合格（`submissions/2026-07-07/`）。提出はユーザー判断。

## 2026-07-06

### 今日決めたこと

- 全体方針: ルールベース+デッキを先に成熟させ、学習は最後（ルール=行動空間の枝刈り）。
- ルールの強度（ハード/ソフト）はルール毎に決め、`docs/planning/ルール抽出_オープン実装.md` に蓄積（R-xx/P-xx 番号制）。用語は `用語とターン手順.md` が正典（判定/マスク/優先則/手順/サブゴール/フェーズ）。
- Wave 1 のデッキは Alakazam（5位実装移植）+ Marnie/Munkidori（スクラッチ）。

### 今日作った土台

- 外部公開資産を `research/external/` に取り込み（ptcg-abc クローン + Kaggle 公開 Notebook 15本、調査は `SURVEY.md`）。Git管理外。
- ブリジュラスエージェント `agents/archaludon_rb` を作成し **2026-07-06 に提出zip作成**（`submissions/2026-07-06/`）。
- **共有基盤 `agents/_base/`**（policy_base.py = BasePolicy + meta_tables.py = メタデータ層）。ターン手順（リーサル判定→負け筋カット→フェーズ分岐）は基盤で固定、デッキは3フック（judge_subgoal/score_setup/score_combat）。
- 同期機構 `scripts/sync_base.py` + build_submission のハッシュ検査。検証は `scripts/check_agent.py`（不変条件）と `scripts/ab_battle.py`（席入替A/B + shadow 挙動一致率）。
- archaludon を BasePolicy へ移行（shadow 2,411手 100%一致で挙動保存を確認）。旧版は `experiments/frozen_agents/` に凍結。
- `agents/alakazam_rb`（5位実装移植）と `agents/marnie_munkidori_rb`（スクラッチ）を実装。全エージェント check_agent 合格。

### 実測（ローカル80戦A/B、実ラダーではない点に注意 = P-03）

- マリィ vs フーディン **71.2%**（実ラダーの相性 62% を再現）
- フーディン vs ブリジュラス 36.2% / マリィ vs ブリジュラス 20.0%（ブリジュラスの220点+回復が両者に刺さる）

### 次にやること

- 提出2枠の構成判断（ブリジュラス提出済み + マリィ or フーディン）— ラダー実測が審判
- メタテーブル（`agents/_base/meta_tables.py`）の7月メタ更新をエピソード分析から
- R-21/R-22（先攻/マリガン）の上位ピロットデータ確認、divergence 分析ツールの移植

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
- 友人向け案内: `安福_長谷川向け.md`（プロジェクト直下）
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
- 安福・長谷川に `安福_長谷川向け.md`（プロジェクト直下）と `docs/collaboration/GIT_MINIMUM.md` を読んでもらう。
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
