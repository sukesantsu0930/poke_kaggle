# Kaggle 公開 Notebook サーベイ 2026-07-23（07-06 以降の差分）

前回サーベイ: 2026-07-06（15本、`research/external/kaggle_notebooks/SURVEY.md`）。
今回の取得分は `research/external/kaggle_notebooks/` 配下に追加済み（下記各項に取得ディレクトリ名を記載）。
LB 確認: **首位 Luca 1206.0**（07-20 提出）、2位 junlee789 1185.9、3位 Majkel1337 1174.9。20位で約 1081。

---

## 総括 — 07-06 以降に何が変わったか

1. **「実ラダー上位提出のリプレイを BC で複製する」流派が公開側の主流に浮上**。
   fishcat37 の attention BC アーキテクチャ（v8/v9）を土台に、prvsiyan が生きた高レート提出
   （Rocket Spidops 1161.9、Rmy の Grimmsnarl 1118 等）のリプレイだけから政策を複製して提出する
   Notebook を量産している。我々の BC ミックス路線（rocket_bc / marnie_bc 等）と完全に同じ発想が
   公開の場で回り始めた。
2. **探索（bounded forward search）が「一番効くレバー」だったという実測報告**。
   Tientrum が実ラダー 1034.6 Elo 到達チェックポイントを公開し、「heuristic 上位K手 × 決定化数手 ×
   2-ply 探索」がヒューリスティック調整全部より効いたと明言。上位者の生の教訓として最重要。
3. **メタ分析はインフラ化・日刊化**。pilkwang の週刊 Meta Snapshot（161 vote）、busyaprime の
   「全部生ログから再計算する」タイプの日次メタ、myso1987 のスコア帯別デッキメタ、makimakiai の
   公開エージェント 36+4 総当たり表。メタ情報自体はもう差別化要因ではない。
4. **デッキメタ（07-16〜18 窓）**: Alakazam が 36〜46% の巨大センター（勝率はほぼ50%）、
   Crustle 壁は 28%→19.5% に後退、**Team Rocket Spidops が 1.4%→12.3% に急伸（52.3%）**、
   Festival 系が新登場（4〜7%、対 Crustle 60%）、Starmie が「正確な60枚単位」での最強リスト
   （schedule調整強度 +198.7）、Marnie/Munkidori 9.9% に回復、Marnie/Grimmsnarl は 1.6% に沈む。

---

## 新着・更新 Notebook 一覧（07-06 以降、重要度順）

### A. エージェント実装（新規パラダイム）

| ref | 日付 | 概要 | 主張スコア |
|---|---|---|---|
| tientrum/search-augmented-heuristic-agent-alakazam | 07-13 | 探索付き Alakazam の実物チェックポイント公開 | **実ラダー 1034.6 Elo**（07-05 時点） |
| prvsiyan/ptcg-rocket-replay-clone-public-0722 | 07-22 | 1161.9 レートの Rocket Spidops 提出を 239 リプレイから BC 複製 | スコア主張なし（出典が1161.9） |
| prvsiyan/ptcg-rmy-grimmsnarl-replay-hybrid-v1 | 07-22 | Rmy（LB 11位 1118）の Grimmsnarl/Froslass を 125 リプレイから BC + 2つのルール補正 | 同上 |
| prvsiyan/ptcg-ai-battle-search-audited-alakazam-v8〜v12 | 07-21/22 | Tientrum 政策 + 現行ラダー観測デッキ + bounded search の連作 | ローカル診断のみ |
| fishcat37/ptcg-v8/v9-attention-all3d-end-to-end | 07-18/19 | 公式日次エピソード → 日次 Top-20 エージェントで絞込 → attention BC 学習 → 提出、の一気通貫 | 主張なし |
| utilisateurrichard/pok-mon-muzero | 07-22 | MuZero 学習（コードは私有 dataset、中身は見えない） | 不明 |

### B. テクニック・分析

| ref | 日付 | 概要 |
|---|---|---|
| hitoshimochizuki/live-opponent-deck-prediction-from-revealed-cards | 07-19 | **公開カードから相手の60枚を期待枚数ベクトルで推定する belief モデル**（DeckBeliefNet） |
| pilkwang/pok-mon-tcg-ai-battle-meta-snapshot-18-july | 07-18 | 週刊メタ（161 vote、シリーズ現行版）。デッキ力と政策力の分離測定が読み所 |
| busyaprime/what-actually-wins-on-the-ladder | 07-20 | 生ログから全メタ指標を再計算する監査可能ノート + 日次 live-meta dataset |
| myso1987/ptcg-ai-battle-leaderboard-deck-meta-by-score-band | 07-22 | LB 全チームの提出リプレイからデッキ復元 → 100点刻みスコア帯別のアーキタイプ分布 |
| makimakiai/ptcg-public-28-plus-sample-4-roster-update | 07-22 | 公開エージェント 36 + 公式4 の総当たり表（780ペア/7800戦）。ベンチ相手カタログとして有用 |
| smallpond/en-replay-archetype-analysis | 07-09 | 日次リプレイ→アーキタイプ分類・勝率上位デッキの CSV/TXT/PY 出力・**BC/RL 用 action trace 出力**つき（95 vote） |
| llccqq624/ptcg-replay-data-miner | 07-08 | 提出→エピソード→デッキ復元のマイニング手順（myso1987 の出典） |
| shlomoron/ptcg-engine-crash-repro-nb | 07-21 | エンジンクラッシュの再現手順（安全設計の参考） |
| naoto714 の EN/JP 連作（07-05〜07-20 に十数本） | — | デッキコンセプト探索: Bronzong 進化ジャマー vs Alakazam、Mega Kangaskhan 2ターン速攻、Slowking コピー、Bloodmoon Ursaluna 140→520、Mega Gengar サイドレース外し、等 |

### C. 既知 Notebook の更新

- `romanrozen/strong-start-baseline-agent-v10-lb-950`（135 vote）: 07-20 再実行。内容は既知の V10 のまま。
- `soutasakurai/max-elo-1208-libraryout-w-crustle-great-tusk`（06-26、今回初認知）: **公開 Notebook 中最大の Elo 主張 1208**。Crustle/Great Tusk/Terrakion の LO（山札切れ）コントロール。メタスナップショット群の「Library-Out 補完枠」の源流。取得済み。
- `abiolatti/custom-engine-with-vectorized-env-2m-sample-sec`（07-05、24 vote): エンジン再実装のベクトル化環境 2M sample/sec。RL 勢のインフラ。

---

## 注目実装の詳細

### 1. tientrum/search-augmented-heuristic-agent-alakazam（実ラダー 1034.6 Elo）
取得: `kaggle_notebooks/search-augmented-heuristic-agent-alakazam/`

- **構成**: 巨大な WEIGHTS 辞書（約70個の優先度重み）による option スコアリング +
  `search_begin/step/end` を使う軽量 2-ply 探索。
- 探索の設計:
  - heuristic の **上位K候補のみ**展開（全合法手ではない）。
  - 各候補につき**数個の決定化**（観測と整合する隠れ情報サンプル）。
  - 自分1ターン + 相手の greedy-heuristic 応手 + 少々 → 葉は簡素な盤面評価（サイド差・HP・展開）。
  - **「探索が heuristic の第一候補を上書きするのは、十分な決定化サンプルで約サイド0.5枚分の差がつく時だけ」**という保守的な上書き閾値。
  - 決定予算 0.8 秒、失敗時は純 heuristic へ。
  - 相手 belief は本来「観測カード→既知デッキテンプレ照合」で絞る（公開版は uniform フォールバック）。
- **著者の実測所感: この探索層が「プロジェクト全体で単一最大のレバー」で、heuristic チューニングの総和より効いた。**
- 重みは手調整シード + memetic（変異→ローカル対戦→採否）の2層。ただし
  **「小さいローカル勝率信号での進化探索は winner's curse がひどい。大きな独立サンプルで再検証してから信用」**。
- **learned value network は何度やってもオフライン指標は良いのに実際の際どい2択を改善しなかった**
  （credit assignment 問題との見立て）。→ 我々の模倣正則化 PPO の評価設計への警句。

### 2. prvsiyan のリプレイ複製ポートフォリオ（Rocket / Grimmsnarl / Alakazam / LO）
取得: `ptcg-rocket-replay-clone-public-0722/`, `ptcg-rmy-grimmsnarl-replay-hybrid-v1/`, `ptcg-ai-battle-search-audited-alakazam-v12/`

- **Rocket Replay Clone**: 現役 1161.9 レートの Rocket Spidops 提出の公開リプレイ 239 本から
  behavior cloning。アーキテクチャは fishcat v9（下記）。BC 政策で合法手をランクし、MAIN では
  時間・候補数・深さを制限した forward lookahead を載せる（失敗時は BC 単独で完結）。
  checkpoint は SHA-256 検証つき公開 dataset。
- **Rmy Grimmsnarl Replay Hybrid**: 125 リプレイの BC + **リプレイ非依存検証で採択した2つの狭い
  ルール補正**（ダメカン配置/直接ダメージ/ダメカン除去は「見えている最低残HPを選ぶ」、
  Grimmsnarl ex の Punk Up 強制エネ配分は深さ制限つき決定木）。BC の弱点（強制選択コンテキスト）
  だけルールで塞ぐ、というハイブリッドの型。ローカル診断 128 戦/相手: 対 Nurs Lucario 51–77(負け越し)、
  対 Alakazam v8 85–43、対 Great Tusk/Crustle 90–38。
- **Search-Audited Alakazam v12**: Tientrum の重み表 + 直近リプレイから観測した現行 Alakazam
  60枚（Rare Candy 4 / Enhanced Hammer 4 / Nighttime Mine 型）+ 0.8s bounded search。
  旧 Great Tusk 控えの成績劣化（対 Alakazam 36.8% 等）を監査して**デッキ乗り換えを決めた過程**を明記。
- 示唆: このシリーズは「メタ監査 → 生きた強デッキの観測 → リプレイ BC → 狭いルール補正 → 提出」の
  ループを公開でやっている。**我々のパイプラインの直接競合**であり、彼らの補正点
  （強制選択コンテキストの BC 弱点）は我々の BC でも同様に確認すべき。

### 3. fishcat37/ptcg-v9-attention-all3d-end-to-end（BC 基盤アーキテクチャ）
取得: `ptcg-v9-attention-all3d-end-to-end/`

- Kaggle 内で完結する BC 学習パイプライン: 公式日次エピソード（07-05〜07-15）→
  **日次ラダー Top-20 エージェント名で行動主を絞り込み**（`fishcat37/ptcg-v8-daily-top20` dataset、
  replay の `agent_index` 対応）→ Parquet（`bc-static-v3` 特徴契約）→ T4×2 で 8 epoch。
- モデル: per-slot ヒストグラム + 静的カード/ワザ特徴 + **盤面 self-attention（51 カードチャネル ×
  slot type embedding の 2層 Transformer）+ option cross-attention（各 option が盤面 slot を query）**。
- 損失: option 毎 BCE（正例1.0/負例0.25 重み）+ no-action ヘッド 0.5 重み。metric は top-1 /
  exact-set 一致。min/maxCount を考慮した予測集合構成（no_action スコアを閾値に使う）。
- デッキは Lucario 系で固定。**「アーキタイチャは公開・データは日次・上位20で絞る」が公開 BC の標準形**になった。

### 4. hitoshimochizuki/live-opponent-deck-prediction-from-revealed-cards（相手デッキ belief）
取得: `live-opponent-deck-prediction-from-revealed-cards/`

- serial 重複排除つき RevealedCardsTracker（場/ベンチ本体+energyCards/tools/preEvolution、
  トラッシュ、スタジアム、logs type 6/10/11/12）で相手の公開カードを累積。
- 公開枚数 1/2/4/8/12/20 のマイルストーンでスナップショット → MLP（DeckBeliefNet）が
  **期待枚数ベクトル（60枚に正確に配分、下限=公開済み枚数、上限=4枚/ACE SPEC 1枠、基本エネ無制限）**を出力。
- 2段階学習: 合成部分公開（共起学習）→ 実リプレイのスナップショットで fine-tune。
- 教訓: **デッキ同一性で split**（スナップショット split は過大評価）、**既知リストカタログへ射影しない**
  （期待値ベクトルのまま belief を保持し、サンプルが要る時だけ制約を適用）、情報量レベル別に精度を報告。
- 我々への接続: リツキの分布予測と、search 決定化（opponent_deck の Snorlax 埋めの置換）両方に効く設計図。

### 5. pilkwang/pok-mon-tcg-ai-battle-meta-snapshot-18-july（現行メタの正典、161 vote）
取得: `pok-mon-tcg-ai-battle-meta-snapshot-18-july/`

- 07-18 窓の要点:
  - **Alakazam**: 35.7〜46.4% で推移し 39.7% で終了。スコア率 50.1% の「勝ててはいない巨大センター」。
  - **Crustle**: 07-12 の 28.0% をピークに 19.5% / 46.7% へ後退。新興プレッシャー系に不利。
  - **Team Rocket Spidops**: 1.4%→12.3%（+10.9pp）、最終日 52.3%。対 Alakazam 54.3%（510戦）、対 Crustle 約61%。
  - **Festival**: 突然 7.2% まで伸び 4.3%/53.3% に定着。対 Crustle 60.5%。
  - **Starmie**: 4.5%/55.0%。対 Crustle 69.1%、**対 Spidops 87.0%**、対 Alakazam 40.5%。
    exact-list `c9902f0e` が schedule 調整強度 +198.7 で首位。
  - Marnie/Munkidori 9.9%/51.8% に回復、Marnie/Grimmsnarl は 1.6%/44.9% に沈む。
  - Alakazam は対 Starmie 59.5% / 対 Cynthia 63.9% で「広さで生き残る」。三すくみ構造が保存。
- 方法論面の読み所:
  - **選択効果の実測**: 広域探索で最良だった Starmie 政策 p005 が確認ランで 89.2%→78.1% に急落、
    安定版 p006 は 81.1% を保持。「選択時最大値ではなく安定性と独立 holdout を採る」。
  - **exact-build coverage**: 名目カバレッジ 90%+ が、ベンチ相手を「実際に対戦した exact ビルド」に
    結び直すと 82.8% に落ちる。
  - 成熟 Lucario 参照は 86.5% で新政策より依然上。**「デッキ発見は注目先を教えるだけで、
    エージェント強度を確立しない」**。
  - 提出プロファイルは A=Archaludon Metal Tempo（強パネル 67.9%）と
    B=Great Tusk/Crustle Library-Out（57.1%、補完枠）の2択構成（デフォルト B）。

### 6. メタ計測系そのほか
- **busyaprime/what-actually-wins-on-the-ladder**（取得: `what-actually-wins-on-the-ladder/`）:
  エピソード JSON から「各席の自視点 obs.logs の playerIndex==自分」でプレイカードを読み、
  最高HP の ex をアーキタイプラベルにする再計算型。Wilson 区間つき tier 表、n>=8 の相性グリッド、
  **usage 加重の対フィールド期待勝率（deck recommender）**、勝敗別 median steps（タイムアウト危険度）。
  結果 CSV は dataset `busyaprime/pokemon-tcg-ai-battle-live-meta` として日次維持。
- **myso1987/…-by-score-band**（取得: `ptcg-ai-battle-leaderboard-deck-meta-by-score-band/`）:
  LB チーム毎に「現スコアに最も近い公開提出→直近公開エピソード→60枚復元→ルールで分類」を
  100点刻み帯で集計。1s ペーシング・429 は再試行せず欠測計上・帯毎に分母を明示、という
  API 節度の設計が参考になる。新規提出は 600 開始なので「自分の帯と一つ上の帯」を見る使い方。

---

## 手法分類マップ（公開実装の現在地）

| 系統 | 代表 | 状態 |
|---|---|---|
| ルールベース（option スコアリング） | strong-start v10、alakazam-best-5th、1084.5 baseline(=islet系Fork)、LibraryOut 1208 | 依然として提出の主流。ただし公開物の上限は 950〜1200 帯 |
| ルール + bounded search | tientrum（1034.6）、prvsiyan v8-v12、multiply(940) | **公開側のベストプラクティス化**。上書き閾値・時間予算・決定化の作法が確立 |
| リプレイ BC（模倣） | fishcat v8/v9、prvsiyan Rocket/Grimmsnarl クローン | 急伸中。生きた上位提出を数百リプレイで複製 + 狭いルール補正 |
| BC + RL | （公開では fishcat 系の BC まで。RL 本体の公開成功例はまだ無し） | penguin069 の [private]ptcg-rl-dataset が示唆的だが非公開 |
| MCTS / MuZero | 公式サンプル、utilisateurrichard/pok-mon-muzero | MuZero は実体非公開。公開の勝ち筋としては未実証 |
| belief / 推定 | prize-tracking(既知)、**live-opponent-deck-prediction** | サイド落ち推定に加えて相手デッキ分布推定が登場 |
| メタ計測 | pilkwang 週刊、busyaprime 日次、myso1987 スコア帯別、smallpond 日次、makimakiai 総当たり | 完全にインフラ化。DL済みエピソードで我々も再現可能 |

---

## 我々への示唆（優先度順）

1. **BC の強制選択コンテキスト監査**: prvsiyan が Grimmsnarl クローンで入れた2補正
   （ダメカン配置系=最低HP選択、強制エネ配分=決定木）は、BC が系統的に弱い場所の指摘。
   我々の *_bc 各エージェントで同じコンテキストの一致率を divergence 監査すべき。
2. **探索層の費用対効果**: 1034.6 Elo の実測で「探索 > heuristic 調整の総和」。我々のルール成熟後の
   次段として、Tientrum 流の保守的上書き閾値（サイド0.5枚分）+ 0.8s 予算 + 数決定化は
   そのまま流用できる設計。PrizeTracker と belief net を決定化に接続すれば公開版より精度が出る。
3. **Rocket Spidops の急伸（1.4%→12.3%）**: 我々の rocket_rb/rocket_bc の対象デッキがメタの主役級に。
   同時に **Starmie が対 Spidops 87%** のカウンターとして観測されている点は 07-14 以降のフィールド
   想定に織り込む必要がある。
4. **評価方法論の借用**: pilkwang の「選択効果（89.2→78.1）」「exact-build coverage」、
   busyaprime の Wilson 区間と usage 加重期待勝率は、我々の gauntlet 80戦/枠（P-12）や
   pool-fit 参考値運用と整合する。特に「広域探索の最大値を信用しない」は EXP 系の候補選定に直結。
5. **進化的重み探索の warning**: winner's curse の実測報告（Tientrum）。ローカル勝率での
   ハイパーパラメータ採択は必ず独立大サンプルで再検証。
6. **value network が際どい2択を改善しなかった**という否定的結果は、我々の PPO 価値関数の
   使い所（行動選択への直接寄与）を過信しない根拠になる。

## 取得できなかったもの・限界

- Kaggle CLI の kernels list は正常動作。`utilisateurrichard/pok-mon-muzero` は本体コードが
  私有 dataset のため中身は確認不能（2セルの実行スタブのみ）。
- `penguin069/private-ptcg-rl-dataset`（07-17）はタイトル通り private で内容不明。
- myso1987 / makimakiai / pilkwang の**実行出力（表・画像）は kernels pull では取れない**
  （ソースのみ）。数値は markdown に書かれたもののみ採録。
- seokjeongeum 名義の LB1100/1208 系 Notebook は現在 404（削除 or 非公開化）。1208 の原典は
  soutasakurai 版で確認。
