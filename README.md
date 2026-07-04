# PTCG Kaggle作業場

ポケモンカードAI Battle Challenge用の作業場です。

## まず見る場所

- 実行入口: `run/README.md`
- 共同作業ルール: `docs/collaboration/COLLABORATION_GUIDE.md`
- 安福・長谷川向け案内: `docs/collaboration/安福_長谷川向け.md`
- 作業日記: `docs/planning/PROJECT_DIARY.md`

## 主要ディレクトリ

- `run/`: ダブルクリックで使う `.bat`
- `agents/`: Agent単体
- `decks/`: デッキCSV単体
- `proposals/`: デッキ + Agent + 評価プロトコルの束
- `scripts/`: 実装担当向けPythonスクリプト
- `research/`: 調査、外部メタ分析、カード/ルール研究
- `experiments/`: 実験結果
- `docs/`: 人間向け説明、計画、公式資料

## よく使う `.bat`

通常作業:

- `run/01_setup/カード画像生成.bat`
- `run/02_deck/デッキコード登録.bat`
- `run/02_deck/デッキ可視化.bat`
- `run/03_play/GUI起動.bat`
- `run/04_evaluate/提案評価全部.bat`
- `run/06_submit/提出.bat`

外部メタ分析:

- `run/05_meta/外部メタ分析全部.bat`
- `run/05_meta/外部メタ分析テスト.bat`

## 提案評価

デッキ、対応Agent、評価プロトコルは `proposals/` に束ねます。

```powershell
uv run python scripts\run_proposal.py --proposal proposals\dragapult_ex
```

出力:

```text
experiments\proposals\
```

## 注意

- `API.txt` は認証情報なので共有しない
- `downloads/`, `models/`, `submissions/`, `build/`, `experiments/proposals/` は生成物なので基本的にGit管理しない
- 初心者メンバーはGitHub Desktopで最新版を取り、公式サイトでデッキを作る
- デッキコードを `run/02_deck/デッキコード登録.bat` に入れて、`OK` ならGUIで試す

