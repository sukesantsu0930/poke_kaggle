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
| EXP-001 | 2026-07-09 | P1 | gauntlet スループット実測（タイマー追加後の初計測） | dragapult_rb / popular_4_dragapult | - | - | 88試合（8/matchup、数値は参考値） | done | **Windows開発機: 336〜627 games/min（デッキ依存、シングルプロセス）**。全フィールド×80試合 ≈ 1.5〜3分 → 評価スループットは当初想定より大幅に潤沢。サーバー（gs83, Docker）側の実測は bootstrap 時に追記 |
| EXP-002 | 2026-07-09 | P2 | **模倣 θ v1**（reason 一律加算の条件付きロジット。T=1000, λ=3, min_count=5, 上位ピロット=LB1000+×自リスト重なり45+） | marnie / winrate_2 | θ=0（手書き） | held-out 一致率 62.6%→**63.1%**（train 61.8→63.9%） | 80/matchup×11: **66.0% → 48.0%（−18pt）** | **reject** | **L0改善とL1大幅悪化が両立**した教科書的な負例。模倣θは「end +9024」「play pokemon −4796」など文脈盲目の一律シフトで、対botプールでは受動的すぎる方向に歪む。含意: (1) 模倣θの直接デプロイは不可、CEM の初期値or divergence レポート用途に格下げ (2) 上位者の強さは文脈依存（φ不足）→ 残差=新述語のシグナルという中心テーゼを実証。データ: build/fit/marnie_theta.json, data/imitation/marnie/ (24,645決定) |
| EXP-003 | 2026-07-09 | P4 | CEM 配管スモーク（pop4×3iter×2対面×4試合、θ注入・checkpoint・history.csv） | marnie / winrate_2 | - | - | 参考値のみ（ノイズ帯） | done | 配管検証のみ。本番レシピ: `--pop 12 --elite 3 --iters 30 --games 24`（≈40分/デッキ @627g/min）はサーバー向き。聖域は実行時 band ガードが保証 |
