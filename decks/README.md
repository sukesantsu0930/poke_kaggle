# デッキ置き場

Gitで共有するデッキ候補をここに置きます。

友人メンバーが手元で試作するデッキは、`decks/local/` に置いてください。`decks/local/*.csv` はGit管理しない設定です。

良いデッキができたら、CSVを助友に直接送ってください。助友が確認して、必要なものだけこの階層へ移してGitに反映します。

推奨する名前:

- `deck_001_sample.csv`
- `deck_002_fast_attack.csv`
- `deck_003_stable_setup.csv`

各デッキファイルは必ず60行にしてください。1行につきカードIDを1つだけ書きます。

デッキとエージェントを組み合わせて提出zipを作る例:

```powershell
python scripts\build_submission.py --agent agents\my_agent.py --deck decks\my_deck.csv
```
