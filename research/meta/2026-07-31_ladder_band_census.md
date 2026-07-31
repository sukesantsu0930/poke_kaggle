# レート帯センサス — days: 2026-07-22, 2026-07-23, 2026-07-24, 2026-07-25, 2026-07-26, 2026-07-27, 2026-07-28, 2026-07-29, 2026-07-30

- LB スナップショット: `downloads/leaderboard/pokemon-tcg-ai-battle-publicleaderboard-2026-07-31T04_00_09.csv`（帯割当は現在スコアであり試合時点のレートではない）
- エピソード: 2250 試合（読込失敗 0）= 4500 プレイヤー側
- 生成: `scripts/ladder_band_census.py`

## 帯 × サブタイプ（プレイヤー側の延べ数）

| subtype | <700 | 700-900 | 900-1100 | 1100+ | unknown | total |
|---|---|---|---|---|---|---|
| marnie | 20 | 133 | 1402 | 700 | 126 | 2381 |
| alakazam | 0 | 0 | 502 | 135 | 8 | 645 |
| rocket | 22 | 33 | 124 | 252 | 66 | 497 |
| crustle_wall | 0 | 11 | 192 | 121 | 1 | 325 |
| garchomp | 0 | 35 | 187 | 4 | 0 | 226 |
| kangaskhan | 0 | 0 | 0 | 48 | 90 | 138 |
| other | 0 | 29 | 105 | 0 | 2 | 136 |
| dragapult | 0 | 1 | 50 | 61 | 0 | 112 |
| froslass_starmie | 0 | 0 | 12 | 0 | 17 | 29 |
| crustle_prism | 0 | 1 | 6 | 0 | 0 | 7 |
| megastarmie | 0 | 0 | 3 | 0 | 0 | 3 |
| archaludon | 0 | 1 | 0 | 0 | 0 | 1 |
| **TOTAL** | **42** | **244** | **2583** | **1321** | **310** | **4500** |

## <700 帯の構成（N=42 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| rocket | 22 | 52.4 | 40.9% | S4nkurero (638): 22 |
| marnie | 20 | 47.6 | 35.0% | Pokémon Day Care (682): 16 / Mega LayerEX (666): 4 |

### <700 帯の exact リスト上位（サブタイプ毎 top3）

- **rocket #1** ×22 — ロケット団のワナイダー4 / ロケット団のタマンチュラ4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: S4nkurero:22
- **marnie #1** ×15 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Pokémon Day Care:15
- **marnie #2** ×5 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Mega LayerEX:4 / Pokémon Day Care:1

## 700-900 帯の構成（N=244 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 133 | 54.5 | 54.1% | __Taichicchi__ (899): 102 / Kh0a (779): 15 / Tanupro (836): 11 / titako0000 (796): 2 |
| garchomp | 35 | 14.3 | 51.4% | junseo lee (819): 32 / Budew (899): 2 / __Taichicchi__ (899): 1 |
| rocket | 33 | 13.5 | 54.5% | __Taichicchi__ (899): 33 |
| other | 29 | 11.9 | 37.9% | Vadim Vasilenko (826): 21 / Battle Data Base (856): 5 / タニシ (822): 2 / yuki0202 (892): 1 |
| crustle_wall | 11 | 4.5 | 63.6% | Budew (899): 10 / Zachary Zhang (864): 1 |
| dragapult | 1 | 0.4 | 0.0% | YutoRagi (875): 1 |
| crustle_prism | 1 | 0.4 | 0.0% | hukuda222 (875): 1 |
| archaludon | 1 | 0.4 | 0.0% | Canon (886): 1 |

### 700-900 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×80 — マリィのベロバー4 / マシマシラ4 / マリィのオーロンゲex3 / マリィのギモー3 — pilots: __Taichicchi__:53 / Kh0a:15 / Tanupro:11
- **marnie #2** ×51 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: __Taichicchi__:49 / titako0000:2
- **marnie #3** ×1 — マシマシラ4 / マリィのベロバー4 / マリィのオーロンゲex3 / ユキメノコ2 — pilots: Budew:1
- **garchomp #1** ×35 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのロズレイド3 — pilots: junseo lee:32 / Budew:2 / __Taichicchi__:1
- **rocket #1** ×33 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: __Taichicchi__:33
- **other #1** ×21 — サルノリ4 / バチンキー4 / カジッチュ4 / カミッチュ4 — pilots: Vadim Vasilenko:21
- **other #2** ×7 — Nのゾロアークex4 / Nのゾロア4 / Nのレシラム2 / Nのゼクロム1 — pilots: Battle Data Base:5 / タニシ:2
- **other #3** ×1 — プルリル4 / ブルンゲルex3 / オーガポン いしずえのめんex2 / ミミロル1 — pilots: yuki0202:1
- **crustle_wall #1** ×10 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: Budew:10
- **crustle_wall #2** ×1 — イシズマイ4 / イワパレス4 / メガガルーラex4 — pilots: Zachary Zhang:1
- **dragapult #1** ×1 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / ノコッチ2 — pilots: YutoRagi:1
- **crustle_prism #1** ×1 — イシズマイ4 / イワパレス4 / エースバーン4 / オーガポン いしずえのめんex2 — pilots: hukuda222:1
- **archaludon #1** ×1 — ブリジュラスex4 / ジュラルドン4 / エースバーン3 / ジーランス2 — pilots: Canon:1

## 900-1100 帯の構成（N=2583 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 1402 | 54.3 | 49.5% | Rmy (1080): 109 / jiatu.l (986): 74 / wwwwwwwwwwwwwwwwwwwwwwwwwwwwww (1034): 74 / me and the lads (1041): 74 |
| alakazam | 502 | 19.4 | 46.7% | Yushin Ito (1053): 124 / Team Rot-Weiß (1077): 65 / Benarg (907): 44 / miya (1058): 36 |
| crustle_wall | 192 | 7.4 | 43.8% | Where is my orbit (1045): 94 / 懒惰的金枪鱼 (1034): 23 / 西松大祐 (1004): 13 / goonew (981): 10 |
| garchomp | 187 | 7.2 | 46.0% | junlee789 (1041): 128 / Yudai Ueno (1003): 15 / Lunariz (1054): 15 / Orin (986): 12 |
| rocket | 124 | 4.8 | 42.7% | kashiwashira (1050): 86 / Oshbocker (1068): 11 / {{ team_name }} 🏆 (1034): 8 / Marshall Maximizer (1051): 7 |
| other | 105 | 4.1 | 60.0% | tw_shin (1001): 40 / lmaffei (965): 29 / Iliamna (980): 21 / vibechu (1050): 8 |
| dragapult | 50 | 1.9 | 52.0% | youtube.com/@BigBugginnings (934): 19 / 213tubo (1073): 15 / Oshbocker (1068): 11 / RtoABC (1013): 5 |
| froslass_starmie | 12 | 0.5 | 58.3% | stardom (929): 12 |
| crustle_prism | 6 | 0.2 | 16.7% | Thai (961): 4 / Marshall Maximizer (1051): 1 / NIWATORI (1025): 1 |
| megastarmie | 3 | 0.1 | 33.3% | WinDecks (963): 3 |

### 900-1100 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×1068 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Rmy:109 / wwwwwwwwwwwwwwwwwwwwwwwwwwwwww:74 / me and the lads:74
- **marnie #2** ×168 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: 213tubo:42 / SQUIRTLE (prime):33 / iwashi:33
- **marnie #3** ×81 — マリィのベロバー4 / マシマシラ4 / マリィのオーロンゲex3 / マリィのギモー3 — pilots: jiatu.l:74 / cm391:6 / Dipam Chakraborty:1
- **alakazam #1** ×393 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Yushin Ito:106 / Team Rot-Weiß:65 / Benarg:44
- **alakazam #2** ×55 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Yushin Ito:18 / miya:18 / insuperabilehart:11
- **alakazam #3** ×21 — ノコッチ4 / ノココッチ4 / ケーシィ4 / ユンゲラー4 — pilots: Pokemon Siuuuu:21
- **crustle_wall #1** ×104 — メガガルーラex4 / イシズマイ3 / イワパレス3 — pilots: Where is my orbit:94 / Oleksandr_Savsunenko:10
- **crustle_wall #2** ×45 — イシズマイ4 / イワパレス4 / メガガルーラex4 — pilots: 懒惰的金枪鱼:23 / 西松大祐:13 / SQUIRTLE (prime):4
- **crustle_wall #3** ×19 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: Oshbocker:10 / Souya__1234:4 / Team Rot-Weiß:3
- **garchomp #1** ×175 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのロズレイド3 — pilots: junlee789:128 / Yudai Ueno:15 / Lunariz:15
- **garchomp #2** ×7 — シロナのフカマル4 / シロナのガバイト4 / シロナのロゼリア4 / シロナのロズレイド4 — pilots: Orin:7
- **garchomp #3** ×5 — シロナのフカマル4 / シロナのガバイト4 / シロナのロゼリア4 / シロナのロズレイド4 — pilots: Orin:5
- **rocket #1** ×54 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: kashiwashira:47 / Marshall Maximizer:7
- **rocket #2** ×15 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: kashiwashira:15
- **rocket #3** ×13 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: kashiwashira:13
- **other #1** ×34 — ノコッチ4 / ノココッチ3 / ミミロル2 / メガミミロップex2 — pilots: tw_shin:34
- **other #2** ×27 — ミミロル4 / ノコッチ4 / ノココッチ4 / メガミミロップex3 — pilots: lmaffei:27
- **other #3** ×22 — サルノリ4 / バチンキー4 / カジッチュ4 / カミッチュ4 — pilots: Iliamna:21 / Oleksandr_Savsunenko:1
- **dragapult #1** ×15 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: youtube.com/@BigBugginnings:15
- **dragapult #2** ×15 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: 213tubo:15
- **dragapult #3** ×11 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: Oshbocker:11
- **froslass_starmie #1** ×11 — ユキワラシ3 / メガユキメノコex3 / ヒトデマン3 / メガスターミーex3 — pilots: stardom:11
- **froslass_starmie #2** ×1 — ユキワラシ3 / メガユキメノコex3 / ヒトデマン3 / メガスターミーex3 — pilots: stardom:1
- **crustle_prism #1** ×4 — マシマシラ4 / イシズマイ4 / イワパレス4 / オーガポン いしずえのめんex2 — pilots: Thai:4
- **crustle_prism #2** ×2 — マシマシラ4 / イシズマイ4 / イワパレス4 / オーガポン いしずえのめんex2 — pilots: Marshall Maximizer:1 / NIWATORI:1
- **megastarmie #1** ×3 — ヒトデマン4 / メガスターミーex3 / ヨマワル2 / サマヨール2 — pilots: WinDecks:3

## 1100+ 帯の構成（N=1321 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 700 | 53.0 | 53.7% | Dominic Peel (1136): 126 / szlachetny snieg (1109): 117 / Dries @ Tufa Labs (1107): 117 / Luca (1136): 92 |
| rocket | 252 | 19.1 | 52.4% | THIRD PTCG Club (1137): 126 / LiamK (1130): 46 / Majkel1337 (1109): 44 / flg (1124): 26 |
| alakazam | 135 | 10.2 | 50.0% | Majkel1337 (1109): 99 / Raja Biswas (1147): 23 / haggle (1125): 5 / Brahim (1156): 5 |
| crustle_wall | 121 | 9.2 | 55.4% | LiamK (1130): 39 / flg (1124): 35 / Majkel1337 (1109): 23 / Dries @ Tufa Labs (1107): 16 |
| dragapult | 61 | 4.6 | 55.7% | LumenLiquidity (1125): 49 / flg (1124): 10 / THIRD PTCG Club (1137): 2 |
| kangaskhan | 48 | 3.6 | 54.2% | James Cox & Henry Chao (1155): 48 |
| garchomp | 4 | 0.3 | 0.0% | Octavi Grau (1107): 4 |

### 1100+ 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×512 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: szlachetny snieg:117 / Luca:92 / Dominic Peel:76
- **marnie #2** ×166 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Dries @ Tufa Labs:58 / Dominic Peel:50 / JZ:46
- **marnie #3** ×10 — マシマシラ4 / マリィのベロバー4 / マリィのオーロンゲex3 / ユキメノコ2 — pilots: 李秉叡（ntumlnoob）:10
- **rocket #1** ×49 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: THIRD PTCG Club:49
- **rocket #2** ×47 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のフリーザー2 — pilots: LiamK:46 / lolzpo + emonga:1
- **rocket #3** ×45 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: THIRD PTCG Club:36 / Dries @ Tufa Labs:9
- **alakazam #1** ×127 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Majkel1337:99 / Raja Biswas:23 / haggle:5
- **alakazam #2** ×5 — ケーシィ4 / フーディン4 / ユンゲラー4 / ノコッチ3 — pilots: Brahim:5
- **alakazam #3** ×2 — ノコッチ4 / ケーシィ4 / ユンゲラー4 / フーディン4 — pilots: Luca:2
- **crustle_wall #1** ×46 — イシズマイ4 / イワパレス4 / メガガルーラex4 — pilots: LiamK:39 / Brahim:7
- **crustle_wall #2** ×35 — イシズマイ4 / イワパレス3 / メガガルーラex2 / オーガポン いしずえのめんex1 — pilots: flg:35
- **crustle_wall #3** ×23 — イシズマイ4 / イワパレス3 / メガガルーラex2 / オーガポン いしずえのめんex1 — pilots: Majkel1337:23
- **dragapult #1** ×48 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / ヨマワル2 — pilots: LumenLiquidity:48
- **dragapult #2** ×12 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: flg:10 / THIRD PTCG Club:2
- **dragapult #3** ×1 — ドラメシヤ4 / ドロンチ4 / マシマシラ2 / ドラパルトex2 — pilots: LumenLiquidity:1
- **kangaskhan #1** ×48 — メガガルーラex3 / ニャースex3 / オーガポン みどりのめんex3 / ラティアスex2 — pilots: James Cox & Henry Chao:48
- **garchomp #1** ×4 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのロズレイド3 — pilots: Octavi Grau:4

## unknown 帯の構成（N=310 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 126 | 40.6 | 42.9% | Eduardo Rocha de Andrade (?): 63 / HowardLeeTW (?): 25 / matheus (?): 9 / Matheus, Dieter, Eduardo (?): 9 |
| kangaskhan | 90 | 29.0 | 62.2% | James Cox (?): 52 / zoroark190 (?): 38 |
| rocket | 66 | 21.3 | 43.9% | Matheus, Dieter, Eduardo (?): 30 / Eduardo Rocha de Andrade (?): 13 / Dieter (?): 11 / {{ team_name }} (?): 5 |
| froslass_starmie | 17 | 5.5 | 70.6% | taksai (?): 17 |
| alakazam | 8 | 2.6 | 50.0% | カントー地方マスター (?): 3 / Donate to Venezuela (?): 2 / Dieter (?): 2 / rick & shikitora (?): 1 |
| other | 2 | 0.6 | 100.0% | PP.TAKEHIRO_KAWADA (?): 2 |
| crustle_wall | 1 | 0.3 | 0.0% | koala_bear “もりたにあん” (?): 1 |

### unknown 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×65 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: HowardLeeTW:25 / matheus:9 / Matheus, Dieter, Eduardo:9
- **marnie #2** ×33 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Eduardo Rocha de Andrade:28 / ebisu_ya:4 / Y:1
- **marnie #3** ×28 — マシマシラ4 / マリィのベロバー4 / マリィのオーロンゲex3 / ユキメノコ2 — pilots: Eduardo Rocha de Andrade:28
- **kangaskhan #1** ×90 — メガガルーラex3 / ニャースex3 / オーガポン みどりのめんex3 / ラティアスex2 — pilots: James Cox:52 / zoroark190:38
- **rocket #1** ×54 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: Matheus, Dieter, Eduardo:30 / Eduardo Rocha de Andrade:13 / Dieter:11
- **rocket #2** ×5 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: {{ team_name }}:5
- **rocket #3** ×4 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: Timmy Juicehouse:4
- **froslass_starmie #1** ×17 — ユキワラシ3 / メガユキメノコex3 / ヒトデマン3 / メガスターミーex3 — pilots: taksai:17
- **alakazam #1** ×7 — フーディン4 / ケーシィ4 / ユンゲラー4 / ノコッチ3 — pilots: カントー地方マスター:3 / Donate to Venezuela:2 / Dieter:2
- **alakazam #2** ×1 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: rick & shikitora:1
- **other #1** ×2 — サルノリ4 / バチンキー4 / カミッチュ4 / セレビィ4 — pilots: PP.TAKEHIRO_KAWADA:2
- **crustle_wall #1** ×1 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: koala_bear “もりたにあん”:1

## dump: 900-1100 帯 exact リスト上位 10 件 → `decks\opponents\band_900_0731`

- `01_marnie_1068x.csv` ×1068 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3
- `02_alakazam_393x.csv` ×393 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3
- `03_garchomp_175x.csv` ×175 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのロズレイド3
- `04_marnie_168x.csv` ×168 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3
- `05_crustle_wall_104x.csv` ×104 — メガガルーラex4 / イシズマイ3 / イワパレス3
- `06_marnie_81x.csv` ×81 — マリィのベロバー4 / マシマシラ4 / マリィのオーロンゲex3 / マリィのギモー3
- `07_marnie_55x.csv` ×55 — マシマシラ4 / マリィのベロバー3 / マリィのギモー3 / マリィのオーロンゲex3
- `08_alakazam_55x.csv` ×55 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3
- `09_rocket_54x.csv` ×54 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2
- `10_crustle_wall_45x.csv` ×45 — イシズマイ4 / イワパレス4 / メガガルーラex4
