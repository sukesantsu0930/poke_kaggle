#!/usr/bin/env bash
# gen6 BC 材料生成 — 教師時代を「エンジン 07-17 修正後」に刷新し、上位帯の新教師で
# 全候補デッキ（7本）を再抽出 + BC 学習する。ローカル（Git Bash）/サーバー両用。
#
# 使い方: bash scripts/prepare_gen6_bc.sh
#
# gen5 からの変更点（EXP-039 準備）:
#   - 教師日: 07-17〜21 のみ（07-16 以前 = エンジン修正前時代は捨てる。rocket メタは
#     修正後に 1.4%→12.3% へ急伸しており、修正前の打ち筋は教師として筋が悪い）
#   - holdout: 2026-07-21
#   - デッキ追加: garchomp（junlee789=LB4位・デッキ完全同一）/ dragapult_dusknoir
#     （LumenLiquidity 1148）/ dragapult（BigBugginnings 1104）
#   - min-score はデッキ毎（07-23 LB で上位帯教師を捕捉する閾値）
#   - 出力は data/imitation/<name>_bc6/ + models/bc_gen6_*（gen5 材料は温存）
#   - dragapult 系のみ min-overlap を緩和（教師リストが fleet と 7〜11 枚差のため。
#     リスト現代化は Phase R の宿題 → research/meta/2026-07-23_band_census.md）
set -u
cd "$(dirname "$0")/.."
OUTROOT=build/gen6_bc
mkdir -p "$OUTROOT"
LOG="$OUTROOT/prepare.log"
exec > >(tee -a "$LOG") 2>&1

DAYS=(2026-07-17 2026-07-18 2026-07-19 2026-07-20 2026-07-21)
HOLDOUT=2026-07-21

echo "=== gen6 BC prepare start: $(date) ==="

prep_deck () {
  local name=$1 agent=$2 deck=$3 minscore=$4 overlap=$5
  echo ""
  echo "--- [$name] extract start: $(date) (min-score=$minscore, overlap=$overlap) ---"
  mkdir -p "data/imitation/${name}_bc6"
  for day in "${DAYS[@]}"; do
    uv run python training/extract_bc_dataset.py \
      --episodes "downloads/episodes/$day" \
      --agent "$agent" --match-deck "$deck" \
      --min-overlap "$overlap" --min-score "$minscore" \
      --out "data/imitation/${name}_bc6/$day.npz" \
      || echo "!! [$name/$day] 抽出失敗（続行）"
  done
  echo "--- [$name] train_bc: $(date) ---"
  uv run python training/train_bc.py \
    --data "data/imitation/${name}_bc6/*.npz" \
    --eval-days "$HOLDOUT" \
    --out "models/bc_gen6_$name.npz" \
    || echo "!! [$name] BC 学習失敗（続行）"
}

#          name                agent                        match-deck                                min-score overlap
prep_deck  crustle             agents/crustle_rb            decks/fleet/crustle_wall_top.csv          1050      55
prep_deck  alakazam            agents/alakazam_rb           decks/fleet/alakazam_top_0710.csv         1100      55
prep_deck  marnie              agents/marnie_munkidori_rb   decks/fleet/marnie_mainstream_0718.csv    1100      55
prep_deck  rocket              agents/rocket_rb             decks/fleet/rocket_lolzpo_0715.csv        1100      55
prep_deck  garchomp            agents/cynthia_garchomp_rb   decks/fleet/cynthia_garchomp_top.csv      1100      55
prep_deck  dragapult_dusknoir  agents/dragapult_dusknoir_rb decks/fleet/dragapult_dusknoir_paper.csv  1100      50
prep_deck  dragapult           agents/dragapult_rb          decks/fleet/popular_4_dragapult.csv       1100      45

echo ""
echo "=== summary: $(date) ==="
for f in models/bc_gen6_*.npz; do ls -la "$f"; done
find data/imitation -name "*.npz" -path "*_bc6*" | sort | while read -r f; do
  printf "%s  %s bytes\n" "$f" "$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f")"
done
echo "=== gen6 BC prepare done: $(date) ==="
