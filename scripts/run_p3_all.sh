#!/usr/bin/env bash
# サーバー §P4 一括実行 — 頑健化 第4陣（5デッキ）の学習から結果 push まで全自動。
#
# 使い方（gs83・リポジトリ直下で）:
#   tmux kill-session -t ppo 2>/dev/null; git pull && tmux new -d -s ppo 'bash scripts/run_p3_all.sh; exec bash'
#   tmux attach -t ppo                        # 進捗を覗く（デタッチ: Ctrl+b → d）
#   tail -f build/ppo_robust2/run_all.log     # attach せずログだけ見る
#
# 第3陣（EXP-032）からの変更点 — 収束診断（学習末期に minwr がまだ +0.12〜0.25pt/iter で
# 上昇中・approx_kl が上限 0.03 の 5% しか使われず・エントロピーが初期比 81〜92%）を受けて、
# **更新幅と学習長を引き上げる**:
#   --lr 3e-4 → 1e-3 / --iters 60 → 200 / --ent 0.01 → 0.02
#   （--target-kl 0.03 のブレーキは据え置き = 動きすぎた iter は自動で更新打ち切り）
# 出力先は build/ppo_robust2/（history.csv は追記仕様のため世代ごとに分ける）。
#
# 1デッキ ≈ 35〜45分 × 5本 ≈ 3〜4時間。失敗したデッキはスキップして続行し、
# 成果物（ema.npz / history.csv）があるものだけ commit & push する。
set -u
cd "$(dirname "$0")/.."
OUTROOT=build/ppo_robust2
mkdir -p "$OUTROOT"
LOG="$OUTROOT/run_all.log"
exec > >(tee -a "$LOG") 2>&1

COMMON_ARGS=(
  --field research/meta/2026-07-20_robust_field.csv
  --exclude rocket,megastarmie,froslass_starmie
  --adv-tau 0.15
  --lr 1e-3 --ent 0.02
  --iters 200 --games-per-iter 256 --workers 7
)

echo "=== P4 all start: $(date) ==="
git pull

# 教師データありの4デッキ（BC 初期値 + 模倣正則化つき）
run_bc_deck () {
  local name=$1 agent=$2 deck=$3 resume=$4 bcdata=$5
  echo ""
  echo "--- [$name] start: $(date) ---"
  if docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent "$agent" --deck "$deck" "${COMMON_ARGS[@]}" \
      --resume "$resume" \
      --bc-data "$bcdata" --bc-eval-days 2026-07-17 \
      --bc-coef 0.3 --bc-coef-final 0.05 \
      --out "$OUTROOT/$name"; then
    echo "--- [$name] OK: $(date) ---"
  else
    echo "--- [$name] FAILED（スキップして続行）: $(date) ---"
  fi
}

# 教師データなし（chandelure = 我々特有のデッキ。LB に使用者が居ないため模倣項なし）。
# --resume も無いので語彙ウォームアップ → 残差ゼロ初期化（= 学習前はルールと完全一致）から。
# 注意: chandelure ルール版は実ラダー 997.5 = 全資産の最高値。**採用ゲートを通るまで
# agents/chandelure_rb/policy_net.npz は差し替えないこと**（劣化したらルール版を維持）。
run_raw_deck () {
  local name=$1 agent=$2 deck=$3
  echo ""
  echo "--- [$name] start (no BC): $(date) ---"
  if docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent "$agent" --deck "$deck" "${COMMON_ARGS[@]}" \
      --out "$OUTROOT/$name"; then
    echo "--- [$name] OK: $(date) ---"
  else
    echo "--- [$name] FAILED（スキップして続行）: $(date) ---"
  fi
}

run_bc_deck  crustle    agents/crustle_rb          decks/fleet/crustle_wall_top.csv       models/bc_crustle_v4.npz  'data/imitation/crustle_bc/*.npz'
run_bc_deck  alakazam   agents/alakazam_rb         decks/fleet/alakazam_top_0710.csv      models/bc_alakazam_v3.npz 'data/imitation/alakazam_bc/*.npz'
run_bc_deck  marnie     agents/marnie_munkidori_rb decks/fleet/marnie_mainstream_0718.csv models/bc_marnie_v3.npz   'data/imitation/marnie_bc/*.npz'
run_bc_deck  rocket     agents/rocket_rb           decks/fleet/rocket_lolzpo_0715.csv     models/bc_rocket_v2.npz   'data/imitation/rocket_bc/*.npz'
run_raw_deck chandelure agents/chandelure_rb       decks/fleet/chandelure_top.csv

echo ""
echo "=== training done: $(date) — 成果物を push ==="
git add -f "$OUTROOT"/*/ema.npz "$OUTROOT"/*/history.csv 2>/dev/null || true
if git commit -m "EXP-033: 頑健化第4陣 5デッキ（lr↑/iters↑/chandelure追加、run_p3_all.sh 自動実行）"; then
  git push || echo "!! push 失敗 — 手動で git pull --rebase && git push を"
else
  echo "!! commit 対象なし（全デッキ失敗?）— run_all.log を確認"
fi
echo "=== all done: $(date) ==="
