# marnie gen7 学習 — サーバ PPO 手順とローカル採否（2026-07-31）

前提: 「場の修正を先、その後 marnie 学習型」（ユーザー方針）。場の修正 = Phase 1 完了
（`research/meta/2026-07-31_field_rebuild.md`）。本書は Phase 2 の実行手順。
正典パイプラインは `docs/strategy/エージェント学習プロセス.md`。

## 出来ているもの（Windows 側・このセッションで生成）

- 教師データ: `data/imitation/marnie_bc7/2026-07-{22..30}.npz`（**700試合・27,127決定・
  被覆97.8%**。P-14/Gate A 合格。教師 = 実ラダー 1100+ の マリィのオーロンゲex 主流形、
  match-deck `decks/fleet/marnie_gold_luca_0723.csv`）。
- BC 初期値: `models/bc_gen7_marnie.npz`（holdout 日 = 07-30。一致率は train_bc の
  best holdout acc を参照）。
- 評価フィールド: `research/meta/2026-07-31_field.csv`（実測シェア）/ `2026-07-31_uniform.csv`
  （maximin）。相手6枠が実エージェント。

## Phase P — 模倣正則化つき PPO（サーバ gs83・数時間）

正典 §4/§4'。**λ（--bc-coef）序盤強く終盤弱く・勝利項が主・模倣項は錨**。頑健化 =
相手盲目化 PN_VERSION 2 ＋ 敵対的サンプリング（負けてる相手ほど高頻度 = soft maximin）。

```bash
# サーバへ: git push（bc7 npz と field csv を含める）→ サーバで pull
docker compose run --rm ptcg uv run python training/train_ppo.py \
  --agent agents/marnie_munkidori_rb --deck decks/fleet/marnie_gold_luca_0723.csv \
  --field research/meta/2026-07-31_uniform.csv \
  --exclude dragapult,other_megamimirop \
  --resume models/bc_gen7_marnie.npz \
  --bc-data "data/imitation/marnie_bc7/*.npz" --bc-eval-days 2026-07-30 \
  --bc-coef 0.3 --bc-coef-final 0.05 \
  --adv-tau 0.15 \
  --iters 60 --games-per-iter 256 --workers <物理コア-1> \
  --out build/ppo_gen7/marnie
```

判断のポイント:
- `--field` は **uniform**（maximin）を主計器に。`2026-07-31_field.csv`（実測シェア）は
  marnie が 54.7% でミラー過多になるため、頑健化には均等が向く（正典 §4'）。
- `--exclude` は holdout 汎化テスト用の 2〜3 アーキ。上例は dragapult / megamimirop を伏せる。
  marnie ミラー（相手=凍結ルール marnie）は自己対戦ではないので学習プールに残してよい。
- **監視**: history.csv の `bc_holdout`（学習中に大きく落ちる = プール過適合開始 → λ↑ or iter絞る）と
  `adv_minwr`（最弱対面 EMA の上昇 = 頑健化の計器。adv 時の win_rate は低めに出るのが正常）。
- デプロイ候補は `build/ppo_gen7/marnie/ema.npz`（winner's curse 対策）。

## Phase E — 評価・採否（Windows）

```bash
# L2 スクリーニング（新フィールド・ミラー除外）
uv run python scripts/gauntlet.py --agent agents/marnie_munkidori_rb \
  --deck decks/fleet/marnie_gold_luca_0723.csv \
  --field research/meta/2026-07-31_field.csv --exclude marnie \
  --net build/ppo_gen7/marnie/ema.npz --games 160
# 現行ルール marnie の同条件ベースライン（比較対象）: --net なしで同じコマンド
```

- 採否ゲート: **新フィールド L2 で +7pt ∧ holdout 3アーキ非劣化**（部品採否表・評価方法.md）。
  ただし絶対値は信じない（相手ピロットがルール強度）。真の審判は L4。
- L4: zip 作成（`--extra ema.npz=policy_net.npz`）→ `scripts/validate_episode.py` 合格 →
  スカウト枠で泳がせ。`research/ladder/scores.csv` で追跡（100戦未満は割引・±50-70ノイズ）。

## 注意（このセッションで判明した重要事実）

- **per-agent LB は較正の物差しにならない**（rho≈0）。場の妥当性は census 代表性で担保。
  → PPO の採否も「新フィールド L2 の相対改善 + L4」で見る（LB 絶対値の点推定に賭けない）。
- **シェア修正だけでは相手ピロットの操縦強度ギャップが残る**（chandelure が局所71%/LB674 の逆転）。
  次の一手 = PPO のプールに BC エージェント（人間模倣）を相手役として混ぜ、操縦強度を上げる
  （正典 §4' のプール多様化）。marnie gen7 が回ればその BC ネットが最初の「人間強度の相手役」になる。
- PN_VERSION: bc7 npz は現行 PN_VERSION で抽出済み（不一致なら train_ppo が fail-fast）。
