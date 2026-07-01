# 勝率候補デッキ探索

入力: `downloads\episodes\2026-06-30`
対象: 1000試合、2000プレイヤーデッキ

## 探し方

- まずアーキタイプ単位で、出現数が少なすぎる候補を落とす。
- 単純勝率ではなく Wilson 信頼下限で並べる。少数の 1勝0敗 を過大評価しないため。
- exact 60枚リストも見るが、ここではリストを保存せず主軸カードだけ表示する。
- 最後に相性表を見る。全体勝率が普通でも、特定上位デッキに強い候補は残す。
- 注意: 公開 episode はランダム実験ではないため、デッキ性能と操作者の強さが混ざっている。

## アーキタイプ候補

### クマシュン / オーガポン いしずえのめんex

- 出現数: 9
- 勝敗: 8勝 1敗
- 勝率: 88.9%
- Wilson下限: 56.5%
- 主軸ポケモン: クマシュン / オーガポン いしずえのめんex / ロケット団のフリーザー
- 主要トレーナーズ: クラッシュハンマー / ポケギア3.0 / リーリエの決心 / ボスの指令 / 改造ハンマー / ロケット団のラムダ
- 主な使用者: Michael Krager
- 代表 episode:
  - Episode 82727566 P0: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82727566.json`)
  - Episode 82741433 P0: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82741433.json`)
  - Episode 82742734 P1: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82742734.json`)
  - Episode 82761010 P1: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82761010.json`)
  - Episode 82765489 P1: Michael Krager reward=-1 (`downloads/episodes/2026-06-30/82765489.json`)

### マリィのベロバー / マシマシラ

- 出現数: 59
- 勝敗: 37勝 22敗
- 勝率: 62.7%
- Wilson下限: 50.0%
- 主軸ポケモン: マリィのベロバー / マシマシラ / マリィのオーロンゲex / マリィのギモー / ノコッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / スパイクタウンジム / ふしぎなアメ / ヒカリ
- 主な使用者: kazuki0123, tonakaiiii, puraza
- 代表 episode:
  - Episode 82721427 P0: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82722612 P0: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82722612.json`)
  - Episode 82723127 P1: kazuki0123 reward=1 (`downloads/episodes/2026-06-30/82723127.json`)
  - Episode 82734665 P0: puraza reward=1 (`downloads/episodes/2026-06-30/82734665.json`)
  - Episode 82742037 P0: puraza reward=-1 (`downloads/episodes/2026-06-30/82742037.json`)

### フーディン超

- 出現数: 523
- 勝敗: 275勝 248敗
- 勝率: 52.6%
- Wilson下限: 48.3%
- 主軸ポケモン: ユンゲラー / ケーシィ / フーディン / ノココッチ / ノコッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ヒカリ / トウコ / ふしぎなアメ / 改造ハンマー
- 主な使用者: 【ＡＩと共に、ＡＩと戦う】tubotu, 樹神, Libra, Janglish
- 代表 episode:
  - Episode 82720918 P1: Lapra5 reward=-1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82720920 P1: aidy reward=-1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720922 P1: aidy reward=1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82720987 P1: Ajishio reward=1 (`downloads/episodes/2026-06-30/82720987.json`)
  - Episode 82720990 P0: kawachi reward=-1 (`downloads/episodes/2026-06-30/82720990.json`)

### ブリジュラスex鋼

- 出現数: 754
- 勝敗: 370勝 384敗
- 勝率: 49.1%
- Wilson下限: 45.5%
- 主軸ポケモン: ブリジュラスex / ジュラルドン / エースバーン / ジーランス
- 主要トレーナーズ: リーリエの決心 / ポケパッド / ハイパーボール / ポケギア3.0 / フルメタルラボ / 探検家の先導
- 主な使用者: Moegi, hikarimaru, Myckel Uribe, iwashi
- 代表 episode:
  - Episode 82720905 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720922 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82720923 P1: Furkan Pirinc reward=1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720940 P0: david valor reward=1 (`downloads/episodes/2026-06-30/82720940.json`)
  - Episode 82720948 P1: DaJimmy reward=-1 (`downloads/episodes/2026-06-30/82720948.json`)

### キュワワー / ヒトモシ

- 出現数: 9
- 勝敗: 7勝 2敗
- 勝率: 77.8%
- Wilson下限: 45.3%
- 主軸ポケモン: キュワワー / ヒトモシ / シャンデラ / ランプラー / シェイミ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / トウコ / クセロシキのたくらみ / ボスの指令
- 主な使用者: Dick Jessen William
- 代表 episode:
  - Episode 82728079 P0: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82728079.json`)
  - Episode 82742669 P1: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82742669.json`)
  - Episode 82765677 P0: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82765677.json`)
  - Episode 82774487 P0: Dick Jessen William reward=-1 (`downloads/episodes/2026-06-30/82774487.json`)
  - Episode 82789957 P1: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82789957.json`)

### タマザラシ / トドゼルガ

- 出現数: 22
- 勝敗: 14勝 8敗
- 勝率: 63.6%
- Wilson下限: 43.0%
- 主軸ポケモン: タマザラシ / トドゼルガ / ノコッチ / ノココッチ / スボミー
- 主要トレーナーズ: ふしぎなアメ / なかよしポフィン / リーリエの決心 / 改造ハンマー / ヒカリ / クラッシュハンマー
- 主な使用者: Kimiaki Nakamura, Hamu.py
- 代表 episode:
  - Episode 82724136 P0: Hamu.py reward=-1 (`downloads/episodes/2026-06-30/82724136.json`)
  - Episode 82738580 P1: Kimiaki Nakamura reward=-1 (`downloads/episodes/2026-06-30/82738580.json`)
  - Episode 82740194 P0: Kimiaki Nakamura reward=-1 (`downloads/episodes/2026-06-30/82740194.json`)
  - Episode 82759907 P0: Kimiaki Nakamura reward=1 (`downloads/episodes/2026-06-30/82759907.json`)
  - Episode 82762120 P0: Hamu.py reward=1 (`downloads/episodes/2026-06-30/82762120.json`)

### シロナのフカマル / シロナのガバイト

- 出現数: 85
- 勝敗: 45勝 40敗
- 勝率: 52.9%
- Wilson下限: 42.4%
- 主軸ポケモン: シロナのフカマル / シロナのガバイト / シロナのロゼリア / シロナのロズレイド / シロナのガブリアスex
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / シロナのパワーウエイト / ファイトゴング / ボスの指令
- 主な使用者: Dongwook Kim, katsudon 421, Orin, tw_shin
- 代表 episode:
  - Episode 82736483 P1: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82736483.json`)
  - Episode 82738083 P0: katsudon 421 reward=1 (`downloads/episodes/2026-06-30/82738083.json`)
  - Episode 82741433 P1: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82741433.json`)
  - Episode 82742724 P0: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82742724.json`)
  - Episode 82744158 P0: Dongwook Kim reward=1 (`downloads/episodes/2026-06-30/82744158.json`)

### イダイナキバ / イシズマイ

- 出現数: 67
- 勝敗: 36勝 31敗
- 勝率: 53.7%
- Wilson下限: 41.9%
- 主軸ポケモン: イダイナキバ / イシズマイ / イワパレス / テラキオン
- 主要トレーナーズ: ファイトゴング / ポケパッド / なかよしポフィン / ポケギア3.0 / ポケモンいれかえ / 探検家の先導
- 主な使用者: ykuroka, Super Mippo, SOUTA Sakurai
- 代表 episode:
  - Episode 82764990 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82764990.json`)
  - Episode 82765050 P0: Super Mippo reward=-1 (`downloads/episodes/2026-06-30/82765050.json`)
  - Episode 82765489 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82765489.json`)
  - Episode 82765979 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82765979.json`)
  - Episode 82766469 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82766469.json`)

### メガスターミーex水

- 出現数: 157
- 勝敗: 70勝 87敗
- 勝率: 44.6%
- Wilson下限: 37.0%
- 主軸ポケモン: ヒトデマン / メガスターミーex / エースバーン / ユキワラシ / メガユキメノコex
- 主要トレーナーズ: リーリエの決心 / なかよしポフィン / ポケギア3.0 / ミツルの思いやり / セイジ / クラッシュハンマー
- 主な使用者: Yushin Ito, Shun, tomatomato, barrybao123
- 代表 episode:
  - Episode 82720905 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720920 P0: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720948 P0: Pokkén reward=1 (`downloads/episodes/2026-06-30/82720948.json`)
  - Episode 82720990 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82720990.json`)
  - Episode 82721019 P0: Jaga reward=-1 (`downloads/episodes/2026-06-30/82721019.json`)

### ドラパルト系

- 出現数: 125
- 勝敗: 56勝 69敗
- 勝率: 44.8%
- Wilson下限: 36.4%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / ニャースex
- 主要トレーナーズ: なかよしポフィン / ハイパーボール / リーリエの決心 / アカマツ / クラッシュハンマー / ポケパッド
- 主な使用者: shibushun, Yasuo 0/10/0, milix, nattomaki
- 代表 episode:
  - Episode 82721496 P0: shibushun reward=1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721949 P1: milix reward=1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722024 P0: nattomaki reward=-1 (`downloads/episodes/2026-06-30/82722024.json`)
  - Episode 82722619 P1: orikage reward=1 (`downloads/episodes/2026-06-30/82722619.json`)
  - Episode 82724781 P0: Yasuo 0/10/0 reward=-1 (`downloads/episodes/2026-06-30/82724781.json`)

### キュワワー / シャンデラ

- 出現数: 7
- 勝敗: 5勝 2敗
- 勝率: 71.4%
- Wilson下限: 35.9%
- 主軸ポケモン: キュワワー / シャンデラ / ヒトモシ / ランプラー / シェイミ
- 主要トレーナーズ: クラッシュハンマー / なかよしポフィン / ポケパッド / リーリエの決心 / クセロシキのたくらみ / トウコ
- 主な使用者: yamy893
- 代表 episode:
  - Episode 82742725 P1: yamy893 reward=-1 (`downloads/episodes/2026-06-30/82742725.json`)
  - Episode 82754944 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82754944.json`)
  - Episode 82758787 P1: yamy893 reward=-1 (`downloads/episodes/2026-06-30/82758787.json`)
  - Episode 82761476 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82761476.json`)
  - Episode 82780440 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82780440.json`)

### イイネイヌ / ソルロック

- 出現数: 28
- 勝敗: 14勝 14敗
- 勝率: 50.0%
- Wilson下限: 32.6%
- 主軸ポケモン: イイネイヌ / ソルロック / ルナトーン / カメテテ / ガメノデス
- 主要トレーナーズ: ファイトゴング / ポケパッド / リーリエの決心 / 夜のタンカ / ロケット団の監視塔 / ツールスクラッパー
- 主な使用者: monnosuke
- 代表 episode:
  - Episode 82778386 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82778386.json`)
  - Episode 82779034 P0: monnosuke reward=-1 (`downloads/episodes/2026-06-30/82779034.json`)
  - Episode 82779743 P1: monnosuke reward=-1 (`downloads/episodes/2026-06-30/82779743.json`)
  - Episode 82780323 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82780323.json`)
  - Episode 82780813 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82780813.json`)

### キチキギス / イーブイ

- 出現数: 8
- 勝敗: 5勝 3敗
- 勝率: 62.5%
- Wilson下限: 30.6%
- 主軸ポケモン: キチキギス / イーブイ / マシマシラ / イイネイヌex / ニンフィア
- 主要トレーナーズ: アカマツ / コック / ルチアのアピール / エキサイトスタジアム / チェレン / ミアレガレット
- 主な使用者: Eli C. Lowry
- 代表 episode:
  - Episode 82737546 P1: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82737546.json`)
  - Episode 82738033 P0: Eli C. Lowry reward=-1 (`downloads/episodes/2026-06-30/82738033.json`)
  - Episode 82738538 P0: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82738538.json`)
  - Episode 82739035 P0: Eli C. Lowry reward=-1 (`downloads/episodes/2026-06-30/82739035.json`)
  - Episode 82739682 P1: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82739682.json`)

### メガガルーラex多色

- 出現数: 18
- 勝敗: 9勝 9敗
- 勝率: 50.0%
- Wilson下限: 29.0%
- 主軸ポケモン: メガガルーラex / ニャースex / リーリエのピッピex / ラティアスex / キチキギスex
- 主要トレーナーズ: アカマツ / ダークボール / ハイパーボール / ゼロの大空洞 / ボスの指令 / ワンダーパッチ
- 主な使用者: zoroark190
- 代表 episode:
  - Episode 82720918 P0: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82721427 P1: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82721949 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722610 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82722610.json`)
  - Episode 82723113 P1: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82723113.json`)

### メガルカリオex闘

- 出現数: 53
- 勝敗: 21勝 32敗
- 勝率: 39.6%
- Wilson下限: 27.6%
- 主軸ポケモン: メガルカリオex / リオル / ソルロック / ルナトーン / マクノシタ
- 主要トレーナーズ: パワープロテイン / ファイトゴング / リーリエの決心 / ダークボール / ポケパッド / ゼイユ
- 主な使用者: Akira-Ninth, easonyanyan, c-number, Rajan Nagarajan
- 代表 episode:
  - Episode 82720923 P0: need a job (we're unemployed) reward=-1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720987 P0: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82720987.json`)
  - Episode 82724072 P1: c-number reward=1 (`downloads/episodes/2026-06-30/82724072.json`)
  - Episode 82727561 P1: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82727561.json`)
  - Episode 82728057 P0: Akira-Ninth reward=1 (`downloads/episodes/2026-06-30/82728057.json`)

### ホップのボクレー / ホップのオーロット

- 出現数: 21
- 勝敗: 9勝 12敗
- 勝率: 42.9%
- Wilson下限: 24.5%
- 主軸ポケモン: ホップのボクレー / ホップのオーロット / ホップのウッウ / ホップのカビゴン / ノコッチ
- 主要トレーナーズ: ホップのこだわりハチマキ / リーリエの決心 / ハロンタウン / ポケギア3.0 / ホップのバッグ / ロケット団のラムダ
- 主な使用者: Yushin Ito, Shunji Minode, EF, RtoABC
- 代表 episode:
  - Episode 82724737 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82724737.json`)
  - Episode 82739714 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82739714.json`)
  - Episode 82742077 P0: RtoABC reward=-1 (`downloads/episodes/2026-06-30/82742077.json`)
  - Episode 82762120 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82762120.json`)
  - Episode 82765669 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82765669.json`)

### ノコッチ / ホップのボクレー

- 出現数: 12
- 勝敗: 5勝 7敗
- 勝率: 41.7%
- Wilson下限: 19.3%
- 主軸ポケモン: ノコッチ / ホップのボクレー / ノココッチ / ホップのカビゴン / ホップのオーロット
- 主要トレーナーズ: なかよしポフィン / ポケギア3.0 / ポケパッド / ホップのこだわりハチマキ / リーリエの決心 / ハロンタウン
- 主な使用者: Ryosei Kojima, matsurih, Shirag Maharaj, CYLik
- 代表 episode:
  - Episode 82728060 P0: Ryosei Kojima reward=-1 (`downloads/episodes/2026-06-30/82728060.json`)
  - Episode 82728706 P0: Shirag Maharaj reward=1 (`downloads/episodes/2026-06-30/82728706.json`)
  - Episode 82732237 P0: Ryosei Kojima reward=1 (`downloads/episodes/2026-06-30/82732237.json`)
  - Episode 82738538 P1: CYLik reward=-1 (`downloads/episodes/2026-06-30/82738538.json`)
  - Episode 82740266 P1: matsurih reward=-1 (`downloads/episodes/2026-06-30/82740266.json`)

### ロケット団のタマンチュラ / ロケット団のワナイダー

- 出現数: 9
- 勝敗: 4勝 5敗
- 勝率: 44.4%
- Wilson下限: 18.9%
- 主軸ポケモン: ロケット団のタマンチュラ / ロケット団のワナイダー / ロケット団のミュウツーex / ロケット団のミミッキュ / ロケット団のフリーザー
- 主要トレーナーズ: ポケパッド / ロケット団のレシーバー / ロケット団のアテナ / ロケット団のランス / ロケット団のアポロ / ロケット団のサカキ
- 主な使用者: kashiwashira
- 代表 episode:
  - Episode 82731841 P1: kashiwashira reward=-1 (`downloads/episodes/2026-06-30/82731841.json`)
  - Episode 82739035 P1: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82739035.json`)
  - Episode 82743841 P0: kashiwashira reward=-1 (`downloads/episodes/2026-06-30/82743841.json`)
  - Episode 82768128 P0: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82768128.json`)
  - Episode 82817120 P1: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82817120.json`)

### マリィのベロバー / マリィのオーロンゲex

- 出現数: 17
- 勝敗: 6勝 11敗
- 勝率: 35.3%
- Wilson下限: 17.3%
- 主軸ポケモン: マリィのベロバー / マリィのオーロンゲex / ノコッチ / ノココッチ / マシマシラ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / リーリエの決心 / ヒカリ / スパイクタウンジム
- 主な使用者: The Debauchery Tea Party
- 代表 episode:
  - Episode 82733556 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82733556.json`)
  - Episode 82745145 P0: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82745145.json`)
  - Episode 82751511 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82751511.json`)
  - Episode 82753775 P0: The Debauchery Tea Party reward=1 (`downloads/episodes/2026-06-30/82753775.json`)
  - Episode 82755554 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82755554.json`)

### メガユキメノコex水

- 出現数: 7
- 勝敗: 3勝 4敗
- 勝率: 42.9%
- Wilson下限: 15.8%
- 主軸ポケモン: メガユキメノコex / ユキワラシ / ノコッチ / ノココッチ / スピンロトム
- 主要トレーナーズ: なかよしポフィン / ポケパッド / クラッシュハンマー / リーリエの決心 / ミツルの思いやり / ポケギア3.0
- 主な使用者: Gotem Penguin
- 代表 episode:
  - Episode 82720949 P1: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82720949.json`)
  - Episode 82745316 P1: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82745316.json`)
  - Episode 82760920 P0: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82760920.json`)
  - Episode 82781390 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82781390.json`)
  - Episode 82801095 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82801095.json`)

### カジッチュ / カミッチュ

- 出現数: 5
- 勝敗: 1勝 4敗
- 勝率: 20.0%
- Wilson下限: 3.6%
- 主軸ポケモン: カジッチュ / カミッチュ / サルノリ / バチンキー / トサキント
- 主要トレーナーズ: なかよしポフィン / むしとりセット / ポケパッド / お祭り会場 / リーリエの決心 / からておうの稽古
- 主な使用者: aca-ta
- 代表 episode:
  - Episode 82721529 P1: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82721529.json`)
  - Episode 82743844 P0: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82743844.json`)
  - Episode 82757927 P0: aca-ta reward=1 (`downloads/episodes/2026-06-30/82757927.json`)
  - Episode 82758355 P1: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82758355.json`)
  - Episode 82776967 P0: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82776967.json`)

## exact 60枚リスト候補

### Exact 1: クマシュン / オーガポン いしずえのめんex

- 出現数: 9
- 勝敗: 8勝 1敗
- 勝率: 88.9%
- Wilson下限: 56.5%
- 主軸ポケモン: クマシュン / オーガポン いしずえのめんex / ロケット団のフリーザー
- 主要トレーナーズ: クラッシュハンマー / ポケギア3.0 / リーリエの決心 / ボスの指令 / 改造ハンマー / ロケット団のラムダ
- 主な使用者: Michael Krager
- 代表 episode:
  - Episode 82727566 P0: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82727566.json`)
  - Episode 82741433 P0: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82741433.json`)
  - Episode 82742734 P1: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82742734.json`)
  - Episode 82761010 P1: Michael Krager reward=1 (`downloads/episodes/2026-06-30/82761010.json`)
  - Episode 82765489 P1: Michael Krager reward=-1 (`downloads/episodes/2026-06-30/82765489.json`)

### Exact 2: ブリジュラスex鋼

- 出現数: 47
- 勝敗: 33勝 14敗
- 勝率: 70.2%
- Wilson下限: 56.0%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: ポケパッド / ハイパーボール / ポケギア3.0 / 夜のタンカ / 探検家の先導 / リーリエの決心
- 主な使用者: Moegi
- 代表 episode:
  - Episode 82725781 P0: Moegi reward=1 (`downloads/episodes/2026-06-30/82725781.json`)
  - Episode 82726924 P1: Moegi reward=1 (`downloads/episodes/2026-06-30/82726924.json`)
  - Episode 82727566 P1: Moegi reward=-1 (`downloads/episodes/2026-06-30/82727566.json`)
  - Episode 82728063 P1: Moegi reward=1 (`downloads/episodes/2026-06-30/82728063.json`)
  - Episode 82728716 P0: Moegi reward=-1 (`downloads/episodes/2026-06-30/82728716.json`)

### Exact 3: フーディン超

- 出現数: 12
- 勝敗: 10勝 2敗
- 勝率: 83.3%
- Wilson下限: 55.2%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ヒカリ / トウコ / ふしぎなアメ / 改造ハンマー
- 主な使用者: THIRD PTCG Club
- 代表 episode:
  - Episode 82740774 P1: THIRD PTCG Club reward=-1 (`downloads/episodes/2026-06-30/82740774.json`)
  - Episode 82742056 P0: THIRD PTCG Club reward=-1 (`downloads/episodes/2026-06-30/82742056.json`)
  - Episode 82762102 P0: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82762102.json`)
  - Episode 82767252 P1: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82767252.json`)
  - Episode 82775952 P0: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82775952.json`)

### Exact 4: ブリジュラスex鋼

- 出現数: 38
- 勝敗: 25勝 13敗
- 勝率: 65.8%
- Wilson下限: 49.9%
- 主軸ポケモン: ブリジュラスex / エースバーン / ジュラルドン / ジーランス
- 主要トレーナーズ: 探検家の先導 / ジャンボアイス / リーリエの決心 / 夜のタンカ / ポケパッド / ポケギア3.0
- 主な使用者: Myckel Uribe
- 代表 episode:
  - Episode 82727581 P1: Myckel Uribe reward=1 (`downloads/episodes/2026-06-30/82727581.json`)
  - Episode 82728079 P1: Myckel Uribe reward=-1 (`downloads/episodes/2026-06-30/82728079.json`)
  - Episode 82728731 P0: Myckel Uribe reward=-1 (`downloads/episodes/2026-06-30/82728731.json`)
  - Episode 82730035 P0: Myckel Uribe reward=1 (`downloads/episodes/2026-06-30/82730035.json`)
  - Episode 82730517 P1: Myckel Uribe reward=1 (`downloads/episodes/2026-06-30/82730517.json`)

### Exact 5: フーディン超

- 出現数: 10
- 勝敗: 8勝 2敗
- 勝率: 80.0%
- Wilson下限: 49.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / バトルコロシアム / ヒカリ
- 主な使用者: TTT Is All You Need
- 代表 episode:
  - Episode 82742077 P1: TTT Is All You Need reward=1 (`downloads/episodes/2026-06-30/82742077.json`)
  - Episode 82744801 P1: TTT Is All You Need reward=-1 (`downloads/episodes/2026-06-30/82744801.json`)
  - Episode 82769860 P1: TTT Is All You Need reward=1 (`downloads/episodes/2026-06-30/82769860.json`)
  - Episode 82771486 P0: TTT Is All You Need reward=1 (`downloads/episodes/2026-06-30/82771486.json`)
  - Episode 82781917 P1: TTT Is All You Need reward=1 (`downloads/episodes/2026-06-30/82781917.json`)

### Exact 6: フーディン超

- 出現数: 65
- 勝敗: 39勝 26敗
- 勝率: 60.0%
- Wilson下限: 47.9%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / トウコ / ヒカリ / ふしぎなアメ / ボスの指令
- 主な使用者: 【ＡＩと共に、ＡＩと戦う】tubotu
- 代表 episode:
  - Episode 82741435 P1: 【ＡＩと共に、ＡＩと戦う】tubotu reward=-1 (`downloads/episodes/2026-06-30/82741435.json`)
  - Episode 82759214 P1: 【ＡＩと共に、ＡＩと戦う】tubotu reward=1 (`downloads/episodes/2026-06-30/82759214.json`)
  - Episode 82759907 P1: 【ＡＩと共に、ＡＩと戦う】tubotu reward=-1 (`downloads/episodes/2026-06-30/82759907.json`)
  - Episode 82760357 P1: 【ＡＩと共に、ＡＩと戦う】tubotu reward=-1 (`downloads/episodes/2026-06-30/82760357.json`)
  - Episode 82761369 P0: 【ＡＩと共に、ＡＩと戦う】tubotu reward=1 (`downloads/episodes/2026-06-30/82761369.json`)

### Exact 7: シロナのフカマル / シロナのガバイト

- 出現数: 53
- 勝敗: 32勝 21敗
- 勝率: 60.4%
- Wilson下限: 46.9%
- 主軸ポケモン: シロナのフカマル / シロナのガバイト / シロナのロゼリア / シロナのガブリアスex / シロナのロズレイド
- 主要トレーナーズ: ボスの指令 / リーリエの決心 / ポケパッド / なかよしポフィン / シロナのパワーウエイト / ファイトゴング
- 主な使用者: Dongwook Kim
- 代表 episode:
  - Episode 82744158 P0: Dongwook Kim reward=1 (`downloads/episodes/2026-06-30/82744158.json`)
  - Episode 82744658 P0: Dongwook Kim reward=1 (`downloads/episodes/2026-06-30/82744658.json`)
  - Episode 82745145 P1: Dongwook Kim reward=1 (`downloads/episodes/2026-06-30/82745145.json`)
  - Episode 82745642 P1: Dongwook Kim reward=1 (`downloads/episodes/2026-06-30/82745642.json`)
  - Episode 82746291 P0: Dongwook Kim reward=-1 (`downloads/episodes/2026-06-30/82746291.json`)

### Exact 8: ブリジュラスex鋼

- 出現数: 17
- 勝敗: 12勝 5敗
- 勝率: 70.6%
- Wilson下限: 46.9%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ポケギア3.0 / ジャンボアイス / ポケパッド / 探検家の先導 / リーリエの決心
- 主な使用者: mikelou1
- 代表 episode:
  - Episode 82738563 P0: mikelou1 reward=1 (`downloads/episodes/2026-06-30/82738563.json`)
  - Episode 82739697 P0: mikelou1 reward=1 (`downloads/episodes/2026-06-30/82739697.json`)
  - Episode 82740196 P1: mikelou1 reward=1 (`downloads/episodes/2026-06-30/82740196.json`)
  - Episode 82740697 P0: mikelou1 reward=1 (`downloads/episodes/2026-06-30/82740697.json`)
  - Episode 82741350 P1: mikelou1 reward=-1 (`downloads/episodes/2026-06-30/82741350.json`)

### Exact 9: タマザラシ / トドゼルガ

- 出現数: 12
- 勝敗: 9勝 3敗
- 勝率: 75.0%
- Wilson下限: 46.8%
- 主軸ポケモン: タマザラシ / トドゼルガ / トドグラー / スボミー / ノコッチ
- 主要トレーナーズ: なかよしポフィン / ふしぎなアメ / リーリエの決心 / ヒカリ / 改造ハンマー / せいなるはい
- 主な使用者: Kimiaki Nakamura
- 代表 episode:
  - Episode 82738580 P1: Kimiaki Nakamura reward=-1 (`downloads/episodes/2026-06-30/82738580.json`)
  - Episode 82740194 P0: Kimiaki Nakamura reward=-1 (`downloads/episodes/2026-06-30/82740194.json`)
  - Episode 82759907 P0: Kimiaki Nakamura reward=1 (`downloads/episodes/2026-06-30/82759907.json`)
  - Episode 82766077 P1: Kimiaki Nakamura reward=1 (`downloads/episodes/2026-06-30/82766077.json`)
  - Episode 82767607 P1: Kimiaki Nakamura reward=1 (`downloads/episodes/2026-06-30/82767607.json`)

### Exact 10: フーディン超

- 出現数: 12
- 勝敗: 9勝 3敗
- 勝率: 75.0%
- Wilson下限: 46.8%
- 主軸ポケモン: フーディン / ユンゲラー / ケーシィ / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / トウコ / 改造ハンマー / ヒカリ
- 主な使用者: みずあめ
- 代表 episode:
  - Episode 82722610 P1: みずあめ reward=1 (`downloads/episodes/2026-06-30/82722610.json`)
  - Episode 82745309 P1: みずあめ reward=-1 (`downloads/episodes/2026-06-30/82745309.json`)
  - Episode 82758297 P1: みずあめ reward=1 (`downloads/episodes/2026-06-30/82758297.json`)
  - Episode 82765632 P0: みずあめ reward=1 (`downloads/episodes/2026-06-30/82765632.json`)
  - Episode 82769166 P0: みずあめ reward=1 (`downloads/episodes/2026-06-30/82769166.json`)

### Exact 11: キュワワー / ヒトモシ

- 出現数: 9
- 勝敗: 7勝 2敗
- 勝率: 77.8%
- Wilson下限: 45.3%
- 主軸ポケモン: キュワワー / ヒトモシ / シャンデラ / ランプラー / シェイミ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / トウコ / クセロシキのたくらみ / ボスの指令
- 主な使用者: Dick Jessen William
- 代表 episode:
  - Episode 82728079 P0: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82728079.json`)
  - Episode 82742669 P1: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82742669.json`)
  - Episode 82765677 P0: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82765677.json`)
  - Episode 82774487 P0: Dick Jessen William reward=-1 (`downloads/episodes/2026-06-30/82774487.json`)
  - Episode 82789957 P1: Dick Jessen William reward=1 (`downloads/episodes/2026-06-30/82789957.json`)

### Exact 12: マリィのベロバー / マシマシラ

- 出現数: 25
- 勝敗: 16勝 9敗
- 勝率: 64.0%
- Wilson下限: 44.5%
- 主軸ポケモン: マリィのベロバー / マシマシラ / マリィのギモー / マリィのオーロンゲex / ノコッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / ヒカリ / スパイクタウンジム / ふしぎなアメ
- 主な使用者: kazuki0123
- 代表 episode:
  - Episode 82723127 P1: kazuki0123 reward=1 (`downloads/episodes/2026-06-30/82723127.json`)
  - Episode 82745330 P0: kazuki0123 reward=1 (`downloads/episodes/2026-06-30/82745330.json`)
  - Episode 82765669 P1: kazuki0123 reward=1 (`downloads/episodes/2026-06-30/82765669.json`)
  - Episode 82783144 P0: kazuki0123 reward=1 (`downloads/episodes/2026-06-30/82783144.json`)
  - Episode 82793815 P1: kazuki0123 reward=-1 (`downloads/episodes/2026-06-30/82793815.json`)

### Exact 13: ブリジュラスex鋼

- 出現数: 64
- 勝敗: 36勝 28敗
- 勝率: 56.2%
- Wilson下限: 44.1%
- 主軸ポケモン: ブリジュラスex / ジュラルドン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケパッド / ゼイユ / リーリエの決心 / ジャッジマン
- 主な使用者: MtN, ShumpeiNomura, ochisamu, Daniel Casellas
- 代表 episode:
  - Episode 82720905 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82721442 P0: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82721442.json`)
  - Episode 82721958 P0: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82721958.json`)
  - Episode 82722605 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82722605.json`)
  - Episode 82723114 P0: ShumpeiNomura reward=-1 (`downloads/episodes/2026-06-30/82723114.json`)

### Exact 14: メガルカリオex闘

- 出現数: 3
- 勝敗: 3勝 0敗
- 勝率: 100.0%
- Wilson下限: 43.8%
- 主軸ポケモン: ソルロック / リオル / メガルカリオex / マクノシタ / ハリテヤマ
- 主要トレーナーズ: ダークボール / パワープロテイン / ファイトゴング / ポケパッド / リーリエの決心 / クセロシキのたくらみ
- 主な使用者: Mudkip's Machines
- 代表 episode:
  - Episode 82742073 P0: Mudkip's Machines reward=1 (`downloads/episodes/2026-06-30/82742073.json`)
  - Episode 82801097 P0: Mudkip's Machines reward=1 (`downloads/episodes/2026-06-30/82801097.json`)
  - Episode 82818952 P1: Mudkip's Machines reward=1 (`downloads/episodes/2026-06-30/82818952.json`)

### Exact 15: イダイナキバ / イシズマイ

- 出現数: 66
- 勝敗: 36勝 30敗
- 勝率: 54.5%
- Wilson下限: 42.6%
- 主軸ポケモン: イダイナキバ / イシズマイ / イワパレス / テラキオン
- 主要トレーナーズ: ファイトゴング / ポケパッド / なかよしポフィン / ポケギア3.0 / ポケモンいれかえ / クセロシキのたくらみ
- 主な使用者: ykuroka, Super Mippo
- 代表 episode:
  - Episode 82764990 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82764990.json`)
  - Episode 82765050 P0: Super Mippo reward=-1 (`downloads/episodes/2026-06-30/82765050.json`)
  - Episode 82765489 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82765489.json`)
  - Episode 82765979 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82765979.json`)
  - Episode 82766469 P0: ykuroka reward=1 (`downloads/episodes/2026-06-30/82766469.json`)

### Exact 16: フーディン超

- 出現数: 17
- 勝敗: 11勝 6敗
- 勝率: 64.7%
- Wilson下限: 41.3%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ふしぎなアメ / ポケパッド / ヒカリ / トウコ / 改造ハンマー
- 主な使用者: Ajishio
- 代表 episode:
  - Episode 82720987 P1: Ajishio reward=1 (`downloads/episodes/2026-06-30/82720987.json`)
  - Episode 82732929 P0: Ajishio reward=1 (`downloads/episodes/2026-06-30/82732929.json`)
  - Episode 82737138 P0: Ajishio reward=-1 (`downloads/episodes/2026-06-30/82737138.json`)
  - Episode 82744765 P1: Ajishio reward=1 (`downloads/episodes/2026-06-30/82744765.json`)
  - Episode 82756114 P1: Ajishio reward=-1 (`downloads/episodes/2026-06-30/82756114.json`)

### Exact 17: フーディン超

- 出現数: 154
- 勝敗: 75勝 79敗
- 勝率: 48.7%
- Wilson下限: 40.9%
- 主軸ポケモン: ノコッチ / ケーシィ / ユンゲラー / フーディン / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / トウコ / ヒカリ
- 主な使用者: 樹神, Janglish, aidy, kami
- 代表 episode:
  - Episode 82720920 P1: aidy reward=-1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720922 P1: aidy reward=1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82721496 P1: kami reward=-1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721963 P1: pompom555 reward=1 (`downloads/episodes/2026-06-30/82721963.json`)
  - Episode 82723946 P0: kami reward=-1 (`downloads/episodes/2026-06-30/82723946.json`)

### Exact 18: フーディン超

- 出現数: 8
- 勝敗: 6勝 2敗
- 勝率: 75.0%
- Wilson下限: 40.9%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / トウコ / なかよしポフィン / ポケパッド / ふしぎなアメ / 改造ハンマー
- 主な使用者: capbloo
- 代表 episode:
  - Episode 82742073 P1: capbloo reward=-1 (`downloads/episodes/2026-06-30/82742073.json`)
  - Episode 82743829 P0: capbloo reward=1 (`downloads/episodes/2026-06-30/82743829.json`)
  - Episode 82750962 P1: capbloo reward=1 (`downloads/episodes/2026-06-30/82750962.json`)
  - Episode 82766657 P1: capbloo reward=1 (`downloads/episodes/2026-06-30/82766657.json`)
  - Episode 82772121 P1: capbloo reward=-1 (`downloads/episodes/2026-06-30/82772121.json`)

### Exact 19: ブリジュラスex鋼

- 出現数: 425
- 勝敗: 191勝 234敗
- 勝率: 44.9%
- Wilson下限: 40.3%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / ボスの指令
- 主な使用者: hikarimaru, iwashi, askamijo, Peng Wang
- 代表 episode:
  - Episode 82720923 P1: Furkan Pirinc reward=1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720940 P0: david valor reward=1 (`downloads/episodes/2026-06-30/82720940.json`)
  - Episode 82720948 P1: DaJimmy reward=-1 (`downloads/episodes/2026-06-30/82720948.json`)
  - Episode 82720949 P0: nsytsqdtn reward=-1 (`downloads/episodes/2026-06-30/82720949.json`)
  - Episode 82721019 P1: taka0808 reward=1 (`downloads/episodes/2026-06-30/82721019.json`)

### Exact 20: マリィのベロバー / マシマシラ

- 出現数: 16
- 勝敗: 10勝 6敗
- 勝率: 62.5%
- Wilson下限: 38.6%
- 主軸ポケモン: マリィのベロバー / マシマシラ / マリィのオーロンゲex / マリィのギモー / ユキメノコ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / ロケット団のラムダ / スパイクタウンジム / ふしぎなアメ
- 主な使用者: tonakaiiii
- 代表 episode:
  - Episode 82820158 P0: tonakaiiii reward=-1 (`downloads/episodes/2026-06-30/82820158.json`)
  - Episode 82820654 P1: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82820654.json`)
  - Episode 82821140 P0: tonakaiiii reward=-1 (`downloads/episodes/2026-06-30/82821140.json`)
  - Episode 82822423 P0: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82822423.json`)
  - Episode 82822910 P1: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82822910.json`)

### Exact 21: ブリジュラスex鋼

- 出現数: 53
- 勝敗: 27勝 26敗
- 勝率: 50.9%
- Wilson下限: 37.9%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: ハイパーボール / ポケギア3.0 / ジャンボアイス / ポケパッド / 探検家の先導 / リーリエの決心
- 主な使用者: anngle, Blacklions., f.a.nina, lingyu07
- 代表 episode:
  - Episode 82722674 P0: Blacklions. reward=1 (`downloads/episodes/2026-06-30/82722674.json`)
  - Episode 82724072 P0: f.a.nina reward=-1 (`downloads/episodes/2026-06-30/82724072.json`)
  - Episode 82737639 P0: Pavel Pavlov reward=-1 (`downloads/episodes/2026-06-30/82737639.json`)
  - Episode 82741351 P0: f.a.nina reward=-1 (`downloads/episodes/2026-06-30/82741351.json`)
  - Episode 82743320 P0: Jiang reward=-1 (`downloads/episodes/2026-06-30/82743320.json`)

### Exact 22: ドラパルト系

- 出現数: 101
- 勝敗: 46勝 55敗
- 勝率: 45.5%
- Wilson下限: 36.2%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / キチキギスex
- 主要トレーナーズ: なかよしポフィン / クラッシュハンマー / ハイパーボール / アカマツ / リーリエの決心 / ポケパッド
- 主な使用者: shibushun, Yasuo 0/10/0, milix, TOMOYA Tsunakawa
- 代表 episode:
  - Episode 82721496 P0: shibushun reward=1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721949 P1: milix reward=1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722619 P1: orikage reward=1 (`downloads/episodes/2026-06-30/82722619.json`)
  - Episode 82724781 P0: Yasuo 0/10/0 reward=-1 (`downloads/episodes/2026-06-30/82724781.json`)
  - Episode 82730509 P1: TOMOYA Tsunakawa reward=1 (`downloads/episodes/2026-06-30/82730509.json`)

### Exact 23: キュワワー / シャンデラ

- 出現数: 7
- 勝敗: 5勝 2敗
- 勝率: 71.4%
- Wilson下限: 35.9%
- 主軸ポケモン: キュワワー / シャンデラ / ヒトモシ / ランプラー / シェイミ
- 主要トレーナーズ: クラッシュハンマー / なかよしポフィン / ポケパッド / リーリエの決心 / クセロシキのたくらみ / トウコ
- 主な使用者: yamy893
- 代表 episode:
  - Episode 82742725 P1: yamy893 reward=-1 (`downloads/episodes/2026-06-30/82742725.json`)
  - Episode 82754944 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82754944.json`)
  - Episode 82758787 P1: yamy893 reward=-1 (`downloads/episodes/2026-06-30/82758787.json`)
  - Episode 82761476 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82761476.json`)
  - Episode 82780440 P1: yamy893 reward=1 (`downloads/episodes/2026-06-30/82780440.json`)

### Exact 24: フーディン超

- 出現数: 7
- 勝敗: 5勝 2敗
- 勝率: 71.4%
- Wilson下限: 35.9%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / トウコ / ヒカリ / ボスの指令
- 主な使用者: Legend Brothers
- 代表 episode:
  - Episode 82742721 P0: Legend Brothers reward=1 (`downloads/episodes/2026-06-30/82742721.json`)
  - Episode 82766162 P1: Legend Brothers reward=1 (`downloads/episodes/2026-06-30/82766162.json`)
  - Episode 82781418 P0: Legend Brothers reward=-1 (`downloads/episodes/2026-06-30/82781418.json`)
  - Episode 82798241 P1: Legend Brothers reward=1 (`downloads/episodes/2026-06-30/82798241.json`)
  - Episode 82817160 P0: Legend Brothers reward=1 (`downloads/episodes/2026-06-30/82817160.json`)

### Exact 25: フーディン超

- 出現数: 7
- 勝敗: 5勝 2敗
- 勝率: 71.4%
- Wilson下限: 35.9%
- 主軸ポケモン: ノココッチ / ノコッチ / ケーシィ / ユンゲラー / フーディン
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / ヒカリ / トウコ
- 主な使用者: UBI=ISHI
- 代表 episode:
  - Episode 82728716 P1: UBI=ISHI reward=1 (`downloads/episodes/2026-06-30/82728716.json`)
  - Episode 82730035 P1: UBI=ISHI reward=-1 (`downloads/episodes/2026-06-30/82730035.json`)
  - Episode 82763233 P1: UBI=ISHI reward=1 (`downloads/episodes/2026-06-30/82763233.json`)
  - Episode 82771450 P0: UBI=ISHI reward=1 (`downloads/episodes/2026-06-30/82771450.json`)
  - Episode 82804355 P0: UBI=ISHI reward=1 (`downloads/episodes/2026-06-30/82804355.json`)

### Exact 26: メガルカリオex闘

- 出現数: 7
- 勝敗: 5勝 2敗
- 勝率: 71.4%
- Wilson下限: 35.9%
- 主軸ポケモン: リオル / メガルカリオex / ルナトーン / ソルロック / マクノシタ
- 主要トレーナーズ: ダークボール / パワープロテイン / ファイトゴング / ポケパッド / リーリエの決心 / ジャッジマン
- 主な使用者: c-number
- 代表 episode:
  - Episode 82724072 P1: c-number reward=1 (`downloads/episodes/2026-06-30/82724072.json`)
  - Episode 82728847 P0: c-number reward=1 (`downloads/episodes/2026-06-30/82728847.json`)
  - Episode 82763146 P0: c-number reward=-1 (`downloads/episodes/2026-06-30/82763146.json`)
  - Episode 82783648 P1: c-number reward=-1 (`downloads/episodes/2026-06-30/82783648.json`)
  - Episode 82797558 P1: c-number reward=1 (`downloads/episodes/2026-06-30/82797558.json`)

### Exact 27: フーディン超

- 出現数: 9
- 勝敗: 6勝 3敗
- 勝率: 66.7%
- Wilson下限: 35.4%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ヒカリ / トウコ / 改造ハンマー / ボスの指令
- 主な使用者: THIRD PTCG Club
- 代表 episode:
  - Episode 82721478 P1: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82721478.json`)
  - Episode 82738607 P1: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82738607.json`)
  - Episode 82745330 P1: THIRD PTCG Club reward=-1 (`downloads/episodes/2026-06-30/82745330.json`)
  - Episode 82746479 P1: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82746479.json`)
  - Episode 82762059 P0: THIRD PTCG Club reward=1 (`downloads/episodes/2026-06-30/82762059.json`)

### Exact 28: ブリジュラスex鋼

- 出現数: 9
- 勝敗: 6勝 3敗
- 勝率: 66.7%
- Wilson下限: 35.4%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケギア3.0 / ポケパッド / 探検家の先導 / リーリエの決心
- 主な使用者: Xander
- 代表 episode:
  - Episode 82726912 P0: Xander reward=1 (`downloads/episodes/2026-06-30/82726912.json`)
  - Episode 82740740 P1: Xander reward=1 (`downloads/episodes/2026-06-30/82740740.json`)
  - Episode 82741368 P0: Xander reward=1 (`downloads/episodes/2026-06-30/82741368.json`)
  - Episode 82743285 P0: Xander reward=1 (`downloads/episodes/2026-06-30/82743285.json`)
  - Episode 82758682 P1: Xander reward=1 (`downloads/episodes/2026-06-30/82758682.json`)

### Exact 29: イイネイヌ / ソルロック

- 出現数: 28
- 勝敗: 14勝 14敗
- 勝率: 50.0%
- Wilson下限: 32.6%
- 主軸ポケモン: イイネイヌ / ソルロック / ルナトーン / カメテテ / ガメノデス
- 主要トレーナーズ: ファイトゴング / ポケパッド / リーリエの決心 / 夜のタンカ / ロケット団の監視塔 / ツールスクラッパー
- 主な使用者: monnosuke
- 代表 episode:
  - Episode 82778386 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82778386.json`)
  - Episode 82779034 P0: monnosuke reward=-1 (`downloads/episodes/2026-06-30/82779034.json`)
  - Episode 82779743 P1: monnosuke reward=-1 (`downloads/episodes/2026-06-30/82779743.json`)
  - Episode 82780323 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82780323.json`)
  - Episode 82780813 P1: monnosuke reward=1 (`downloads/episodes/2026-06-30/82780813.json`)

### Exact 30: メガスターミーex水

- 出現数: 12
- 勝敗: 7勝 5敗
- 勝率: 58.3%
- Wilson下限: 32.0%
- 主軸ポケモン: ヒトデマン / メガスターミーex / ヨマワル / サマヨール / ヨノワール
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ハイパーボール / ポケギア3.0 / トウコ / リーリエの決心
- 主な使用者: pokeka_ryo
- 代表 episode:
  - Episode 82721992 P0: pokeka_ryo reward=-1 (`downloads/episodes/2026-06-30/82721992.json`)
  - Episode 82734203 P1: pokeka_ryo reward=-1 (`downloads/episodes/2026-06-30/82734203.json`)
  - Episode 82737650 P1: pokeka_ryo reward=-1 (`downloads/episodes/2026-06-30/82737650.json`)
  - Episode 82739109 P1: pokeka_ryo reward=1 (`downloads/episodes/2026-06-30/82739109.json`)
  - Episode 82744816 P0: pokeka_ryo reward=1 (`downloads/episodes/2026-06-30/82744816.json`)

### Exact 31: ドラパルト系

- 出現数: 10
- 勝敗: 6勝 4敗
- 勝率: 60.0%
- Wilson下限: 31.3%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / キチキギスex
- 主要トレーナーズ: なかよしポフィン / ハイパーボール / ポケパッド / アカマツ / リーリエの決心 / クラッシュハンマー
- 主な使用者: nattomaki
- 代表 episode:
  - Episode 82722024 P0: nattomaki reward=-1 (`downloads/episodes/2026-06-30/82722024.json`)
  - Episode 82738009 P0: nattomaki reward=1 (`downloads/episodes/2026-06-30/82738009.json`)
  - Episode 82739804 P0: nattomaki reward=1 (`downloads/episodes/2026-06-30/82739804.json`)
  - Episode 82752001 P0: nattomaki reward=-1 (`downloads/episodes/2026-06-30/82752001.json`)
  - Episode 82769712 P0: nattomaki reward=1 (`downloads/episodes/2026-06-30/82769712.json`)

### Exact 32: マリィのベロバー / マシマシラ

- 出現数: 10
- 勝敗: 6勝 4敗
- 勝率: 60.0%
- Wilson下限: 31.3%
- 主軸ポケモン: マリィのベロバー / マシマシラ / マリィのギモー / マリィのオーロンゲex / ノコッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / リーリエの決心 / ヒカリ / スパイクタウンジム
- 主な使用者: puraza
- 代表 episode:
  - Episode 82734665 P0: puraza reward=1 (`downloads/episodes/2026-06-30/82734665.json`)
  - Episode 82742037 P0: puraza reward=-1 (`downloads/episodes/2026-06-30/82742037.json`)
  - Episode 82745284 P0: puraza reward=-1 (`downloads/episodes/2026-06-30/82745284.json`)
  - Episode 82746951 P1: puraza reward=1 (`downloads/episodes/2026-06-30/82746951.json`)
  - Episode 82760984 P1: puraza reward=1 (`downloads/episodes/2026-06-30/82760984.json`)

### Exact 33: メガスターミーex水

- 出現数: 59
- 勝敗: 25勝 34敗
- 勝率: 42.4%
- Wilson下限: 30.6%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex
- 主要トレーナーズ: なかよしポフィン / クラッシュハンマー / ポケギア3.0 / メガシグナル / セイジ / リーリエの決心
- 主な使用者: Yushin Ito, keidroid, ysakuragi, Pixegami
- 代表 episode:
  - Episode 82720905 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720920 P0: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82721340 P0: Banjo reward=-1 (`downloads/episodes/2026-06-30/82721340.json`)
  - Episode 82721442 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82721442.json`)
  - Episode 82721451 P1: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82721451.json`)

### Exact 34: キチキギス / イーブイ

- 出現数: 8
- 勝敗: 5勝 3敗
- 勝率: 62.5%
- Wilson下限: 30.6%
- 主軸ポケモン: キチキギス / イーブイ / マシマシラ / イイネイヌex / ニンフィア
- 主要トレーナーズ: アカマツ / コック / ルチアのアピール / エキサイトスタジアム / チェレン / ミアレガレット
- 主な使用者: Eli C. Lowry
- 代表 episode:
  - Episode 82737546 P1: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82737546.json`)
  - Episode 82738033 P0: Eli C. Lowry reward=-1 (`downloads/episodes/2026-06-30/82738033.json`)
  - Episode 82738538 P0: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82738538.json`)
  - Episode 82739035 P0: Eli C. Lowry reward=-1 (`downloads/episodes/2026-06-30/82739035.json`)
  - Episode 82739682 P1: Eli C. Lowry reward=1 (`downloads/episodes/2026-06-30/82739682.json`)

### Exact 35: マリィのベロバー / マシマシラ

- 出現数: 8
- 勝敗: 5勝 3敗
- 勝率: 62.5%
- Wilson下限: 30.6%
- 主軸ポケモン: マリィのベロバー / マシマシラ / マリィのオーロンゲex / マリィのギモー / ユキメノコ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / リーリエの決心 / ロケット団のラムダ / スパイクタウンジム / ふしぎなアメ
- 主な使用者: tonakaiiii
- 代表 episode:
  - Episode 82721427 P0: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82722612 P0: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82722612.json`)
  - Episode 82744836 P1: tonakaiiii reward=-1 (`downloads/episodes/2026-06-30/82744836.json`)
  - Episode 82757171 P1: tonakaiiii reward=1 (`downloads/episodes/2026-06-30/82757171.json`)
  - Episode 82775952 P1: tonakaiiii reward=-1 (`downloads/episodes/2026-06-30/82775952.json`)

### Exact 36: フーディン超

- 出現数: 4
- 勝敗: 3勝 1敗
- 勝率: 75.0%
- Wilson下限: 30.1%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ふしぎなアメ / 改造ハンマー / ヒカリ / トウコ
- 主な使用者: iwata hiroki
- 代表 episode:
  - Episode 82762008 P1: iwata hiroki reward=-1 (`downloads/episodes/2026-06-30/82762008.json`)
  - Episode 82811507 P0: iwata hiroki reward=1 (`downloads/episodes/2026-06-30/82811507.json`)
  - Episode 82822490 P1: iwata hiroki reward=1 (`downloads/episodes/2026-06-30/82822490.json`)
  - Episode 82827933 P0: iwata hiroki reward=1 (`downloads/episodes/2026-06-30/82827933.json`)

### Exact 37: フーディン超

- 出現数: 6
- 勝敗: 4勝 2敗
- 勝率: 66.7%
- Wilson下限: 30.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ヒカリ / トウコ / バトルコロシアム / ふしぎなアメ
- 主な使用者: llkarill
- 代表 episode:
  - Episode 82725245 P0: llkarill reward=1 (`downloads/episodes/2026-06-30/82725245.json`)
  - Episode 82728731 P1: llkarill reward=1 (`downloads/episodes/2026-06-30/82728731.json`)
  - Episode 82780427 P1: llkarill reward=1 (`downloads/episodes/2026-06-30/82780427.json`)
  - Episode 82801093 P0: llkarill reward=1 (`downloads/episodes/2026-06-30/82801093.json`)
  - Episode 82814287 P0: llkarill reward=-1 (`downloads/episodes/2026-06-30/82814287.json`)

### Exact 38: フーディン超

- 出現数: 23
- 勝敗: 11勝 12敗
- 勝率: 47.8%
- Wilson下限: 29.2%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / トウコ / ヒカリ
- 主な使用者: Libra
- 代表 episode:
  - Episode 82814902 P0: Libra reward=1 (`downloads/episodes/2026-06-30/82814902.json`)
  - Episode 82815390 P1: Libra reward=1 (`downloads/episodes/2026-06-30/82815390.json`)
  - Episode 82815884 P0: Libra reward=1 (`downloads/episodes/2026-06-30/82815884.json`)
  - Episode 82816373 P1: Libra reward=1 (`downloads/episodes/2026-06-30/82816373.json`)
  - Episode 82817012 P1: Libra reward=1 (`downloads/episodes/2026-06-30/82817012.json`)

### Exact 39: メガガルーラex多色

- 出現数: 18
- 勝敗: 9勝 9敗
- 勝率: 50.0%
- Wilson下限: 29.0%
- 主軸ポケモン: メガガルーラex / ニャースex / リーリエのピッピex / ラティアスex / キチキギスex
- 主要トレーナーズ: アカマツ / ダークボール / ハイパーボール / ゼロの大空洞 / ボスの指令 / ワンダーパッチ
- 主な使用者: zoroark190
- 代表 episode:
  - Episode 82720918 P0: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82721427 P1: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82721949 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722610 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82722610.json`)
  - Episode 82723113 P1: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82723113.json`)

### Exact 40: フーディン超

- 出現数: 11
- 勝敗: 6勝 5敗
- 勝率: 54.5%
- Wilson下限: 28.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / なかよしポフィン / ポケパッド / バトルコロシアム / トウコ / ボスの指令
- 主な使用者: Team Rocket
- 代表 episode:
  - Episode 82737144 P1: Team Rocket reward=1 (`downloads/episodes/2026-06-30/82737144.json`)
  - Episode 82760984 P0: Team Rocket reward=-1 (`downloads/episodes/2026-06-30/82760984.json`)
  - Episode 82762013 P1: Team Rocket reward=-1 (`downloads/episodes/2026-06-30/82762013.json`)
  - Episode 82771553 P1: Team Rocket reward=-1 (`downloads/episodes/2026-06-30/82771553.json`)
  - Episode 82791115 P0: Team Rocket reward=-1 (`downloads/episodes/2026-06-30/82791115.json`)

### Exact 41: フーディン超

- 出現数: 16
- 勝敗: 8勝 8敗
- 勝率: 50.0%
- Wilson下限: 28.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ヒカリ / トウコ / 夜の鉱山 / ふしぎなアメ
- 主な使用者: チームロスギラ
- 代表 episode:
  - Episode 82737593 P1: チームロスギラ reward=-1 (`downloads/episodes/2026-06-30/82737593.json`)
  - Episode 82738033 P1: チームロスギラ reward=1 (`downloads/episodes/2026-06-30/82738033.json`)
  - Episode 82739745 P1: チームロスギラ reward=-1 (`downloads/episodes/2026-06-30/82739745.json`)
  - Episode 82740210 P0: チームロスギラ reward=1 (`downloads/episodes/2026-06-30/82740210.json`)
  - Episode 82763233 P0: チームロスギラ reward=-1 (`downloads/episodes/2026-06-30/82763233.json`)

### Exact 42: メガスターミーex水

- 出現数: 14
- 勝敗: 7勝 7敗
- 勝率: 50.0%
- Wilson下限: 26.8%
- 主軸ポケモン: ヒトデマン / メガスターミーex
- 主要トレーナーズ: セイジ / リーリエの決心 / ミツルの思いやり / なかよしポフィン / ポケギア3.0 / クラッシュハンマー
- 主な使用者: barrybao123
- 代表 episode:
  - Episode 82726264 P1: barrybao123 reward=-1 (`downloads/episodes/2026-06-30/82726264.json`)
  - Episode 82729376 P1: barrybao123 reward=1 (`downloads/episodes/2026-06-30/82729376.json`)
  - Episode 82739170 P0: barrybao123 reward=1 (`downloads/episodes/2026-06-30/82739170.json`)
  - Episode 82740253 P0: barrybao123 reward=-1 (`downloads/episodes/2026-06-30/82740253.json`)
  - Episode 82742725 P0: barrybao123 reward=1 (`downloads/episodes/2026-06-30/82742725.json`)

### Exact 43: フーディン超

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: ケーシィ / フーディン / ノココッチ / ノコッチ / ユンゲラー
- 主要トレーナーズ: なかよしポフィン / ヒカリ / 改造ハンマー / ポケパッド / ふしぎなアメ / トウコ
- 主な使用者: Gotem Penguin
- 代表 episode:
  - Episode 82721451 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82721451.json`)
  - Episode 82743376 P1: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82743376.json`)
  - Episode 82746941 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82746941.json`)
  - Episode 82761406 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82761406.json`)
  - Episode 82779180 P0: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82779180.json`)

### Exact 44: フーディン超

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノココッチ / ノコッチ
- 主要トレーナーズ: ふしぎなアメ / なかよしポフィン / ポケパッド / トウコ / ヒカリ / 改造ハンマー
- 主な使用者: 水間
- 代表 episode:
  - Episode 82743322 P0: 水間 reward=1 (`downloads/episodes/2026-06-30/82743322.json`)
  - Episode 82758888 P0: 水間 reward=1 (`downloads/episodes/2026-06-30/82758888.json`)
  - Episode 82773353 P1: 水間 reward=1 (`downloads/episodes/2026-06-30/82773353.json`)
  - Episode 82773966 P0: 水間 reward=-1 (`downloads/episodes/2026-06-30/82773966.json`)
  - Episode 82797094 P1: 水間 reward=-1 (`downloads/episodes/2026-06-30/82797094.json`)

### Exact 45: フーディン超

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / トウコ / なかよしポフィン / ポケパッド / 改造ハンマー / ボスの指令
- 主な使用者: カドラバ Kadoraba
- 代表 episode:
  - Episode 82743860 P1: カドラバ Kadoraba reward=1 (`downloads/episodes/2026-06-30/82743860.json`)
  - Episode 82744836 P0: カドラバ Kadoraba reward=1 (`downloads/episodes/2026-06-30/82744836.json`)
  - Episode 82767112 P1: カドラバ Kadoraba reward=1 (`downloads/episodes/2026-06-30/82767112.json`)
  - Episode 82767252 P0: カドラバ Kadoraba reward=-1 (`downloads/episodes/2026-06-30/82767252.json`)
  - Episode 82772055 P0: カドラバ Kadoraba reward=1 (`downloads/episodes/2026-06-30/82772055.json`)

### Exact 46: ブリジュラスex鋼

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / 探検家の先導
- 主な使用者: らすはる
- 代表 episode:
  - Episode 82733580 P1: らすはる reward=1 (`downloads/episodes/2026-06-30/82733580.json`)
  - Episode 82754972 P1: らすはる reward=-1 (`downloads/episodes/2026-06-30/82754972.json`)
  - Episode 82765194 P1: らすはる reward=-1 (`downloads/episodes/2026-06-30/82765194.json`)
  - Episode 82768723 P1: らすはる reward=1 (`downloads/episodes/2026-06-30/82768723.json`)
  - Episode 82782450 P0: らすはる reward=-1 (`downloads/episodes/2026-06-30/82782450.json`)

### Exact 47: メガスターミーex水

- 出現数: 17
- 勝敗: 8勝 9敗
- 勝率: 47.1%
- Wilson下限: 26.2%
- 主軸ポケモン: ユキワラシ / ヒトデマン / メガユキメノコex / メガスターミーex
- 主要トレーナーズ: セイジ / リーリエの決心 / エネルギー転送 / なかよしポフィン / ミツルの思いやり / ポケギア3.0
- 主な使用者: tomatomato
- 代表 episode:
  - Episode 82724103 P1: tomatomato reward=-1 (`downloads/episodes/2026-06-30/82724103.json`)
  - Episode 82743811 P1: tomatomato reward=1 (`downloads/episodes/2026-06-30/82743811.json`)
  - Episode 82745315 P1: tomatomato reward=-1 (`downloads/episodes/2026-06-30/82745315.json`)
  - Episode 82764546 P0: tomatomato reward=-1 (`downloads/episodes/2026-06-30/82764546.json`)
  - Episode 82767785 P0: tomatomato reward=1 (`downloads/episodes/2026-06-30/82767785.json`)

### Exact 48: ブリジュラスex鋼

- 出現数: 20
- 勝敗: 9勝 11敗
- 勝率: 45.0%
- Wilson下限: 25.8%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / 夜のタンカ / 探検家の先導
- 主な使用者: Takaaki Matsuda, ChillR
- 代表 episode:
  - Episode 82720922 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82721455 P0: Takaaki Matsuda reward=1 (`downloads/episodes/2026-06-30/82721455.json`)
  - Episode 82721970 P1: Takaaki Matsuda reward=1 (`downloads/episodes/2026-06-30/82721970.json`)
  - Episode 82722639 P1: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82722639.json`)
  - Episode 82723127 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82723127.json`)

### Exact 49: メガスターミーex水

- 出現数: 7
- 勝敗: 4勝 3敗
- 勝率: 57.1%
- Wilson下限: 25.0%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex
- 主要トレーナーズ: ポケギア3.0 / なかよしポフィン / クラッシュハンマー / リーリエの決心 / ポケパッド / セイジ
- 主な使用者: Shun
- 代表 episode:
  - Episode 82745800 P0: Shun reward=1 (`downloads/episodes/2026-06-30/82745800.json`)
  - Episode 82770332 P0: Shun reward=-1 (`downloads/episodes/2026-06-30/82770332.json`)
  - Episode 82787180 P0: Shun reward=-1 (`downloads/episodes/2026-06-30/82787180.json`)
  - Episode 82792179 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82792179.json`)
  - Episode 82804421 P0: Shun reward=-1 (`downloads/episodes/2026-06-30/82804421.json`)

### Exact 50: フーディン超

- 出現数: 7
- 勝敗: 4勝 3敗
- 勝率: 57.1%
- Wilson下限: 25.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ヒカリ / トウコ / ふしぎなアメ / せいなるはい
- 主な使用者: kemurayama
- 代表 episode:
  - Episode 82728709 P0: kemurayama reward=-1 (`downloads/episodes/2026-06-30/82728709.json`)
  - Episode 82732842 P1: kemurayama reward=1 (`downloads/episodes/2026-06-30/82732842.json`)
  - Episode 82738054 P0: kemurayama reward=1 (`downloads/episodes/2026-06-30/82738054.json`)
  - Episode 82763724 P1: kemurayama reward=1 (`downloads/episodes/2026-06-30/82763724.json`)
  - Episode 82779034 P1: kemurayama reward=1 (`downloads/episodes/2026-06-30/82779034.json`)

### Exact 51: フーディン超

- 出現数: 7
- 勝敗: 4勝 3敗
- 勝率: 57.1%
- Wilson下限: 25.0%
- 主軸ポケモン: フーディン / ケーシィ / ユンゲラー / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / なかよしポフィン / ボスの指令 / 夜の鉱山 / ポケパッド / トウコ
- 主な使用者: Psychic Genesis
- 代表 episode:
  - Episode 82737555 P0: Psychic Genesis reward=1 (`downloads/episodes/2026-06-30/82737555.json`)
  - Episode 82740196 P0: Psychic Genesis reward=-1 (`downloads/episodes/2026-06-30/82740196.json`)
  - Episode 82763261 P0: Psychic Genesis reward=1 (`downloads/episodes/2026-06-30/82763261.json`)
  - Episode 82778467 P0: Psychic Genesis reward=1 (`downloads/episodes/2026-06-30/82778467.json`)
  - Episode 82783568 P0: Psychic Genesis reward=-1 (`downloads/episodes/2026-06-30/82783568.json`)

### Exact 52: タマザラシ / トドゼルガ

- 出現数: 10
- 勝敗: 5勝 5敗
- 勝率: 50.0%
- Wilson下限: 23.7%
- 主軸ポケモン: タマザラシ / トドゼルガ / ノコッチ / ノココッチ / スボミー
- 主要トレーナーズ: ふしぎなアメ / なかよしポフィン / クラッシュハンマー / ポケパッド / リーリエの決心 / 改造ハンマー
- 主な使用者: Hamu.py
- 代表 episode:
  - Episode 82724136 P0: Hamu.py reward=-1 (`downloads/episodes/2026-06-30/82724136.json`)
  - Episode 82762120 P0: Hamu.py reward=1 (`downloads/episodes/2026-06-30/82762120.json`)
  - Episode 82763110 P0: Hamu.py reward=1 (`downloads/episodes/2026-06-30/82763110.json`)
  - Episode 82763790 P0: Hamu.py reward=1 (`downloads/episodes/2026-06-30/82763790.json`)
  - Episode 82768106 P0: Hamu.py reward=-1 (`downloads/episodes/2026-06-30/82768106.json`)

### Exact 53: メガスターミーex水

- 出現数: 10
- 勝敗: 5勝 5敗
- 勝率: 50.0%
- Wilson下限: 23.7%
- 主軸ポケモン: メガスターミーex / ユキワラシ / ヒトデマン / メガユキメノコex
- 主要トレーナーズ: なかよしポフィン / ポケギア3.0 / ミツルの思いやり / リーリエの決心 / セイジ / トウコ
- 主な使用者: quwon_000
- 代表 episode:
  - Episode 82735732 P0: quwon_000 reward=1 (`downloads/episodes/2026-06-30/82735732.json`)
  - Episode 82736371 P1: quwon_000 reward=1 (`downloads/episodes/2026-06-30/82736371.json`)
  - Episode 82737022 P1: quwon_000 reward=-1 (`downloads/episodes/2026-06-30/82737022.json`)
  - Episode 82737056 P1: quwon_000 reward=1 (`downloads/episodes/2026-06-30/82737056.json`)
  - Episode 82737525 P1: quwon_000 reward=1 (`downloads/episodes/2026-06-30/82737525.json`)

### Exact 54: フーディン超

- 出現数: 10
- 勝敗: 5勝 5敗
- 勝率: 50.0%
- Wilson下限: 23.7%
- 主軸ポケモン: ユンゲラー / ケーシィ / ノココッチ / ノコッチ / フーディン
- 主要トレーナーズ: なかよしポフィン / ポケパッド / トウコ / ヒカリ / バトルコロシアム / ふしぎなアメ
- 主な使用者: Kohenyan
- 代表 episode:
  - Episode 82741442 P1: Kohenyan reward=-1 (`downloads/episodes/2026-06-30/82741442.json`)
  - Episode 82763226 P0: Kohenyan reward=-1 (`downloads/episodes/2026-06-30/82763226.json`)
  - Episode 82768184 P1: Kohenyan reward=-1 (`downloads/episodes/2026-06-30/82768184.json`)
  - Episode 82769864 P0: Kohenyan reward=1 (`downloads/episodes/2026-06-30/82769864.json`)
  - Episode 82780861 P0: Kohenyan reward=1 (`downloads/episodes/2026-06-30/82780861.json`)

### Exact 55: ホップのボクレー / ホップのオーロット

- 出現数: 16
- 勝敗: 7勝 9敗
- 勝率: 43.8%
- Wilson下限: 23.1%
- 主軸ポケモン: ホップのボクレー / ホップのオーロット / ホップのウッウ / ホップのカビゴン
- 主要トレーナーズ: ホップのバッグ / ポケギア3.0 / ロケット団のレシーバー / ホップのこだわりハチマキ / ロケット団のラムダ / リーリエの決心
- 主な使用者: Yushin Ito, EF, 俺達何え?チームcudgk
- 代表 episode:
  - Episode 82724737 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82724737.json`)
  - Episode 82739714 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82739714.json`)
  - Episode 82762120 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82762120.json`)
  - Episode 82765669 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82765669.json`)
  - Episode 82769087 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82769087.json`)

### Exact 56: メガスターミーex水

- 出現数: 5
- 勝敗: 3勝 2敗
- 勝率: 60.0%
- Wilson下限: 23.1%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex / ユキワラシ / メガユキメノコex
- 主要トレーナーズ: 改造ハンマー / ポケギア3.0 / リーリエの決心 / ロケット団の監視塔 / ジャッジマン / なかよしポフィン
- 主な使用者: shogo1229
- 代表 episode:
  - Episode 82765165 P0: shogo1229 reward=1 (`downloads/episodes/2026-06-30/82765165.json`)
  - Episode 82770332 P1: shogo1229 reward=1 (`downloads/episodes/2026-06-30/82770332.json`)
  - Episode 82775872 P1: shogo1229 reward=1 (`downloads/episodes/2026-06-30/82775872.json`)
  - Episode 82781888 P1: shogo1229 reward=-1 (`downloads/episodes/2026-06-30/82781888.json`)
  - Episode 82828942 P1: shogo1229 reward=-1 (`downloads/episodes/2026-06-30/82828942.json`)

### Exact 57: フーディン超

- 出現数: 5
- 勝敗: 3勝 2敗
- 勝率: 60.0%
- Wilson下限: 23.1%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / トウコ / ヒカリ / バトルコロシアム
- 主な使用者: TAKUTO INOUE, okg
- 代表 episode:
  - Episode 82735307 P1: okg reward=-1 (`downloads/episodes/2026-06-30/82735307.json`)
  - Episode 82813563 P1: TAKUTO INOUE reward=1 (`downloads/episodes/2026-06-30/82813563.json`)
  - Episode 82814214 P1: TAKUTO INOUE reward=1 (`downloads/episodes/2026-06-30/82814214.json`)
  - Episode 82814862 P1: TAKUTO INOUE reward=-1 (`downloads/episodes/2026-06-30/82814862.json`)
  - Episode 82815348 P1: TAKUTO INOUE reward=1 (`downloads/episodes/2026-06-30/82815348.json`)

### Exact 58: フーディン超

- 出現数: 5
- 勝敗: 3勝 2敗
- 勝率: 60.0%
- Wilson下限: 23.1%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: トウコ / ポケパッド / なかよしポフィン / ヒカリ / リーリエの決心 / ボスの指令
- 主な使用者: suwat513
- 代表 episode:
  - Episode 82826314 P1: suwat513 reward=1 (`downloads/episodes/2026-06-30/82826314.json`)
  - Episode 82826811 P1: suwat513 reward=1 (`downloads/episodes/2026-06-30/82826811.json`)
  - Episode 82827309 P0: suwat513 reward=-1 (`downloads/episodes/2026-06-30/82827309.json`)
  - Episode 82827803 P0: suwat513 reward=-1 (`downloads/episodes/2026-06-30/82827803.json`)
  - Episode 82828946 P0: suwat513 reward=1 (`downloads/episodes/2026-06-30/82828946.json`)

### Exact 59: ブリジュラスex鋼

- 出現数: 8
- 勝敗: 4勝 4敗
- 勝率: 50.0%
- Wilson下限: 21.5%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケギア3.0 / ジャンボアイス / ポケパッド / 探検家の先導
- 主な使用者: Yufeng
- 代表 episode:
  - Episode 82728060 P1: Yufeng reward=1 (`downloads/episodes/2026-06-30/82728060.json`)
  - Episode 82728709 P1: Yufeng reward=1 (`downloads/episodes/2026-06-30/82728709.json`)
  - Episode 82729376 P0: Yufeng reward=-1 (`downloads/episodes/2026-06-30/82729376.json`)
  - Episode 82730011 P0: Yufeng reward=1 (`downloads/episodes/2026-06-30/82730011.json`)
  - Episode 82730493 P1: Yufeng reward=-1 (`downloads/episodes/2026-06-30/82730493.json`)

### Exact 60: シロナのフカマル / シロナのガバイト

- 出現数: 14
- 勝敗: 6勝 8敗
- 勝率: 42.9%
- Wilson下限: 21.4%
- 主軸ポケモン: シロナのフカマル / シロナのガバイト / シロナのロゼリア / シロナのロズレイド / シロナのガブリアスex
- 主要トレーナーズ: リーリエの決心 / ボスの指令 / ポケパッド / なかよしポフィン / ファイトゴング / シロナのパワーウエイト
- 主な使用者: Orin
- 代表 episode:
  - Episode 82812295 P0: Orin reward=1 (`downloads/episodes/2026-06-30/82812295.json`)
  - Episode 82812937 P1: Orin reward=1 (`downloads/episodes/2026-06-30/82812937.json`)
  - Episode 82813573 P1: Orin reward=-1 (`downloads/episodes/2026-06-30/82813573.json`)
  - Episode 82814229 P1: Orin reward=1 (`downloads/episodes/2026-06-30/82814229.json`)
  - Episode 82814874 P1: Orin reward=-1 (`downloads/episodes/2026-06-30/82814874.json`)

### Exact 61: フーディン超

- 出現数: 11
- 勝敗: 5勝 6敗
- 勝率: 45.5%
- Wilson下限: 21.3%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / トウコ / なかよしポフィン / ポケパッド / 夜の鉱山 / ボスの指令
- 主な使用者: capbloo
- 代表 episode:
  - Episode 82739797 P0: capbloo reward=1 (`downloads/episodes/2026-06-30/82739797.json`)
  - Episode 82761476 P0: capbloo reward=-1 (`downloads/episodes/2026-06-30/82761476.json`)
  - Episode 82769225 P1: capbloo reward=1 (`downloads/episodes/2026-06-30/82769225.json`)
  - Episode 82771635 P1: capbloo reward=-1 (`downloads/episodes/2026-06-30/82771635.json`)
  - Episode 82772743 P0: capbloo reward=-1 (`downloads/episodes/2026-06-30/82772743.json`)

### Exact 62: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 2勝 1敗
- 勝率: 66.7%
- Wilson下限: 20.8%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / 夜のタンカ / 探検家の先導
- 主な使用者: Moegi
- 代表 episode:
  - Episode 82725429 P0: Moegi reward=1 (`downloads/episodes/2026-06-30/82725429.json`)
  - Episode 82739077 P1: Moegi reward=-1 (`downloads/episodes/2026-06-30/82739077.json`)
  - Episode 82740306 P1: Moegi reward=1 (`downloads/episodes/2026-06-30/82740306.json`)

### Exact 63: メガルカリオex闘

- 出現数: 3
- 勝敗: 2勝 1敗
- 勝率: 66.7%
- Wilson下限: 20.8%
- 主軸ポケモン: リオル / メガルカリオex / ソルロック / マクノシタ / ハリテヤマ
- 主要トレーナーズ: ダークボール / パワープロテイン / ファイトゴング / ゼイユ / リーリエの決心 / ボスの指令
- 主な使用者: Kuriboh
- 代表 episode:
  - Episode 82787125 P1: Kuriboh reward=1 (`downloads/episodes/2026-06-30/82787125.json`)
  - Episode 82816466 P0: Kuriboh reward=-1 (`downloads/episodes/2026-06-30/82816466.json`)
  - Episode 82827803 P1: Kuriboh reward=1 (`downloads/episodes/2026-06-30/82827803.json`)

### Exact 64: ブリジュラスex鋼

- 出現数: 15
- 勝敗: 6勝 9敗
- 勝率: 40.0%
- Wilson下限: 19.8%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ジャンボアイス / ボスの指令 / 探検家の先導
- 主な使用者: MR.h
- 代表 episode:
  - Episode 82728063 P0: MR.h reward=-1 (`downloads/episodes/2026-06-30/82728063.json`)
  - Episode 82732276 P1: MR.h reward=-1 (`downloads/episodes/2026-06-30/82732276.json`)
  - Episode 82757270 P0: MR.h reward=-1 (`downloads/episodes/2026-06-30/82757270.json`)
  - Episode 82762431 P1: MR.h reward=1 (`downloads/episodes/2026-06-30/82762431.json`)
  - Episode 82763724 P0: MR.h reward=-1 (`downloads/episodes/2026-06-30/82763724.json`)

### Exact 65: ノコッチ / ホップのボクレー

- 出現数: 12
- 勝敗: 5勝 7敗
- 勝率: 41.7%
- Wilson下限: 19.3%
- 主軸ポケモン: ノコッチ / ホップのボクレー / ノココッチ / ホップのカビゴン / ホップのオーロット
- 主要トレーナーズ: なかよしポフィン / ポケギア3.0 / ポケパッド / ホップのこだわりハチマキ / リーリエの決心 / ハロンタウン
- 主な使用者: Ryosei Kojima, matsurih, Shirag Maharaj, CYLik
- 代表 episode:
  - Episode 82728060 P0: Ryosei Kojima reward=-1 (`downloads/episodes/2026-06-30/82728060.json`)
  - Episode 82728706 P0: Shirag Maharaj reward=1 (`downloads/episodes/2026-06-30/82728706.json`)
  - Episode 82732237 P0: Ryosei Kojima reward=1 (`downloads/episodes/2026-06-30/82732237.json`)
  - Episode 82738538 P1: CYLik reward=-1 (`downloads/episodes/2026-06-30/82738538.json`)
  - Episode 82740266 P1: matsurih reward=-1 (`downloads/episodes/2026-06-30/82740266.json`)

### Exact 66: ロケット団のタマンチュラ / ロケット団のワナイダー

- 出現数: 9
- 勝敗: 4勝 5敗
- 勝率: 44.4%
- Wilson下限: 18.9%
- 主軸ポケモン: ロケット団のタマンチュラ / ロケット団のワナイダー / ロケット団のミュウツーex / ロケット団のミミッキュ / ロケット団のフリーザー
- 主要トレーナーズ: ポケパッド / ロケット団のレシーバー / ロケット団のアテナ / ロケット団のランス / ロケット団のアポロ / ロケット団のサカキ
- 主な使用者: kashiwashira
- 代表 episode:
  - Episode 82731841 P1: kashiwashira reward=-1 (`downloads/episodes/2026-06-30/82731841.json`)
  - Episode 82739035 P1: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82739035.json`)
  - Episode 82743841 P0: kashiwashira reward=-1 (`downloads/episodes/2026-06-30/82743841.json`)
  - Episode 82768128 P0: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82768128.json`)
  - Episode 82817120 P1: kashiwashira reward=1 (`downloads/episodes/2026-06-30/82817120.json`)

### Exact 67: フーディン超

- 出現数: 23
- 勝敗: 8勝 15敗
- 勝率: 34.8%
- Wilson下限: 18.8%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ヒカリ / トウコ / なかよしポフィン / ポケパッド / 改造ハンマー / ボスの指令
- 主な使用者: Inlon Kou, カドラバ Kadoraba
- 代表 episode:
  - Episode 82723609 P0: Inlon Kou reward=1 (`downloads/episodes/2026-06-30/82723609.json`)
  - Episode 82723611 P0: カドラバ Kadoraba reward=1 (`downloads/episodes/2026-06-30/82723611.json`)
  - Episode 82741415 P1: Inlon Kou reward=-1 (`downloads/episodes/2026-06-30/82741415.json`)
  - Episode 82742691 P0: Inlon Kou reward=-1 (`downloads/episodes/2026-06-30/82742691.json`)
  - Episode 82744816 P1: カドラバ Kadoraba reward=-1 (`downloads/episodes/2026-06-30/82744816.json`)

### Exact 68: シロナのフカマル / シロナのガバイト

- 出現数: 17
- 勝敗: 6勝 11敗
- 勝率: 35.3%
- Wilson下限: 17.3%
- 主軸ポケモン: シロナのフカマル / シロナのガバイト / シロナのロゼリア / シロナのロズレイド / シロナのガブリアスex
- 主要トレーナーズ: なかよしポフィン / ファイトゴング / ポケパッド / シロナのパワーウエイト / リーリエの決心 / パワープロテイン
- 主な使用者: katsudon 421
- 代表 episode:
  - Episode 82736483 P1: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82736483.json`)
  - Episode 82738083 P0: katsudon 421 reward=1 (`downloads/episodes/2026-06-30/82738083.json`)
  - Episode 82741433 P1: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82741433.json`)
  - Episode 82742724 P0: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82742724.json`)
  - Episode 82748089 P1: katsudon 421 reward=-1 (`downloads/episodes/2026-06-30/82748089.json`)

### Exact 69: マリィのベロバー / マリィのオーロンゲex

- 出現数: 17
- 勝敗: 6勝 11敗
- 勝率: 35.3%
- Wilson下限: 17.3%
- 主軸ポケモン: マリィのベロバー / マリィのオーロンゲex / ノコッチ / ノココッチ / マシマシラ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / リーリエの決心 / ヒカリ / スパイクタウンジム
- 主な使用者: The Debauchery Tea Party
- 代表 episode:
  - Episode 82733556 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82733556.json`)
  - Episode 82745145 P0: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82745145.json`)
  - Episode 82751511 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82751511.json`)
  - Episode 82753775 P0: The Debauchery Tea Party reward=1 (`downloads/episodes/2026-06-30/82753775.json`)
  - Episode 82755554 P1: The Debauchery Tea Party reward=-1 (`downloads/episodes/2026-06-30/82755554.json`)

### Exact 70: ブリジュラスex鋼

- 出現数: 10
- 勝敗: 4勝 6敗
- 勝率: 40.0%
- Wilson下限: 16.8%
- 主軸ポケモン: ブリジュラスex / ジュラルドン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケギア3.0 / ポケパッド / ボスの指令 / ゼイユ
- 主な使用者: ShumpeiNomura
- 代表 episode:
  - Episode 82721340 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82721340.json`)
  - Episode 82731144 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82731144.json`)
  - Episode 82741350 P0: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82741350.json`)
  - Episode 82765594 P0: ShumpeiNomura reward=-1 (`downloads/episodes/2026-06-30/82765594.json`)
  - Episode 82765672 P0: ShumpeiNomura reward=-1 (`downloads/episodes/2026-06-30/82765672.json`)

### Exact 71: メガルカリオex闘

- 出現数: 22
- 勝敗: 7勝 15敗
- 勝率: 31.8%
- Wilson下限: 16.4%
- 主軸ポケモン: リオル / メガルカリオex / ソルロック / マクノシタ / ハリテヤマ
- 主要トレーナーズ: ダークボール / パワープロテイン / ファイトゴング / ゼイユ / リーリエの決心 / ボスの指令
- 主な使用者: easonyanyan, Rajan Nagarajan, need a job (we're unemployed), Octavi Grau
- 代表 episode:
  - Episode 82720923 P0: need a job (we're unemployed) reward=-1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720987 P0: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82720987.json`)
  - Episode 82727561 P1: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82727561.json`)
  - Episode 82731114 P1: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82731114.json`)
  - Episode 82741407 P0: Rajan Nagarajan reward=-1 (`downloads/episodes/2026-06-30/82741407.json`)

### Exact 72: フーディン超

- 出現数: 7
- 勝敗: 3勝 4敗
- 勝率: 42.9%
- Wilson下限: 15.8%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / トウコ / 改造ハンマー / ヒカリ / ボスの指令
- 主な使用者: Himi Yamato
- 代表 episode:
  - Episode 82739797 P1: Himi Yamato reward=-1 (`downloads/episodes/2026-06-30/82739797.json`)
  - Episode 82762616 P0: Himi Yamato reward=1 (`downloads/episodes/2026-06-30/82762616.json`)
  - Episode 82780934 P0: Himi Yamato reward=-1 (`downloads/episodes/2026-06-30/82780934.json`)
  - Episode 82783118 P0: Himi Yamato reward=-1 (`downloads/episodes/2026-06-30/82783118.json`)
  - Episode 82803340 P0: Himi Yamato reward=1 (`downloads/episodes/2026-06-30/82803340.json`)

### Exact 73: フーディン超

- 出現数: 7
- 勝敗: 3勝 4敗
- 勝率: 42.9%
- Wilson下限: 15.8%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ふしぎなアメ / 改造ハンマー / ヒカリ / トウコ
- 主な使用者: takuya noto
- 代表 episode:
  - Episode 82768068 P1: takuya noto reward=-1 (`downloads/episodes/2026-06-30/82768068.json`)
  - Episode 82775191 P1: takuya noto reward=-1 (`downloads/episodes/2026-06-30/82775191.json`)
  - Episode 82776964 P1: takuya noto reward=-1 (`downloads/episodes/2026-06-30/82776964.json`)
  - Episode 82779180 P1: takuya noto reward=-1 (`downloads/episodes/2026-06-30/82779180.json`)
  - Episode 82784962 P0: takuya noto reward=1 (`downloads/episodes/2026-06-30/82784962.json`)

### Exact 74: メガユキメノコex水

- 出現数: 7
- 勝敗: 3勝 4敗
- 勝率: 42.9%
- Wilson下限: 15.8%
- 主軸ポケモン: メガユキメノコex / ユキワラシ / ノコッチ / ノココッチ / スピンロトム
- 主要トレーナーズ: なかよしポフィン / ポケパッド / クラッシュハンマー / リーリエの決心 / ミツルの思いやり / ポケギア3.0
- 主な使用者: Gotem Penguin
- 代表 episode:
  - Episode 82720949 P1: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82720949.json`)
  - Episode 82745316 P1: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82745316.json`)
  - Episode 82760920 P0: Gotem Penguin reward=1 (`downloads/episodes/2026-06-30/82760920.json`)
  - Episode 82781390 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82781390.json`)
  - Episode 82801095 P0: Gotem Penguin reward=-1 (`downloads/episodes/2026-06-30/82801095.json`)

### Exact 75: メガスターミーex水

- 出現数: 15
- 勝敗: 5勝 10敗
- 勝率: 33.3%
- Wilson下限: 15.2%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex
- 主要トレーナーズ: ポケギア3.0 / なかよしポフィン / クラッシュハンマー / セイジ / ミツルの思いやり / リーリエの決心
- 主な使用者: Shun
- 代表 episode:
  - Episode 82720990 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82720990.json`)
  - Episode 82721968 P0: Shun reward=1 (`downloads/episodes/2026-06-30/82721968.json`)
  - Episode 82722605 P0: Shun reward=-1 (`downloads/episodes/2026-06-30/82722605.json`)
  - Episode 82722639 P0: Shun reward=1 (`downloads/episodes/2026-06-30/82722639.json`)
  - Episode 82723114 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82723114.json`)

### Exact 76: フーディン超

- 出現数: 4
- 勝敗: 2勝 2敗
- 勝率: 50.0%
- Wilson下限: 15.0%
- 主軸ポケモン: ケーシィ / ユンゲラー / ノココッチ / ノコッチ / フーディン
- 主要トレーナーズ: 改造ハンマー / なかよしポフィン / ポケパッド / ヒカリ / 夜の鉱山 / ふしぎなアメ
- 主な使用者: ondy0705
- 代表 episode:
  - Episode 82741435 P0: ondy0705 reward=1 (`downloads/episodes/2026-06-30/82741435.json`)
  - Episode 82766623 P1: ondy0705 reward=-1 (`downloads/episodes/2026-06-30/82766623.json`)
  - Episode 82824686 P1: ondy0705 reward=1 (`downloads/episodes/2026-06-30/82824686.json`)
  - Episode 82826359 P0: ondy0705 reward=-1 (`downloads/episodes/2026-06-30/82826359.json`)

### Exact 77: ホップのボクレー / ホップのオーロット

- 出現数: 4
- 勝敗: 2勝 2敗
- 勝率: 50.0%
- Wilson下限: 15.0%
- 主軸ポケモン: ホップのボクレー / ホップのオーロット / ノコッチ / ノココッチ / ホップのウッウ
- 主要トレーナーズ: ホップのバッグ / なかよしポフィン / ポケパッド / ポケギア3.0 / ホップのこだわりハチマキ / リーリエの決心
- 主な使用者: Shunji Minode
- 代表 episode:
  - Episode 82776452 P0: Shunji Minode reward=-1 (`downloads/episodes/2026-06-30/82776452.json`)
  - Episode 82780361 P0: Shunji Minode reward=-1 (`downloads/episodes/2026-06-30/82780361.json`)
  - Episode 82782481 P1: Shunji Minode reward=1 (`downloads/episodes/2026-06-30/82782481.json`)
  - Episode 82814392 P0: Shunji Minode reward=1 (`downloads/episodes/2026-06-30/82814392.json`)

### Exact 78: フーディン超

- 出現数: 13
- 勝敗: 4勝 9敗
- 勝率: 30.8%
- Wilson下限: 12.7%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: ポケパッド / なかよしポフィン / ヒカリ / トウコ / ふしぎなアメ / 夜のタンカ
- 主な使用者: ヌメルゴンex
- 代表 episode:
  - Episode 82732876 P1: ヌメルゴンex reward=-1 (`downloads/episodes/2026-06-30/82732876.json`)
  - Episode 82741442 P0: ヌメルゴンex reward=1 (`downloads/episodes/2026-06-30/82741442.json`)
  - Episode 82743802 P1: ヌメルゴンex reward=-1 (`downloads/episodes/2026-06-30/82743802.json`)
  - Episode 82744344 P0: ヌメルゴンex reward=-1 (`downloads/episodes/2026-06-30/82744344.json`)
  - Episode 82755027 P0: ヌメルゴンex reward=1 (`downloads/episodes/2026-06-30/82755027.json`)

### Exact 79: メガスターミーex水

- 出現数: 13
- 勝敗: 4勝 9敗
- 勝率: 30.8%
- Wilson下限: 12.7%
- 主軸ポケモン: ヒトデマン / メガスターミーex / サマヨール / マシマシラ / ヨマワル
- 主要トレーナーズ: ハイパーボール / ポケパッド / なかよしポフィン / トウコ / リーリエの決心 / 危ない廃墟
- 主な使用者: Jaga
- 代表 episode:
  - Episode 82721019 P0: Jaga reward=-1 (`downloads/episodes/2026-06-30/82721019.json`)
  - Episode 82724781 P1: Jaga reward=1 (`downloads/episodes/2026-06-30/82724781.json`)
  - Episode 82735841 P0: Jaga reward=-1 (`downloads/episodes/2026-06-30/82735841.json`)
  - Episode 82738118 P1: Jaga reward=-1 (`downloads/episodes/2026-06-30/82738118.json`)
  - Episode 82752641 P0: Jaga reward=1 (`downloads/episodes/2026-06-30/82752641.json`)

### Exact 80: ドラパルト系

- 出現数: 9
- 勝敗: 3勝 6敗
- 勝率: 33.3%
- Wilson下限: 12.1%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / ニャースex
- 主要トレーナーズ: ふしぎなアメ / なかよしポフィン / ハイパーボール / ポケパッド / ボスの指令 / アカマツ
- 主な使用者: mw
- 代表 episode:
  - Episode 82738627 P0: mw reward=1 (`downloads/episodes/2026-06-30/82738627.json`)
  - Episode 82764508 P0: mw reward=-1 (`downloads/episodes/2026-06-30/82764508.json`)
  - Episode 82798700 P1: mw reward=1 (`downloads/episodes/2026-06-30/82798700.json`)
  - Episode 82801686 P1: mw reward=-1 (`downloads/episodes/2026-06-30/82801686.json`)
  - Episode 82802633 P1: mw reward=-1 (`downloads/episodes/2026-06-30/82802633.json`)

### Exact 81: フーディン超

- 出現数: 9
- 勝敗: 3勝 6敗
- 勝率: 33.3%
- Wilson下限: 12.1%
- 主軸ポケモン: フーディン / ユンゲラー / ケーシィ / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ふしぎなアメ / トウコ / ヒカリ / 改造ハンマー
- 主な使用者: Lapra5
- 代表 episode:
  - Episode 82720918 P1: Lapra5 reward=-1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82743371 P1: Lapra5 reward=-1 (`downloads/episodes/2026-06-30/82743371.json`)
  - Episode 82749698 P1: Lapra5 reward=1 (`downloads/episodes/2026-06-30/82749698.json`)
  - Episode 82765087 P1: Lapra5 reward=-1 (`downloads/episodes/2026-06-30/82765087.json`)
  - Episode 82766623 P0: Lapra5 reward=1 (`downloads/episodes/2026-06-30/82766623.json`)

### Exact 82: メガルカリオex闘

- 出現数: 15
- 勝敗: 4勝 11敗
- 勝率: 26.7%
- Wilson下限: 10.9%
- 主軸ポケモン: メガルカリオex / リオル / ソルロック / ルナトーン
- 主要トレーナーズ: ダークボール / ポケパッド / パワープロテイン / ファイトゴング / リーリエの決心 / ポケモンいれかえ
- 主な使用者: Akira-Ninth
- 代表 episode:
  - Episode 82728057 P0: Akira-Ninth reward=1 (`downloads/episodes/2026-06-30/82728057.json`)
  - Episode 82735354 P0: Akira-Ninth reward=-1 (`downloads/episodes/2026-06-30/82735354.json`)
  - Episode 82747426 P0: Akira-Ninth reward=-1 (`downloads/episodes/2026-06-30/82747426.json`)
  - Episode 82757808 P0: Akira-Ninth reward=-1 (`downloads/episodes/2026-06-30/82757808.json`)
  - Episode 82775197 P1: Akira-Ninth reward=-1 (`downloads/episodes/2026-06-30/82775197.json`)

### Exact 83: ブリジュラスex鋼

- 出現数: 6
- 勝敗: 2勝 4敗
- 勝率: 33.3%
- Wilson下限: 9.7%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ジャンボアイス / ボスの指令 / 探検家の先導
- 主な使用者: cimyzzz
- 代表 episode:
  - Episode 82738563 P1: cimyzzz reward=-1 (`downloads/episodes/2026-06-30/82738563.json`)
  - Episode 82742712 P0: cimyzzz reward=-1 (`downloads/episodes/2026-06-30/82742712.json`)
  - Episode 82786095 P0: cimyzzz reward=-1 (`downloads/episodes/2026-06-30/82786095.json`)
  - Episode 82802713 P0: cimyzzz reward=1 (`downloads/episodes/2026-06-30/82802713.json`)
  - Episode 82811530 P0: cimyzzz reward=-1 (`downloads/episodes/2026-06-30/82811530.json`)

### Exact 84: ブリジュラスex鋼

- 出現数: 6
- 勝敗: 2勝 4敗
- 勝率: 33.3%
- Wilson下限: 9.7%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / 探検家の先導 / リーリエの決心
- 主な使用者: NukoNiko15, Shoya Taguchi
- 代表 episode:
  - Episode 82740293 P1: NukoNiko15 reward=-1 (`downloads/episodes/2026-06-30/82740293.json`)
  - Episode 82748064 P0: NukoNiko15 reward=-1 (`downloads/episodes/2026-06-30/82748064.json`)
  - Episode 82750962 P0: Shoya Taguchi reward=-1 (`downloads/episodes/2026-06-30/82750962.json`)
  - Episode 82762125 P0: Shoya Taguchi reward=-1 (`downloads/episodes/2026-06-30/82762125.json`)
  - Episode 82770984 P1: NukoNiko15 reward=1 (`downloads/episodes/2026-06-30/82770984.json`)

### Exact 85: フーディン超

- 出現数: 6
- 勝敗: 2勝 4敗
- 勝率: 33.3%
- Wilson下限: 9.7%
- 主軸ポケモン: ノコッチ / ケーシィ / ユンゲラー / フーディン / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / トウコ / ヒカリ
- 主な使用者: knomura03
- 代表 episode:
  - Episode 82824572 P1: knomura03 reward=1 (`downloads/episodes/2026-06-30/82824572.json`)
  - Episode 82825065 P0: knomura03 reward=-1 (`downloads/episodes/2026-06-30/82825065.json`)
  - Episode 82826359 P1: knomura03 reward=1 (`downloads/episodes/2026-06-30/82826359.json`)
  - Episode 82826859 P0: knomura03 reward=-1 (`downloads/episodes/2026-06-30/82826859.json`)
  - Episode 82827362 P1: knomura03 reward=-1 (`downloads/episodes/2026-06-30/82827362.json`)

### Exact 86: メガスターミーex水

- 出現数: 3
- 勝敗: 1勝 2敗
- 勝率: 33.3%
- Wilson下限: 6.1%
- 主軸ポケモン: エースバーン / メガスターミーex / ヒトデマン
- 主要トレーナーズ: なかよしポフィン / ポケギア3.0 / メガシグナル / セイジ / リーリエの決心 / ミツルの思いやり
- 主な使用者: ysakuragi
- 代表 episode:
  - Episode 82743841 P1: ysakuragi reward=1 (`downloads/episodes/2026-06-30/82743841.json`)
  - Episode 82764517 P1: ysakuragi reward=-1 (`downloads/episodes/2026-06-30/82764517.json`)
  - Episode 82817752 P0: ysakuragi reward=-1 (`downloads/episodes/2026-06-30/82817752.json`)

### Exact 87: フーディン超

- 出現数: 3
- 勝敗: 1勝 2敗
- 勝率: 33.3%
- Wilson下限: 6.1%
- 主軸ポケモン: ケーシィ / ユンゲラー / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ハンディサーキュレーター / ポケパッド / バトルコロシアム / ヒカリ / トウコ
- 主な使用者: BluezLee
- 代表 episode:
  - Episode 82739804 P1: BluezLee reward=-1 (`downloads/episodes/2026-06-30/82739804.json`)
  - Episode 82749698 P0: BluezLee reward=-1 (`downloads/episodes/2026-06-30/82749698.json`)
  - Episode 82756045 P1: BluezLee reward=1 (`downloads/episodes/2026-06-30/82756045.json`)

### Exact 88: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 1勝 2敗
- 勝率: 33.3%
- Wilson下限: 6.1%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / ボスの指令
- 主な使用者: sea8gull
- 代表 episode:
  - Episode 82736495 P1: sea8gull reward=-1 (`downloads/episodes/2026-06-30/82736495.json`)
  - Episode 82769779 P1: sea8gull reward=1 (`downloads/episodes/2026-06-30/82769779.json`)
  - Episode 82796921 P1: sea8gull reward=-1 (`downloads/episodes/2026-06-30/82796921.json`)

### Exact 89: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 1勝 2敗
- 勝率: 33.3%
- Wilson下限: 6.1%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケギア3.0 / ポケパッド / 探検家の先導 / リーリエの決心
- 主な使用者: ezreal77
- 代表 episode:
  - Episode 82722674 P1: ezreal77 reward=-1 (`downloads/episodes/2026-06-30/82722674.json`)
  - Episode 82755027 P1: ezreal77 reward=-1 (`downloads/episodes/2026-06-30/82755027.json`)
  - Episode 82810886 P1: ezreal77 reward=1 (`downloads/episodes/2026-06-30/82810886.json`)

### Exact 90: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 1勝 2敗
- 勝率: 33.3%
- Wilson下限: 6.1%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケギア3.0 / ジャンボアイス / ポケパッド / 探検家の先導
- 主な使用者: tadhase
- 代表 episode:
  - Episode 82760464 P1: tadhase reward=1 (`downloads/episodes/2026-06-30/82760464.json`)
  - Episode 82762628 P1: tadhase reward=-1 (`downloads/episodes/2026-06-30/82762628.json`)
  - Episode 82781917 P0: tadhase reward=-1 (`downloads/episodes/2026-06-30/82781917.json`)

### Exact 91: カジッチュ / カミッチュ

- 出現数: 5
- 勝敗: 1勝 4敗
- 勝率: 20.0%
- Wilson下限: 3.6%
- 主軸ポケモン: カジッチュ / カミッチュ / サルノリ / バチンキー / トサキント
- 主要トレーナーズ: なかよしポフィン / むしとりセット / ポケパッド / お祭り会場 / リーリエの決心 / からておうの稽古
- 主な使用者: aca-ta
- 代表 episode:
  - Episode 82721529 P1: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82721529.json`)
  - Episode 82743844 P0: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82743844.json`)
  - Episode 82757927 P0: aca-ta reward=1 (`downloads/episodes/2026-06-30/82757927.json`)
  - Episode 82758355 P1: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82758355.json`)
  - Episode 82776967 P0: aca-ta reward=-1 (`downloads/episodes/2026-06-30/82776967.json`)

### Exact 92: フーディン超

- 出現数: 8
- 勝敗: 1勝 7敗
- 勝率: 12.5%
- Wilson下限: 2.2%
- 主軸ポケモン: ケーシィ / ユンゲラー / ノコッチ / フーディン / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / なかよしポフィン / ポケパッド / トウコ / ヒカリ / ボスの指令
- 主な使用者: kawachi
- 代表 episode:
  - Episode 82720990 P0: kawachi reward=-1 (`downloads/episodes/2026-06-30/82720990.json`)
  - Episode 82721455 P1: kawachi reward=-1 (`downloads/episodes/2026-06-30/82721455.json`)
  - Episode 82742734 P0: kawachi reward=-1 (`downloads/episodes/2026-06-30/82742734.json`)
  - Episode 82762586 P1: kawachi reward=-1 (`downloads/episodes/2026-06-30/82762586.json`)
  - Episode 82780414 P0: kawachi reward=-1 (`downloads/episodes/2026-06-30/82780414.json`)

### Exact 93: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 0勝 3敗
- 勝率: 0.0%
- Wilson下限: 0.0%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / ボスの指令
- 主な使用者: kokatsu
- 代表 episode:
  - Episode 82730424 P0: kokatsu reward=-1 (`downloads/episodes/2026-06-30/82730424.json`)
  - Episode 82779202 P0: kokatsu reward=-1 (`downloads/episodes/2026-06-30/82779202.json`)
  - Episode 82827897 P0: kokatsu reward=-1 (`downloads/episodes/2026-06-30/82827897.json`)

### Exact 94: ブリジュラスex鋼

- 出現数: 3
- 勝敗: 0勝 3敗
- 勝率: 0.0%
- Wilson下限: 0.0%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / ボスの指令 / 探検家の先導
- 主な使用者: Yiding Cui
- 代表 episode:
  - Episode 82813664 P0: Yiding Cui reward=-1 (`downloads/episodes/2026-06-30/82813664.json`)
  - Episode 82815448 P0: Yiding Cui reward=-1 (`downloads/episodes/2026-06-30/82815448.json`)
  - Episode 82819014 P1: Yiding Cui reward=-1 (`downloads/episodes/2026-06-30/82819014.json`)

### Exact 95: ドラパルト系

- 出現数: 3
- 勝敗: 0勝 3敗
- 勝率: 0.0%
- Wilson下限: 0.0%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / キチキギスex
- 主要トレーナーズ: なかよしポフィン / ハイパーボール / ポケパッド / アカマツ / リーリエの決心 / ふしぎなアメ
- 主な使用者: koiwashi
- 代表 episode:
  - Episode 82730470 P1: koiwashi reward=-1 (`downloads/episodes/2026-06-30/82730470.json`)
  - Episode 82758366 P0: koiwashi reward=-1 (`downloads/episodes/2026-06-30/82758366.json`)
  - Episode 82795149 P1: koiwashi reward=-1 (`downloads/episodes/2026-06-30/82795149.json`)

### Exact 96: ナンジャモ雷

- 出現数: 3
- 勝敗: 0勝 3敗
- 勝率: 0.0%
- Wilson下限: 0.0%
- 主軸ポケモン: ナンジャモのビリリダマ / ナンジャモのズピカ / ナンジャモのハラバリーex / ナンジャモのカイデン / ナンジャモのタイカイデン
- 主要トレーナーズ: リーリエの決心 / カナリィ / なかよしポフィン / ハイパーボール / ハッコウシティ / 夜のタンカ
- 主な使用者: yaruwo, pinoko
- 代表 episode:
  - Episode 82720940 P1: yaruwo reward=-1 (`downloads/episodes/2026-06-30/82720940.json`)
  - Episode 82763261 P1: yaruwo reward=-1 (`downloads/episodes/2026-06-30/82763261.json`)
  - Episode 82774665 P1: pinoko reward=-1 (`downloads/episodes/2026-06-30/82774665.json`)

### Exact 97: フーディン超

- 出現数: 3
- 勝敗: 0勝 3敗
- 勝率: 0.0%
- Wilson下限: 0.0%
- 主軸ポケモン: ノコッチ / フーディン / ユンゲラー / ケーシィ / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / トウコ / なかよしポフィン / ポケパッド / ヒカリ
- 主な使用者: Yuiki
- 代表 episode:
  - Episode 82765579 P0: Yuiki reward=-1 (`downloads/episodes/2026-06-30/82765579.json`)
  - Episode 82767212 P0: Yuiki reward=-1 (`downloads/episodes/2026-06-30/82767212.json`)
  - Episode 82768198 P1: Yuiki reward=-1 (`downloads/episodes/2026-06-30/82768198.json`)

## 相性候補

- ドラパルト系 vs イダイナキバ / イシズマイ: 7/7勝、勝率100.0%、Wilson下限64.6%
- ブリジュラスex鋼 vs メガスターミーex水: 46/63勝、勝率73.0%、Wilson下限61.0%
- タマザラシ / トドゼルガ vs フーディン超: 9/10勝、勝率90.0%、Wilson下限59.6%
- フーディン超 vs ブリジュラスex鋼: 123/189勝、勝率65.1%、Wilson下限58.0%
- ブリジュラスex鋼 vs タマザラシ / トドゼルガ: 5/5勝、勝率100.0%、Wilson下限56.6%
- マリィのベロバー / マシマシラ vs ドラパルト系: 5/5勝、勝率100.0%、Wilson下限56.6%
- キュワワー / ヒトモシ vs フーディン超: 4/4勝、勝率100.0%、Wilson下限51.0%
- クマシュン / オーガポン いしずえのめんex vs ブリジュラスex鋼: 4/4勝、勝率100.0%、Wilson下限51.0%
- マリィのベロバー / マシマシラ vs メガスターミーex水: 4/4勝、勝率100.0%、Wilson下限51.0%
- ブリジュラスex鋼 vs ドラパルト系: 33/51勝、勝率64.7%、Wilson下限51.0%
- イダイナキバ / イシズマイ vs フーディン超: 15/21勝、勝率71.4%、Wilson下限50.0%
- シロナのフカマル / シロナのガバイト vs ブリジュラスex鋼: 15/21勝、勝率71.4%、Wilson下限50.0%
- ブリジュラスex鋼 vs メガルカリオex闘: 14/20勝、勝率70.0%、Wilson下限48.1%
- フーディン超 vs シロナのフカマル / シロナのガバイト: 15/22勝、勝率68.2%、Wilson下限47.3%
- ドラパルト系 vs フーディン超: 19/30勝、勝率63.3%、Wilson下限45.5%
- イイネイヌ / ソルロック vs フーディン超: 7/9勝、勝率77.8%、Wilson下限45.3%
- シロナのフカマル / シロナのガバイト vs ドラパルト系: 7/9勝、勝率77.8%、Wilson下限45.3%
- クマシュン / オーガポン いしずえのめんex vs フーディン超: 3/3勝、勝率100.0%、Wilson下限43.8%
- フーディン超 vs マリィのベロバー / マリィのオーロンゲex: 3/3勝、勝率100.0%、Wilson下限43.8%
- メガガルーラex多色 vs ブリジュラスex鋼: 5/6勝、勝率83.3%、Wilson下限43.6%
