# eval_battery: alakazam_rb（2026-07-08）

- agent: `agents/alakazam_rb` / deck: `decks/candidates/alakazam_5th.csv`
- L2: field=`research/meta/2026-07-08_field.csv` games/マッチ=30（P-03: ±10pt級ノイズ帯）
- L3: holdout=`downloads/episodes/2026-07-05` cards=741,742,743 min-score=900 max-games=60
- 判定規則: L2改善 ∧ L3非悪化（±3pt=ノイズ帯 / 5pt超低下=コンテキスト別に調査）。正典: `docs/planning/評価方法.md`

## サマリ

- **L1**: 合格（exit=0） — `decisions=676 wins=9/10`
- **L2**: 制圧度（シェア加重勝率）: 42.9%  (covered share 97.4%) / 最弱マッチアップ: rocket 10%, chandelure 17%, marnie 27%
- **L3**: TOTAL agree 2397/4645 = 51.6% — `games=60` holdout=downloads/episodes/2026-07-05

## L1 check_agent（不変条件）

- cmd: `scripts/check_agent.py --agent agents/alakazam_rb --deck decks/candidates/alakazam_5th.csv --games 10`（exit=0, 1s）

```
decisions=676 wins=9/10
DIAG={'decisions': 676, 'policy_ok': 676, 'errors': 0, 'option_errors': 0}
OK all invariants pass
```

## L2 gauntlet（メタ加重プール対戦）

- cmd: `scripts/gauntlet.py --agent agents/alakazam_rb --deck decks/candidates/alakazam_5th.csv --field research/meta/2026-07-08_field.csv --games 30`（exit=0, 42s）

```
alakazam_rb vs marnie [target=p0]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
alakazam_rb vs marnie [target=p1]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs marnie: 8-22 (26.7%) share=34.0%

alakazam_rb vs alakazam [target=p0]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
alakazam_rb vs alakazam [target=p1]: p0=8 p1=7 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs alakazam: 14-16 (46.7%) share=20.0%

alakazam_rb vs kangaskhan [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs kangaskhan [target=p1]: p0=5 p1=10 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs kangaskhan: 20-10 (66.7%) share=9.5%

alakazam_rb vs garchomp [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs garchomp [target=p1]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs garchomp: 15-15 (50.0%) share=8.5%

alakazam_rb vs okidogi [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs okidogi [target=p1]: p0=4 p1=11 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs okidogi: 21-9 (70.0%) share=4.8%

alakazam_rb vs comfey_yveltal [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs comfey_yveltal [target=p1]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs comfey_yveltal: 18-12 (60.0%) share=4.8%

alakazam_rb vs chandelure [target=p0]: p0=2 p1=13 draw=0 unfinished=0 start_failed=0
alakazam_rb vs chandelure [target=p1]: p0=12 p1=3 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs chandelure: 5-25 (16.7%) share=4.5%

alakazam_rb vs lopunny [target=p0]: p0=9 p1=6 draw=0 unfinished=0 start_failed=0
alakazam_rb vs lopunny [target=p1]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs lopunny: 17-13 (56.7%) share=3.8%

alakazam_rb vs megastarmie [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs megastarmie [target=p1]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs megastarmie: 19-11 (63.3%) share=3.5%

alakazam_rb vs rocket [target=p0]: p0=1 p1=14 draw=0 unfinished=0 start_failed=0
alakazam_rb vs rocket [target=p1]: p0=13 p1=2 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs rocket: 3-27 (10.0%) share=2.0%

alakazam_rb vs archaludon [target=p0]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
alakazam_rb vs archaludon [target=p1]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
==> alakazam_rb vs archaludon: 19-11 (63.3%) share=2.0%


=== gauntlet: agents/alakazam_rb (30 games/matchup) ===
       archetype  share%     W-L    WR%
          marnie    34.0   8-22   26.7
        alakazam    20.0  14-16   46.7
      kangaskhan     9.5  20-10   66.7
        garchomp     8.5  15-15   50.0
         okidogi     4.8  21-9    70.0
  comfey_yveltal     4.8  18-12   60.0
      chandelure     4.5   5-25   16.7
         lopunny     3.8  17-13   56.7
     megastarmie     3.5  19-11   63.3
          rocket     2.0   3-27   10.0
      archaludon     2.0  19-11   63.3
----------------------------------------
制圧度（シェア加重勝率）: 42.9%  (covered share 97.4%)
最弱マッチアップ: rocket 10%, chandelure 17%, marnie 27%
```

## L3 replay_divergence（人間アンカー・ホールドアウト日）

- cmd: `scripts/replay_divergence.py --episodes downloads/episodes/2026-07-05 --agent agents/alakazam_rb --archetype-cards 741,742,743 --leaderboard downloads/leaderboard --min-score 900 --max-games 60`（exit=0, 31s）

```
games=60 pilots={'THIRD PTCG Club(1055)': 13, 'aidy(998)': 16, 'Ajishio(1030)': 8, 'みずあめ(1004)': 3, 'tsukammo(980)': 8, 'みがわり(975)': 3, '変化の書ゾロアーク(989)': 5, 'llkarill(966)': 1, 'e-toppo(963)': 1, 'kawachi(1019)': 2}

TOTAL agree 2397/4645 = 51.6%

-- SelectContext別 一致率（不一致の多い順） --
                      MAIN: 925/2658 = 35%
                   TO_HAND: 508/815 = 62%
                 TO_ACTIVE: 153/192 = 80%
                  TO_BENCH: 146/182 = 80%
                    SWITCH: 47/75 = 63%
                  ACTIVATE: 319/342 = 93%
               ATTACH_FROM: 10/30 = 33%
                   DISCARD: 1/20 = 5%
                   TO_DECK: 17/35 = 49%
      SETUP_ACTIVE_POKEMON: 51/60 = 85%
                    EVOLVE: 72/79 = 91%
       SETUP_BENCH_POKEMON: 20/25 = 80%
            DISCARD_ENERGY: 43/46 = 93%
         DISCARD_TOOL_CARD: 6/7 = 86%
                  IS_FIRST: 29/29 = 100%
                DRAW_COUNT: 13/13 = 100%
                 ATTACH_TO: 3/3 = 100%
             SWITCH_ENERGY: 27/27 = 100%
                    DAMAGE: 3/3 = 100%
               DETACH_FROM: 2/2 = 100%
       DISCARD_ENERGY_CARD: 2/2 = 100%

-- R-21 IS_FIRST 上位ピロットの実選択: {'YES': 29}
-- R-22 MULLIGAN 上位ピロットの実選択: {}

-- 不一致パターン上位（ctx / 人間の第1選択 / 我々の第1選択） --
   17x           ACTIVATE: human=[1]NO  ours=[0]YES
   13x            TO_HAND: human=[1]CARD  ours=[0]CARD
   12x               MAIN: human=[0]ABILITY/Dudunsparce  ours=[2]ATTACK/Powerful
    9x               MAIN: human=[1]ATTACK/Powerful  ours=[0]ABILITY/Dudunsparce
    8x               MAIN: human=[0]ABILITY/Dudunsparce  ours=[1]END
    8x           TO_BENCH: human=[0]CARD/Dunsparce  ours=[1]CARD/Abra
    7x            TO_HAND: human=[1]CARD/Kadabra  ours=[0]CARD/Dudunsparce
    7x               MAIN: human=[0]EVOLVE/Kadabra/->Abra  ours=[1]EVOLVE/Kadabra/->Abra
    7x            TO_HAND: human=[1]CARD/Dudunsparce  ours=[0]CARD/Kadabra
    7x               MAIN: human=[2]ATTACK/Powerful  ours=[0]ABILITY/Dudunsparce
    7x            TO_HAND: human=[1]CARD/Dudunsparce  ours=[0]CARD/Alakazam
    6x             SWITCH: human=[0]CARD/Dunsparce  ours=[1]CARD/Abra
    6x               MAIN: human=[0]ABILITY/Dudunsparce  ours=[1]ATTACK/Powerful
    6x            TO_HAND: human=[1]CARD/Dudunsparce  ours=[0]CARD/Dudunsparce
    6x           ACTIVATE: human=[0]YES  ours=[1]NO
    6x             EVOLVE: human=[1]EVOLVE/Alakazam/->Abra  ours=[0]EVOLVE/Alakazam/->Abra
    6x        ATTACH_FROM: human=[0]CARD/Budew  ours=[1]CARD/Cubchoo
    6x            TO_HAND: human=[0]CARD/Kadabra  ours=[1]CARD/Dudunsparce
    6x            TO_HAND: human=[1]CARD/Alakazam  ours=[0]CARD/Alakazam
    5x            TO_HAND: human=[0]CARD/Dudunsparce  ours=[1]CARD/Kadabra

-- 不一致サンプル --
  83970415 THIRD PTCG Club MAIN
    human: [0]PLAY/Enhanced Hammer
    ours : [6]PLAY/Dunsparce
  83970415 THIRD PTCG Club MAIN
    human: [0]EVOLVE/Kadabra/->Abra
    ours : [4]PLAY/Dunsparce
  83970415 THIRD PTCG Club MAIN
    human: [2]PLAY/Buddy-Buddy Poffin
    ours : [1]PLAY/Dunsparce
  83970415 THIRD PTCG Club TO_ACTIVE
    human: [4]CARD/Dunsparce
    ours : [0]CARD/Kadabra
  83970415 THIRD PTCG Club MAIN
    human: [3]ATTACH/Telepath Psychic Energy/->Alakazam
    ours : [0]PLAY/Dunsparce
  83970415 THIRD PTCG Club MAIN
    human: [1]EVOLVE/Kadabra/->Abra
    ours : [0]PLAY/Poké Pad
  83970415 THIRD PTCG Club MAIN
    human: [1]PLAY/Hilda
    ours : [0]PLAY/Poké Pad
  83970415 THIRD PTCG Club TO_HAND
    human: [0]CARD/Dudunsparce
    ours : [4]CARD/Kadabra
  83970415 THIRD PTCG Club TO_HAND
    human: [0]CARD/Dudunsparce
    ours : [1]CARD/Kadabra
  83970415 THIRD PTCG Club MAIN
    human: [2]ATTACH/Enriching Energy/->Alakazam
    ours : [1]PLAY/Dunsparce
  83970415 THIRD PTCG Club MAIN
    human: [2]EVOLVE/Alakazam/->Kadabra
    ours : [1]PLAY/Dunsparce
  83970415 THIRD PTCG Club MAIN
    human: [1]EVOLVE/Dudunsparce/->Dunsparce
    ours : [3]PLAY/Poké Pad
  83970415 THIRD PTCG Club MAIN
    human: [5]PLAY/Nighttime Mine
    ours : [7]ABILITY/Dudunsparce
  83970415 THIRD PTCG Club MAIN
    human: [4]PLAY/Dawn
    ours : [1]PLAY/Poké Pad
  83970415 THIRD PTCG Club MAIN
    human: [5]ABILITY/Dudunsparce
    ours : [1]PLAY/Poké Pad
  83970415 THIRD PTCG Club MAIN
    human: [7]ATTACH/Lucky Helmet/->Alakazam
    ours : [1]PLAY/Poké Pad
  83970415 THIRD PTCG Club MAIN
    human: [5]PLAY/Poké Pad
    ours : [6]PLAY/Dunsparce
  83970415 THIRD PTCG Club TO_HAND
    human: (none)
    ours : [0]CARD/Dudunsparce
  83970415 THIRD PTCG Club MAIN
    human: [3]ATTACK/Powerful Hand
    ours : [2]EVOLVE/Alakazam/->Kadabra
  83970415 THIRD PTCG Club MAIN
    human: [8]PLAY/Night Stretcher
    ours : [19]PLAY/Fezandipiti ex
  83970415 THIRD PTCG Club MAIN
    human: [13]EVOLVE/Alakazam/->Kadabra
    ours : [18]PLAY/Fezandipiti ex
  83970415 THIRD PTCG Club MAIN
    human: [6]EVOLVE/Dudunsparce/->Dunsparce
    ours : [0]PLAY/Sacred Ash
  83970415 THIRD PTCG Club MAIN
    human: [11]EVOLVE/Dudunsparce/->Dunsparce
    ours : [0]PLAY/Sacred Ash
  83970415 THIRD PTCG Club MAIN
    human: [30]ABILITY/Dudunsparce
    ours : [29]ABILITY/Dudunsparce
  83970415 THIRD PTCG Club MAIN
    human: [21]EVOLVE/Alakazam/->Kadabra
    ours : [26]PLAY/Buddy-Buddy Poffin
  83970415 THIRD PTCG Club ACTIVATE
    human: [1]NO
    ours : [0]YES
  83970415 THIRD PTCG Club MAIN
    human: [27]ATTACK/Powerful Hand
    ours : [25]PLAY/Buddy-Buddy Poffin
  83970415 THIRD PTCG Club MAIN
    human: [23]ABILITY/Dudunsparce
    ours : [21]PLAY/Buddy-Buddy Poffin
  83970415 THIRD PTCG Club MAIN
    human: [8]ATTACH/Telepath Psychic Energy/->Alakazam
    ours : [17]PLAY/Buddy-Buddy Poffin
  83970415 THIRD PTCG Club MAIN
    human: [16]ATTACH/Telepath Psychic Energy/->Alakazam
    ours : [20]PLAY/Dunsparce
```
