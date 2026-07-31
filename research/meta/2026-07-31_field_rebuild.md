# ローカル評価フィールドの再構築と LB 較正の試み — 2026-07-31

動機: LB が伸びない（ローカルは改善報告を続けているのに、実 LB は横ばい〜悪化）。
ユーザー指示で「場の修正を先、その後に学習型（marnie）」。本書は Phase 1（場の修正）の記録。

## 1. 原因の実証 — メタが激変し、評価フィールドが実メタの真逆になっていた

9日分（07-22〜07-30、各250試合＝計2250試合・4500プレイヤー側）を新規取得し、
`scripts/ladder_band_census.py` で「レート帯 × アーキタイプ」を実測（LBスナップショット
`2026-07-31T04_00_09`、6012チーム）。正本: `research/meta/2026-07-31_ladder_band_census.md`。

**全帯の実測分布（延べ4500側）**: marnie 2381（53%）/ alakazam 645 / rocket 497 /
crustle_wall 325 / garchomp 226 / kangaskhan 138 / other 136 / dragapult 112 /
froslass_starmie 29 / crustle_prism 7 / megastarmie 3 / **archaludon 1**。

**07-20 → 07-31 のメタ変化**（登坂帯 600-900）:

| | 07-20 登坂帯 | 07-31 登坂帯(700-900, N=244) |
|---|---|---|
| archaludon | **52.3** | 0.4（4500中1回＝消滅） |
| marnie | 1.5 | **54.5** |
| garchomp | 0 | 14.3 |
| rocket | 0 | 13.5 |
| 草(thwackey等) | 15.4 | ~4（"other"の一部） |
| alakazam | 18.5 | 0（この帯では上位に不在、900+で19%） |

**現行の評価フィールド `2026-07-27_uniform_frozen.csv`**（archaludon 14% / alakazam 14% /
thwackey 14% / crustle_prism 14% / meganium 14% / froslass 14% / marnie 14%）は、
実メタのほぼ**真逆**だった:
- archaludon を 14% 重み付け → 実際は ~0%。
- 草(thwackey+meganium)を 28% → 実際は "other" の一部で数%。
- crustle は prism 14% → 実際は **wall** が主流（prism は 0.2%）。
- froslass_starmie 14% → 実際 0.5%。
- **marnie を 14%** → 実際は **53%**。
- garchomp / rocket / dragapult / kangaskhan は**フィールドに存在しない**。

→ 「弱い自作プールに勝つルールを積む＝実メタと無関係な最適化＝LB劣化」。これが
chandelure 997→669、marnie 914→590 の単調悪化の構造的原因（L2↔L4 乖離の主因）。

## 2. 新フィールド（成果物）

登坂帯+中位帯（700-1100＝新規提出が通過する帯、N=2826）のブレンドでシェアを算出。
相手ピロットは可能な限り**実エージェント**に差し替え（旧来の generic 4枠を底上げ）。

- `research/meta/2026-07-31_field.csv`（実測シェア）:
  marnie 54.7 / alakazam 17.9 / garchomp 7.9 / crustle_wall 7.2 / rocket 5.6 /
  other_megamimirop 4.8 / dragapult 1.8。相手 = agents/{marnie_munkidori,alakazam,
  cynthia_garchomp,crustle,rocket,dragapult}_rb（6枠が実エージェント）+ メガミミロップ
  のみ generic（`decks/opponents/band_megamimirop_0731.csv`、900-1100帯で勝率60%の実ローグ）。
- `research/meta/2026-07-31_uniform.csv`（同7アーキ均等 = maximin 評価用）。

marnie を対象に評価する際は `--exclude marnie`（ミラー除外）で、残り6アーキが実効フィールド。

## 3. LB 較正の試み（Phase 1-4）と、その否定的だが重要な結論

現行HEAD 8エージェントを新旧フィールドで gauntlet（40戦/枠）→ 制圧度と LB の Spearman 相関:
- 新フィールド `2026-07-31_field.csv`: **rho = +0.01**（n=8）
- 均等 `2026-07-31_uniform.csv`: rho = -0.01
- 旧 `2026-07-27_uniform_frozen.csv`: rho = -0.11（n=4）

**どのフィールドでも相関ゼロ**。エージェント別（制圧度 vs LB）:

| agent | LB | 新フィールド制圧度 |
|---|---|---|
| chandelure_rb | 674 | **71.4**（最高なのにLB中位） |
| cynthia_garchomp_rb | 711 | 61.8 |
| dragapult_dusknoir_rb | 737 | 54.7 |
| crustle_rb | 596 | 54.0 |
| dragapult_rb | 656 | 53.8 |
| marnie_munkidori_rb | **779** | 52.2（LB最高なのに制圧度低） |
| rocket_rb | 698 | 51.6 |
| alakazam_rb | 674 | 42.8 |

**結論（3層）**:
1. **per-agent LB は較正の物差しにならない**。LB の帰無ノイズ ±50〜70点に対し、8点が
   ~180点幅に密集。加えてルール改変で「現行HEADコード ≠ その LB を出した時のコード」。
   ノイズと版ズレで相関は原理的に出ない。→ 場の妥当性は **census 代表性**で担保する
   （per-agent LB 相関では担保できない）のが正しい。
2. **シェア修正は必要だが不十分**。chandelure が新フィールドでも 71%（最高）なのに
   LB 674 という逆転が残る。原因は相手の**操縦強度**: 相手が全てルールベースだと
   chandelure のミル(LO)を実人間ほど捌けず、局所で過大評価される。
3. → **相手ピロットを人間強度に近づける必要**がある。これは Phase 2 の学習型
   （BC＝人間模倣の相手役）が場の質も上げる、という二重の動機になる。
   模倣正則化つき PPO の相手プールに BC エージェントを混ぜる方向（正典 §4' の
   プール多様化）が、シェア修正の次の一手。

## 4. 再現手順

```bash
# 1) データ更新（直URL・認証不要・並列）
#    downloads/episodes/<day>/ に 07-22..07-30 を各250件
#    最新LB: kaggle competitions leaderboard download → downloads/leaderboard/
# 2) センサス
uv run python scripts/ladder_band_census.py --days 2026-07-22 ... 2026-07-30 \
   --lb-csv <最新snapshot> --band-edges 700,900,1100 \
   --out research/meta/2026-07-31_ladder_band_census.md \
   --dump-band 900-1100 --dump-dir decks/opponents/band_900_0731 --dump-top 10
# 3) フィールド gauntlet（例: marnie）
uv run python scripts/gauntlet.py --agent agents/marnie_munkidori_rb \
   --deck decks/fleet/marnie_gold_luca_0723.csv \
   --field research/meta/2026-07-31_field.csv --exclude marnie --games 320
# 4) LB 相関（診断・厳密較正には使えないと判明）
uv run python scripts/lb_field_correlation.py --results research/eval/corr_new_0731.csv \
   --lb research/meta/2026-07-31_agent_lb_pairing.csv --fields research/meta/2026-07-31_field.csv
```

新規スクリプト: `scripts/lb_field_correlation.py`（制圧度↔LB の Spearman）。
`scripts/ladder_band_census.py` は既存を流用（07-23作成）。
