# 学習コード置き場

2026-07-11 の方針転換（探索は EXP-011 で reject・凍結保存 → モデルフリーへ）以降、
**主線は方策ネットの PPO**（実験計画 §4 段2「スコアラを NN 化したら方策勾配系へ切替」の実行）。
V(s) は critic の初期値として PPO に取り込まれた。θ（CEM）は φ 細分化まで棚上げ（EXP-006）。
①確定ルール（リーサル・負け筋カット・禁じ手）は聖域で、学習も探索も触れない。
設計の正典: [docs/strategy/エージェントアーキテクチャと実験計画.md](../docs/strategy/エージェントアーキテクチャと実験計画.md)。

## アーキテクチャ全体（どこに何を学習させるか）

```
choose()（agents/_base/policy_base.py）
  │ ①聖域: リーサル昇格 R-07 / 負け筋マスク R-08 / 禁じ手 …… 学習・探索の対象外
  │ ②ルールスコア（手書き φ + θ）…… 候補の絞り込み & move ordering
  ▼ MAIN・候補が割れている時だけ（SEARCH_SKIP_MARGIN）
ターン内探索（agents/_base/turn_search.py）
  │ 決定化: counting + R-20 matchup → opp_decks.py のリスト → search_begin
  │ 候補手ごとに:
  │   rollout 葉: 両側パイロット（自機クラス + GenericPolicy）で終局まで → 勝率
  │   value  葉: 自ターン終端まで貪欲展開 → V(盤面) ← ★学習対象
  ▼ 同じ隠れ世界で全候補を測る（paired）→ 平均が最大の手
選択
```

- **rollout 葉は訓練不要の基準線**（探索そのものの価値を測る物差し）
- **V(s) は rollout の代替**: 1評価 33ms → <1ms。同じ予算で数十倍の盤面を読める。
  さらに教師が実ラダーの対局なので「相手の応手の分布」が実データとして焼き込まれる
  （rollout の相手役 = 自前 bot は近似。V の方が場のモデルとして正確）
- **脅威分類器 P(threat) は尻尾の担当**: V（平均）が隠す「この盤面は10%で返しリーサル」を
  減点項として足す（葉 = V − λP。λ は gauntlet A/B で決める。v1 は λ=0 で未接続）

## V(s) / 脅威分類器の学習フロー

```
downloads/episodes/<day>/*.json      Daily Episodes（毎朝取得済みの資産をそのまま使う）
   │  extract_value_dataset.py      各ステップ×各視点 → 特徴量47次元 + ラベル
   │                                 y_win（最終勝敗）/ y_threat（2ターン以内にサイド損失）
   ▼
data/value/<day>.npz                （gitignore。再抽出は npz を消して再実行）
   │  train_value.py                numpy MLP（BCE+Adam）。分割はエピソード単位
   ▼                                 L0 = holdout AUC / ターン帯別 AUC / 較正表
models/value_v1.npz
   │  配備（2経路）
   ├─ ローカル評価: cp models/value_v1.npz agents/<deck>_rb/value_model.npz
   │                → gauntlet --search value で L1 A/B
   └─ 提出 zip:     build_submission --extra models/value_v1.npz=value_model.npz
```

重要な規約:

- **特徴量の正本は `agents/_base/value_model.py` の `extract_features` 一つ**。
  抽出（訓練）もエージェント（推論）も同じ関数を import する（train/serve skew の排除）。
  特徴量を変えたら `FEATURE_VERSION` を上げる → 版不一致の npz/モデルはロード拒否され、
  エージェントは rollout に自動縮退する（黙って壊れない）
- **分割はエピソード単位**（同一対局の行はラベルを共有するので行単位分割はリーク）
- **ベースラインは「サイド差だけのロジスティック」**。これを明確に超えない V に価値はない
- 合格の形: 終盤ほど AUC が高い（勝敗が盤面に書き込まれていく）+ 較正が単調

## 方策ネット PPO（EXP-012〜）

②選好スコアの NN 化。ルールが絞った **MAIN・maxCount==1・正帯候補**（聖域の外側だけ）を
softmax で再ランクする小型 MLP を、勝敗を報酬に PPO で直接最適化する。

```
choose()（policy_base.py）
  │ ①聖域 → ②ルールスコア（変更なし）
  ▼ _maybe_net: MAIN・maxCount==1・リーサル不成立・正帯(0<=s<100k)上位12件のみ
policy_net.npz があれば: logit = β·ルールスコア + MLP(状態71 + 候補37 + reason語彙)
  │   デプロイ = argmax（決定的）。npz 不在/版不一致/例外 → ルール順位に縮退（R-01）
  ▼
選択
```

設計の要点:

- **残差型初期化**: MLP 出力層ゼロ + β·正規化ルールスコア → 学習前の greedy は
  手書きルールと**完全一致**（shadow 100% で確認済み）。模倣θは使わない（EXP-002 の教訓）
- **critic は value_v3 から初期化**し GAE(γ=1, λ=0.95) — 終端しか報酬がなくても
  V(s) の TD 誤差が毎決定に密な信号を配る（potential shaping と等価な効果）
- **相手は gauntlet の凍結プール**（θ=0・ネット無し・シェア加重・holdout 3種除外）。
  自己対戦はしない（正典 §7.2）。ミラー行の相手も凍結版なので目的関数は動かない
- **デプロイ候補は ema.npz**（重みの指数移動平均 = μ 相当。EXP-006 winner's curse 対策）。
  latest.npz は --resume 用
- 特徴量・npz 形式の正本は `agents/_base/policy_net.py` 一つ（train/serve 共通。
  PN_VERSION + value_model FEATURE_VERSION の二重ガード、不一致はロード拒否→ルール縮退）

### BC（模倣）事前学習 → PPO 仕上げ（2026-07-15 新設。対象第1号 = フーディン）

「現行ルールエージェント = 初期値」から、ラダー支配ピロット（Yushin Ito 1184 / Majkel1337 1297、
同一の収束リスト）の選択へ MLP 残差だけを教師あり学習する。EXP-002 の教訓により
**BC 出力は直接デプロイせず、train_ppo --resume の初期値**にする。
採否ゲートは L0（holdout 日一致率）と L4（ラダー）。プール制圧度は参考値（ユーザー指示 07-15）。

```bash
# 1) 決定データ抽出（日毎。教師 = min-score 1180 の同型リスト使い）
uv run python training/extract_bc_dataset.py \
    --episodes downloads/episodes/2026-07-13 \
    --agent agents/alakazam_rb --match-deck decks/fleet/alakazam_top_0710.csv \
    --min-overlap 55 --min-score 1180 \
    --out data/imitation/alakazam_bc/2026-07-13.npz
# 2) BC 学習（時間ホールドアウト = P-10。最新日を --eval-days に）
uv run python training/train_bc.py --data "data/imitation/alakazam_bc/*.npz" \
    --eval-days 2026-07-13 --out models/bc_alakazam_v1.npz
# 3) PPO 仕上げ（サーバー）: BC npz を初期値に
docker compose run --rm ptcg uv run python training/train_ppo.py \
    --agent agents/alakazam_rb --deck decks/fleet/alakazam_top_0710.csv \
    --resume models/bc_alakazam_v1.npz \
    --iters 60 --games-per-iter 256 --out build/ppo/alakazam
```

- v1 実績（2026-07-15）: 教師 07-10+07-11 = 2,637決定 / holdout 07-13 = 3,617決定。
  **ゲート対象 MAIN の holdout 一致率: ルール 50.3% → BC 60.4%（+10.1pt）**。
  npz は `models/bc_alakazam_v1.npz`（git 追跡。サーバーは pull だけで PPO に入れる）
- 抽出のゲートは `_maybe_net` と同一（MAIN・maxCount==1・リーサル不成立・正帯上位12）。
  人間の選択が候補外の決定（負帯・13位以下）は skip して件数報告（≈10%）
- 特徴量は語彙なしで保存し train_bc が語彙確定後に one-hot 展開（extract_features と厳密一致）。
  PN_VERSION / FEATURE_VERSION を npz に焼き込み、不一致は再抽出を要求

### サーバー実行手順（gs83）

```bash
# 0) 初回のみ: docker compose build && docker compose run --rm ptcg uv sync
git pull
# 1) 勾配実装の自己検証（エンジン不要・数秒）
docker compose run --rm ptcg uv run python training/train_ppo.py --self-test
# 2) 本番学習（60 iter × 256 games ≈ 3〜4時間、CPU のみで可）
docker compose run --rm ptcg uv run python training/train_ppo.py \
    --agent agents/marnie_munkidori_rb \
    --deck decks/fleet/winrate_2_marnie_grimmsnarl.csv \
    --iters 60 --games-per-iter 256 --out build/ppo/marnie
# 3) L2 screening（80試合、holdout除外8対面）: OFF vs EMA
docker compose run --rm ptcg uv run python scripts/gauntlet.py \
    --agent agents/marnie_munkidori_rb \
    --deck decks/fleet/winrate_2_marnie_grimmsnarl.csv \
    --exclude okidogi,lopunny,rocket --games 10 --net off
docker compose run --rm ptcg uv run python scripts/gauntlet.py \
    --agent agents/marnie_munkidori_rb \
    --deck decks/fleet/winrate_2_marnie_grimmsnarl.csv \
    --exclude okidogi,lopunny,rocket --games 10 --net build/ppo/marnie/ema.npz
# 4) screening +7pt 以上なら確定測定（--games 40 = 320試合）+ holdout 非劣化
#    （--only okidogi,lopunny,rocket --games 30）
```

- 進捗は `build/ppo/marnie/history.csv`（iter 毎の win_rate/entropy/kl/vloss）。
  学習中の win_rate は**サンプリング方策**の値なので greedy より低く出る（正常）。
  greedy の参考値は --eval-every の eval 列
- 中断→再開: `--resume build/ppo/marnie/latest.npz`（Adam 状態は初期化される）
- 採用時のデプロイ: `cp build/ppo/marnie/ema.npz agents/marnie_munkidori_rb/policy_net.npz`
  （ローカル評価用）/ 提出 zip は `build_submission --extra build/ppo/marnie/ema.npz=policy_net.npz`

## 評価の漏斗（探索部品用。番号は 評価方法.md の5層に統一）

| 層 | 物差し | コマンド |
|---|---|---|
| L0 | holdout AUC・較正・shadow 一致率（対戦不要） | `train_value.py` / `ab_battle.py --shadow` |
| L1 | 不変条件 | `check_agent.py` |
| L2 | gauntlet 制圧度の A/B + holdout アーキタイプ非劣化 | `gauntlet.py --search off\|rollout\|value` |
| L4 | 実ラダー（スカウト枠泳がせ 2〜3日） | 提出前に `validate_episode.py` 必須 |

注意: 探索ONの対戦は 4s/試合（value葉）〜23s/試合（rollout葉・1決定1秒）。
L2 確定 320 試合 = value 約20分 / rollout 約2時間（サーバー or 夜間）。

## ファイル

| ファイル | 実行環境 | 役割 |
|---|---|---|
| `train_ppo.py` | サーバー推奨（numpy のみ。対戦生成が主コスト） | **主線**。方策ネットの PPO。`--self-test` = 勾配数値検証 |
| `extract_value_dataset.py` | Windows（生エピソード必要） | エピソード → data/value/<day>.npz |
| `train_value.py` | どちらでも（numpy のみ） | 学習 + L0 評価 + models/*.npz 出力。`--target win\|threat`。v3 は PPO critic の初期値 |
| `extract_decisions.py` / `fit_theta.py` | Windows | （θ 系・棚上げ中）模倣データ抽出 / 模倣θ推定 |
| `optimize_theta.py` | サーバー | （θ 系・棚上げ中）CEM。EXP-006 の構造的限界により φ 細分化後に再検討 |

## θ 系の記録（棚上げの経緯）

- 模倣θの直接デプロイ不可（EXP-002: L0改善・L1 −18pt）
- CEM は現行 φ の粒度では探索地形が平坦か崖で、選抜の SNR≈0（EXP-006）。
  θ は reason 単位の一律シフトしかできず、状態依存の判断を表現できない
- この限界の解が探索アーキテクチャ（EXP-007 のスパイクで実証 → 2026-07-10 実装）
