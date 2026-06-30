# Git最低限

初心者メンバー向けの最低限のGit手順です。

## 最初に一度だけ

GitHub Desktopを使う場合は、GitHub DesktopでリポジトリをCloneしてください。

コマンドでやる場合:

```bash
git clone <repo-url>
cd poke_kaggle
```

## 毎回、作業前にやる

```bash
git pull
```

## 作業する

基本的には以下だけ編集します。

- `decks/`
- `research/`

## 変更を確認する

```bash
git status
```

## 保存して共有する

```bash
git add decks research
git commit -m "add research note"
git push
```

## 注意

- `API.txt` は触らない、共有しない
- `models/` や `downloads/` は基本的に共有しない
- 既存ファイルを大きく書き換えるより、自分の新しいメモファイルを作る
- 分からなくなったら `git status` の結果を実装担当に送る
