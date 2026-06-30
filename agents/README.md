# エージェント置き場

Kaggle提出形式に対応したエージェントファイルをここに置きます。

推奨する名前:

- `rb_001_baseline.py`
- `rb_002_attack_priority.py`
- `rb_003_setup_tuned.py`
- `ml_001_template.py`

各エージェントファイルは、`main.py` としてそのまま使える形にしてください。最低限、次の2つを定義します。

- `read_deck_csv() -> list[int]`
- `agent(obs_dict: dict) -> list[int]`

エージェントとデッキを組み合わせて提出zipを作る例:

```powershell
python scripts\build_submission.py --agent agents\my_agent.py --deck decks\my_deck.csv
```

機械学習エージェントの場合は、学習済みファイルを `models/` に置き、`--extra` で提出zipに入れます。

```powershell
python scripts\build_submission.py --agent agents\ml_agent.py --deck decks\my_deck.csv --extra models\policy.pkl=model.pkl
```

提出される `main.py` では、まずカレントディレクトリからファイルを読み、見つからない場合に `/kaggle_simulations/agent/` を読むようにしてください。
