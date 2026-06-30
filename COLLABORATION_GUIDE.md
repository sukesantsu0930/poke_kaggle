# 共同作業ガイド

このリポジトリでは、役割を分けて作業します。

## 役割

### デッキ研究担当

主に触る場所:

- `decks/local/`
- `research/deck_notes/`
- `research/card_notes/`

やること:

- 使いたいカードを調べる
- デッキ案を60枚で作り、`decks/local/` にCSVとして保存する
- なぜそのカードを入れたかを書く
- 強そうな動き、弱そうな相手、事故りそうな点を書く

### ストラテジー研究担当

主に触る場所:

- `research/strategy_notes/`
- `research/rule_findings/`

やること:

- ルールやカード効果で重要そうなことを発見する
- 「先攻/後攻」「進化」「エネルギー」「ベンチ」「サイド」などの戦略を調べる
- エージェントに入れたい判断ルールを書く

### 実装・評価担当

主に触る場所:

- `agents/`
- `scripts/`
- `experiments/`

やること:

- エージェントに判断ルールを入れる
- デッキとエージェントの組み合わせを評価する
- 勝率や失敗例をまとめる
- Kaggle提出zipを作る

## 初心者メンバーの作業場所

初心者メンバーは、基本的に以下だけを使ってください。

- `decks/local/*.csv`
- `research/**/*.md`

ただし、Gitへ自分で `commit` や `push` はしません。良いデッキやメモができたら、ファイルを助友に直接送ってください。

慣れるまでは以下は編集しないでください。

- `agents/*.py`
- `scripts/*.py`
- `submission/`
- `cg/`
- `models/`
- `Dockerfile`
- `docker-compose.yml`

## デッキファイルのルール

`decks/local/` に `deck_番号_名前.csv` という名前で保存します。

例:

- `decks/local/deck_002_fast_attack.csv`
- `decks/local/deck_003_stable_setup.csv`

中身は60行です。1行にカードIDを1つだけ書きます。

カード名や採用理由はCSVには書かず、`research/deck_notes/` のメモに書いてください。

## メモのルール

研究メモはMarkdownで書きます。

例:

- `research/deck_notes/deck_002_fast_attack.md`
- `research/strategy_notes/energy_attachment_priority.md`
- `research/rule_findings/first_turn_attack.md`

結論だけでなく、なぜそう思ったかを書いてください。

## Gitの最低限

作業前:

```bash
git pull
```

初心者メンバーは、基本的にこれだけで大丈夫です。

変更確認:

```bash
git status
```

`decks/local/*.csv` はGit管理しないため、手元にだけ残ります。採用候補は助友に直接送ってください。

## 提案から評価までの流れ

1. デッキ案や戦略メモを書く
2. 良いデッキCSVとメモを助友に直接送る
3. 実装担当がエージェントや共有デッキcsvに反映する
4. `scripts/batch_evaluate.py` で評価する
5. `experiments/` に結果を残す
6. よかった案だけ次の候補に残す
