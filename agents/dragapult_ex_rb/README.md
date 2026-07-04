# Dragapult ex rule-based agent

ドラパルト系デッキ向けのルールベースAgentです。

対応デッキ:

```text
decks/candidates/2026-06-30_top5/popular_4_dragapult.csv
```

基本方針:

- Dreepy / Drakloak / Dragapult ex を優先して場に揃える
- Rare Candy、Akamatsu、炎/超エネルギーを高く評価する
- 攻撃では `Phantom Dive` を最優先する
- 万能Agentではなく、このデッキのコンセプト達成を優先する

評価例:

```powershell
uv run python scripts\batch_evaluate.py --agent agents\dragapult_ex_rb --deck decks\candidates\2026-06-30_top5\popular_4_dragapult.csv --games 50 --seed 1
```

提出zip作成:

```powershell
uv run python scripts\build_submission.py --agent agents\dragapult_ex_rb --deck decks\candidates\2026-06-30_top5\popular_4_dragapult.csv
```

