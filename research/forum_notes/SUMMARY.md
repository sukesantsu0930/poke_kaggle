# Kaggle掲示板メモ

取得日: 2026-07-01

## 重要トピック

### 公式Visualizer

- トピックID: `713051`
- タイトル: `Official Visualiser/Replay Viewer`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/713051
- 非公式Viewerは規約違反として削除されたという案内あり。
- 公式Notebook: https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
- Game Historyから `Open Visualiser` で個別リプレイを確認できる。

方針:

- 対戦リプレイ表示は公式Visualizerを使う。
- 自作GUIは「デッキ編集」「手動選択」「ローカル検証補助」に寄せる。
- 公式Viewerの代替として公開するようなものは避ける。

### 公式ルールとシミュレータ挙動の差分

- トピックID: `708586`
- タイトル: `Differences Between the Official Pokémon TCG Rules and the Simulator Behavior`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/708586
- シミュレータ挙動がこの競技では正しい扱い。
- 一部攻撃は公式ルールなら宣言できても、シミュレータでは選択肢に出ないことがある。
- 同時きぜつ時のサイド取得順など、公式ルールと処理順が異なる場合がある。
- `ABILITY` は明示的に選ぶ行動、`SKILL` は受動・継続効果寄り。
- セットアップ時、任意ベンチ選択は `minCount == 0` なら `[]` を返してスキップ可能。

方針:

- 友人の「ルール発見」は公式ルールだけでなく、シミュレータで実際にどう動くかを重視する。
- 発見した差分は `research/rule_findings/` に残す。

### Daily Top Episodes

- トピックID: `709160`
- タイトル: `Daily Top Episodes Datasets`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/709160
- 上位対戦のエピソードデータセットが毎日作られる。
- インデックス: https://www.kaggle.com/datasets/kaggle/pokemon-tcg-ai-battle-episodes-index
- 上位参加者の対戦に偏ったデータ。

方針:

- 強いデッキ・強い判断の観察材料として使える。
- 友人向けには、リプレイを見て「何が強いか」をメモしてもらう運用がよい。

### 1提出1デッキ

- トピックID: `711741`
- タイトル: `Is it allowed that one agent use multi-decks?`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/711741
- 1つの提出内で複数デッキをゲームごとに切り替えるのは意図された競技設定ではない。
- 各提出は単一デッキを一貫して使う期待。

方針:

- 研究段階では多数のデッキを作ってよい。
- 提出時は `1 Agent + 1 Deck` の組み合わせに固定する。

### 提出・評価形式

- トピックID: `714189`
- タイトル: `Reminder about the Kaggle Simulation Competition Format`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/714189
- 最大2つのアクティブ提出。
- 1日5回まで提出可能。
- 最新2提出がアクティブ。
- 競技終了後もしばらく対戦が続き、ランキングが収束する。
- 実験提出で安定版が押し出されるリスクがある。

方針:

- ローカル検証を厚くしてから提出する。
- 提出候補は `submissions/` に明確な名前で残す。

### 6月30日更新

- トピックID: `716045`
- タイトル: `June 30 Update: Updated Simulation Environment, gameplay increases`
- URL: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/716045
- `cg` ライブラリが更新され、macOS/Linux ARM64対応が追加。
- `main.py`, `deck.csv`, APIの変更はなし。
- 無限ループはドローではなくタイムアウト負けになりやすくなった。

方針:

- サンプルデータ更新が来たら `cg/` の差し替えを確認する。
- 無限ループしないエージェント検証を重視する。

