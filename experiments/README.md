# 実験結果置き場

実験メモ、実行結果、比較表をここに置きます。

推奨する名前:

- `YYYYMMDD_agent_deck_notes.md`
- `YYYYMMDD_results.csv`

採用済みのデッキ案は `decks/`、友人の手元試作デッキは `decks/local/`、エージェント案は `agents/` に置きます。観察結果や評価結果はここに置きます。

非エンジニア向けの研究メモは `research/` に置きます。

全組み合わせ評価:

```powershell
python scripts\batch_evaluate.py --games 50 --seed 1
```

特定の組み合わせだけ評価:

```powershell
python scripts\batch_evaluate.py --agent agents\agent_a.py --agent agents\agent_b.py --deck decks\deck_a.csv --games 100
```
