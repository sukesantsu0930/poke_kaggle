# Docker GPU実行手順

このプロジェクトは、GPUサーバー上でDocker Composeを使って学習を回せるようにしています。
サーバー（gs83）の初期構築・データ転送・スモークテストは
[docs/planning/サーバーブートストラップ.md](../docs/planning/サーバーブートストラップ.md) を参照。

## ビルド

```bash
docker compose build
```

## 初回セットアップ（重要）

イメージには `/workspace/.venv` が焼き込まれているが、compose がリポジトリを
`/workspace` にマウントするため焼き込み venv は隠れる。初回に一度だけ実行:

```bash
docker compose run --rm ptcg uv sync
```

GPU を使わないフェーズで nvidia-container-toolkit が未導入の場合は、
`docker-compose.yml` の `gpus:` / `deploy:` 節をコメントアウトして CPU で使う。

サーバー側のCUDA/PyTorch事情に合わせてイメージを変える場合:

```bash
BASE_IMAGE=pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime docker compose build
```

## コンテナに入る

```bash
docker compose run --rm ptcg
```

GPUが見えているか確認:

```bash
docker compose run --rm ptcg python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no gpu')"
```

## 学習

学習コードは `training/` に置き、学習済みファイルは `models/` に出力します。

例:

```bash
docker compose run --rm ptcg uv run python training/train_policy.py --output models/policy_v001.pkl
```

## 評価

ガントレット（メタ加重の制圧度。throughput 行が L1 実験予算の根拠）:

```bash
docker compose run --rm ptcg uv run python scripts/gauntlet.py \
  --agent agents/dragapult_rb \
  --deck decks/candidates/2026-06-30_top5/popular_4_dragapult.csv \
  --games 80
```

模倣学習データの抽出（決定ログ JSONL）:

```bash
docker compose run --rm ptcg uv run python scripts/replay_divergence.py \
  --episodes downloads/episodes/2026-07-06 \
  --agent agents/marnie_munkidori_rb --archetype-cards 648,112 \
  --min-score 900 --dump-decisions build/decisions/marnie.jsonl
```

単体エージェントの検査・A/B:

```bash
docker compose run --rm ptcg uv run python scripts/check_agent.py \
  --agent agents/archaludon_rb --deck decks/candidates/archaludon_cityleague.csv
docker compose run --rm ptcg uv run python scripts/evaluate_submission.py \
  --agent agents/ml_agent_v001.py \
  --deck decks/deck_v001.csv \
  --extra models/policy_v001.pkl=model.pkl \
  --games 50
```

## 提出zip作成

```bash
docker compose run --rm ptcg uv run python scripts/build_submission.py \
  --agent agents/ml_agent_v001.py \
  --deck decks/deck_v001.csv \
  --extra models/policy_v001.pkl=model.pkl
```

生成されたzipは `submissions/` に出力されます。
