#!/usr/bin/env bash
# サーバー §P7 — gen7（dragapult のみ）。EXP-041 の DRA_CONCENTRATE でドラパルトの MAIN
# 候補集合が変わったため、新ルール土台で再抽出した bc_gen7_dragapult を初期値に学習し直す。
#
# 使い方（gs83）:
#   tmux kill-session -t ppo 2>/dev/null; git pull && tmux new -d -s ppo 'bash scripts/run_gen7_all.sh; exec bash'
#   tail -f build/ppo_gen7/run_all.log
#
# なぜ dragapult だけか:
#   - R-31（前出しはにげ0）は TO_ACTIVE 決定 = BC 抽出（MAIN 限定）に入らない → 他デッキの
#     BC 候補集合は不変。既存 gen4-6 ネットは新ルール土台でもそのまま有効。
#   - DRA_CONCENTRATE は ATTACH（MAIN 内）でエネ分散を負帯化 = ドラパルトの候補集合が変化 →
#     再抽出・再学習が必要なのはドラパルトのみ。
#   - 配合は gen5/6 と同じ模倣増幅（λ 0.5→0.2・lr 3e-4・60it・相手盲目化・敵対サンプリング）。
#   - 注意: 現ラダーの dragapult gen6（883）は旧ルール土台の学習版。gen7 が L2 で
#     「新ルール素」と gen6 の両方を上回るか要確認（採用ゲートは Windows 側）。
set -u
cd "$(dirname "$0")/.."
OUTROOT=build/ppo_gen7
mkdir -p "$OUTROOT"
LOG="$OUTROOT/run_all.log"
exec > >(tee -a "$LOG") 2>&1

echo "=== gen7 start: $(date) ==="
git pull

if docker compose run --rm ptcg uv run python training/train_ppo.py \
    --agent agents/dragapult_rb --deck decks/fleet/popular_4_dragapult.csv \
    --field research/meta/2026-07-20_robust_field.csv \
    --exclude rocket,megastarmie,froslass_starmie \
    --adv-tau 0.15 --lr 3e-4 --ent 0.01 \
    --iters 60 --games-per-iter 256 --workers 7 \
    --bc-coef 0.5 --bc-coef-final 0.2 --bc-eval-days 2026-07-21 \
    --resume models/bc_gen7_dragapult.npz \
    --bc-data 'data/imitation/dragapult_bc7/*.npz' \
    --out "$OUTROOT/dragapult"; then
  echo "--- dragapult OK: $(date) ---"
else
  echo "--- dragapult FAILED: $(date) ---"
fi

echo "=== training done: $(date) — push ==="
git add -f "$OUTROOT"/*/ema.npz "$OUTROOT"/*/history.csv 2>/dev/null || true
if git commit -m "EXP-042: gen7 dragapult（新ルール土台・DRA_CONCENTRATE後の再学習）"; then
  git push || echo "!! push 失敗 — git pull --rebase && git push を手動で"
else
  echo "!! commit 対象なし — run_all.log を確認"
fi
echo "=== all done: $(date) ==="
