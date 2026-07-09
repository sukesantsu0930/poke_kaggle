# archaludon_rb — ブリジュラス（Archaludon ex + Cinderace）

設計文書: `docs/planning/デッキ設計_ブリジュラス.md` / `docs/planning/用語とターン手順.md` / `docs/planning/ルール抽出_オープン実装.md`

土台: Kaggle 公開 Notebook "A Sample Archaludon"（masamikobayashi、対 1300+ Starmie 74.4%）。
そこに**ターン手順の層**（リーサル判定・負け筋カットの常時実行）を追加したのが v1。

対応デッキ: `decks/candidates/archaludon_cityleague.csv`（シティリーグ準優勝リスト、ボス×4）

## ルール ↔ コード対応表

| ルール | 内容 | 実装箇所（main.py の関数） |
|---|---|---|
| S-0 | サブゴール判定「ブリジュラスが技をうてる」 | `judge_subgoal` → `_T["phase"]` |
| R-07 | リーサル判定（常時・閉形式）と勝ち切り手の昇格 | `judge_lethal` + `apply_protocol`（LETHAL_BAND） |
| R-08 | 被リーサル判定（ボス想定・全盤面露出・辞書式緩和） | `judge_loss_threats` + `score_target`（前出しマスク）+ `should_skip_ice_cream`（回復強制）+ `attach_target_score`（追い銭防止） |
| R-20 | マッチアップ検出 | `detect_matchup` → `_T["matchup"]` |
| R-08入力 | 相手最大打点テーブル + アラカザム floor/ceiling | `opp_max_damage` / `_estimate_alakazam` |
| R-01/R-02 | 例外=敗北、合法手クランプ | `agent`（try/except）+ `_legal_fallback` + `choose_options` |
| R-03 | ドンク回避（ベンチ0でUltra Ball強制） | `score_play`（"donk risk" 分岐） |
| R-04 | スコア帯=行動順序（ワザは最後） | `score_option` の MAIN 分岐全体 |
| R-10相当 | エネ過剰付与マスク（3枚上限=Metal Defenderコスト由来） | `attach_target_score`（e>=3 → -5000） |
| R-11系 | 山札切れガード（低山札でドロー封印） | `apply_overrides`（Explorer/Lillie 分岐） |
| R-13 | 勝ち筋ライン保護（捨てない） | `score_discard`（Archaludon/Duraludon 負スコア） |
| R-15 | スナイプは低HP優先 | `score_target`（DAMAGE 分岐） |
| R-21/R-22 | 先攻/マリガン（暫定: 後攻・マリガンNO。**要データ確認**） | `score_setup` |
| S-1 | 経路A: エースバーン始動（Explosiveness） | `score_setup`（SETUP_ACTIVE）+ `score_option`（ACTIVATE） |
| S-2/S-5 | エネはジュラルドン系統へ集約 | `attach_target_score` / `score_attach` |
| S-3 | ジュラルドン2体構え | `need_duraludon` / `score_to_hand` |
| S-4 | Assemble Alloy 連動（進化タイミング・エネのトラッシュ送り） | `alloy_attack_energy_route` / `score_evolve` / `score_discard`（UB分岐） |
| 経路B | エースバーン不発時（Ultra Ball で鋼エネをトラッシュへ） | `score_play`（"fuel Alloy"）※専用フェーズは未実装 |
| E-2 | 攻撃計画（Metal Defender 220 デフォルト / Raging Hammer 切替） | `planned_archaludon_attacks` / `best_attack_damage` |
| E-3 | ボス多段（吊り出し/温存/スタール）・回復閾値・マッチアップ上書き・前ターン技追跡 | `score_play`（BOSS）/ `should_skip_ice_cream` / `apply_overrides` / `_update_opp_attack_tracking` |
| P-04 | (score, reason) で採択理由を追跡 | 全スコアラー |

## v1 の既知の制約（次版候補）

1. リーサル判定の射程は「単発KO + ボス吊り出しKO」。ばら撒き複数KO・複合手は探索版（Search API、R-23の時間プール消費）で。
2. 相手最大打点テーブルが6月メタ（Marnie/Munkidori 未対応）。エピソード分析から更新する。
3. R-21/R-22（先攻・マリガン）は参照実装の踏襲。上位 Archaludon 使いの divergence 分析で確定させる。
4. 経路Bは Ultra Ball 分岐のみで、専用の優先則セットは未実装。
