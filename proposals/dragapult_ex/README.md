# dragapult_ex

ドラパルトexに進化し、`Phantom Dive` を打つことをコンセプトにした提案です。

## 部品

- Deck: `decks/fleet/popular_4_dragapult.csv`
- Agent: `agents/dragapult_ex_rb`
- Protocol: `protocol.py`

## 評価

```powershell
uv run python scripts\run_proposal.py --proposal proposals\dragapult_ex --games 20 --max-steps 500
```

一人回し評価では、`Phantom Dive` を初めて選択したターンを記録します。

