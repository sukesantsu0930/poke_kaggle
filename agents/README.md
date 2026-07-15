# エージェント置き場

Kaggle提出形式に対応したエージェントをここに置きます。

## 推奨構成

今後は、エージェントごとにディレクトリを作ります。

```text
agents/
  cubchoo_ogerpon_rb/
    main.py
    README.md
```

Kaggle提出zipの中では、各ディレクトリの `main.py` がルートの `main.py` として使われます。

現在あるエージェント:

- `archaludon_rb/`: ブリジュラス（2026-07-06提出。BasePolicy 移行済み・shadow 100%検証済み）
- `alakazam_rb/`: フーディン（公開5位実装の移植。BasePolicy）
- `marnie_munkidori_rb/`: マリィのオーロンゲ+マシマシラ（フルスクラッチ。BasePolicy）
- `cynthia_garchomp_rb/`: シロナのガブリアスex（フルスクラッチ。BasePolicy。7/6メタ新興・レート1000+帯シェア11.1%）
- `chandelure_rb/`: シャンデラ・コントロール=ミル（7/6メタ レート1000+ 実測77.3%の移植。BasePolicy）
- `dragapult_rb/`: ドラパルトex（公式サンプルの枝刈りDFS配分プランを移植。BasePolicy。旧 dragapult_ex_rb を代替）
- `mega_kangaskhan_rb/`: メガガルーラex（7/6メタ10%の新興。zoroark190リスト。BasePolicy）
- `crustle_rb/`: イワパレス壁ガルーラ（7/14メタ シェア2位ファミリー。懒惰的金枪鱼=系統Bリスト。
  BasePolicy。07-14フィールド制圧度 63.2%+CR1/CR2。設計: デッキ設計_イワパレス.md）
- `cubchoo_ogerpon_rb/`: クマシュン+オーガポンex（旧・自己完結型。2026-07-02提出、Elo 152）
- `dragapult_ex_rb/`: ドラパルトex（旧・自己完結型）
- `rb_001_baseline.py`: 汎用ベースライン（単一ファイル形式、`submission/main.py` と同一内容）
- `ml_agent_template.py`: MLエージェントの雛形（推論部は未実装のスタブ）

## 共有基盤（`_base/`）

新しいデッキは `_base/policy_base.py` の `BasePolicy` を継承して作ります
（設計: `docs/planning/用語とターン手順.md`、ルール一覧: `docs/planning/ルール抽出_オープン実装.md`）。

1. `docs/planning/デッキ設計_<デッキ>.md` を書く（サブゴール/S-x/E-x）
2. `agents/<deck>_rb/main.py` で BasePolicy を継承（必須: judge_subgoal / score_setup / score_combat + クラス属性）
3. `uv run python scripts\sync_base.py` で基盤ファイルを同期
4. `uv run python scripts\check_agent.py --agent agents\<deck>_rb --deck <deck.csv>` で不変条件確認
5. `proposals/<deck>/` を作って `run_proposal.py`、`ab_battle.py` でプール対戦
6. 以後のスコア変更は「変更 → `scripts\eval_battery.py`（L1/L2/L3）→ 採用判定（**L2改善 ∧ L3非悪化**）」を標準とする（正典: `docs/planning/評価方法.md`。L2のみ改善は【暫定】= P-09）

`policy_base.py`/`meta_tables.py` の正本は `_base/` のみ。**各エージェントdir内のコピーは直接編集禁止**
（build_submission がハッシュ照合で古い基盤の提出を弾きます）。

旧・自己完結型の凍結版は `experiments/frozen_agents/`（対戦相手プール資産）。

各エージェントの `main.py` は、提出用 `main.py` としてそのまま使える形にしてください。最低限、次の2つを定義します。

- `read_deck_csv() -> list[int]`
- `agent(obs_dict: dict) -> list[int]`

エージェントとデッキを組み合わせて提出zipを作る例:

```powershell
uv run python scripts\build_submission.py --agent agents\cubchoo_ogerpon_rb --deck decks\archive\winrate_1_cubchoo_ogerpon.csv
```

## デッキ対応Agent

このコンペでは、完全に汎用的なAgentを作るより、デッキのコンセプトに対応したAgentを複数持つ方針にします。

候補例:

- `agents/cubchoo_ogerpon_rb` + `decks/archive/winrate_1_cubchoo_ogerpon.csv`
- `agents/dragapult_ex_rb` + `decks/fleet/popular_4_dragapult.csv`

新しいデッキを追加するときは、対応するAgentか、既存Agentをそのデッキ向けに調整した派生Agentも一緒に用意してください。

機械学習エージェントを作る場合は `ml_agent_template.py` を元に新しいディレクトリを作り、学習済みファイルを `models/` に置いて `--extra` で提出zipに入れます（学習パイプラインは未整備）。

```powershell
uv run python scripts\build_submission.py --agent agents\<ml_agent_dir> --deck decks\my_deck.csv --extra models\policy.pkl=model.pkl
```

提出される `main.py` では、まずカレントディレクトリからファイルを読み、見つからない場合に `/kaggle_simulations/agent/` を読むようにしてください。
