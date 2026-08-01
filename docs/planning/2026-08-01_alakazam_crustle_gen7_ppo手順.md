# alakazam（フーディン）/ crustle（イワパレス）gen7 学習 — サーバ PPO 手順（2026-08-01）

marnie gen7（`2026-07-31_marnie_gen7_ppo手順.md`、L2 +7.3pt で採用候補）と同じパイプラインを
2デッキへ横展開。場は 07-31 再構築済み（`research/meta/2026-07-31_field_rebuild.md`）。

## 出来ているもの（Windows 生成済み・このセッション）

| デッキ | 教師データ | 教師量 | 被覆 | BC holdout（vs ルール） | BC npz |
|---|---|---|---|---|---|
| alakazam | `data/imitation/alakazam_bc7/*.npz` | 419試合/18,164決定 | 88.6% | **64.6%（47.0）+17.6pt** | `models/bc_gen7_alakazam.npz` |
| crustle | `data/imitation/crustle_bc7/*.npz` | 207試合/6,894決定 | 94.1% | **47.7%（35.1）+12.6pt** | `models/bc_gen7_crustle.npz` |

- 教師 = 実ラダーの主流形（match-deck: alakazam `alakazam_top_0710.csv` = ケーシィ/ユンゲラー/
  フーディン/ノコッチ、min-score 1050 / crustle `crustle_wall_top.csv` = イシズマイ/イワパレス/
  メガガルーラ、min-score 1000）。holdout 日 = 07-30。
- 注記: alakazam 被覆 88.6% は Gate A(95%) 未達＝現行ルールが現メタのフーディン教師をやや刈り気味。
  BC は候補内並べ替えを学ぶので進めるが、PPO 後も対面が伸び切らなければ Phase R（ルール成熟）へ戻す。

## サーバ（gs83）PPO — tmux で（`--workers 7`、i7-7700K 4C/8T）

```bash
cd ~/work/poke_kaggle && git pull origin main
tmux new -s gen7_ala   # crustle は別セッション gen7_cru で

# ── alakazam ──
docker compose run --rm ptcg uv run python training/train_ppo.py \
  --agent agents/alakazam_rb --deck decks/fleet/alakazam_top_0710.csv \
  --field research/meta/2026-07-31_uniform.csv \
  --exclude dragapult,other_megamimirop \
  --resume models/bc_gen7_alakazam.npz \
  --bc-data "data/imitation/alakazam_bc7/*.npz" --bc-eval-days 2026-07-30 \
  --bc-coef 0.3 --bc-coef-final 0.05 --adv-tau 0.15 \
  --iters 60 --games-per-iter 256 --workers 7 \
  --out build/ppo_gen7/alakazam

# ── crustle ──
docker compose run --rm ptcg uv run python training/train_ppo.py \
  --agent agents/crustle_rb --deck decks/fleet/crustle_wall_top.csv \
  --field research/meta/2026-07-31_uniform.csv \
  --exclude dragapult,other_megamimirop \
  --resume models/bc_gen7_crustle.npz \
  --bc-data "data/imitation/crustle_bc7/*.npz" --bc-eval-days 2026-07-30 \
  --bc-coef 0.3 --bc-coef-final 0.05 --adv-tau 0.15 \
  --iters 60 --games-per-iter 256 --workers 7 \
  --out build/ppo_gen7/crustle
```

学習後、サーバで成果を push（marnie と同じ）:
```bash
# sudo chown -R suketomo:suketomo build/ppo_gen7   # docker(root)所有なら
git add -f build/ppo_gen7/alakazam/{ema,latest}.npz build/ppo_gen7/alakazam/history.csv \
           build/ppo_gen7/crustle/{ema,latest}.npz build/ppo_gen7/crustle/history.csv
git commit -m "alakazam/crustle gen7 PPO 出力" && git pull --rebase origin main && git push origin main
```

## Windows 側 L2 採否（私が実行）

各デッキで新フィールド・ミラー除外・160戦、ルール版 vs `--net ema.npz` を比較。
ゲート = **+7pt ∧ holdout非劣化（dragapult / megamimirop）**。合格なら zip（`--extra ema=policy_net`）
→ validate_episode → スカウト枠。監視は history.csv の `bc_holdout`（崩れ）と `adv_minwr`（最弱対面）。

## 期待

alakazam は marnie の最大の壁（17.9%・marnie 対 alakazam を gen7 が +9.4 で埋めた相手）。
alakazam 自体を強くすればラダー上位帯（1100+ で alakazam 10%）にも効く。crustle（イワパレス）は
メガガルーラの硬い盤面で marnie/dragapult に強い枠。両方が「人間強度の相手役」になれば場の質も上がる。
