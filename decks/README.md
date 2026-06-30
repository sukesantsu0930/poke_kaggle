# デッキ置き場

Gitで共有するコンパイル済みデッキCSVをここに置きます。

友人メンバーはCSVを直接編集しません。ポケカ公式サイトでデッキを作り、デッキコードをシステムに入れてGUIで試します。

良いデッキが見つかったら、デッキコードを助友に送ります。助友が確認して、必要なものだけこの階層へ置いてGitに反映します。

推奨する名前:

- `deck_001_sample.csv`
- `deck_002_fast_attack.csv`
- `deck_003_stable_setup.csv`

各デッキファイルは必ず60行にしてください。1行につきカードIDを1つだけ書きます。

デッキコードをCSVへ変換する例:

```powershell
python scripts\import_deck_code.py 4GGxYc-KmW2Iv-8c4c8c
```

デッキとエージェントを組み合わせて提出zipを作る例:

```powershell
python scripts\build_submission.py --agent agents\my_agent.py --deck decks\my_deck.csv
```
