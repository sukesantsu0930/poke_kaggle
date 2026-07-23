# Kaggle Discussion サーベイ — pokemon-tcg-ai-battle（2026-07-23 実施）

- 取得方法: Kaggle 内部 API（`api/i/discussions.DiscussionsService/GetTopicListByForumId` / `GetForumTopicById`、匿名 Cookie + XSRF）。WebFetch は SPA のため空、curl の HTML も 5.7KB シェルのみ → 内部 API が唯一の有効ルートだった。
- Simulation 部門 forumId=8948467、全 **161 トピック**の一覧を取得し、07-06 以降に活動のある主要 39 スレッドの本文＋コメントを全文取得。
- 戦略部門（`pokemon-tcg-ai-battle-challenge-strategy`、forumId=10272044）は 13 トピックすべて確認。
- 生データ: セッションの scratchpad（`threads/*.json`, `threads_txt/*.txt`）。恒久保存が必要ならコピー可。
- 取得不可: なし（一部コメントは削除済みで `? ()` 表示のみ）。リーダーボードは Kaggle CLI（`.kaggle/access_token`）で取得成功。

## 0. コンペ基本情報（GetCompetition API より）

- 締切: **2026-08-16 23:59 UTC**。チームマージ / 新規参加締切: **2026-08-09 23:59 UTC**。公開ノートブック公開禁止化も 08-09。
- 提出 5 回/日、最終スコア対象 2 提出。提出サイズ上限 20,480MB（実測 UI は 197.7MiB との報告あり）。
- 参加 5,542 チーム / 12,088 参加者、総提出 10,464（07-23 時点）。
- 戦略部門の締切: **2026-09-13 23:59 UTC**。
- LB トップ（07-23 時点、CLI 取得）: 1. Luca 1200.3 / 2. junlee789 1192.7 / 3. Majkel1337 1163.2 / 4. LumenLiquidity 1153.6 / 5. tw_shin 1136.9 … 12. Eduardo Rocha de Andrade（GM）1114.9。

---

## 1. 運営アナウンス・仕様の公式開示

### [727094] Updated game engine, sample submission file（ADMIN, 07-17）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/727094
- 717141 で報告されたバグ（下記 ToolCountProc）を受け、**07-17 にエンジンと sample submission を更新**。ローカルエンジンの再取得が必要。

### [716045] June 30 Update（ADMIN, 06-30）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/716045
- cg ライブラリに macOS / Linux ARM64 バイナリ追加。
- ステップ上限による引き分けを廃止 → 無限ループ側がタイムアウト負けに。
- **マッチ目標 48 戦/日/提出、マッチングの 10% はランダム対戦**に変更。
- レート差が大きい相手に勝っても +0 は仕様（Addison 回答）。

### [726690] Large systematic disparity in episode rates（07-16、Addison の詳細回答が重要）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/726690
- kurikuri54 の実測: 上位提出は 14–24 エピソード/時、下位は 2.4/時（6–10 倍差）。
- **Addison(STAFF) がマッチメイカー仕様を公式開示**:
  - マッチメイカーは **約 4 分毎**に実行。「必要度」= σ（不確実性）+ 経過時間、これに**レーティング依存の乗数（初期 600 比で最大 ~8 倍）**が掛かる。高レートほど多く戦う設計。
  - 相手選択: 自分のスコア中心の**ガウス窓による重み付きランダム**（+10% 完全ランダム）。
  - **対戦相手側として選ばれた試合でもレーティングと σ は更新される**。
  - 最低 48 戦/日を想定（ただし kurikuri54 実測は 20–29 戦/日で未達）。
  - **最終評価: 新規エピソードを生成し続けて不確実性を削減。中間期の試合数差は最終順位を決めない**（詳細な打ち切り条件・リセット有無への追加質問には 07-21 時点で未回答）。
- Santiago J.(rank 339): 上位ほどリプレイデータを多く得られる→学習データ格差という指摘。

### [708586] Differences Between the Official Rules and the Simulator（HOST sticky、07-22 まで更新継続）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/708586
- 公式ルールとの相違（宣言不能攻撃の事前除外、Mega Zygarde ex の対象順自動化、同時きぜつ時のサイド取り順）。**シミュレータ挙動が正**。
- コメントに有用仕様: `SETUP_BENCH_POKEMON` で `minCount==0` なら `[]` でベンチ出しスキップ可 / ABILITY=選択式・SKILL=常在（常在効果は自動適用）/ ベンチに下げると攻撃制限などの効果はリセット / Mega Lopunny の Gale Thrust はバンナー昇格→進化では 230 にならない（公式裁定: 正しい挙動）。

### [717141] Game Engine Source Code（ADMIN, 07-01, v117）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/717141
- `ptcg_engine.zip` を Data タブで公開。**派生・改変・コンパイルしたコードの submission への同梱は許可**（Addison 07-06 回答。ただしコンペ外利用・商用は禁止）。
- バグ悪用（exploit）は禁止、発見したらフォーラム報告。

### その他運営回答
- **[726708]** 時間制限は **600 秒/ゲーム、1 手あたりの制限なし**（Addison, 07-16）。
- **[724904][727929][728111]** 10% ランダムマッチは仕様。レート差過大時の +0/-0 も仕様。
- **[725074]** 優勝者への「ポケモンマスター」称号授与の要望（v18）→ 運営回答なし。
- **[728131]** エンジンの学術利用可否の質問 → 未回答。

---

## 2. エンジンのバグ・仕様判明（品質面で重要）

### リプレイ JSON の selected が 1 ステップずれる off-by-one（★BC パイプラインに直撃）
[717141] 内 Prema Ananda のコメント（07-09）:
- **ビジュアライザ用リプレイ（list 形式 JSON）の `selected` は 1 ステップ後ろにずれている**。`entry[0].selected` は常に null、entry[i] の実際の選択は `entry[i+1].selected` に入る。最終手はダミー終端ステップに入る。
- 原因は `Export.cpp` の `GetBattleData` が state 前進後に前ステップの `selected` を書くため。修正案も提示（`Api.h` の `ApiSelect` 内で `data->next()` 前にシリアライズ）。
- **これを補正せず BC すると「前の手を予測する」学習になる**。当プロジェクトの `data/imitation/*` 生成時に補正済みかの監査を推奨。

### ToolCountProc の変数シャドーイング → 07-17 修正済み
[717141] 内 KawattaTaido のコメント（07-12）:
- ロケット団専用エネルギーが非ロケット団ポケモンに付いた時の破棄処理で、外側ループ `i`（プレイヤー）を内側ループ `i`（エネルギー index）がシャドー → `MoveCard` に `activePlayerIndex()` が渡り、**相手側の盤面のエネルギーを間違って破棄 or out-of-range で例外→クラッシュ**。負けそうなプレイヤーが故意にクラッシュを誘発可能だった。→ これが 07-17 エンジン更新の内容。

### [728068] Ninetales #660 × Amarys #1207 で SIGSEGV（07-21、未修正）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/728068
- greySnow（自律エージェントが発見・報告）: キュウコンの技 Supernatural Shapeshifter が山札トップの Amarys（遅延効果サポート）の効果を借用すると、遅延スキルを**アタッカー側で lookup して null deref → エンジン子プロセスが signal 11 で死ぬ**。再現ノートブック: https://www.kaggle.com/code/shlomoron/ptcg-engine-crash-repro-nb
- この 2 枚を同時採用するデッキは避けるべき。相手が使う場合の挙動（エピソード無効？）は不明。

### [728287] 数学的に正しい 60 枚デッキが Step 0 で "Player 1's deck error"（07-22、未回答）
- Mega Charizard X / Y を合計 4 枚以下に調整、ACE SPEC 1 枚でも INVALID。ID パースの問題の可能性。デッキバリデーションの罠として注視。

### [728301] ローカル検証の実務知見（Busya PRIME, 07-22）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/728301
- 勝率の標準誤差表: 30 戦 ±18pt / 100 戦 ±10 / 400 戦 ±5 / 2500 戦 ±2（95%帯）。**100 戦で 0.52→0.57 は雑音**。
- エンジンが提示していない option index を返すと raise してそのゲームは消える。**この「違反率」を敗北と別に数えるべき**（数%でもレートを静かに抑圧）。`battle_start` のエラーオブジェクトの `errorType` でデッキ違反理由が分かる。
- 公開ハーネス: https://www.kaggle.com/code/busyaprime/test-your-agent-a-local-matchup-harness

---

## 3. LB 分散・提出戦略（コミュニティの合意事項）

### [712621] Leaderboard Scoring Inconsistency（v75）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/712621
- 同一エージェント 2 提出で 150〜400pt 差の報告多数（djschmit、Zhenyu Zhang ら）。
- Shun_PI(GM, rank 20) の 4 問題整理: ①収束後の試合数・変動が過小 ②提出直後の変動が過大→「当たりが出るまで再提出」が最適戦略化 ③運とマッチアップで収束値自体が大分散 ④対戦相手のレート窓が狭すぎ、上位は上位としか戦わず弱点が露呈しない。
- djschmit のシミュレーション: **Bo3 化で安定性が大幅改善、Bo5 以上は微増**（運営は未対応）。

### [727695] How do you tell if your new version is actually better?（Heisei, rank 219, 07-20）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/727695
- 8 提出の実測: **バイト同一 zip 2 本が 50pt 差**。1 勝差で 95pt 差。**最初の ~15 高 K 値試合でほぼ確定し、その後 20–70 戦しても平均 |drift| ≈ 15pt**。
- 結論: 公開 LB での A/B テストはほぼ無意味。ローカル評価 + 同一版複数提出が実務解。

### [728071] コメント欄の提出運用知見（Tony Li, 07-21〜22）
- スコア安定まで **7–12 時間**（他スレでは「最初の 5 時間が不安定」「最低 1 日」）。
- **アクティブ提出は 2 本まで**: 3 本以上あると直近 2 本しかマッチせず、最新版に試合が集中する。
- [728243] Tony Li が変動対応策を整理（実証済み提出の保護、seat-balanced なローカル数百戦 + 独立再実行での確認、同一提出の複製は「分散推定の実験」としてのみ使う等）。

---

## 4. 手法動向（誰が何をしているか）

### [724362] Top players' methods, revealed by 30,000 games（Abhyuday, v70, 07-10）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/724362
- 思考時間の統計から手法推定: **フィールドの大半はルールベース（約半分は手書き or 公開ボットのコピー）**。大半の手は ~0.03 秒。
- **トップ（当時 1 位）は重いモデルをロードしつつゲーム内時間もフル活用 → RL + bounded search と推定**。トップ層の残りは検索なしの高速 NN。
- コメント: Aji Samudra(rank 88) RL 1.7M パラメータ・ロード 8 秒 / 5M パラメータで 40 秒の例も / rank 44 曰く「ルールベース分類の多くは実際は RL」/ Abhyuday 自身は「value が正確でないと検索は効かない。不完全情報で高分散のこのゲームでは検索は難しい」。

### [728071] RL Beginner Question（07-21 開始、c45 の最活発スレ）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/728071
- **Tony Li (rank ~18 まで上昇)**: 公開リプレイ 21,957 games / 168,626 state-action で BC。policy accuracy 79%→95% だが **LB スコアと精度は相関しない**（似た版で 30–80pt 差）。RTX 4080。チェックポイント選抜は新版 vs 実績版 vs 公開エージェントのローカル総当たり戦で。
- **NguyenThanhNhan (rank 59)**: **純 BC ~21k games、H200 1 枚で 3–4 時間**で現スコア。「**同じチェックポイントでもデッキを替えるだけでスコアが激変** → デッキ選択が模倣・自己対戦と同格に重要」。
- Mikael Kerimov (rank 13): 100k games で精度 73–75%。Sayaka Miki (rank 192): 4M games で学習。
- greySnow: ゼロから PPO なら 1e7–1e8 self-play games が必要（1e7 は良い GPU 1 枚で可能）。「エンジンの GPU 移植は非自明」。
- Jake (rank 146): エピソード JSON の**約 50% は可視化用データで、除去すると容量半減**。
- 元データはみな Daily Top Episodes データセット（discussion/709160）から。

### [717697] Sharing my RL journey（Abhyuday, v34、純 self-play PPO の代表例）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/717697
- 公式バイナリのまま **7k steps/s ≈ 45 games/s、1 日で 3–5M games**、パラメータ <2M、カード語彙は**上位 250 種（LB ゲームの 95% をカバー）**に限定。「洗練されたカリキュラム」が効いたと明言。表現(observation)の質が最重要と繰り返し主張。
- **theredbluepill (rank 98): BC が土台（実力の 20–30%）→ 失敗モードが一貫していたので RL を上に重ね、さらに検索も**。generalist+specialist の併用がデッキ実験を速くする。
- Jake (rank 146-149): ローカルで学習 6 体 + 公開ルールベース 3 体のリーグ戦。ローカル順位は Kaggle と「概ね相関するが常にではない」。
- Ryan Rumble（現役競技プレイヤー・PTCG 上位 1%）による長文ドメイン知識: シーケンシング（汎用ドロー→サーチの順）、プライズマッピング、Crustle vs Alakazam の詳細（Enhanced Hammer 枯渇 vs Mist Energy のレース、Dudunsparce 回転、Dedenne テックで相性反転）、デッキごとのスキルフロア/シーリング論。

### [724187] Things I tried that didn't work（Yohei Nakajima、詳細ポストモーテム）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/724187
- 90 レポート分の失敗マップ。**信用してはいけないシグナル**の一覧が秀逸:
  - ランダム相手の勝率（66%→実エージェント相手 0.6%）/ 局所的に正しいルール追加（全体を悪化）/ **模倣一致率（不一致 <8% でも on-policy では弱い）**/ ミラー戦 RL の勝率（54.5% が場に転移せず）/ マリガン率改善（ミラー勝率は低下）/ オフライン加重フィールド勝率（ライブ順位と逆転）。
  - 高権限オーバーライド（強制ルール）は追加するほど悪化（26.2%→21.2%→20.0%）。
  - CRN（共通乱数）でクローン比較の分散 4.88 倍削減。ペア評価・座席交換・Wilson 下限での判定を推奨。
  - ladder は Elo 固定点: `settled ≈ mean_opp + 400*log10(p/(1-p))`。
  - Kaggle 実行環境は `__file__` 未定義の bare namespace。fail-closed の合法手フォールバック必須。

### [721338] Boss's Orders / Ultra Ball の教え方（e-toppo, GM, rank 81）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/721338
- Chrismaghuhn: 検索型なら発動条件は書かず評価関数に発見させる。手書きが効くのは**行動空間の枝刈り**（ハイパーボールの C(n,2) 破棄組合せは keep-value ヒューリスティックで上位 1–2 だけ展開、ボスは対象を prior で刈り、使うか否かは値比較）。「一度も発動しない」と「誤発動」を区別する計測を仕込むこと。
- djschmit: ボスはルール化しやすい（ベンチ KO 可能か、次ターン KO されるか）。ハイパーボールの「使わない判断」は多ターン地平で難しい。

### [723591] 先攻/後攻の統計（e-toppo, 07-07、5,333 games）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/723591
- 選択権を持つ側の **91.5% が先攻を選択**。先攻勝率 **55.2%**。
- 欲しい手番を実際に得られる確率: **後攻 ~96% / 先攻 ~54%**。→「後攻に強いビルド」は数少ない制御可能ポジションという仮説。

### その他
- **[728168]** ルールベースの最高到達点: 「一時 rank 2、普段トップ 10」（現 rank 21 のユーザー）。ルールベースの天井はまだ高い。
- **[727565]** 提出サイズ: 3MiB で 1000+ の例あり、100MB 勢もあり。サイズと強さは非相関。
- **[723576]** CPMP のスレ: ドメイン知識なしでも上位可能が多数派。**junlee789（現 2 位）「ポケモン知識ゼロ。RL が自分で学ぶ」**。Timmy Juicehouse(rank 67) は実店舗のジムでメタとマッチアップを学んでから RL。
- **[726696]** Heuristic vs RL 比較質問（回答なし）。[728159] コーディングエージェント用ベースプロンプト共有スレ（KISS/fail-fast 強制が有効との報告）。

---

## 5. メタ（流行デッキ）の変化

### [727816] How'd you pick your deck?（Ryan Rumble, 07-20）
https://www.kaggle.com/competitions/pokemon-tcg-ai-battle/discussion/727816
- メタ変遷の総括: **Abomasnow（+大量の Lucario）→ Crustle → Typhlosion（Crustle 対策）→ Starmie（両対応）→ Alakazam → 現在は Crustle と Alakazam が主流**。TR Mewtwo / Grimmsnarl / Garchomp / **Festival Lead** が上位に散発。
- 実トーナメントの近似フォーマット: https://limitlesstcg.com/decks?time=all&type=all&format=TEF-POR — Mega Lucario は Crustle に有利・Starmie 五分・Alakazam に不利。
- [717697] の Ryan 補足: Crustle は Ethan's Typhlosion にほぼ自動負け → **Crustle デッキに Typhlosion を混ぜる「ラダー最適化」ハイブリッドが出現**（現実ではあり得ない構築）。
- レーティングシステム上、上位が提出を控えるためメタが固着気味という指摘が複数（[712621]）。

---

## 6. 戦略レポート部門（pokemon-tcg-ai-battle-challenge-strategy）

- フォーラムは低調（13 トピック）。締切 **2026-09-13**。
- **[724094] ML は必須ではない（shige 公式回答）**: 評価表の「Model Score」の model は広義（ルールベース/検索/ヒューリスティック含む）。「強く、頑健で、よく設計され、レポートで明確に説明されている」ことが基準。**強いルールベース + 良いレポートで十分戦える**。
  https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy/discussion/724094
- **[724831] Rule 3.5.d（私的共有禁止）の公式解釈**: チーム外の人（例: 上級プレイヤーの友人）がリプレイをレビューして私的に助言するのは違反。**その場合は正式にチーム参加させること**（Addison）。コンペ固有の助言は公開リプレイ由来でも「私的共有」になる。
  https://www.kaggle.com/competitions/pokemon-tcg-ai-battle-challenge-strategy/discussion/724831

---

## 7. その他の注目トピック（本文未取得含む・一覧より）

| ID | 日付 | 票 | タイトル | メモ |
|---|---|---|---|---|
| 709160 | 06-17 | v66 | Daily Top Episodes Datasets (ADMIN) | 日次リプレイデータセット。BC 勢のデータ源 |
| 712657 | 06-23 | v58 | Is Battle Simulate Matching Process Working Well? | 初期のマッチング不信スレ |
| 709494 | 06-18 | v50 | [For First-Timers] Kaggle Rules You Should Know | |
| 708869 | 06-17 | v38 | Is there a way to view the visualizer without submitting? | |
| 710361 | 06-20 | v32 | A Vibecoded Website to View Metas and Cards | メタ閲覧サイト |
| 711741 | 06-22 | v26 | 【Question to Host】one agent が multi-decks 使用可か | |
| 713608 | 06-24 | v26 | What We Tried, What Ceilinged, and Two Questions | |
| 711329 | 06-21 | v22 | Proposal: official API extension for simulation/search agents | |
| 724421 | 07-11 | v-1 | 私のループエンジニアリング失敗の記録 | 日本語の失敗記録 |
| 724378 | 07-10 | v1 | Action Order: [0,2,4] vs [2,0,4] | 複数選択の順序が意味を持つか（未回答） |
| 724213 | 07-10 | v0 | Reliable Submission Checklist | `__file__`/sys.path/bare namespace 対策 |
| 726690 | 07-16 | v9 | （§1 参照） | |

---

## 8. 当プロジェクトへの示唆（サーベイヤー所見）

1. **BC データ監査**: リプレイ JSON の off-by-one（§2）が我々の `data/imitation/*` 生成に影響していないか要確認。ずれたまま学習していたなら policy accuracy が高くても弱い説明になる。
2. **07-17 エンジン更新への追随**: ローカルの cabt/エンジンが 07-17 build か確認。ロケット団エネ絡みのクラッシュ・仕様が変わっている。
3. **提出運用**: アクティブ 2 本まで・最初の ~15 戦で確定・安定まで 7–12h・同一版 2 本提出が事実上の標準。最終週は「実績版の保護 + 分散を見込んだ複数提出」戦略が必要。
4. **後攻対応**: 後攻は 96% の確率で取れる制御可能ポジション。後攻 1 ターン目の手順最適化は投資対効果が高い可能性。
5. **メタ**: Crustle / Alakazam 二強 + Festival Lead 台頭。Crustle+Typhlosion ハイブリッドのようなラダー特化構築も出ている。リツキの分布予測と突き合わせるべき。
6. **戦略部門**: ルールベースでも勝てると公式明言。我々のルール成熟プロセス（ルール毎強度・監査計器）はレポート素材として強い。締切 9/13 で simulation 締切後にも執筆時間がある。
