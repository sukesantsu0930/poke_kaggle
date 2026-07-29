# デッキ置き場

コンパイル済みデッキCSV（60行・1行=カードID）の置き場です。**役割ごとにフォルダを分けます**（2026-07-14 再編）。

```text
decks/
  fleet/        自艦隊 — エージェントに対応する現用デッキ（提出・gauntlet 対象）
  opponents/    ガントレット相手専用 — GenericPolicy が操縦する小粒デッキ（small_*）
  candidates/   候補 — 採掘・取込したが役割未確定のデッキの一時置き場
  archive/      旧・未使用 — 参照されなくなったデッキ（履歴として保持）
  local/        GUI取込の生置き場（Git管理外。run\02_deck\デッキコード登録.bat の出力先）
  manifest.json デッキ→担当エージェントの対応表（GUIの絞り込みが読む）
```

## 運用ルール

1. **fleet に入れるのは「エージェントとペアで使う」デッキだけ**。入れたら
   `manifest.json` に対応エージェントを1行追記する（可視化GUIの絞り込みに反映される）。
2. 新しいデッキの流入経路は2つ:
   - 友人のデッキコード → `run\02_deck\デッキコード登録.bat` → `local/` → 採用なら `fleet/` へ
   - エピソード採掘（`scripts/build_candidate_decks_from_episodes.py`）→ `candidates/` → 分類
3. gauntlet のフィールド定義（`research/meta/2026-07-08_field.csv`）が参照するのは
   `fleet/`（tuned 相手）と `opponents/`（generic 相手）。パスを動かしたら field.csv も更新する。
4. 使わなくなったデッキは削除せず `archive/` へ（過去の実験ログのパスは書き換えない）。

## 現在の対応（詳細は manifest.json）

| デッキ | エージェント |
|---|---|
| fleet/dragapult_dusknoir_paper.csv | dragapult_dusknoir_rb（9体目・開発中） |
| fleet/popular_4_dragapult.csv | dragapult_rb |
| fleet/marnie_gold_luca_0723.csv | marnie_munkidori_rb（**金圏正本**。Luca 1位 + GUOHAOYANG 6位が完全同一の60枚） |
| fleet/marnie_mainstream_0718.csv | marnie_munkidori_rb（07-18 主流形。金圏正本と2枠差。A/B の対抗腕） |
| fleet/alakazam_top_0710.csv | alakazam_rb（現行提出リスト。5th は旧） |
| fleet/alakazam_5th.csv | alakazam_rb（旧リスト） |
| fleet/chandelure_top.csv | chandelure_rb |
| fleet/cynthia_garchomp_top.csv | cynthia_garchomp_rb |
| fleet/mega_kangaskhan_top.csv | mega_kangaskhan_rb |
| fleet/archaludon_cityleague.csv | archaludon_rb |
| fleet/froslass_starmie_taksai.csv | froslass_starmie_rb |
| opponents/small_*.csv（5種） | （GenericPolicy 操縦・gauntlet 専用） |

友人メンバーはCSVを直接編集しません。公式サイトのデッキコードを `run\02_deck\デッキコード登録.bat` に入れてください。
