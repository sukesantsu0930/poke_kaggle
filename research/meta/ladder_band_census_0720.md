# 登坂帯（レート600-900）ラダー実測センサス — 2026-07-20

目的: プールの相手分布を実ラダーの登坂帯（600-900）に合わせる。現行フィールド
`research/meta/2026-07-14_field.csv` は上位メタのシェア加重（alakazam 40% 等）だが、
登坂帯の実際の対戦相手分布は別物であり、この乖離がプール学習のラダー転移失敗
（L2↔L4 逆転）の主因仮説。本センサスはその実測データ。

## 方法

- 対象: `downloads/episodes/2026-07-16` と `2026-07-17` の全 1,000 エピソード
  （= 2,000 プレイヤー側。デッキ抽出失敗 0）。
- デッキ抽出: 各エピソード JSON の `visualize.action`（両者の 60 枚 ID リスト。
  `scripts/analyze_episode_decks.py` と同じ方式）。
- LB スコア: `downloads/leaderboard/pokemon-tcg-ai-battle-publicleaderboard-2026-07-18T05_46_25.csv`
  （最新スナップショット）を `scripts/replay_divergence.load_scores` で TeamName → Score に引く。
- アーキタイプ判定: `agents/_base/meta_tables.py` の `ARCHETYPES` とデッキ ID 集合の交差。
  一致 ID 種数が最大のアーキを採用。どれにも当たらなければ `other`。
  - ガード: chandelure は {97, 98, 494}（ヒトモシ系統）が無ければ不成立
    （164=キュワワー単独の誤検出防止）。
  - フィールド粒度の亜種分け: crustle は 756（ガルーラ）有→ `crustle_wall` / 無→ `crustle_prism`。
    starmie は {860, 861}（ユキワラシ/ユキメノコ）有→ `froslass_starmie` / 無→ `megastarmie`。
- 集計スクリプト: scratchpad の census.py（使い捨て。本ファイルが記録の正本）。

## レート帯 × アーキタイプ（プレイヤー側の延べ数）

| archetype | <700 | 700-900 | 900-1100 | 1100+ | unknown | total |
|---|---|---|---|---|---|---|
| alakazam | 0 | 12 | 268 | 355 | 0 | 635 |
| crustle | 0 | 6 | 208 | 204 | 0 | 418 |
| marnie | 0 | 1 | 141 | 142 | 0 | 284 |
| rocket | 0 | 0 | 127 | 104 | 31 | 262 |
| garchomp | 0 | 0 | 2 | 105 | 0 | 107 |
| starmie | 0 | 2 | 76 | 26 | 2 | 106 |
| other | 0 | 10 | 95 | 0 | 0 | 105 |
| dragapult | 0 | 0 | 47 | 0 | 0 | 47 |
| archaludon | 0 | 34 | 0 | 0 | 0 | 34 |
| lucario | 0 | 0 | 2 | 0 | 0 | 2 |
| **TOTAL** | **0** | **65** | **966** | **936** | **33** | **2000** |

- unknown = LB 最新スナップショットに TeamName が無い側
  （lolzpo emonga 31・ysakuragi 2。改名または LB 落ちとみられる）。
- 複数アーキ同時一致（参考）: crustle+kangaskhan 389 / crustle+kangaskhan+rocket 21 /
  archaludon+rocket 13 / crustle+rocket 8 / rocket+starmie 2。いずれも一致 ID 種数
  最大のアーキ（ほぼ crustle）に付けた。

## 600-900 帯の構成（フィールド粒度・N=65 側）

<700 帯は 0 件だったため、600-900 帯 = 上表の 700-900 列と同一。

| subtype | sides | share% | 帯内のチーム（スコア: 出現数） |
|---|---|---|---|
| archaludon | 34 | 52.3 | hatata (835.9): 21 / Canon (828.2): 13 |
| alakazam | 12 | 18.5 | fuga doggo (890.6): 6 / msd0110 (777.7): 6 |
| thwackey_festival (other) | 7 | 10.8 | PP.TAKEHIRO_KAWADA (704.7): 7 |
| crustle_prism | 6 | 9.2 | hukuda222 (887.2): 6 |
| meganium_ogerpon (other) | 3 | 4.6 | Jose Coronel (795.0): 3 |
| froslass_starmie | 2 | 3.1 | taksai (868.6): 2 |
| marnie | 1 | 1.5 | Pokésonic (878.5): 1 |

### 'other' の代表デッキ（600-900 帯・出現数上位。exact 60枚署名で 2 種のみ）

1. **thwackey_festival**（7 側、全て同一リスト）→ `decks/opponents/band_thwackey_festival_0720.csv`
   - サルノリ4 / バチンキー4 / カミッチュ4 / セレビィ4 / カジッチュ4(42×2+92×2) /
     お祭り会場4 / なかよしポフィン4 / むしとりセット4 / ポケパッド4 / リーリエの決心4 /
     トウコ3 / ブレイブバングル2 / 草エネ8 ほか
2. **meganium_ogerpon**（3 側、全て同一リスト）→ `decks/opponents/band_meganium_ogerpon_0720.csv`
   - オーガポン みどりのめんex4 / チコリータ2 / ベイリーフ2 / メガニウム2 / カミツオロチex2 /
     ニャースex2 / カジッチュ2 / カミッチュ2 / 活力の森4 / リーリエの決心4 / むしとりセット4 /
     ハイパーボール4 / ポケパッド3 / 草エネ13 ほか

## 成果物

- `research/meta/2026-07-20_ladderband_field.csv` — 600-900 帯実測 share のフィールド定義
  （`scripts/gauntlet.py read_field` 互換。既存アーキは 07-14 フィールドの相手役定義を流用、
  'other' 2 種は上記の帯実測リストを generic 相手役で追加）。
- `research/meta/2026-07-20_uniform_field.csv` — 同じ 7 行構成で share を均等
  （100/7 = 14.2857）にした maximin 評価用。
- `decks/opponents/band_thwackey_festival_0720.csv` / `band_meganium_ogerpon_0720.csv`。

## 07-14 フィールドとの対比（乖離の中身）

| | 07-14（上位メタ加重） | 07-20 登坂帯実測 |
|---|---|---|
| alakazam | 40.0 | 18.5 |
| crustle（wall+prism） | 20.0 | 9.2（prism のみ） |
| marnie | 10.0 | 1.5 |
| archaludon | 2.0 | **52.3** |
| garchomp / chandelure / rocket / dragapult / megastarmie | 計 22.0 | 0 |
| 草系ロースコアデッキ（thwackey_festival + meganium_ogerpon） | 0 | 15.4 |

登坂帯は archaludon が過半、上位常連の garchomp / rocket / dragapult は不在、
LB 圏外の草系デッキが 15% を占める。上位メタ加重フィールドとは明確に別物。

## 注意（サンプルの限界）

- 600-900 帯は N=65 側・**実 9 チーム**のみ。特に archaludon 52.3% は 2 チーム
  （hatata / Canon）の出現数で決まっており、帯の「アーキ分布」というより
  「この 2 日間にこの帯で潜っていた面子」の実測。share の 1pt 単位に意味はない。
- エピソード集合（07-16/17 の 1,000 試合）自体がダウンロード時の選別を経ており、
  帯の無作為抽出ではない。<700 帯が 0 件なのもこのため（600 台のチームの試合が
  たまたま含まれていないだけで、存在しない証拠ではない）。
- スコアは 07-18 スナップショット時点の値であり、試合時点のレートではない。
- 頑健性が欲しい評価には uniform 版（maximin）を併用すること
  （メモリ: pool-fit-is-advisory — プール制圧度は参考値）。
