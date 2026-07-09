# proposal: archaludon（ブリジュラス）

- デッキ: `decks/candidates/archaludon_cityleague.csv`（シティリーグ準優勝リスト、ボス×4）
- エージェント: `agents/archaludon_rb`（ターン手順実装 v1。設計は `docs/planning/デッキ設計_ブリジュラス.md`）
- プロトコル: ブリジュラスの攻撃（Metal Defender/Raging Hammer）を最初に打てたターンを記録
  （= サブゴール実現速度の計測）

実行:

```powershell
uv run python scripts\run_proposal.py --proposal proposals\archaludon
```
