# 提案置き場

デッキ、対応Agent、評価プロトコルを1つの提案単位で管理します。

`decks/` と `agents/` は部品置き場です。`proposals/` は「このデッキを、このAgentで、この目的に向けて評価する」という束ね先です。

## 構成

```text
proposals/
  dragapult_ex/
    proposal.yml
    protocol.py
    README.md
```

## 実行

```powershell
uv run python scripts\run_proposal.py --proposal proposals\dragapult_ex
```

出力は以下に作られます。

```text
experiments\proposals\<proposal名>\<日時>\
```

## 評価

- 通常対戦評価: 既存のランダム相手に対する勝率
- 一人回し評価: 相手はできるだけ何もせず、ドローして番を返す
- コンセプト評価: proposal内の `protocol.py` が記録する

