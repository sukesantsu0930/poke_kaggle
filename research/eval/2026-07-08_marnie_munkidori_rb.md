# eval_battery: marnie_munkidori_rb（2026-07-08）

- agent: `agents/marnie_munkidori_rb` / deck: `decks/candidates/2026-06-30_top5/winrate_2_marnie_grimmsnarl.csv`
- L2: field=`research/meta/2026-07-08_field.csv` games/マッチ=30（P-03: ±10pt級ノイズ帯）
- L3: holdout=`downloads/episodes/2026-07-05` cards=648,112 min-score=900 max-games=60
- 判定規則: L2改善 ∧ L3非悪化（±3pt=ノイズ帯 / 5pt超低下=コンテキスト別に調査）。正典: `docs/planning/評価方法.md`

## サマリ

- **L1**: 合格（exit=0） — `decisions=629 wins=10/10`
- **L2**: 制圧度（シェア加重勝率）: 55.7%  (covered share 97.4%) / 最弱マッチアップ: archaludon 20%, marnie 37%, garchomp 40%
- **L3**: TOTAL agree 3652/5637 = 64.8% — `games=60` holdout=downloads/episodes/2026-07-05

## L1 check_agent（不変条件）

- cmd: `scripts/check_agent.py --agent agents/marnie_munkidori_rb --deck decks/candidates/2026-06-30_top5/winrate_2_marnie_grimmsnarl.csv --games 10`（exit=0, 2s）

```
decisions=629 wins=10/10
DIAG={'decisions': 629, 'policy_ok': 629, 'errors': 0, 'option_errors': 0}
OK all invariants pass
```

## L2 gauntlet（メタ加重プール対戦）

- cmd: `scripts/gauntlet.py --agent agents/marnie_munkidori_rb --deck decks/candidates/2026-06-30_top5/winrate_2_marnie_grimmsnarl.csv --field research/meta/2026-07-08_field.csv --games 30`（exit=0, 46s）

```
marnie_munkidori_rb vs marnie [target=p0]: p0=6 p1=9 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs marnie [target=p1]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs marnie: 11-19 (36.7%) share=34.0%

marnie_munkidori_rb vs alakazam [target=p0]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs alakazam [target=p1]: p0=8 p1=7 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs alakazam: 21-9 (70.0%) share=20.0%

marnie_munkidori_rb vs kangaskhan [target=p0]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs kangaskhan [target=p1]: p0=8 p1=7 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs kangaskhan: 14-16 (46.7%) share=9.5%

marnie_munkidori_rb vs garchomp [target=p0]: p0=8 p1=7 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs garchomp [target=p1]: p0=11 p1=4 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs garchomp: 12-18 (40.0%) share=8.5%

marnie_munkidori_rb vs okidogi [target=p0]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs okidogi [target=p1]: p0=4 p1=11 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs okidogi: 25-5 (83.3%) share=4.8%

marnie_munkidori_rb vs comfey_yveltal [target=p0]: p0=15 p1=0 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs comfey_yveltal [target=p1]: p0=1 p1=14 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs comfey_yveltal: 29-1 (96.7%) share=4.8%

marnie_munkidori_rb vs chandelure [target=p0]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs chandelure [target=p1]: p0=7 p1=8 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs chandelure: 15-15 (50.0%) share=4.5%

marnie_munkidori_rb vs lopunny [target=p0]: p0=14 p1=1 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs lopunny [target=p1]: p0=0 p1=15 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs lopunny: 29-1 (96.7%) share=3.8%

marnie_munkidori_rb vs megastarmie [target=p0]: p0=13 p1=2 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs megastarmie [target=p1]: p0=2 p1=13 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs megastarmie: 26-4 (86.7%) share=3.5%

marnie_munkidori_rb vs rocket [target=p0]: p0=15 p1=0 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs rocket [target=p1]: p0=1 p1=14 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs rocket: 29-1 (96.7%) share=2.0%

marnie_munkidori_rb vs archaludon [target=p0]: p0=1 p1=14 draw=0 unfinished=0 start_failed=0
marnie_munkidori_rb vs archaludon [target=p1]: p0=10 p1=5 draw=0 unfinished=0 start_failed=0
==> marnie_munkidori_rb vs archaludon: 6-24 (20.0%) share=2.0%


=== gauntlet: agents/marnie_munkidori_rb (30 games/matchup) ===
       archetype  share%     W-L    WR%
          marnie    34.0  11-19   36.7
        alakazam    20.0  21-9    70.0
      kangaskhan     9.5  14-16   46.7
        garchomp     8.5  12-18   40.0
         okidogi     4.8  25-5    83.3
  comfey_yveltal     4.8  29-1    96.7
      chandelure     4.5  15-15   50.0
         lopunny     3.8  29-1    96.7
     megastarmie     3.5  26-4    86.7
          rocket     2.0  29-1    96.7
      archaludon     2.0   6-24   20.0
----------------------------------------
制圧度（シェア加重勝率）: 55.7%  (covered share 97.4%)
最弱マッチアップ: archaludon 20%, marnie 37%, garchomp 40%
```

## L3 replay_divergence（人間アンカー・ホールドアウト日）

- cmd: `scripts/replay_divergence.py --episodes downloads/episodes/2026-07-05 --agent agents/marnie_munkidori_rb --archetype-cards 648,112 --leaderboard downloads/leaderboard --min-score 900 --max-games 60`（exit=0, 23s）

```
games=60 pilots={'Shardul Gharat(998)': 5, 'iwashi(1058)': 8, '渡邊征央(1060)': 12, 'Yudai Ueno(978)': 4, 'tonakaiiii(1040)': 8, 'junlee789(1054)': 6, 'hoshippi(991)': 3, 'Ars Noveau(955)': 5, 'easonyanyan(945)': 2, 'kazuki0123(1014)': 7}

TOTAL agree 3652/5637 = 64.8%

-- SelectContext別 一致率（不一致の多い順） --
                      MAIN: 1426/2606 = 55%
                   TO_HAND: 572/819 = 70%
               ATTACH_FROM: 164/357 = 46%
            DAMAGE_COUNTER: 147/261 = 56%
                 ATTACH_TO: 52/130 = 40%
                    DAMAGE: 164/219 = 75%
     REMOVE_DAMAGE_COUNTER: 224/261 = 86%
                  TO_BENCH: 62/91 = 68%
                    SWITCH: 40/56 = 71%
                 TO_ACTIVE: 126/141 = 89%
  REMOVE_DAMAGE_COUNTER_COUNT: 234/243 = 96%
                   DISCARD: 3/12 = 25%
       SETUP_BENCH_POKEMON: 25/27 = 93%
                  ACTIVATE: 145/146 = 99%
      SETUP_ACTIVE_POKEMON: 60/60 = 100%
                  IS_FIRST: 26/26 = 100%
                    EVOLVE: 67/67 = 100%
            DISCARD_ENERGY: 41/41 = 100%
             SWITCH_ENERGY: 53/53 = 100%
                DRAW_COUNT: 15/15 = 100%
               SKILL_ORDER: 6/6 = 100%

-- R-21 IS_FIRST 上位ピロットの実選択: {'YES': 26}
-- R-22 MULLIGAN 上位ピロットの実選択: {}

-- 不一致パターン上位（ctx / 人間の第1選択 / 我々の第1選択） --
  107x        ATTACH_FROM: human=[1]CARD/Marnie's  ours=[0]CARD/Marnie's
   73x          ATTACH_TO: human=[0]CARD/Basic  ours=[0]CARD/Basic
   59x        ATTACH_FROM: human=[2]CARD/Marnie's  ours=[0]CARD/Marnie's
   15x            TO_HAND: human=[0]CARD/Marnie's  ours=[1]CARD/Marnie's
    9x               MAIN: human=[1]ATTACK/Shadow  ours=[0]PLAY/Night
    9x            TO_HAND: human=[1]CARD/Marnie's  ours=[0]CARD/Marnie's
    9x               MAIN: human=[4]ABILITY/Spikemuth  ours=[3]ABILITY/Munkidori
    9x            TO_HAND: human=[2]CARD/Marnie's  ours=[0]CARD/Marnie's
    8x REMOVE_DAMAGE_COUNTER: human=[1]CARD/Munkidori  ours=[0]CARD/Marnie's
    8x     DAMAGE_COUNTER: human=[0]CARD/Archaludon  ours=[2]CARD/Duraludon
    7x            TO_HAND: human=[3]CARD/Marnie's  ours=[0]CARD/Marnie's
    7x               MAIN: human=[4]ABILITY/Spikemuth  ours=[2]ABILITY/Munkidori
    7x               MAIN: human=[0]ATTACH/Handheld  ours=[6]ATTACK/Shadow
    7x            TO_HAND: human=[0]CARD/Marnie's  ours=[2]CARD/Marnie's
    6x               MAIN: human=[6]END  ours=[0]ATTACH/Basic
    6x               MAIN: human=[5]ABILITY/Spikemuth  ours=[3]ABILITY/Munkidori
    6x REMOVE_DAMAGE_COUNTER: human=[2]CARD/Munkidori  ours=[0]CARD/Marnie's
    6x               MAIN: human=[1]ATTACK/Shadow  ours=[0]PLAY/Snorunt
    6x     DAMAGE_COUNTER: human=[0]CARD/Cubchoo  ours=[1]CARD/Budew
    6x REMOVE_DAMAGE_COUNTER: human=[1]CARD/Munkidori  ours=[0]CARD/Munkidori

-- 不一致サンプル --
  83970308 Shardul Gharat MAIN
    human: [0]PLAY/Poké Pad
    ours : [5]PLAY/Marnie's Impidimp
  83970308 Shardul Gharat TO_HAND
    human: [6]CARD/Marnie's Impidimp
    ours : [1]CARD/Marnie's Morgrem
  83970308 Shardul Gharat TO_HAND
    human: [6]CARD/Unfair Stamp
    ours : [9]CARD/Rare Candy
  83970308 Shardul Gharat MAIN
    human: [4]PLAY/Unfair Stamp
    ours : [3]PLAY/Night Stretcher
  83970308 Shardul Gharat TO_HAND
    human: [2]CARD/Marnie's Morgrem
    ours : [6]CARD/Munkidori
  83970308 Shardul Gharat MAIN
    human: [7]EVOLVE/Marnie's Morgrem/->Marnie's Impidimp
    ours : [6]EVOLVE/Marnie's Morgrem/->Marnie's Impidimp
  83970308 Shardul Gharat MAIN
    human: [6]END
    ours : [0]ATTACH/Basic {D} Energy/->Marnie's Morgrem
  83970308 Shardul Gharat MAIN
    human: [9]END
    ours : [0]ATTACH/Basic {D} Energy/->Marnie's Morgrem
  83970308 Shardul Gharat MAIN
    human: [9]PLAY/Spikemuth Gym
    ours : [10]ABILITY/Munkidori
  83970308 Shardul Gharat MAIN
    human: [10]ABILITY/Spikemuth Gym
    ours : [9]ABILITY/Munkidori
  83970308 Shardul Gharat MAIN
    human: [9]EVOLVE/Marnie's Grimmsnarl ex/->Marnie's Morgrem
    ours : [11]ABILITY/Munkidori
  83970308 Shardul Gharat ATTACH_TO
    human: [0]CARD/Basic {D} Energy [1]CARD/Basic {D} Energy [2]CARD/Basic {D} Energy
    ours : [0]CARD/Basic {D} Energy [1]CARD/Basic {D} Energy
  83970308 Shardul Gharat ATTACH_FROM
    human: [1]CARD/Marnie's Morgrem
    ours : [0]CARD/Marnie's Grimmsnarl ex
  83970308 Shardul Gharat MAIN
    human: [6]ATTACH/Handheld Fan/->Marnie's Grimmsnarl ex
    ours : [9]ABILITY/Munkidori
  83970308 Shardul Gharat MAIN
    human: [6]ATTACK/Shadow Bullet
    ours : [2]ATTACH/Basic {D} Energy/->Marnie's Morgrem
  83970308 Shardul Gharat MAIN
    human: [9]ABILITY/Spikemuth Gym
    ours : [8]ABILITY/Munkidori
  83970308 Shardul Gharat MAIN
    human: [6]PLAY/Marnie's Impidimp
    ours : [9]ABILITY/Munkidori
  83970308 Shardul Gharat MAIN
    human: [9]EVOLVE/Marnie's Grimmsnarl ex/->Marnie's Morgrem
    ours : [10]ABILITY/Munkidori
  83970308 Shardul Gharat ATTACH_TO
    human: [0]CARD/Basic {D} Energy [1]CARD/Basic {D} Energy
    ours : [0]CARD/Basic {D} Energy
  83970308 Shardul Gharat ATTACH_FROM
    human: [1]CARD/Marnie's Grimmsnarl ex
    ours : [0]CARD/Marnie's Grimmsnarl ex
  83970308 Shardul Gharat ATTACH_FROM
    human: [2]CARD/Marnie's Impidimp
    ours : [0]CARD/Marnie's Grimmsnarl ex
  83970446 iwashi MAIN
    human: [2]PLAY/Spikemuth Gym
    ours : [5]PLAY/Munkidori
  83970446 iwashi MAIN
    human: [5]END
    ours : [4]PLAY/Marnie's Impidimp
  83970446 iwashi MAIN
    human: [1]PLAY/Poké Pad
    ours : [7]ABILITY/Spikemuth Gym
  83970446 iwashi TO_HAND
    human: [6]CARD/Froslass
    ours : [0]CARD/Marnie's Impidimp
  83970446 iwashi MAIN
    human: [4]PLAY/Marnie's Impidimp
    ours : [6]ABILITY/Spikemuth Gym
  83970446 iwashi MAIN
    human: [8]END
    ours : [7]ABILITY/Spikemuth Gym
  83970446 iwashi MAIN
    human: [0]ATTACH/Basic {D} Energy/->Marnie's Impidimp
    ours : [6]ABILITY/Spikemuth Gym
  83970446 iwashi MAIN
    human: [0]PLAY/Team Rocket's Petrel
    ours : [4]ABILITY/Spikemuth Gym
  83970446 iwashi MAIN
    human: [0]PLAY/Munkidori
    ours : [3]ABILITY/Spikemuth Gym
```
