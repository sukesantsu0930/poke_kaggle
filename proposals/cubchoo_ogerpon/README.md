# cubchoo_ogerpon

クマシュン / オーガポン いしずえのめんex 候補デッキと専用Agentを束ねる提案です。

## 部品

- Deck: `decks/archive/winrate_1_cubchoo_ogerpon.csv`
- Agent: `agents/cubchoo_ogerpon_rb`
- Protocol: `protocol.py`

## 評価

```powershell
uv run python scripts\run_proposal.py --proposal proposals\cubchoo_ogerpon --games 20 --max-steps 500
```

最初のプロトコルは簡易版です。指定した重要カードが場に出たかを記録します。

