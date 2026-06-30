# デッキ置き場

デッキ候補をここに置きます。

推奨する名前:

- `deck_001_sample.csv`
- `deck_002_fast_attack.csv`
- `deck_003_stable_setup.csv`

各デッキファイルは必ず60行にしてください。1行につきカードIDを1つだけ書きます。

デッキとエージェントを組み合わせて提出zipを作る例:

```powershell
python scripts\build_submission.py --agent agents\my_agent.py --deck decks\my_deck.csv
```
