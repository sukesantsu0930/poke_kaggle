# research/external — 外部公開資産の取り込み場所

取り込み日: 2026-07-06

このディレクトリは Git 管理外（`.gitignore` 済み）。中身は下記コマンドで再取得できる。

## 1. ptcg-abc（GitHub 完全公開のラダーエージェント一式）

```powershell
git clone --depth 1 https://github.com/wmh/ptcg-abc research\external\ptcg-abc
```

台湾の参加者による**完成品レベルの公開実装**。ルールベースエージェント複数 + メタ分析 + 評価ツール一式。

### まず読むべきファイル

| ファイル | 内容 |
|---|---|
| `CLAUDE.md` | **最重要**。開発ログ・教訓集（6/25時点）。メタ変遷、Elo実績、失敗と対策が全部書いてある |
| `README.md` | リポジトリ概要（内容はCLAUDE.mdより古い） |
| `agents/_base/policy_base.py` | 共有 `BasePolicy`(ABC)。エネルギー過剰付与を構造的に防ぐ energy discipline、`PrizeTracker`、絶対にクラッシュしない `agent()` ラッパー |
| `agents/megastarmie/main.py` | BasePolicy サブクラスの参照実装（ラダー1位 keidroid のクローン、Elo 871 到達）|
| `tools/divergence_decode.py` | **上位プレイヤーのエピソードを自エージェントでリプレイし、不一致をカード名/技名で出す** → 具体的なピロット改善ルールを導く要のツール |
| `tools/check_agent.py` | エージェント不変条件チェッカー（過剰エネ付与・フォールバック率・違法手） |
| `tools/meta_analyze.py` | エピソードzip → アーキタイプ分布 + 勝率 + 相性マトリクス |
| `tools/autopsy.py` | 日次パイプライン（エピソードDL→メタ分析→divergence） |
| `tools/cabt_eval.py` / `cabt_ab.py` / `cabt_gauntlet.py` | 公式 cabt 環境での評価 / A/B / メタ加重ガントレット |

### このリポジトリの主要な教訓（CLAUDE.md より）

1. **デッキ選択が支配的、かつメタは1日で反転する**（Lucario 56%→3日で絶滅）。日次でエピソード分析を回すこと。
2. **ローカル評価（ctypes も cabt も）はラダー順位を正しく予測しない**。cabt は回帰検知用の物差しであり戦略の審判ではない。実ラダー A/B が唯一の審判。
3. **cabt 40試合は ±10pt ブレる。結論は80試合以上で。**
4. 公式サンプル流の「カード毎の完全ポリシー」が from-scratch ポリシーに 13-1 で勝った。ただし **divergence mining（上位ピロットとの不一致を測って直す）を回せば from-scratch も上位級に届く**。
5. **スコアを勘で上げない**。全変更を divergence データで検証（EVOLVE スコアを勘で上げて2提出を無駄にした失敗例あり）。
6. 先攻/後攻・マリガン判断は**デッキ固有**。上位ピロットのデータから読む。
7. スプレッド/スナイプは**相手の低HPエンジン駒**（ドロー要員・進化元）を狙う。高HPの壁ではない。
8. 共通ロジックはコピペせず共有基盤に（コピペしたデッキ間でバグが再発した反省から BasePolicy 化）。
9. エピソード zip は展開せず Python `zipfile` で直接処理（展開すると21GB）。`steps[t+1]` が `obs[t]` への答え（off-by-one）。

## 2. kaggle_notebooks（コンペ公開 Notebook 15本）

```powershell
# 例: uv run python -m kaggle kernels pull <ref> -p research\external\kaggle_notebooks\<name>
```

取得済み（詳細は `kaggle_notebooks/SURVEY.md`）:

**強いエージェント実装:**
- `rule-based-not-psychic-alakazam-best-5th` — **最高5位到達のルールベース Alakazam（7/5更新）**
- `strong-start-baseline-agent-v10-lb-950` — LB950+ の汎用ベースライン
- `multiply-agent-best-940-lb` — LB940
- `a-sample-archaludon-75-wr-vs-my-1300-starmie` — 1300+ Starmie 作者による Archaludon サンプル

**テクニック:**
- `prize-card-tracking-1300-starmie` — サイド落ち推定（ptcg-abc の PrizeTracker の出典）
- `card2vec-learning-dense-card-embeddings` — カード埋め込み学習
- `pok-mon-tcg-deck-transformer-training` — デッキ Transformer（ML系）
- `ptcg-tiny-rl-to-submission-baseline-guide` — 小型RL→提出の導線

**公式サンプル（kiyotah）:**
- `a-sample-rule-based-agent-{mega-lucario-ex,dragapult-ex,iono-s,mega-abomasnow-ex}-deck`
- `reinforcement-learning-and-mcts-sample-code`

**分析系:**
- `simple-baseline-matchup-tests`、`pok-mon-tcg-ai-battle-meta-snapshot-04-july`

## 3. ライセンス注意

ptcg-abc にライセンスファイルは無い（＝デフォルトで all rights reserved）。**コードの直接コピーは避け、設計・知見の参考にとどめる**。Kaggle Notebook は大半が Apache 2.0（各 Notebook のメタデータを確認）。公式サンプル（kiyotah）は流用可。
