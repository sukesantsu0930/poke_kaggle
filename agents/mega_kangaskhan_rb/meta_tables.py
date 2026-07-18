"""メタデータテーブル — 相手アーキタイプ検出と相手モデリングの入力データ。

正本は agents/_base/meta_tables.py。各エージェントdirへのコピーは scripts/sync_base.py で
同期する（直接編集禁止）。コード(policy_base.py)と更新周期が違うためファイルを分離している。
エピソード分析でメタが動いたら、このファイルだけ更新して再同期する。

出所と更新日:
  - 2026-07-06 初版。値は Kaggle 公開 Notebook "A Sample Archaludon"(Apache-2.0系譜) の
    6月メタ実測値。ルール抽出_オープン実装.md の R-08/R-20 の入力。
  - TODO: 7月メタ（Marnie/Munkidori 17.8%/60%, Alakazam 25.7%, Starmie 復調）向けの
    打点・アーキタイプ更新をエピソード分析から行う。
"""

# ── R-20: アーキタイプ検出（相手の場のカードID集合と交差判定） ──
ARCHETYPES = {
    "crustle": {344, 345, 532},
    "hop": {288, 289, 299, 304, 307, 308, 309, 310, 878, 879},
    "starmie": {1030, 1031},
    "lucario": {677, 678},
    "alakazam": {741, 742, 743},
    # 2026-07-07 追加（7月メタ。値の出所は各 デッキ設計_*.md）
    "marnie": {646, 647, 648},
    # chandelure(LO): たねで早期検出する（2026-07-13 ユーザー指示）。97=ヒトモシ・
    # 164=キュワワー(Flower Shower お互い3ドロー=ミル始動)が序盤の tell。98=シャンデラ
    # (2進化)まで待つと LO 検出が遅れ、R-28 の圧縮停止が手遅れになる。494=ランプラー
    "chandelure": {97, 98, 164, 494},
    "garchomp": {379, 380, 381},
    "kangaskhan": {756},
    "dragapult": {119, 120, 121},
    "archaludon": {169, 190},
    # 2026-07-17 追加（デッキ設計_ロケット団.md）。OPP_MAX_DAMAGE / OPP_BOSS_COUNTS は
    # 意図的に未追加 = generic 値へフォールバック = 既存艦隊の挙動不変（P-12 非該当）。
    "rocket": {400, 401, 414, 431, 434},
}

# ── R-08 入力: マッチアップ別の相手最大打点（次ターン被リーサル判定用） ──
# 可変打点の相手は OPP_DAMAGE_ESTIMATORS が優先される。
OPP_MAX_DAMAGE = {
    "crustle": 120,
    "hop": 220,
    "lucario": 270,   # Mega Brave 基準。PPP で+30ずつ乗るが予測不能のため据え置き
    "starmie": 210,
    "generic": 220,
    # 2026-07-07 追加
    "marnie": 210,        # Shadow Bullet 180 + ベンチ30
    "chandelure": 40,     # 実質脅威は打点でなくミル
    "garchomp": 320,      # Draconic Buster 260 + ロズレイド2体分
    "kangaskhan": 250,    # Rapid-Fire Combo 期待値
    "dragapult": 200,     # Phantom Dive 本体（ベンチ60は別枠）
    "archaludon": 220,    # Metal Defender
}

# ── R-08 緩和条件: アーキタイプ既知のボスの指令採用枚数 ──
# 相手トラッシュの使用済み枚数がこれspecに達したらボス想定を解除する。
# 未知は保守的に4（最大採用数）。
OPP_BOSS_COUNTS = {
    "generic": 4,
    "alakazam": 2,   # 5位実装のリスト実測（ボス×2）。R-08 緩和がその分早く効く
    # 2026-07-07 追加
    "marnie": 0,       # winrate_2 リストはボス不採用（呼び出しは Shadow Bullet 30 で代替）
    "chandelure": 3,
    "garchomp": 2,
    "kangaskhan": 2,
    "dragapult": 3,
    "archaludon": 4,
}

# ── ex/megaEx からのダメージを無効化するアクティブ（リーサル誤検出ガード） ──
# 345=Crustle。158/207/330 は ptcg-abc が記録した同種の免疫持ち（設計参照からのID引用）。
IMMUNE_TO_EX_ACTIVE = {345, 158, 207, 330}

# ── R-11 入力: カード毎のドロー/山札消費枚数（山札切れガードの閾値） ──
# デッキ実装のサイクルで実カードを追加していく（5位Alakazam Notebook 由来の設計）。
DRAW_CONSUMPTION = {}

# ── R-26/R-28 入力: ドロー系カードの分類（2026-07-13 追加。リプレイ 85690212 で
#    手張り権を残したままアンフェアスタンプを打つ一般不具合を確認 → 順序規律を新設） ──

# 手札リフレッシュ: 自分の手札を山へ戻して引き直すカード。
# R-26: 未使用のエネ手張りを済ませてから使う（戻すと手札のエネが山へ消える）。
HAND_REFRESH_IDS = {
    1080,  # アンフェアスタンプ（ACE SPEC: 被KOの返しに自分5枚/相手2枚）
    1227,  # リーリエの決心（手札を山へ戻して6ドロー）
}

# 純ドロー系サポート（手札は戻さない。R-28 の圧縮先行の対象）
DRAW_SUPPORT_IDS = {
    1224,  # チェレン（3ドロー）
    1216,  # ロケット団のアテナ（5枚/全ロケット団なら8枚まで引く。ロケット団デッキ専用ID）
}

# 山札圧縮アイテム（山札から確定サーチして山を薄くするグッズ）。
# R-28: ドロー札より先に使って山の質を上げる。
#   TO_BOARD = 盤面へ直接出る → 手札リフレッシュの前でも無駄にならない
#   TO_HAND  = 手札へ入る → 手札リフレッシュの前に使うと戻されるため、純ドローの前のみ
THIN_TO_BOARD_IDS = {
    1086,  # なかよしポフィン（HP70以下のたね×2をベンチへ）
}
THIN_TO_HAND_IDS = {
    1077,  # ロトムのスティック（山上4枚からサポートを手札へ）
    1119,  # エネルギー転送（基本エネを手札へ）
    1121,  # ハイパーボール（ポケモンを手札へ）
    1122,  # ポケギア3.0（山上7枚からサポートを手札へ）
    1142,  # ファイトゴング（基本{F}エネ or たね{F}ポケモンを手札へ）
    1145,  # メガシグナル（メガシンカexを手札へ）
    1152,  # ポケパッド（非ルールボックスのポケモンを手札へ）
    1094,  # むしとりセット（山上7枚から草ポケ+草エネを手札へ。ロケット団デッキ専用ID）
    1134,  # ロケット団のレシーバー（ロケット団サポートを手札へ。同上）
}

# ── R-28 の停止条件: LO（Library Out / 山札切れ狙い）アーキタイプ ──
# 相手が LO と確認できたら（R-20 detect_matchup）山札圧縮の先行を止める
# （LO 相手では自分の山札=寿命。不要な山消費を増やさない）。
LO_ARCHETYPES = {"chandelure"}

# ── 相手の特殊ID（policy_base と各デッキが共通で参照するもの） ──
BOSS = 1182            # ボスの指令
MEGA_BRAVE = 983       # Mega Brave（使用後1ターン攻撃不可 → R-17 で利用）
HOP_SNORLAX = 304

# ── 可変打点の相手モデル（R-08: floor/ceiling 推定） ──

_ALA_LINE = ARCHETYPES["alakazam"]
_ALA_BOARD_GAIN = {66: 3, 742: 2, 305: 2, 65: 2, 741: 1}  # Dudunsparce, Kadabra, Dunsparce×2, Abra
_ALA_ENRICHING = 13
_ALA_FEZ = 140


def estimate_alakazam(opp, pokes):
    """(floor, ceiling, ceiling_with_boss) — Powerful Hand の打点推定。
    opp: 相手 PlayerState, pokes: 対象に含める相手ポケモンのリスト。"""
    ids = [p.id for p in pokes if p]
    if not (_ALA_LINE & set(ids)):
        return 0, 0, 0
    base = opp.handCount + 1
    gain = sum(_ALA_BOARD_GAIN.get(i, 0) for i in ids)
    enriching_seen = (
        any(c and c.id == _ALA_ENRICHING for c in (opp.discard or []))
        or any(c and c.id == _ALA_ENRICHING
               for p in pokes if p
               for c in (getattr(p, "energyCards", None) or []))
    )
    if not enriching_seen:
        gain += 3
    if any(i == _ALA_FEZ for i in ids):
        gain += 3
    return base * 20, (base + gain + 2) * 20, (base + gain - 1) * 20


def _alakazam_ceiling(obs, opp):
    pokes = ([opp.active[0]] if opp.active else []) + list(opp.bench or [])
    _, ceiling, _ = estimate_alakazam(opp, pokes)
    return ceiling


# matchup名 → (obs, opp_state) -> 最大打点。OPP_MAX_DAMAGE より優先。
OPP_DAMAGE_ESTIMATORS = {
    "alakazam": _alakazam_ceiling,
}
