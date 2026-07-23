# レート帯センサス — days: 2026-07-19, 2026-07-20, 2026-07-21

- LB スナップショット: `downloads/leaderboard/pokemon-tcg-ai-battle-publicleaderboard-2026-07-23T01_29_15.csv`（帯割当は現在スコアであり試合時点のレートではない）
- エピソード: 1500 試合（読込失敗 0）= 3000 プレイヤー側
- 生成: `scripts/ladder_band_census.py`

## 帯 × サブタイプ（プレイヤー側の延べ数）

| subtype | <900 | 900-1100 | 1100+ | unknown | total |
|---|---|---|---|---|---|
| alakazam | 97 | 468 | 468 | 0 | 1033 |
| marnie | 101 | 671 | 127 | 6 | 905 |
| crustle_wall | 34 | 253 | 14 | 0 | 301 |
| rocket | 4 | 173 | 119 | 0 | 296 |
| garchomp | 3 | 2 | 231 | 0 | 236 |
| dragapult | 0 | 0 | 138 | 0 | 138 |
| other | 0 | 49 | 11 | 0 | 60 |
| froslass_starmie | 0 | 26 | 0 | 0 | 26 |
| kangaskhan | 0 | 3 | 0 | 0 | 3 |
| lucario | 0 | 1 | 0 | 0 | 1 |
| archaludon | 0 | 1 | 0 | 0 | 1 |
| **TOTAL** | **239** | **1647** | **1108** | **6** | **3000** |

## <900 帯の構成（N=239 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 101 | 42.3 | 53.5% | KawattaTaido (791): 100 / Mykhailo Kalus (873): 1 |
| alakazam | 97 | 40.6 | 50.5% | 齐乐 (766): 95 / Abhyuday (874): 1 / MooDerEchte (730): 1 |
| crustle_wall | 34 | 14.2 | 47.1% | 懒惰的金枪鱼 (878): 32 / S4nkurero (834): 1 / Marshall Maximizer (763): 1 |
| rocket | 4 | 1.7 | 25.0% | やる気元気ミワハルキ (873): 3 / xnx (860): 1 |
| garchomp | 3 | 1.3 | 0.0% | 懒惰的金枪鱼 (878): 3 |

### <900 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×100 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: KawattaTaido:100
- **marnie #2** ×1 — マシマシラ4 / マリィのベロバー4 / ノコッチ3 / マリィのギモー3 — pilots: Mykhailo Kalus:1
- **alakazam #1** ×96 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: 齐乐:95 / MooDerEchte:1
- **alakazam #2** ×1 — ケーシィ4 / ユンゲラー4 / ノコッチ4 / フーディン3 — pilots: Abhyuday:1
- **crustle_wall #1** ×32 — イシズマイ4 / イワパレス4 / メガガルーラex4 — pilots: 懒惰的金枪鱼:32
- **crustle_wall #2** ×1 — イシズマイ4 / イワパレス4 / メガガルーラex3 / オーガポン いしずえのめんex1 — pilots: S4nkurero:1
- **crustle_wall #3** ×1 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: Marshall Maximizer:1
- **rocket #1** ×3 — ロケット団のワナイダー4 / ロケット団のタマンチュラ4 / ロケット団のミミッキュ3 / ロケット団のフリーザー2 — pilots: やる気元気ミワハルキ:3
- **rocket #2** ×1 — クマシュン4 / オーガポン いしずえのめんex1 / ロケット団のフリーザー1 — pilots: xnx:1
- **garchomp #1** ×3 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのガブリアスex3 — pilots: 懒惰的金枪鱼:3

## 900-1100 帯の構成（N=1647 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 671 | 40.7 | 54.0% | Kotaro OKUYAMA (1070): 121 / bono (1014): 115 / jiatu.l (1038): 110 / __Taichicchi__ (1093): 77 |
| alakazam | 468 | 28.4 | 40.2% | Oshbocker (988): 64 / ei ei ei yikuso (1028): 56 / Dieter (1037): 52 / Team KASA. (1071): 50 |
| crustle_wall | 253 | 15.4 | 40.9% | Oshbocker (988): 72 / __Taichicchi__ (1093): 35 / SQUIRTLE (prime) (1075): 29 / koala_bear “もりたにあん” (1013): 26 |
| rocket | 173 | 10.5 | 53.2% | THIRD PTCG Club (1077): 153 / {{ team_name }} (1039): 13 / palsystem (1004): 7 |
| other | 49 | 3.0 | 49.0% | Battle Data Base (1051): 22 / PP.TAKEHIRO_KAWADA (960): 12 / Banjo (952): 11 / Jack (1020): 2 |
| froslass_starmie | 26 | 1.6 | 42.3% | taksai (1066): 26 |
| kangaskhan | 3 | 0.2 | 33.3% | zoroark190 (1007): 3 |
| garchomp | 2 | 0.1 | 50.0% | Orin (1055): 1 / Topdecking is All You Need (1010): 1 |
| lucario | 1 | 0.1 | 100.0% | mitomeat823 (992): 1 |
| archaludon | 1 | 0.1 | 100.0% | Canon (945): 1 |

### 900-1100 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×284 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Kotaro OKUYAMA:121 / Rafael:48 / Oshbocker:47
- **marnie #2** ×212 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: bono:115 / __Taichicchi__:77 / iwashi:18
- **marnie #3** ×110 — マリィのベロバー4 / マシマシラ4 / マリィのオーロンゲex3 / マリィのギモー3 — pilots: jiatu.l:110
- **alakazam #1** ×342 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Oshbocker:64 / Team KASA.:50 / Benarg:43
- **alakazam #2** ×66 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: miya:36 / Dieter:13 / Team Rot-Weiß:7
- **alakazam #3** ×56 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: ei ei ei yikuso:56
- **crustle_wall #1** ×138 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: Oshbocker:72 / __Taichicchi__:35 / koala_bear “もりたにあん”:26
- **crustle_wall #2** ×61 — イシズマイ4 / イワパレス4 / メガガルーラex4 — pilots: SQUIRTLE (prime):29 / カントー地方マスター:14 / Zachary Zhang:13
- **crustle_wall #3** ×37 — イシズマイ4 / イワパレス4 / メガガルーラex3 / オーガポン いしずえのめんex1 — pilots: gecogeco:22 / Dries @ Tufa Labs:15
- **rocket #1** ×153 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: THIRD PTCG Club:153
- **rocket #2** ×13 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: {{ team_name }}:13
- **rocket #3** ×7 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のフリーザー2 / ロケット団のミュウツーex2 — pilots: palsystem:7
- **other #1** ×22 — Nのゾロアークex4 / Nのゾロア4 / Nのレシラム2 / Nのゼクロム1 — pilots: Battle Data Base:22
- **other #2** ×12 — サルノリ4 / バチンキー4 / カミッチュ4 / セレビィ4 — pilots: PP.TAKEHIRO_KAWADA:12
- **other #3** ×11 — キバニア4 / メガサメハダーex4 / エレズン2 / ストリンダー2 — pilots: Banjo:11
- **froslass_starmie #1** ×24 — ユキワラシ3 / メガユキメノコex3 / ヒトデマン3 / メガスターミーex3 — pilots: taksai:24
- **froslass_starmie #2** ×2 — ユキワラシ3 / メガユキメノコex3 / ヒトデマン3 / メガスターミーex3 — pilots: taksai:2
- **kangaskhan #1** ×3 — メガガルーラex4 / ニャースex3 / オーガポン みどりのめんex3 / ラティアスex2 — pilots: zoroark190:3
- **garchomp #1** ×1 — シロナのフカマル4 / シロナのガバイト4 / シロナのロゼリア4 / シロナのロズレイド4 — pilots: Orin:1
- **garchomp #2** ×1 — シロナのロゼリア4 / シロナのロズレイド4 / シロナのフカマル4 / シロナのガバイト4 — pilots: Topdecking is All You Need:1
- **lucario #1** ×1 — リオル4 / メガルカリオex4 / ソルロック3 / ルナトーン2 — pilots: mitomeat823:1
- **archaludon #1** ×1 — ブリジュラスex4 / ジュラルドン4 / エースバーン3 / ジーランス2 — pilots: Canon:1

## 1100+ 帯の構成（N=1108 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| alakazam | 468 | 42.2 | 52.1% | Yushin Ito (1128): 190 / Majkel1337 (1159): 175 / Rmy (1118): 103 |
| garchomp | 231 | 20.8 | 55.0% | junlee789 (1149): 213 / Yudai Ueno (1117): 18 |
| dragapult | 138 | 12.5 | 46.4% | LumenLiquidity (1148): 91 / youtube.com/@BigBugginnings (1104): 47 |
| marnie | 127 | 11.5 | 60.6% | Luca (1186): 92 / GUOHAOYANG (1136): 35 |
| rocket | 119 | 10.7 | 63.0% | kashiwashira (1116): 119 |
| crustle_wall | 14 | 1.3 | 21.4% | Budew (1106): 12 / Eduardo Rocha de Andrade (1127): 2 |
| other | 11 | 1.0 | 45.5% | tw_shin (1150): 11 |

### 1100+ 帯の exact リスト上位（サブタイプ毎 top3）

- **alakazam #1** ×413 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Majkel1337:175 / Yushin Ito:135 / Rmy:103
- **alakazam #2** ×55 — ケーシィ4 / ユンゲラー4 / フーディン4 / ノコッチ3 — pilots: Yushin Ito:55
- **garchomp #1** ×231 — シロナのロゼリア4 / シロナのフカマル4 / シロナのガバイト4 / シロナのロズレイド3 — pilots: junlee789:213 / Yudai Ueno:18
- **dragapult #1** ×91 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / ヨマワル2 — pilots: LumenLiquidity:91
- **dragapult #2** ×44 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: youtube.com/@BigBugginnings:44
- **dragapult #3** ×3 — ドラメシヤ4 / ドロンチ4 / ドラパルトex3 / マシマシラ2 — pilots: youtube.com/@BigBugginnings:3
- **marnie #1** ×127 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: Luca:92 / GUOHAOYANG:35
- **rocket #1** ×75 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: kashiwashira:75
- **rocket #2** ×44 — ロケット団のタマンチュラ4 / ロケット団のワナイダー4 / ロケット団のミミッキュ3 / ロケット団のミュウツーex2 — pilots: kashiwashira:44
- **crustle_wall #1** ×12 — イシズマイ4 / イワパレス4 / メガガルーラex4 / シェイミ1 — pilots: Budew:12
- **crustle_wall #2** ×2 — メガガルーラex4 / イシズマイ3 / イワパレス3 — pilots: Eduardo Rocha de Andrade:2
- **other #1** ×10 — ノコッチ4 / ノココッチ3 / ミミロル2 / メガミミロップex2 — pilots: tw_shin:10
- **other #2** ×1 — ノコッチ4 / ノココッチ3 / ミミロル3 / メガミミロップex3 — pilots: tw_shin:1

## unknown 帯の構成（N=6 側）

| subtype | sides | share% | win% | 帯内の上位チーム（スコア: 出現数） |
|---|---|---|---|---|
| marnie | 6 | 100.0 | 16.7% | wwwwwwwwwwwwwwwwwwww (?): 6 |

### unknown 帯の exact リスト上位（サブタイプ毎 top3）

- **marnie #1** ×6 — マシマシラ4 / マリィのベロバー4 / マリィのギモー3 / マリィのオーロンゲex3 — pilots: wwwwwwwwwwwwwwwwwwww:6
