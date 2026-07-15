# アタッカー運用ポケモン（対戦履歴からの実測。extract_attacker_pokemon.py 生成）

- データ源: `downloads/episodes`（1761 エピソード）
- 対象: HP >= 121 かつ active 出現 >= 5 試合
- アタッカー度 = ATTACK宣言試合数 / active出現試合数、閾値 0.5 で2値化
- アタッカー判定 = 23 種 / 集計対象 33 種

## ATTACKER_IDS_LEARNED（agent が読む集合）

```python
ATTACKER_IDS_LEARNED = {58, 63, 96, 108, 116, 117, 121, 169, 190, 245, 272, 345, 381, 401, 431, 648, 666, 674, 678, 743, 849, 861, 1031}
```

## 全集計（アタッカー度降順）

| id | name | HP | 出現 | 攻撃 | 度 | アタッカー |
|---:|---|---:|---:|---:|---:|:---:|
| 849 | Mega Lopunny ex | 330 | 22 | 22 | 1.00 | ✓ |
| 861 | Mega Froslass ex | 310 | 16 | 16 | 1.00 | ✓ |
| 245 | Alakazam | 140 | 6 | 6 | 1.00 | ✓ |
| 743 | Alakazam | 140 | 927 | 924 | 1.00 | ✓ |
| 648 | Marnie's Grimmsnarl ex | 320 | 711 | 706 | 0.99 | ✓ |
| 381 | Cynthia's Garchomp ex | 330 | 208 | 206 | 0.99 | ✓ |
| 121 | Dragapult ex | 320 | 68 | 67 | 0.98 | ✓ |
| 1031 | Mega Starmie ex | 330 | 174 | 171 | 0.98 | ✓ |
| 401 | Team Rocket's Spidops | 130 | 42 | 41 | 0.98 | ✓ |
| 678 | Mega Lucario ex | 340 | 124 | 120 | 0.97 | ✓ |
| 190 | Archaludon ex | 300 | 95 | 92 | 0.97 | ✓ |
| 108 | Wellspring Mask Ogerpon ex | 210 | 46 | 44 | 0.96 | ✓ |
| 116 | Okidogi | 130 | 106 | 101 | 0.95 | ✓ |
| 272 | Lillie’s Clefairy ex | 190 | 55 | 47 | 0.85 | ✓ |
| 63 | Raging Bolt ex | 240 | 56 | 47 | 0.84 | ✓ |
| 58 | Great Tusk | 140 | 30 | 25 | 0.83 | ✓ |
| 431 | Team Rocket's Mewtwo ex | 280 | 21 | 14 | 0.67 | ✓ |
| 96 | Teal Mask Ogerpon ex | 210 | 96 | 63 | 0.66 | ✓ |
| 169 | Duraludon | 130 | 106 | 67 | 0.63 | ✓ |
| 666 | Cinderace | 160 | 69 | 43 | 0.62 | ✓ |
| 345 | Crustle | 150 | 378 | 233 | 0.62 | ✓ |
| 117 | Cornerstone Mask Ogerpon ex | 210 | 70 | 38 | 0.54 | ✓ |
| 674 | Hariyama | 150 | 10 | 5 | 0.50 | ✓ |
| 756 | Mega Kangaskhan ex | 300 | 380 | 188 | 0.49 |  |
| 135 | Bloodmoon Ursaluna | 150 | 9 | 4 | 0.44 |  |
| 1052 | Barbaracle | 130 | 40 | 2 | 0.05 |  |
| 140 | Fezandipiti ex | 210 | 141 | 1 | 0.01 |  |
| 66 | Dudunsparce | 140 | 610 | 3 | 0.01 |  |
| 184 | Latias ex | 210 | 93 | 0 | 0.00 |  |
| 342 | Cynthia's Roserade | 130 | 56 | 0 | 0.00 |  |
| 1071 | Meowth ex | 170 | 20 | 0 | 0.00 |  |
| 98 | Chandelure | 130 | 10 | 0 | 0.00 |  |
| 607 | Terrakion | 140 | 5 | 0 | 0.00 |  |
