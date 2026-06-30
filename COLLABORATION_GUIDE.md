# 共同作業ガイド

このリポジトリでは、役割を分けて作業します。

## 役割

### デッキ研究担当

主に触る場所:

- `research/deck_notes/`
- `research/card_notes/`

やること:

- 使いたいカードを調べる
- ポケカ公式サイトで60枚デッキを作り、デッキコードを発行する
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

- `research/**/*.md`

ただし、Gitへ自分で `commit` や `push` はしません。良いデッキができたら、デッキコードとメモを助友に直接送ってください。

慣れるまでは以下は編集しないでください。

- `agents/*.py`
- `scripts/*.py`
- `submission/`
- `cg/`
- `models/`
- `Dockerfile`
- `docker-compose.yml`

## デッキコードのルール

初心者メンバーはCSVを直接書きません。

ポケカ公式サイトでデッキを作り、次のようなデッキコードを助友に送ってください。

```text
4GGxYc-KmW2Iv-8c4c8c
```

助友側で、デッキコードをKaggle用CSVへ変換できるかチェックします。変換できたものだけGUIや評価に使います。

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

採用候補はデッキコードとメモを助友に直接送ってください。

## 提案から評価までの流れ

1. デッキ案や戦略メモを書く
2. 良いデッキコードとメモを助友に直接送る
3. 実装担当がエージェントや共有デッキcsvに反映する
4. `scripts/batch_evaluate.py` で評価する
5. `experiments/` に結果を残す
6. よかった案だけ次の候補に残す
