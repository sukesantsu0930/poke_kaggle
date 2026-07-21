# チャンデラ ルール版チャンピオン（保全）

**これは「完全に別物」として永久保存する資産である**（ユーザー決定 2026-07-20）。
学習（BC/PPO）系列とは切り離し、上書き・改変・置換を一切しない。

## 何か

- `chandelure_rb_RULES__chandelure_top.zip` — 純ルール版チャンデラ（**ネット非搭載**。
  zip 内に `.npz` は無く `policy_net.py`（モジュール）のみ = 残差ネット不在でルール argmax 動作）。
  build 元 = `agents/chandelure_rb`（学習 npz 未配置の状態）+ `decks/fleet/chandelure_top.csv`。
  validate_episode 合格（2026-07-20）。

## なぜ

チャンデラは LB に現用者が居ない「我々特有のデッキ」（教師0件のため学習トラック外）。
**実ラダー 997.5 = 全提出資産の最高値**（submissionId 54453456 系統のルール実装）。
頑健化第4陣（EXP-033）で学習版チャンデラも作ったが、これは実験であって、
ルール版チャンピオンを脅かしてはならない。

## 規律

- 学習版チャンデラは `build/ppo_robust2/chandelure/ema.npz` に**隔離**。
  L2/L4 のゲートを通過し、かつルール版 997.5 を明確に上回った場合に**限り**
  `agents/chandelure_rb/policy_net.npz` への配置を検討する。それ以外では配置しない。
- ルール版に戻したいときは、この zip をそのまま提出すればよい（再現可能な保全物）。
- 関連の初期保全: `submissions/2026-07-0{7,8}/chandelure_rb__chandelure_top.zip`（922 期）。
