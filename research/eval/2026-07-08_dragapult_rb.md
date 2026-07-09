# eval_battery: dragapult_rb（2026-07-08）

- agent: `agents/dragapult_rb` / deck: `decks/candidates/2026-06-30_top5/popular_4_dragapult.csv`
- L2: field=`research/meta/2026-07-08_field.csv` games/マッチ=30（P-03: ±10pt級ノイズ帯）
- L3: holdout=`downloads/episodes/2026-07-05` cards=119,120,121 min-score=900 max-games=60
- 判定規則: L2改善 ∧ L3非悪化（±3pt=ノイズ帯 / 5pt超低下=コンテキスト別に調査）。正典: `docs/planning/評価方法.md`

## サマリ

- **L1**: 合格（exit=0） — `decisions=542 wins=10/10`
- **L2**: 制圧度（シェア加重勝率）: 70.8%  (covered share 97.4%) / 最弱マッチアップ: garchomp 37%, archaludon 43%, alakazam 60%
- **L3**: (not found) — `games=0` holdout=downloads/episodes/2026-07-05

## L1 check_agent（不変条件）

- cmd: `scripts/check_agent.py --agent agents/dragapult_rb --deck decks/candidates/2026-06-30_top5/popular_4_dragapult.csv --games 10`（exit=0, 1s）

```
decisions=542 wins=10/10
DIAG={'decisions': 542, 'policy_ok': 542, 'errors': 0, 'option_errors': 0}
OK all invariants pass
```

## L2 gauntlet（メタ加重プール対戦）

- cmd: `scripts/gauntlet.py --agent agents/dragapult_rb --deck decks/candidates/2026-06-30_top5/popular_4_dragapult.csv --field research/meta/2026-07-08_field.csv --games 30`（exit=0, 62s）

```
dragapult_rb vs marnie [target=p0]: p0=13 p1=2 draw=0 unfinished=0 start_failed=0
dragapult_rb vs marnie [target=p1]: p0=4 p1=11 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs marnie: 24-6 (80.0%) share=34.0%

dragapult_rb vs alakazam [target=p0]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
dragapult_rb vs alakazam [target=p1]: p0=4 p1=11 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs alakazam: 18-12 (60.0%) share=20.0%

dragapult_rb vs kangaskhan [target=p0]: p0=13 p1=2 draw=0 unfinished=0 start_failed=0
dragapult_rb vs kangaskhan [target=p1]: p0=5 p1=10 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs kangaskhan: 23-7 (76.7%) share=9.5%

dragapult_rb vs garchomp [target=p0]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
dragapult_rb vs garchomp [target=p1]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs garchomp: 11-19 (36.7%) share=8.5%

dragapult_rb vs okidogi [target=p0]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
dragapult_rb vs okidogi [target=p1]: p0=4 p1=11 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs okidogi: 25-5 (83.3%) share=4.8%

dragapult_rb vs comfey_yveltal [target=p0]: p0=13 p1=2 draw=0 unfinished=0 start_failed=0
dragapult_rb vs comfey_yveltal [target=p1]: p0=2 p1=13 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs comfey_yveltal: 26-4 (86.7%) share=4.8%

dragapult_rb vs chandelure [target=p0]: p0=9 p1=6 draw=0 unfinished=0 start_failed=0
dragapult_rb vs chandelure [target=p1]: p0=5 p1=10 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs chandelure: 19-11 (63.3%) share=4.5%

dragapult_rb vs lopunny [target=p0]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
dragapult_rb vs lopunny [target=p1]: p0=2 p1=13 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs lopunny: 27-3 (90.0%) share=3.8%

dragapult_rb vs megastarmie [target=p0]: p0=9 p1=6 draw=0 unfinished=0 start_failed=0
dragapult_rb vs megastarmie [target=p1]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs megastarmie: 18-12 (60.0%) share=3.5%

dragapult_rb vs rocket [target=p0]: p0=15 p1=0 draw=0 unfinished=0 start_failed=0
dragapult_rb vs rocket [target=p1]: p0=0 p1=15 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs rocket: 30-0 (100.0%) share=2.0%

dragapult_rb vs archaludon [target=p0]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
dragapult_rb vs archaludon [target=p1]: p0=8 p1=7 draw=0 unfinished=0 start_failed=0
==> dragapult_rb vs archaludon: 13-17 (43.3%) share=2.0%


=== gauntlet: agents/dragapult_rb (30 games/matchup) ===
       archetype  share%     W-L    WR%
          marnie    34.0  24-6    80.0
        alakazam    20.0  18-12   60.0
      kangaskhan     9.5  23-7    76.7
        garchomp     8.5  11-19   36.7
         okidogi     4.8  25-5    83.3
  comfey_yveltal     4.8  26-4    86.7
      chandelure     4.5  19-11   63.3
         lopunny     3.8  27-3    90.0
     megastarmie     3.5  18-12   60.0
          rocket     2.0  30-0   100.0
      archaludon     2.0  13-17   43.3
----------------------------------------
制圧度（シェア加重勝率）: 70.8%  (covered share 97.4%)
最弱マッチアップ: garchomp 37%, archaludon 43%, alakazam 60%
```

## L3 replay_divergence（人間アンカー・ホールドアウト日）

- cmd: `scripts/replay_divergence.py --episodes downloads/episodes/2026-07-05 --agent agents/dragapult_rb --archetype-cards 119,120,121 --leaderboard downloads/leaderboard --min-score 900 --max-games 60`（exit=0, 24s）

```
games=0 pilots={}
no decisions

-- SelectContext別 一致率（不一致の多い順） --

-- R-21 IS_FIRST 上位ピロットの実選択: {}
-- R-22 MULLIGAN 上位ピロットの実選択: {}

-- 不一致パターン上位（ctx / 人間の第1選択 / 我々の第1選択） --

-- 不一致サンプル --
```
