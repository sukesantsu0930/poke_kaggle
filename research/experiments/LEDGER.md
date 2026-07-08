# 実験台帳

1実験 = 1行。**構成で引く**ための台帳（時系列の記録は `docs/planning/PROJECT_DIARY.md`）。
運用ルールの正典: [エージェントアーキテクチャと実験計画.md](../../docs/strategy/エージェントアーキテクチャと実験計画.md) §5（3審級の漏斗・昇格/kill基準）。

## 記法

- **id**: EXP-NNN 連番。
- **構成**: 何を変えたか（部品・θ・belief 等）。ベースラインとの差分を書く。
- **L0**: 対戦不要メトリクス（shadow一致率 / divergence一致率 / held-out選択一致率）。
- **L1**: gauntlet 制圧度（**試合数を必ず明記**。80試合=スクリーニング±7pt / 320試合=確定±3.5pt。P-03）。
- **verdict**: adopt / reject / shelve / provisional / done（計測タスク）。
- 昇格基準: L1確定で **+7pt 以上**（ノイズの2倍）+ holdout 相手への非劣化 → L2（実ラダー）。
- kill基準: L1スクリーニングで差なし〜劣化 → reject。time-box 3日で L1 未到達 → shelve。
- 詳細ログ・生データは `research/eval/` や `build/` に置き、notes からリンク。

## 台帳

| id | date | phase | 構成 | agent / deck | baseline | L0 | L1 (games, 制圧度) | verdict | notes |
|---|---|---|---|---|---|---|---|---|---|
| EXP-001 | 2026-07-09 | P1 | gauntlet スループット実測（タイマー追加後の初計測） | dragapult_rb / popular_4_dragapult | - | - | 88試合（8/matchup、数値は参考値） | done | **Windows開発機: 336 games/min（0.18 s/game、シングルプロセス）**。全フィールド×80試合 ≈ 3分、×320試合 ≈ 12分 → 評価スループットは当初想定より大幅に潤沢。サーバー（gs83, Docker）側の実測は bootstrap 時に追記 |
