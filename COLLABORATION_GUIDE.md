# 共同作業ガイド

このリポジトリでは、役割を分けて作業します。

## 役割

### デッキ研究担当

主に触る場所:

- `decks/`
- `research/deck_notes/`
- `research/card_notes/`

やること:

- 使いたいカードを調べる
- デッキ案を60枚で作り、`decks/` にCSVとして保存する
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

## 触ってよいファイル

初心者メンバーは、基本的に以下だけを編集してください。

- `decks/*.csv`
- `research/**/*.md`

慣れるまでは以下は編集しないでください。

- `agents/*.py`
- `scripts/*.py`
- `submission/`
- `cg/`
- `models/`
- `Dockerfile`
- `docker-compose.yml`

## デッキファイルのルール

`decks/` に `deck_番号_名前.csv` という名前で保存します。

例:

- `decks/deck_002_fast_attack.csv`
- `decks/deck_003_stable_setup.csv`

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

変更確認:

```bash
git status
```

変更を保存:

```bash
git add decks research
git commit -m "add deck idea"
git push
```

他人と同じファイルを同時に編集すると衝突しやすいです。基本は「自分のメモファイルを作る」運用にしてください。

## 提案から評価までの流れ

1. デッキ案や戦略メモを書く
2. 実装担当がエージェントやデッキcsvに反映する
3. `scripts/batch_evaluate.py` で評価する
4. `experiments/` に結果を残す
5. よかった案だけ次の候補に残す
