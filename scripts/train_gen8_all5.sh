#!/usr/bin/env bash
# gen8 再学習ワンショット: 5デッキ（marnie→alakazam→crustle→rocket→garchomp）を**逐次**PPOし、
# 出力(ema/latest/history)を自動 push。サーバ gs83 のリポジトリ root で実行。
#   サーバで一手:  git pull origin main && tmux new -s gen8 'bash scripts/train_gen8_all5.sh 2>&1 | tee ~/gen8.log'
#
# gen7 との違い（ここが再学習の主眼）:
#   - 相手プールの5アーキ全枠に gen7 ema ネットを注入（research/meta/2026-08-02_gen8_field.csv の net 列）
#     = 相手が「素のルール版」でなく学習済み世代になる（PSRO 世代凍結昇格）。ミラーも同様に強い。
#   - train_ppo が相手側にも my_deck_list を注入するよう修正済み（自山カウンティング復活）。
# 途中で失敗しても後続は続行する（set -e にしない）。ログは各機の START/END を見る。
set -uo pipefail
cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-7}"
ITERS="${ITERS:-60}"
COMMON=(--field research/meta/2026-08-02_gen8_field.csv \
        --exclude dragapult,other_megamimirop \
        --bc-coef 0.3 --bc-coef-final 0.05 --adv-tau 0.15 \
        --iters "$ITERS" --games-per-iter 256 --workers "$WORKERS")

run_one () {
  local name="$1" agent="$2" deck="$3" bc="$4" bcdata="$5"
  echo "########## $(date +%H:%M:%S) START $name ##########"
  docker compose run --rm ptcg uv run python training/train_ppo.py \
    --agent "$agent" --deck "$deck" \
    --resume "$bc" --bc-data "$bcdata" --bc-eval-days 2026-07-30 \
    "${COMMON[@]}" --out "build/ppo_gen8/$name"
  echo "########## $(date +%H:%M:%S) END $name (exit $?) ##########"
}

run_one marnie   agents/marnie_munkidori_rb  decks/fleet/marnie_gold_luca_0723.csv \
        models/bc_gen7_marnie.npz   "data/imitation/marnie_bc7/*.npz"
run_one alakazam agents/alakazam_rb          decks/fleet/alakazam_top_0710.csv \
        models/bc_gen7_alakazam.npz "data/imitation/alakazam_bc7/*.npz"
run_one crustle  agents/crustle_rb           decks/fleet/crustle_wall_top.csv \
        models/bc_gen7_crustle.npz  "data/imitation/crustle_bc7/*.npz"
run_one rocket   agents/rocket_rb            decks/fleet/rocket_lolzpo_0715.csv \
        models/bc_gen7_rocket.npz   "data/imitation/rocket_bc7/*.npz"
run_one garchomp agents/cynthia_garchomp_rb  decks/fleet/cynthia_garchomp_top.csv \
        models/bc_gen7_garchomp.npz "data/imitation/garchomp_bc7/*.npz"

echo "########## $(date +%H:%M:%S) 全5本 完了 → 出力を push ##########"
# docker(root)所有だと add で弾かれる場合あり。その時は次行を外して再実行:
# sudo chown -R "$(id -un)":"$(id -gn)" build/ppo_gen8
for n in marnie alakazam crustle rocket garchomp; do
  git add -f "build/ppo_gen8/$n/ema.npz" "build/ppo_gen8/$n/latest.npz" \
             "build/ppo_gen8/$n/history.csv" 2>/dev/null
done
git commit -m "gen8 PPO 出力5本(ema/latest/history) — 相手プール gen7 強化で再学習" \
  && git pull --rebase origin main && git push origin main \
  && echo ">>> push 完了。Windows 側で L2 採否（gen8 vs gen7）へ。" \
  || echo ">>> push 失敗（所有権 or 競合）。chown 行を外して手動 add/commit/pull --rebase/push。"
