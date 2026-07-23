# 外部発信サーベイ 2026-07-23（X・ブログ・GitHub・公開Notebook）

調査日: 2026-07-23。対象コンペ: Kaggle `pokemon-tcg-ai-battle`（ポケカABC）。
調査手段: WebSearch（日英）、WebFetch（GitHub検索6ページ中5ページ・各リポジトリ・raw README/CLAUDE.md）、Kaggle CLI（kernels list / pull）。

---

## 1. 最重要: wmh/ptcg-abc の更新（6/25 以降、大幅追記あり）

- URL: https://github.com/wmh/ptcg-abc （★4、最終更新 7/21〜22）
- **CLAUDE.md は 6/25 以降も毎営業日級で追記されており、7/21 まで更新確認**。コミット例:
  - 7/13「Alakazam v4 Xerosic anti-mirror package」
  - 7/14「v4.1 Xerosic rush-gate + v3 同時窓 A/B」＋ frozen v3.1 を A/B 対照として保存
  - 7/16「v4.2 Archaludon fortress-gate（検証済み・未提出）」
  - 7/17「v4.2 SHIPPED + **ladder matchmaking mechanics decoded** + Luca dual-track mining」
  - 7/21「v4.2 ladder A/B WON (765.2 converged) + mirror autopsy + v4.3 escape-fuel」＋ `_ab_v42_frozen` 追加
- **agents/ ディレクトリは 23 個に拡大**（GitHub API 実測）: `_ab_v3_frozen, _ab_v41_frozen, _ab_v42_frozen, _base, alakazam, alakazam_mist, archaludon, bellibolt, chandelure, dragapult, dragapult_nobonus, froslass, garchomp, grimmsnarl, grimmsnarl_luca, kangaskhan, lucario_v3, megastarmie, megastarmie_v2, mewtwo, ogerpon, trevenant, typhlosion`。6月時点の3体構成から大幅拡張。凍結版を A/B 対照として同居させる運用。

### CLAUDE.md の新知見（6/25→7/21、raw 取得の要約）
- **ラダー機構の逆解析（7-17、エピソードAPIより）**:
  1. 新規提出は最初の6時間に 50–140 試合（~23試合/時）消化、その後旧提出は 1–2 試合/時に減速
  2. K 値は急減衰: 初期600 → 初戦±60–120 → 60戦目で±4
  3. 序盤のマッチング相手プールは系統的に弱い（最初の20戦の相手平均 Elo 635）。ピーク Elo は 20–60 戦目に出やすく、100 戦超で真の実力へ回帰
  4. **「100戦未満のスコアは割引いて見る」**——自身の 860.3 は未収束サージで、真の収束は 130 戦超で 765 前後
- **divergence mining（上位者の決定採掘）を柱に**: Majkel（Alakazam、MAIN 決定 7,275 手）、keidroid（ラダー1位 1341.9、Mega Starmie/Cinderace）、kashiwashira（TR Mewtwo ex、上位帯勝率 63.2% で「メタ頂点」と評価）から実試合決定を採掘し操縦修正。Megastarmie は 6 修正で対 Dragapult 40%→66%
- **「pointwise agree ≠ 実戦の勝ち。mirror A/B は必須の毒検出器」**: 局所ロジック改善に見えた4候補ルールが frozen v3.1 相手のミラー A/B で全崩壊。ミラー A/B ＋ gauntlet の両方を通ったものだけ採用
- **v4.2 の主戦場（132戦全リプレイ精査）**: ミラー Alakazam が field の 25.8%（勝率44.1%）で最大の失血点。敗因の典型は「エネ0の Fezandipiti ex がボスで前に釘付け」（敗戦11回 vs 勝戦2回）→ 対策 `escape_fuel()`（前線エネ0・逃げ1以下・ベンチに準備済み Alakazam があるとき逃げ用エネを1枚貼る）。Archaludon 21.2%/勝率53.6%、Mega Lucario 11.4%/67%
- Grimmsnarl 操縦の要点:「序盤エネは未進化体+Munkidori に貼る」= Alakazam と全く違う配分

---

## 2. Jun-Morita/kaggle-ptcg-ai-battle（7/22 push、実験台帳が超高密度）

- URL: https://github.com/Jun-Morita/kaggle-ptcg-ai-battle （Claude Code 運用のワークスペース。README が日次実験報告になっており一読の価値大）
- 立ち位置: **Hop's Trevenant 非ex の LO/ミル（koff）** ~918、silver cut 916.8（271位）/ **全5,437チーム**。最終評価は「締切後約2週間の継続対戦」＝真の強度が効くという前提で運用
- **RL・最適化のネガティブ結果を25件、機構付きで公開**（Actor-Critic、sNES 69次元、デッキGA、探索汎化など全滅）。例外は exp041（AlphaGo型 教師あり→MCTS→自己対戦）の限定ポジのみ
  - **exp064: BC クローン top-1 一致率 0.78 → 教師本人への勝率 0.122**。「decision-match ≠ strength」の最鮮明な定量化（当方 EXP-002 の marnie 模倣θ否定と完全同型）
- **計測規律の教訓**: CRN（共通乱数）ハーネスが実は一度も効いていなかったバグを提出直前に発見（同一エージェント2回走行の不一致で検出）。「CRN を使っている」は毎回同一シード完全一致で検証せよ。API 属性名は推測せず実物を読み null 率チェックを標準計装に
- **Kaggle discussion からの外部情報（本人が60スレッド/297コメントを収集）**:
  - disc726690（**スタッフ公式回答**): マッチメーカーは新規提出・高σを大幅優先 → 高止まり枠は試合頻度が落ちて自然保護。リロール運用の裏書き
  - disc727695: 他チームの8提出統制実験で **バイト同一の提出が 873 vs 923 ＝ 50点差**。「ラダー A/B はほぼ無意味」「2枠同時提出は良い戦術」
  - disc727565: **提出サイズとレートに相関（1MB=800-950 / 3-10MB=990-1000+）**。純ヒューリスティック 499KB で ~918 の同氏は「RL 無効でなく予算・実装が届かなかった」説に言及
- **提出運用モデル**: レートは「固定点まわりのランダムウォーク」。day1-2 で ≥850=健全 / <800=低 basin トラップ / 800-850=グレー。基本は両枠 HOLD、リロールは <~820 で 24-36h 停滞時のみ
- **deck ⊗ pilot 結合則**（3度確認）: 同一60枚でもパイロット差で勝率 0.5 動く（exp055）。LB#4 kashiwashira はリスト 56/60 一致でも勝てない＝障壁はパイロット。公開物の採用スイープは「パイロット付き」に限定
- **公開ノートブックの罠（exp066）**:「LB 950+」を謳う公開エージェントの探索が完全な死にコード（search_begin 0回）、**著者の実順位は 4078位/506.1**。→ 採用前に著者本人の LB 順位照合＋主要機構のコールカウント計装をルール化
- **exp072**: 公開 notebook prvsiyan「Metagame-Resilient Control」が自軍 koff とデッキ60/60完全一致 → ミラー直接対決で自軍パイロット 0.588 vs 0.412（n=600, z≈4.3）。「同一デッキ拡散はパイロット差の土俵が増えるので追い風」
- **v025 として一時採用した公開資産**: tientrum の **search-augmented Alakazam（実ラダー収束 1034.6）** ＝調律済み重み表＋2-ply 信念サンプリング bounded search。「探索は効かない」通説への限定的反例（ただしミラー 0.35・対 dragapult 0.36 の穴で 884 律速→枠転換）

---

## 3. メタ動向（公開 Notebook・各リポジトリ横断）

- **myso1987「PTCG AI Battle: Leaderboard Deck Meta by Score Band」**（42票、隔日更新、最終実行 7/22）
  - https://www.kaggle.com/code/myso1987/ptcg-ai-battle-leaderboard-deck-meta-by-score-band
  - LB チーム毎に1デッキをリプレイから復元し、100点刻みスコア帯（500-599〜1100+）でアーキタイプシェアを集計。帯別メタの定点観測として現在の事実上の標準。分類ルール21種に **Team Rocket Mewtwo / Mega Clefable / Mega Greninja / Festival Lead (Dipplin) / Hop Snorlax** 等が既に入っている点がメタの広がりを示す
  - 手法出典: llccqq624「PTCG Replay Data Miner」 https://www.kaggle.com/code/llccqq624/ptcg-replay-data-miner
  - 注: kernels output は空（出力非公開）。CLI では結果表は取れず、ノートブック閲覧が必要
- **pilkwang「Meta Snapshot」シリーズ**: https://www.kaggle.com/code/pilkwang/pokemon-tcg-lucario-alakazam — タイトルが「09 July」→「**18 July**」に更新済み（継続運用）。Jun-Morita の引用によれば **TR Spidops が field 全帯域で 1.4%→12.3% に急伸**
- 帯別シェアの具体値（Jun-Morita が myso 分類を引用）: 純 Crustle Wall（Tusk なし）**9.33%**、Great Tusk+Crustle **<1.33%**。同氏の silver 帯ではミラー相手の Alakazam 系が 43%
- wmh 側の上位帯観測: TR Mewtwo ex（kashiwashira）が上位帯勝率 63.2% で頂点、Grimmsnarl ex / Kangaskhan ex / Cynthia's Garchomp ex が Elo≥1000 で支配的（7月初旬時点の記述）。新 LB#1 の LumenLiquidity（Dragapult 型）は 1199→1110 で #11 に転落（Jun-Morita 診断と整合、首位は不安定）

---

## 4. GitHub 新規・注目リポジトリ（検索56件中、7月更新分中心）

探索ベース勢の台頭が目立つ:

| リポジトリ | 手法・内容 | 更新 |
|---|---|---|
| **henriquetakahiroito/pokemon-tcg-ai-battle** | エンジンの search_begin/search_step API 上の **determinized flat-UCB MCTS ＋ numpy value-net**（MLP 32→64→64→1、PyTorch で学習し numpy 推論のみで提出）。決定化は可視状態と整合する相手デッキ/手札サンプリング。episode JSON 6,533 件からデッキ選定。**hops_hybrid で提出1時間で948**、v2 が対 baseline 79% | 6日前 |
| **souyuukou/pokemon-tcg-ai-battle3 / 4** | C/C++。battle3=「exact, information-safe turn search」、battle4=「**boundary-evaluated information-set DAG search**」。ネイティブ実装で情報集合探索を回す本格路線 | 5日前/昨日 |
| **SebAustin/ptcg-ai-battle-challenge** | **Determinized IS-MCTS**（K 世界の信念サンプリング→各世界で bounded MCTS→PIMC 投票）。Cowling et al. 準拠。Heuristic→Tuned→Search→Learned の段階提出計画。まだ足場段階 | 5日前 |
| **brunoramosmartins/ptcgabc-ismcts** | ISMCTS 研究プロジェクト | 11日前 |
| **Fukami1213/pokemon-tcg-ai-battle-flygon-search** | フライゴン・強化学習編: BC(α=0.10) ベース vs trust-gated Search の比較を **DR-learner（doubly robust off-policy）** で uplift 推定。Phase 1B〜3C のランダム化実験構造。「held-out レビューまで DR モデルを live 投入するな」と自戒 | 2日前 |
| **fullvaluedan/ptcg-abc** | 「autonomous self-improving agent」——watchdog / autoloop / **council（多エージェント合議）** 構成、488 コミット。中身は競技中につき非公開と明記 | 6日前 |
| **satory074/ptcgai-deck** | 参加エージェント ptcgai の**現行デッキ公開サイト**（Astro/GitHub Pages、deck.json + 改訂履歴、コンペデータ・カード画像は排除するコンプラ設計） | 7日前 |
| **Leundai/cabt-replay-viewer** | Svelte 製 CABT リプレイビューア（★3）。ptcgvis 代替のローカルツールとして注目 | 4日前 |
| **goldbar123467/ptcg-meta-bench** | メタ加重ローカルベンチ・ハーネス（当方 gauntlet と同発想） | 20日前 |
| その他7月更新 | sota1111（ume/sol の複数ワークスペース、43分前更新＝現役）、trevoreliot、Beiciccc、ErliCai、atsushi11o7、IMINABO1(C)、shreyas463、tuannm3812、yowayani517（rule-based/RL/planning/forward search 併記）、cha7ura（learned card-policy）、1ulce（Rust WebSocket クライアント+Dragapult ボット） | — |

- 検索: https://github.com/search?q=pokemon-tcg-ai-battle&type=repositories&s=updated （56件、p1〜p5 を確認。p6 は6月中旬の初期リポジトリ帯で未精査）

---

## 5. ブログ（note / zenn / Qiita）・ニュース

7月の**技術的な参加記は乏しい**。ヒットの大半は6月開幕時の紹介記事:

- zenn: kkj「【めざせカードマスター】Kaggleコンペ紹介」 https://zenn.dev/kkj/articles/85a3a0a08f193c （6月、コンペ紹介）
- Qiita: Te2hi-ro「ポケカABCにチャレンジ #1」 https://qiita.com/Te2hi-ro/items/db57cc682c1fb71eeb9c （6/18。WebFetch は404＝限定公開化の可能性。続編は検索で未確認）
- Qiita: sc-nakamura「kaggleでポケモンカードのコンペ！？」 https://qiita.com/sc-nakamura/items/9dc67173f0abf5581afb （初心者参加記）
- note: なぞなぞ博士「ポケカABCに参加しよう！」 https://note.com/riddles/n/nff77dab68fee ／ ひど（ポケカプレイヤー視点）「ポケカABCが気になる人へ」 https://note.com/pokeka_ryo/n/n3873f44cc783 ／ YGPuzzleGTANT「ポケカKaggleに参加する人のために」 https://note.com/213414/n/n9846064b4ea1 ／ やきいも https://note.com/yakiimo_blog/n/n71a63378b943
- note: venom「AIエヴァンジェリストとして参加します」（進捗連載を予告）→ **現在404**（削除または限定公開）
- pokebros.net: 「AIはどうやってポケモンカードをプレイするのか？」「コンペを調べてみた」——TLS 証明書エラーで取得不能（試したが収穫なし）
- ニュース系（6月開幕報道のみ）: AUTOMATON / こどもとIT / ORICON / AICU / aismiley / PokeBeach / Plus Web3

## 6. X（Twitter）

**未ログインの制約で本文取得はほぼ不能**（x.com は WebFetch で 402）。検索エンジン経由で拾えた範囲:

- 公式・共催の開幕告知: @Pokemon_cojp（6/16）、@MatsuoInstitute
- @umireon「ポケカABCで優秀な成績を収めるために必要なことは…」（本文取得不能）
- @kabu_0508（深瀨風歩、ポケカ 2025 日本1位・2026 日本2位）: 「カード知識は誰にも負けない、チームメンバー募集」＝**トッププレイヤーが AI 側人材を募ってチーム参戦する動き**
- @peke_pcg: データサイエンス経験者の参戦表明
- 7月分のハッシュタグ・レート報告ツイートは検索エンジンからは回収できず（「試したが収穫なし」: `#ポケカABC` の x.com 限定検索、`ポケカABC レート/提出/順位 7月`、ptcgvis.heroz.jp 言及検索）

## 7. 試したが収穫なし（探索経路の記録）

- `site:x.com` / `site:twitter.com` の7月投稿検索 → 6月開幕時の投稿しか出ない。X 本文は 402（未ログイン制限）
- pilkwang / myso Notebook の WebFetch → タイトルのみ（Kaggle は JS レンダリングで本文不可）。`kaggle kernels output myso1987/...` → 空（出力未公開）。**pilkwang のノートは CLI の kernels pull も404**（slug 変更か非公開ソース）
- note venom 記事 404、pokebros TLS エラー、Qiita Te2hi-ro 404
- 「ポケカABC リーダーボード メタ」等の日本語検索はポケポケ（TCG Pocket）記事に汚染されがち
- reddit の議論スレは表面化せず（英語圏の個人発信は GitHub / Kaggle Notebook に集中している模様）

## 8. 当方への示唆（要約）

1. **ラダー計測の常識が外部で確立しつつある**: 新規提出ブースト・K減衰・serve バイアス・「100戦未満は割引」・バイト同一50点差・2枠HOLD戦術。当方の「泳がせ時間較正」「好調枠は置き換えない」方針は外部知見（スタッフ回答 disc726690 含む）と一致。scores.csv 分析に「試合数<100 は未収束」の注記を入れる価値あり
2. **模倣の限界の相互確認**: 「decision-match 0.78 → 対教師勝率 0.12」（Jun-Morita）と「ミラー A/B は毒検出器」（wmh）は、当方 EXP-002 の負例・ミラー除外ゲート（L0/L4）と同じ結論。外部2チームが独立に同じ罠を踏んで同じ対策に到達
3. **メタ**: TR Mewtwo ex が上位帯頂点、TR Spidops 急伸（1.4→12.3%）、Alakazam ミラー飽和、Crustle 純壁 9.33%。ミラー対策（gust-lock 対応の escape_fuel 的ルール）は当方デッキ群にも横展開の検討価値
4. **探索勢の台頭**: tientrum の 2-ply belief search Alakazam が実ラダー 1034.6、提出サイズとレートの正相関（3-10MB=990-1000+）。当方は EXP-009/011 で木探索を reject したが、「浅い探索＋調律済み評価」の形なら上位帯の実例がある——AZ+belief 棚上げ判断の再評価材料
5. **公開資産の検収規律**: 著者本人の LB 順位照合＋主要機構のコールカウント計装（死にコード検出）を、外部 Notebook 取り込み時のゲートに追加すべき
