# Docker GPU実行手順

このプロジェクトは、GPUサーバー上でDocker Composeを使って学習を回せるようにしています。

## ビルド

```bash
docker compose build
```

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
docker compose run --rm ptcg python training/train_policy.py --output models/policy_v001.pkl
```

## 評価

```bash
docker compose run --rm ptcg python scripts/evaluate_submission.py \
  --agent agents/ml_agent_v001.py \
  --deck decks/deck_v001.csv \
  --extra models/policy_v001.pkl=model.pkl \
  --games 50
```

## 提出zip作成

```bash
docker compose run --rm ptcg python scripts/build_submission.py \
  --agent agents/ml_agent_v001.py \
  --deck decks/deck_v001.csv \
  --extra models/policy_v001.pkl=model.pkl
```

生成されたzipは `submissions/` に出力されます。
