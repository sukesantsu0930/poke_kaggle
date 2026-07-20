#!/usr/bin/env bash
# サーバー §P3 一括実行 — 頑健化第3陣（4デッキ）の学習から結果 push まで全自動。
#
# 使い方（gs83・リポジトリ直下で。tmux 内で走らせれば切断しても続行）:
#   git pull && tmux new -d -s ppo 'bash scripts/run_p3_all.sh; exec bash'
#   tmux attach -t ppo        # 進捗を覗く（デタッチ: Ctrl+b → d）
#   tail -f build/ppo_robust/run_all.log   # attach せずにログだけ見る
#
# 1デッキ ≈ 10〜15分 × 4本。失敗したデッキはスキップして続行し、
# 成果物（ema.npz / history.csv）があるものだけ commit & push する。
set -u
cd "$(dirname "$0")/.."
mkdir -p build/ppo_robust
LOG=build/ppo_robust/run_all.log
exec > >(tee -a "$LOG") 2>&1

echo "=== P3 all start: $(date) ==="
git pull

run_deck () {
  local name=$1 agent=$2 deck=$3 resume=$4 bcdata=$5
  echo ""
  echo "--- [$name] start: $(date) ---"
  if docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent "$agent" --deck "$deck" \
      --field research/meta/2026-07-20_robust_field.csv \
      --exclude rocket,megastarmie,froslass_starmie \
      --resume "$resume" \
      --bc-data "$bcdata" --bc-eval-days 2026-07-17 \
      --bc-coef 0.3 --bc-coef-final 0.05 --adv-tau 0.15 \
      --iters 60 --games-per-iter 256 --workers 7 \
      --out "build/ppo_robust/$name"; then
    echo "--- [$name] OK: $(date) ---"
  else
    echo "--- [$name] FAILED（スキップして続行）: $(date) ---"
  fi
}

run_deck crustle  agents/crustle_rb          decks/fleet/crustle_wall_top.csv       models/bc_crustle_v4.npz  'data/imitation/crustle_bc/*.npz'
run_deck alakazam agents/alakazam_rb         decks/fleet/alakazam_top_0710.csv      models/bc_alakazam_v3.npz 'data/imitation/alakazam_bc/*.npz'
run_deck marnie   agents/marnie_munkidori_rb decks/fleet/marnie_mainstream_0718.csv models/bc_marnie_v3.npz   'data/imitation/marnie_bc/*.npz'
run_deck rocket   agents/rocket_rb           decks/fleet/rocket_lolzpo_0715.csv     models/bc_rocket_v2.npz   'data/imitation/rocket_bc/*.npz'

echo ""
echo "=== training done: $(date) — 成果物を push ==="
git add -f build/ppo_robust/*/ema.npz build/ppo_robust/*/history.csv 2>/dev/null || true
if git commit -m "EXP-031: 頑健化第3陣 4デッキ（ema + history、run_p3_all.sh 自動実行）"; then
  git push || echo "!! push 失敗 — 手動で git pull --rebase && git push を"
else
  echo "!! commit 対象なし（全デッキ失敗?）— run_all.log を確認"
fi
echo "=== all done: $(date) ==="
