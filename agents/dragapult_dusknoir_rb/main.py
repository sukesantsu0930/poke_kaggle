"""ドラパルトヨノワール（Dragapult ex + Dusknoir カーズドボム）ルールベースエージェント

土台: agents/dragapult_rb（公式サンプル移植 + div-D2〜D8 + S-7 ばら撒き配分探索）。
新デッキ = ユーザー持参の紙トーナメント実績リスト（decks/candidates/dragapult_dusknoir_paper.csv）。
ラダーに同型 0 件（1761 エピソード採掘）のため divergence 模倣は使えず、ユーザー決定ルールで作る。

設計文書: docs/planning/デッキ設計_ドラパルトヨノワール.md（ユーザー決定ルール 1〜7）
  1. カーズドボムは「KO を取り切れる時だけ」爆発【ハード】（①130単体 ②正面200合算 ③ばら撒き60合算）
  2. 悪エネはマシマシラ専用（貼る先）。再利用可能資源【ソフト】
  3. メイのはげまし = 「使えばドラパルトが技を打てる」局面でリーリエ超え【ソフト・条件付き】
  4. アカマツはドラパルトライン優先、余裕時のみマシマシラ【ソフト】
  5. Risky Ruins は攻撃の直前に張る【ソフト（順序）】
  6. ヒカリ: 基本リーリエ未満。「この番ファントムダイブが打てる ∧ 手札にエネあり」でリーリエ超え【ソフト】
  7. 偵察指令 = 不確定ドロー先・確定サーチ後。ポフィン →（リーリエ）→ 偵察指令 → ポケパッド【ソフト（順序）】

ルールタグ: R-07/R-08/R-10/R-11/R-13/R-15/R-16/R-18/R-21(先攻・旧型 div-D1 継承【暫定】)/R-22/R-26/R-28
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
    LETHAL_BAND,
    active_pokemon,
    all_my_pokemon,
    attack_base_damage,
    damage_on,
    energy_count,
    get_card,
    hand_ids,
    make_agent,
    my_state,
    opp_state,
    option_card,
    option_target,
    read_deck_csv as _read_deck_csv,
    retreat_cost,
)

# ── カードID（デッキ設計_ドラパルトヨノワール.md のリスト） ──

DREEPY = 119            # ドラメシヤ HP70
DRAKLOAK = 120          # ドロンチ HP90（Recon Directive: 上2枚見て1枚）
DRAGAPULT_EX = 121      # ドラパルトex HP320（Phantom Dive 200+ベンチ60配分）
DUSKULL = 131           # ヨマワル HP60
DUSCLOPS = 132          # サマヨール HP90（Cursed Blast: 5個=50 置いて自壊）
DUSKNOIR = 133          # ヨノワール HP160（Cursed Blast: 13個=130 置いて自壊）
MUNKIDORI = 112         # マシマシラ HP110（Adrena-Brain: 悪エネ付きで毎ターン3個移動）
FEZANDIPITI_EX = 140    # Flip the Script / Cruel Arrow
BUDEW = 235             # Itchy Pollen（相手グッズロック）
MEOWTH_EX = 1071        # Last-Ditch Catch（サポートサーチ）
RARE_CANDY = 1079
UNFAIR_STAMP = 1080     # ACE SPEC
POFFIN = 1086
NIGHT_STRETCHER = 1097
ULTRA_BALL = 1121
POKE_PAD = 1152
BOSS = mt.BOSS          # 1182
CRISPIN = 1198          # アカマツ
BROCK = 1210            # タケシのスカウト（山からたね2枚 or 進化1枚を手札へ）
LILLIE = 1227           # リーリエの決心（手札を山へ戻して6ドロー）
DAWN = 1231             # ヒカリ（たね+1進化+2進化サーチ）
ROSA = 1240             # メイのはげまし（サイド負け時のみ・トラッシュから基本エネ2枚を2進化へ）
WATCHTOWER = 1256       # ロケット団の監視塔（{C}特性消し）
RISKY_RUINS = 1260      # 非{D}たねのベンチ着地に2個
FIRE_ENERGY = 2
PSYCHIC_ENERGY = 5
DARK_ENERGY = 7

BASIC_ENERGIES = (FIRE_ENERGY, PSYCHIC_ENERGY, DARK_ENERGY)

ATK_JET_HEADBUTT = 153      # {C} 70
ATK_PHANTOM_DIVE = 154      # {R}{P} 200 + ダメカン6個配分
ATK_ITCHY_POLLEN = 323      # Budew（相手は次の番グッズ不可）

# 相手側の特殊ID（dragapult_rb 準拠）
NO_DAMAGE_DEX = frozenset({158, 207, 330, 345})   # Drednaw/Milotic ex/Sylveon/Crustle（ex打点無効）
NO_DAMAGE_COUNTER_IDS = frozenset({28, 199, 203, 207, 362, 1136})  # ダメカン配置不可
GUARD_ENERGY_IDS = frozenset({11, 20})   # Mist / Rock Fighting（装着でダメカン配置不可）
LEGACY_ENERGY = 12
LILLIES_PEARL = 1172
LOW_VALUE_TARGETS = frozenset({173, 174, 190, 1071})  # Noctowl/Fan Rotom/Archaludon ex/Meowth ex
BONUS_COUNTER_TARGETS = frozenset({133, 351})   # 相手の Dusknoir/Rapidash（優先スナイプ）
LUMIOSE_CITY = 1267

# アタッカー運用ポケモン（S-7 配分探索用。research/meta/attacker_pokemon.md）
ATTACKER_IDS_LEARNED = frozenset({58, 63, 96, 108, 116, 117, 121, 169, 190, 245, 272,
                                  381, 401, 431, 648, 666, 674, 678, 743, 849, 861, 1031})

DRAGAPULT_LINE = frozenset({DREEPY, DRAKLOAK, DRAGAPULT_EX})
# DUSK_CONCENTRATE の「集中先をまだ仕上げられる見込みがあるか」の材料（通常版 DIG_OUT_IDS
# の移植）。手札にこれらがあるうちは、集中先のドラパルト化がまだ確定不可能とは言えない。
# ヒカリは2進化を直接サーチできるので本機では追加（ポフィンはたね専用なので対象外）。
DIG_OUT_IDS = frozenset({ULTRA_BALL, POKE_PAD, LILLIE, CRISPIN, BROCK, NIGHT_STRETCHER, DAWN})
DUSKNOIR_LINE = frozenset({DUSKULL, DUSCLOPS, DUSKNOIR})

# R-10: ライン最大コスト。ボムライン=0（自壊要員にエネは張らない）【ハード】、
# マシマシラ=1（アドレナブレイン起動の悪エネ1枚のみ。ユーザールール2）【ハード】
LINE_MAX_COST = {DREEPY: 2, DRAKLOAK: 2, DRAGAPULT_EX: 2,
                 FEZANDIPITI_EX: 3, MEOWTH_EX: 3, BUDEW: 0,
                 MUNKIDORI: 1, DUSKULL: 0, DUSCLOPS: 0, DUSKNOIR: 0}

UNNECESSARY = -10_000_000

# ── 背骨の組み直し（2026-07-25 ユーザー構想: メインストリーム/サブストリーム × 3フェーズ）──
# 立ち上げ(setup) … ムズムズ花粉ロック + ドロンチ engine(2-3体) を最優先。サブは従属
# 始動(priming)   … ドロンチ着地・ダイブ完成へ最短
# 詰め(online)    … ドラパルト ex 着地・ダイブ稼働。**サブストリーム(カーズドボム/アドレナ)起動**
# 判定は戦績でなく「意図した振る舞いになったか」のプローブで行う（本流が組み上がるまで
# 戦績で判定しない = ユーザー方針。序盤を変えたら中盤以降を紐づけ調整してから測る）。
DUSK_STREAMS = os.environ.get("DUSK_STREAMS", "1") != "0"            # 本流優先・サブ従属の背骨（採用）
DUSK_OPEN_BUDEW = os.environ.get("DUSK_OPEN_BUDEW", "1") != "0"      # 序盤 Poffin で Dreepy+Budew（T1 も）
DUSK_PAD_DRAKLOAK = os.environ.get("DUSK_PAD_DRAKLOAK", "1") != "0"  # Pad→Drakloak（本流 engine の一部として再ON）
# DUSK_BUDEW_OPEN2（2026-07-26）: 通常版 dragapult_rb の DRA_BUDEW_OPEN（EXP-043、
# 対marnie +10.6pt）の移植。開幕にバトル場へ1エネ張って退却 → スボミー前出し → グッズロック。
# 2026-07-26 の 2×2 分解（エージェント×デッキ・各320戦）で、対オーロンゲの通常版との差
# 約20pt のうち **約10pt がエージェント側**と判明し、その主犯としてこの穴を特定した。
# 【既定 OFF・移植したが無効と実測】発火はしている（3.27決定/試合）が、v2 リスト（スボミー2枚）
# では既存 DUSK_OPEN_BUDEW で既にスボミーが前に出ており、ロック回数が増えない
# （1.42→1.36回/試合・対オーロンゲ 320戦 17.5%→17.2%）。トグルとして温存。
DUSK_BUDEW_OPEN2 = os.environ.get("DUSK_BUDEW_OPEN2", "0") != "0"

# DUSK_CONCENTRATE（2026-07-26 ユーザー決定）: エネルギー分散の禁止。
#
# 病理（コード読解＋実測で確定）: `_attach_score` の素点表は e==1（片色済み・あと1枚で
# ファントムダイブが完成する個体）を −120/−150 と減点するため、**未着手の新品**
# （ドロンチ 20120 / ドラメシヤ 20100）が**完成間近の個体**（19880 / 19850）に勝つ。
# 結果、4回に1回の手張りが「完成間近を横目に新しい個体へ着手」になっていた
# （分散事故 24% vs 通常版 3%）。死蔵エネ 1.36個/試合 → {炎}{超}が揃う個体が
# 1.39体（通常版 2.02体）→ ダイブ 1.91回（同 3.04回）→ 対オーロンゲ 18.8%（同 28.4%）。
# 通常版 dragapult_rb は EXP-041 の DRA_CONCENTRATE で同じ穴を塞いでいる（対marnie +9.4pt）
# が、本機は 2026-07-14 の分岐後に入った修正のため未移植だった。
#
# e==1 の減点は「ボスの指令で2エネのドロンチを吊り出されて焼かれる」恐れの現れだが、
# **その心配はまずファントムダイブが撃てることを満たしてから**（ユーザー 2026-07-26）。
# よって散らしてよいのは「散らしてもダイブが確定するとき」だけ = _dive_secured。
DUSK_CONCENTRATE = os.environ.get("DUSK_CONCENTRATE", "1") != "0"

# ── ファントムダイブ「持続 vs 損切り」の 2×2 閾値表（2026-07-25 ユーザー構想）──
# バトル場が準備中（ドラパルト ex e<2 / 掘り進め中ドロンチ）のとき、今ターンにダイブを
# 撃てる確率 P を _dive_prob_this_turn / _dive_prob_drakloak で厳密計算し（deck_counts=
# 掘れる枚数・確定/死に線を含む）、単一閾値と比較。P>=閾値 → 持続（散らさず掘る）/
# P<閾値 → 損切り（エネ分散）。
# 【2026-07-26 統一】旧 2×2(安全な降り先×晒しの痛み) はグリッドサーチ81構成で勝率に無効
# （均等制圧度が全構成 55.0-56.5 で平坦）と実証。さらに両極端の実測で アグレッシブ(常に掘る)
# が全7対面でパッシブ以上・制圧度 57.1% vs 52.9% と判明。→ 2×2 を廃し単一閾値に統一。
# 既定 0.0 = 準備中は常にダイブへ賭ける（＝アグレッシブ・ドラパルト。ユーザー方針 2026-07-26）。
# 値を上げるほどパッシブ（確定に近い時のみ賭ける）。tune したい時はこの1本だけ振る。
DUSK_TH_DIVE = float(os.environ.get("DUSK_TH_DIVE", "0.0"))
# 場のドラパルト線 max 3 は既存の main_pokemon_count>=3 ゲート（_hand_score DREEPY）で
# 既に成立（ユーザー「max 3匹でいい」と一致）。トグル不要 = 現状維持。

# ── 対オーロンゲ（マリィのオーロンゲex）特殊化パッケージ（2026-07-26 ユーザー指示）──
# 設計の不変条件【ハード】: **オーロンゲを認識した試合でしか挙動を変えない**。
# 「オーロンゲデッキ相手にオーロンゲと気づかずにプレイする」のがおかしいのと同様、
# 「オーロンゲでない相手にオーロンゲ用の手を打つ」のもおかしい。よって本パッケージの
# 全ルールは vs_grimmsnarl() ゲートの内側にのみ書く。他対面の A/B が動いたらそれ自体がバグ。
# 検証器 = scripts/dusknoir_gate_invariance.py（非オーロンゲ対面で決定一致率 100% を要求）。
IMPIDIMP = 646                                 # マリィのベロバー HP70（オーロンゲ線のたね）
MORGREM = 647                                  # マリィのギモー HP100
GRIMMSNARL_EX = 648                            # マリィのオーロンゲex HP320・サイド2
GRIMMSNARL_LINE = frozenset({IMPIDIMP, MORGREM, GRIMMSNARL_EX})
DUSK_GRIM = os.environ.get("DUSK_GRIM", "1") != "0"          # パッケージ全体の A/B トグル
# G-1【ハード・ユーザー決定 2026-07-26】カーズドボムはオーロンゲex にしか撃たない。
#   診断（120戦）: ボムの 0.57/試合 が マシマシラ(HP110・サイド1)に消え、正面200と合算して
#   オーロンゲex(HP320・サイド2)を丸取りする mode2 は **0回**。ヨノワール自壊はサイド1献上
#   なので、マシマシラ狩りは 1:1 交換（しかも相手は4枚積み・こちらは2進化を1体消費）＝損。
#   200+130=330 >= 320 が唯一の勝ち交換（+2 −1 = +1）なので、そこまでボマーを温存する。
DUSK_GRIM_BOMB = os.environ.get("DUSK_GRIM_BOMB", "1") != "0"
# G-2 対オーロンゲでは「危ない廃墟」を張らない（ユーザー懸念 2026-07-26）。
#   廃墟は「非{D}のたねがベンチに出るたび2個」。相手のたねは マリィのベロバー={悪} で対象外、
#   マシマシラ/ノコッチだけが食らう。一方こちらは ドラメシヤ(70)/ヨマワル(60)/スボミー(30) が
#   全部食らい、シャドーバレットのベンチ30 + マシマシラのダメカン移動30 の「2回で落ちる」圏へ
#   自分から落ちる。＝相手に有利に働いている疑い。A/B で検証する。
DUSK_GRIM_RUINS = os.environ.get("DUSK_GRIM_RUINS", "1") != "0"
# GL 対オーロンゲの本流モード = 「グッズロック優先」（ユーザー決定 2026-07-26）。
#   このデッキはオーロンゲ(HP320・シャドーバレット180+ベンチ30・マシマシラでダメカン移送)に
#   サイドレースで構造的に負ける（実測 相手4.05 / 自分2.1〜2.4）。テラスタルはワザのダメージ
#   しか防げず、アドレナブレインは「のせ替え」効果なので貫通する＝ベンチ退避で出血は止まらない。
#   残る勝ち筋は むずむずかふん の**グッズロックだけ**。ロックは非対称（相手のグッズだけが
#   止まり、こちらのグッズは通る）なので、ロックできる番はロックが常に正。
#   ※重要な区別: これは 2026-07-26 に棄却済みの「パッシブ(DUSK_TH_DIVE=1.0)」とは別機構。
#     棄却されたのは『準備中に掘り続けるか散らすか』の閾値軸で、こちらは行動優先度の軸。
#   終了ラダー（_compute_grim_mode）: リーサル(既存R-07) > むずむず不可能 > 相手オーロンゲ起動済み
#     > ペイロード完成(ダイブ可∧ヨノワール在場) > ベロバー線枯渇 > それ以外はロック継続。
# 【既定 OFF・2026-07-26 の A/B で棄却】320戦で FULL 11.2% vs 素 16.9%。ロックは
# スボミー枚数に律速され（1.42→1.36回/試合しか増えない）、優先させるとセットアップ資源を
# 食って −5.7pt。機構はトグルとして温存（負の結果の記録）。
DUSK_GRIM_LOCK = os.environ.get("DUSK_GRIM_LOCK", "0") != "0"

# G-3【対オーロンゲ限定】ヨノワールラインを展開しない（2026-07-26）。
#   実測の根拠: 同一の中立デッキ（ボムライン無し）だと本機は 21.0%（1280戦）だが、
#   ボムライン2-2-2 を積んだ v2 では 18.6% に落ちる。ダイブ回数も 2.98 → 1.91 に半減。
#   一方リターン側は、この対面ではボムが取るのはマシマシラ(サイド1)止まりで、自壊で
#   サイド1を返すため収支が 1:1 = ±0。オーロンゲ(320・サイド2)を 200+130 で丸取りできる
#   局面は全試合の17%しか成立しない。
#   → **ボムラインはデッキに残したまま、この対面でだけ展開しない**（他6対面では
#   thwackey 94 / meganium 82 / prism 81 と機能しているので抜かない）。
DUSK_GRIM_NOBOMB = os.environ.get("DUSK_GRIM_NOBOMB", "1") != "0"

# DUSK_RECON_FIRST（2026-07-26 差分マイニング）: 偵察指令（ドロンチ特性）を div-D3 の
# 56000 帯（グッズ・エネ付け・進化より先）へ戻す。**対面非依存の一般ルール**なので
# vs_grimmsnarl() ゲートの外側にある = 全対面の再計測が必要。詳細は _score_any の注記。
# 【既定 OFF・実測で棄却】640戦/腕で 16.1%（ルール7のまま）→ 12.7%（div-D3 に戻す）。
# 「進化前に偵察を使い忘れて特性を捨てている（0.9回/試合）」という読みは立つが、
# それ以上にポフィンの遅延が痛い。**ユーザーのルール7（ポフィン→リーリエ→偵察）が正しい**。
# 通常版との最大の決定差分は、バグではなく意図的かつ妥当な差だったということ。
DUSK_RECON_FIRST = os.environ.get("DUSK_RECON_FIRST", "0") != "0"

# ルール12+（ユーザー 2026-07-26）: ポフィンは温存しない = R-11（山薄）より上で常に即プレイ。
# 対面非依存の一般ルールなので全対面の再計測が要る。
DUSK_POFFIN_ALWAYS = os.environ.get("DUSK_POFFIN_ALWAYS", "1") != "0"

# S-0!（ユーザー 2026-07-26・loss1.json 観戦）: 手番内ファントムダイブ判定を**進化の選択**に
# 繋ぐ。「バトル場のドロンチを進化させればこの番に撃てる」を最優先。対面非依存の一般ルール。
DUSK_DIVE_NOW = os.environ.get("DUSK_DIVE_NOW", "1") != "0"

# R-13+【ユーザー決定 2026-07-26】ハイパーボールの3点セットを「即プレイできるか」で統一する。
#   ① 切る札 = **この番に即プレイできない札**。手札評価の高低ではない。
#      （例: この番リーリエを打つと決まっているなら、他のサポートは全部切ってよい。
#        ドラパルト ex も、進化先が場に無い序盤なら切ってよい。試合が進めば場にドロンチが
#        いて「即プレイできる」側に入るので、自然に切られなくなる）
#   ② ハイパーボール自身の優先度 = **グッズの最後**。他のグッズを打ち切ってから打てば、
#      手札に残るのは即プレイ不能札だけになり、①のコストが最小になる。
#   ③ 呼ぶ札も **即プレイできる札**（進化先が場に無い2進化を持ってきても手札で腐る）。
#   発見の経緯: 実測で ドラパルト ex 0.12/試合・基本エネ 0.33/試合・ポフィン 0.19/試合 を
#   トラッシュしていた。さらに基盤の R-13 ハード保護（default_score_discard の
#   LINE_PROTECT_IDS）はドラパルト系では**一度も呼ばれていない死にコード**だった。
DUSK_PLAYABLE_NOW = os.environ.get("DUSK_PLAYABLE_NOW", "1") != "0"
# ふしぎなアメの例外（ユーザー 2026-07-26）: 「持ってくる札で即プレイ可能になるならホールド」。
# 進化元が場にいて対応する2進化が手札か山にあれば、この番に同時プレイできる = 切らない。
DUSK_CANDY_HOLD = os.environ.get("DUSK_CANDY_HOLD", "1") != "0"
# カナリア（既定OFF・本番挙動に無関与）: ゲート検証器が「検出力があること」を示すための
# 意図的な差分。ON にすると対オーロンゲでだけダイブ閾値がパッシブ(1.0)に変わる。
DUSK_GRIM_CANARY = os.environ.get("DUSK_GRIM_CANARY", "0") != "0"

# リスト A/B 用のフック（2026-07-26）。設定するとその CSV を自デッキ勘定に使う。
# 未設定＝従来どおり deck.csv → DECK_FALLBACK の順（提出物の挙動は不変）。
DECK_CSV_OVERRIDE = os.environ.get("DUSK_DECK_CSV", "")

# デッキリスト（dragapult_dusknoir_paper.csv と同一。deck.csv 不在時のフォールバック）
DECK_FALLBACK = (
    [DREEPY] * 4 + [DRAKLOAK] * 4 + [DRAGAPULT_EX] * 3
    + [DUSKULL] * 2 + [DUSCLOPS] * 2 + [DUSKNOIR] * 2
    + [FEZANDIPITI_EX, MUNKIDORI, MEOWTH_EX, BUDEW]
    + [POFFIN] * 4 + [POKE_PAD] * 4 + [ULTRA_BALL] * 4 + [RARE_CANDY] * 3
    + [NIGHT_STRETCHER] * 2 + [UNFAIR_STAMP]
    + [LILLIE] * 4 + [BOSS] * 3 + [CRISPIN] * 2 + [DAWN, ROSA]
    + [WATCHTOWER, RISKY_RUINS]
    + [FIRE_ENERGY] * 3 + [PSYCHIC_ENERGY] * 3 + [DARK_ENERGY] * 2
)


def _counter_blocked_by_body(pokemon):
    """本体特性でダメカン配置を防ぐ対象（ボム・アドレナ等の特性由来にも効く想定）。"""
    if pokemon is None:
        return True
    return pokemon.id in NO_DAMAGE_COUNTER_IDS


def _no_damage_counter(pokemon):
    """ワザの効果によるダメカン配置（ばら撒き）を防ぐ対象。
    ルール9（2026-07-14 ユーザー）: ミスト装着体をばら撒きで指定しない【ハード】。
    Mist/Rock Fighting のテキストは「相手のワザの効果を防ぐ（Damage is not an effect）」
    — 特性（カーズドボム/アドレナブレイン）は防がれない点に注意（ガードを分離する理由）。
    Rock Fighting の防御は {F} ポケモンに付いている時だけ。"""
    if _counter_blocked_by_body(pokemon):
        return True
    for card in (pokemon.energyCards or []):
        if card.id == 11:      # Mist Energy
            return True
        if card.id == 20:      # Rock Fighting Energy（{F} 装着時のみ防御）
            data = CARD_DB.get(pokemon.id)
            if data is not None and getattr(data, "energyType", None) == 6:
                return True
    return False


# ── S-7: 進化前提の最終形（役割判定のみ。HP は現物） ──

_CHILDREN_MAP = None


def _children_map():
    global _CHILDREN_MAP
    if _CHILDREN_MAP is None:
        _CHILDREN_MAP = defaultdict(list)
        for c in CARD_DB.values():
            ef = getattr(c, "evolvesFrom", None)
            if ef:
                _CHILDREN_MAP[ef].append(c)
    return _CHILDREN_MAP


def _final_form(card):
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
    if card is None:
        return False
    return card.cardId in ATTACKER_IDS_LEARNED or getattr(card, "megaEx", False)


class DragapultDusknoirPolicy(BasePolicy):
    DECK_NAME = "dragapult_dusknoir"
    GO_FIRST = True            # R-21【暫定】: 旧型 dragapult_rb の div-D1（先攻優位の A/B 実測）を継承。
                               # 同型のラダー実測 0 件のため gauntlet で再検証する。
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定】
    ATTACKER_IDS = {DRAGAPULT_EX, FEZANDIPITI_EX}
    ENERGY_IDS = {FIRE_ENERGY, PSYCHIC_ENERGY, DARK_ENERGY}
    LINE_PROTECT_IDS = DRAGAPULT_LINE | {RARE_CANDY}   # R-13
    ATTACK_ENERGY_TYPE = None
    USE_SPREAD_SEARCH = os.environ.get("DRAGA_SPREAD", "1") != "0"
    # ルール8/R-29（捨て駒バトル場への投資禁止）の A/B トグル。DUSK_R29=0 で旧挙動
    USE_R29 = os.environ.get("DUSK_R29", "1") != "0"

    def __init__(self):
        super().__init__()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False, "can_main_attack": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []
        self._deck_cache = None
        self.spread_plan = None
        self.bomb_plan = None       # ルール1: カーズドボムの計画（MAIN 毎に再計算）
        self._attach_tag = None     # _attach_score の特殊分岐ラベル（ログ用）
        self.stuck = False          # ルール10: 詰まり判定（MAIN 毎に再計算）
        # ダイブ「持続 vs 損切り」の決定は【ターン頭に一度だけ】確定し、その番は固定する
        # （ユーザー 2026-07-25）。手札/盤面がターン中に変わっても判断をブレさせない。
        self._dive_plan = None      # {"kind","persist","prob","threshold"} or None
        self._dive_plan_turn = -1   # プランを確定したターン番号
        self._grim_seen = False     # 対オーロンゲ: 一度見たらラッチ（_latch_grimmsnarl）
        self._grim_mode = None      # "lock" | "dive" | None（対オーロンゲ以外）
        self._grim_reason = ""      # モード確定の理由（プローブ用・挙動には無関与）
        self._grim_plan_turn = -1   # モードを確定したターン番号（ターン頭で一度だけ）
        self._playable_ids = set()  # R-13+: この番に即プレイできる手札IDのスナップショット

    def reset_game(self):
        super().reset_game()
        self.p = {}
        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        self.flags = {"can_switch": False, "can_attack": False, "can_main_attack": False}
        self.use_support = 0
        self._prize_ids = []
        self._log_buf = []
        self._pre_logs = []
        self.spread_plan = None
        self.bomb_plan = None
        self.stuck = False
        self._dive_plan = None
        self._dive_plan_turn = -1
        self._grim_seen = False
        self._grim_mode = None
        self._grim_plan_turn = -1
        self._playable_ids = set()

    # ═══════════ 対オーロンゲ検出（ラッチ式・特殊化パッケージの唯一のゲート） ═══════════

    def _latch_grimmsnarl(self, obs):
        """「オーロンゲを見たか」を単調（False→True のみ）にラッチする。

        なぜ基盤の detect_matchup をそのまま使わないか: R-20 は毎手番、相手の『場』の
        カードIDだけから再計算するため、オーロンゲ線が場から消える（ベロバーが気絶して
        トラッシュに落ちた・まだ出ていない）と matchup が generic に戻る＝認識が揺れる。
        特殊化は「一度オーロンゲと分かったらその試合は最後までオーロンゲとして指す」で
        なければ意味がないので、こちらで独立のラッチを持つ。
        基盤の self.t["matchup"] には手を触れない = 他デッキ・他対面へ影響しない。

        呼ぶ場所が update_belief でなく choose() の先頭なのは順序の都合:
        本デッキの choose は _analyze(→_plan_bomb) を基盤の update_belief より先に回すため、
        belief 側に置くと計画1回ぶん認識が遅れる。"""
        if not self._grim_seen and self._grim_visible(obs):
            self._grim_seen = True

    @staticmethod
    def _grim_visible(obs):
        """相手の場（バトル場・ベンチ）とトラッシュにオーロンゲ線が見えているか。
        トラッシュも見るのは、ベロバーが気絶した後でも認識を落とさないため。"""
        opp = opp_state(obs)
        for pk in list(opp.active or []) + list(opp.bench or []):
            if pk is not None and pk.id in GRIMMSNARL_LINE:
                return True
        for card in (opp.discard or []):
            if card is not None and getattr(card, "id", None) in GRIMMSNARL_LINE:
                return True
        return False

    def vs_grimmsnarl(self):
        """対オーロンゲ特殊化を有効にしてよいか。**特殊化ルールは必ずこれで囲う**。"""
        return DUSK_GRIM and self._grim_seen

    # ═══════════ GL: 対オーロンゲの本流モード（グッズロック vs ダイブ） ═══════════

    def _grim_lock(self):
        """この番はグッズロック維持モードか。GL 系ルールはこれで囲う。"""
        return self._grim_mode == "lock"

    def _ensure_grim_plan(self, obs):
        """モードは【ターン頭で一度だけ】確定して固定する（_dive_plan と同じ規律）。"""
        turn = getattr(obs.current, "turn", -1)
        if turn == self._grim_plan_turn and self._grim_mode is not None:
            return
        self._grim_plan_turn = turn
        self._grim_mode = self._compute_grim_mode(obs)

    def _compute_grim_mode(self, obs):
        """終了ラダー（上から優先）。ロックを畳む条件だけを列挙し、残りは全部ロック継続。

        「いつまでロックするか」は、実は『ロックもダイブも両方立つ番にどちらを選ぶか』に
        還元される（ダイブが立たない番はロックが常に正＝非対称な得、ロックが不能な番は
        ダイブ一択）。よってここでは "畳む理由" だけを判定する。
          ① リーサルは基盤 R-07 が LETHAL_BAND で常に最優先 → ここでは扱わない（不可侵）
          ② むずむず不可能（スボミーが永久に取れない）→ 即ダイブ（ユーザー 2026-07-26）
          ③ 相手オーロンゲex が起動済み（悪エネ2個＝毎番殴れる）→ グッズを止めても意味が無い
          ④ ペイロード完成（ダイブが撃てる ∧ ヨノワール在場 = 200+130 の丸取りが立つ）
          ⑤ ベロバー線枯渇（トラッシュにベロバー4枚 ∧ 場にベロバー/ギモー無し）＝もう
             オーロンゲを作れない → 圧が消えたので取りに行く
        """
        self._grim_reason = ""
        if not (self.vs_grimmsnarl() and DUSK_GRIM_LOCK):
            return None
        if self._lock_impossible(obs):
            self._grim_reason = "lock_impossible"
            return "dive"
        if self._grim_online(obs):
            self._grim_reason = "grim_online"
            return "dive"
        if self.flags.get("can_main_attack") and self._bomb_payload_ready(obs):
            self._grim_reason = "payload_ready"
            return "dive"
        if self._impidimp_exhausted(obs):
            self._grim_reason = "impidimp_exhausted"
            return "dive"
        self._grim_reason = "lock"
        return "lock"

    def _lock_impossible(self, obs):
        """むずむずかふんが永久に不能か（_dive_impossible と同型の到達可能性判定）。
        スボミーが 場・手札・山・（夜のタンカで回収可能な）トラッシュ のどこにも無い＝不能。
        サイド落ちは deck_counts が 0 を返すので自動的に不能側に入る。"""
        p = self.p or {}
        if (p.get("fc") or {}).get(BUDEW, 0) >= 1:
            return False
        ms = my_state(obs)
        if any(c is not None and c.id == BUDEW for c in (ms.hand or [])):
            return False
        deck = p.get("deck_counts") or {}
        if deck.get(BUDEW, 0) >= 1:
            return False
        if any(c is not None and c.id == BUDEW for c in (ms.discard or [])):
            # トラッシュのスボミーは夜のタンカでのみ手札に戻せる
            if (any(c is not None and c.id == NIGHT_STRETCHER for c in (ms.hand or []))
                    or deck.get(NIGHT_STRETCHER, 0) >= 1):
                return False
        return True

    @staticmethod
    def _grim_online(obs):
        """相手のオーロンゲex が起動済み（悪エネ2個以上＝シャドーバレットを毎番撃てる）。"""
        osn = opp_state(obs)
        for pk in (list(osn.active or []) + list(osn.bench or [])):
            if pk is not None and pk.id == GRIMMSNARL_EX and len(pk.energyCards or []) >= 2:
                return True
        return False

    @staticmethod
    def _impidimp_exhausted(obs):
        """ベロバー線が枯れた＝もう新しいオーロンゲを立てられない。
        ベロバーはデッキに4枚。トラッシュに4枚あれば全部死んでいる（進化した個体は
        進化元として盤面に残るのでトラッシュには来ない）。場に ベロバー/ギモー も
        居なければ、手札のオーロンゲ/ギモーは行き場が無い。"""
        osn = opp_state(obs)
        trashed = sum(1 for c in (osn.discard or [])
                      if c is not None and getattr(c, "id", None) == IMPIDIMP)
        if trashed < 4:
            return False
        for pk in (list(osn.active or []) + list(osn.bench or [])):
            if pk is not None and pk.id in (IMPIDIMP, MORGREM):
                return False
        return True

    @staticmethod
    def _bomb_payload_ready(obs):
        """ヨノワールが場にいる＝ダイブ200と合算して 330 の丸取りが立つ。"""
        return any(pk is not None and pk.id == DUSKNOIR for pk in all_my_pokemon(obs))

    # ═══════════════ ログ追跡（pre_ko / no_item） ═══════════════

    def track_logs(self, obs):
        for entry in obs.logs:
            self._log_buf.append(entry)
            if entry.type == LogType.TURN_END:
                self._pre_logs = self._log_buf
                self._log_buf = []
        super().track_logs(obs)   # R-17

    # ═══════════════ R-18: サイド落ち推定 ═══════════════

    def _deck_list(self):
        """R-18（サイド落ち推定）の母集合となる自デッキ60枚。

        提出時は kaggle 側の deck.csv、ローカル評価では DECK_FALLBACK が使われる。
        リスト A/B のときは policy 側の勘定も一緒に切り替えないと deck_counts が
        嘘になるので、環境変数 DUSK_DECK_CSV で差し替えられるようにしてある
        （未設定なら従来どおり = 提出物の挙動は不変）。"""
        if self._deck_cache is None:
            try:
                if DECK_CSV_OVERRIDE:
                    with open(DECK_CSV_OVERRIDE) as f:
                        self._deck_cache = [int(l.strip()) for l in f if l.strip()][:60]
                else:
                    self._deck_cache = _read_deck_csv()
            except Exception:
                self._deck_cache = list(DECK_FALLBACK)
        return self._deck_cache

    def _subtract_visible(self, counts, serials, card, my_index):
        if card is None:
            return
        if isinstance(card, Pokemon) or card.playerIndex == my_index:
            if card.serial not in serials:
                counts[card.id] -= 1
                serials.add(card.serial)
        if isinstance(card, Pokemon):
            for c in (card.energyCards or []):
                self._subtract_visible(counts, serials, c, my_index)
            for c in (card.tools or []):
                self._subtract_visible(counts, serials, c, my_index)
            for c in (card.preEvolution or []):
                self._subtract_visible(counts, serials, c, my_index)

    def _visible_counts(self, obs):
        counts = defaultdict(int)
        serials = set()
        for cid in self._deck_list():
            counts[cid] += 1
        yi = obs.current.yourIndex
        ms = my_state(obs)
        for zone in (ms.hand or []), (ms.discard or []), ms.bench, ms.active:
            for card in zone:
                self._subtract_visible(counts, serials, card, yi)
        for card in obs.current.stadium:
            self._subtract_visible(counts, serials, card, yi)
        if obs.current.looking is not None:
            for card in obs.current.looking:
                self._subtract_visible(counts, serials, card, yi)
        self._subtract_visible(counts, serials, obs.select.effect, yi)
        return counts

    # ═══════════════ ターン分析 ═══════════════

    def choose(self, obs):
        self._latch_grimmsnarl(obs)     # _analyze(_plan_bomb) より先に認識を確定させる
        self.p = self._analyze(obs)
        return super().choose(obs)

    def _analyze(self, obs):
        ms = my_state(obs)
        osn = opp_state(obs)
        yi = obs.current.yourIndex

        # R-18: 山札閲覧（select.deck）が来たらサイド集合を確定
        if obs.select.deck is not None:
            counts = self._visible_counts(obs)
            for card in obs.select.deck:
                if card is not None:
                    counts[card.id] -= 1
            self._prize_ids = [cid for cid, n in counts.items() for _ in range(max(0, n))]
        deck_counts = self._visible_counts(obs)
        for cid in self._prize_ids:
            deck_counts[cid] -= 1

        fc = defaultdict(int)
        hc = defaultdict(int)
        dc = defaultdict(int)
        active_id = 0
        bench_attacker = False
        can_evolve_dreepy = False
        evolve_dreepy_count = 0
        can_evolve_drakloak = False
        can_evolve_duskull = False
        can_evolve_dusclops = False
        own_damage = False
        for card in ms.active:
            if card is None:
                continue
            active_id = card.id
            fc[card.id] += 1
            if damage_on(card) > 0:
                own_damage = True
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
                elif card.id == DUSKULL:
                    can_evolve_duskull = True
                elif card.id == DUSCLOPS:
                    can_evolve_dusclops = True
        for card in ms.bench:
            if card is None:
                continue
            fc[card.id] += 1
            if damage_on(card) > 0:
                own_damage = True
            if not card.appearThisTurn:
                if card.id == DREEPY:
                    can_evolve_dreepy = True
                    evolve_dreepy_count += 1
                elif card.id == DRAKLOAK:
                    can_evolve_drakloak = True
                elif card.id == DUSKULL:
                    can_evolve_duskull = True
                elif card.id == DUSCLOPS:
                    can_evolve_dusclops = True
            if card.id == DRAGAPULT_EX and len(card.energies) >= 2:
                bench_attacker = True
        for card in (ms.discard or []):
            if card is not None:
                dc[card.id] += 1

        stadium_id = 0
        for card in obs.current.stadium:
            stadium_id = card.id

        pre_ko = False
        no_item = False
        for log in self._pre_logs:
            if log.type == LogType.ATTACK and log.attackId == ATK_ITCHY_POLLEN:
                no_item = True
            elif (log.type == LogType.MOVE_CARD and log.playerIndex == yi
                  and log.fromArea in (AreaType.BENCH, AreaType.ACTIVE)
                  and log.toArea == AreaType.DISCARD):
                pre_ko = True

        energy_in_hand = sum(1 for c in (ms.hand or [])
                             if c is not None and c.id in BASIC_ENERGIES)

        p = {
            "fc": fc, "hc": hc, "dc": dc, "deck_counts": deck_counts,
            "active_id": active_id, "bench_attacker": bench_attacker,
            "can_evolve_dreepy": can_evolve_dreepy,
            "evolve_dreepy_count": evolve_dreepy_count,
            "can_evolve_drakloak": can_evolve_drakloak,
            "can_evolve_duskull": can_evolve_duskull,
            "can_evolve_dusclops": can_evolve_dusclops,
            "own_damage": own_damage,
            "energy_in_hand": energy_in_hand,
            "main_pokemon_count": fc[DREEPY] + fc[DRAKLOAK] + fc[DRAGAPULT_EX],
            "no_more_dex": fc[DRAGAPULT_EX] * 2 >= len(osn.prize),
            "stadium_id": stadium_id,
            "prize_diff": len(ms.prize) - len(osn.prize),
            "pre_ko": pre_ko, "no_item": no_item,
            "no_draw": ms.deckCount <= 8,   # R-11
            "effect_id": obs.select.effect.id if obs.select.effect is not None else 0,
            "context_card_id": obs.select.contextCard.id if obs.select.contextCard is not None else 0,
            "support_count": 0, "hand_scores": [], "negative_hand": 0,
        }

        # S-7: ばら撒き配分の探索計画（DAMAGE_COUNTER_ANY の連続選択中はキャッシュ）
        if self.USE_SPREAD_SEARCH and obs.select.context == SelectContext.DAMAGE_COUNTER_ANY:
            if self.spread_plan is None:
                self.spread_plan = self._plan_spread(obs)
        else:
            self.spread_plan = None

        # MAIN でだけ: 配分プラン（DFS）+ ボム計画 + 詰まり判定 + 使うサポートの択一
        if obs.select.context == SelectContext.MAIN:
            self._main_option_proc(obs, p)
            self.bomb_plan = self._plan_bomb(obs)   # flags 更新後に計算（②③は can_main_attack 前提）
            # ルール10（2026-07-14 ユーザー）: 詰まり判定 —
            # 「エネルギーが張れない または 進化できない」が成立する序盤の番は
            # ハイパーボール→ニャース（Last-Ditch Catch）→リーリエで前へ進む。
            # phase は前決定の値（1決定ラグ・同一ターン内なら実害なし）
            self.p = p   # _score_evolve が self.p を読むため先行代入
            # ダイブ「持続 vs 損切り」を【このターンで一度だけ】確定（ユーザー 2026-07-25）。
            # 以後この番の attach/use_support は _dive_plan を固定参照する（判断をブレさせない）。
            self._ensure_dive_plan(obs)
            # GL: 対オーロンゲの本流モード（ロック維持 / ダイブ移行）も同じくターン頭で確定。
            # _hand_score・do_switch・前出し採点がこの後この値を固定参照する。
            self._ensure_grim_plan(obs)
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

            can_attach_now = False
            can_evolve_now = False
            for o in obs.select.option:
                if o.type == OptionType.ATTACH and not can_attach_now:
                    c0 = option_card(obs, o)
                    t0 = option_target(obs, o)
                    if (c0 is not None and t0 is not None
                            and c0.id in BASIC_ENERGIES
                            and self._attach_score(obs, p, c0.id, t0,
                                                   o.inPlayArea == AreaType.ACTIVE) > 0):
                        can_attach_now = True
                elif o.type == OptionType.EVOLVE and not can_evolve_now:
                    if self._score_evolve(obs, o)[0] > 0:
                        can_evolve_now = True
            self.stuck = (self.t["phase"] == "setup"
                          and (not can_attach_now or not can_evolve_now))
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
                # ルート実行（ユーザー 2026-07-25「計算したルートを実際に辿れるか」）:
                # ターン頭の決定が【持続】で、かつダイブ完成が手張りチャネルでは不可・アカマツで
                # のみ可能な局面なら、汎用サポート選定を上書きして必ずアカマツを打つ（route を確定
                # 執行）。損切りターンには打たない = 決定と実行を一致させる。
                if (DUSK_STREAMS and self._dive_plan is not None
                        and self._dive_plan.get("persist")
                        and self._dive_needs_crispin(obs)
                        and any(o.type == OptionType.PLAY
                                and get_card(obs, AreaType.HAND, o.index, yi) is not None
                                and get_card(obs, AreaType.HAND, o.index, yi).id == CRISPIN
                                for o in obs.select.option)):
                    self.use_support = CRISPIN

        # 手札スコア（PLAY 採点の材料）
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

        # DUSK_BUDEW_OPEN2（2026-07-26）: 開幕（両者の最初の番 = turn<=2）にダイブが撃てない
        # なら、バトル場に1エネ張って退却しスボミーを前に出してムズムズ花粉（相手グッズロック）
        # を撃つ。旧 DUSK_OPEN_BUDEW は「ポフィンでスボミーを盤面に置く」までで、退却が
        # turn>=2 ゲートに阻まれて先行T1 で前に出せていなかった（通常版 EXP-043 と同じ穴）。
        budew_open = (DUSK_BUDEW_OPEN2
                      and not self.flags["can_main_attack"]
                      and obs.current.turn <= 2
                      and active_id != BUDEW and fc[BUDEW] >= 1)
        p["budew_open"] = budew_open
        p["do_switch"] = (not self.flags["can_main_attack"]
                          and (bench_attacker
                               or (active_id != BUDEW and fc[BUDEW] >= 1
                                   and (obs.current.turn >= 2 or budew_open))))
        # GL-2: ロックモード中はスボミーの在位を最優先で維持する。
        #   場に居て前でない → 前に出す（攻撃できる番でも。ロックのほうが価値が高い）
        #   既に前 → 絶対に退却させない（ベンチアタッカーが居ても降ろさない）
        if self._grim_lock() and fc[BUDEW] >= 1:
            p["do_switch"] = (active_id != BUDEW)
        return p

    # ═══════════════ 配分プラン（枝刈り DFS。dragapult_rb 移植） ═══════════════

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

        self.plan_a = {"attack": -1, "counter": [], "prizes": 0}
        self.plan_b = {"attack": -1, "counter": [], "prizes": 0}
        if not f["can_main_attack"] and not (p["bench_attacker"] and f["can_switch"]):
            return
        if not osn.active or osn.active[0] is None:
            return

        cards = [osn.active[0]] + list(osn.bench)
        HUGE = 10 ** 9

        def counter_hp(pk):
            if pk is None or _no_damage_counter(pk):
                return HUGE
            return pk.hp

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
                        score = 50000
                    else:
                        if prize >= 2:
                            if remain_prize <= 4:
                                score -= 1200
                        elif prize == 1:
                            score -= 300
                        else:
                            score += 1200
                    if max_score < score:
                        max_score = score
                        best_ci = indices
                        best_prizes = prize
            if plan_score < max_score:
                plan_score = max_score
                self.plan_a = {"attack": i, "counter": list(best_ci), "prizes": best_prizes}
            if i == 0:
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

    # ═══════════════ S-7: ばら撒き60 の配分探索（dragapult_rb 移植・現在HP版） ═══════════════

    def _bench_targets(self, obs):
        osn = opp_state(obs)
        out = []
        for j, pk in enumerate(osn.bench):
            if pk is None:
                continue
            if _no_damage_counter(pk):
                continue
            static = CARD_DB.get(pk.id) or pk
            ff = _final_form(static)
            remain = max(10, pk.hp)
            need = -(-remain // 10)
            # ルール13（2026-07-14 ユーザー）: 相手の投資度 = エネ枚数 + 進化済み(+2)。
            # 即殺候補が複数あるときの優先順位（同サイドなら投資済みを先に取る）
            evolved = bool(getattr(static, "stage1", False)
                           or getattr(static, "stage2", False))
            out.append({
                "coord": j + 1, "remain": remain, "need": need,
                "prize": self._prize_count(pk, False),
                "attacker": _is_attacker(ff),
                "invest": len(pk.energies or []) + (2 if evolved else 0),
            })
        return out

    def _plan_spread(self, obs):
        targets = self._bench_targets(obs)
        target_hp = {}
        if not targets:
            return target_hp

        best_subset, best_key = [], (-1, 0, 0)
        n = len(targets)
        for mask in range(1 << n):
            used, prize, invest, ok = 0, 0, 0, True
            for i in range(n):
                if mask & (1 << i):
                    used += targets[i]["need"]
                    prize += targets[i]["prize"]
                    invest += targets[i]["invest"]
                    if used > 6:
                        ok = False
                        break
            if ok and used <= 6:
                # ルール13: サイド最大 → 投資済み（エネ付き/進化後）優先 → 消費個数最小
                key = (prize, invest, -used)
                if key > best_key:
                    best_key, best_subset = key, [i for i in range(n) if mask & (1 << i)]
        chosen = set(best_subset)
        used = sum(targets[i]["need"] for i in chosen)
        for i in chosen:
            target_hp[targets[i]["coord"]] = 0

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
                        val = t["prize"] * 1000 + 500
                    elif t["remain"] <= 320:
                        val = t["prize"] * 1000 + 200
                    else:
                        val = t["prize"] * 1000 - 100
                else:
                    need_after = -(-max(0, after) // 10)
                    if need_after <= 6:
                        val = t["prize"] * 1000 + 400
                    else:
                        val = t["prize"] * 1000 - 200
                val -= t["remain"] * 0.1
                if val > best_val:
                    best_val, best_i = val, i
            if best_i is not None:
                t = targets[best_i]
                target_hp[t["coord"]] = max(0, t["remain"] - leftover * 10)
        return target_hp

    # ═══════════════ ルール1: カーズドボム計画 ═══════════════

    def _plan_bomb(self, obs):
        """爆発は「KO を取り切れる時だけ」【ハード】。
        ①130(50)単体 / ②正面200と合算（アクティブ） / ③ばら撒き60と合算（ベンチ）。
        自壊 = 相手にサイド1を渡すため、相手残りサイド1以下では絶対に撃たない【ハード】。
        サマヨール(50)は「基本は2進化を目指す」に従い、①でサイド2以上を取れる時だけ。
        戻り値: {"bomber", "dmg", "coord", "mode", "prize", "remain"} or None。"""
        osn = opp_state(obs)
        if len(osn.prize) <= 1:
            return None
        bombers = {pk.id for pk in all_my_pokemon(obs)} & DUSKNOIR_LINE
        if DUSKNOIR in bombers:
            bomber, dmg = DUSKNOIR, 130
        elif DUSCLOPS in bombers:
            bomber, dmg = DUSCLOPS, 50
        else:
            return None
        cards = ([osn.active[0]] if osn.active else [None]) + list(osn.bench)
        can_dive = self.flags.get("can_main_attack", False)
        best = None
        grim_only = self.vs_grimmsnarl() and DUSK_GRIM_BOMB
        for i, pk in enumerate(cards):
            # ボムは特性 = ミストを貫通。除外は本体特性持ちのみ（ルール9の分離ガード）
            if pk is None or _counter_blocked_by_body(pk):
                continue
            # G-1【ハード】: 対オーロンゲでは的をオーロンゲex に限定する（ボマーの温存）
            if grim_only and pk.id != GRIMMSNARL_EX:
                continue
            remain = pk.hp
            prize = self._prize_count(pk, False)
            if remain <= dmg:
                mode = 1
            elif i == 0 and can_dive and pk.id not in NO_DAMAGE_DEX and remain <= 200 + dmg:
                mode = 2   # ボム→正面200 で取り切り（正面はダメージ=ミスト無関係）
            elif (i > 0 and can_dive and remain <= 60 + dmg
                    and not _no_damage_counter(pk)):
                mode = 3   # ボム→ばら撒き60 で取り切り（ばら撒き側はミストに阻まれる）
            else:
                continue
            if bomber == DUSCLOPS and not (mode == 1 and prize >= 2):
                continue
            waste = dmg - remain if mode == 1 else 0
            key = (1 if mode == 1 else 0, prize, -waste, -remain)
            if best is None or key > best["key"]:
                best = {"key": key, "bomber": bomber, "dmg": dmg, "coord": i,
                        "mode": mode, "prize": prize, "remain": remain}
        return best

    def _bomb_lethal_now(self, obs):
        """ボムを絡めた取り切り（ボム単体 or ボム+配分プラン）。成立ならボム特性を
        リーサル帯に昇格させる（ボム解決後は通常の R-07 機構が残りを拾う）。"""
        bp = self.bomb_plan
        if bp is None or bp["mode"] != 1:
            return False
        my_remaining = len(my_state(obs).prize)
        if bp["prize"] >= my_remaining:
            return True
        plan = self.plan_a
        if (self.flags.get("can_main_attack") and plan["attack"] >= 0
                and bp["coord"] != plan["attack"]
                and bp["coord"] not in plan["counter"]
                and bp["prize"] + plan["prizes"] >= my_remaining):
            return True
        return False

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
        spread = self._spread_lethal(obs)
        if spread is not None:
            return spread
        return super().judge_lethal(obs)

    def _spread_lethal(self, obs):
        plan = self.plan_a
        if plan["attack"] < 0 or plan["prizes"] < len(my_state(obs).prize):
            return None
        if not self.flags.get("can_main_attack"):
            return None
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return None
        if plan["attack"] == 0:
            return {"route": "active", "attack_id": ATK_PHANTOM_DIVE,
                    "attacker": active, "needs_retreat": False}
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
        return super().score_setup_context(obs, opt)

    def score_yes_no(self, obs, opt):
        # R-11: 山札が薄いときは任意ドロー特性を辞退（ボム/アドレナはドローでないため除外）
        if (obs.select.context == SelectContext.ACTIVATE and self.p.get("no_draw")
                and self.t.get("lethal") is None
                and self.p.get("effect_id") not in (DUSCLOPS, DUSKNOIR, MUNKIDORI)):
            return (1, "R-11: decline activate (deck thin)") if opt.type == OptionType.NO \
                else (0, "R-11: deck thin")
        return super().score_yes_no(obs, opt)

    # ═══════════════ 優先則（3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt)

    def _score_any(self, obs, opt):
        p = self.p
        yi = obs.current.yourIndex

        if opt.type == OptionType.CARD:
            return self._score_card(obs, opt)

        if opt.type in (OptionType.ENERGY_CARD, OptionType.ENERGY):
            pi = opt.playerIndex if opt.playerIndex is not None else yi
            if pi != yi:
                score = 20 if opt.area == AreaType.BENCH else 10
                card = get_card(obs, opt.area, opt.index, pi)
                data = CARD_DB.get(card.id) if card is not None else None
                if data is not None and data.cardType == CardType.SPECIAL_ENERGY:
                    score += 1
                return score, "opp energy (bench first, special first)"
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
            return score, (self._attach_tag or "S-5: attach")

        if opt.type == OptionType.EVOLVE:
            return self._score_evolve(obs, opt)

        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card is not None else 0
            if cid in (DUSCLOPS, DUSKNOIR):
                # ルール1【ハード】: KO を取り切れる時だけ爆発。取り切りに絡むなら
                # リーサル帯へ昇格（攻撃より先に解決しないとターンが終わるため）
                bp = self.bomb_plan
                if bp is None or bp["bomber"] != cid:
                    return -1, "B-1: hold Cursed Blast (no KO)"
                if self._bomb_lethal_now(obs):
                    return LETHAL_BAND + 1, "B-1: LETHAL Cursed Blast"
                return 2600, f"B-1: Cursed Blast mode{bp['mode']}"
            if cid == MUNKIDORI:
                # E-6: アドレナブレイン。自分の場にダメカンがある時だけ（回復+削り）。
                # 順序は攻撃直前帯（marnie div-14 準拠）
                if p["own_damage"]:
                    return 2500, "E-6: Adrena-Brain (move counters)"
                return -1, "E-6: save Adrena-Brain (no damage)"
            if p["no_draw"]:
                return -1, "R-11: deck thin (ability)"
            if cid == LUMIOSE_CITY:
                return 1, "Lumiose City (low)"
            # ルール7【ソフト（順序）】: 偵察指令は不確定ドロー先・確定サーチ後。
            # 旧: ポフィン46000 →（リーリエ45800）→ 偵察45700 → ポケパッド45000。
            #
            # DUSK_RECON_FIRST（2026-07-26 差分マイニングで発見）: 上の実装は**ルール7の
            # 原則そのものと矛盾**していた。偵察指令＝不確定ドロー / ポフィン＝確定サーチ
            # なので、原則どおりなら偵察が先。実装は 45700 < 46000 で逆になっていた。
            # 通常版との決定差分 1065件のうち **399件(37%)** がこの一族で、最大クラスタは
            # 「偵察指令を使う前にドロンチをドラパルト ex へ進化させて特性を捨てる」
            # （72回/80戦 ≈ 0.9回/試合の偵察を丸ごと無駄にしていた）。
            # → 通常版の div-D3（07-08 人間リプレイ実測「Recon はグッズ・エネ付けより先」）
            #   の 56000 帯へ戻す。リーリエだけは手札を山へ戻すので例外的に先（56100）。
            if DUSK_RECON_FIRST:
                return 56000, "div-D3: Recon Directive first (before goods/attach/evolve)"
            return 45700, "S-4/rule7: Recon Directive (after thinning, before Poke Pad)"

        if opt.type == OptionType.RETREAT:
            if p["do_switch"]:
                return 10000, "retreat (bench attacker / Budew lock)"
            return -1, "no retreat"

        if opt.type == OptionType.ATTACK:
            return (opt.attackId or 0), "E-1: attack"

        if opt.type == OptionType.END:
            return 0, "end"

        return 0, "fallback"

    # ── EVOLVE（S-3。進化カード側の id で分岐） ──

    def _score_evolve(self, obs, opt):
        p = self.p
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        cid = card.id if card is not None else 0
        e = len(getattr(target, "energies", []) or []) if target is not None else 0

        # ルール8b（2026-07-14 ユーザー）: 序盤のバトル場はいけにえ — 進化先はベンチ優先。
        # ドロンチはベンチのドラメシヤへ（バトル場のドラメシヤは捨て駒に進化を注がない）。
        # ベンチに対象が居なければ従来通り進化する（優先であって禁止ではない）。
        # -2100 は同一進化カードのベンチ対象を必ず上回らせつつ正帯に留める幅
        sac = 2100 if (self.USE_R29 and self.t["phase"] == "setup"
                       and opt.inPlayArea == AreaType.ACTIVE) else 0

        if cid == DRAKLOAK:
            return 58000 + e - sac, "div-D3/rule8b: evolve Dreepy (bench first)"
        if cid == DRAGAPULT_EX:
            if p["fc"][DRAGAPULT_EX] >= 1:
                return -1, "div-D4: hold 2nd Dragapult ex"
            # S-0!【ハード・ユーザー 2026-07-26（loss1.json の観戦で発見）】
            # 「バトル場のドロンチを進化させれば**この番のうちにファントムダイブが撃てる**」
            # 局面は、他のどの進化よりも優先する。旧実装は Dreepy→Drakloak が 58000、
            # 本行が 48000−sac=45900 で、**ベンチのドラメシヤ進化が常に勝っていた**
            # （＝手番内ダイブ判定が進化の選択に一切繋がっていなかった）。
            if (DUSK_DIVE_NOW and opt.inPlayArea == AreaType.ACTIVE
                    and not self.flags.get("can_main_attack")
                    and self._dive_now_after_evolve(obs, target)):
                return 62000, "S-0!: evolve active -> Dragapult ex (dive THIS turn)"
            return 48000 + e - sac, "S-3: evolve -> Dragapult ex"
        if cid == DUSCLOPS:
            return 47500 + e - sac, "S-3b: evolve Duskull -> Dusclops"
        if cid == DUSKNOIR:
            # 基本は2進化（ヨノワール）を目指す（ユーザー決定）。130ボムの装填
            return 49200 + e - sac, "S-3b: evolve -> Dusknoir (load bomb)"
        if target is not None and target.id == DREEPY:
            return 58000 + e - sac, "div-D3/rule8b: evolve Dreepy (bench first)"
        return 30000 + e - sac, "S-3: evolve (other)"

    # ── PLAY ──

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
            return 54000, "S-2: play Dreepy"
        if cid == DUSKULL:
            if fc[DUSKULL] + fc[DUSCLOPS] + fc[DUSKNOIR] < 2:
                return 53000, "S-2b: play Duskull (bomb line)"
            return -1, "Duskull: enough bomb line"
        if cid == MUNKIDORI:
            if fc[MUNKIDORI] == 0:
                return 49000, "S-2c: play Munkidori"
            return -1, "Munkidori: already in play"
        if cid == FEZANDIPITI_EX:
            if card_score > 0:
                return 35000, "play Fez"
            return -1, "Fez: not needed"
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
            dreepy_path = (p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1
                           and fc[DRAGAPULT_EX] == 0 and not p["no_more_dex"])
            duskull_path = p["can_evolve_duskull"] and hc[DUSKNOIR] >= 1
            if dreepy_path or duskull_path:
                return 75000, "S-3: Rare Candy"
            return -1, "Rare Candy: no path now"
        if cid == UNFAIR_STAMP:
            return 57000, "E-5: Unfair Stamp (div-D8)"
        if cid == NIGHT_STRETCHER:
            if card_score >= 18000:
                return 42000, "Night Stretcher: recover"
            return -1, "Night Stretcher: nothing"
        if cid == BOSS:
            if cid == self.use_support:
                return 35000, "R-16: Boss (plan target)"
            return -1, "R-16: hold Boss"
        if cid == LILLIE:
            if cid == self.use_support:
                # ルール7: リーリエは手札を山へ戻すので、偵察指令で取った札を戻す無駄を
                # 避けるため偵察より先（R-26/R-28 と同じ構造）。DUSK_RECON_FIRST で
                # 偵察を 56000 に上げたので、この例外も 56100 へ追随させる。
                # 進化 47500+ はリーリエより先（手札の進化パーツを山へ戻さない）
                if DUSK_RECON_FIRST:
                    return 56100, "rule7: Lillie before Recon"
                return 45800, "rule7: Lillie before Recon"
            return -1, "Lillie: other supporter"
        if cid == DAWN:
            if cid == self.use_support:
                return 30000, "S-4b: Dawn (chosen supporter)"
            return -1, "Dawn: other supporter"
        if cid == ROSA:
            if cid == self.use_support:
                return 35000, "S-5b: Rosa (energy from discard)"
            return -1, "Rosa: other supporter"
        if cid == CRISPIN:
            if cid == self.use_support:
                return 35000, "S-6: Crispin"
            return -1, "Crispin: not chosen"
        if cid == BROCK:
            if cid == self.use_support:
                return 35000, "S-4b: Brock's Scouting"
            return -1, "Brock: not chosen"
        if cid == WATCHTOWER:
            # ルール11（2026-07-14 ユーザー）: スタジアムは温存しない。
            # 相手スタジアム置換 / T1 は即時（80000）。自分のスタジアムが出ている間だけ保持。
            # それ以外は攻撃前帯（正帯最下層）で必ず張る
            if p["stadium_id"] in (WATCHTOWER, RISKY_RUINS):
                return -1, "Watchtower: own stadium up"
            if p["stadium_id"] > 0 or obs.current.turn == 1:
                return 80000, "play Watchtower (replace/T1)"
            return 490, "rule11: play stadium before attack"
        if cid == RISKY_RUINS:
            # G-2: 対オーロンゲでは張らない（相手のたねは{悪}で無傷・こちらの小駒だけが削れる）
            if self.vs_grimmsnarl() and DUSK_GRIM_RUINS:
                return -1, "G-2: hold Risky Ruins (vs Grimmsnarl)"
            # ルール5+11: 攻撃の直前に張る（全行動を済ませた後 = 正帯最下層。
            # ATTACK(154) と END(0) より上、他の全正帯より下）。攻撃できない番も温存しない
            if p["stadium_id"] in (RISKY_RUINS, WATCHTOWER):
                return -1, "Risky Ruins: own stadium up"
            return 500, "rule5/11: Risky Ruins before attack"
        # ルール12+【ソフト・ユーザー 2026-07-26】ポフィンは**いついかなるときも即プレイ**。
        # ルール7の意図は「グッズが要求札に足りない時、偵察指令で先に要求を埋める」であって、
        # ポフィンは要求札そのもの（＝偵察より先）。ドロンチが立った後も温存する利得は無く、
        # 山の圧縮も兼ねる。旧実装は R-11（deckCount<=8）が先に効いて終盤ずっと握っていた
        # ので、判定を R-11 より**上**へ移す。例外は対LOのみ（自山を削るのが致命的、R-28 同条件）。
        if cid == POFFIN and DUSK_POFFIN_ALWAYS:
            # 的の有無だけを見る（G-3 中でもヨマワルを的に数える = ポフィン自体は必ず打つ。
            # ヨマワルをベンチに置くかは TO_BENCH 側の採点で断る）
            targets = deck[DREEPY] + deck[BUDEW] + deck[DUSKULL]
            if targets <= 0:
                return -1, "Poffin: no target"
            if p["no_draw"] and self.t["matchup"] in mt.LO_ARCHETYPES:
                return -1, "R-11: deck thin (LO only)"
            return 46000, "rule12+: Poffin (always play, never hold)"
        if p["no_draw"]:
            return -1, "R-11: deck thin (draw item/supporter)"
        if cid == POFFIN:
            # ルール12（2026-07-14 ユーザー）: ポフィン/ポケパッドは温存しない・積極使用
            if deck[DREEPY] + deck[DUSKULL] + deck[BUDEW] > 0:
                return 46000, "S-2/rule12: Poffin"
            return -1, "Poffin: no target"
        if cid == ULTRA_BALL:
            # ルール10: 詰まり脱出 — ニャース経由でリーリエへ（手札を2枚切る価値あり）
            if (self.stuck and not obs.current.supporterPlayed
                    and p["stadium_id"] != WATCHTOWER
                    and hc[MEOWTH_EX] == 0 and deck[MEOWTH_EX] >= 1
                    and p["support_count"] <= hc[BOSS]):
                return 44500, "rule10: Ultra Ball -> Meowth -> Lillie (unstick)"
            # R-13+②: ハイパーボールは**グッズの最後**（41000 = ポフィン46000・ポケパッド
            # 45000・夜のタンカ42000 の下）。他のグッズを打ち切ってから打てば、手札に残るのは
            # 即プレイ不能札だけになり、切るコストが最小になる。
            # 発火条件も「切れる札（＝即プレイ不能札）が2枚あるか」で定義する。
            if DUSK_PLAYABLE_NOW:
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
            if (deck[DREEPY] + deck[DRAKLOAK] + deck[DUSKULL]
                    + deck[DUSCLOPS] + deck[DUSKNOIR] + deck[MUNKIDORI]
                    + deck[BUDEW]) > 0:
                return 45000, "S-4/rule7/rule12: Poke Pad (after Recon)"
            return -1, "Poke Pad: no target"
        return -0.5, "div-D6: unknown card (below END)"

    # ── ATTACH（S-5 + R-10 + ルール2） ──

    def _attach_score(self, obs, p, attach_id, pokemon, active):
        self._attach_tag = None
        data = CARD_DB.get(attach_id)
        if data is not None and data.cardType == CardType.TOOL:
            return 60000 + (1000 if active else 0)

        e = len(pokemon.energies or [])
        if e >= LINE_MAX_COST.get(pokemon.id, 2):
            return -1   # R-10【ハード】（ボムライン=0 / マシマシラ=1 もここで効く）
        # ルール2【ハード】: 悪エネはマシマシラ専用。他ポケモンには張らない。
        # マシマシラに悪以外も張らない（アドレナ起動の1枚だけで良い）
        if attach_id == DARK_ENERGY and pokemon.id != MUNKIDORI:
            return -1
        if pokemon.id == MUNKIDORI:
            if attach_id != DARK_ENERGY:
                return -1
            # サブストリーム: アドレナ用の悪エネは本流稼働(online)/終盤のみ張る
            if DUSK_STREAMS and not self._munki_ok(obs, p):
                return -1
            return 8300   # アドレナブレイン起動（アカマツの「余裕があるとき」の受け皿）
        f = self.flags
        ms = my_state(obs)
        if pokemon.id == BUDEW:
            return -1
        # DUSK_BUDEW_OPEN2（2026-07-26）: 通常版 dragapult_rb の DRA_BUDEW_OPEN の移植。
        # 開幕ロックのため、バトル場に「退却で捨てる前提の1エネ」を供給する。ベンチ充電
        # （+20000帯）より上に置かないとバトル場が退却できず、スボミーが前に出られない。
        # EXP-043 では通常版で対marnie +10.6pt（maximin 床上げ）の実測がある。
        if p.get("budew_open") and active and e == 0:
            self._attach_tag = "S-5: fund active retreat (Budew lock)"
            return 20500
        # ルール8/R-29 候補（2026-07-14 ユーザー）: サブゴール前のバトル場は捨て駒。
        # 「ドラメシヤにエネを張って次の番に倒される」の対策 —
        #   ①逃げエネは容認（スボミーを前に出すための退却コスト。あと1枚で逃げられる時だけ）
        #   ②次の相手番に飛ばされる見込み（opp_max_damage ≥ 残HP）のバトル場には張らない
        # アタッカー（ドラパルトex/フェザン）は起動優先で例外。ベンチ育成は影響なし。
        if (self.USE_R29 and active and self.t["phase"] == "setup"
                and pokemon.id not in self.ATTACKER_IDS):
            rc = retreat_cost(pokemon)
            wants_escape = ((p["fc"][BUDEW] >= 1 and pokemon.id != BUDEW)
                            or p["bench_attacker"])
            if rc - e == 1 and wants_escape:
                self._attach_tag = "S-1b: escape energy (bring Budew forward)"
                return 21000
            if self.opp_max_damage(obs) >= pokemon.hp:
                self._attach_tag = "R-29: no invest in doomed active"
                return -1
        if pokemon.id in (MEOWTH_EX, FEZANDIPITI_EX):
            if active and not f["can_switch"] and not ms.asleep and not ms.paralyzed:
                return 22000 if (p["bench_attacker"] or p["fc"][BUDEW] >= 1) else 18000
            return -1
        if active and f["can_main_attack"]:
            return -1
        # ファントムダイブ「持続 vs 損切り」（ユーザー 2026-07-25）。判断は【ターン頭で確定】済み
        # （_dive_plan）。ここでは persist フラグを参照するだけ = ターン中に手札/盤面が変わっても
        # 判断がブレない。対象は「準備中ドラパルト ex(e<2)」または「掘り進め中ドロンチ」の露出局面。
        #   persist → 必要色でないエネもベンチへ散らさない(-1、本流の活性ラインへ寄せる)
        #   losscut → fall through して散布許可（エネ分散して安全に降りる）
        # ベンチのドラパルト ex 本体（2体目起動）と山切れ時は除外。
        plan = self._dive_plan
        if (DUSK_STREAMS and not active and pokemon.id != DRAGAPULT_EX
                and plan is not None and plan.get("kind") and ms.deckCount > 0):
            if plan["persist"]:
                return -1                  # 持続: 散らさず本流へ寄せる
            # 損切り: fall through してベンチ手張りを許可（エネ分散）
        # DUSK_CONCENTRATE: 完成間近（e==1）の個体がいる間、未着手（e==0）の別個体へは
        # 張らない。素点表が新品を優遇してしまう構造バグの是正（定数コメント参照）。
        # 場のドラパルト ex 本体への付与は常に「ダイブ狙い」なので対象外。
        if DUSK_CONCENTRATE and e == 0 and pokemon.id != DRAGAPULT_EX:
            charged = any(pk is not pokemon and pk.id in DRAGAPULT_LINE
                          and len(pk.energies or []) == 1
                          for pk in all_my_pokemon(obs))
            if charged and not self._dive_secured(obs):
                # 集中先をまだ仕上げられる見込みがあるなら分散禁止（見込みが無いなら
                # 抱えても死ぬだけなので散らす = 通常版 DRA_CONCENTRATE の安全弁）
                hc = p["hc"]
                if hc[DRAGAPULT_EX] >= 1 or any(hc[c] >= 1 for c in DIG_OUT_IDS):
                    self._attach_tag = "DUSK_CONCENTRATE: no dispersal (finish the charged one)"
                    return -1
        score = 20000
        if e == 1:
            if pokemon.energyCards and attach_id == pokemon.energyCards[0].id:
                return -1   # 同色2枚目は不要（Phantom Dive は {R}{P} の2色）
            if pokemon.id == DRAGAPULT_EX:
                score += 250
            elif pokemon.id == DRAKLOAK:
                score -= 120
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
                    score += 120   # div-D7
                elif pokemon.id == DREEPY:
                    score += 100
                else:
                    score += 50
                if p["bench_attacker"]:
                    score -= 200
        if pokemon.id == DRAGAPULT_EX and e < 2:
            score += 25000   # Phantom Dive 起動の最速化
        if p["no_more_dex"] and pokemon.id in (DREEPY, DRAKLOAK):
            score -= 500
        return score

    # ═══════════ R-13+: 「この番に即プレイできるか」（切る/呼ぶ/打つ順の共通述語） ═══════════

    def _playable_now(self, obs, cid):
        """手札の cid を【この番のうちに】場へ出せるか。

        判定はエンジンの選択肢（合法手）が根拠。ただしサポートだけは1番1枚の制約があるので、
        「この番打つと決めた1枚」以外は即プレイ不能として扱う（ユーザー 2026-07-26:
        リーリエを打つと決まっているなら他のサポートは積極的に切ってよい）。"""
        # ふしぎなアメの例外【ユーザー 2026-07-26】: アメは「ハイパーボールで持ってくる札で
        # 即プレイ可能になるならホールド」。むしろアメが手札にある時は2進化を能動的に掘って
        # 同ターンに同時プレイするのが正解（ドラパルト ex 優先・ヨノワールは従属）。
        # 素の合法性判定だと、2進化が手札に無い間ずっと「即プレイ不能」になって切られてしまう。
        if cid == RARE_CANDY and DUSK_CANDY_HOLD:
            pp = self.p or {}
            hc2, deck2 = pp.get("hc") or {}, pp.get("deck_counts") or {}
            if (pp.get("can_evolve_dreepy")
                    and (hc2.get(DRAGAPULT_EX, 0) >= 1 or deck2.get(DRAGAPULT_EX, 0) >= 1)):
                return True
            if (pp.get("can_evolve_duskull")
                    and not (self.vs_grimmsnarl() and DUSK_GRIM_NOBOMB)
                    and (hc2.get(DUSKNOIR, 0) >= 1 or deck2.get(DUSKNOIR, 0) >= 1)):
                return True
        if cid is None or cid not in (self._playable_ids or ()):
            return False
        data = CARD_DB.get(cid)
        if data is not None and data.cardType == CardType.SUPPORTER:
            return (not obs.current.supporterPlayed) and cid == self.use_support
        return True

    def _fetch_playable_now(self, obs, p, cid):
        """ハイパーボール等で山から**手札に取った直後にそのまま場へ出せる**カードか。

        たね = ベンチに空きがあれば可。進化カード = 対応する進化元が場にいる（またはドラメシヤ/
        ヨマワル + ふしぎなアメ）なら可。手札で腐る2進化を掘らないための判定。"""
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
        if cid == DUSCLOPS:
            return bool(p["can_evolve_duskull"])
        if cid == DUSKNOIR:
            return bool(p["can_evolve_dusclops"]
                        or (p["can_evolve_duskull"] and hc[RARE_CANDY] >= 1))
        # たね: ベンチに空きがあるか
        return len(ms.bench or []) < getattr(ms, "benchMax", 5)

    def _dive_now_after_evolve(self, obs, target):
        """この進化を実行したら【この番のうちに】ファントムダイブを撃てるか（確定判定）。

        ファントムダイブは {炎}{超}。進化してもエネは引き継がれるので、進化後の不足色は
        target に今ついている色だけで決まる。撃てるのはバトル場だけなので呼び出し側で
        ACTIVE に限定する。**確定できる経路だけを True** にする（推測では上げない）:
          ① もう {炎}{超} が揃っている → 進化した瞬間に撃てる
          ② 1色不足 かつ 手張り権が残っていて不足色が手札にある
          ③ 1色不足 かつ サポート未使用でアカマツが手札にあり、不足色が山に残っている
             （アカマツは山から基本エネを2枚まで、1枚を場に付け1枚を手札へ）
          ④ 2色不足 かつ 手張り権もサポートも残っていてアカマツがあり、両色が山にある
             （アカマツで1枚付与＋手札に来た1枚を手張り）"""
        if target is None:
            return False
        have = {c.id for c in (getattr(target, "energyCards", None) or []) if c is not None}
        need = {FIRE_ENERGY, PSYCHIC_ENERGY} - have
        if not need:
            return True
        ms = my_state(obs)
        hand = [c.id for c in (ms.hand or []) if c is not None]
        deck = (self.p or {}).get("deck_counts") or {}
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

    def _dive_secured(self, obs):
        """ファントムダイブが【もう確定している】か（ユーザー 2026-07-26）。

        「エネルギーを散らしてよいのは、散らしてもダイブが確定するときだけ。ボスの指令で
        2エネのドロンチを吊られる心配は、まずダイブが撃てることを満たしてから」という
        優先順位の実装。確定と見なすのは次の3つだけ（推測での確定は認めない）:
          ① この番すでにダイブが撃てる（can_main_attack）
          ② 場のドラパルト ex に {炎}{超} が揃っている（次の番に確実に撃てる）
          ③ {炎}{超} が揃ったドロンチ／ドラメシヤがいて、手札に進化先が揃っている
             （ドロンチ→ex 1枚 / ドラメシヤ→ex + ふしぎなアメ）"""
        if self.flags.get("can_main_attack"):
            return True
        hc = (self.p or {}).get("hc") or {}
        for pk in all_my_pokemon(obs):
            if pk is None or pk.id not in DRAGAPULT_LINE:
                continue
            cols = {c.id for c in (pk.energyCards or []) if c is not None}
            if FIRE_ENERGY not in cols or PSYCHIC_ENERGY not in cols:
                continue
            if pk.id == DRAGAPULT_EX:
                return True
            if hc.get(DRAGAPULT_EX, 0) < 1:
                continue
            if pk.id == DRAKLOAK:
                return True
            if pk.id == DREEPY and hc.get(RARE_CANDY, 0) >= 1:
                return True
        return False

    def _best_attach(self, obs, p, attach_id):
        ms = my_state(obs)
        best = -10000
        for pk in ms.active:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, True))
        for pk in ms.bench:
            if pk is not None:
                best = max(best, self._attach_score(obs, p, attach_id, pk, False))
        return best

    def _rosa_enables(self, obs, p):
        """ルール3の発火条件: 「使えないと技が打てない・使えばドラパルトが技を打てる」。
        アクティブの Dragapult ex のエネ不足を、トラッシュの基本エネで埋められるか。"""
        if self.flags.get("can_main_attack"):
            return False
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return False
        have = [c.id for c in (active.energyCards or [])]
        dc = p["dc"]
        need = []
        if FIRE_ENERGY not in have:
            need.append(FIRE_ENERGY)
        if PSYCHIC_ENERGY not in have:
            need.append(PSYCHIC_ENERGY)
        if not need or len(need) > 2:
            return False
        return all(dc[cid] >= 1 for cid in need)

    # ── 手札価値（PLAY/サーチ/DISCARD の共通材料） ──

    def _draw_count_this_turn(self, obs):
        """このターンまだ山を見られる枚数の近似。Recon Directive（場のドロンチ = top2 見て
        1枚 ≈ 1）+ リーリエ（サポート未使用時 ≈ 6）。※ v1 近似。ワイルド（ハイパーボール
        任意サーチ）は _dive_prob 側で確定扱い。Crispin/精密 Recon は Phase 2。"""
        p = self.p
        n = p["fc"][DRAKLOAK]
        if p["hc"][LILLIE] >= 1 and not obs.current.supporterPlayed:
            n += 6
        return n

    def _draw_hit_prob(self, obs, K):
        """このターンのドロー枚数 N で、山の当たり K 枚のうち1枚以上を引ける確率（単変量超幾何）。
        K は呼び出し側で「開いてるチャネルの当たり総数」を渡す（K<=0 は死に線=0.0）。"""
        if K <= 0:
            return 0.0
        deck = self.p["deck_counts"]
        D = sum(v for v in deck.values() if v > 0)
        N = self._draw_count_this_turn(obs)
        if N <= 0 or D <= 0:
            return 0.0
        if K >= D or N >= D or N > D - K:
            return 1.0                      # 引く枚数が外れ枚数を超える等 = 必ず当たる
        from math import comb
        return 1.0 - comb(D - K, N) / comb(D, N)

    def _color_reach_prob(self, obs, need_ids):
        """バトル場/進化先が、このターン中に不足色 need_ids を全て乗せられる確率（超幾何 v1）。
        手段: 手張り(1色) / アカマツ(2色ぶん) / ハイパーボール確定サーチ。各チャネルは
        「その番まだ使えるか」(energyAttached / supporterPlayed) で開閉する（行動列の記憶）。
          need_ids=[]  → 1.0（色は足りている）
          len==1       → 手張り or アカマツ
          len==2       → アカマツ必須（手張りは1回=1色まで）"""
        m = len(need_ids)
        if m == 0:
            return 1.0
        p = self.p
        hc, deck = p["hc"], p["deck_counts"]
        color_ch = not obs.current.energyAttached      # 手張り権（1回=1色）
        crispin_ch = not obs.current.supporterPlayed    # アカマツ権（=2色ぶん）
        ub_ready = hc[ULTRA_BALL] >= 1 and len(my_state(obs).hand or []) >= 3
        if m >= 2:
            # 2色を1ターンで乗せるには実質アカマツ（手張りは1色まで）。
            if not crispin_ch:
                return 0.0
            if hc[CRISPIN] >= 1:
                return 1.0                  # 手札のアカマツを打てば確定
            if deck[CRISPIN] <= 0:
                return 0.0                  # アカマツが手札にも山にも無い = 2色は無理
            if ub_ready:
                return 1.0                  # UB でアカマツを確定サーチ→即打ち
            return self._draw_hit_prob(obs, deck[CRISPIN])
        # m == 1: 不足1色。手張り(その色) or アカマツ。
        need = need_ids[0]
        if not color_ch and not crispin_ch:
            return 0.0                      # 手張りもサポートも使い切り = このターン不可
        if (color_ch and hc[need] >= 1) or (crispin_ch and hc[CRISPIN] >= 1):
            return 1.0                      # 手札に必要色(張れる) or アカマツ(打てる) = 確定
        K = (deck[need] if color_ch else 0) + (deck[CRISPIN] if crispin_ch else 0)
        if K <= 0:
            return 0.0                      # 開いてるチャネルの当たりが山でも枯れ = 死に線
        if ub_ready:
            return 1.0                      # UB で色 or アカマツを確定サーチ（当たりは山に在る）
        return self._draw_hit_prob(obs, K)

    def _dive_prob_this_turn(self, obs):
        """バトル場ドラパルト ex が、このターン不足色を取って Phantom Dive を撃てる確率。
        1.0=確定 / 0.0=死に線（deck_counts で厳密判定）/ 灰色=超幾何。EV は扱わず確率のみ。
        色到達は _color_reach_prob に委譲（不足0/1色を一般に扱う）。
        チャネル3=メイのはげまし(Rosa) は手張り/アカマツと別経路（トラッシュ発・山に無くても撃てる）
        なので、確定完成する局面はここで先に 1.0 を返す（ユーザー指摘 2026-07-26）。"""
        active = active_pokemon(obs)
        if active is None or active.id != DRAGAPULT_EX:
            return 1.0
        # チャネル3: Rosa — サイド負け時、トラッシュの基本エネ2枚を2進化(ex)へ付けて確定完成
        # （Rosa 手札＋サポート権残＋prize_diff>0＋不足色がトラッシュ = _rosa_enables）。
        p = self.p
        if (p["hc"][ROSA] >= 1 and not obs.current.supporterPlayed
                and p["prize_diff"] > 0 and self._rosa_enables(obs, p)):
            return 1.0
        types = [c.id for c in (active.energyCards or [])]
        need_ids = [cid for cid in (FIRE_ENERGY, PSYCHIC_ENERGY) if cid not in types]
        return self._color_reach_prob(obs, need_ids)

    def _dive_prob_drakloak(self, obs):
        """バトル場ドロンチが、このターン中に進化(→ドラパルト ex)＋{R}{P} を揃えて Phantom Dive
        を撃てる確率（v1 近似）。進化out × 色out の独立積で保守的に見積もる。
          進化out … active ドロンチにドラパルト ex を今ターン乗せられるか（手札/UB確定/ドロー超幾何）
          色out  … ドロンチ上の現エネから不足色を今ターン満たせるか（進化でエネ持ち越し）
        ※ 両者は同じドローを食い合うため厳密には独立でない。ドロンチ露出のケアは低め P が安全側
          （ユーザー『ドロンチをさらけ出すのは明確に不利』）なので v1 は積で保守的に寄せる。
        ※ 既知の過大: 進化と色の双方が『UBで唯一の1枚を取る』に依存する稀ケースは積が過大評価。"""
        active = active_pokemon(obs)
        if active is None or active.id != DRAKLOAK:
            return 0.0
        p = self.p
        hc, deck = p["hc"], p["deck_counts"]
        # 進化 out: 今ターン active ドロンチに ドラパルト ex を乗せられるか
        if hc[DRAGAPULT_EX] >= 1:
            p_evo = 1.0
        elif (hc[ULTRA_BALL] >= 1 and len(my_state(obs).hand or []) >= 3
                and deck[DRAGAPULT_EX] >= 1):
            p_evo = 1.0                     # UB でドラパルト ex を確定サーチ
        else:
            p_evo = self._draw_hit_prob(obs, deck[DRAGAPULT_EX])
        if p_evo <= 0.0:
            return 0.0                      # ドラパルト ex が場にも山にも無い = 死に線
        # 色 out: ドロンチ上の現エネから {R}{P} の不足色を満たせるか（進化で持ち越し）
        types = [c.id for c in (active.energyCards or [])]
        need_ids = [cid for cid in (FIRE_ENERGY, PSYCHIC_ENERGY) if cid not in types]
        return p_evo * self._color_reach_prob(obs, need_ids)

    def _ensure_dive_plan(self, obs):
        """【ターン頭で一度だけ】ダイブ『持続 vs 損切り』を確定してキャッシュ。以後その番は
        _dive_plan を固定参照し、手札/盤面が変わっても判断をブレさせない（ユーザー 2026-07-25）。"""
        turn = getattr(obs.current, "turn", -1)
        if turn == self._dive_plan_turn and self._dive_plan is not None:
            return
        self._dive_plan_turn = turn
        self._dive_plan = self._compute_dive_plan(obs) if DUSK_STREAMS else None

    def _compute_dive_plan(self, obs):
        """露出中の本流ポケモン（準備中ドラパルト ex(e<2) or 掘り進め中ドロンチ）について
        persist(持続=掘る) / losscut(損切り=散らす) を確定して返す。対象外は None。優先順:
          ① ダイブが原理的に不可能（必要色/進化先が手札にも山にも無い）→ 損切り確定
             （打てないのに掘り続けない。ユーザー 2026-07-26）。閾値に優先。
          ② e==0 ドラパルト ex の立ち上げ（複数ターン手張りで構築）→ 常に持続（従来）。
          ③ それ以外 → 今ターンのダイブ確率 P と単一閾値 DUSK_TH_DIVE 比較（既定0.0=常に持続）。"""
        active = active_pokemon(obs)
        ms = my_state(obs)
        if active is None or ms.deckCount <= 0:
            return None
        e = len(active.energyCards or [])
        if active.id == DRAGAPULT_EX and e < 2:
            kind = "dragapult"
        elif active.id == DRAKLOAK:
            kind = "drakloak"
        else:
            return None
        th = self._dive_threshold(obs)
        if self._dive_impossible(obs):
            return {"kind": kind, "persist": False, "prob": 0.0, "threshold": th}
        if kind == "dragapult" and e == 0:
            return {"kind": kind, "persist": True, "prob": None, "threshold": th}
        prob = (self._dive_prob_this_turn(obs) if kind == "dragapult"
                else self._dive_prob_drakloak(obs))
        return {"kind": kind, "persist": prob >= th, "prob": prob, "threshold": th}

    def _dive_impossible(self, obs):
        """ファントムダイブが原理的に不可能（＝打てない）な局面か。必要色 {R}{P} のうち少なくとも
        1色が『手札・山・（夜のタンカ or メイのはげましで使える）トラッシュ』のどこからも取れない
        ＝永久に張れない＝ダイブ完成不能。ドロンチはさらに進化先ドラパルト ex が同様に取れなければ
        進化不能。True なら閾値に関わらず損切り確定（ユーザー 2026-07-26: 打てないならパッシブ確定）。

        トラッシュ回収は2枚:
          夜のタンカ(Night Stretcher) … Pokémon か基本エネを1枚トラッシュ→手札
          メイのはげまし(Rosa)        … トラッシュの基本エネを最大2枚、2進化(ex)へ付ける
        いずれかが手札か山にある間は、トラッシュの必要『色』は回収/使用可能として不可能から除外。
        ※ ex(ポケモン)の回収は夜のタンカのみ（Rosa は基本エネ専用）。サイド落ちは回収不可＝不可能。
        ※ 保守設計: 複数不足でも各色を独立に回収可と見なし、Rosa の prize 条件も緩め扱い
          （＝不可能を過小申告＝アグレ側に倒す＝生きた線の損切り誤爆を防ぐ）。"""
        active = active_pokemon(obs)
        if active is None or active.id not in (DRAGAPULT_EX, DRAKLOAK):
            return False
        p = self.p
        hc, deck, dc = p["hc"], p["deck_counts"], p["dc"]
        # トラッシュの基本エネを使える札（夜のタンカ or Rosa）が手札か山にあるか
        recov_energy = (hc[NIGHT_STRETCHER] + deck[NIGHT_STRETCHER]
                        + hc[ROSA] + deck[ROSA]) >= 1
        ns_avail = hc[NIGHT_STRETCHER] + deck[NIGHT_STRETCHER] >= 1  # ex(ポケモン)回収は夜タンカのみ
        types = [c.id for c in (active.energyCards or [])]
        for cid in (FIRE_ENERGY, PSYCHIC_ENERGY):
            if cid in types:
                continue
            if hc[cid] + deck[cid] >= 1:
                continue                    # 手札か山にある = 張れる
            if recov_energy and dc[cid] >= 1:
                continue                    # トラッシュにあり回収札(夜タンカ/Rosa)がある = 使える
            return True                     # その色をどこからも取れない = 永久に張れない
        if active.id == DRAKLOAK:
            ex_ok = (hc[DRAGAPULT_EX] + deck[DRAGAPULT_EX] >= 1
                     or (ns_avail and dc[DRAGAPULT_EX] >= 1))
            if not ex_ok:
                return True                 # 進化先ドラパルト ex も取れない = 進化不能
        return False

    def _dive_needs_crispin(self, obs):
        """このターンのダイブ完成が『アカマツを打つ』ことを要する局面か（手張りだけでは不可）。
        ルート実行用: True かつ持続ターンなら use_support をアカマツに固定して計算ルートを辿らせる。
        対象は準備中ドラパルト ex か掘り進め中ドロンチ。アカマツが手札・サポート権残が前提。"""
        if obs.current.supporterPlayed:
            return False
        p = self.p
        if p["hc"][CRISPIN] < 1:
            return False
        active = active_pokemon(obs)
        if active is None or active.id not in (DRAGAPULT_EX, DRAKLOAK):
            return False
        types = [c.id for c in (active.energyCards or [])]
        missing = [cid for cid in (FIRE_ENERGY, PSYCHIC_ENERGY) if cid not in types]
        m = len(missing)
        if m == 0:
            return False                    # 色は足りている
        if active.id == DRAKLOAK:
            # ドロンチは進化(ドラパルト ex)も必要。ex を『サポート以外』で確保できる時だけ寄せる
            # （さもなくばリーリエ等で ex を掘る番を潰さない）。
            ub_ready = (p["hc"][ULTRA_BALL] >= 1
                        and len(my_state(obs).hand or []) >= 3)
            if not (p["hc"][DRAGAPULT_EX] >= 1 or ub_ready):
                return False
        if m >= 2:
            return True                     # 2色は手張り1回では無理 = アカマツ必須
        return obs.current.energyAttached   # m==1: 手張り権が無い時のみアカマツ必須

    def _dive_threshold(self, obs):
        """ダイブ「持続 vs 損切り」の単一閾値（2026-07-26 統一・アグレッシブ既定 0.0）。
        旧 2×2(safe×pain) は実測で無効（グリッド平坦・両極端でアグレが全対面優位）と判り廃止。
        obs は将来また状態依存にしたくなった時のため受けるだけ（現状は未使用）。"""
        if DUSK_GRIM_CANARY and self.vs_grimmsnarl():
            return 1.0      # ゲート検証器用のカナリア（既定OFF）。本番の既定挙動には無関与
        return DUSK_TH_DIVE

    def _plan_phase(self, obs, p):
        """本流の進行フェーズ（ユーザー構想 2026-07-25）。
          setup   … ドロンチもドラパルト ex も未着地 = ムズムズ + engine を作る立ち上げ
          priming … ドロンチ着地・ドラパルト ex 未完成 = ダイブ完成へ最短
          online  … ドラパルト ex 着地 = ダイブ稼働。サブストリーム(ボム/アドレナ)起動可"""
        fc = p["fc"]
        if fc[DRAGAPULT_EX] >= 1:
            return "online"
        if fc[DRAKLOAK] >= 1:
            return "priming"
        return "setup"

    def _munki_ok(self, obs, p):
        """マシマシラ(アドレナ)= サブストリーム。本流が稼働(online)してから、または
        終盤(相手サイド<=3 の詰め)でのみ場に出す/起動する。立ち上げ・始動では休眠。"""
        return (self._plan_phase(obs, p) == "online"
                or len(opp_state(obs).prize) <= 3)

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
        elif cid in DUSKNOIR_LINE and self.vs_grimmsnarl() and DUSK_GRIM_NOBOMB:
            # G-3: 対オーロンゲではボムラインを展開しない（ベンチ枠・サーチ先・アメ・
            # 立ち上がりのアクションを本流に集中させる。トラッシュ要員として切ってよい）
            score = UNNECESSARY
        elif cid == DUSKULL:
            line = fc[DUSKULL] + fc[DUSCLOPS] + fc[DUSKNOIR]
            # サブストリーム: 立ち上げ(setup)ではボムは種1体までのサブタスク。engine
            # (Dreepy 18000 / Drakloak 20000 / Budew 30000) を追い越さない 4000 帯に留め、
            # ベンチ枠と手札を本流に集中。始動/詰め(priming/online)では通常展開
            if DUSK_STREAMS and self._plan_phase(obs, p) == "setup":
                score = 4000 if line == 0 else 60
            else:
                score = 15000 if line < 2 else 100
        elif cid == DUSCLOPS:
            score = 17000 if p["can_evolve_duskull"] else 2500
        elif cid == DUSKNOIR:
            if p["can_evolve_dusclops"]:
                score = 21000
            elif p["can_evolve_duskull"] and hc[RARE_CANDY] >= 1 and not p["no_item"]:
                score = 20000
            else:
                score = 1500
        elif cid == MUNKIDORI:
            # サブストリーム: マシマシラは本流稼働(online)/終盤のみ場に出す。立ち上げ・始動では
            # **ハード休眠**（UNNECESSARY = 手札に温存。ベンチ枠・手張り・進化を本流に集中）。
            # ソフト降格(40)だと他に手が無い番に出てしまい従属が漏れる（プローブで実測）
            if fc[MUNKIDORI] >= 1:
                score = 30
            elif DUSK_STREAMS and not self._munki_ok(obs, p):
                score = UNNECESSARY
            else:
                score = 12000
        elif cid == FEZANDIPITI_EX:
            if p["pre_ko"]:
                score = 15000
            elif p["prize_diff"] <= -2:
                score = 5
            elif len(osn.prize) == 1:
                score = UNNECESSARY
        elif cid == BUDEW:
            # GL-3: ロック中はスボミーを切らさない。既定ルールは「ドロンチ/ドラパルトが
            # 立ったらスボミーは不要」だが、対オーロンゲではロックが勝ち筋なので逆
            # （ポフィン・ポケパッド・ハイパーボール・夜のタンカ の第一対象になる）
            if self._grim_lock() and fc[BUDEW] == 0:
                score = 36000
            elif fc[BUDEW] + fc[DRAKLOAK] + fc[DRAGAPULT_EX] >= 1:
                score = UNNECESSARY
            # DUSK_OPEN_BUDEW（ユーザー 2026-07-25）: 序盤 Poffin で Dreepy と一緒に
            # スボミーを盤面へ（先行T1=turn 1 も。旧 turn>=2 ゲートを解錠）
            elif DUSK_OPEN_BUDEW or obs.current.turn >= 2:
                score = 30000
        elif cid == MEOWTH_EX:
            if p["support_count"] > hc[BOSS] or p["stadium_id"] == WATCHTOWER:
                score = 5
            elif obs.current.supporterPlayed:
                score = 40
            else:
                score = 35000
        elif cid == RARE_CANDY:
            if p["can_evolve_dreepy"] and hc[DRAGAPULT_EX] >= 1 and not p["no_more_dex"]:
                score = 40000
            elif p["can_evolve_duskull"] and hc[DUSKNOIR] >= 1:
                score = 38000
            elif p["no_more_dex"] and deck[DUSKNOIR] + hc[DUSKNOIR] == 0:
                score = UNNECESSARY
        elif cid == UNFAIR_STAMP:
            if p["pre_ko"]:
                score = 80000
            elif len(osn.prize) == 1:
                score = UNNECESSARY
            else:
                score = 80
        elif cid == POFFIN:
            # G-3: 対オーロンゲではポフィンでヨマワルを拾わない（本流のたねだけ数える）
            count = deck[DREEPY]
            if deck[DUSKULL] >= 1 and not (self.vs_grimmsnarl() and DUSK_GRIM_NOBOMB):
                count += 1
            if count == 0:
                score = UNNECESSARY
            else:
                # GL-3: ロック中はターン制限なくスボミーをポフィンの対象に数える
                if ((obs.current.turn <= 2 or self._grim_lock())
                        and fc[BUDEW] == 0 and deck[BUDEW] >= 1):
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
        elif cid == ULTRA_BALL:
            score = 70 if (p["main_pokemon_count"] <= 2 or fc[DREEPY] >= 1) else 5
        elif cid == POKE_PAD:
            score = max(self._hand_score(obs, p, DREEPY, ignore_count),
                        self._hand_score(obs, p, DRAKLOAK, ignore_count),
                        self._hand_score(obs, p, DUSKULL, ignore_count),
                        self._hand_score(obs, p, DUSCLOPS, ignore_count),
                        self._hand_score(obs, p, DUSKNOIR, ignore_count),
                        self._hand_score(obs, p, MUNKIDORI, ignore_count),
                        self._hand_score(obs, p, BUDEW, ignore_count))
        elif cid == BROCK:
            # v2 リストの新規カード（2026-07-26）。たね2枚を一度に取れるので、
            # 立ち上げでは「スボミー＋ドラメシヤ」を1枚で揃えられる = リーリエより上。
            # 中盤以降は進化1枚サーチに落ちるのでリーリエ(45800)の下に置く。
            if not ignore_count or p["support_count"] == 0:
                if obs.current.turn <= 2 and fc[BUDEW] == 0:
                    score = 50000
                else:
                    score = 30000
        elif cid == BOSS:
            if self.plan_a["attack"] > 0:
                score = 60000   # R-16
        elif cid == CRISPIN:
            if not ignore_count or p["support_count"] == 0:
                colors = [c for c in BASIC_ENERGIES if deck[c] > 0]
                if len(colors) < 2:
                    score = 10
                elif (not f["can_main_attack"] and not p["bench_attacker"]
                        and fc[DRAGAPULT_EX] >= 1):
                    score = 55000
                else:
                    score = 25000
        elif cid == LILLIE:
            if not ignore_count or p["support_count"] == 0:
                score = 45000
        elif cid == DAWN:
            # ルール6: 基本はリーリエ(45000)未満。「この番ファントムダイブが打てる ∧
            # 手札にエネあり」のときだけリーリエ超え（リフレッシュで手札のエネを
            # 山へ戻さず、進化パーツを取りに行く）
            if not ignore_count or p["support_count"] == 0:
                targets = (deck[DREEPY] + deck[DUSKULL] + deck[DRAKLOAK]
                           + deck[DUSCLOPS] + deck[DRAGAPULT_EX] + deck[DUSKNOIR])
                if targets == 0:
                    score = 20
                elif f["can_main_attack"] and p["energy_in_hand"] >= 1:
                    score = 46000
                else:
                    score = 43000
        elif cid == ROSA:
            # ルール3: 通常は温存（低帯）。「使えばドラパルトが技を打てる」局面で
            # リーリエ超え。エンジン条件（サイド負け時のみ）は engine 側が合法性で弾く
            if not ignore_count or p["support_count"] == 0:
                if p["prize_diff"] > 0 and self._rosa_enables(obs, p):
                    score = 47000
                else:
                    score = 200
        elif cid == WATCHTOWER:
            if p["stadium_id"] != 0 and p["stadium_id"] != WATCHTOWER:
                score = 4000
        elif cid == RISKY_RUINS:
            # G-2: 対オーロンゲでは張らないので手札に取る価値も無い（サーチ先から外す）
            if self.vs_grimmsnarl() and DUSK_GRIM_RUINS:
                score = 0
            elif p["stadium_id"] != RISKY_RUINS:
                score = 3000
        elif cid in BASIC_ENERGIES:
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
                score -= 100000   # 同名2枚目の割引（R-13 の順序側）
        return score

    # ── CARD 選択（前出し・サーチ先・配分・DISCARD 等） ──

    def _score_promote(self, obs, opt):
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
                # GL-2: ロック中は SWITCH 文脈でも無条件で最優先（ロックを切らさない）
                if ctx != SelectContext.SWITCH or self._grim_lock():
                    score += 100000
                elif not self.p.get("bench_attacker"):
                    score += 30000
            elif cid == DUSKNOIR:
                score += 5000
            elif cid == DUSCLOPS:
                score += 4000
            elif cid == DUSKULL:
                score += 3000
            elif cid == MUNKIDORI:
                score += 2000
            elif cid == FEZANDIPITI_EX:
                score -= 1000
            elif cid == MEOWTH_EX:
                score -= 2000
            score += e * 1000 + hp
            return self.default_score_promote(obs, opt, score, "S-1: promote")   # R-08
        if self.plan_a["attack"] == opt.index + 1:
            return 100000 + e * 1000 + hp, "R-16: pull plan target"
        return e * 1000 + hp, "pull: energy/hp heuristic"

    @staticmethod
    def _take_band(score):
        if score >= 0:
            return min(score, 900000)
        return (200000 + max(score, -200000)) / 200000.0

    def _score_card(self, obs, opt):
        p = self.p
        ctx = obs.select.context
        yi = obs.current.yourIndex
        card = option_card(obs, opt)
        cid = card.id if card is not None else getattr(opt, "cardId", None)

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            return self._score_promote(obs, opt)

        if ctx in (SelectContext.TO_BENCH, SelectContext.TO_HAND):
            if cid is None:
                return 0, "take none"
            score = self._hand_score(obs, p, cid, False)
            p["hc"][cid] += 1
            if p["effect_id"] == CRISPIN:
                if cid in BASIC_ENERGIES:
                    # S-6a（3色対応）: 手札に取らなかった色が場に付く。残る色の
                    # 最良付け先価値（S-5）が最も高くなる色を手札に取る。
                    # 逆色が山に残らない色は付与消滅のため降格【ハード】
                    others = [o for o in BASIC_ENERGIES if o != cid
                              and any(c is not None and c.id == o
                                      for c in (obs.select.deck or []))]
                    if others:
                        score = 100000 + max(self._best_attach(obs, p, o) for o in others)
                    else:
                        score = 50
                else:
                    score = 100000 - self._hand_score(obs, p, cid, True)
            # ルール10: 詰まり脱出コンボの取得先を固定 —
            # ハイパーボールはニャースを掘り、ニャースのサポートサーチはリーリエへ
            if self.stuck and p["effect_id"] == ULTRA_BALL and cid == MEOWTH_EX:
                score = max(score, 46000)
            if self.stuck and p["effect_id"] == MEOWTH_EX and cid == LILLIE:
                score = max(score, 61000)   # ボス(60000)より上 = 詰まり時はリーリエ直行
            # DUSK_PAD_DRAKLOAK（ユーザー 2026-07-25）: ポケパッドで手札に取るとき、
            # 場にドラメシヤを用意できる（進化元が居る）ならドロンチを優先的に持ってくる
            # （Dusknoir 21000 の上に置く。ダイブ線の次ターン完成を最優先）
            if (DUSK_PAD_DRAKLOAK and ctx == SelectContext.TO_HAND
                    and p["effect_id"] == POKE_PAD and cid == DRAKLOAK
                    and p["can_evolve_dreepy"]):
                score = max(score, 33000)
            # R-13+③: ハイパーボールで呼ぶ札も「即プレイできる札」に限る。進化先が場に
            # 無い2進化を掘っても手札で腐り、次のハイパーボールで切る羽目になる。
            if (DUSK_PLAYABLE_NOW and ctx == SelectContext.TO_HAND
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
            # R-13+①: 切るのは「この番に即プレイできない札」から。即プレイできる札は
            # 一律 200,000 下へ落として最後まで残す（不能札の評価順 = 従来どおり保存される。
            # 不能札のスコアは -80,000 以上なので、この差は必ず勝つ）
            if DUSK_PLAYABLE_NOW and self._playable_now(obs, cid):
                return min(score, 900000) - 200000, "R-13+: keep (playable this turn)"
            return min(score, 900000), "R-13: discard lowest value"

        if ctx in (SelectContext.DAMAGE_COUNTER, SelectContext.DAMAGE_COUNTER_ANY):
            return self._score_counter(obs, opt, card, ctx)

        if ctx == SelectContext.DAMAGE:
            # E-6: アドレナブレインの移動元（自分側）/ 移動先（相手側）
            if p["effect_id"] == MUNKIDORI:
                pi = opt.playerIndex if opt.playerIndex is not None else yi
                if pi == yi:
                    return self._score_adrena_source(obs, card)
                return self._score_adrena_target(obs, opt, card)
            return self.default_score_damage_target(obs, opt)   # R-15

        if ctx == SelectContext.REMOVE_DAMAGE_COUNTER:
            # E-6: アドレナブレインの移動元（エンジン経路の別形）
            return self._score_adrena_source(obs, card)

        if ctx == SelectContext.ATTACH_TO:
            if cid is None:
                return 0, "attach none"
            return self._take_band(self._best_attach(obs, p, cid)), "S-6b: attach energy pick"

        if ctx == SelectContext.ATTACH_FROM:
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

    def _score_adrena_source(self, obs, card):
        """アドレナブレインの移動元: ドラパルトライン（タンク・進化元）の回復を優先。
        マシマシラ自身は重傷時のみ救出（marnie div-11 v2 準拠）。"""
        if card is None:
            return 0, "adrena source none"
        dmg = damage_on(card)
        cid = card.id
        if cid == MUNKIDORI and dmg >= 60:
            return 3000 + dmg, "E-6: rescue heavily-hit Munkidori"
        if cid == DRAGAPULT_EX:
            return 2200 + dmg, "E-6: heal Dragapult ex"
        if cid in (DREEPY, DRAKLOAK):
            return 1800 + dmg, "E-6: heal evolving line"
        if cid == MUNKIDORI:
            return -1000 + dmg, "E-6: keep Munkidori damage"
        return 1000 + dmg, "E-6: heal other"

    def _score_adrena_target(self, obs, opt, card):
        """アドレナブレインの移動先（相手側）: 取り切り最優先、次にボム/配分の布石。
        アドレナは特性 = ミストを貫通（除外は本体特性のみ）。"""
        if card is None:
            return 0, "adrena target none"
        if _counter_blocked_by_body(card):
            return -1, "E-6: body-ability guard"
        hp = getattr(card, "hp", 999)
        if hp <= 30:
            return 15000 + (500 - hp), "E-6: counter-move KO"
        if card.id in BONUS_COUNTER_TARGETS:
            return 12000 - hp, "E-6: priority snipe target"
        return self.default_score_damage_target(obs, opt)   # R-15

    def _score_counter(self, obs, opt, card, ctx):
        """E-2: ダメカン配分（S-7 探索計画 + カーズドボムの対象選択）。"""
        if card is None or getattr(card, "hp", 0) <= 0:
            return 0, "counter none"
        p = self.p
        hp = card.hp
        score = 100000 - 10 * hp + self._pokemon_score(card, False)
        if ctx == SelectContext.DAMAGE_COUNTER:
            # ボムの対象選択（effect = サマヨール/ヨノワール）は計画の対象に固定。
            # ボムは特性なのでミストを貫通（除外は本体特性のみ）
            if p["effect_id"] in (DUSCLOPS, DUSKNOIR):
                bp = self.bomb_plan
                coord = 0 if opt.area == AreaType.ACTIVE else (opt.index or 0) + 1
                if bp is not None and coord == bp["coord"]:
                    return 500000, "B-1: bomb plan target"
                if _counter_blocked_by_body(card):
                    return -1, "E-2: body-ability guard"
                return score, "B-1: bomb fallback (off-plan)"
            # ルール9【ハード】: ワザ効果の単発ダメカンもミスト装着体を指定しない
            if _no_damage_counter(card):
                return -1, "rule9: mist/no-counter guard"
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
        if self.USE_SPREAD_SEARCH and self.spread_plan is not None:
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
# R-25【ハード】: def agent は必ずファイル末尾の callable にする。

_impl = make_agent(DragapultDusknoirPolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
