#!/usr/bin/env bash
# gen7 学習ワンショット: alakazam(フーディン) → crustle(イワパレス) を順に PPO 仕上げし、
# 出力(ema/latest/history)を自動 push する。サーバ gs83 のリポジトリ root で実行。
#   使い方（サーバで一手）:  git pull origin main && tmux new -s gen7 'bash scripts/train_gen7_ala_cru.sh'
# 8スレ機なので2本は「並行でなく順番」に回す(各 --workers 7)。tmux 内なら切断しても継続。
set -uo pipefail
cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-7}"
COMMON=(--field research/meta/2026-07-31_uniform.csv \
        --exclude dragapult,other_megamimirop \
        --bc-coef 0.3 --bc-coef-final 0.05 --adv-tau 0.15 \
        --iters 60 --games-per-iter 256 --workers "$WORKERS")

run_one () {
  local name="$1" agent="$2" deck="$3" bc="$4" bcdata="$5"
  echo "########## $(date +%H:%M:%S) START $name ##########"
  docker compose run --rm ptcg uv run python training/train_ppo.py \
    --agent "$agent" --deck "$deck" \
    --resume "$bc" --bc-data "$bcdata" --bc-eval-days 2026-07-30 \
    "${COMMON[@]}" --out "build/ppo_gen7/$name"
  echo "########## $(date +%H:%M:%S) END $name (exit $?) ##########"
}

run_one alakazam agents/alakazam_rb decks/fleet/alakazam_top_0710.csv \
        models/bc_gen7_alakazam.npz "data/imitation/alakazam_bc7/*.npz"
run_one crustle  agents/crustle_rb  decks/fleet/crustle_wall_top.csv \
        models/bc_gen7_crustle.npz  "data/imitation/crustle_bc7/*.npz"

echo "########## 学習完了 → 出力を push ##########"
# docker(root)所有だと add で弾かれる場合あり。その時は下行のコメントを外して再実行:
# sudo chown -R "$(id -un)":"$(id -gn)" build/ppo_gen7
git add -f build/ppo_gen7/alakazam/ema.npz build/ppo_gen7/alakazam/latest.npz build/ppo_gen7/alakazam/history.csv \
           build/ppo_gen7/crustle/ema.npz  build/ppo_gen7/crustle/latest.npz  build/ppo_gen7/crustle/history.csv 2>/dev/null
git commit -m "alakazam/crustle gen7 PPO 出力(ema/latest/history) — gs83学習完了" \
  && git pull --rebase origin main && git push origin main \
  && echo ">>> push 完了。Windows 側で L2 採否へ。" \
  || echo ">>> push 失敗（所有権 or 競合）。上のchown行を外して 'git add -f ...; git commit; git pull --rebase; git push' を手動で。"
