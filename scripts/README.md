# scripts の見方

普段使いは `run/` の `.bat` から行います。ここは実装担当や助友が直接コマンドで確認するときの置き場です。

## デッキ

- `import_deck_code.py`: 公式サイトのデッキコードをCSVへ変換
- `check_decks.py`: デッキCSVの形式確認
- `deck_validation.py`: デッキ検証の共通処理
- `render_deck_html.py`: デッキCSVを画像付きHTMLに変換

## Agent / 評価

- `batch_evaluate.py`: 既存のランダム相手評価
- `evaluate_submission.py`: 提出形式の評価
- `solo_evaluate.py`: 一人回し評価。相手はなるべくドローして番を返す
- `run_proposal.py`: `proposals/` のデッキ+Agent+評価をまとめて実行
- `action_abstraction.py`: 行動選択の補助

## 外部メタ分析

- `run_episode_analysis_protocol.py`: 公開episode分析パイプラインの入口
- `download_episode_sample.py`: 公開episode取得
- `extract_episode_visualizer_json.py`: episodeからVisualizer JSONを抽出
- `analyze_episode_decks.py`: episode内デッキの解析
- `rank_episode_deck_winrates.py`: 勝率候補の集計
- `build_candidate_decks_from_episodes.py`: exact 60枚候補のCSV化

## GUI / 可視化

- `manual_play_server.py`: 手動対戦GUI
- `export_visualizer_json.py`: 対戦リプレイJSON作成
- `visualizer_workflow_server.py`: リプレイJSON作成と公式Visualizer導線
- `submission_workflow_server.py`: 提出zip作成GUI
- `extract_card_images.py`: カード画像生成

## 提出

- `build_submission.py`: Kaggle提出zipの中身作成
- `prepare_submission.py`: 提出前処理
- `docker_gpu_check.py`: Docker/GPU確認

## メモ

- `download_kaggle_data.md`: Kaggleデータ取得メモ
