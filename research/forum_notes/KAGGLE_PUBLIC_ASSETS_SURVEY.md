# Kaggle 公開資産調査メモ

調査日: 2026-07-01

## 結論

現時点で最も有益そうなのは、公開 Notebook そのものよりも、公式が提供している上位対戦エピソードの Dataset です。

優先順位は次の通りです。

1. Daily Top Episodes Datasets
2. Official Visualiser / Replay Viewer Notebook
3. RL / PPO / MCTS に関する公開 discussion
4. ルール差分・提出形式に関する公式 discussion
5. Competition Code タブの公開 Notebook 群

Kaggle の Code タブはブラウザ上では確認できる一方、CLI で一覧取得するには Kaggle 認証設定が必要でした。現時点のローカル環境では未認証扱いだったため、Notebook 一覧の完全な棚卸しは未完了です。

## 1. Daily Top Episodes Datasets

- Index: https://www.kaggle.com/datasets/kaggle/pokemon-tcg-ai-battle-episodes-index
- 手元の `manifest.csv` には、2026-06-16 から 2026-06-30 までの日次 Dataset が載っている。
- 各日付の Dataset は数 GB から 20 GB 程度あり、上位プレイヤーの対戦に偏っている。

用途:

- 強いデッキの傾向を見る。
- 序盤の動き、セットアップ、サーチ先、エネルギーの貼り先を集計する。
- 「この盤面では何を選ぶか」の教師データを作る。
- 将来の Behavioral Cloning や強化学習の初期方策に使う。
- 友人が見つけたデッキ案を、上位エピソード内の似た動きと比較する。

注意:

- 上位対戦データなので、全体分布ではなく強者バイアスがある。
- データサイズが大きいため、まず 1 日分か小さいサンプルだけ読むべき。
- そのまま GUI に流すより、局面・合法手・選択手・勝敗に分解して保存するのがよい。

## 2. Official Visualiser / Replay Viewer Notebook

- Notebook: https://www.kaggle.com/code/kiyotah/how-to-output-local-battle-as-json-and-view
- Discussion: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/713051

用途:

- ローカル対戦を JSON に出力し、公式 Visualiser で見る。
- GUI で操作した試合や、自作エージェント同士の試合を後から確認する。
- 非公式 Viewer を公開すると規約面で危ないため、リプレイ確認は公式 Notebook に寄せる。

このプロジェクトでの位置づけ:

- 手動プレイ GUI は継続して使う。
- Official Visualiser は「終わった試合を確認する道具」として使う。
- 友人には必須にしない。こちら側の検証・説明用でよい。

## 3. RL / PPO / MCTS discussion

- 手元の保存ファイル: `discussion/How has your experience been with RL_PPO_MCTS in this competition so far.md`

読み取れる示唆:

- 上位では強い heuristic baseline が支配的らしい。
- C++ シミュレータは閉じており、巨大な高速ベクトル化環境としては扱いにくい。
- 長時間 self-play ではメモリリーク対策として、一定試合ごとに worker を再起動する運用がある。
- いきなり PPO ではなく、強い heuristic の行動を真似る Behavioral Cloning で初期方策を作る流れが現実的。
- 1 手 1 秒制限では MCTS の rollout 数が非常に少なく、policy prior なしの探索は弱そう。

このプロジェクトでの方針:

- 直近はルールベースとデッキ検証を優先する。
- 機械学習を始める場合も、まずは Daily Top Episodes か自作 heuristic の行動を教師データ化する。
- MCTS は最初の主役にしない。使うなら policy prior ができてから検討する。

## 4. ルール差分・提出形式 discussion

重要な discussion:

- Differences Between the Official Pokémon TCG Rules and the Simulator Behavior
- Is it allowed that one agent use multi-decks?
- Reminder about the Kaggle Simulation Competition Format
- June 30 Update: Updated Simulation Environment, gameplay increases

用途:

- 公式ポケカのルールではなく、競技シミュレータで実際に起きる挙動を確認する。
- 提出は基本的に `1 Agent + 1 Deck` と考える。
- 提出数・アクティブ提出数の制約を踏まえて、ローカル評価を厚くする。
- シミュレータ更新時に、GUI・deck validation・runner の挙動が壊れていないか確認する。

## 5. Competition Code タブの公開 Notebook 群

- Code tab: https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/code

現状:

- Web ページは確認できるが、外部取得では JS ページとしてしか読めなかった。
- Kaggle CLI の `kernels list` は、現在のローカル設定では未認証扱いで失敗した。
- したがって、公開 Notebook 群の網羅的な評価はまだできていない。

次に見るべき Notebook の種類:

- submission baseline を改造したもの。
- deck.csv の作り方、デッキコードの扱い、カード ID 変換を扱うもの。
- episode JSON や visualizer JSON を処理するもの。
- heuristic agent の実装を公開しているもの。
- 学習済みモデル提出や、Behavioral Cloning の前処理を含むもの。

## 次の実装候補

1. `manifest.csv` から、指定日付の Daily Top Episodes Dataset を取得するスクリプトを作る。
2. 取得した episode の schema を確認し、最初の 100 試合だけ読む。
3. 局面、合法手、選択手、勝敗、使用デッキを抽出する。
4. サーチ先、エネルギー貼り先、攻撃選択、マリガン、初期展開を集計する。
5. GUI での手動研究結果と、上位 episode の傾向を比較する。

まずは `1 日分を少量だけ読む` ところから始めるのがよいです。全量処理や学習基盤は、その schema が確定してからで十分です。
