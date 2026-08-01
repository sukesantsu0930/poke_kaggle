#!/usr/bin/env bash
# gen7 学習ワンショット(第2バッチ): rocket(ロケット団) → garchomp(ガブリアス) を順にPPO仕上げし、
# 出力(ema/latest/history)を自動 push。サーバ gs83 のリポジトリ root で実行。
#   使い方（サーバで一手）:  git pull origin main && tmux new -s gen7b 'bash scripts/train_gen7_roc_gar.sh'
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

run_one rocket   agents/rocket_rb          decks/fleet/rocket_lolzpo_0715.csv \
        models/bc_gen7_rocket.npz   "data/imitation/rocket_bc7/*.npz"
run_one garchomp agents/cynthia_garchomp_rb decks/fleet/cynthia_garchomp_top.csv \
        models/bc_gen7_garchomp.npz "data/imitation/garchomp_bc7/*.npz"

echo "########## 学習完了 → 出力を push ##########"
# docker(root)所有だと add で弾かれる場合あり。その時は次行を外して再実行:
# sudo chown -R "$(id -un)":"$(id -gn)" build/ppo_gen7
git add -f build/ppo_gen7/rocket/ema.npz   build/ppo_gen7/rocket/latest.npz   build/ppo_gen7/rocket/history.csv \
           build/ppo_gen7/garchomp/ema.npz build/ppo_gen7/garchomp/latest.npz build/ppo_gen7/garchomp/history.csv 2>/dev/null
git commit -m "rocket/garchomp gen7 PPO 出力(ema/latest/history) — gs83学習完了" \
  && git pull --rebase origin main && git push origin main \
  && echo ">>> push 完了。Windows 側で L2 採否へ。" \
  || echo ">>> push 失敗（所有権 or 競合）。chown 行を外して手動 add/commit/pull --rebase/push。"
