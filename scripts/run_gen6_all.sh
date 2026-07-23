#!/usr/bin/env bash
# サーバー §P5 一括実行 — gen6「新教師×修正後エンジン」配合（7デッキ）の学習から結果 push まで全自動。
#
# 使い方（gs83・リポジトリ直下で）:
#   tmux kill-session -t ppo 2>/dev/null; git pull && tmux new -d -s ppo 'bash scripts/run_gen6_all.sh; exec bash'
#   tail -f build/ppo_gen6/run_all.log
#
# gen6 の変更点（EXP-039。gen5 = EXP-037 の模倣増幅配合は維持）:
#   - エンジン 07-17 修正版（kaggle-environments 1.32.1 の cg。submission/cg 差し替え済み）
#   - BC 教師を全面刷新: 07-17〜21 の修正後時代のみ・上位帯ピロット
#     （Luca/kashiwashira/junlee789/Majkel/Yushin/LumenLiquidity 等）= bc_gen6_* + *_bc6/
#   - デッキ 4→7: + garchomp（junlee789 デッキ完全同一）/ dragapult_dusknoir / dragapult
#   - プールに rocket を復帰（gen5 の exclude はエンジンクラッシュ回避。修正版で解除。
#     rocket は上位帯シェア 10.7%・勝率 63% の頂点捕食者 = プール不在は盲点になる）
#   - holdout: 2026-07-21
#   - chandelure は対象外（教師なしデッキはルールで全覆 = EXP-034 確定方針。王者 997.5 防衛）
set -u
cd "$(dirname "$0")/.."
OUTROOT=build/ppo_gen6
mkdir -p "$OUTROOT"
LOG="$OUTROOT/run_all.log"
exec > >(tee -a "$LOG") 2>&1

COMMON_ARGS=(
  --field research/meta/2026-07-20_robust_field.csv
  --exclude megastarmie,froslass_starmie
  --adv-tau 0.15
  --lr 3e-4 --ent 0.01
  --iters 60 --games-per-iter 256 --workers 7
  --bc-coef 0.5 --bc-coef-final 0.2
)

echo "=== gen6 all start: $(date) ==="
git pull

run_deck () {
  local name=$1 agent=$2 deck=$3 evalday=$4
  echo ""
  echo "--- [$name] start: $(date) ---"
  if [ ! -f "models/bc_gen6_$name.npz" ]; then
    echo "--- [$name] SKIP: models/bc_gen6_$name.npz が無い（prepare_gen6_bc.sh 未完了？） ---"
    return
  fi
  if docker compose run --rm ptcg uv run python training/train_ppo.py \
      --agent "$agent" --deck "$deck" "${COMMON_ARGS[@]}" \
      --bc-eval-days "$evalday" \
      --resume "models/bc_gen6_$name.npz" \
      --bc-data "data/imitation/${name}_bc6/*.npz" \
      --out "$OUTROOT/$name"; then
    echo "--- [$name] OK: $(date) ---"
  else
    echo "--- [$name] FAILED（スキップして続行）: $(date) ---"
  fi
}

# 帯別制圧度（EXP-038）の序列順 = チャンピオン候補を先に仕上げる。
# holdout は原則 07-21。rocket のみ 07-20（07-21 サンプルに教師 kashiwashira 不在のため）
run_deck marnie             agents/marnie_munkidori_rb   decks/fleet/marnie_mainstream_0718.csv   2026-07-21
run_deck garchomp           agents/cynthia_garchomp_rb   decks/fleet/cynthia_garchomp_top.csv     2026-07-21
run_deck rocket             agents/rocket_rb             decks/fleet/rocket_lolzpo_0715.csv       2026-07-20
run_deck alakazam           agents/alakazam_rb           decks/fleet/alakazam_top_0710.csv        2026-07-21
run_deck crustle            agents/crustle_rb            decks/fleet/crustle_wall_top.csv         2026-07-21
run_deck dragapult_dusknoir agents/dragapult_dusknoir_rb decks/fleet/dragapult_dusknoir_paper.csv 2026-07-21
run_deck dragapult          agents/dragapult_rb          decks/fleet/popular_4_dragapult.csv      2026-07-21

echo ""
echo "=== training done: $(date) — 成果物を push ==="
git add -f "$OUTROOT"/*/ema.npz "$OUTROOT"/*/history.csv 2>/dev/null || true
if git commit -m "EXP-039: gen6 新教師×修正後エンジン 7デッキ（run_gen6_all.sh 自動実行）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"; then
  git push || echo "!! push 失敗 — 手動で git pull --rebase && git push を"
else
  echo "!! commit 対象なし — run_all.log を確認"
fi
echo "=== all done: $(date) ==="
