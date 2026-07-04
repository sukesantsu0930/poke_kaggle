# 実行用ファイルの使い方

自分でダブルクリックして使うファイルは、この `run/` 以下に用途別に分けています。

黒い画面が出たら、完了するまで閉じないでください。`DONE` や `OK` が出れば成功です。`FAILED`、`NG`、`ERROR` が出た場合は、その画面を助友に送ってください。

各 `.bat` は `uv` のキャッシュをプロジェクト直下の `.uv-cache\` に置きます。
Windowsのユーザーフォルダ権限やCodex sandboxで `uv` が詰まるのを避けるためです。このフォルダは生成物なのでGit管理しません。

## 基本の流れ

1. 初回だけ `01_setup\カード画像生成.bat`
2. デッキコードを使うなら `02_deck\デッキコード登録.bat`
3. デッキ内容を確認するなら `02_deck\デッキ可視化.bat`
4. 自分で対戦して試すなら `03_play\GUI起動.bat`
5. Agentや提案を評価するなら `04_evaluate\提案評価全部.bat`
6. Kaggle に提出するなら `06_submit\提出.bat`

## 01_setup

### カード画像生成.bat

初回だけ使います。

カード画像をローカルに作ります。GUIやデッキ可視化でカード画像が表示されるようになります。

## 02_deck

### デッキコード登録.bat

公式サイトのデッキコードを、このシステムで使えるデッキCSVに変換します。

成功すると `OK decks\local\deck_....csv` のように表示されます。`NG` や `ERROR` が出たら、公式サイト側でデッキを直してもう一度実行してください。

### デッキ可視化.bat

デッキCSVを画像付きHTMLにします。

何も入力せず Enter を押すと、既定のクマシュン・オーガポン候補デッキを表示します。

出力:

```text
experiments\deck_views\
```

## 03_play

### GUI起動.bat

自分で両方のプレイヤーを操作して、デッキを試す画面を開きます。

ブラウザが自動で開かない場合:

```text
http://127.0.0.1:8765
```

### リプレイJSON作成.bat

Agent同士で1試合を実行し、公式Visualizerで見るためのJSONを作ります。

出力:

```text
experiments\visualizer\latest_replay.json
experiments\visualizer\latest_agent_log.json
```

### 公式Visualizerフォルダを開く.bat

リプレイJSON作成と公式Visualizerを開くためのローカル画面を起動します。

このプロジェクトの手動GUIとは別物です。公式Visualizerは、作成済みリプレイを見るために使います。

## 04_evaluate

### 提案評価_ドラパルト.bat

`proposals\dragapult_ex` を評価します。

通常対戦評価と一人回し評価をまとめて実行します。

### 提案評価_クマシュンオーガポン.bat

`proposals\cubchoo_ogerpon` を評価します。

通常対戦評価と一人回し評価をまとめて実行します。

### 提案評価全部.bat

現在登録されている主要proposalをまとめて評価します。

出力:

```text
experiments\proposals\
```

## 05_meta

Kaggle公開episodeから、環境に多いデッキや勝率候補を調べるための流れです。

公開episodeの勝率は、デッキ性能と操作者/Agent性能が混ざっています。ここで見つけた候補は、そのまま結論にせず、自分たちのGUI確認やAgent評価へ回してください。

### エピソード取得.bat

公開episodeを取得し、今回の分析対象リストを保存します。

### メタ分析.bat

最新の取得結果を使い、アーキタイプ別の概観と勝率候補を作ります。

### 候補デッキ作成.bat

最新の取得結果から exact 60枚候補をCSV化し、次に見ることを `next_actions.md` にまとめます。

### 外部メタ分析全部.bat

取得、メタ分析、候補デッキ作成、`next_actions.md` 生成をまとめて実行します。

### 外部メタ分析テスト.bat

5件だけで小さく動作確認します。

### 1000エピソード分析.bat / 1000_episode_analysis.bat

旧入口です。基本は `外部メタ分析全部.bat` を使えば大丈夫です。

## 06_submit

### 提出.bat

ブラウザ画面でKaggle提出zipを作ります。提出自体はKaggleの画面から手動で行います。

このコンペでは、`main.py`、`deck.csv`、`cg/` を含むzipを提出します。
