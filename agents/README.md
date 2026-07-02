# エージェント置き場

Kaggle提出形式に対応したエージェントをここに置きます。

## 推奨構成

今後は、エージェントごとにディレクトリを作ります。

```text
agents/
  cubchoo_ogerpon_rb/
    main.py
    README.md
```

Kaggle提出zipの中では、各ディレクトリの `main.py` がルートの `main.py` として使われます。

古い単一ファイル形式も当面は使えます。

- `rb_001_baseline.py`
- `rb_002_attack_priority.py`
- `rb_003_setup_tuned.py`
- `ml_001_template.py`

各エージェントの `main.py` は、提出用 `main.py` としてそのまま使える形にしてください。最低限、次の2つを定義します。

- `read_deck_csv() -> list[int]`
- `agent(obs_dict: dict) -> list[int]`

エージェントとデッキを組み合わせて提出zipを作る例:

```powershell
python scripts\build_submission.py --agent agents\cubchoo_ogerpon_rb --deck decks\candidates\2026-06-30_top5\winrate_1_cubchoo_ogerpon.csv
```

機械学習エージェントの場合は、学習済みファイルを `models/` に置き、`--extra` で提出zipに入れます。

```powershell
python scripts\build_submission.py --agent agents\ml_agent --deck decks\my_deck.csv --extra models\policy.pkl=model.pkl
```

提出される `main.py` では、まずカレントディレクトリからファイルを読み、見つからない場合に `/kaggle_simulations/agent/` を読むようにしてください。
