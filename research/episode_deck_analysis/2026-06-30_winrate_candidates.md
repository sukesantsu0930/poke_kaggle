# 勝率候補デッキ探索

入力: `downloads\episodes\2026-06-30`
対象: 60試合、120プレイヤーデッキ

## 探し方

- まずアーキタイプ単位で、出現数が少なすぎる候補を落とす。
- 単純勝率ではなく Wilson 信頼下限で並べる。少数の 1勝0敗 を過大評価しないため。
- exact 60枚リストも見るが、ここではリストを保存せず主軸カードだけ表示する。
- 最後に相性表を見る。全体勝率が普通でも、特定上位デッキに強い候補は残す。
- 注意: 公開 episode はランダム実験ではないため、デッキ性能と操作者の強さが混ざっている。

## アーキタイプ候補

### ブリジュラスex鋼

- 出現数: 53
- 勝敗: 28勝 25敗
- 勝率: 52.8%
- Wilson下限: 39.7%
- 主軸ポケモン: ブリジュラスex / ジュラルドン / エースバーン / ジーランス
- 主要トレーナーズ: ポケパッド / リーリエの決心 / ハイパーボール / ポケギア3.0 / フルメタルラボ / 夜のタンカ
- 主な使用者: ShumpeiNomura, Takaaki Matsuda, Peng Wang, DaJimmy
- 代表 episode:
  - Episode 82720905 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720922 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82720923 P1: Furkan Pirinc reward=1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720940 P0: david valor reward=1 (`downloads/episodes/2026-06-30/82720940.json`)
  - Episode 82720948 P1: DaJimmy reward=-1 (`downloads/episodes/2026-06-30/82720948.json`)

### フーディン超

- 出現数: 15
- 勝敗: 8勝 7敗
- 勝率: 53.3%
- Wilson下限: 30.1%
- 主軸ポケモン: ユンゲラー / ケーシィ / フーディン / ノコッチ / ノココッチ
- 主要トレーナーズ: なかよしポフィン / ポケパッド / ヒカリ / トウコ / ふしぎなアメ / 改造ハンマー
- 主な使用者: aidy, kawachi, kami, Lapra5
- 代表 episode:
  - Episode 82720918 P1: Lapra5 reward=-1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82720920 P1: aidy reward=-1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720922 P1: aidy reward=1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82720987 P1: Ajishio reward=1 (`downloads/episodes/2026-06-30/82720987.json`)
  - Episode 82720990 P0: kawachi reward=-1 (`downloads/episodes/2026-06-30/82720990.json`)

### メガガルーラex多色

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: メガガルーラex / ニャースex / リーリエのピッピex / ラティアスex / キチキギスex
- 主要トレーナーズ: アカマツ / ダークボール / ハイパーボール / ゼロの大空洞 / ボスの指令 / ワンダーパッチ
- 主な使用者: zoroark190
- 代表 episode:
  - Episode 82720918 P0: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82721427 P1: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82721949 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722610 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82722610.json`)
  - Episode 82723113 P1: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82723113.json`)

### メガスターミーex水

- 出現数: 27
- 勝敗: 11勝 16敗
- 勝率: 40.7%
- Wilson下限: 24.5%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex / サマヨール / ヨマワル
- 主要トレーナーズ: なかよしポフィン / リーリエの決心 / ポケギア3.0 / ミツルの思いやり / セイジ / クラッシュハンマー
- 主な使用者: Yushin Ito, Shun, Jaga, Pokkén
- 代表 episode:
  - Episode 82720905 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720920 P0: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720948 P0: Pokkén reward=1 (`downloads/episodes/2026-06-30/82720948.json`)
  - Episode 82720990 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82720990.json`)
  - Episode 82721019 P0: Jaga reward=-1 (`downloads/episodes/2026-06-30/82721019.json`)

### ドラパルト系

- 出現数: 5
- 勝敗: 3勝 2敗
- 勝率: 60.0%
- Wilson下限: 23.1%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / キチキギスex
- 主要トレーナーズ: なかよしポフィン / ハイパーボール / アカマツ / リーリエの決心 / クラッシュハンマー / ポケパッド
- 主な使用者: shibushun, milix, nattomaki, orikage
- 代表 episode:
  - Episode 82721496 P0: shibushun reward=1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721949 P1: milix reward=1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722024 P0: nattomaki reward=-1 (`downloads/episodes/2026-06-30/82722024.json`)
  - Episode 82722619 P1: orikage reward=1 (`downloads/episodes/2026-06-30/82722619.json`)
  - Episode 82724781 P0: Yasuo 0/10/0 reward=-1 (`downloads/episodes/2026-06-30/82724781.json`)

## exact 60枚リスト候補

### Exact 1: ブリジュラスex鋼

- 出現数: 10
- 勝敗: 6勝 4敗
- 勝率: 60.0%
- Wilson下限: 31.3%
- 主軸ポケモン: ブリジュラスex / ジュラルドン / ジーランス
- 主要トレーナーズ: 夜のタンカ / ハイパーボール / ポケパッド / ゼイユ / リーリエの決心 / ジャッジマン
- 主な使用者: ShumpeiNomura
- 代表 episode:
  - Episode 82720905 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82721442 P0: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82721442.json`)
  - Episode 82721958 P0: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82721958.json`)
  - Episode 82722605 P1: ShumpeiNomura reward=1 (`downloads/episodes/2026-06-30/82722605.json`)
  - Episode 82723114 P0: ShumpeiNomura reward=-1 (`downloads/episodes/2026-06-30/82723114.json`)

### Exact 2: ブリジュラスex鋼

- 出現数: 27
- 勝敗: 13勝 14敗
- 勝率: 48.1%
- Wilson下限: 30.7%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン / ジーランス
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / ジャンボアイス / ボスの指令
- 主な使用者: Peng Wang, DaJimmy, Furkan Pirinc, taka0808
- 代表 episode:
  - Episode 82720923 P1: Furkan Pirinc reward=1 (`downloads/episodes/2026-06-30/82720923.json`)
  - Episode 82720940 P0: david valor reward=1 (`downloads/episodes/2026-06-30/82720940.json`)
  - Episode 82720948 P1: DaJimmy reward=-1 (`downloads/episodes/2026-06-30/82720948.json`)
  - Episode 82720949 P0: nsytsqdtn reward=-1 (`downloads/episodes/2026-06-30/82720949.json`)
  - Episode 82721019 P1: taka0808 reward=1 (`downloads/episodes/2026-06-30/82721019.json`)

### Exact 3: ドラパルト系

- 出現数: 4
- 勝敗: 3勝 1敗
- 勝率: 75.0%
- Wilson下限: 30.1%
- 主軸ポケモン: ドラメシヤ / ドロンチ / ドラパルトex / スボミー / キチキギスex
- 主要トレーナーズ: なかよしポフィン / クラッシュハンマー / ハイパーボール / アカマツ / リーリエの決心 / ポケパッド
- 主な使用者: shibushun, milix, orikage, Yasuo 0/10/0
- 代表 episode:
  - Episode 82721496 P0: shibushun reward=1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721949 P1: milix reward=1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722619 P1: orikage reward=1 (`downloads/episodes/2026-06-30/82722619.json`)
  - Episode 82724781 P0: Yasuo 0/10/0 reward=-1 (`downloads/episodes/2026-06-30/82724781.json`)

### Exact 4: メガスターミーex水

- 出現数: 6
- 勝敗: 4勝 2敗
- 勝率: 66.7%
- Wilson下限: 30.0%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex
- 主要トレーナーズ: ポケギア3.0 / なかよしポフィン / クラッシュハンマー / セイジ / ミツルの思いやり / リーリエの決心
- 主な使用者: Shun
- 代表 episode:
  - Episode 82720990 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82720990.json`)
  - Episode 82721968 P0: Shun reward=1 (`downloads/episodes/2026-06-30/82721968.json`)
  - Episode 82722605 P0: Shun reward=-1 (`downloads/episodes/2026-06-30/82722605.json`)
  - Episode 82722639 P0: Shun reward=1 (`downloads/episodes/2026-06-30/82722639.json`)
  - Episode 82723114 P1: Shun reward=1 (`downloads/episodes/2026-06-30/82723114.json`)

### Exact 5: ブリジュラスex鋼

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: ジュラルドン / ブリジュラスex / エースバーン
- 主要トレーナーズ: フルメタルラボ / ポケパッド / ハイパーボール / ポケギア3.0 / 夜のタンカ / 探検家の先導
- 主な使用者: Takaaki Matsuda
- 代表 episode:
  - Episode 82720922 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82721455 P0: Takaaki Matsuda reward=1 (`downloads/episodes/2026-06-30/82721455.json`)
  - Episode 82721970 P1: Takaaki Matsuda reward=1 (`downloads/episodes/2026-06-30/82721970.json`)
  - Episode 82722639 P1: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82722639.json`)
  - Episode 82723127 P0: Takaaki Matsuda reward=-1 (`downloads/episodes/2026-06-30/82723127.json`)

### Exact 6: メガガルーラex多色

- 出現数: 9
- 勝敗: 5勝 4敗
- 勝率: 55.6%
- Wilson下限: 26.7%
- 主軸ポケモン: メガガルーラex / ニャースex / リーリエのピッピex / ラティアスex / キチキギスex
- 主要トレーナーズ: アカマツ / ダークボール / ハイパーボール / ゼロの大空洞 / ボスの指令 / ワンダーパッチ
- 主な使用者: zoroark190
- 代表 episode:
  - Episode 82720918 P0: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82720918.json`)
  - Episode 82721427 P1: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721427.json`)
  - Episode 82721949 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82721949.json`)
  - Episode 82722610 P0: zoroark190 reward=-1 (`downloads/episodes/2026-06-30/82722610.json`)
  - Episode 82723113 P1: zoroark190 reward=1 (`downloads/episodes/2026-06-30/82723113.json`)

### Exact 7: メガスターミーex水

- 出現数: 16
- 勝敗: 5勝 11敗
- 勝率: 31.2%
- Wilson下限: 14.2%
- 主軸ポケモン: エースバーン / ヒトデマン / メガスターミーex
- 主要トレーナーズ: なかよしポフィン / クラッシュハンマー / ポケギア3.0 / メガシグナル / セイジ / リーリエの決心
- 主な使用者: Yushin Ito, Banjo, keidroid, ysakuragi
- 代表 episode:
  - Episode 82720905 P0: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82720905.json`)
  - Episode 82720920 P0: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82721340 P0: Banjo reward=-1 (`downloads/episodes/2026-06-30/82721340.json`)
  - Episode 82721442 P1: Yushin Ito reward=-1 (`downloads/episodes/2026-06-30/82721442.json`)
  - Episode 82721451 P1: Yushin Ito reward=1 (`downloads/episodes/2026-06-30/82721451.json`)

### Exact 8: フーディン超

- 出現数: 5
- 勝敗: 2勝 3敗
- 勝率: 40.0%
- Wilson下限: 11.8%
- 主軸ポケモン: ノコッチ / ケーシィ / ユンゲラー / フーディン / ノココッチ
- 主要トレーナーズ: ふしぎなアメ / 改造ハンマー / なかよしポフィン / ポケパッド / トウコ / ヒカリ
- 主な使用者: aidy, kami, pompom555
- 代表 episode:
  - Episode 82720920 P1: aidy reward=-1 (`downloads/episodes/2026-06-30/82720920.json`)
  - Episode 82720922 P1: aidy reward=1 (`downloads/episodes/2026-06-30/82720922.json`)
  - Episode 82721496 P1: kami reward=-1 (`downloads/episodes/2026-06-30/82721496.json`)
  - Episode 82721963 P1: pompom555 reward=1 (`downloads/episodes/2026-06-30/82721963.json`)
  - Episode 82723946 P0: kami reward=-1 (`downloads/episodes/2026-06-30/82723946.json`)

## 相性候補

- ブリジュラスex鋼 vs メガスターミーex水: 12/16勝、勝率75.0%、Wilson下限50.5%
- メガガルーラex多色 vs ブリジュラスex鋼: 3/3勝、勝率100.0%、Wilson下限43.8%
- メガスターミーex水 vs フーディン超: 3/4勝、勝率75.0%、Wilson下限30.1%
- フーディン超 vs ブリジュラスex鋼: 4/6勝、勝率66.7%、Wilson下限30.0%
- フーディン超 vs メガガルーラex多色: 2/3勝、勝率66.7%、Wilson下限20.8%
- メガスターミーex水 vs ブリジュラスex鋼: 4/16勝、勝率25.0%、Wilson下限10.2%
- ブリジュラスex鋼 vs フーディン超: 2/6勝、勝率33.3%、Wilson下限9.7%
- メガガルーラex多色 vs フーディン超: 1/3勝、勝率33.3%、Wilson下限6.1%
- フーディン超 vs メガスターミーex水: 1/4勝、勝率25.0%、Wilson下限4.6%
- ブリジュラスex鋼 vs メガガルーラex多色: 0/3勝、勝率0.0%、Wilson下限0.0%
