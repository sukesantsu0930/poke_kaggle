#!/usr/bin/env bash
# サーバー §P5 一括実行 — gen5「模倣増幅」配合（4デッキ）の学習から結果 push まで全自動。
#
# 使い方（gs83・リポジトリ直下で）:
#   tmux kill-session -t ppo 2>/dev/null; git pull && tmux new -d -s ppo 'bash scripts/run_gen5_all.sh; exec bash'
#   tail -f build/ppo_gen5/run_all.log
#
# gen5 の配合（EXP-034 の確定方針 = 学習の役割を「プール最適化」から「模倣増幅」へ）:
#   - λ 強化: --bc-coef 0.5 → 0.2（gen4 は 0.3 → 0.05。錨を終始強く残す）
#   - プール RL 浅く: --lr 3e-4（gen4 の 1e-3 から戻す）・--iters 60（200 から戻す）
#     根拠 = ラダー実績 gen1(779) > gen3(669) > gen2(645)（教師に近いほど強い）+
#     gen4 crustle の最悪対面掘り下げ（深い最適化の過学習）
#   - 維持: 相手盲目化（PN v2）・敵対サンプリング --adv-tau 0.15・頑健プール14相手
#   - ルール土台 = 第3ラウンド + R-30 済み（EXP-035/036）。BC は bc_gen5_*（教師 07-21 まで拡張）
#   - chandelure は対象外（教師なしデッキはルールで全覆 = EXP-034 確定方針。王者 997.5 防衛）
set -u
cd "$(dirname "$0")/.."
OUTROOT=build/ppo_gen5
mkdir -p "$OUTROOT"
LOG="$OUTROOT/run_all.log"
exec > >(tee -a "$LOG") 2>&1

COMMON_ARGS=(
  --field research/meta/2026-07-20_robust_field.csv
  --exclude rocket,megastarmie,froslass_starmie
  --adv-tau 0.15
  --lr 3e-4 --ent 0.01
  --iters 60 --games-per-iter 256 --workers 7
  --bc-coef 0.5 --bc-coef-final 0.2
  --bc-eval-days 2026-07-21
)

echo "=== gen5 all start: $(date) ==="
git pull

run_deck () {
  local name=$1 agent=$2 deck=$3
  echo ""
  echo "--- [$name] start: $(date) ---"
  if docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent "$agent" --deck "$deck" "${COMMON_ARGS[@]}" \
      --resume "models/bc_gen5_$name.npz" \
      --bc-data "data/imitation/${name}_bc/*.npz" \
      --out "$OUTROOT/$name"; then
    echo "--- [$name] OK: $(date) ---"
  else
    echo "--- [$name] FAILED（スキップして続行）: $(date) ---"
  fi
}

run_deck crustle  agents/crustle_rb          decks/fleet/crustle_wall_top.csv
run_deck alakazam agents/alakazam_rb         decks/fleet/alakazam_top_0710.csv
run_deck marnie   agents/marnie_munkidori_rb decks/fleet/marnie_mainstream_0718.csv
run_deck rocket   agents/rocket_rb           decks/fleet/rocket_lolzpo_0715.csv

echo ""
echo "=== training done: $(date) — 成果物を push ==="
git add -f "$OUTROOT"/*/ema.npz "$OUTROOT"/*/history.csv 2>/dev/null || true
if git commit -m "EXP-037: gen5 模倣増幅 4デッキ（run_gen5_all.sh 自動実行）"; then
  git push || echo "!! push 失敗 — 手動で git pull --rebase && git push を"
else
  echo "!! commit 対象なし — run_all.log を確認"
fi
echo "=== all done: $(date) ==="
