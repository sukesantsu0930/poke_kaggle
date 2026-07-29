"""ドラパルトex（Dragapult ex / Phantom Dive ばら撒き）ルールベースエージェント — 公式サンプル移植

土台: Kaggle 公式サンプル "A Sample Rule-Based Agent (Dragapult ex Deck)"（Apache-2.0 系譜。
research/external/kaggle_notebooks/a-sample-rule-based-agent-dragapult-ex-deck/main_reference.py）。
その方策の核 = `main_option_proc` の配分プラン DFS（「60 で取り切れる相手部分集合」だけを列挙する
枝刈り + prize_count/pokemon_score によるサイドペース採点）を BasePolicy のフックに移植し、
ptcg-abc の divergence 実測修正（Fez 降格 / EVOLVE 据え置き / Dragapult ex への ATTACH 強化）を適用。

設計文書: docs/planning/デッキ設計_ドラパルト.md（S-x/E-x/初期値表/移植ノート）
ルールタグ: R-07(配分プラン込みリーサル)/R-08/R-10(ライン最大コスト)/R-11(no_draw)/
R-15(ばら撒き先)/R-16(ボス温存)/R-18(サイド落ち推定 serial版)/R-21(先攻 div-D1)/R-22(マリガン引く)/
R-30(バトル場が今すぐ撃てるならバトル場優先＝資源節約)
"""

import os
import sys
from collections import defaultdict

# sys.path ブートストラップ（base import より前に必須）
try:
    _ROOT = __file__
except NameError:
    _ROOT = None
_CG_PATH = "/kaggle_simulations/agent"
for _p in ([os.path.dirname(os.path.abspath(_ROOT))] if _ROOT else []) + [_CG_PATH]:
    if _p and _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from cg.api import AreaType, CardType, LogType, OptionType, Pokemon, SelectContext

import meta_tables as mt
from policy_base import (
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    energy_count,
    get_card,
    hand_ids,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    read_deck_csv as _read_deck_csv,
)

# ── カードID（デッキ設計_ドラパルト.md のリスト） ──

DREEPY = 119            # ドラメシヤ HP70
DRAKLOAK = 120          # ドロンチ HP90（Recon Directive: 上2枚見て1枚）
DRAGAPULT_EX = 121      # ドラパルトex HP320（Phantom Dive 200+ベンチ60配分）
FEZANDIPITI_EX = 140    # Flip the Script / Cruel Arrow
LATIAS_EX = 184         # Skyliner（たねのにげる0）
BUDEW = 235             # Itchy Pollen（相手グッズロック）
MEOWTH_EX = 1071        # Last-Ditch Catch（サポートサーチ）
RARE_CANDY = 1079
UNFAIR_STAMP = 1080     # ACE SPEC
POFFIN = 1086
NIGHT_STRETCHER = 1097
CRUSHING_HAMMER = 1120
ULTRA_BALL = 1121
POKE_PAD = 1152
LUCKY_HELMET = 1156
BOSS = mt.BOSS          # 1182
CRISPIN = 1198
BROCK = 1210
LILLIE = 1227
WATCHTOWER = 1256       # ロケット団の監視塔（{C}特性消し）
FIRE_ENERGY = 2
PSYCHIC_ENERGY = 5

ATK_JET_HEADBUTT = 153      # {C} 70
ATK_PHANTOM_DIVE = 154      # {R}{P} 200 + ダメカン6個配分
ATK_ITCHY_POLLEN = 323      # Budew（相手は次の番グッズ不可）

# 相手側の特殊ID（サンプル準拠）
NO_DAMAGE_DEX = frozenset({158, 207, 330, 345})   # Drednaw/Milotic ex/Sylveon/Crustle（ex打点無効）
NO_DAMAGE_COUNTER_IDS = frozenset({28, 199, 203, 207, 362, 1136})  # ダメカン配置不可
GUARD_ENERGY_IDS = frozenset({11, 20})   # Mist / Rock Fighting（装着でダメカン配置不可）
LEGACY_ENERGY = 12
LILLIES_PEARL = 1172
LOW_VALUE_TARGETS = frozenset({173, 174, 190, 1071})  # Noctowl/Fan Rotom/Archaludon ex/Meowth ex
MUNKIDORI = 112
BONUS_COUNTER_TARGETS = frozenset({133, 351})   # Dusknoir/Rapidash（サンプル準拠の優先スナイプ）
LUMIOSE_CITY = 1267
NIGHTTIME_MINE = 1266   # よるのこうざん: 場のテラスタルの攻撃コスト +{C}（アラカザム型）

# アタッカー運用ポケモン（S-7 配分探索用。research/meta/attacker_pokemon.md、
# extract_attacker_pokemon.py が 1761 エピソードから抽出。アタッカー度 = active滞在中に
# ATTACK宣言した試合率、閾値0.5で2値化。HP>120 のみ = 小粒は配分探索でHP判定するため不要）。
# 履歴だけでは Mega Kangaskhan ex(756) が 0.49 で漏れるため、_is_attacker では megaEx 属性を
# 無条件アタッカーとして OR する（メガ進化は定義上メインアタッカー）。
ATTACKER_IDS_LEARNED = frozenset({58, 63, 96, 108, 116, 117, 121, 169, 190, 245, 272,
                                  381, 401, 431, 648, 666, 674, 678, 743, 849, 861, 1031})

DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})

# DRA_CONCENTRATE（2026-07-24 ユーザー指示）: エネ集中の A/B トグル（既定 ON）
DRA_CONCENTRATE = os.environ.get("DRA_CONCENTRATE", "1") != "0"
# DRA_BUDEW_OPEN（2026-07-24 ユーザー指示）: 開幕ムズムズ花粉ロック（既定 ON）
DRA_BUDEW_OPEN = os.environ.get("DRA_BUDEW_OPEN", "1") != "0"

# ═══════ 2026-07-27: カースドボム版（EXP-048）で採用した一般ルールの移植 ═══════
# 対オーロンゲ用に起こしたドクトリンだが、実体は「ファントムダイブ到達を速くする」汎用修正で、
# ボム版では他対面のほうが伸びた（archaludon 27.2→33.1 / froslass 59.1→63.7・均等制圧度 +1.4）。
# 既定は OFF（＝提出物の挙動は不変）。640戦/腕の A/B で確認してから ON に倒す。
# 正典: docs/planning/デッキ設計_ドラパルトヨノワール.md 8b節 / LEDGER EXP-048。
#
# S-0!【ユーザー 2026-07-26・loss1.json 観戦】手番内ダイブ判定を**進化の選択**に繋ぐ。
# 通常版にも同じ穴がある: R-30（48600）が div-D3「ドラメシヤ進化」（58000）に常に負けるため、
# 「バトル場のドロンチを進化させればこの番撃てる」局面でベンチ進化が選ばれていた。
DRA_DIVE_NOW = os.environ.get("DRA_DIVE_NOW", "1") != "0"
# S-0! の判定強度（2026-07-27 ユーザー指摘）。前セッションの結論は「ファントムダイブの
# 可能性がある時点でアグレッシブが得／パッシブは別プロファイルでなく劣化版」（ボム版で
# 全7対面で アグレ≧パッシブ、閾値を単一 DUSK_TH_DIVE=0.0 に統一）。
#   OFF（既定・保守形）= `_dive_now_after_evolve`「**撃てると証明できる経路だけ**」
#   ON（アグレッシブ形）= `_dive_maybe_after_evolve`「**撃てないと証明できるときだけ降りる**」
# 後者が閾値0.0 の忠実な移植。初期移植は前者＝ドクトリンの逆側を実装していた。
DRA_DIVE_AGGRO = os.environ.get("DRA_DIVE_AGGRO", "1") != "0"
# D-1（ユーザー指摘 2026-07-27）: 到達判定を**手書きの経路リストから網羅探索へ**置き換える。
# 旧実装（`_dive_now_after_evolve` / `_dive_maybe_after_evolve`）は4経路の列挙で、
# **夜のタンカのエネ回収・ふしぎなアメ直行・ニャース ex→アカマツ の連鎖が抜けていた**。
# 自分の手番内の行動空間は有限なので、列挙せず探索して決定する（`_dive_reachable`）。
DRA_DIVE_EXACT = os.environ.get("DRA_DIVE_EXACT", "1") != "0"
# D-2: 確定したら最小コスト経路をそのまま執行する（重み付けをやめる・ユーザー指示）
DRA_DIVE_ROUTE = os.environ.get("DRA_DIVE_ROUTE", "1") != "0"
# R-13+【ユーザー 2026-07-26】切る/呼ぶ/打つ順を「この番に即プレイできるか」で統一。
#   ① 切る札 = この番に即プレイできない札（手札評価の高低ではない）
#   ② ハイパーボール自身の優先度 = グッズの最後（切るコストが最小になってから打つ）
#   ③ 呼ぶ札も即プレイできる札に限る（進化先が場に無い2進化は手札で腐る）
DRA_PLAYABLE_NOW = os.environ.get("DRA_PLAYABLE_NOW", "0") != "0"
# ②だけを切り離す細粒度トグル（2026-07-27）。①③（切る札の保護・呼ぶ札の限定）は資源を
# 損しない片側だけの変更なのに対し、②はハイパーボールの**発火条件そのもの**を
# `negative_hand>=2`（価値ゼロ以下が2枚）から「即プレイ不能札が2枚」へ置き換えるため、
# サーチを握り込む方向に効きうる。DRA_PLAYABLE_NOW=1 のとき既定 ON（＝バンドルと同じ）。
DRA_UB_LAST = os.environ.get("DRA_UB_LAST", "1") != "0"
# ふしぎなアメの例外（ユーザー 2026-07-26）: 進化元が場にいて2進化が手札か山にあるなら、
# 「持ってくる札で即プレイ可能になる」ので切らない（R-13+ の中でだけ効く従属トグル）。
DRA_CANDY_HOLD = os.environ.get("DRA_CANDY_HOLD", "0") != "0"
# ルール12+（ユーザー 2026-07-26）: ポフィンは温存しない = R-11（山薄）より上で常に即プレイ。
DRA_POFFIN_ALWAYS = os.environ.get("DRA_POFFIN_ALWAYS", "0") != "0"

# ═══════════ ハイパーボール収支（U-1。ユーザー仕様 2026-07-27） ═══════════
# 打つ判断を**2つのスカラーの比較**に還元する（感覚を排し論理に落とす）:
#   G = 山から持ってくる駒の価値（最良の1枚）
#   C = 手札から**最もリスクの小さい2枚**を選んだときの合計コスト
#   使用条件: **C <= G**
#
# 【論理的必須要件】C を計算するコスト関数と、DISCARD で実際に切る札を選ぶ関数は
# **同一でなければならない**。旧実装は打つ判断が `negative_hand>=2`、切る判断が
# `-hand_score` と割れており、「最もリスクの小さい2枚のコスト」という前提が
# 支払いで保証されていなかった。U-1 では両者が `_ub_discard_cost` を共有する。
#
# 【コストの定義】「即プレイできるか」では測らない（07-27 の失敗の原因＝次ターン以降に
# 効く札を不能札と誤認してボス/アカマツ/アメ/ドラパルト ex を焼いていた）。
#   必要枚数（**この番＋次の番**の2ターン地平線・ユーザー決定） > 失った後の到達可能枚数
#     → コスト = 壊れる計画の価値
#   そうでなければ → コスト 0
# 到達可能枚数 = 手札 + 山 + **夜のタンカで拾える分**（ポケモン/基本エネのみ、
# タンカ枚数が上限。切った札自身もトラッシュに入るので回収対象に含む＝ユーザー決定）。
#
# 【サポートの帰結】2ターン地平線ではサポートは最大2枚しか打てない（この番に未使用なら
# 2枚、使用済みなら次の番の1枚）。よって手札に滞留した3枚目以降のサポートは
# **論理的に余剰**でコスト 0 になる。発火が緩むことと、上位サポート（ボス/アカマツ）が
# 守られることが同じ原理から出る。旧実装が発火率 8% で詰まっていた主因がこれ。
DRA_UB_LEDGER = os.environ.get("DRA_UB_LEDGER", "0") != "0"

# ═══════════ U-2: ハイパーボールの保険則（ユーザー仕様 2026-07-27・簡潔版） ═══════════
# U-1（収支スカラー）は「山にまだ代えがあるなら無料」というコスト定義のせいで、ほぼ全ての
# 札のコストが 0 になり、ゲートが事実上ノーと言わなくなった（コスト超過での保留 0.13回/試合）
# ＝ 焼きすぎに退化して −2.2pt。**山にボスが3枚あることと、必要な番にボスを引けることは別**。
#
# U-2 はこれを「次の番も動けるか」という**保険**の1点に還元する（ユーザー）:
#
#   悪手は「**ドロサポを切って、手札にドロサポが1枚も残らない**」こと。
#
# したがって制約は **支払い側にだけ** かかる。ドロサポを持っていないことは掘らない理由に
# ならない（守るべき札が無いだけ）。※初版はこれを発火条件にしてしまい「保険が無いときほど
# 打てない」という逆立ちしたルールになっていた（ユーザー訂正 2026-07-27）。
#
# 本デッキのドロサポは **リーリエ 1種だけ**（手札を山に戻して6枚引く。タケシ=ポケモン
# サーチ / アカマツ=エネサーチ / ボス=吊り出し はいずれもドロサポではない）。
# 払ってよい札はユーザー列挙の4種:
#   ① ドロサポ以外のサポート  ② 余分なハイパーボール
#   ③ 即プレイできないグッズ  ④ 中盤以降のポフィン
# ＋ ドロサポも**最後の1枚以外は**払ってよい（2枚目のリーリエは普通の支払い原資）。
# 発火条件は「切ってよい札が2枚あるか」だけ。
DRA_UB_INSURANCE = os.environ.get("DRA_UB_INSURANCE", "0") != "0"
# ③の解釈。素の「この番プレイできないグッズ」だと、進化元待ちのふしぎなアメ・回収先待ちの
# 夜のタンカ・詰め用のスタンプまで支払いに回る（実測でアメ 0.43/試合を焼いていた）。これは
# ユーザーが指摘した失敗そのもの（「次ターン以降有効な札を叩き落す」）なので、③を
# **「打てない」ではなく「死んでいる」= 発動条件が今後も来ない** で定義する版。
DRA_UB_DEADITEM = os.environ.get("DRA_UB_DEADITEM", "1") != "0"
DRAW_SUPPORTER_IDS = frozenset({LILLIE})

# ═══════════ U-3: ハイパーボールの3条件（ユーザー仕様 2026-07-27） ═══════════
# ハイパーボールは**自分の山に対するアメリカン・コール**。持っている限り「後で、より多くを
# 知った状態で必要なものへ変換する権利」を保有しており、早く行使するとその分を捨てる。
# 実際 U-2/U-1/R-13+② は「払えるか」だけを3通りに作り直して発火を増やし、全て負けた。
# 行使は次の3条件の**積**で決める:
#
#   ① 需要が今ある      G = この番の行動が変わるか（下記の2軸・ユーザー定義）
#   ② 代替が手札に無い  ポフィン/ポケパッドが**今手札にあって同じ的を取れる**なら不要
#   ③ 支払いが余剰      U-2 の `_ub_pay_rank`（ドロサポの最後の1枚は守る）
#
# 【需要の2軸（ユーザー 2026-07-27）】
#   (a) ファントムダイブが**確定するか、近づくか**
#   (b) **ドロンチにつながるか** — ドロンチがこのデッキのエンジンなので、
#       「ハイパーボールでドロンチ」は意外と正解。進化したてでも同じ番に偵察指令が回る
#       （山の上2枚を見て1枚を手札）ため、**この番のドローが増え、かつ線が1歩進む**。
# 利得は「そのカードの価値」ではなく **早く手に入ることの価値（加速）**。この番に使えない
# 札は、今取っても3ターン後に取っても同じなので加速ゼロ（U-1 はここを取り違えていた）。
DRA_UB_DEMAND = os.environ.get("DRA_UB_DEMAND", "0") != "0"
UB_G_MIN = float(os.environ.get("DRA_UB_G_MIN", "40"))   # 行使の下限（②③の前に効く）

# 価値の単位（G と C は同一スケールに乗せる）
UB_V_CORE = 100    # 勝ち筋そのもの（最後のドラパルト ex、リーサルに要るボス）
UB_V_LINE = 60     # 線の必須パーツ（ドロンチ・アメ・アカマツ・必要エネ）
UB_V_AID = 30      # 計画の補助（ポフィン・パッド・タンカ・余剰サポート筆頭）
UB_V_DEAD = 0      # 死に札（的の尽きたポフィン、盤面が足りている駒）
# 「この番はまだドラパルト化が確定不可能ではない」判定に使う掘り札（ドロー/サーチ手段）。
# 手札にこれらが1枚でもあれば、ドラパルトを引き込む余地がある = エネ分散はまだ許可しない
DIG_OUT_IDS = frozenset({ULTRA_BALL, POKE_PAD, LILLIE, CRISPIN, BROCK, NIGHT_STRETCHER})

# R-10: ライン最大コスト（技の実コストから確認済み: Phantom Dive=2 / Cruel Arrow・Eon Blade・Tuck Tail=3）
LINE_MAX_COST = {DREEPY: 2, DRAKLOAK: 2, DRAGAPULT_EX: 2,
                 FEZANDIPITI_EX: 3, LATIAS_EX: 3, MEOWTH_EX: 3, BUDEW: 0}

UNNECESSARY = -10_000_000

# デッキリスト（popular_4_dragapult.csv と同一。deck.csv 不在時のフォールバック）
DECK_FALLBACK = (
    [DREEPY] * 4 + [DRAKLOAK] * 4 + [DRAGAPULT_EX] * 3
    + [FEZANDIPITI_EX, LATIAS_EX] + [BUDEW] * 2 + [MEOWTH_EX]
    + [RARE_CANDY] * 2 + [UNFAIR_STAMP] + [POFFIN] * 4 + [NIGHT_STRETCHER] * 2
    + [CRUSHING_HAMMER] * 4 + [ULTRA_BALL] * 4 + [POKE_PAD] * 3 + [LUCKY_HELMET]
    + [BOSS] * 3 + [CRISPIN] * 4 + [BROCK] * 2 + [LILLIE] * 4 + [WATCHTOWER] * 2
    + [FIRE_ENERGY] * 4 + [PSYCHIC_ENERGY] * 4
)


def _no_damage_counter(pokemon):
    """Phantom Dive のダメカン配置を防ぐ対象（特性 or Mist/Rock Fighting エネ）。"""
    if pokemon is None:
        return True
    if pokemon.id in NO_DAMAGE_COUNTER_IDS:
        return True
    for card in (pokemon.energyCards or []):
        if card.id in GUARD_ENERGY_IDS:
            return True
    return False


# ── S-7: 進化前提の最終形（evolvesFrom はカード名。generic_policy.py L299 と同じ規約） ──

_CHILDREN_MAP = None


def _children_map():
    """親カード名 → その名から進化する子カードのリスト（全カード固定なので1回だけ構築）。"""
    global _CHILDREN_MAP
    if _CHILDREN_MAP is None:
        _CHILDREN_MAP = defaultdict(list)
        for c in CARD_DB.values():
            ef = getattr(c, "evolvesFrom", None)
            if ef:
                _CHILDREN_MAP[ef].append(c)
    return _CHILDREN_MAP


def _final_form(card):
    """進化前提の最終形カードを返す（分岐は最大HPを取る。楽観仮定＝相手は進化する）。"""
    if card is None:
        return None
    cur = card
    seen = set()
    while getattr(cur, "cardId", None) not in seen:
        seen.add(cur.cardId)
        kids = _children_map().get(getattr(cur, "name", None), [])
        if not kids:
            break
        cur = max(kids, key=lambda k: getattr(k, "hp", 0) or 0)
    return cur


def _is_attacker(card):
    """アタッカー運用されるか（履歴テーブル OR megaEx 属性）。card は静的カードデータ。"""
    if card is None:
        return False
    return card.cardId in ATTACKER_IDS_LEARNED or getattr(card, "megaEx", False)


def _final_prize(card):
    """最終形のサイド数（進化前提）。megaEx=3 / ex=2 / その他=1。"""
    if card is None:
        return 1
    if getattr(card, "megaEx", False):
        return 3
    if getattr(card, "ex", False):
        return 2
    return 1


class DragapultPolicy(BasePolicy):
    DECK_NAME = "dragapult"
    GO_FIRST = True            # div-D1（2026-07-08 A/B実測・R-21 更新）: 7/8フィールド（マリィ34%のアグロ
                               # 環境）では先攻のセットアップ1ターン先取りが優位。対マリィ 49.5%(220戦)→58.0%(200戦)。
                               # 旧値 False は ptcg-abc 6月メタ（Trevenant環境）の実測。上位ドラパルトピロットが
                               # エピソードに現れたら divergence で再検証（7/6 は2試合のみで YES/NO 割れ）
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】
    ATTACKER_IDS = {DRAGAPULT_EX, LATIAS_EX, FEZANDIPITI_EX}
    ENERGY_IDS = {FIRE_ENERGY, PSYCHIC_ENERGY}
    LINE_PROTECT_IDS = DRAGAPULT_LINE | {RARE_CANDY}   # R-13
    ATTACK_ENERGY_TYPE = None  # サンプル準拠: 弱点計算は使わない
    # S-7【2026-07-13 採用】: Phantom Dive ばら撒き60 の配分を「最小攻撃回数でサイド取り切り」
    # の探索（_plan_spread）に委ねる。HPは現物・進化前提はアタッカー役割判定のみ（進化前提を
    # 全HPに適用した版は制圧度非改善で棄却）。gauntlet 80戦で旧配分 52.9% → 56.7%（+3.8pt、
    # 主因 marnie +11.3pt=120戦で+7.5pt確認）。既定 True。DRAGA_SPREAD=0 で旧配分に戻せる
    # （garchomp -12.5pt の比較調査用に旧ヒューリスティックを一旦残置）。
    USE_SPREAD_SEARCH = os.environ.get("DRAGA_SPREAD", "1") != "0"
    # ターン内探索（TurnSearcher）の時間予算。検証で gauntlet を回すため環境変数で短縮可能。
    # 探索の有効化自体は gauntlet --search rollout（search_enabled 注入）で行う。
    SEARCH_TIME_PER_DECISION = float(os.environ.get("DRAGA_SEARCH_TIME", "1.0"))

    def __init__(self):
        super().__init__()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False,
                      "can_main_attack": False, "active_route": False}
        self.use_support = 0
        self._log_buf = []
        self._pre_logs = []
        self._deck_cache = None
        self.spread_plan = None
        self._playable_ids = set()  # R-13+: この番に即プレイできる手札IDのスナップショット
        self._dive_step = None      # D-2: 確定ダイブ経路の次の1手
        self._dive_route = None     # D-2: 経路全体（steps）
        self._dive_reserved = {}    # D-2: 経路が手札から消費する札（DISCARD 保護）
        self._dive_fetch = None     # D-2: 直前の取得手のサブ選択 pin

    def reset_game(self):
        super().reset_game()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False,
                      "can_main_attack": False, "active_route": False}
        self.use_support = 0
        self._log_buf = []
        self._pre_logs = []
        self.spread_plan = None
        self._playable_ids = set()
        self._dive_step = None
        self._dive_route = None
        self._dive_reserved = {}
        self._dive_fetch = None

    # ═══════════════ ログ追跡（pre_ko / no_item の材料。サンプルの pre_turn_log） ═══════════════

    def track_logs(self, obs):
        for entry in obs.logs:
            self._log_buf.append(entry)
            if entry.type == LogType.TURN_END:
                self._pre_logs = self._log_buf
                self._log_buf = []
        super().track_logs(obs)   # R-17（相手最終攻撃）

    # ═══════════════ R-18: サイド落ち推定（サンプルの serial ベース簡易版） ═══════════════

    def _deck_list(self):
        if self._deck_cache is None:
            try:
                self._deck_cache = _read_deck_csv()
            except Exception:
                self._deck_cache = list(DECK_FALLBACK)
        return self._deck_cache

    # ※ 自山カウンティングは基盤 R-32（policy_base）に一本化した（2026-07-27）。
    #    旧 `_visible_counts` / `_subtract_visible` / `_prize_ids` は削除済み。

    # ═══════════════ ターン分析（サンプル agent() 冒頭の会計を毎手番再現） ═══════════════

    def choose(self, obs):
        # R-32 の自己回復（2026-07-28）: ハーネスが my_deck_list を注入しない場合でも
        # 本機は CSV→DECK_FALLBACK で自リストを確定できる。これが無いと deck_counts が
        # 全ゼロになり、ポフィン/パッド「的なし」等が常時発火する（07-28 の崩壊の教訓）。
        if not self.my_deck_list:
            self.my_deck_list = list(self._deck_list())
        # R-32 を _analyze より先に回す（_analyze が deck_min/deck_max を読むため）
        self.update_deck_knowledge(obs)
        self.p = self._analyze(obs)
        # D-2: 経路は判定（update_belief = lethal/threats の更新）の**後**に立てる。
        # base の choose も update_belief を呼ぶが冪等なので二重実行は挙動に影響しない
        # （DRA_DIVE_ROUTE=0 ではこのブロック自体が走らない = 既定挙動は不変）。
        if DRA_DIVE_ROUTE and obs.select.context == SelectContext.MAIN:
            self.update_belief(obs)
            self._dive_fetch = None
            self._dive_route = self._compute_dive_route(obs)
            self._dive_step = self._dive_route[0] if self._dive_route else None
            self._dive_reserved = self._route_reserved(self._dive_route)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        osn = opp_state(obs)
        yi = obs.current.yourIndex

        # R-32（基盤の自山カウンティング）に一本化。旧 R-18 自前実装の2つのバグを解消:
        #   ① 全山ビューの確認が無く、部分公開でも「見えなかった山」をサイド扱いしていた
        #   ② サイドを取られても `_prize_ids` を無効化せず、手札側と二重に減算して
        #      山を過小評価していた（負の枚数にもなり得た）
        # さらに **上限(deck_counts) と下限(deck_min) を分離**する。見えていない札は
        # 山とサイドのどちらにもあり得るので、「確定」の主張は下限、「不可能」の判定は
        # 上限を見なければならない（従来は上限だけで「確定」を語っていた＝嘘をつき得た）。
        deck_counts = defaultdict(int)
        deck_min = defaultdict(int)
        for cid in set(self._deck_list()):
            hi = self.deck_max(cid)
            if hi is None:
                break                       # 基盤がまだリスト未取得（初手のみ）
            deck_counts[cid] = hi
            deck_min[cid] = self.deck_min(cid) or 0

        fc = defaultdict(int)
        hc = defaultdict(int)
        dc = defaultdict(int)
        active_id = 0
        bench_attacker = False
        can_evolve_dreepy = False
        evolve_dreepy_count = 0
        can_evolve_drakloak = False
        for card in ms.active:
            if card is None:
                continue
            active_id = card.id
            fc[card.id] += 1
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
        for card in ms.bench:
            if card is None:
                continue
            fc[card.id] += 1
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
            if card.id == DRAGAPULT_EX and len(card.energies) >= 2:
                bench_attacker = True
        for card in (ms.discard or []):
            if card is not None:
                dc[card.id] += 1

        stadium_id = 0
        for card in obs.current.stadium:
            stadium_id = card.id

        # 前の相手番のイベント（Unfair Stamp / Fez / グッズロックの材料）
        pre_ko = False
        no_item = False
        for log in self._pre_logs:
            if log.type == LogType.ATTACK and log.attackId == ATK_ITCHY_POLLEN:
                no_item = True
            elif (log.type == LogType.MOVE_CARD and log.playerIndex == yi
                  and log.fromArea in (AreaType.BENCH, AreaType.ACTIVE)
                  and log.toArea == AreaType.DISCARD):
                pre_ko = True

        p = {
            # deck_counts = 上限（山にあるかもしれない） / deck_min = 下限（確実に山にある）
            "fc": fc, "hc": hc, "dc": dc, "deck_counts": deck_counts,
            "deck_min": deck_min,
            "active_id": active_id, "bench_attacker": bench_attacker,
            "can_evolve_dreepy": can_evolve_dreepy,
            "evolve_dreepy_count": evolve_dreepy_count,
            "can_evolve_drakloak": can_evolve_drakloak,
            "main_pokemon_count": fc[DREEPY] + fc[DRAKLOAK] + fc[DRAGAPULT_EX],
            "no_more_dex": fc[DRAGAPULT_EX] * 2 >= len(osn.prize),
            "stadium_id": stadium_id,
            "prize_diff": len(ms.prize) - len(osn.prize),
            "pre_ko": pre_ko, "no_item": no_item,
            "no_draw": ms.deckCount <= 8,   # R-11（サンプル準拠の簡易閾値）
            "effect_id": obs.select.effect.id if obs.select.effect is not None else 0,
            "context_card_id": obs.select.contextCard.id if obs.select.contextCard is not None else 0,
            "support_count": 0, "hand_scores": [], "negative_hand": 0,
        }

        # S-7: ばら撒き配分の探索計画。DAMAGE_COUNTER_ANY の連続選択中は開始時点で1回だけ計算し
        # キャッシュ（目標残りHPは絶対値なので配置が進んでも不変。ここで毎回引き直すと現hpの
        # 減少でドリフトする）。他 context に移ったら破棄して次の攻撃で再計算。
        if self.USE_SPREAD_SEARCH and obs.select.context == SelectContext.DAMAGE_COUNTER_ANY:
            if self.spread_plan is None:
                self.spread_plan = self._plan_spread(obs)
        else:
            self.spread_plan = None

        # MAIN でだけ: 配分プラン（DFS）+ 使うサポートの択一
        if obs.select.context == SelectContext.MAIN:
            self._main_option_proc(obs, p)
            # R-13+: 「この番に即プレイできる手札」を記録する。エンジンは合法手しか
            # 選択肢に出さないので、PLAY/EVOLVE/ATTACH に出ている手札カード = 即プレイ可能。
            # DISCARD やサーチ先の採点はこのターンの間このスナップショットを参照する。
            playable = set()
            for o in obs.select.option:
                if o.type in (OptionType.PLAY, OptionType.EVOLVE, OptionType.ATTACH):
                    c0 = option_card(obs, o)
                    if c0 is not None:
                        playable.add(c0.id)
            self._playable_ids = playable
            self.p = p          # 経路計算（_dive_assess）が self.p を読む
            # D-2 の経路計算はここではなく choose() 側（update_belief の後）で行う。
            # _analyze 時点の self.t（lethal 等）は**前の決定の値**なので、ここで経路を
            # 立てると古い lethal 判定で経路を放棄する（07-27 法医学検証で実測）。
            self.use_support = 0
            if not obs.current.supporterPlayed:
                best = 0
                for o in obs.select.option:
                    if o.type != OptionType.PLAY:
                        continue
                    card = get_card(obs, AreaType.HAND, o.index, yi)
                    data = CARD_DB.get(card.id) if card is not None else None
                    if data is not None and data.cardType == CardType.SUPPORTER:
                        s = self._hand_score(obs, p, card.id, True)
                        if best < s:
                            best = s
                            self.use_support = card.id

        # 手札スコア（PLAY 採点の材料。走査しながら同名カウントを進める = サンプル準拠）
        for card in (ms.hand or []):
            s = self._hand_score(obs, p, card.id, False) if card is not None else 0
            p["hand_scores"].append(s)
            if s < 0:
                p["negative_hand"] += 1
            if card is not None:
                hc[card.id] += 1
                data = CARD_DB.get(card.id)
                if data is not None and data.cardType == CardType.SUPPORTER and card.id != BOSS:
                    p["support_count"] += 1

        # DRA_BUDEW_OPEN（2026-07-24 ユーザー指示）: 開幕（両者の最初の番 = turn<=2）で
        # ファントムダイブが撃てないとき、バトル場に1エネ張って退却しスボミーを前に出し、
        # ムズムズ花粉（相手グッズロック）を撃つ。1エネ捨てる無理攻めを肯定。旧実装は
        # 退却が turn>=2 ゲートで先行T1（global turn 1）を除外していた + エネ張りが
        # ベンチのドロンチ(20120)を優先してバトル場が退却できなかった（両方をここで解錠）。
        budew_open = (DRA_BUDEW_OPEN
                      and not self.flags["can_main_attack"]
                      and not self.flags["active_route"]
                      and obs.current.turn <= 2
                      and active_id != BUDEW and fc[BUDEW] >= 1)
        p["budew_open"] = budew_open
        p["do_switch"] = (not self.flags["can_main_attack"]
                          and not self.flags["active_route"]   # R-30: バトル場で撃てるなら退却しない
                          and (bench_attacker
                               or (active_id != BUDEW and fc[BUDEW] >= 1
                                   and (obs.current.turn >= 2 or budew_open))))
        return p

    # ═══════════════ R-30: バトル場から今すぐ Phantom Dive を撃てるか（手番内ルート検証） ═══════════════

    def _active_dive_route(self, obs):
        """R-30【ハード・ユーザー決定 2026-07-15】: バトル場のポケモンが退却なしで
        この番 Phantom Dive を撃てるルートがあるか。考慮する手 = 場の Drakloak の進化
        （EVOLVE オプションの実在で合法性確認）+ 手張り1回（ATTACH オプションで確認。
        R-10 の上限があるため e<2 のときだけ）。Dreepy+アメ直行はアメの付け先選択を
        このフラグから保証できないため対象外（従来挙動に委ねる）。
        True のとき: EVOLVE はバトル場優先（ベンチ進化→退却=エネ破棄のルートを封じる）、
        do_switch を抑制。"""
        ms = my_state(obs)
        if ms.asleep or ms.paralyzed:
            return False
        active = active_pokemon(obs)
        if active is None:
            return False
        if active.id == DRAKLOAK:
            if not any(o.type == OptionType.EVOLVE and o.inPlayArea == AreaType.ACTIVE
                       for o in obs.select.option):
                return False
        elif active.id != DRAGAPULT_EX:
            return False
        ids = [c.id for c in (active.energyCards or [])]
        need = [color for color in (FIRE_ENERGY, PSYCHIC_ENERGY) if color not in ids]
        if not need:
            return True
        if len(need) > 1 or len(ids) >= 2:
            return False   # 手張り1回では {R}{P} が揃わない / R-10 上限で張れない
        for o in obs.select.option:
            if o.type != OptionType.ATTACH or o.inPlayArea != AreaType.ACTIVE:
                continue
            card = option_card(obs, o)
            if card is not None and card.id == need[0]:
                return True
        return False

    def _dive_now_after_evolve(self, obs, target):
        """S-0!: この進化を実行したら【この番のうちに】ファントムダイブを撃てるか（確定判定）。

        ファントムダイブは {炎}{超}。進化してもエネは引き継がれるので、進化後の不足色は
        target に今ついている色だけで決まる。撃てるのはバトル場だけなので呼び出し側で
        ACTIVE に限定する。**確定できる経路だけを True** にする（推測では上げない）:
          ① もう {炎}{超} が揃っている → 進化した瞬間に撃てる
          ② 1色不足 かつ 手張り権が残っていて不足色が手札にある
          ③ 1色不足 かつ サポート未使用でアカマツが手札にあり、不足色が山に残っている
             （アカマツは山から基本エネを2枚まで、1枚を場に付け1枚を手札へ）
          ④ 2色不足 かつ 手張り権もサポートも残っていてアカマツがあり、両色が山にある
             （アカマツで1枚付与＋手札に来た1枚を手張り）
        R-30 の `_active_dive_route` との違いはアカマツ経路（③④）を見る点。本デッキは
        アカマツ4枚なので、この経路の取りこぼしがボム版（2〜4枚）より効く。

        【R-32 適用 2026-07-27】「山にある」は **deck_min（確実に山にある下限）** で見る。
        従来は上限（山＋サイド）で見ていたため、**サイド落ちした色を『確定で取れる』と
        主張していた**（＝ここが「確定が確定でなかった」箇所）。サイド確定後は
        下限＝上限になるので、判定は自動的に本来の強さに戻る。"""
        if target is None:
            return False
        have = {c.id for c in (getattr(target, "energyCards", None) or []) if c is not None}
        need = {FIRE_ENERGY, PSYCHIC_ENERGY} - have
        if not need:
            return True
        ms = my_state(obs)
        hand = [c.id for c in (ms.hand or []) if c is not None]
        deck = (self.p or {}).get("deck_min") or {}
        attach_left = not obs.current.energyAttached
        crispin_ready = (not obs.current.supporterPlayed) and CRISPIN in hand
        if len(need) == 1:
            col = next(iter(need))
            if attach_left and col in hand:
                return True
            if crispin_ready and deck.get(col, 0) >= 1:
                return True
            return False
        if attach_left and crispin_ready:
            return all(deck.get(c, 0) >= 1 for c in need)
        return False

    # ※ 手書きの状態探索（旧 D-1 `_dive_search`）は 2026-07-27 に削除。
    #    到達判定は基盤 R-33 `acquire_plan`（実測ドメイン表）へ一本化 = `_dive_assess`。

    def _dive_maybe_after_evolve(self, obs, target):
        """S-0! のアグレッシブ形（閾値0.0 の忠実な移植・ユーザー指摘 2026-07-27）。

        `_dive_now_after_evolve` が「撃てると**証明できる**経路だけ True」なのに対し、
        こちらは「**撃てないと証明できるときだけ** False」。ボム版 `_dive_impossible` と
        同型の到達可能性判定で、降りる条件は次の2つだけ:
          ① 必要な色が手札にも山にも無い（そもそも色が取れない）
          ② この番に色を供給する手段が1つも残っていない（手張り権もサポート権も無い）
        それ以外は「可能性がある」= ダイブに寄せる。前セッションの結論（可能性がある時点で
        アグレッシブが得・パッシブは劣化版）に従うなら、こちらが本来の形。

        【R-32 適用】こちらは「不可能と**証明**できるか」を問うので **deck_counts（上限）**
        が正しい（上限が0のときだけ『どこからも取れない』が確定する）。確定側の
        `_dive_now_after_evolve` が下限を使うのと対になっている。"""
        if target is None:
            return False
        have = {c.id for c in (getattr(target, "energyCards", None) or []) if c is not None}
        need = {FIRE_ENERGY, PSYCHIC_ENERGY} - have
        if not need:
            return True
        ms = my_state(obs)
        hand = [c.id for c in (ms.hand or []) if c is not None]
        deck = (self.p or {}).get("deck_counts") or {}
        for col in need:
            if col not in hand and deck.get(col, 0) <= 0:
                return False                      # ①
        if obs.current.energyAttached and obs.current.supporterPlayed:
            return False                          # ②
        return True

    # ═══════════════ 配分プラン（サンプル main_option_proc の移植 = 枝刈り DFS） ═══════════════

    def _main_option_proc(self, obs, p):
        select = obs.select
        ms = my_state(obs)
        osn = opp_state(obs)
        f = self.flags
        f["can_switch"] = False
        f["can_attack"] = False
        f["can_main_attack"] = False
        for o in select.option:
            if o.type == OptionType.RETREAT:
                f["can_switch"] = True
            elif o.type == OptionType.ATTACK:
                f["can_attack"] = True
                if o.attackId == ATK_PHANTOM_DIVE:
                    f["can_main_attack"] = True
        f["active_route"] = self._active_dive_route(obs)

        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        if not f["can_main_attack"] and not (p["bench_attacker"] and f["can_switch"]):
            return
        if not osn.active or osn.active[0] is None:
            return

        # cards[0]=相手アクティブ, cards[1..]=相手ベンチ（インデックスは plan の座標系）
        cards = [osn.active[0]] + list(osn.bench)
        HUGE = 10 ** 9

        def counter_hp(pk):
            # ダメカン配置不可の対象は「取り切れない」扱いで DFS から除外（移植ノート1）
            if pk is None or _no_damage_counter(pk):
                return HUGE
            return pk.hp

        # DFS: 「残り60で完全に取り切れる部分集合」だけを列挙（サンプル準拠の枝刈り）
        counter_indices = []
        ci = [0]
        remain = 60
        while ci:
            index = ci[-1]
            hp = counter_hp(cards[index])
            if remain >= hp:
                counter_indices.append(ci.copy())
                if index < len(cards) - 1:
                    remain -= hp
                    ci.append(index + 1)
                    continue
            if index == len(cards) - 1:
                ci.pop()
                if ci:
                    remain += counter_hp(cards[ci[-1]])
            if ci:
                ci[-1] += 1
        counter_indices.append([])

        remain_prize = len(ms.prize)
        damage = attack_base_damage(ATK_PHANTOM_DIVE) or 200
        plan_score = 0
        for i, pokemon in enumerate(cards):
            if pokemon is None:
                continue
            base_prize = 0
            base_score = self._pokemon_score(pokemon, True)
            active_damage = 0 if pokemon.id in NO_DAMAGE_DEX else damage
            if pokemon.hp <= active_damage:
                base_prize += self._prize_count(pokemon, True)
            else:
                base_score *= active_damage / pokemon.hp
            best_ci = []
            best_prizes = base_prize
            max_score = base_score
            if remain_prize <= base_prize:
                max_score = 50000
            else:
                for indices in counter_indices:
                    if i in indices:
                        continue
                    prize = base_prize
                    score = base_score
                    for index in indices:
                        prize += self._prize_count(cards[index], False)
                        score += self._pokemon_score(cards[index], False)
                    if remain_prize <= prize:
                        score = 50000   # 取り切り = リーサルマーカー
                    else:
                        if prize >= 2:
                            if remain_prize <= 4:
                                score -= 1200   # サイド先行のペース管理（R-09 相当）
                        elif prize == 1:
                            score -= 300
                        else:
                            score += 1200       # 温存配分
                    if max_score < score:
                        max_score = score
                        best_ci = indices
                        best_prizes = prize
            if plan_score < max_score:
                plan_score = max_score
                self.plan_a = {"attack": i, "counter": list(best_ci), "prizes": best_prizes}
            if i == 0:
                # plan_b = 「アクティブを攻撃する前提」の最良（DAMAGE_COUNTER_ANY が参照）
                self.plan_b = {"attack": self.plan_a["attack"],
                               "counter": list(self.plan_a["counter"]),
                               "prizes": self.plan_a["prizes"]}

    def _prize_count(self, pokemon, is_attack_damage):
        data = CARD_DB.get(pokemon.id)
        count = 3 if (data is not None and getattr(data, "megaEx", False)) else \
            2 if (data is not None and getattr(data, "ex", False)) else 1
        if is_attack_damage:
            for card in (pokemon.energyCards or []):
                if card.id == LEGACY_ENERGY:
                    count -= 1
            for card in (pokemon.tools or []):
                if card.id == LILLIES_PEARL and data is not None and "Lillie" in data.name:
                    count -= 1
        return max(0, count)

    def _pokemon_score(self, pokemon, is_attack_damage):
        """相手ポケモンを対象に取る戦術価値（サンプル準拠のヒューリスティック）。"""
        data = CARD_DB.get(pokemon.id)
        score = self._prize_count(pokemon, is_attack_damage) * 1000
        score += len(pokemon.energies) * 150
        score += len(pokemon.tools) * 100
        if data is not None and getattr(data, "stage2", False):
            score += 250
        elif data is not None and getattr(data, "stage1", False):
            score += 130
        if pokemon.id in LOW_VALUE_TARGETS:
            score -= 200
        if pokemon.id == MUNKIDORI and len(pokemon.energies) >= 1:
            score += 300
        score += pokemon.hp
        return score

    # ═══════════════ S-7: ばら撒き60 の配分探索（最小攻撃回数でサイド取り切り） ═══════════════

    def _bench_targets(self, obs):
        """相手ベンチを (coord, 現物残HP, need, サイド, アタッカー) に抽象化。
        coord = ベンチindex+1（plan_b['counter'] / _score_counter の座標系に一致）。
        取り切りは現物HP（今の盤面で削る対象。進化前に潰す＝現在HP版で実証済み・制圧度+3.8pt）。
        進化前提は「アタッカーか＝将来正面に来るか」の役割判定にのみ使う（HPには使わない）。
        （進化する/しないを p_evo で重み合成する進化分岐版は gauntlet 80戦 56.0% で現在HP版 56.7%
        を上回れず棄却。garchomp +10pt だが marnie -5pt で相殺。2026-07-14）"""
        osn = opp_state(obs)
        out = []
        for j, pk in enumerate(osn.bench):
            if pk is None:
                continue
            if _no_damage_counter(pk):
                continue   # ダメカン配置不可（特性 / Mist・Rock Fighting）
            static = CARD_DB.get(pk.id) or pk
            ff = _final_form(static)
            remain = max(10, pk.hp)                        # 現物の残HP（今削る対象）
            need = -(-remain // 10)                        # ceil(remain/10) = KOに要る個数
            out.append({
                "coord": j + 1, "remain": remain, "need": need,
                "prize": self._prize_count(pk, False),     # 現物のサイド
                "attacker": _is_attacker(ff),              # 役割のみ進化前提
            })
        return out

    def _plan_spread(self, obs):
        """ばら撒き6個の配分を {coord: 目標残りHP} で返す（USE_SPREAD_SEARCH 時に _score_counter が参照）。
        方針: ①ばら撒きで取り切れるベンチ集合をサイド最大で確保（無駄なく分割）→
        ②余った個を、次サイクルで取り切りに最も近づく1体へ布石（A=置物のベンチKO /
        B=アタッカーを正面200圏に押し込み）。相手は静止＋進化前提の楽観。"""
        targets = self._bench_targets(obs)
        target_hp = {}
        if not targets:
            return target_hp

        # ① 6個以内で取り切れるベンチ部分集合をサイド最大で選ぶ（ベンチ数は小さいので全列挙）
        best_subset, best_key = [], (-1, 0)
        n = len(targets)
        for mask in range(1 << n):
            used, prize, ok = 0, 0, True
            for i in range(n):
                if mask & (1 << i):
                    used += targets[i]["need"]
                    prize += targets[i]["prize"]
                    if used > 6:
                        ok = False
                        break
            if ok and used <= 6:
                key = (prize, -used)   # サイド最大 → 同点は消費個数最小
                if key > best_key:
                    best_key, best_subset = key, [i for i in range(n) if mask & (1 << i)]
        chosen = set(best_subset)
        used = sum(targets[i]["need"] for i in chosen)
        for i in chosen:
            target_hp[targets[i]["coord"]] = 0   # 取り切り

        # ② 余りを1体へ布石（A=置物のベンチKO / B=アタッカーを正面200圏へ押し込み）
        leftover = 6 - used
        if leftover > 0:
            best_i, best_val = None, -10 ** 9
            for i in range(n):
                if i in chosen:
                    continue
                t = targets[i]
                after = t["remain"] - leftover * 10
                if t["attacker"]:
                    if after <= 200:
                        val = t["prize"] * 1000 + 500      # 1発で正面200圏（B・優）
                    elif t["remain"] <= 320:
                        val = t["prize"] * 1000 + 200      # 2発で正面圏へ chip（B）
                    else:
                        val = t["prize"] * 1000 - 100      # 大型・非効率
                else:
                    need_after = -(-max(0, after) // 10)
                    if need_after <= 6:
                        val = t["prize"] * 1000 + 400      # 次1サイクルでベンチKO（A・2発圏）
                    else:
                        val = t["prize"] * 1000 - 200      # 遠い置物
                val -= t["remain"] * 0.1                   # 近いほど良い（tiebreak）
                if val > best_val:
                    best_val, best_i = val, i
            if best_i is not None:
                t = targets[best_i]
                target_hp[t["coord"]] = max(0, t["remain"] - leftover * 10)
        return target_hp

    # ═══════════════ 判定（S-0 / R-07 探索版） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場の Dragapult ex が Phantom Dive を払える（エネ2枚以上）。"""
        return any(pk.id == DRAGAPULT_EX and energy_count(pk) >= 2
                   for pk in all_my_pokemon(obs))

    def plan_attacks(self, obs):
        plans = super().plan_attacks(obs)
        for plan in plans:
            if plan.attack_id == ATK_PHANTOM_DIVE:
                plan.spread_damage = 60
        return plans

    def judge_lethal(self, obs):
        """R-07 探索版: 配分プラン（アクティブKO + counter部分集合KO）で残りサイドを
        取り切れるなら昇格。単発KO・ボス単発は base に委譲。"""
        spread = self._spread_lethal(obs)
        if spread is not None:
            return spread
        return super().judge_lethal(obs)

    def _spread_lethal(self, obs):
        plan = self.plan_a
        if plan["attack"] < 0 or plan["prizes"] < len(my_state(obs).prize):
            return None
        if not self.flags.get("can_main_attack"):
            return None   # Phantom Dive を今すぐ払えるときだけ（ベンチ経由は昇格しない）
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return None
        if plan["attack"] == 0:
            return {"route": "active", "attack_id": ATK_PHANTOM_DIVE,
                    "attacker": active, "needs_retreat": False}
        # ボスで釣り出してから取り切る計画（base apply_protocol の boss 経路に乗せる）
        if BOSS in hand_ids(obs) and not obs.current.supporterPlayed:
            osn = opp_state(obs)
            cards = ([osn.active[0]] if osn.active else [None]) + list(osn.bench)
            idx = plan["attack"]
            if idx < len(cards) and cards[idx] is not None:
                return {"route": "boss", "target": cards[idx],
                        "attack_id": ATK_PHANTOM_DIVE, "attacker": active,
                        "needs_retreat": False}
        return None

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            return self._score_promote(obs, opt)
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            if obs.current.yourIndex != obs.current.firstPlayer and cid == DREEPY:
                return 100, "S-2: bench Dreepy (going second)"
            return -1, "S-2: no extra bench at setup"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_yes_no(self, obs, opt):
        # R-11: 山札が薄いときは任意ドロー特性を辞退（サンプルの no_draw をACTIVATEにも適用）
        if (obs.select.context == SelectContext.ACTIVATE and self.p.get("no_draw")
                and self.t.get("lethal") is None):
            return (1, "R-11: decline activate (deck thin)") if opt.type == OptionType.NO \
                else (0, "R-11: deck thin")
        return super().score_yes_no(obs, opt)

    # ═══════════════ 優先則（3フック。サンプルの一枚岩スコアラーを移植） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    # ═══════ D-2: 確定ダイブ経路の**執行**（ユーザー 2026-07-27） ═══════
    # 「確定したら打つ一択なので、ルールの重みを考える必要が無い」。
    # 検証した最小コスト経路の**次の1手**を、通常のプレイ帯より上（ただしリーサル帯 1e6 の下）
    # に置いて確実に実行させる。旧実装は S-0! で進化の点数を上げるだけだったので、
    # 「確定と判定したのに進化すらしない」が 153回中48回（実測）発生していた。
    # 副産物: **ハイパーボールの発火条件を手で書く必要が消える** — 経路コストが最も高い札
    # なので、他に手が無いときだけ経路に乗る。

    def _dive_legal(self, obs, p):
        """(blocked, サポートを打てるか, searcher_guards) — 観測に基づく合法性制約。

        07-27 の「嘘の確定」の残り原因: グッズロック被弾ターンの UB/パッド、先攻1ターン目
        などエンジンが打たせない番のサポート、監視塔下のニャース ex（{C}特性無効）を
        経路に載せていた。**プレイ可能性はエンジンの提示（選択肢）を根拠にする**。"""
        blocked = set()
        if p.get("no_item"):
            blocked |= {POFFIN, POKE_PAD, ULTRA_BALL, NIGHT_STRETCHER}
        sup_playable = not obs.current.supporterPlayed
        sel = obs.select
        if (sup_playable and sel is not None
                and sel.context == SelectContext.MAIN):
            in_hand = False
            offered = False
            for c in (my_state(obs).hand or []):
                d = CARD_DB.get(c.id) if c is not None else None
                if d is not None and d.cardType == CardType.SUPPORTER:
                    in_hand = True
                    break
            if in_hand:
                for o in (sel.option or []):
                    if o.type != OptionType.PLAY:
                        continue
                    c = option_card(obs, o)
                    d = CARD_DB.get(c.id) if c is not None else None
                    if d is not None and d.cardType == CardType.SUPPORTER:
                        offered = True
                        break
                # 手札にサポートがあるのに1枚も選択肢に出ていない = この番は打てない
                sup_playable = offered
        ms = my_state(obs)
        guards = {MEOWTH_EX: (p.get("stadium_id") != WATCHTOWER
                              and len(ms.bench or []) < getattr(ms, "benchMax", 5))}
        return blocked, sup_playable, guards

    def _dive_assess(self, obs, certain=True, assume_evolve_active=False,
                     include_bench=False):
        """(コスト, 経路) — ファントムダイブの必要札がこの番に揃うか（R-33 接続）。

        設計（ユーザー 2026-07-27）: 「撃てる盤面まで展開するのは計算資源の無駄。
        必要札がそろうかどうかで探索する」。揃った後の進化と手張りは探索ではなく算術。

        経路 = 取得手 [(action, searcher, target), ...] + 配備手:
            ("candy", アメ, None) / ("evolve_active", ドラパルト ex, None)
            / ("attach", 色, None) / ("crispin", アカマツ, 場に付ける色)
        **完全な経路を返す**のは、執行側が予約（DISCARD 保護）とサブ選択の pin に使うため。

        certain=True  … 過小近似（証明できる経路のみ。偵察指令などの引き運は除外）。
        certain=False … 過大近似（deck_max + ドロー札も可）。False =「不可能」の証明。
        include_bench … possibility 専用。ベンチの充電済みライン + 入れ替えも数える
            （「この番ダイブが起こり得るか」を問う検証・損切り用。執行は active 経路のみ）。"""
        ms = my_state(obs)
        active = active_pokemon(obs)
        if active is None or ms.asleep or ms.paralyzed:
            return None, None
        p = self.p or {}
        blocked, sup_playable, guards = self._dive_legal(obs, p)
        body = active.id
        if assume_evolve_active and body == DRAKLOAK:
            body = DRAGAPULT_EX
        cols = {c.id for c in (active.energyCards or []) if c is not None}
        best = self._dive_body_route(obs, p, active, body, cols, certain,
                                     blocked, sup_playable, guards)
        if best[0] is not None or certain or not include_bench:
            return best
        if self._dive_bench_possible(obs, p, blocked, sup_playable):
            return 99, []
        return None, None

    def _active_evolvable_now(self, obs, active):
        """バトル場の個体がこの番進化できるか。**EVOLVE の選択肢があれば真値**。

        進化先が手札に無く選択肢で確認できない場合は、進化酔い（この番に出た/進化した
        = appearThisTurn）と両者の初手番の進化禁止（turn<=2）で判定する。
        07-27 の「確定なのに進化すらせず」の一因: この検査が無く、進化酔いの個体に
        『この番進化して撃てる』と主張していた（エンジンは EVOLVE を提示しない）。"""
        sel = obs.select
        if sel is not None and sel.context == SelectContext.MAIN:
            for o in (sel.option or []):
                if (o.type == OptionType.EVOLVE
                        and o.inPlayArea == AreaType.ACTIVE):
                    return True
            # 進化先が手札にあるのに EVOLVE が選択肢に無い = この番は進化できない
            if any(c is not None and c.id == DRAGAPULT_EX
                   for c in (my_state(obs).hand or [])):
                return False
        return (not getattr(active, "appearThisTurn", False)
                and obs.current.turn >= 3)

    def _dive_body_route(self, obs, p, active, body, cols, certain,
                         blocked, sup_playable, guards):
        """バトル場の個体（body に進化後を仮定可）でのダイブ経路。(コスト, 経路)。"""
        missing = [c for c in (FIRE_ENERGY, PSYCHIC_ENERGY) if c not in cols]
        base = {}
        deploy_body = []
        if body == DRAKLOAK:
            if not self._active_evolvable_now(obs, active):
                return None, None
            base[DRAGAPULT_EX] = 1
            deploy_body = [("evolve_active", DRAGAPULT_EX, None)]
        elif body == DREEPY:
            if (obs.current.turn <= 1
                    or getattr(active, "appearThisTurn", False)
                    or p.get("no_item")):     # アメはグッズ = ロック中は打てない
                return None, None
            base[RARE_CANDY] = 1
            base[DRAGAPULT_EX] = 1
            deploy_body = [("candy", RARE_CANDY, None)]
        elif body != DRAGAPULT_EX:
            return None, None

        attach_left = not obs.current.energyAttached
        deckf = self.deck_min if certain else self.deck_max

        # 色の供給チャネルは手張り(1回)とアカマツ(サポート枠)だけ。ドロー/サーチは
        # 色を**手札に**運ぶだけで、場に乗せる枠はこの2つ以外に存在しない。
        #
        # よるのこうざん（1266）: 場に出ている間、テラスタル（ドラパルト ex）の攻撃コスト
        # +{C}。**印刷コストだけ見ると『2エネで撃てる』という嘘の確定になる**
        # （07-27 法医学検証: 対アラカザムの失敗が全てこれ。ex+{R}{P} なのにエンジンは
        # ファントムダイブを提示せず、選択肢はジェットヘッドバット153のみだった）。
        # 追加分は任意の色でよい。**自分のスタジアム（監視塔×2）を張れば剥がせる**ので、
        # その変種も経路に含める = 対アラカザムの実在の勝ち筋。
        mine_up = (p.get("stadium_id") == NIGHTTIME_MINE
                   and bool(getattr(CARD_DB.get(DRAGAPULT_EX), "tera", False)))
        other_of = {FIRE_ENERGY: PSYCHIC_ENERGY, PSYCHIC_ENERGY: FIRE_ENERGY}

        def attach_variants(t):
            cols = [t] if t != "ANY" else [FIRE_ENERGY, PSYCHIC_ENERGY]
            return [({c: 1}, [("attach", c, None)]) for c in cols]

        def crispin_variants(t):
            cols = [t] if t != "ANY" else [FIRE_ENERGY, PSYCHIC_ENERGY]
            out = []
            for c in cols:
                # アカマツは「違うタイプ2枚→1枚場・1枚手札」。山に1タイプしか無いと
                # 1枚拾い（手札行き）になり場に付かない（T5 実測）→ 確定は両色在庫を要求
                if (deckf(c) or 0) < 1:
                    continue
                if certain and (deckf(other_of[c]) or 0) < 1:
                    continue
                out.append(({CRISPIN: 1}, [("crispin", CRISPIN, c)]))
            return out

        def color_plans(extra_c, stadium_fix):
            targets = list(missing) + ["ANY"] * extra_c
            pre, fix_needs = [], {}
            if stadium_fix:
                pre = [("play", WATCHTOWER, None)]
                fix_needs = {WATCHTOWER: 1}
            outs = []
            if not targets:
                outs.append((dict(fix_needs), True, list(pre)))
            elif len(targets) == 1:
                t = targets[0]
                if attach_left:
                    for add, dep in attach_variants(t):
                        n = dict(fix_needs)
                        for k, v in add.items():
                            n[k] = n.get(k, 0) + v
                        outs.append((n, True, pre + dep))
                if sup_playable:
                    for add, dep in crispin_variants(t):
                        n = dict(fix_needs)
                        for k, v in add.items():
                            n[k] = n.get(k, 0) + v
                        outs.append((n, False, pre + dep))
            elif len(targets) == 2 and attach_left and sup_playable:
                for i in (0, 1):
                    for add_a, dep_a in attach_variants(targets[i]):
                        for add_c, dep_c in crispin_variants(targets[1 - i]):
                            n = dict(fix_needs)
                            for src in (add_a, add_c):
                                for k, v in src.items():
                                    n[k] = n.get(k, 0) + v
                            outs.append((n, False, pre + dep_a + dep_c))
            return outs        # 3枚以上はこの番のチャネルでは供給不能

        raw_plans = color_plans(1 if mine_up else 0, False)
        if mine_up:
            raw_plans += color_plans(0, True)   # 監視塔で鉱山を剥がす変種
        plans = []
        for add_needs, sup_free, deploy in raw_plans:
            n = dict(base)
            for k, v in add_needs.items():
                n[k] = n.get(k, 0) + v
            plans.append((n, sup_free, deploy))

        best = (None, None)
        for needs, sup_free, color_deploy in plans:
            cost, acq = self.acquire_plan(
                obs, needs, certain=certain,
                supporter_available=sup_free and sup_playable,
                item_available=not p.get("no_item"),
                blocked=blocked, searcher_guards=guards)
            if cost is None:
                continue
            steps = list(acq) + deploy_body + color_deploy
            total = cost + sum(2 if k == "crispin" else 1 if k == "candy" else 0
                               for k, _, _ in steps)
            if best[0] is None or total < best[0]:
                best = (total, steps)
        return best

    def _dive_bench_possible(self, obs, p, blocked, sup_playable):
        """ベンチ経由のダイブ可能性（過大近似・possibility 専用）。

        条件: ①ベンチに ドラパルト ex（または進化可能なドロンチ + ex が世界のどこかにある）
              ②不足色の数 ≤ 供給チャネル数（手張り≤1 + アカマツ≤1）
              ③各不足色が世界のどこかにある（手札/deck_max/回収可能トラッシュ）
              ④入れ替え手段がある（RETREAT の選択肢 or can_switch フラグ）"""
        ms = my_state(obs)
        sel = obs.select
        can_move = bool(self.flags.get("can_switch")) or bool(p.get("do_switch"))
        if not can_move and sel is not None and sel.context == SelectContext.MAIN:
            can_move = any(o.type == OptionType.RETREAT for o in (sel.option or []))
        if not can_move:
            return False
        attach_left = not obs.current.energyAttached
        hand_ids_ = [c.id for c in (ms.hand or []) if c is not None]
        ex_reachable = (DRAGAPULT_EX in hand_ids_
                        or (self.deck_max(DRAGAPULT_EX) or 0) >= 1
                        or (any(c.id == DRAGAPULT_EX for c in (ms.discard or []) if c)
                            and self._color_recovery_possible(obs)))
        for pk in (ms.bench or []):
            if pk is None:
                continue
            if pk.id == DRAGAPULT_EX:
                pass
            elif (pk.id == DRAKLOAK and ex_reachable
                    and not getattr(pk, "appearThisTurn", False)):
                pass
            elif (pk.id == DREEPY and ex_reachable
                    and not getattr(pk, "appearThisTurn", False)
                    and obs.current.turn > 1 and not p.get("no_item")
                    and (RARE_CANDY in hand_ids_
                         or (self.deck_max(RARE_CANDY) or 0) >= 1)):
                pass                    # アメ直行（ベンチのドラメシヤ→ex）
            else:
                continue
            have = {c.id for c in (pk.energyCards or []) if c is not None}
            missing = [c for c in (FIRE_ENERGY, PSYCHIC_ENERGY) if c not in have]
            channels = (1 if attach_left else 0) + (1 if sup_playable else 0)
            if len(missing) > channels:
                continue
            if all(self._color_reachable_anywhere(obs, col) for col in missing):
                return True
        return False

    def _color_recovery_possible(self, obs):
        """夜のタンカが手札か山（deck_max）にあるか。"""
        ms = my_state(obs)
        if any(c is not None and c.id == NIGHT_STRETCHER for c in (ms.hand or [])):
            return True
        return (self.deck_max(NIGHT_STRETCHER) or 0) >= 1

    def _color_reachable_anywhere(self, obs, col):
        """色が世界のどこかから取れる可能性（過大近似）。"""
        ms = my_state(obs)
        if any(c is not None and c.id == col for c in (ms.hand or [])):
            return True
        if (self.deck_max(col) or 0) >= 1:
            return True
        if any(c is not None and c.id == col for c in (ms.discard or [])):
            return self._color_recovery_possible(obs)
        return False

    def _compute_dive_route(self, obs):
        """この番の確定ダイブ経路（steps）。確定できなければ None。

        毎 MAIN 決定で**現在の状態から再計画**する。各ステップは needs を単調に
        縮める（取得は手札を増やし、配備は不足を減らす）ので、再計画は必ず収束する
        = 「履歴をなぞる」と等価（ユーザー設計 2026-07-27）。"""
        if not DRA_DIVE_ROUTE or self.flags.get("can_main_attack"):
            return None
        if self.t["lethal"] is not None:
            return None
        cost, steps = self._dive_assess(obs, certain=True)
        return steps if (cost is not None and steps) else None

    def _route_reserved(self, steps):
        """残りの経路が**手札から**消費する札の多重集合（DISCARD/UB 支払いから守る）。"""
        r = {}
        for kind, cid, tgt in (steps or []):
            if kind == "attach":
                r[cid] = r.get(cid, 0) + 1
            elif kind == "evolve_active":
                r[DRAGAPULT_EX] = r.get(DRAGAPULT_EX, 0) + 1
            elif kind == "candy":
                r[RARE_CANDY] = r.get(RARE_CANDY, 0) + 1
                r[DRAGAPULT_EX] = r.get(DRAGAPULT_EX, 0) + 1
            elif kind == "crispin":
                r[CRISPIN] = r.get(CRISPIN, 0) + 1
            elif kind == "play":
                r[cid] = r.get(cid, 0) + 1
            # "ability"（偵察指令等）は盤面の特性 = 手札を消費しない
        return r

    def _dive_route_match(self, obs, opt, step):
        """このオプションが経路の次の1手か。"""
        if step is None:
            return False
        kind, cid, tgt = step
        if kind == "evolve_active":
            c = option_card(obs, opt)
            return (opt.type == OptionType.EVOLVE
                    and opt.inPlayArea == AreaType.ACTIVE
                    and c is not None and c.id == DRAGAPULT_EX)
        if kind == "candy":
            c = option_card(obs, opt)
            if opt.type == OptionType.PLAY and c is not None and c.id == RARE_CANDY:
                return True
            # アメ経由の進化が EVOLVE として直接提示される形にも対応
            return (opt.type == OptionType.EVOLVE
                    and opt.inPlayArea == AreaType.ACTIVE
                    and c is not None and c.id == DRAGAPULT_EX)
        if kind == "ability":
            c = get_card(obs, opt.area, opt.index, obs.current.yourIndex)
            return (opt.type == OptionType.ABILITY
                    and c is not None and c.id == cid)
        c = option_card(obs, opt)
        if c is None or c.id != cid:
            return False
        if kind in ("play", "crispin"):
            return opt.type == OptionType.PLAY
        if kind == "attach":
            return (opt.type == OptionType.ATTACH
                    and opt.inPlayArea == AreaType.ACTIVE)
        return False

    def _score_any(self, obs, opt):
        p = self.p
        yi = obs.current.yourIndex

        # D-2: 確定経路の執行（リーサル帯 1e6 の下・通常プレイ帯 8万 の上）。
        # 取得手を選んだ瞬間、続くサブ選択（DISCARD/TO_HAND/ATTACH_*）が経路と同じ札を
        # 選ぶよう `_dive_fetch` に意図を記録する = 「履歴をなぞる」の後半部分。
        if (DRA_DIVE_ROUTE and obs.select.context == SelectContext.MAIN
                and self._dive_route_match(obs, opt, self._dive_step)):
            kind = self._dive_step[0]
            if kind in ("play", "ability") and self._dive_step[2] is not None:
                self._dive_fetch = (self._dive_step[1], self._dive_step[2], None)
            elif kind == "crispin":
                self._dive_fetch = (CRISPIN, None, self._dive_step[2])
            return 300000, "D-2: execute confirmed dive route (next step)"

        if opt.type == OptionType.CARD:
            return self._score_card(obs, opt)

        if opt.type in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            # クラッシュハンマー等の相手エネ / 自分の退却コスト
            pi = opt.playerIndex if opt.playerIndex is not None else yi
            if pi != yi:
                score = 20 if opt.area == AreaType.BENCH else 10
                card = get_card(obs, opt.area, opt.index, pi)
                data = CARD_DB.get(card.id) if card is not None else None
                if data is not None and data.cardType == CardType.SPECIAL_ENERGY:
                    score += 1
                return score, "E-4: opp energy (bench first, special first)"
            return 0, "own energy (retreat cost)"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt)

        if opt.type == OptionType.ATTACH:
            card = option_card(obs, opt)
            target = option_target(obs, opt)
            if card is None or target is None:
                return 0, "attach none"
            score = self._attach_score(obs, p, card.id, target,
                                       opt.inPlayArea == AreaType.ACTIVE)
            return score, "S-5: attach"

        if opt.type == OptionType.EVOLVE:
            target = option_target(obs, opt)
            e = len(getattr(target, "energies", []) or []) if target is not None else 0
            # S-0!【ハード・ユーザー 2026-07-26（ボム版 loss1.json の観戦で発見）・07-27 移植】
            # 「バトル場のドロンチを進化させれば**この番のうちにファントムダイブが撃てる**」
            # 局面は、他のどの進化よりも優先する。旧実装は div-D3（下の Dreepy 進化）が 58000、
            # R-30（さらに下）が 48600 で、**ベンチのドラメシヤ進化が常に勝っていた**
            # ＝手番内ダイブ判定が進化の選択に一切繋がっていなかった。62000 は div-D3(58000) の
            # 上・アメ(75000) の下（アメ直行が残る局面ではアメを先に打つ）。
            if (DRA_DIVE_NOW and opt.inPlayArea == AreaType.ACTIVE
                    and target is not None and target.id == DRAKLOAK
                    and not self.flags.get("can_main_attack")
                    and (self._dive_assess(obs, certain=not DRA_DIVE_AGGRO,
                                           assume_evolve_active=True)[0] is not None
                         if DRA_DIVE_EXACT
                         else (self._dive_maybe_after_evolve(obs, target)
                               if DRA_DIVE_AGGRO
                               else self._dive_now_after_evolve(obs, target)))):
                return 62000, "S-0!: evolve active -> Dragapult ex (dive THIS turn)"
            if target is not None and target.id == DREEPY:
                # div-D3（2026-07-11 実測 07-07/07-08/07-09。旧: ptcg-abc 6月実測で 30000 据え置き）:
                # 7月上位ピロット（1080/1053）は Dreepy→Drakloak 進化をターン冒頭に行う
                # （進化したての Drakloak も同ターン Recon Directive を使えるため）。
                # precedence 実測（07-08, 32試合）: evo_drak が ability より先 228/84、
                # ハンマーより先 44/22、ポケパッドより先 55/29、Dreepy 展開より先 24/4。
                return 58000 + e, "div-D3: evolve Dreepy first"
            # R-30【ハード・ユーザー決定 2026-07-15】: バトル場の Drakloak を進化させれば
            # この番 Phantom Dive が撃てる（{R}{P} が場+手張り1回で揃う）なら、ベンチ進化→
            # 退却（エネ1枚破棄）より優先。div-D4（2体目温存）も「今すぐ撃てる」時は上書き。
            # 起点の観測: 両ドロンチにエネ1の盤面で 48000+e が同点 → インデックス順でベンチが
            # 進化し、退却でバトル場のエネを捨てていた（資源損）。
            if (opt.inPlayArea == AreaType.ACTIVE
                    and target is not None and target.id == DRAKLOAK
                    and self.flags.get("active_route")):
                return 48600 + e, "R-30: evolve active -> Phantom Dive this turn"
            if p["fc"][DRAGAPULT_EX] >= 1:
                # div-D4（2026-07-11 実測 07-08）: human の evolve->Dragapult 65回/32試合 ≒
                # 初回+KO後の補充のみ。「場に1体いる間は2体目に進化しない」（Drakloak を
                # Recon ドローエンジンとして温存 + ボス2枚取りの的を増やさない）。
                # 我々の evolve 選択のうち human が同ターン内に一度も行わなかったもの 110件。
                # 旧条件（fc>=2 or fc==1&&残りサイド<=2 で -1）を fc>=1 に拡大【ソフト・暫定】。
                return -1, "div-D4: hold 2nd Dragapult ex"
            # div-D4 順序側: 70000（アメ 75000 の直下）→ 48000。ability(56000) の後・
            # attach(<=45450) の前に進化する（precedence: ability が先 139/31 / attach より先 39/24。
            # Drakloak の Recon を使ってから進化しないと特性が無駄になる）。
            return 48000 + e, "S-3: evolve -> Dragapult ex"

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            if p["no_draw"]:
                return -1, "R-11: deck thin (ability)"
            if card is not None and card.id == LUMIOSE_CITY:
                return 1, "Lumiose City (low)"
            # div-D3（2026-07-11 実測 07-08）: Recon Directive はグッズ・エネ付けより先。
            # precedence: ability が attach より先 266/97、ハンマーより先 110/31、
            # ポケパッドより先 103/38、ハイパーボールより先 44/13、進化(Dragapult)より先 139/31。
            # 40000 → 56000（evo_drak 58000 の下・Dreepy 展開 54000 の上）。
            return 56000, "ability (Recon Directive etc.)"

        if opt.type == OptionType.RETREAT:
            if p["do_switch"]:
                return 10000, "retreat (bench attacker / Budew lock)"
            return -1, "no retreat"

        if opt.type == OptionType.ATTACK:
            # E-1: ワザ間の選好は attackId 準拠（Phantom Dive 154 > Jet Headbutt 153）
            return (opt.attackId or 0), "E-1: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        return 0, "fallback"

    # ── PLAY（サンプルの帯 + ptcg-abc 実測修正） ──

    def _score_play(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        cid = card.id
        hand_scores = p["hand_scores"]
        card_score = hand_scores[opt.index] if opt.index < len(hand_scores) else 0
        fc, hc, deck = p["fc"], p["hc"], p["deck_counts"]

        if cid == DREEPY:
            return 54000, "S-2: play Dreepy (ptcg-abc: 51000->54000)"
        if cid == FEZANDIPITI_EX:
            if card_score > 0:
                return 35000, "play Fez (ptcg-abc: 53000->35000)"
            return -1, "Fez: not needed"
        if cid == LATIAS_EX:
            if p["active_id"] not in (DRAKLOAK, DRAGAPULT_EX):
                return 51000, "play Latias (Skyliner)"
            return -1, "Latias: not needed"
        if cid == BUDEW:
            if fc[BUDEW] == 0 and fc[DRAGAPULT_EX] == 0:
                return 52000, "play Budew (item lock)"
            return -1, "Budew: not needed"
        if cid == MEOWTH_EX:
            if obs.current.supporterPlayed or p["stadium_id"] == WATCHTOWER:
                return -1, "Meowth: blocked"
            if p["support_count"] == 0:
                return 50000, "play Meowth ex (fetch supporter)"
            if p["support_count"] == hc[BOSS] and not self.plan_a["attack"] <= 0:
                return 50000, "play Meowth ex (fetch non-Boss)"
            return -1, "Meowth: hold"
        if cid == RARE_CANDY:
            if p["no_more_dex"]:
                return -1, "Rare Candy: enough dex"
            if (self.flags["active_route"] and p["active_id"] == DRAKLOAK
                    and hc[DRAGAPULT_EX] <= 1):
                # R-30: 手札のドラパルトが最後の1枚 → アメで別の Dreepy に進化させると
                # バトル場の「この番撃てる」ルートが消える。直接進化で済ませアメも温存。
                return -1, "R-30: hold candy (evolve active directly)"
            return 75000, "S-3: Rare Candy"
        if cid == UNFAIR_STAMP:
            # div-D8（2026-07-11 実測 07-08）: human はスタンプを Recon 特性より先に打つ
            # （precedence 34/18。相手の手札干渉+自分5ドローを先に済ませてから山を掘る）。
            # 15000 → 57000（evo_drak 58000 の下・ability 56000 の上）。
            # ハンマー→スタンプの precedence 8/4 とは非推移だが n=12 と薄く、34/18 を優先。
            return 57000, "E-5: Unfair Stamp"
        if cid == NIGHT_STRETCHER:
            if card_score >= 18000:
                return 42000, "Night Stretcher: recover"
            return -1, "Night Stretcher: nothing"
        if cid == CRUSHING_HAMMER:
            # div-D5（2026-07-11 実測 07-08。設計md 未決事項1の解消）: 40000 は毎ターン
            # 最優先グッズ級で過大。human は特性/進化/エネ付け/夜のタンカ/サポートの後に打つ
            # （precedence: attach が先 53/5、ability が先 110/31、night が先 16/4、
            # サポートが先 5/0。我々のハンマー選択のうち human 不実行 52件）。
            # 40000 → 17000（attach 帯 18000-45450 の下・Unfair Stamp 15000 の上。
            # ハンマー→スタンプの順は precedence 8/4）。
            return 17000, "E-4: Crushing Hammer"
        if cid == BOSS:
            if cid == self.use_support:
                return 35000, "R-16: Boss (plan target)"
            return -1, "R-16: hold Boss"
        if cid == LILLIE:
            if cid == self.use_support:
                return 14000, "Lillie (chosen supporter)"
            return -1, "Lillie: other supporter"
        if cid == WATCHTOWER:
            if p["stadium_id"] > 0 or obs.current.turn == 1:
                return 80000, "play Watchtower"
            return -1, "Watchtower: hold"
        # ルール12+【ソフト・ユーザー 2026-07-26】ポフィンは**いついかなるときも即プレイ**。
        # ルール7の意図は「グッズが要求札に足りない時に先に要求を埋める」であって、ポフィンは
        # 要求札そのもの。ドロンチが立った後も温存する利得は無く、山の圧縮も兼ねる。旧実装は
        # R-11（deckCount<=8）が先に効いて終盤ずっと握っていたので、判定を R-11 より**上**へ。
        # 例外は対LOのみ（自山を削るのが致命的、R-28 同条件）。
        # 的の勘定に Budew(HP30) を含める: ポフィンは HP70 以下のたね2枚なので Budew も対象で、
        # 旧実装（deck[DREEPY] のみ）はドラメシヤを引き切った後のポフィンを死に札にしていた。
        if cid == POFFIN and DRA_POFFIN_ALWAYS:
            if deck[DREEPY] + deck[BUDEW] <= 0:
                return -1, "Poffin: no target"
            if p["no_draw"] and self.t["matchup"] in mt.LO_ARCHETYPES:
                return -1, "R-11: deck thin (LO only)"
            return 46000, "rule12+: Poffin (always play, never hold)"
        if p["no_draw"]:
            return -1, "R-11: deck thin (draw item/supporter)"
        if cid == POFFIN:
            if deck[DREEPY] > 0:
                return 46000, "S-2: Poffin"
            return -1, "Poffin: no target"
        if cid == ULTRA_BALL:
            # U-3【ユーザー仕様 2026-07-27】3条件の積で行使する
            if DRA_UB_DEMAND:
                target, g = self._ub_best_target(obs, p)
                if target is None or g < UB_G_MIN:
                    return -1, "U-3: Ultra Ball hold (no immediate demand / covered by free search)"
                if len(self._ub_payable(obs, p)) < 2:
                    return -1, "U-3: Ultra Ball hold (cannot pay 2 spare cards)"
                return 44000, "U-3: Ultra Ball (demand + no cheaper route + spare pay)"
            # U-2【ユーザー仕様 2026-07-27・簡潔版】保険が残るなら打つ
            if DRA_UB_INSURANCE:
                ok, why = self._ub_insurance_ok(obs, p)
                return (44000, why) if ok else (-1, why)
            # U-1【ユーザー仕様 2026-07-27】収支で打つ: C（最もリスクの小さい2枚）<= G
            if DRA_UB_LEDGER:
                gain = self._ub_fetch_gain(obs, p)
                if gain <= 0:
                    return -1, "U-1: Ultra Ball (nothing worth fetching)"
                cost, _picked = self._ub_cheapest_two(obs, p)
                if cost is None:
                    return -1, "U-1: Ultra Ball (cannot pay 2)"
                if cost <= gain:
                    return 44000, "U-1: Ultra Ball (cost<=gain)"
                return -1, "U-1: Ultra Ball hold (cost>gain)"
            # R-13+②: ハイパーボールは**グッズの最後**（41000 = ポフィン46000・ポケパッド
            # 45000・夜のタンカ42000 の下）。他のグッズを打ち切ってから打てば、手札に残るのは
            # 即プレイ不能札だけになり、切るコストが最小になる。
            # 発火条件も「切れる札（＝即プレイ不能札）が2枚あるか」で定義する。
            if DRA_PLAYABLE_NOW and DRA_UB_LAST:
                hand_ids_ = [c.id for c in (my_state(obs).hand or []) if c is not None]
                if ULTRA_BALL in hand_ids_:
                    hand_ids_.remove(ULTRA_BALL)     # 打つ1枚は勘定から外す
                spare = sum(1 for x in hand_ids_ if not self._playable_now(obs, x))
                if spare >= 2:
                    return 41000, "S-4/R-13+: Ultra Ball (last item, cut non-playable)"
                return -1, "Ultra Ball: hold (fewer than 2 spare cards)"
            if p["negative_hand"] >= 2:
                return 44000, "S-4: Ultra Ball"
            return -1, "Ultra Ball: hold"
        if cid == POKE_PAD:
            if deck[DREEPY] + deck[DRAKLOAK] > 0:
                return 45000, "S-4: Poke Pad"
            return -1, "Poke Pad: no target"
        if cid in (CRISPIN, BROCK):
            if cid == self.use_support:
                return 35000, "S-4/S-5: chosen supporter"
            return -1, "supporter: not chosen"
        # div-D6（2026-07-11 実測 07-08）: リスト外カード（上位ピロットの変種デッキを
        # リプレイするときだけ発生。自デッキ60枚は全て上の分岐で採点済み）が 0 だと
        # END(0) と同点でインデックス順により先に選ばれていた（human=END / ours=PLAY/
        # Jamming Tower 等）。END より下げ「知らないカードは切らずにターンを終える」に揃える。
        return -0.5, "div-D6: unknown card (below END)"

    # ── ATTACH（S-5 + R-10 + ptcg-abc 修正④） ──

    def _attach_score(self, obs, p, attach_id, pokemon, active):
        data = CARD_DB.get(attach_id)
        if data is not None and data.cardType == CardType.TOOL:
            return 60000 + (1000 if active else 0)

        # エネルギー付与
        e = len(pokemon.energies or [])
        if e >= LINE_MAX_COST.get(pokemon.id, 2):
            return -1   # R-10【ハード】: ライン最大コストを満たしたら付与禁止
        f = self.flags
        ms = my_state(obs)
        if pokemon.id == BUDEW:
            return -1
        # DRA_BUDEW_OPEN: 開幕ロックのため、バトル場に退却分の1エネを供給（ベンチ充電
        # 20120 より上に置いてバトル場へ確実に乗せる。退却で捨てる前提の1エネ = ユーザー
        # 肯定の無理攻め。この番ダイブ不可・スボミー待機の開幕のみ発火）
        # 【バグ修正 2026-07-27】この行だけタプルを返していた（`_attach_score` の他の全分岐は
        # スカラー）。呼び出し側 `_score_any` が `((20500, "..."), "S-5: attach")` を返し、
        # `score_option` が TypeError → R-01 が -999999 を割り当てるため、**開幕ロックのための
        # 最優先付与が「絶対に選ばれない手」に反転していた**。`_best_attach` の max() も同じ
        # 例外を踏むので、開幕のエネ手札評価と付け先選択まで巻き添えになる。
        # ⇒ DRA_BUDEW_OPEN は 07-24 の採用時からこの状態で測られている（要・再計測）。
        if p.get("budew_open") and active and e == 0:
            return 20500
        if pokemon.id in (MEOWTH_EX, FEZANDIPITI_EX, LATIAS_EX):
            if active and not f["can_switch"] and not ms.asleep and not ms.paralyzed:
                return 22000 if (p["bench_attacker"] or p["fc"][BUDEW] >= 1) else 18000
            return -1
        if active and f["can_main_attack"]:
            return -1
        # DRA_CONCENTRATE（2026-07-24 ユーザー指示）: 常にファントムダイブ（{R}{P}×2）を
        # 狙う — 充電途中（e==1）のライン個体がいる間、別個体（e==0）への新規付与 =
        # **エネ分散を禁止**する。分散を許可するのは「この番のドラパルト化が確定不可能」
        # な時だけ: 手札にドラパルト無し ∧ 掘り札（DIG_OUT_IDS）も無し。リーリエ等が
        # 残っている手札はまだ確定しない（ユーザー観測の事故: 炎1のドロンチを横目に
        # 別ドロンチへ手張り = 従来は e==0 の +120 が e==1 継続の −120 に勝っていた）。
        # 場のドラパルト ex 本体への付与は常に「ダイブ狙い」なので対象外。
        if (DRA_CONCENTRATE and e == 0 and pokemon.id != DRAGAPULT_EX):
            charged = any(
                pk is not pokemon and pk.id in DRAGAPULT_LINE
                and len(pk.energies or []) == 1
                for pk in all_my_pokemon(obs))
            if charged:
                hc = p["hc"]
                not_final = (hc[DRAGAPULT_EX] >= 1
                             or any(hc[c] >= 1 for c in DIG_OUT_IDS))
                if not_final:
                    return -1   # 分散禁止（集中先が生きている間は手張りを温存してよい）
        score = 20000
        if e == 1:
            if pokemon.energyCards and attach_id == pokemon.energyCards[0].id:
                return -1   # 同色2枚目は不要（Phantom Dive は {R}{P} の2色）
            if pokemon.id == DRAGAPULT_EX:
                score += 250
            elif pokemon.id == DRAKLOAK:
                score -= 120   # div-D7: Drakloak > Dreepy（下記）
            elif pokemon.id == DREEPY:
                score -= 150
            else:
                score -= 200
            if active:
                score += 200
        else:   # e == 0
            if active:
                if p["bench_attacker"]:
                    score += 400
            else:
                if pokemon.id == DRAGAPULT_EX:
                    score += 150
                elif pokemon.id == DRAKLOAK:
                    # div-D7（2026-07-11 実測 07-06/07-07/07-08/07-09 全日）: human の
                    # エネ手張り先は Drakloak > Dreepy（次ターン Dragapult ex になる個体へ
                    # 先行チャージ。human=ATTACH->Drakloak / ours=->Dreepy が4日間同方向）。
                    # 旧: Drakloak は else 束(+50) で Dreepy(+100) より下だった。
                    score += 120
                elif pokemon.id == DREEPY:
                    score += 100
                else:
                    score += 50
                if p["bench_attacker"]:
                    score -= 200
        if pokemon.id == DRAGAPULT_EX and e < 2:
            score += 25000   # ptcg-abc 実測修正④: Phantom Dive 起動を最速化
        if p["no_more_dex"] and pokemon.id in (DREEPY, DRAKLOAK):
            score -= 500
        return score

    def _best_attach(self, obs, p, attach_id):
        """S-6: attach_id を場に付けるときの最良 S-5 価値（付け先だけ最適化した値）。"""
        ms = my_state(obs)
        best = -10000
        for pk in ms.active:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, True))
        for pk in ms.bench:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, False))
        return best

    # ── 手札価値（サンプル hand_score の移植。PLAY/サーチ/DISCARD の共通材料） ──

    # ═══════════ R-13+: 「この番に即プレイできるか」（切る/呼ぶ/打つ順の共通述語） ═══════════

    def _playable_now(self, obs, cid):
        """手札の cid を【この番のうちに】場へ出せるか。

        判定はエンジンの選択肢（合法手）が根拠。ただしサポートだけは1番1枚の制約があるので、
        「この番打つと決めた1枚」以外は即プレイ不能として扱う（ユーザー 2026-07-26:
        リーリエを打つと決まっているなら他のサポートは積極的に切ってよい）。"""
        # ふしぎなアメの例外【ユーザー 2026-07-26】: アメは「ハイパーボールで持ってくる札で
        # 即プレイ可能になるならホールド」。むしろアメが手札にある時は2進化を能動的に掘って
        # 同ターンに同時プレイするのが正解。素の合法性判定だと、ドラパルト ex が手札に無い間
        # ずっと「即プレイ不能」になって切られてしまう。
        if cid == RARE_CANDY and DRA_CANDY_HOLD:
            pp = self.p or {}
            hc2, deck2 = pp.get("hc") or {}, pp.get("deck_counts") or {}
            if (pp.get("can_evolve_dreepy")
                    and (hc2.get(DRAGAPULT_EX, 0) >= 1 or deck2.get(DRAGAPULT_EX, 0) >= 1)):
                return True
        if cid is None or cid not in (self._playable_ids or ()):
            return False
        data = CARD_DB.get(cid)
        if data is not None and data.cardType == CardType.SUPPORTER:
            return (not obs.current.supporterPlayed) and cid == self.use_support
        return True

    def _fetch_playable_now(self, obs, p, cid):
        """ハイパーボール等で山から**手札に取った直後にそのまま場へ出せる**カードか。

        たね = ベンチに空きがあれば可。進化カード = 対応する進化元が場にいる（またはドラメシヤ
        + ふしぎなアメ）なら可。手札で腐る2進化を掘らないための判定。"""
        data = CARD_DB.get(cid)
        if data is None or int(getattr(data, "cardType", -1)) != int(CardType.POKEMON):
            return False
        ms = my_state(obs)
        hc = p["hc"]
        if cid == DRAKLOAK:
            return bool(p["can_evolve_dreepy"])
        if cid == DRAGAPULT_EX:
            return bool(p["can_evolve_drakloak"]
                        or (p["can_evolve_dreepy"] and hc[RARE_CANDY] >= 1))
        # たね: ベンチに空きがあるか
        return len(ms.bench or []) < getattr(ms, "benchMax", 5)

    # ═══════════ U-2: ハイパーボールの保険則（ユーザー仕様・簡潔版） ═══════════

    def _ub_pay_rank(self, obs, p, cid, n_left_after):
        """切ってよい札か。切ってよいなら順位（小さいほど先に切る）、駄目なら None。

        `n_left_after` = **この1枚を切った後に手札へ残る同名の枚数**。

        ユーザー列挙の4種のみを支払い原資とする。ここに無い札（線のポケモン・エネ・
        アメ・スタンプ等）は**そもそも支払いに使わない** = 焼かれない。
        順位は「失っても痛くない順」: 死にグッズ → 中盤ポフィン → 余分なUB → 非ドロサポ。"""
        if cid in DRAW_SUPPORTER_IDS:
            # 【2026-07-27 ユーザー訂正】悪手は「ドロサポを切って手札に1枚も残らない」こと。
            # よって守るのは**最後の1枚だけ**で、2枚目以降は普通に支払ってよい。
            # （旧実装はこれを『ドロサポを持っていること』という発火条件にしてしまい、
            #   保険が無いときほど掘れないという逆立ちしたルールになっていた）
            return None if n_left_after <= 0 else 3
        data = CARD_DB.get(cid)
        if data is None:
            return 0                         # リスト外の未知カードは最優先で切る
        ctype = data.cardType
        if ctype == CardType.SUPPORTER:
            return 3                         # ① ドロサポ以外のサポート
        if cid == ULTRA_BALL:
            return 2                         # ② 余分なハイパーボール
        if cid == POFFIN:
            # ④ 中盤以降のポフィン（的が尽きていれば序盤でも死に札）
            if p["deck_min"][DREEPY] + p["deck_min"][BUDEW] <= 0:
                return 0
            return 1 if self.t["phase"] != "setup" else None
        if ctype in (CardType.ITEM, CardType.TOOL, CardType.STADIUM):
            # ③ 即プレイできないグッズ
            if cid in (self._playable_ids or ()):
                return None                  # この番打てる = 使う札
            if DRA_UB_DEADITEM and not self._ub_item_dead(obs, p, cid):
                return None                  # 打てないだけで死んではいない（アメ等）
            return 0
        return None                          # ポケモン・エネ・その他は支払いに使わない

    def _ub_item_dead(self, obs, p, cid):
        """このグッズは**今後も**仕事が無いか（発動条件が二度と来ないか）。

        「この番打てない」と「死んでいる」は別物。アメは進化元が揃えば打てるし、タンカは
        トラッシュが肥えれば打てる。ここで死と判定するのは条件が復活し得ないものだけ。"""
        osn = opp_state(obs)
        dmin = p["deck_min"]
        if cid == RARE_CANDY:
            return bool(p["no_more_dex"])
        if cid == NIGHT_STRETCHER:
            return not any(p["dc"][i] >= 1 and CARD_DB.get(i) is not None
                           and CARD_DB.get(i).cardType in (CardType.POKEMON,
                                                           CardType.BASIC_ENERGY)
                           for i in list(p["dc"].keys()))
        if cid == POKE_PAD:
            return (dmin[DREEPY] + dmin[DRAKLOAK] + dmin[DRAGAPULT_EX]) <= 0
        if cid == CRUSHING_HAMMER:
            return not any(len(pk.energies or []) >= 1
                           for pk in ((osn.active or []) + (osn.bench or [])) if pk)
        if cid == UNFAIR_STAMP:
            return len(osn.prize) <= 1       # ACE SPEC。詰めに使うので基本は死なない
        if cid == WATCHTOWER:
            return p["stadium_id"] == WATCHTOWER
        return True                          # それ以外の打てないグッズは死んでいる扱い

    def _ub_target_gain(self, obs, p, cid):
        """U-3 の需要 G: この札を**今**手に入れると、この番の行動がどれだけ変わるか。

        ユーザー定義の2軸で測る:
          (a) ダイブが確定するか / 近づくか
          (b) ドロンチにつながるか（＝エンジンが回るか）
        この番に使えない札は加速ゼロ（今取っても後で取っても同じ）。"""
        ms = my_state(obs)
        fc, hc = p["fc"], p["hc"]
        bench_room = len(ms.bench or []) < getattr(ms, "benchMax", 5)

        if cid == DRAGAPULT_EX:
            if p["no_more_dex"]:
                return 0.0
            # (a) この番ドラパルト化できる = ダイブに直結
            if p["can_evolve_drakloak"]:
                return 100.0
            if p["can_evolve_dreepy"] and hc[RARE_CANDY] >= 1 and not p["no_item"]:
                return 100.0
            return 10.0                       # 進化先が無い = 手札で待つだけ（加速しない）
        if cid == DRAKLOAK:
            # (b) エンジン。**この番進化できるなら偵察指令が同ターンに回る**ので、
            #     ドローが増える + 線が1歩進む の二重利得。ダイブ確定の一歩手前でもある。
            if p["can_evolve_dreepy"]:
                return 90.0 if fc[DRAKLOAK] + fc[DRAGAPULT_EX] == 0 else 75.0
            return 15.0
        if cid == DREEPY:
            # (b) の土台。次の番のドロンチになる。盤面が薄いときだけ需要がある
            if bench_room and p["main_pokemon_count"] < 3:
                return 45.0
            return 5.0
        if cid == MEOWTH_EX:
            # サポートを作る = 実質ドロサポ。詰まっている番の脱出
            if (not obs.current.supporterPlayed and bench_room
                    and p["stadium_id"] != WATCHTOWER and p["support_count"] == 0):
                return 55.0
            return 5.0
        if cid == BUDEW:
            if bench_room and obs.current.turn <= 2 and fc[BUDEW] == 0:
                return 45.0
            return 5.0
        if cid == LATIAS_EX:
            if bench_room and fc[LATIAS_EX] == 0 and p["active_id"] not in DRAGAPULT_LINE:
                return 40.0
            return 5.0
        if cid == FEZANDIPITI_EX:
            return 40.0 if (bench_room and p["pre_ko"] and fc[FEZANDIPITI_EX] == 0) else 5.0
        return 0.0

    def _ub_free_searcher_covers(self, obs, p, cid):
        """② 同じ的を、**今手札にある無料の札**で取れるか。

        ポフィン = HP70以下のたね2体をベンチへ（ドラメシヤ・スボミー）
        ポケパッド = **ルールボックスを持たない**ポケモン1体を手札へ（ex には届かない）
        どちらも手札を1枚も切らないので、届くならハイパーボールを使う理由が無い。"""
        data = CARD_DB.get(cid)
        if data is None:
            return False
        is_ex = bool(getattr(data, "ex", False) or getattr(data, "megaEx", False))
        if p["hc"][POFFIN] >= 1 and POFFIN in (self._playable_ids or ()):
            if bool(getattr(data, "basic", False)) and (getattr(data, "hp", 0) or 0) <= 70:
                return True
        if p["hc"][POKE_PAD] >= 1 and POKE_PAD in (self._playable_ids or ()):
            if not is_ex:
                return True
        return False

    def _ub_best_target(self, obs, p):
        """行使する価値のある最良の的と、その G を返す（②で代替可能な的は除外）。"""
        best, best_g = None, 0.0
        for cid, n in (p["deck_min"] or {}).items():
            if n <= 0:
                continue
            data = CARD_DB.get(cid)
            if data is None or int(getattr(data, "cardType", -1)) != int(CardType.POKEMON):
                continue
            g = self._ub_target_gain(obs, p, cid)
            if g <= 0 or self._ub_free_searcher_covers(obs, p, cid):
                continue
            if g > best_g:
                best, best_g = cid, g
        return best, best_g

    def _ub_payable(self, obs, p):
        """支払いに使える札を「先に切る順」に並べて返す。

        同名が複数ある札は**枚数ぶん逐次**に見る（1枚目を切ると残数が減るため）。
        これにより「リーリエ2枚なら1枚は払える、最後の1枚は払えない」が自然に出る。"""
        ms = my_state(obs)
        remain = {}
        for c in (ms.hand or []):
            if c is not None:
                remain[c.id] = remain.get(c.id, 0) + 1
        if remain.get(ULTRA_BALL, 0) > 0:
            remain[ULTRA_BALL] -= 1          # 打つ1枚は支払いに数えない
        out = []
        for cid, n in remain.items():
            for k in range(n):
                r = self._ub_pay_rank(obs, p, cid, n - k - 1)
                if r is None:
                    break                    # 以降の同名も切れない（最後の1枚保護）
                out.append((r, cid))
        out.sort()
        return out

    def _ub_insurance_ok(self, obs, p):
        """U-2 の発火判定: **切ってよい札が2枚あるか**、それだけ。

        ドロサポの保護は支払い側（`_ub_pay_rank`）に閉じており、ゲートは関与しない。
        戻り値 (打てるか, 理由)。"""
        if len(self._ub_payable(obs, p)) < 2:
            return False, "U-2: Ultra Ball hold (cannot pay 2 spare cards)"
        return True, "U-2: Ultra Ball (2 spare cards, last draw supporter kept)"

    # ═══════════ U-1: ハイパーボール収支（打つ判断と支払いの共通基盤） ═══════════

    def _ub_plan(self, obs, p, cid):
        """(必要枚数, 1枚あたりの価値)。

        【地平線の切り分け（2026-07-27 実測を受けた修正）】
        当初は必要枚数も2ターン地平線で数えたが、それだとボスの指令が序盤に need=0 と
        なって余剰判定され、**終盤に吊るための札を焼いていた**（実測 0.45回/試合。
        ドラパルト ex 0.29・アメ 0.24 も同様）。切ることは不可逆なので:
          - **必要枚数 = 試合終了までに使う枚数**（捨てたら二度と戻らないから）
          - **2ターン地平線がかかるのはサポートの budget** = 2ターンで2枚しか打てない
            というルール上の制約。これは事実であって見積りではない。
        両者は `_ub_discard_cost` で合流する（枠内なら守る／枠外でも最後の1枚なら守る）。

        「今プレイできるか」は依然として一切見ない（それが 07-27 の失敗の原因）。"""
        fc, hc, deck, dc = p["fc"], p["hc"], p["deck_counts"], p["dc"]
        osn = opp_state(obs)
        line_bodies = [pk for pk in all_my_pokemon(obs)
                       if pk is not None and pk.id in DRAGAPULT_LINE]
        n_line = len(line_bodies)
        best_e = max((len(pk.energies or []) for pk in line_bodies), default=0)

        if cid == DRAGAPULT_EX:
            # 試合を通して「もう1体」を欲しがり続ける（KO されれば即要る）。
            # 余っている間は reach 側でコスト0になるので、実質「最後の1枚を守る」。
            return (0, UB_V_DEAD) if p["no_more_dex"] else (1, UB_V_CORE)
        if cid == DRAKLOAK:
            return (0, UB_V_DEAD) if p["no_more_dex"] else (1, UB_V_LINE)
        if cid == DREEPY:
            return (0, UB_V_DEAD) if p["no_more_dex"] else (1, UB_V_LINE)
        if cid == RARE_CANDY:
            # アメは「線をもう1本立てる」計画が生きている限り、いつ使うか未定でも要る
            return (0, UB_V_DEAD) if p["no_more_dex"] else (1, UB_V_LINE)
        if cid == BOSS:
            if not (osn.bench or []):
                return 0, UB_V_DEAD          # 吊る的が居ない = 死に札
            # 吊る番は未定でも、試合中に必ず1回は要る札（終盤の詰め）
            value = UB_V_CORE if (self.plan_a["attack"] > 0
                                  or len(osn.prize) <= 3) else UB_V_LINE
            return 1, value
        if cid == CRISPIN:
            # エネ供給が要る間（山にエネが無ければ死に札）
            if deck[FIRE_ENERGY] + deck[PSYCHIC_ENERGY] <= 0:
                return 0, UB_V_DEAD
            return 1, (UB_V_CORE if best_e < 2 else UB_V_LINE)
        if cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
            # 主戦力を {R}{P} にするのに、その色があと何枚要るか
            have = set()
            if line_bodies:
                top = max(line_bodies, key=lambda pk: len(pk.energies or []))
                have = {c.id for c in (top.energyCards or []) if c is not None}
            return (0 if cid in have else 1), UB_V_LINE
        if cid == POFFIN:
            if deck[DREEPY] + deck[BUDEW] <= 0:
                return 0, UB_V_DEAD          # 的が尽きた = 死に札（プレイ可能でもコスト0）
            return (1 if n_line < 3 else 0), UB_V_AID
        if cid == POKE_PAD:
            if deck[DREEPY] + deck[DRAKLOAK] + deck[DRAGAPULT_EX] <= 0:
                return 0, UB_V_DEAD
            return 1, UB_V_AID
        if cid == NIGHT_STRETCHER:
            live = any(dc[i] >= 1 and CARD_DB.get(i) is not None
                       and CARD_DB.get(i).cardType in (CardType.POKEMON,
                                                       CardType.BASIC_ENERGY)
                       for i in list(dc.keys()))
            return (1 if live else 0), UB_V_AID
        if cid == ULTRA_BALL:
            return (1 if self.t["phase"] == "setup" else 0), UB_V_AID
        if cid == UNFAIR_STAMP:
            return (1 if (p["pre_ko"] or len(osn.prize) <= 2) else 0), UB_V_LINE
        if cid == BUDEW:
            return (1 if (obs.current.turn <= 2 and fc[BUDEW] == 0) else 0), UB_V_AID
        if cid == MEOWTH_EX:
            return (1 if p["support_count"] == 0 else 0), UB_V_AID
        if cid == FEZANDIPITI_EX:
            return (1 if p["pre_ko"] else 0), UB_V_AID
        if cid == LATIAS_EX:
            need = 1 if (fc[LATIAS_EX] == 0
                         and p["active_id"] not in DRAGAPULT_LINE) else 0
            return need, UB_V_AID
        if cid == CRUSHING_HAMMER:
            live = any(len(pk.energies or []) >= 1
                       for pk in ((osn.active or []) + (osn.bench or [])) if pk)
            return (1 if live else 0), UB_V_AID
        if cid == WATCHTOWER:
            return (1 if (p["stadium_id"] not in (0, WATCHTOWER)) else 0), UB_V_AID
        if cid in (LILLIE, BROCK):
            return 1, UB_V_AID               # 実際の要否は supporter budget 側で決まる
        return 0, UB_V_DEAD                  # リスト外 = 切ってよい

    def _ub_supporter_budget(self, obs):
        """2ターン地平線でまだ打てるサポートの枚数（この番の未使用分 + 次の番の1枚）。"""
        return (0 if obs.current.supporterPlayed else 1) + 1

    def _ub_protected_supporters(self, obs, p, working_hc):
        """手札のサポートのうち、budget 枠に入る（＝守る）カードidの多重集合。

        枠から溢れたサポートは**論理的に余剰**（2ターン以内に打てない）のでコスト0。
        どれが枠に入るかは `_ub_plan` の価値順で決める。"""
        cards = []
        for cid, n in working_hc.items():
            if n <= 0:
                continue
            data = CARD_DB.get(cid)
            if data is None or data.cardType != CardType.SUPPORTER:
                continue
            need, value = self._ub_plan(obs, p, cid)
            cards.extend([(value if need > 0 else 0, cid)] * n)
        cards.sort(reverse=True)
        keep = {}
        for _, cid in cards[:self._ub_supporter_budget(obs)]:
            keep[cid] = keep.get(cid, 0) + 1
        return keep

    def _ub_discard_cost(self, obs, p, cid, working_hc, protected):
        """この1枚を切ったときに壊れる計画の価値（U-1 の共通コスト関数）。

        必要枚数（2ターン地平線）> 失った後の到達可能枚数  →  価値、そうでなければ 0。"""
        data = CARD_DB.get(cid)
        need, value = self._ub_plan(obs, p, cid)
        # R-32: 「代えが効く」の主張は **下限** で見る（サイド落ちしている可能性のある
        # 山の枚数を当てにして最後の1枚を切ると、代えが来ない事故になる）
        deck, dc = p["deck_min"], p["dc"]
        if data is not None and data.cardType == CardType.SUPPORTER:
            # サポートは2つの制約が合流する:
            #   ① budget 枠内（2ターン以内に打つ予定がある）→ 守る
            #   ② 枠外でも、それが**最後の1枚**で計画がまだ必要とするなら守る
            #      （ボスの指令は吊る番が未定でも試合中に必ず要る = 焼いてはいけない）
            if protected.get(cid, 0) > 0:
                return float(value)
            if need <= 0:
                return 0.0
            reach = (working_hc.get(cid, 0) - 1) + deck.get(cid, 0)
            return 0.0 if reach >= need else float(value)
        if need <= 0:
            return 0.0
        reach = (working_hc.get(cid, 0) - 1) + deck.get(cid, 0)
        # 夜のタンカ割引（ユーザー決定）: ポケモン/基本エネは回収可能。切った1枚自身も
        # トラッシュに入るので対象に含める。上限はタンカの枚数（1枚につき1枚）。
        if data is not None and data.cardType in (CardType.POKEMON,
                                                  CardType.BASIC_ENERGY):
            stretchers = working_hc.get(NIGHT_STRETCHER, 0) + deck.get(NIGHT_STRETCHER, 0)
            reach += min(stretchers, dc.get(cid, 0) + 1)
        return 0.0 if reach >= need else float(value)

    def _ub_cheapest_two(self, obs, p):
        """最もリスクの小さい2枚を**逐次**選び、(合計コスト, [hand index,...]) を返す。

        逐次で選ぶのは論理的必然: 1枚目を切ると2枚目の到達可能枚数が減る
        （例: ボス2枚で必要1枚なら、1枚目は無料だが2枚目は計画を壊す）。"""
        ms = my_state(obs)
        hand = [(i, c.id) for i, c in enumerate(ms.hand or []) if c is not None]
        working = dict(p["hc"])
        # 打つ1枚のハイパーボール自身はコストに数えない
        used_ub = False
        pool = []
        for i, cid in hand:
            if cid == ULTRA_BALL and not used_ub:
                used_ub = True
                working[cid] = working.get(cid, 0) - 1
                continue
            pool.append((i, cid))
        total, picked = 0.0, []
        for _ in range(2):
            if not pool:
                return None, []              # 切る札が足りない = 打てない
            protected = self._ub_protected_supporters(obs, p, working)
            best = None
            for i, cid in pool:
                c = self._ub_discard_cost(obs, p, cid, working, protected)
                if best is None or c < best[0]:
                    best = (c, i, cid)
            total += best[0]
            picked.append(best[1])
            pool = [(i, cid) for i, cid in pool if i != best[1]]
            working[best[2]] = working.get(best[2], 0) - 1
        return total, picked

    def _ub_fetch_gain(self, obs, p):
        """山から持ってくる最良の1枚の価値（G）。

        コスト側と違い、利得側は**テンポの評価**なので「すぐ場に出せるか」を見てよい
        （出せない駒は手札で待つぶん価値が落ちる、という事実の反映）。"""
        best = 0.0
        for cid, n in (p["deck_counts"] or {}).items():
            if n <= 0:
                continue
            data = CARD_DB.get(cid)
            if data is None or int(getattr(data, "cardType", -1)) != int(CardType.POKEMON):
                continue
            need, value = self._ub_plan(obs, p, cid)
            if need <= 0:
                continue
            gain = float(value) if self._fetch_playable_now(obs, p, cid) else value / 2.0
            best = max(best, gain)
        return best

    def _hand_score(self, obs, p, cid, ignore_count):
        fc, hc, deck, dc = p["fc"], p["hc"], p["deck_counts"], p["dc"]
        f = self.flags
        osn = opp_state(obs)
        score = 0
        if cid == DREEPY:
            score = 1000 if p["main_pokemon_count"] >= 3 else 18000
        elif cid == DRAKLOAK:
            score = 20000 if p["can_evolve_dreepy"] else 3000
        elif cid == DRAGAPULT_EX:
            if p["no_more_dex"]:
                score = UNNECESSARY
            elif p["can_evolve_dreepy"] and hc[RARE_CANDY] >= 1 and not p["no_item"]:
                score = 40000
            elif p["can_evolve_drakloak"]:
                score = 30000 if fc[DRAGAPULT_EX] == 0 else \
                    10000 if fc[DRAGAPULT_EX] == 1 else 50
            else:
                score = 50 if fc[DRAGAPULT_EX] >= 2 else 2000
        elif cid == FEZANDIPITI_EX:
            if p["pre_ko"]:
                score = 15000   # ptcg-abc 実測修正②: 50000->15000
            elif p["prize_diff"] <= -2:
                score = 5
            elif len(osn.prize) == 1:
                score = UNNECESSARY
        elif cid == LATIAS_EX:
            if p["active_id"] in (FEZANDIPITI_EX, MEOWTH_EX, DREEPY):
                score = 28000 if fc[DRAKLOAK] + fc[DRAGAPULT_EX] == 0 else 15000
            else:
                score = 10
        elif cid == BUDEW:
            if fc[BUDEW] + fc[DRAKLOAK] + fc[DRAGAPULT_EX] >= 1:
                score = UNNECESSARY
            elif obs.current.turn >= 2:
                score = 30000
        elif cid == MEOWTH_EX:
            if p["support_count"] > hc[BOSS] or p["stadium_id"] == WATCHTOWER:
                score = 5
            elif obs.current.supporterPlayed:
                score = 40
            else:
                score = 35000
        elif cid == RARE_CANDY:
            if p["no_more_dex"]:
                score = UNNECESSARY
            elif p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1:
                score = 40000
        elif cid == UNFAIR_STAMP:
            if p["pre_ko"]:
                score = 80000
            elif len(osn.prize) == 1:
                score = UNNECESSARY
            else:
                score = 80
        elif cid == POFFIN:
            count = deck[DREEPY]
            if count == 0:
                score = UNNECESSARY
            else:
                if obs.current.turn <= 2 and fc[BUDEW] == 0 and deck[BUDEW] >= 1:
                    count += 1
                if count >= 2:
                    score = 35000
        elif cid == NIGHT_STRETCHER:
            for i in list(dc.keys()):
                if dc[i] >= 1:
                    data = CARD_DB.get(i)
                    if data is not None and data.cardType in (CardType.POKEMON,
                                                              CardType.BASIC_ENERGY):
                        score = max(score, self._hand_score(obs, p, i, ignore_count))
        elif cid == CRUSHING_HAMMER:
            score = 20
        elif cid == ULTRA_BALL:
            score = 70 if (p["main_pokemon_count"] <= 2 or fc[DREEPY] >= 1) else 5
        elif cid == POKE_PAD:
            score = max(self._hand_score(obs, p, DREEPY, ignore_count),
                        self._hand_score(obs, p, DRAKLOAK, ignore_count))
        elif cid == LUCKY_HELMET:
            score = 15
        elif cid == BOSS:
            if self.plan_a["attack"] > 0:
                score = 60000   # R-16: 配分プランが吊り出しを要求するときだけ
        elif cid == CRISPIN:
            if not ignore_count or p["support_count"] == 0:
                # 移植ノート3: サンプルのデッド代入を elif に解釈（山にエネ無し -> 10）
                if deck[FIRE_ENERGY] == 0 or deck[PSYCHIC_ENERGY] == 0:
                    score = 10
                elif (not f["can_main_attack"] and not p["bench_attacker"]
                        and fc[DRAGAPULT_EX] >= 1):
                    score = 55000
                else:
                    score = 25000
        elif cid == BROCK:
            if not ignore_count or p["support_count"] == 0:
                if obs.current.turn == 2 and fc[BUDEW] + fc[LATIAS_EX] == 0:
                    score = 50000
                else:
                    score = 30000
        elif cid == LILLIE:
            if not ignore_count or p["support_count"] == 0:
                score = 45000
        elif cid == WATCHTOWER:
            if p["stadium_id"] != 0 and p["stadium_id"] != WATCHTOWER:
                score = 4000
        elif cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
            if f["can_main_attack"] and (len(osn.prize) <= 2
                                         or (p["bench_attacker"] and len(osn.prize) <= 4)):
                score = UNNECESSARY
            else:
                score = self._best_attach(obs, p, cid) - 5000
                if f["can_main_attack"] or p["bench_attacker"]:
                    score /= 10
        if not ignore_count and hc[cid] > 0:
            if cid == DRAKLOAK and hc[cid] < p["evolve_dreepy_count"]:
                score -= 10
            elif cid == DREEPY:
                score -= 100
            else:
                score -= 100000   # 同名2枚目の価値を大きく割引（R-13 の順序側）
        return score

    # ── CARD 選択（前出し・サーチ先・配分・DISCARD 等） ──

    def _score_promote(self, obs, opt):
        """SWITCH / TO_ACTIVE / SETUP_ACTIVE の共通形（サンプルの CARD 分岐移植）。"""
        yi = obs.current.yourIndex
        ctx = obs.select.context
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        card = option_card(obs, opt)
        if card is None:
            return 0, "promote none"
        e = len(getattr(card, "energies", []) or [])
        hp = getattr(card, "hp", 0)
        if pi == yi:
            score = 0
            cid = card.id
            if cid == DREEPY:
                score += 10000
            elif cid == DRAKLOAK:
                score += 20000 if e >= 1 else -10000
            elif cid == DRAGAPULT_EX:
                score += 50000
            elif cid == BUDEW:
                if ctx != SelectContext.SWITCH:
                    score += 100000
                elif not self.p.get("bench_attacker"):
                    score += 30000
            elif cid == FEZANDIPITI_EX:
                score -= 1000
            elif cid == MEOWTH_EX:
                score -= 2000
            score += e * 1000 + hp
            return self.default_score_promote(obs, opt, score, "S-1: promote")   # R-08
        # 相手側の吊り出し（ボスの対象）: 配分プランの対象を最優先
        if self.plan_a["attack"] == opt.index + 1:
            return 100000 + e * 1000 + hp, "R-16: pull plan target"
        return e * 1000 + hp, "pull: energy/hp heuristic"

    @staticmethod
    def _take_band(score):
        """移植ノート4: TO_HAND の負スコアを (0,1) 帯へ圧縮（サーチは常に何か取る）。"""
        if score >= 0:
            return min(score, 900000)
        return (200000 + max(score, -200000)) / 200000.0

    def _score_card(self, obs, opt):
        p = self.p
        ctx = obs.select.context
        card = option_card(obs, opt)
        cid = card.id if card is not None else getattr(opt, "cardId", None)

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            return self._score_promote(obs, opt)

        # D-2: 経路の取得手のサブ選択を pin する（「履歴をなぞる」の後半部分）。
        # 経路の根拠になった取得先を実際に取り、アカマツは経路の色を経路の個体に付ける。
        # これが無いと、UB を打つ判断は経路由来なのに取得先は汎用採点で決まり、
        # 「打つ理由になった札を取らない」不一致が起きる（07-27 の実測事故）。
        if DRA_DIVE_ROUTE and self._dive_fetch is not None:
            f_sid, f_tgt, f_att = self._dive_fetch
            if p["effect_id"] == f_sid:
                if (ctx == SelectContext.TO_HAND and f_tgt is not None
                        and cid == f_tgt):
                    p["hc"][cid] = p["hc"].get(cid, 0) + 1
                    return self._take_band(880000), "D-2: fetch dive-route target"
                if (ctx == SelectContext.TO_HAND and f_att is not None
                        and cid in (FIRE_ENERGY, PSYCHIC_ENERGY)):
                    # アカマツ: 手札に取らなかった色が場に付く（S-6a）→
                    # 場に付けたい色 f_att の**逆色**を手札に取る
                    other = (PSYCHIC_ENERGY if f_att == FIRE_ENERGY
                             else FIRE_ENERGY)
                    if cid == other:
                        p["hc"][cid] = p["hc"].get(cid, 0) + 1
                        return self._take_band(880000), "D-2: Crispin keep other color"
                if (ctx == SelectContext.ATTACH_TO and f_att is not None
                        and cid == f_att):
                    return self._take_band(880000), "D-2: Crispin pick route color"
                if (ctx == SelectContext.ATTACH_FROM and f_att is not None
                        and opt.area == AreaType.ACTIVE
                        and card is not None and isinstance(card, Pokemon)):
                    return self._take_band(880000), "D-2: Crispin attach to active"

        if ctx in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
            if cid is None:
                return 0, "take none"
            score = self._hand_score(obs, p, cid, False)
            p["hc"][cid] += 1
            if p["effect_id"] == CRISPIN:
                if cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
                    # S-6a（2026-07-13 リプレイ84790412）: 手札に取らなかった色（逆色）が
                    # 場に付く。逆色の最良付け先価値（S-5）が高い方を選ぶ。
                    # 逆色が山に残らない色を取ると付与自体が消滅するため降格。
                    other = PSYCHIC_ENERGY if cid == FIRE_ENERGY else FIRE_ENERGY
                    other_left = sum(1 for c in (obs.select.deck or [])
                                     if c is not None and c.id == other)
                    if other_left > 0:
                        score = 100000 + self._best_attach(obs, p, other)
                    else:
                        score = 50
                else:
                    # 変種デッキのリプレイ用フォールバック（旧: 逆順選択）
                    score = 100000 - self._hand_score(obs, p, cid, True)
            # U-3: 取る札は**発火判断と同じ需要関数**で選ぶ（前提と実行の一致）。
            # 「打つ理由になった的」を実際に取ることを構造で保証する。
            if (DRA_UB_DEMAND and ctx == SelectContext.TO_HAND
                    and p["effect_id"] == ULTRA_BALL and cid is not None):
                return (self._take_band(20000 + self._ub_target_gain(obs, p, cid) * 100),
                        "U-3: fetch by immediate demand")
            # R-13+③: ハイパーボールで呼ぶ札も「即プレイできる札」に限る。進化先が場に
            # 無い2進化を掘っても手札で腐り、次のハイパーボールで切る羽目になる。
            if (DRA_PLAYABLE_NOW and ctx == SelectContext.TO_HAND
                    and p["effect_id"] == ULTRA_BALL and cid is not None):
                if self._fetch_playable_now(obs, p, cid):
                    score += 20000
                else:
                    score -= 20000
            if ctx == SelectContext.TO_HAND:
                return self._take_band(score), "S-4: take to hand"
            return min(score, 900000), "S-2: take to bench"

        if ctx in (SelectContext.DISCARD, SelectContext.DISCARD_CARD_OR_ATTACHED_CARD):
            if cid is None:
                return 0, "discard none"
            p["hc"][cid] -= 1
            data = CARD_DB.get(cid)
            if data is not None and data.cardType == CardType.SUPPORTER:
                p["support_count"] -= 1
            score = -self._hand_score(obs, p, cid, False)
            # D-2: 経路が消費する札は支払いから守る（予約）。hc は直上で減算済みなので
            # 「この1枚を切ると残りが予約数を割る」= 経路が壊れる、を検出できる。
            # -400000 は R-13+ keep(-200000) より深く、経路保護が常に勝つ。
            if (DRA_DIVE_ROUTE and self._dive_reserved
                    and p["hc"][cid] < self._dive_reserved.get(cid, 0)):
                # レビュー確定所見（07-28 wf_faed270f）: 旧 -400000 は U-2 の keep 帯
                # （非支払い -1e6 / ドロサポ -2e6）より浅く、複合腕（ROUTE×UB_INSURANCE）で
                # **予約札が非支払い札より先に切られて経路が壊れる**。全 keep 帯の底に置く。
                tie = max(-100000.0, min(100000.0, score)) / 1000.0
                return (-3_000_000.0 + tie, "D-2: keep (dive route reserved)")
            # U-2: 支払いも**発火判断と同じ述語**で選ぶ（前提と実行の一致）。
            # 切ってよい札（ユーザー列挙の4種）を順位どおりに、それ以外は最後まで残す。
            # ドロサポは -1e6 の底に置き、保険が最後まで守られることを構造で保証する。
            if DRA_UB_INSURANCE or DRA_UB_DEMAND:
                # 直上で `p["hc"][cid] -= 1` 済みなので、この値が
                # 「この1枚を切った後に手札へ残る同名の枚数」になる（サンプルの逐次会計）。
                # 2枚目のリーリエは残数1で払える / 最後の1枚は残数0で守られる。
                rank = self._ub_pay_rank(obs, p, cid, p["hc"][cid])
                tie = max(-100000.0, min(100000.0, score)) / 1000.0
                if rank is None:
                    base = -2000000.0 if cid in DRAW_SUPPORTER_IDS else -1000000.0
                    return base + tie, "U-2: keep (not a payment card)"
                return -(rank * 1000.0) + tie, "U-2: pay (spare card)"
            # U-1: 支払いは**発火判断と同じコスト関数**で選ぶ（前提と実行の一致）。
            # コストが主、`-hand_score` は同コスト内の順序付けだけに使う（桁を分離）。
            if DRA_UB_LEDGER:
                protected = self._ub_protected_supporters(obs, p, p["hc"])
                cost = self._ub_discard_cost(obs, p, cid, p["hc"], protected)
                tie = max(-100000.0, min(100000.0, score)) / 1000.0
                return -(cost * 1000.0) + tie, "U-1: discard by plan cost"
            # R-13+①: 切るのは「この番に即プレイできない札」から。即プレイできる札は
            # 一律 200,000 下へ落として最後まで残す（不能札の評価順 = 従来どおり保存される。
            # 不能札のスコアは -80,000 以上なので、この差は必ず勝つ）
            if DRA_PLAYABLE_NOW and self._playable_now(obs, cid):
                return min(score, 900000) - 200000, "R-13+: keep (playable this turn)"
            return min(score, 900000), "R-13: discard lowest value"

        if ctx in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
            return self._score_counter(obs, opt, card, ctx)

        if ctx == SelectContext.DAMAGE:
            return self.default_score_damage_target(obs, opt)   # R-15（Cruel Arrow 等）

        if ctx == SelectContext.ATTACH_TO:
            # S-6b（2026-07-13）: アカマツ等「山から付けるエネ」の選択。自デッキの2色構成では
            # 常に同色のみが候補になるが、S-5 の最良付け先価値で採点しておく（変種リプレイの保険）
            if cid is None:
                return 0, "attach none"
            return self._take_band(self._best_attach(obs, p, cid)), "S-6b: attach energy pick"

        if ctx == SelectContext.ATTACH_FROM:
            # div-D2（2026-07-11 実測 06-30/07-06/07-07/07-08/07-09 全日）: Crispin 等の
            # 「付け先ポケモン選択」が未実装で全候補 10 の同点 → インデックス順になり
            # 一致 0/7(07-07)・7/27(07-08)・0/2(07-09) だった。S-5 の attach 採点に接続。
            # S-6c（2026-07-13）: contextCard に付けるカードが入る（Crispin ならエネの色が判明）
            # ため attach_id に実IDを渡す（旧: 0 固定）。同色2枚目回避 = {R}{P} 成立が効く。
            # （R-10 / Budew 除外は従来どおり。負値は TO_HAND と同じ (0,1) 帯圧縮で
            # 「必ずどれかを選ぶ」を保つ）。
            aid = p["context_card_id"]
            adata = CARD_DB.get(aid)
            if adata is None or adata.cardType not in (CardType.BASIC_ENERGY,
                                                       CardType.TOOL):
                aid = 0
            if card is not None and isinstance(card, Pokemon):
                score = self._attach_score(obs, p, aid, card,
                                           opt.area == AreaType.ACTIVE)
                return self._take_band(score), "div-D2/S-6c: attach target (S-5)"
            return 0, "div-D2: attach target none"

        return 10, "generic card"

    def _score_counter(self, obs, opt, card, ctx):
        """E-2: ダメカン配分（サンプル準拠 + 配分プラン参照）。"""
        if card is None or getattr(card, "hp", 0) <= 0:
            return 0, "counter none"
        hp = card.hp
        score = 100000 - 10 * hp + self._pokemon_score(card, False)
        if ctx == SelectContext.DAMAGE_COUNTER:
            if 210 <= hp <= 230:
                score += 20000 + hp * 20
                if opt.area == AreaType.ACTIVE:
                    score += 10000
            elif 40 <= hp <= 90:
                score += 10000 + hp * 20
            elif hp <= 30:
                score += -10000 + hp * 20
            if card.id in BONUS_COUNTER_TARGETS:
                score += 30000
            return score, "E-2: counter (zone heuristic)"
        if _no_damage_counter(card):
            return -1, "E-2: no-damage-counter guard"
        # DAMAGE_COUNTER_ANY = Phantom Dive の6個配分（座標系: cards[bench_index + 1]）
        if self.USE_SPREAD_SEARCH and self.spread_plan is not None:
            # S-7: 探索計画の「目標残りHP」まで削る。現hp が目標より上なら置く価値
            #（差が大きいほど優先）。目標に達したベンチは 0 帯へ落として次のベンチへ回す。
            tgt = self.spread_plan.get(opt.index + 1)
            if tgt is not None and hp > tgt:
                return score + 100000 + (hp - tgt), "S-7: spread plan target"
            return score, "S-7: spread plan (satisfied/other)"
        if opt.index + 1 in self.plan_b["counter"]:
            score += 100000
            reason = "E-2: plan counter target"
        else:
            remain = (obs.select.remainDamageCounter or 0) * 10
            if 210 <= hp <= 200 + remain:
                score += 30000
            elif 20 <= hp <= 60 + remain:
                score += 10000
            elif hp == 10:
                score -= 100000
            reason = "E-2/R-15: spread heuristic"
        return score, reason


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」を呼ぶ。
# def agent は必ずファイル末尾の callable にする。

_impl = make_agent(DragapultPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
