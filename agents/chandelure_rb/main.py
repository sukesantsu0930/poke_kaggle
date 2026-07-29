"""シャンデラ（Chandelure コントロール / 山札切れ = ミル）ルールベースエージェント

7/6メタのレート1000+勝ち組（kidekikish 1065.5、実測17勝5敗=77.3%）の移植。
設計文書: docs/planning/デッキ設計_シャンデラ.md（S-x/E-x/実測データ/未決事項）

コンセプト:
  自分はほぼダメージを出さない。コンフィの Flower Shower（お互い3ドロー）と
  シャンデラの特性 Alluring Light（お互い1ドロー）で相手を山札切れに追い込み、
  自分の山はリーリエの決心（手札を山へ戻す）で回復してミルレースに勝つ。
  防御は NZ（ex攻撃無効）+ シェイミ（ベンチ保護）+ バトルケージ（ダメカン配置無効）、
  妨害はハンマー（エネ剥がし）+ クセロシキ/エリ（手札破壊）+ ボス+重力宝石（拘束）。
  シャンデラの Mind Ruler は炎コストで不発（エピソード実測で提示0回）= 純粋な特性ボディ。
"""

import os
import sys
from collections import Counter, defaultdict

# sys.path ブートストラップ（base import より前に必須）
try:
    _ROOT = __file__
except NameError:
    _ROOT = None
_CG_PATH = "/kaggle_simulations/agent"
for _p in ([os.path.dirname(os.path.abspath(_ROOT))] if _ROOT else []) + [_CG_PATH]:
    if _p and _p not in sys.path and os.path.isdir(_p):
        sys.path.insert(0, _p)

from cg.api import AreaType, CardType, OptionType, SelectContext

import meta_tables as mt
from policy_base import (
    BasePolicy,
    CARD_DB,
    DIAG,
    active_pokemon,
    all_my_pokemon,
    damage_on,
    energy_count,
    get_card,
    hand_ids,
    has_in_play,
    has_tool,
    is_ex,
    make_agent,
    my_state,
    opp_active_pokemon,
    opp_state,
    option_card,
    option_target,
    payable_attacks,
    retreat_cost,
    read_deck_csv as _read_deck_csv,
)

# ── カードID（デッキ設計_シャンデラ.md のリスト） ──

COMFEY = 164          # コンフィ HP70（Flower Shower: お互い3ドロー = ミル主エンジン）
LITWICK = 97          # ヒトモシ HP60
LAMPENT = 494         # ランプラー HP80
CHANDELURE = 98       # シャンデラ HP130（特性 Alluring Light: お互い1ドロー）
SHAYMIN = 343         # シェイミ HP80（特性 Flower Curtain: 非ルールボックスのベンチ保護）

BASIC_P = 5           # 基本{P}エネ
TELEPATH = 19         # テレパスエネルギー（{P}に手張りで山からたね{P}を2枚ベンチへ）

POFFIN = 1086
POKE_PAD = 1152
RARE_CANDY = 1079
NIGHT_STRETCHER = 1097
ENERGY_SEARCH = 1119
CRUSHING_HAMMER = 1120
ENHANCED_HAMMER = 1081
SWITCH_ITEM = 1123
GRAVITY_GEMSTONE = 1166   # どうぐ: バトル場のにげるコスト+1（両者）= 拘束
LILLIE = 1227             # リーリエの決心: 手札を山へ戻して6ドロー = 山の回復装置
XEROSIC = 1197            # 相手手札を3枚に
HILDA = 1225              # 進化+エネのサーチ
DAWN = 1231               # たね+1進化+2進化のサーチ
ERI = 1186                # 相手手札のグッズを2枚まで破壊
NEUTRAL_ZONE = 1247       # NZ (ACE SPEC): ex/V→非ルールボックスのダメージ全無効
BATTLE_CAGE = 1264        # ベンチへのダメカン配置無効

ATK_FLOWER_SHOWER = 215   # Comfey {P} 0dmg お互い3ドロー
ATK_PLAY_ROUGH = 216      # Comfey {P} 20+コイン20

OPP_MUNKIDORI = 112       # 相手のマシマシラ（バトルケージの主対象）

# ── 決定性ラウンド トグル（EXP-036 第3ラウンド 2026-07-22） ──
# 決定性監査（scripts/decisiveness_audit.py 140戦・純ルール）で、負け試合の
# 無意見決定（首位-2位 margin が 0 or <1000）が SELECT 系に集中していると判明。
# 負け対面は froslass_starmie / marnie に集中し、敗因の型はプライズレース負け
# （相手山3〜6枚まで追い詰めての力尽き = ミルテンポの浪費が直接効く）。
#
# 【判定 2026-07-22 A/B 実測（80戦×7対面 + 160戦確定）】3つの挙動系トグルは
# 全構成で集計悪化（全ON −4.3pt / PROMOTE単 −5.2 / FUEL単 −2.9 / TAKE単 −4.3、
# 160戦確定 全ON −0.7 / プール240戦 −1.8pt）。本デッキの厳格基準
# 「集計 −1pt 超悪化は即 OFF（ルール王者 997.5 非劣化が絶対条件）」により既定 OFF。
# 代わりに CHA_MARGIN（挙動厳密不変のマージン拡幅のみ）を既定 ON で採用 —
# 監査の無意見クラスタ解消は挙動を変えずに達成する（詳細 デッキ設計_シャンデラ.md）。
CHA_MARGIN = os.environ.get("CHA_MARGIN", "1") != "0"            # 挙動不変のマージン拡幅（採用・既定ON）
CHA_PROMOTE = os.environ.get("CHA_PROMOTE", "0") != "0"          # 昇格順ドクトリン（棄却・既定OFF）
CHA_FUEL_TARGET = os.environ.get("CHA_FUEL_TARGET", "0") != "0"  # fuel対象+ミル手順序（棄却・既定OFF）
CHA_TAKE_ENERGY = os.environ.get("CHA_TAKE_ENERGY", "0") != "0"  # TO_HANDエネ使い分け（棄却・既定OFF）
# ── 第4弾（2026-07-24 ユーザー指示。判定は王者ゲート = A/B −1pt 超悪化で即 OFF） ──
CHA_BOSS_HEAVY = os.environ.get("CHA_BOSS_HEAVY", "1") != "0"    # にげ重ベンチの吊り出し（余裕時）
CHA_ERI_IDLE = os.environ.get("CHA_ERI_IDLE", "1") != "0"        # サポート枠が暇なら Eri（ビワ）
CHA_NC_HOLD = os.environ.get("CHA_NC_HOLD", "1") != "0"          # NZ は敗北リーチ可視まで温存
CHA_LILLIE_EARLY = os.environ.get("CHA_LILLIE_EARLY", "1") != "0"  # 後攻T1/先攻T2 はリーリエ優先
# 第16弾（2026-07-27 ユーザー指摘・EXP-060）: リーリエの山札収支を実計算して赤字打ちを止める。
# 0 で旧挙動（手札≤6 のリフレッシュ許可・「手札≥7 で純増」という誤った前提）へロールバック。
CHA_LILLIE_LEDGER = os.environ.get("CHA_LILLIE_LEDGER", "1") != "0"
# 第16弾（2026-07-27 ユーザー指示・EXP-061）: ポフィンは「次のキュワワー在庫が無い」or
# 「ヒトモシラインが2体未満」の時だけ。0 で旧挙動（セットアップ期は常に打つ）へロールバック。
CHA_POFFIN_STRICT = os.environ.get("CHA_POFFIN_STRICT", "1") != "0"
# ── 第18弾（2026-07-27 ユーザー指示・EXP-063）: サポートの基本順序を合理化 ──
# **クセロシキ → ビワ → ボスで縛る**。序盤のボスは逃げられて空振るので、
# ①クセロシキで手札を3枚まで削る ②ビワでピンポイントにリソース（グッズ2枚）を抜く
# ③資源が枯渇したところでボスで拘束する、という資源枯らしのエスカレーション。
# ※厳密な順序強制ではなく**優先度の方針**（クセロシキを優先的に打ち、相手手札が少なければ
#   ビワやボス。ビワとボスならボスのほうが後のほうが嬉しい、という程度）。
# ※**イレギュラーは不変**: 次番負け確定時のボス「あがき」(6800) はそのまま最優先。
# 0 で旧バンド（ボスがクセロシキより上）へロールバック。
CHA_SUPPORT_ORDER = os.environ.get("CHA_SUPPORT_ORDER", "1") != "0"
# ── 第19弾（2026-07-27 ユーザー指示・EXP-064） ──
# バトル場のヒトモシ/ランプラーは技が炎エネコストで**実質不発**（22試合で提示0回）。
# 居座らせるとその番のミルが丸ごと止まるので、ベンチにエネ付きキュワワーがいるなら
# **積極的に**にげエネを張って交代し、フラワーシャワーを始める（にげは両者とも1）。
CHA_LINE_RETREAT = os.environ.get("CHA_LINE_RETREAT", "1") != "0"
# ── 第20弾（2026-07-27 ユーザー指示・EXP-065） ──
# バトル場にキュワワー以外 ∧ ベンチにキュワワー（エネ不問）→ 入れ替え（グッズ）を使う。
# 「バトル場にキュワワー以外がいる意味がない」。0 で旧挙動（エネ付きベンチ限定）。
CHA_SWITCH_COMFEY = os.environ.get("CHA_SWITCH_COMFEY", "1") != "0"
# ── 第21弾（2026-07-27 ユーザー指示・EXP-066） ──
# NZ のタイミングが甘い（次番2枚取られ負けなのに張らず負け＝リーサル判定が弱い）。
# 探索は挟まず単純化: **相手サイド残り2枚以下になったら張る**（従来の threats/wipe_risk も維持）。
CHA_NZ_PRIZE2 = os.environ.get("CHA_NZ_PRIZE2", "1") != "0"
# ── 第22弾（2026-07-27 ユーザー指示・EXP-067） ──
# 手番中サポートを打っていなければ、ボス以外のサポートを打つ（サポート枠を空けない）。
# Hilda(2350)/Dawn(2250) に遊軍帯を新設（既存: クセロシキ2450/ビワ2400/リーリエ2300黒字時）。
# ボスは拘束/あがき用に温存（対象外）。赤字リーリエ禁止(第16弾)と LO safety は維持。
CHA_IDLE_SUPPORT = os.environ.get("CHA_IDLE_SUPPORT", "1") != "0"
# ── 第23弾（2026-07-28 ユーザー指示・EXP-068）──
# ①リーリエの山回復が発火しすぎ（＝その番のクセロシキ/ビワを潰す）。相手が LO でない限り
#   「次の自分番を回せない」時だけに絞る（負けない範囲で緩和）。自山が無事な限り妨害を連打。
CHA_LILLIE_URGENT = os.environ.get("CHA_LILLIE_URGENT", "1") != "0"
# ②ヒトモシラインの進化はベンチ優先（前はいけにえ/交代要員 — 育てるのはベンチ）。
CHA_EVOLVE_BENCH = os.environ.get("CHA_EVOLVE_BENCH", "1") != "0"
# ③キュワワーの技が打てない番はリーリエを妨害札より優先（掘ってエンジンを直す）。
CHA_LILLIE_NOFS = os.environ.get("CHA_LILLIE_NOFS", "1") != "0"
# ── 第24弾（2026-07-29 ユーザー指示・EXP-069） ──
# ポフィンの div-C2 交戦期ホールド（2026-07-07 由来・場にキュワワー2体で無条件温存）を撤廃。
# ライン<2 か在庫ゼロなら交戦期でも打つ（ヒトモシは積極的に出す）。ただし取ってくる駒が
# 山札に存在しないと**判明**していたら空撃ちしない（第12弾カウンティング）。
CHA_POFFIN_TARGETED = os.environ.get("CHA_POFFIN_TARGETED", "1") != "0"
# ── 第25弾（2026-07-29 ユーザー指摘・EXP-070）: 山札記憶のローカル自己回復 ──
# 基盤 R-32 の会計は my_deck_list（= CWD の deck.csv、本番のみ存在）が無いと**丸ごと休止**する。
# ローカル（gauntlet/プローブ/観戦）では None のままで、サイド落ちを「山にあるかも」と数える
# 近似に落ちていた＝ポケパッド/ポフィンの空撃ちの原因（ユーザー指摘）。dusknoir の
# DUSK_DECK_CSV→DECK_FALLBACK と同じ自己回復を chandelure 側だけに実装（基盤・ドラパは不変）。
# リスト A/B 時は CHA_DECK_CSV で差し替える（会計が対象デッキと一致していないと嘘になる）。
CHA_DECK_CSV = os.environ.get("CHA_DECK_CSV", "")
CHA_DECK_RECOVER = os.environ.get("CHA_DECK_RECOVER", "1") != "0"   # 0=自己回復なし（旧挙動）
DECK_FALLBACK = (   # decks/fleet/chandelure_top.csv と同一60枚
    164, 164, 164, 164, 97, 97, 97, 494, 494, 98, 98, 98,
    343, 19, 19, 19, 19, 5, 5, 5, 5, 1086, 1086, 1086,
    1086, 1152, 1152, 1152, 1152, 1227, 1227, 1227, 1227, 1197, 1197, 1197,
    1225, 1225, 1225, 1264, 1182, 1182, 1182, 1119, 1119, 1120, 1120, 1120,
    1120, 1186, 1186, 1097, 1097, 1166, 1166, 1079, 1247, 1231, 1123, 1081,
)
# ── 第25弾b（2026-07-29 ユーザー指示・EXP-070）──
# キュワワーがベンチ+山に居ない ∧ 夜のタンカが手札に無い → リーリエ最優先で夜のタンカを
# 引きに行く（コンスタントに3枚引かせ続けるのが最重要）。
CHA_LILLIE_FOR_TANKA = os.environ.get("CHA_LILLIE_FOR_TANKA", "1") != "0"
# 第16弾b: 赤字リーリエの可否を「打った後も相手より山が多いか」で決める（山札レース不変条件）。
# 0 = 赤字は常に禁止（第16弾a の挙動）。CHA_LILLIE_LEDGER=0 なら丸ごと旧ロジック。
CHA_LILLIE_RACE = os.environ.get("CHA_LILLIE_RACE", "1") != "0"
# 第17弾（EXP-062）の「2つの時計」は **棄却**（ユーザー判断 2026-07-27）。コードも撤去済み。
# 山の消費速度は両者同じ（FS/特性はお互いに引かせる）ので「山の時計 < 相手の山の時計」は
# **「自山 < 相手山」と数学的に同値＝新情報ゼロ**。挙動を変えていたサイドの時計の外挿は粗く、
# 集計 64.9 → 64.1（リーリエ判定のみ）/ 63.4（掘り止めにも使用）と両用途で悪化した。
# 経緯と数字は デッキ設計_シャンデラ.md 第16〜17弾 / LEDGER EXP-060〜062 に保存。
# ── 第5弾（2026-07-25 ユーザー指示） ──
# 「サポート・道具を手札に抱えたまま end するターンをなくす」+「ベンチ狙撃相手にはシェイミ設置」。
# 判定は王者ゲート = A/B −1pt 超悪化で即 OFF。詳細 = デッキ設計_シャンデラ.md 第5弾。
CHA_USE_SUPPORTER = os.environ.get("CHA_USE_SUPPORTER", "1") != "0"  # 妨害系サポートは攻撃前に必ず使う（遊軍帯）
CHA_USE_TOOL = os.environ.get("CHA_USE_TOOL", "1") != "0"            # 手札の道具（重力宝石）は攻撃前に必ず着ける
CHA_SHAYMIN_VS_SNIPE = os.environ.get("CHA_SHAYMIN_VS_SNIPE", "1") != "0"  # ベンチ狙撃相手ならシェイミを壁に置く
# 第15弾（2026-07-27 ユーザー指摘・EXP-058）: 狙撃手判定をカードID + 単調ラッチに置換。
# 0 で旧判定（アーキタイプ名 + FROSLASS_IDS・ラッチ無し）へロールバック。
CHA_SNIPER_LATCH = os.environ.get("CHA_SNIPER_LATCH", "1") != "0"
# ── 第6弾（2026-07-25 ユーザー指示・ボスの指令バグ修正） ──
# 第5弾の「遊軍ボス（相手ベンチがいれば無条件吊り）」がバトル場のベロバーに対してベンチの
# ベロバーを呼ぶ無意味ドラッグを誘発（＋ヒカリを無視）。ボスは「相手バトル場が攻撃条件を
# 満たす ∧ ベンチに攻撃条件を満たさない駒（にげ≥1・≥2 望ましい）がいる」時だけ拘束に使い、
# 番を返すと負け確定の時だけ最優先で吊る（あがき）。
CHA_BOSS_SMART = os.environ.get("CHA_BOSS_SMART", "1") != "0"
# ── 第7弾（2026-07-25 ユーザー指示） ──
# ①ポケパッド温存しすぎ（R-30「グッズは積極使用」）＋②シャンデラ完成率が低い → 場にシャンデラが
# 出るまでポケパッドで積極的にライン部品を掘る。③キュワワーは場に3体で十分（4体目はベンチ献上）。
CHA_PAD_BUILD = os.environ.get("CHA_PAD_BUILD", "1") != "0"    # シャンデラ完成までポケパッドを掘る
CHA_COMFEY_CAP = os.environ.get("CHA_COMFEY_CAP", "1") != "0"  # キュワワーは場に3体まで
COMFEY_FIELD_CAP = 3
# ── 第8弾（2026-07-26 ユーザー指示 → 2026-07-27 除外・EXP-059） ──
# ①ベンチ狙撃相手ならシェイミを夜のタンカでも回収（ポケパッドは第5弾で対応済）。
# ②バトル場スタートのシェイミは、ベンチにFS即撃ちキュワワー（エネ≥1）がいれば
#   エネを張って逃げ→キュワワー前出し→フラワーシャワー（逃げエネ1枚の対価を肯定）。
# ③ポフィン・ポケパッドは温存せず確定使用（自山切れ防止の下限のみ残す）。
#
# **既定 OFF に変更（ユーザー判断 2026-07-27）**。理由 = 独立2回の測定がともに負で、
# 正の証拠が一度も無い: 採用時 −0.9pt / EXP-057 の専用試験台（marnie×2・n=5,120/腕）−0.7pt。
# 出荷時は「froslass 単セルの分散」と解釈して −0.9pt のまま採用したが、その解釈は否定された。
# ①②は同じ第8弾パッケージなので**同一トグルで束ねる**（①は従来トグル外だった＝env では
# 完全に戻せなかった。EXP-057 で zip 実物を走らせる必要があったのはこのため）。
CHA_RULES8 = os.environ.get("CHA_RULES8", "0") != "0"   # 第8弾パッケージ全体（既定OFF＝除外）
CHA_SHAYMIN_RETREAT = CHA_RULES8 and os.environ.get("CHA_SHAYMIN_RETREAT", "1") != "0"
# CHA_FORCE_ITEMS（確定使用）: A/B で自山切れにより −2〜3pt 悪化（王者ゲート抵触）→ 既定 OFF に暫定。
# ユーザーが勝率低下を承知で確定使用を望む場合は既定を "1" に戻す（コードは保持）。
CHA_FORCE_ITEMS = os.environ.get("CHA_FORCE_ITEMS", "0") != "0"          # ポフィン/ポケパッド確定使用
ITEM_DECK_FLOOR = 6   # これ未満の自山では確定使用を止める（ミルの生命線 = 自分の山切れ負けを防ぐ）
# ── 第9弾（2026-07-26 ユーザー指示）: バトル場に出す（＝いけにえ）優先順位を狙撃有無で切替 ──
# 非狙撃: キュワワー ＞ シェイミ ＞ シャンデラライン（シェイミを犠牲に線を守る）
# 狙撃  : キュワワー ＞ シャンデラライン ＞ シェイミ（壁のシェイミを温存し線を先に切る）
# ライン内は常にたね優先（ヒトモシ ＞ ランプラー ＞ シャンデラ = 既存序列で充足）
CHA_ACTIVE_PRIORITY = os.environ.get("CHA_ACTIVE_PRIORITY", "1") != "0"
# ── 第11弾（2026-07-26 ユーザー指示・ポケパッドバグ修正） ──
# ポケパッドは「即プレイできるカードしか持ってこない」。即プレイできる札が山に無ければ使わない。
# バグ = 即進化できないシャンデラをパッドで手札に持ってきて、リーリエで山に戻す無駄挙動。
CHA_PAD_PLAYABLE = os.environ.get("CHA_PAD_PLAYABLE", "1") != "0"
# ── 第12弾（2026-07-26 ユーザー指示・カウンティング） ──
# 「ポケパッドで山を見たらサイド落ちでした」を無くす。山を見るカード発動時に obs.select.deck が
# 全山を見せる（実測）ので、サイド落ち = デッキリスト − 見えた山 − 見えるゾーン（進化下敷き込み）で
# 確定。以後は山の中身を完全既知として、パッドは「確実に山にある即プレイ駒」がある時だけ使う。
# 履歴保持は Kaggle で禁止されておらず（永続ポリシーインスタンス）、コストも無視できる。
CHA_DECK_COUNT = os.environ.get("CHA_DECK_COUNT", "1") != "0"
# ── 第13弾（2026-07-26 ユーザー指示・サイド落ち活用） ──
# シャンデラが全部サイド落ち（カウンティングで確定）なら、ヒトモシラインは死に札 → 出さず、
# キュワワー単体ミル＋山札回復（リーリエ）に振る。手札の死にライン札はリーリエで山へ戻して寿命に。
CHA_CHAND_DEAD = os.environ.get("CHA_CHAND_DEAD", "1") != "0"
# ── 第14弾（2026-07-26 敗因分析→ユーザー着手指示）: LO デッキが LO（自滅）で負けない ──
# 敗因診断: marnie/alakazam の負けの ~46%/42% が「相手を残り数枚まで削りながら自分が先に山切れ」。
# 機構: 相手KOで再展開（Pad/Poffin等）を強いられ、探索が自山を非対称に薄める（自滅損7.0回 > 勝ち6.1）。
# 対策: 終盤（自山が薄い）で「ミルできるキュワワーが場にいる」なら非対称な掘りを止め、ミル＋回復で凌ぐ。
CHA_LO_SAFETY = os.environ.get("CHA_LO_SAFETY", "1") != "0"
LO_DANGER_DECK = 13       # 自山がこれ以下＝終盤の自山切れ危険域
OPP_ENDGAME_DECK = 10     # 相手山もこれ以下＝最終レース（もう1〜2ターンで決着・再建不要）
# ── 第10弾（2026-07-26 ユーザー指示）: サポートの時間帯優先 + クセロシキ被弾時の残し手札 ──
# バグ修正（常時ON）: 1T目空ベンチでヒカリをスルーしクセロシキ連打→負け → ライン全欠損時は
#   ヒカリを Xerosic より上の帯で打って盤面成熟を優先（下の DAWN ハンドラ 5700）。
# 【棄却→opt-in OFF】CHA_SUPPORTER_TIMING = クセロシキ/ビワを後半限定＋手札多少で使い分ける
#   doctrine。A/B で −1.4〜−3.9pt（早期妨害=特に対 marnie の価値を失う）→ 既定 OFF。
CHA_SUPPORTER_TIMING = os.environ.get("CHA_SUPPORTER_TIMING", "0") != "0"
XEROSIC_HAND = 6   # 相手手札がこれ以上=クセロシキ / 未満=ビワ（大体の基準。doctrine 有効時のみ）
XEROSIC_FLOOR = 3  # クセロシキは「相手手札を3枚まで捨てさせる」= これ以下では空振る（第18弾）
# CHA_DISCARD_KEEP = 手札を減らす時に「サポート1枚だけ残す」（ユーザー指示・再確認）。
#   初版（フル独自ランキング）は −2.1pt（エネ捨て副作用）→ 改版は「既定 discard ＋ 最良サポ
#   1枚だけ残す」の最小実装で再計測（下の A/B 参照）。
CHA_DISCARD_KEEP = os.environ.get("CHA_DISCARD_KEEP", "1") != "0"

CHANDELURE_LINE = {LITWICK, LAMPENT, CHANDELURE}
ENERGY_CARDS = {BASIC_P, TELEPATH}
# 第10弾: 手札を減らす時に残すサポートの優先度（高い順 = 手札回復→サーチ→妨害）。
# リーリエ = 山回復＆6ドローで手札を丸ごと立て直せるので最優先で残す。
SUPPORTER_KEEP = (LILLIE, HILDA, DAWN, mt.BOSS, XEROSIC, ERI)

# ── ベンチ狙撃（攻撃ダメージによるベンチ加害）デッキの識別（第5弾・ユーザー指示） ──
# シェイミ Flower Curtain は「相手ポケモンの攻撃によるベンチ非ルールボックスへのダメージ」を
# 無効化する。対象は攻撃ダメージ型の狙撃のみ:
#   starmie … メガスターミー JetBlow（120 + ベンチ50）= スターみぃ
#   marnie  … オーロンゲ Shadow Bullet（180 + ベンチ30）= べろばぁ（ベロバー線）
# ※ドラパルト Phantom Dive / マシマシラ Adrena-Brain は「ダメカン配置・移動」で攻撃ダメージ
#   ではないためシェイミでは止まらない（後者はバトルケージ担当）→ 意図的に除外。
BENCH_SNIPE_ARCHETYPES = {"starmie", "marnie"}
FROSLASS_IDS = {860, 861}   # 旧 tell（ユキワラシ/メガユキメノコ）。CHA_SNIPER_LATCH=0 の時だけ使う

# ── 第15弾（2026-07-27・ユーザー指摘 / EXP-058）: 狙撃手はデッキ名でなくカードで決まる ──
# 上のコメントどおり「ダメカンを乗せる/動かす」効果はシェイミで止まらない。そこで
# EN_Card_Data.csv をデッキプール全走査し、**技の効果として相手ベンチにダメージを与える**
# カードだけを列挙した。プール全体でこの3枚しか存在しない。
#   648  マリィのオーロンゲex   Shadow Bullet 180 + ベンチ1匹に30
#   1031 メガスターミーex       Jetting Blow  120 + ベンチ1匹に50
#   108  ウェルスプリング仮面オーガポンex  Torrential Pump（mega_kangaskhan_top 収録）
# 旧実装が 108 を取りこぼしていた。アーキタイプ名では代替できない（crustle_wall も
# メガガルーラex 756 を4枚積むため "kangaskhan" を狙撃扱いにすると誤検出する）。
BENCH_SNIPER_IDS = {648, 1031, 108}
# 進化前 = 狙撃手の予告。ユキメノコ型の検出は 860/861 でなく 1030（ヒトデマン）で取る
# ＝ スターミー非同居のユキメノコ型に誤発火しない。
BENCH_SNIPER_PRE_IDS = {646, 647, 1030}


class ChandelurePolicy(BasePolicy):
    DECK_NAME = "chandelure_mill"
    # R-31 不適用（2026-07-24 実測）: 均等80戦/枠×3標本で一貫 −2pt 超 = 王者ゲート抵触。
    # 前出し表（エネ付き Comfey 優先 = ミルの即時継続）が支配戦略の例外になるデッキ
    R31_OPT_OUT = True
    GO_FIRST = True            # R-21 確定（2026-07-07 実測: kidekikish IS_FIRST 9/9 YES）
    TAKE_MULLIGAN = True       # R-22【ハード・ユーザー決定 2026-07-07】マリガンは常にマックス引く
    ATTACKER_IDS = {COMFEY}
    ENERGY_IDS = ENERGY_CARDS
    LINE_PROTECT_IDS = CHANDELURE_LINE | {RARE_CANDY, NEUTRAL_ZONE}   # R-13（NZは回収不能）
    ATTACK_ENERGY_TYPE = 5     # 超（弱点計算用。実質 Play Rough のみ）

    def __init__(self):
        super().__init__()
        self.p = {}
        # 第12弾: 自山カウンティング（サイド落ち確定）の永続 state
        self._sniper_seen = False   # 第15弾: 狙撃手を一度見たらラッチ（False→True のみ）

    def reset_game(self):
        super().reset_game()
        self._sniper_seen = False

    # ═══════════════ ターン分析（軽量: 枚数と旗だけ） ═══════════════

    def choose(self, obs):
        # 第25弾: 基盤 R-32 会計の自己回復。ハーネスが my_deck_list を注入しない場合でも
        # CHA_DECK_CSV → deck.csv（基盤が試す）→ DECK_FALLBACK の順で自リストを確定させる。
        if CHA_DECK_RECOVER and not self.my_deck_list:
            deck = None
            if CHA_DECK_CSV:
                try:
                    with open(CHA_DECK_CSV) as f:
                        deck = [int(l) for l in f.read().split() if l.strip()][:60]
                except Exception:
                    deck = None
            if not deck:
                try:
                    deck = _read_deck_csv()   # 本番: 同梱 deck.csv
                except Exception:
                    deck = None
            self.my_deck_list = list(deck) if deck else list(DECK_FALLBACK)
        self.p = self._analyze(obs)
        return super().choose(obs)

    # ── 第12弾: 自山カウンティング → 基盤 R-32 に一本化（2026-07-27）──
    # 旧 `_collect_stack_into` / `_update_deck_knowledge` は削除。会計は policy_base の
    # `update_deck_knowledge`（choose 冒頭で毎手番実行）が担う。安全側の不変条件
    # （全山ビューのときだけサイド確定 / サイドを取られたら未確定に戻す）は基盤へ移設済み。

    def _in_deck_count(self, card_id):
        """今『山に』このカードが何枚あるか（基盤 R-32 の上限＝山+サイド寄りの値）。
        情報が全く無い（デッキリスト未取得）なら None を返し、呼び出し側は従来近似を使う。
        ※ 確定を主張する判定には `deck_min()` を、不可能を言う判定には `deck_max()` を使う。"""
        if not CHA_DECK_COUNT:
            return None
        return self.deck_max(card_id)

    def _chandelure_dead(self):
        """第13弾: シャンデラ3枚が全てサイド落ち = ラインが死んでいる。
        「二度と到達できない」という**不可能**の主張なので上限 `deck_max` で判定する
        （上限が0 = 山にもトラッシュにも場にも無い）。サイド確定前は主張しない。"""
        if not (CHA_CHAND_DEAD and CHA_DECK_COUNT) or not self.prizes_known():
            return False
        return (self.prized_count(CHANDELURE) or 0) >= 3

    # ── 第14弾: 自山切れ（自滅）回避 ──

    def _engine_intact(self, obs):
        """ミルできるキュワワー（{P}1枚以上）が場にいる = 掘り直さなくてもミルを続けられる。"""
        return any(pk.id == COMFEY and energy_count(pk) >= 1 for pk in all_my_pokemon(obs))

    def _lo_deck_thinning_forbidden(self, obs):
        """最終レース = 自山が薄い ∧ 相手山も薄い（あと1〜2ターンで決着）∧ ミルできるキュワワー健在。
        この局面では①これ以上掘ると自滅②相手も削り切る寸前で再建の必要も無い → 掘りを止めて
        ミル＋回復で自山を保たせ、相手を先に山切れさせる。エンジンが落ちていれば再建の掘りは許可。
        （初版は自山だけで判定→中盤の再建まで止めて resilience を失い −1.7pt。相手山条件で最終
        レースに限定して改善。）"""
        if not CHA_LO_SAFETY:
            return False
        # R-08 脅威（次番に取られると負ける駒がある = 相手が攻めてくる）時は resilience が要る
        # ので掘りを止めない。froslass 等の攻撃デッキで再建を止めて負ける事故（−7pt）を回避。
        if self.t["threats"]:
            return False
        # ※ 旧条件「相手山≤10」は相手がリーリエ等で自山を回復するデッキ（crustle_wall は
        # リーリエ×4）だと到達せず、最も温存が要る対面で発火しない。第17弾で「2つの時計」に
        # 置換したが**両用途で悪化して棄却**（EXP-062）。ここは未解決の課題として残る。
        return (self.p["my_deck"] <= LO_DANGER_DECK
                and self.p["opp_deck"] <= OPP_ENDGAME_DECK
                and self._engine_intact(obs))

    def _analyze(self, obs):
        ms = my_state(obs)
        os_ = opp_state(obs)
        fc = defaultdict(int)
        hc = defaultdict(int)
        dc = defaultdict(int)
        for pk in (ms.active + ms.bench):
            if pk is not None:
                fc[pk.id] += 1
        for c in (ms.hand or []):
            if c is not None:
                hc[c.id] += 1
        for c in (ms.discard or []):
            if c is not None:
                dc[c.id] += 1
        hand_size = len(ms.hand) if ms.hand else ms.handCount
        stadium_id = 0
        for c in obs.current.stadium:
            stadium_id = c.id
        opp_pokes = [p for p in (os_.active + os_.bench) if p]
        # 相手のエネ事情（ハンマーの発動判定）
        opp_energy_total = sum(energy_count(p) for p in opp_pokes)
        opp_special_energy = any(
            getattr(CARD_DB.get(ec.id), "cardType", None) == CardType.SPECIAL_ENERGY
            for p in opp_pokes for ec in (getattr(p, "energyCards", None) or []))
        # 自軍のエネ需要（エネ0のコンフィ）
        comfey_need = sum(1 for p in all_my_pokemon(obs)
                          if p.id == COMFEY and energy_count(p) == 0)
        return {
            "fc": fc, "hc": hc, "dc": dc,
            "hand_size": hand_size,
            "bench_free": ms.benchMax - len([b for b in ms.bench if b]),
            "bench_used": len([b for b in ms.bench if b]),
            # 第16弾: 「次にバトル場へ出せるキュワワー」の在庫（ポフィンの要否判定）
            "bench_comfey": sum(1 for b in ms.bench if b is not None and b.id == COMFEY),
            "stadium_id": stadium_id,
            "my_deck": ms.deckCount,
            "opp_deck": os_.deckCount,
            # 第16弾: 山札レースの収支に必要な量（詳細は _lillie_deck_delta）
            "my_prize": len(ms.prize) if ms.prize is not None else 6,
            # 第17弾: サイドの時計（相手のサイド残 = 殴り殺されるまでの余裕）
            "opp_prize": len(os_.prize) if os_.prize is not None else 6,
            "opp_hand": os_.handCount,
            "opp_has_ex": any(is_ex(p) for p in opp_pokes),
            "opp_has_munki": any(p.id == OPP_MUNKIDORI for p in opp_pokes),
            "opp_energy_total": opp_energy_total,
            "opp_special_energy": opp_special_energy,
            "comfey_need": comfey_need,
            "energy_in_hand": hc[BASIC_P] + hc[TELEPATH],
            "line_in_play": fc[LITWICK] + fc[LAMPENT] + fc[CHANDELURE],
        }

    # ═══ 第16弾（2026-07-27 ユーザー指摘・EXP-060）: 山札レースの収支を厳密に勘定する ═══

    def _lillie_deck_delta(self, p):
        """リーリエの決心を打った時、**自分の山が何枚増減するか**を返す。

        カードテキスト = 「手札を山に戻す → 6ドロー。**サイドがちょうど6枚残っているなら
        代わりに8ドロー**」。手札 H（リーリエ自身を含む）で打つと:
            リーリエは場を離れる → 手札 H−1 が山へ → 山 +（H−1） → N ドロー → 山 −N
            **山の増減 = H − 1 − N**（N = サイド残6なら 8、それ以外なら 6）

        **本デッキは攻撃しない＝サイドは常に6枚残る＝常に8ドロー**。したがって
        損益分岐は手札9枚、純増は10枚以上。旧実装は「手札≥7で山が純増」（＝6ドロー前提）を
        3か所で仮定しており、実測では手札3〜6での使用が6試合で13回・**−56枚**の自滅要因だった
        （リーリエ全23回の正味は −44枚 ≒ 1試合あたり −7.3枚。負け時の相手残り山は中央値12〜14枚
        なので、これだけで敗因の大半を説明する）。

        なぜ「相手も同じだけ引く」ミルデッキでこれが致命的か（ユーザー指摘）:
        フラワーシャワー（お互い3ドロー）もシャンデラの特性（お互い1ドロー）も**対称**なので、
        **エンジンをいくら回しても山札の枚数差は動かない**。差を動かすのは非対称な行動
        ＝こちらのサーチ（自分だけ減る）とリーリエ（自分だけ増える）だけ。よって
        **差がマイナスに転じた瞬間、相手が自発的に掘らない限り確定で負ける**。
        """
        draw = 8 if p.get("my_prize", 6) == 6 else 6
        return p["hand_size"] - 1 - draw

    def _engine_broken(self, obs):
        """エンジン（フラワーシャワーを撃てるキュワワー）が場に無く、手札にも作る材料が
        無い＝手札を作り直すしかない局面。**赤字リーリエを許す唯一の例外**（打たなければ
        何もできずに負けるので、山を減らしてでも引き直す価値がある）。"""
        if any(pk.id == COMFEY and energy_count(pk) >= 1 for pk in all_my_pokemon(obs)):
            return False            # 今すぐ FS が撃てる = 引き直す必要がない
        hc = self.p["hc"]
        if hc[COMFEY] >= 1 or self.p["energy_in_hand"] >= 1:
            return False            # 手札の材料で自力で立て直せる
        return True

    # ═══════════════ 判定（S-0） ═══════════════

    def judge_subgoal(self, obs):
        """S-0: 場のコンフィが Flower Shower を払える({P}1枚以上) かつ シャンデラが1体以上。
        第13弾: シャンデラ全落ちなら、コンフィ即撃ちだけで交戦扱い（キュワワー単体ミル＝自山温存モード）。"""
        comfey_ready = any(p.id == COMFEY and energy_count(p) >= 1
                           for p in all_my_pokemon(obs))
        if comfey_ready and self._chandelure_dead():
            return True
        return comfey_ready and has_in_play(obs, CHANDELURE)

    def _opp_bench_snipes(self, obs):
        """第5弾（ユーザー指示）: 相手が攻撃ダメージでベンチを狙撃するデッキか。
        フラグが立ったらシェイミ（壁）を能動的に探して置く。

        第15弾（2026-07-27・EXP-058）で3点を修正:
          ①**カードID判定**（BENCH_SNIPER_IDS）に置換。旧実装はオーガポンex(108)を
            取りこぼしていた。
          ②**単調ラッチ**。self.t["matchup"] は基盤 R-20 が毎手番『相手の場』だけから
            再計算するため、オーロンゲが場から消えると generic に戻る＝認識が揺れ、
            その瞬間に第9弾がシェイミを狙撃手の前へ差し出す。False→True のみに固定する
            （dusknoir の _grim_seen と同じ手当て。基盤 t["matchup"] には触らない）。
          ③tell をトラッシュにも広げる（一度出て落ちた狙撃手も「このデッキは狙撃型」の証拠）。
        """
        if not CHA_SHAYMIN_VS_SNIPE:
            return False
        if not CHA_SNIPER_LATCH:                      # 旧判定（ロールバック用）
            if self.t["matchup"] in BENCH_SNIPE_ARCHETYPES:
                return True
            opp = opp_state(obs)
            return any(p.id in FROSLASS_IDS for p in (opp.active + opp.bench) if p)
        if self._sniper_seen:
            return True
        if self.t["matchup"] in BENCH_SNIPE_ARCHETYPES:
            self._sniper_seen = True
            return True
        opp = opp_state(obs)
        tells = BENCH_SNIPER_IDS | BENCH_SNIPER_PRE_IDS
        for pk in (opp.active + opp.bench):
            if pk is not None and self._stack_has(pk, tells):
                self._sniper_seen = True
                return True
        for c in (opp.discard or []):
            if c is not None and getattr(c, "id", None) in tells:
                self._sniper_seen = True
                return True
        return False

    def _stack_has(self, node, ids):
        """進化スタック（preEvolution 再帰）に ids のカードが含まれるか。
        進化後だけを見ると「ヒトデマン→メガスターミー」で下敷きの tell を見落とす。"""
        if node is None:
            return False
        if getattr(node, "id", None) in ids:
            return True
        return any(self._stack_has(c, ids)
                   for c in (getattr(node, "preEvolution", None) or []))

    # ── 第6弾: ボスの指令の「意味のある拘束」判定 ──

    def _can_attack_now(self, pokemon):
        """攻撃条件を満たす = エネが1枚以上載っていて払える技が1つ以上ある。
        0エネの置物たね（ベロバー等）を「アタッカー」と誤認しないための下限（energy≥1）。"""
        return (pokemon is not None and energy_count(pokemon) >= 1
                and len(payable_attacks(pokemon)) >= 1)

    def _boss_trap_targets(self, obs):
        """ボスで吊るのが有意義な相手ベンチ = 攻撃条件を満たさない（今は殴れない）かつ
        にげるコスト≥1（≥2 が望ましい）。攻撃できる駒を吊るのは相手が得するだけなので除外。"""
        return [b for b in opp_state(obs).bench
                if b is not None and not self._can_attack_now(b)
                and retreat_cost(b) >= 1]

    # ── 第10弾: 手札を減らす時（クセロシキ等）に残す札を選ぶ ──

    def _best_supporter_in_hand(self):
        """手札にある最良サポート1枚（SUPPORTER_KEEP の優先順）。無ければ None。"""
        hc = self.p["hc"]
        for s in SUPPORTER_KEEP:
            if hc.get(s, 0) > 0:
                return s
        return None

    def _score_discard(self, obs, opt):
        """クセロシキ等で手札を減らす時「サポートを1枚だけ残す」（第10弾ユーザー指示・改）。
        既定の discard（ライン保護＋余剰カット＝A/B で最良と判明）をそのまま使い、最良サポート
        1枚だけを追加で残す。余剰サポート（最良以外）は既定どおり捨てる。"""
        base_score, base_reason = self.default_score_discard(obs, opt)
        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, "cardId", None)
        if cid is None:
            return base_score, base_reason
        # 最良サポート1枚だけ残す（ライン -5000 の下、余剰/generic より上 = 確実に生き残る）
        if cid == self._best_supporter_in_hand():
            return -3000, "第10弾: keep 1 supporter (act next turn)"
        return base_score, base_reason

    # ── 第7弾: シャンデラライン完成のためのポケパッド積極堀り ──

    def _need_line_dig(self):
        """場にシャンデラがいない間、ポケパッドで掘って揃えたいライン部品があるか。
        端（土台ヒトモシ/ランプラー・上のシャンデラのカード）や橋（ランプラー/ふしぎなアメ）が
        欠けていれば掘る = シャンデラ完成まで手を止めない（R-30 積極グッズ＋完成率改善）。"""
        fc, hc = self.p["fc"], self.p["hc"]
        if fc[CHANDELURE] >= 1:
            return False                                   # エンジン完成 = これ以上ラインは掘らない
        base = fc[LITWICK] + hc[LITWICK] + fc[LAMPENT] + hc[LAMPENT]   # 土台
        top = hc[CHANDELURE] + fc[CHANDELURE]                          # シャンデラのカード
        bridge = fc[LAMPENT] + hc[LAMPENT] + hc[RARE_CANDY]            # 進化の橋渡し
        return base == 0 or top == 0 or bridge == 0

    # ── 第11弾: ポケパッドは「即プレイできる駒」だけ持ってくる ──

    def _pad_immediately_playable(self, cid):
        """ポケパッドで手札に加えて「その番に即プレイ/進化できる」カードか。
        たね = ベンチ空きで即ベンチ／ランプラー = 場のヒトモシに即進化／
        シャンデラ = 場のランプラーに即進化 or アメ手札∧場ヒトモシで即直行。"""
        p = self.p
        fc, hc = p["fc"], p["hc"]
        if cid in (LITWICK, COMFEY, SHAYMIN):
            if p["bench_free"] <= 0:
                return False
            if cid == COMFEY and fc[COMFEY] >= COMFEY_FIELD_CAP:
                return False
            return True
        if cid == LAMPENT:
            return fc[LITWICK] >= 1
        if cid == CHANDELURE:
            return fc[LAMPENT] >= 1 or (hc[RARE_CANDY] >= 1 and fc[LITWICK] >= 1)
        return False

    def _maybe_in_deck(self, card_id, total):
        """山にまだあり得るか。第12弾: サイド落ちが確定していれば「確実に山にある」枚数で
        判定。未確定/情報なしなら山+サイド近似（total − 見えるゾーン > 0）＝
        「存在しないと判明」した時だけ False を返す保守的判定。"""
        known = self._in_deck_count(card_id)
        if known is not None:
            return known > 0
        p = self.p
        return (total - p["fc"][card_id] - p["hc"][card_id] - p["dc"][card_id]) > 0

    def _pad_wanted_playable(self, obs):
        """ポケパッドで取ってきて『即使える ∧ まだ欲しい ∧ 山にありそう』な駒があるか。
        無ければパッドを使わない（ユーザー指示）。山の有無は hand/play/discard 以外に
        残っているか（= 山orサイド）で近似する。"""
        p = self.p
        fc, hc, dc = p["fc"], p["hc"], p["dc"]

        def maybe_in_deck(card_id, total):
            return self._maybe_in_deck(card_id, total)

        dead = self._chandelure_dead()   # 第13弾: シャンデラ全落ちならライン部品は掘らない
        if p["bench_free"] >= 1:
            if (not dead) and p["line_in_play"] < 3 and maybe_in_deck(LITWICK, 3):
                return True                                   # 土台ヒトモシを即ベンチ
            if (fc[COMFEY] + hc[COMFEY] < COMFEY_FIELD_CAP
                    and fc[COMFEY] < COMFEY_FIELD_CAP and maybe_in_deck(COMFEY, 4)):
                return True                                   # ミルのキュワワーを即ベンチ
            if (self._opp_bench_snipes(obs) and fc[SHAYMIN] == 0 and hc[SHAYMIN] == 0
                    and maybe_in_deck(SHAYMIN, 1)):
                return True                                   # 狙撃相手の壁シェイミ
        if (not dead and fc[CHANDELURE] == 0 and hc[CHANDELURE] == 0
                and self._pad_immediately_playable(CHANDELURE) and maybe_in_deck(CHANDELURE, 3)):
            return True                                       # 即進化できるシャンデラ
        if (not dead and fc[LAMPENT] == 0 and hc[LAMPENT] == 0
                and self._pad_immediately_playable(LAMPENT) and maybe_in_deck(LAMPENT, 2)):
            return True                                       # 場ヒトモシへ即進化のランプラー
        return False

    # ── 第8弾: 場スタートのシェイミを逃がしてキュワワーのFSを始める ──

    def _shaymin_retreat_ready(self, obs):
        """バトル場がシェイミ ∧ ベンチにフラワーシャワー即撃ち可能なキュワワー（エネ≥1）がいる。
        = シェイミにエネを張って逃げ、キュワワーを前に出してミルを始めるべき局面
        （逃げエネ1枚の対価を払ってでもFSを始める。ユーザー肯定）。"""
        if not CHA_SHAYMIN_RETREAT:
            return False
        active = active_pokemon(obs)
        if active is None or active.id != SHAYMIN:
            return False
        return any(pk.id == COMFEY and energy_count(pk) >= 1
                   for pk in my_state(obs).bench if pk)

    # ── 第19弾（2026-07-27 ユーザー指示）: 前のヒトモシ/ランプラーを退かしてFSを始める ──

    def _line_retreat_ready(self, obs):
        """バトル場がヒトモシ/ランプラー ∧ ベンチにFS即撃ち可能なキュワワー（エネ≥1）がいる。

        ヒトモシ(Live Coal)もランプラー(Fire Blast)も**炎エネコストなので本デッキでは実質不発**
        （22試合で提示0回を実測）。バトル場に居座らせると**その番のミルが丸ごと止まる**ので、
        にげエネ1枚（両者ともにげ1）を払ってでもエネ付きキュワワーを前に出す。
        第8弾のシェイミ逃げと同型だが、あちらは壁として価値のあるシェイミを退かす話（−0.7pt で
        除外済み）。**こちらは前に居ても何もできない駒を退かす**ので機構が違う。"""
        if not CHA_LINE_RETREAT:
            return False
        active = active_pokemon(obs)
        if active is None or active.id not in (LITWICK, LAMPENT):
            return False
        return any(pk.id == COMFEY and energy_count(pk) >= 1
                   for pk in my_state(obs).bench if pk)

    # ═══════════════ セットアップコンテキスト（S-1/S-2） ═══════════════

    def score_setup_context(self, obs, opt):
        ctx = obs.select.context
        if ctx == SelectContext.SETUP_ACTIVE_POKEMON:
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {COMFEY: 10, LITWICK: 5, SHAYMIN: 3}   # S-1 実測: 14/5/3
            return table.get(cid, 0), "S-1: setup active"
        if ctx == SelectContext.SETUP_BENCH_POKEMON:
            # S-2: セットアップでもベンチ展開する（実測あり。ドンク回避も兼ねる）
            card = option_card(obs, opt)
            cid = card.id if card else None
            table = {LITWICK: 100, SHAYMIN: 80, COMFEY: 60}
            return table.get(cid, 10), "S-2: setup bench"
        return super().score_setup_context(obs, opt)   # R-21/R-22 はクラス属性

    def score_number(self, obs, opt):
        # E-8/div-C4: DRAW_COUNT は 1 を選ぶ（自山温存。実測: 1,1,1,2 — 0 ではなく 1）
        if obs.select.context == SelectContext.DRAW_COUNT:
            return -abs((opt.number or 0) - 1), "E-8: draw one (preserve deck)"
        return super().score_number(obs, opt)

    # ═══════════════ 優先則（純粋3フック） ═══════════════

    def score_setup(self, obs, opt):
        return self._score_any(obs, opt, combat=False)

    def score_combat(self, obs, opt):
        return self._score_any(obs, opt, combat=True)

    def _score_any(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex

        # ── ABILITY 帯（R-04 最上位） ──
        if opt.type == OptionType.ABILITY:
            card = get_card(obs, opt.area, opt.index, yi)
            cid = card.id if card else None
            if cid == CHANDELURE:
                # E-1: Alluring Light は毎ターン。E-1a: 自山2枚以上でのみ（実測: 山2使用/山1スキップ）
                # div-C8【棄却 2026-07-11】: 帯 29000→1500（攻撃直前）を試行 — human=Boss/EVOLVE/
                # Lillie→ours=ABILITY が両日17件（逆0件）だったが、実測は 07-08 68.4→63.0% /
                # 07-09 59.4→58.5% と大幅悪化。人間の特性使用位置はターン中盤に分散しており
                # 「最後」固定は「最初」固定より遠い。29000 に差し戻し
                if p["my_deck"] >= 2:
                    return 29000, "E-1: Alluring Light (mill 1)"
                return -1, "E-1a: deck too thin for Alluring Light"
            # div-C4（2026-07-07 divergence 実測）: 相手スタジアム等の汎用特性は
            # 自分の行動（ハンマー・手張り・サポート）を全て済ませた後に回す
            return 2000, "generic ability (late)"

        if opt.type == OptionType.PLAY:
            return self._score_play(obs, opt, combat)

        if opt.type == OptionType.ATTACH:
            return self._score_attach(obs, opt)

        if opt.type == OptionType.EVOLVE:
            card = option_card(obs, opt)
            cid = card.id if card else None
            # 第23弾②（ユーザー指示）: 進化先はベンチ優先。前の駒はいけにえ/交代要員で、
            # 育てる価値があるのはベンチ側（第20弾で前は常にキュワワーに寄せる方針とも整合）。
            # −200 はバンド内の選好差のみ（Chandelure 24800 > Lampent 24000 の序列は不変）。
            bench_pref = 0
            if CHA_EVOLVE_BENCH:
                tgt = option_target(obs, opt)
                act = active_pokemon(obs)
                if tgt is not None and act is not None and tgt is act:
                    bench_pref = -200
            if cid == CHANDELURE:
                return 25000 + bench_pref, "S-3: evolve Chandelure (Alluring Light body)"
            if cid == LAMPENT:
                return 24000 + bench_pref, "S-3: evolve Lampent"
            return 7000, "generic evolve"

        if opt.type == OptionType.RETREAT:
            # 第8弾: 場スタートのシェイミは、FS即撃ちキュワワーがベンチにいてシェイミが
            # 逃げエネを払えるなら逃がす（キュワワー前出し→フラワーシャワー）。
            if self._shaymin_retreat_ready(obs):
                active = active_pokemon(obs)
                if active is not None and energy_count(active) >= retreat_cost(active):
                    return 9000, "第8弾: retreat Shaymin (promote Comfey for FS)"
            # 第19弾（ユーザー指示）: 前のヒトモシ/ランプラーは何もできないので、
            # にげエネを払えるならエネ付きキュワワーに交代してFSを始める。
            if self._line_retreat_ready(obs):
                active = active_pokemon(obs)
                if active is not None and energy_count(active) >= retreat_cost(active):
                    return 9000, "第19弾: retreat Litwick/Lampent (promote fueled Comfey)"
            return -5000, "E-7: never retreat (use Switch item)"

        if opt.type == OptionType.ATTACK:
            aid = getattr(opt, "attackId", None)
            if aid == ATK_FLOWER_SHOWER:
                # E-1a【ハード・ミル版R-11】: 自山≤3 でのセルフデッキアウト禁止
                #（相手山≤3なら相手のターン開始ドローが先に尽きるので解除）
                if p["my_deck"] <= 3 and p["opp_deck"] > 3:
                    return -1, "E-1a: Flower Shower would deck us out"
                # 【2026-07-22 決定性監査】負け試合の最大無意見クラスタ（OFF監査117件）が
                # 「FS 1200 vs Play Rough 1020+dmg = margin 180」。選択自体は実測どおり
                # FS（106:1）で正しく、margin だけが薄い。
                # CHA_MARGIN【採用】: FS 1200→1950 / chip 1000+dmg→850+dmg。序列は全対全で
                # 厳密不変（FS > chip > 宝石700 > END のまま。(870,1200] 帯に他スコア無し —
                # generic play 1000 はこのデッキの60枚全てが明示ハンドラ持ちで不到達）。
                # margin 180→1080 = decisive。generic ability 2000 の下は維持。
                # CHA_FUEL_TARGET【棄却・opt-in】: FS 1750 / chip 150+dmg（chip vs 宝石の
                # 弱序列320を反転 = FS封印末期に宝石を張ってから殴る、まで踏み込む版）。
                if CHA_FUEL_TARGET:
                    return 1750, "E-1: Flower Shower (mill 3)"
                return (1950 if CHA_MARGIN else 1200), "E-1: Flower Shower (mill 3)"
            active = active_pokemon(obs)
            dmg = self.attack_damage(obs, active, aid) if active else 0
            if CHA_FUEL_TARGET:
                return 150 + dmg, "attack (chip damage)"
            return ((850 if CHA_MARGIN else 1000) + dmg), "attack (chip damage)"

        if opt.type == OptionType.END:
            return 0, "end"

        if opt.type in (OptionType.CARD, OptionType.ENERGY):
            return self._score_card(obs, opt, combat)

        return 100, "fallback"

    # ── PLAY ──

    def _score_play(self, obs, opt, combat):
        p = self.p
        card = option_card(obs, opt)
        if card is None:
            return 0, "play none"
        cid = card.id
        data = CARD_DB.get(cid)
        fc, hc, dc = p["fc"], p["hc"], p["dc"]

        if data is not None and data.cardType == CardType.POKEMON:
            score, reason = 20000, "play pokemon"
            if cid == LITWICK:
                if self._chandelure_dead():
                    # 第13弾: シャンデラ全落ち = ヒトモシ線は死に札。出さずベンチをコンフィに空ける
                    return -1, "第13弾: Chandelure dead — don't deploy Litwick line"
                score += 500 if p["line_in_play"] < 3 else 100
            elif cid == COMFEY:
                # 第7弾（ユーザー指示）: 場のキュワワーは3体で十分。4体目はベンチ=サイド献上 +
                # シャンデラ線のベンチ枠を潰すので出さない
                if CHA_COMFEY_CAP and fc[COMFEY] >= COMFEY_FIELD_CAP:
                    score, reason = -1, "第7弾: 3 Comfey is enough (no 4th)"
                # div-C2: 2体目以降のコンフィ素出しは急がない（ベンチ=サイド献上。妨害が先）
                elif fc[COMFEY] >= 1:
                    score, reason = 13800, "play spare Comfey (after items)"
                else:
                    score += 400
            elif cid == SHAYMIN:
                if (CHA_SHAYMIN_VS_SNIPE and fc[SHAYMIN] == 0
                        and self._opp_bench_snipes(obs)):
                    score += 900   # 第5弾: ベンチ狙撃相手は壁を優先設置（ヒトモシ線より上）
                else:
                    score += 300 if fc[SHAYMIN] == 0 else -300
            # R-03: ベンチ0は即死筋 → 最優先で解消 / R-24: 1枠空け
            if p["bench_used"] == 0:
                score += 5000
            elif p["bench_free"] <= 1:
                score -= 5000
            return score, reason

        # ── スタジアム（E-4: NZ が先、ケージは NZ 消滅後） ──
        if cid == NEUTRAL_ZONE:
            if p["stadium_id"] == NEUTRAL_ZONE:
                return -1, "NZ already up"
            # CHA_NC_HOLD v2（2026-07-24 ユーザー指示・同日改訂）: NZ は ACE SPEC ×1 で
            # 回収不能 — 早張りは貼り替えで剥がされ損なので、**次の相手番の敗北リーチが
            # 見えた時だけ**リーサルブロッカーとして張る。リーチは2系統:
            #   (a) R-08 threats = 取られるとサイド取り切りで負ける駒が存在
            #   (b) 盤面全滅リーチ = ベンチ0 ∧ バトル場が相手投影打点で落ちる
            #       （初版「相手サイド1-2枚」条件はこの序盤全滅パターンを守れなかった）
            if CHA_NC_HOLD:
                active = active_pokemon(obs)
                wipe_risk = (p["bench_used"] == 0 and active is not None
                             and self.opp_max_damage(obs) >= active.hp)
                # 第21弾（2026-07-27 ユーザー指示・EXP-066）: 従来の「リーサル可視」判定
                # （threats / wipe_risk）は甘く、次番に2枚取られて負ける局面で張らずに
                # 負けていた。探索は挟まず単純に: **相手サイド残り2枚以下になったら張る**。
                prize_rush = CHA_NZ_PRIZE2 and p["opp_prize"] <= 2
                if not prize_rush and not self.t["threats"] and not wipe_risk:
                    return -1, "CHA: hold NZ until lethal visible"
            if p["opp_has_ex"]:
                return 19500, "E-4: Neutralization Zone (block ex damage)"
            return -1, "E-4: hold NZ (no rule-box threat yet)"
        if cid == BATTLE_CAGE:
            if p["stadium_id"] == NEUTRAL_ZONE:
                return -1, "E-4: never overwrite own NZ"
            if p["stadium_id"] == BATTLE_CAGE:
                return -1, "cage already up"
            if p["opp_has_munki"]:
                return 19000, "E-4: Battle Cage (block Adrena-Brain)"
            if p["stadium_id"] != 0:
                return 15000, "E-4: Battle Cage (stadium war)"
            return -1, "hold Battle Cage"

        # ── グッズ ──
        if cid == RARE_CANDY:
            if fc[LITWICK] >= 1 and hc[CHANDELURE] >= 1:
                return 19000, "S-3: Rare Candy -> Chandelure"
            return -1, "Rare Candy: no line"
        if cid == POFFIN:
            # 第8弾（ユーザー指示・確定使用）: 温存（div-C2 の交戦期ホールド）を撤廃し、
            # 「ベンチ枠がある ∧ 自山切れしない ∧ まだ増やせる駒がある」限り必ず打つ。
            # 打たない理由は3つに限定 = ①ベンチ満杯（物理的に置けない）②自山下限
            # （ミルの生命線）③盤面飽和（キュワワー3体上限 ∧ ライン3体 = 増やす先が無い=空撃ち）
            if p["bench_free"] <= 0:
                return -1, "Poffin: bench full"
            # 第14弾: 終盤の自山切れ危険域 ∧ ミルエンジン健在なら掘らない（自滅回避）
            if self._lo_deck_thinning_forbidden(obs):
                return -1, "第14弾: LO safety — don't thin (mill+recover)"
            # 第13弾: シャンデラ全落ちならヒトモシは足さない（コンフィ補充だけ）
            can_add = (fc[COMFEY] < COMFEY_FIELD_CAP) or (
                p["line_in_play"] < 3 and not self._chandelure_dead())
            if not can_add:
                return -1, "Poffin: board saturated (nothing to add)"
            # 第16弾（2026-07-27 ユーザー指示・EXP-061）: 毎ターンキュワワーをバトル場へ
            # 出せる態勢が整っているなら、ポフィンは打つ必要がない（自山を2枚削るだけ）。
            # 使うのは「ベンチに次のキュワワーが用意できていない」or「ヒトモシラインが2体未満」
            # の時だけ。※グッズは使いたくて入れているカードなので、**両方満たした時だけ止める**
            # （ユーザー注意: on/off は慎重に）。
            if (CHA_POFFIN_STRICT and p["bench_comfey"] >= 1
                    and p["line_in_play"] >= 2):
                return -1, "第16弾: Poffin 不要（次のキュワワー在庫あり ∧ ライン2体）"
            if CHA_FORCE_ITEMS:
                if p["my_deck"] < ITEM_DECK_FLOOR:
                    return -1, "Poffin: deck floor (mill life-line)"
                need = (fc[COMFEY] < 2) or (p["line_in_play"] < 2)
                return (18000 if need else 12000), "第8弾: Poffin (確定使用)"
            # 第24弾（2026-07-29 ユーザー指示・EXP-069）: div-C2 の交戦期ホールドを撤廃。
            # 温存条件は第16弾（上の STRICT）に一本化し、**ヒトモシは積極的に出す**。
            # ただし「取ってくる駒が山札に存在しないと判明」していたら空撃ちしない
            # （第12弾カウンティングで確定した時だけ False になる保守的判定）。
            if CHA_POFFIN_TARGETED:
                want_litwick = (p["line_in_play"] < 2
                                and not self._chandelure_dead()
                                and self._maybe_in_deck(LITWICK, 3))
                want_comfey = (p["bench_comfey"] == 0
                               and fc[COMFEY] < COMFEY_FIELD_CAP
                               and self._maybe_in_deck(COMFEY, 4))
                if want_litwick or want_comfey:
                    return 18000, "第24弾: Poffin (restock Litwick/Comfey)"
                return -1, "第24弾: Poffin 空撃ち回避（山に対象なし）"
            # 旧ロジック（CHA_POFFIN_TARGETED=0 フォールバック）
            if combat:
                return (8000 if fc[COMFEY] < 2 else -1), "div-C2: Poffin only to rebuild"
            need = (fc[COMFEY] < 2) or (p["line_in_play"] < 2)
            return (18000 if need else 8000), "S-2: Poffin"
        if cid == POKE_PAD:
            # 第14弾: 終盤の自山切れ危険域 ∧ ミルエンジン健在なら掘らない（自滅回避）
            if self._lo_deck_thinning_forbidden(obs):
                return -1, "第14弾: LO safety — don't thin (mill+recover)"
            # S-4: シャンデラ堀り（TO_HAND 実測33回の主役）
            # 第8弾（ユーザー指示・確定使用）: 温存（交戦期 div-C2 ホールド）を撤廃。有用な
            # 取得先（ライン部品/エンジン駒/2枚目シャンデラ/狙撃対策シェイミ）がある限り必ず掘る。
            # 打たないのは「自山下限」か「取得先が全く無い」時だけ。
            snipe_need = (fc[SHAYMIN] == 0 and hc[SHAYMIN] == 0
                          and self._opp_bench_snipes(obs))
            if CHA_PAD_PLAYABLE:
                # 第11弾（ユーザー指示・バグ修正）: 即プレイできる取得先が山にありそうな時だけ使う。
                # 即進化できないシャンデラを持ってきてリーリエで山に戻す無駄挙動を根絶する。
                if p["my_deck"] < 5:
                    return -1, "Pad: deck too thin (mill life-line)"
                if combat:
                    # エンジン完成後は自山温存。即ベンチできる壁シェイミ（狙撃相手）だけ許可
                    if snipe_need and p["bench_free"] >= 1 and p["my_deck"] >= 8:
                        return 8000, "第11弾: Pad for Shaymin (vs snipe, combat)"
                    return -1, "div-C2: preserve deck (combat)"
                if not self._pad_wanted_playable(obs):
                    return -1, "第11弾: Pad (no immediately-playable target in deck)"
                return 17000, "第11弾: Poke Pad (fetch immediately-playable)"
            line_dig = CHA_PAD_BUILD and self._need_line_dig()
            if CHA_FORCE_ITEMS:
                if p["my_deck"] < ITEM_DECK_FLOOR:
                    return -1, "Poke Pad: deck floor (mill life-line)"
                want_2nd_chand = (fc[CHANDELURE] < 2 and hc[CHANDELURE] == 0)
                want_comfey = (fc[COMFEY] + hc[COMFEY] < COMFEY_FIELD_CAP)
                if line_dig or snipe_need or want_2nd_chand or want_comfey:
                    return 17000, "第8弾: Poke Pad (確定使用)"
                return -1, "Poke Pad: nothing useful to fetch"
            # 旧ロジック（CHA_FORCE_ITEMS=0 フォールバック）
            if combat:
                if fc[CHANDELURE] < 2 and hc[CHANDELURE] == 0 and p["my_deck"] >= 10:
                    return 8000, "div-C2: Pad for 2nd Chandelure"
                if snipe_need and p["my_deck"] >= 8:
                    return 7800, "第5弾: Pad for Shaymin (vs snipe)"
                return -1, "div-C2: preserve deck"
            if line_dig and p["my_deck"] >= 5:
                return 17000, "第7弾: Poke Pad (build Chandelure line)"
            need = ((fc[COMFEY] + hc[COMFEY] == 0) or snipe_need)
            if need and p["my_deck"] >= 5:
                return 17000, "S-4: Poke Pad (missing piece)"
            return -1, "S-4: hold Pad (line ready)"
        if cid == CRUSHING_HAMMER:
            # E-6: エネが見える限り毎ターン投げる（実測50回 = 最多プレイ）
            if p["opp_energy_total"] >= 1:
                return 14000, "E-6: Crushing Hammer"
            return -1, "Crushing Hammer: no target"
        if cid == ENHANCED_HAMMER:
            # div-C4: クラッシュハンマーが先（実測: 両方持ちはクラッシュから）
            if p["opp_special_energy"]:
                return 13500, "E-6: Enhanced Hammer (special energy)"
            return -1, "Enhanced Hammer: no special energy"
        if cid == NIGHT_STRETCHER:
            # 第8弾（ユーザー指示）: ベンチ狙撃相手で壁のシェイミが焼かれた（トラッシュ）なら、
            # 夜のタンカで回収して置き直す（ポケパッドと並ぶ回収ルートに割り当て）。
            # 2026-07-27（EXP-059）: 第8弾は除外 → CHA_RULES8 既定OFF でこの枝も止まる。
            if (CHA_RULES8 and self._opp_bench_snipes(obs) and fc[SHAYMIN] == 0
                    and hc[SHAYMIN] == 0 and dc[SHAYMIN] >= 1):
                return 12500, "第8弾: Night Stretcher (recover Shaymin vs snipe)"
            if (dc[BASIC_P] >= 1 and p["energy_in_hand"] == 0 and p["comfey_need"] >= 1):
                return 13000, "Night Stretcher: recover energy"
            # div-C11（2026-07-11 実測・調整日07-08/09）: ポケモン回収は「エンジン駒が実際に
            # 足りない時」だけ。トラッシュに駒があるだけで拾うのは山掘り（手数）の無駄で、
            # 上位勢はボス/パッド/攻撃を優先（human=Pad,Boss,Flower / ours=Stretcher が
            # 07-09 ×5 + 07-08 ×1、逆方向1件）
            need_comfey = (fc[COMFEY] < 2 and dc[COMFEY] >= 1)
            need_chand = (fc[CHANDELURE] + hc[CHANDELURE] == 0 and dc[CHANDELURE] >= 1)
            # 第14弾: 終盤の自山切れ危険域 ∧ エンジン健在なら再建の掘りはしない（自滅回避）
            if (need_comfey or need_chand) and not self._lo_deck_thinning_forbidden(obs):
                return 12000, "div-C11: Night Stretcher (rebuild engine)"
            return -1, "Night Stretcher: nothing"
        if cid == ENERGY_SEARCH:
            # div-C4: エネ確保はハンマーより先（上位勢はエネ→グッズの順）。
            # div-C10（2026-07-11 実測・調整日07-08/09）: div-C4 の「手張り済みでも先回り確保」を
            # 差し戻し、エネ0のコンフィが実在する時だけ使う。上位勢は不要な山掘りをしない
            # （human=Flower/Comfey/Lillie 等 / ours=Energy Search が 07-08 ×5 + 07-09 ×9、逆方向1件。
            #  ミル型は自山1枚の温存が勝敗に直結する）
            # 第14弾: 終盤の自山切れ危険域 ∧ ミルエンジン健在なら予備エネ堀りはしない（自滅回避）
            if (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1
                    and not self._lo_deck_thinning_forbidden(obs)):
                return 14800, "div-C10: Energy Search (fuel needed)"
            return -1, "Energy Search: not needed"
        if cid == SWITCH_ITEM:
            active = active_pokemon(obs)
            ready = any(pk.id == COMFEY and energy_count(pk) >= 1
                        for pk in my_state(obs).bench if pk)
            if active is not None and active.id != COMFEY and ready:
                return 11000, "Switch: promote Comfey attacker"
            # 第20弾（2026-07-27 ユーザー指示・EXP-065）: バトル場にキュワワー以外がいる意味は
            # ない（FSも撃てず、エンジン/壁をリスクに晒すだけ）。ベンチにキュワワーがいるなら
            # **エネが付いていなくても**入れ替えを使う。エネは後から張れるし、前が非キュワワー
            # のままでは張り先の優先度も崩れる。入れ替え先の選択は既存の「エネ付き優先」帯。
            # ターゲット行動指標 = 「入れ替えを握ったまま非キュワワー前でターン終了」→ 0。
            if (CHA_SWITCH_COMFEY and active is not None and active.id != COMFEY
                    and any(pk is not None and pk.id == COMFEY
                            for pk in my_state(obs).bench)):
                return 11000, "第20弾: Switch (front must be Comfey)"
            return -1, "save Switch"
        if cid == GRAVITY_GEMSTONE:
            # div-C1（2026-07-07 divergence 実測）: 攻撃より下の帯（埋め手）だったが、
            # 第5弾（ユーザー指示）で CHA_USE_TOOL 既定 ON = 手札の道具は攻撃前に必ず着ける
            # （Flower Shower 1950 の上 2080/2060 に持ち上げ、着けてから殴る）。着け先は
            # 従来どおりアクティブ or コンフィ（永久ベンチのシャンデラ等に着けても無意味なので除外）。
            active = active_pokemon(obs)
            if active is not None and not has_tool(active):
                return (2080 if CHA_USE_TOOL else 700), "E-5/div-C1: Gemstone (filler)"
            if any(pk.id == COMFEY and not has_tool(pk) for pk in all_my_pokemon(obs)):
                return (2060 if CHA_USE_TOOL else 650), "E-5/div-C1: Gemstone (bench Comfey filler)"
            return -1, "save Gravity Gemstone"

        # ── サポート（択一） ──
        if obs.current.supporterPlayed and data is not None and data.cardType == CardType.SUPPORTER:
            return -1, "Supporter already used"
        if cid == XEROSIC:
            if CHA_SUPPORT_ORDER:
                # 第18弾: クセロシキが最優先（手札を3枚まで削る＝以降のビワ/ボスを効かせる下地）。
                # 相手手札3枚以下では空振るので打たない（そこはビワ/ボスの帯）。
                if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                    return 6000, "E-3: Xerosic vs Alakazam"
                if p["opp_hand"] > XEROSIC_FLOOR:
                    return (5600 if combat else 5300), "第18弾: Xerosic (最優先で手札を削る)"
                return -1, "第18弾: save Xerosic (相手手札≤3 = 空振る)"
            if CHA_SUPPORTER_TIMING:
                # 第10弾: 序盤（盤面未成熟 = ラインが場に0）はヒカリ/リーリエで展開を優先し、
                # クセロシキは温存（1T目空ベンチでXerosic連打→負けの修正）。ライン始動後は
                # 相手手札が多い時（≥XEROSIC_HAND）にクセロシキ。少ない時はビワへ。
                if p["line_in_play"] == 0:
                    return -1, "第10弾: save Xerosic (develop board first)"
                if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                    return 6000, "E-3: Xerosic vs Alakazam"
                if p["opp_hand"] >= XEROSIC_HAND:
                    return 5500, "第10弾: Xerosic (hand large)"
                return -1, "第10弾: save Xerosic (hand small→Eri)"
            # 旧ロジック（CHA_SUPPORTER_TIMING=0 フォールバック）
            if self.t["matchup"] == "alakazam" and p["opp_hand"] >= 4:
                return 6000, "E-3: Xerosic vs Alakazam"
            if p["opp_hand"] >= 7:
                return 5500, "E-3: Xerosic (big hand)"
            if combat and p["opp_hand"] >= 4:
                return 4800, "E-3: Xerosic"
            if CHA_USE_SUPPORTER and p["opp_hand"] >= 4:
                return 2450, "第5弾: Xerosic (idle disruption)"
            return -1, "save Xerosic"
        if cid == LILLIE:
            # CHA_LILLIE_EARLY（2026-07-24 ユーザー指示）: 序盤はリーリエで攻める —
            # ベンチ展開・エネ堀りなどやりたいことが多い立ち上がりは、トウコ（Hilda 5000）
            # より手数の増えるリーリエを先に切る。対象は「後攻の自分1ターン目（global
            # turn 2）/ 先攻の自分2ターン目（global turn 3）」。帯 5600 = Hilda より上、
            # 山回復 6500・対アラカザム Xerosic 6000 より下（緊急時はそちらが先勝ち）
            if CHA_LILLIE_EARLY:
                st = obs.current
                first = (st.firstPlayer == st.yourIndex)
                if (first and st.turn == 3) or (not first and st.turn == 2):
                    return 5600, "CHA: Lillie (early tempo)"
            # 第25弾b（ユーザー指示）: キュワワーがベンチ+山に居らず（山は会計で不在が判明した
            # 時だけ）、夜のタンカも手札に無い → リーリエ最優先で夜のタンカを引きに行く。
            # トラッシュにキュワワーが居る時だけ（居なければタンカでも回収できない＝掘る意味なし）。
            # 帯 6700 = 回復 6500 より上・あがきボス 6800 の下。
            if CHA_LILLIE_FOR_TANKA:
                # 手札のキュワワーも確認（ユーザー監査 2026-07-29）: 手札に居るなら出せば
                # 済む＝掘り不要。ベンチ満杯で置けない局面での誤発火（手札のキュワワーごと
                # 山へシャッフル）も防ぐ。トラッシュにも居ない（=4枚全サイド落ち）なら
                # タンカでも回収不能＝この筋は諦める（dc ガードで自然に不発火）。
                if (p["bench_comfey"] == 0
                        and hc[COMFEY] == 0
                        and not self._maybe_in_deck(COMFEY, 4)
                        and hc[NIGHT_STRETCHER] == 0
                        and dc[COMFEY] >= 1):
                    return 6700, "第25弾: Lillie (dig for Night Stretcher)"
            # 第23弾③（ユーザー指示）: キュワワーの技が打てない番は、妨害札（クセロシキ
            # 5600/ビワ 5000）より先にリーリエで掘ってエンジンを直す。ミルが止まった番の
            # 妨害はレースを進めない。帯 5800 = クセロシキ 5600 の直上。
            # 手張りで直る局面では ATTACH(19800+) が先に走り、この条件は自然に偽へ戻る。
            # ※収支の赤字ゲートより先に置く（掘れないと詰むので赤字でも打つ）。
            if CHA_LILLIE_NOFS:
                act = active_pokemon(obs)
                if not (act is not None and act.id == COMFEY
                        and energy_count(act) >= 1):
                    # ③b: 赤字の掘りは「**打った後も**自山 > 相手山」の時だけ（ユーザーの
                    # 不変条件と同じ事後判定 = 第16弾ゲートと統一）。これで
                    #   ・しまっている首をさらにしめる（打つ前から負けレースで赤字掘り）
                    #   ・首をしめる（打つと追い越される。例: 自山16/相手15/手札3 → 打つと10）
                    # の両方を止める。黒字（手札≥9）は山が減らないので常に掘ってよい。
                    # 負けレース時の再建は Hilda 遊軍 2350（固定費 −2）が担う。
                    # 帯 6100（2026-07-28 ユーザー監査で 5800→6100）: 対アラカザムの
                    # クセロシキ特化帯 6000 より上に置く。「ミル不能番はリーリエが妨害より
                    # 優先」は対アラカザムでも成立する（回復6500・あがき6800の下）。
                    if (p["hand_size"] >= 9
                            or p["my_deck"] + (p["hand_size"] - 9) > p["opp_deck"]):
                        return 6100, "第23弾: Lillie (can't mill — dig, beats disruption)"
            # ── 第16弾（EXP-060）: 収支を実際に計算してから打つ ──
            # 旧実装は「手札≥7 で山が純増」（＝6ドロー前提）を3か所で仮定していたが、
            # 本デッキはサイドを取らない＝常に8ドロー＝損益分岐は手札9枚。実測で
            # 手札3〜6 の使用が 6試合13回・−56枚の自滅要因だった。
            delta = self._lillie_deck_delta(p)
            if not CHA_LILLIE_LEDGER:
                # ── 旧ロジック（完全ロールバック用・原文のまま） ──
                # 「手札≥7 なら山が純増」という 6ドロー前提の誤りを含む。
                if self._chandelure_dead() and p["my_deck"] <= 12:
                    return 6500, "第13弾: Lillie (deck recovery, Chandelure dead)"
                if (CHA_LO_SAFETY and p["my_deck"] <= LO_DANGER_DECK
                        and p["hand_size"] >= 7):
                    return 6500, "第14弾: Lillie (deck recovery, LO danger)"
                if p["my_deck"] <= 6:
                    return 6500, "E-2: Lillie (refill deck)"
                if p["hand_size"] <= 6:
                    return 4500, "E-2: Lillie (refresh)"
                if p["hand_size"] >= 9 and p["my_deck"] <= 15:
                    return 4200, "E-2: Lillie (bank fat hand)"
                if CHA_USE_SUPPORTER and p["hand_size"] >= 7:
                    return 2300, "第5弾: Lillie (idle, bank into deck)"
                return -1, "save Lillie"
            # 赤字リーリエの可否は「手札が何枚か」ではなく **打った後も相手より山が多いか**
            # で決める（ユーザーの不変条件 2026-07-27）:
            #   「こちらの残り枚数の少なさが相手を追い越してしまった場合、
            #     相手が能動的に引かない限り確定で負け」
            # エンジン（FS/特性）は両者同数を引かせるので**枚数差を動かさない**。差を動かすのは
            # こちらのサーチ（自分だけ減る）とリーリエだけ。よって差がマイナスに転じたら詰み。
            # 相手より山が厚いうちは赤字を払って手札を作り直す余裕がある（＝プライズ負けする
            # 対面で生存に必要な手札を確保できる。CHA_LILLIE_RACE=0 で「常に赤字禁止」に戻る）。
            if delta < 0 and not self._engine_broken(obs):
                # 第17弾: 山切れが本当の死因でないなら温存に意味がない（marnie 戦は
                # 自山切れ 0% なのに温存して −6pt だった）→ 赤字を払って手札を作り直す。
                afford = (CHA_LILLIE_RACE
                          and p["my_deck"] + delta > p["opp_deck"])
                if not afford:
                    return -1, f"第16弾: Lillie は赤字({delta:+d}枚)で追い越される — 打たない"
            # 第13弾: シャンデラ全落ち = キュワワー単体ミルの寿命勝負 → 山札回復を最優先（早めに回す）。
            # 手札の死にヒトモシ線も山へ戻って寿命に変わる（「山札回復に割り当てる」）。
            if self._chandelure_dead() and p["my_deck"] <= 12:
                return 6500, "第13弾: Lillie (deck recovery, Chandelure dead)"
            # 第23弾①（ユーザー指示）: 相手が LO でない限り、山回復リーリエは
            # 「次の自分番を回せない」時だけ（need = ターン頭1 + FS3 + 特性×シャンデラ + 余裕2）。
            # 旧閾値 13 は発火しすぎで、その番のクセロシキ/ビワを潰していた。
            # 自山が無事な限りサポート枠は妨害に使う（対 LO＝ミラーだけは従来の早め回復）。
            # 第23弾①b: 「緊急時のみ」を適用するのは**山札レースに勝っている時だけ**
            # （自山 > 相手山 ＝ 相手が先に尽きる ＝ ユーザーの「本来負けません」局面）。
            # レースに負けている/並んでいる時（crustle_wall 型: 相手がリーリエ×4で山を
            # 回復し続け、こちらの負け筋96%が自山切れ）は従来の早め回復（閾値13）で山を守る。
            # 相手のデッキ名でなく山札レースの現在値で切り替える（特殊化はしない）。
            if (CHA_LILLIE_URGENT and self.t["matchup"] not in mt.LO_ARCHETYPES
                    and p["my_deck"] > p["opp_deck"]):
                need = 6 + fc[CHANDELURE]
                if p["my_deck"] <= need and delta > 0:
                    return 6500, "第23弾: Lillie (urgent recovery)"
            else:
                # 第14弾: 終盤の自山切れ危険域は、手札が回復に足りる（＝山が純増する）なら早めに回復して
                # エンジンドロー（FS3+AL1+ドロー1=約5/ターン）で山切れする前に立て直す（自滅回避）。
                # 第16弾で閾値を「手札≥7」から「実際の収支 delta>0」へ厳密化。
                if CHA_LO_SAFETY and p["my_deck"] <= LO_DANGER_DECK and delta > 0:
                    return 6500, "第14弾: Lillie (deck recovery, LO danger)"
                # E-2: 山の回復装置。山が薄い時は最優先、手札が太い時は山へ還流
                # 第16弾: 「山が薄いから打つ」は収支が黒字の時だけ（赤字なら打つほど早く死ぬ）
                if p["my_deck"] <= 6 and delta >= 0:
                    return 6500, "E-2: Lillie (refill deck)"
            if p["hand_size"] >= 9 and p["my_deck"] <= 15:
                return 4200, "E-2: Lillie (bank fat hand)"
            # 第5弾: サポート枠が暇でも、リーリエは「手札を山へ戻す」= 山が純増する時だけ
            # 遊軍で切る（ミルの自山温存に順方向）。赤字なら温存のまま。
            if CHA_USE_SUPPORTER and delta > 0:
                return 2300, "第5弾: Lillie (idle, bank into deck)"
            return -1, "save Lillie"
        if cid == mt.BOSS:
            return self._score_boss(obs, combat)
        if cid == HILDA:
            # 第14弾: 終盤の自山切れ危険域 ∧ エンジン健在なら掘らない（自滅回避）
            if self._lo_deck_thinning_forbidden(obs):
                return -1, "第14弾: LO safety — save Hilda (don't thin)"
            need_evo = (fc[LITWICK] >= 1 and hc[LAMPENT] + hc[CHANDELURE] == 0)
            need_energy = (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1)
            if need_evo or need_energy:
                return (5000 if not combat else 4200), "S-4: Hilda"
            # 第22弾（ユーザー指示・EXP-067）: サポート枠を空けたままターンを終えない。
            # 上位帯（クセロシキ/ビワ/黒字リーリエ等）が全て見送った時の遊軍として打つ。
            if CHA_IDLE_SUPPORT:
                return 2350, "第22弾: Hilda (idle supporter slot)"
            return -1, "save Hilda"
        if cid == DAWN:
            # 第14弾: 終盤の自山切れ危険域 ∧ エンジン健在なら掘らない（自滅回避）
            if self._lo_deck_thinning_forbidden(obs):
                return -1, "第14弾: LO safety — save Dawn (don't thin)"
            # 第13弾: シャンデラ全落ちなら一式サーチは無意味（線は死に札）→ 打たない
            if self._chandelure_dead():
                return -1, "第13弾: Dawn useless (Chandelure dead)"
            # 第10弾バグ修正（常時ON）: ライン全欠損（場に線0 ∧ 手札にも線0）なら、ヒカリで一式
            # （たね+1進化+2進化）サーチを Xerosic(5500) より上の 5700 で打ち、盤面成熟を最優先。
            # = 1T目空ベンチでヒカリをスルーしクセロシキ連打→負けの事故の修正。
            if p["line_in_play"] == 0 and hc[LITWICK] + hc[LAMPENT] + hc[CHANDELURE] == 0:
                return 5700, "第10弾: Dawn (develop whole line, beats Xerosic)"
            # 第22弾（ユーザー指示・EXP-067）: サポート枠を空けたままターンを終えない。
            # ヒカリの山3枚引っこ抜きは「一旦きにしなくていい」（ユーザー）。Hilda(2350) の次。
            if CHA_IDLE_SUPPORT:
                return 2250, "第22弾: Dawn (idle supporter slot)"
            return -1, "save Dawn"
        if cid == ERI:
            if CHA_SUPPORT_ORDER:
                # 第18弾: クセロシキの次。相手手札が薄い（＝クセロシキが空振る帯）ほど
                # ビワの「グッズ2枚抜き」が資源に占める割合が大きく、ピンポイントに効く。
                # 手札0では何も抜けないので打たない。
                if 1 <= p["opp_hand"] <= XEROSIC_FLOOR + 2:
                    return (5000 if combat else 4600), "第18弾: Eri (資源をピンポイントに削る)"
                if CHA_USE_SUPPORTER and p["opp_hand"] >= 1:
                    return 2400, "第5弾: Eri (idle disruption)"
                return -1, "第18弾: save Eri"
            if CHA_SUPPORTER_TIMING:
                # 第10弾: ビワも試合後半（combat）＋相手手札が少ない時（クセロシキが空振る帯 =
                # 手札 < XEROSIC_HAND）。序盤は温存して盤面成熟を優先。
                if combat and 1 <= p["opp_hand"] < XEROSIC_HAND:
                    return 4000, "第10弾: Eri (late-game, hand small)"
                return -1, "第10弾: save Eri (early or hand large→Xerosic)"
            # 旧ロジック（CHA_SUPPORTER_TIMING=0 フォールバック）
            if combat and p["opp_hand"] >= 4:
                return 4000, "E-3: Eri"
            if CHA_USE_SUPPORTER:
                return 2400, "第5弾: Eri (idle disruption)"
            if CHA_ERI_IDLE:
                return 400, "CHA: Eri (idle supporter)"
            return -1, "save Eri"
        return 1000, "generic play"

    # ── ボスの指令（第6弾 2026-07-25 ユーザー指示で全面改訂） ──

    def _score_boss(self, obs, combat):
        """拘束（trap）として意味を持つ最低条件（ユーザー指定）:
          (a) 相手バトル場が攻撃条件を満たす（エネ載り・払える技あり = 実アタッカー）
          (b) ベンチに攻撃条件を満たさない駒がいる（にげ≥1、≥2 が望ましい）
        → 相手の実アタッカーをベンチへ剥がし、殴れない＆重い駒を前に貼って番を潰す。
        (a) を欠く「バトル場のベロバーに対しベンチのベロバーを呼ぶ」無意味ドラッグを廃止。

        あがき: 番を返すと負け確定（R-08 脅威が可視 ∧ 相手バトル場が攻撃可能）な時だけ、
        トラップ先を最優先で吊ってリーサルを1ターン遅らせる延命策。
        （リーサルボスは apply_protocol が LETHAL_BAND へ昇格するのでここは非リーサル帯のみ）"""
        if not CHA_BOSS_SMART:
            return self._score_boss_legacy(obs, combat)
        trap_targets = self._boss_trap_targets(obs)
        if not trap_targets:
            return -1, "第6弾: Boss (no trappable non-attacker)"
        if not self._can_attack_now(opp_active_pokemon(obs)):
            return -1, "第6弾: Boss (opp active can't attack — pointless)"
        # あがき: 負け確定リーチなら最優先で延命（Lillie 山回復 6500 も上回る）
        # ★イレギュラーとして第18弾でも不変（ユーザー指示）
        if self.t["threats"]:
            return 6800, "第6弾: Boss (あがき: deny next-turn lethal)"
        if CHA_SUPPORT_ORDER:
            # 第18弾（ユーザー指示）: 基本順序は **クセロシキ → ビワ → ボスで縛る**。
            # 序盤のボスは逃げられて空振るので、まず手札と資源を枯らしてから拘束する。
            # ⇒ ボスの帯をクセロシキ(5600/5300)・ビワ(5000/4600)の下へ置く。
            # 「ビワとボスならボスのほうが後のほうが嬉しい」＝ビワより下（ユーザー）。
            if any(retreat_cost(b) >= 2 for b in trap_targets):
                return (4400 if combat else 3900), "第18弾: Boss (heavy retreat trap・資源枯渇後)"
            return (4200 if combat else 3700), "第18弾: Boss (trap・資源枯渇後)"
        if any(retreat_cost(b) >= 2 for b in trap_targets):
            return (5800 if combat else 5000), "第6弾: Boss (heavy retreat trap)"
        return (5200 if combat else 4700), "第6弾: Boss (trap, retreat>=1)"

    def _score_boss_legacy(self, obs, combat):
        """CHA_BOSS_SMART=0 時のフォールバック（第4/5弾の旧ロジック。ロールバック用）。"""
        if CHA_BOSS_HEAVY and any(
                retreat_cost(b) >= 2 and energy_count(b) <= 1
                for b in opp_state(obs).bench if b):
            return (5800 if combat else 5000), "CHA: Boss (heavy retreat trap)"
        if combat and any(energy_count(b) == 0 for b in opp_state(obs).bench if b):
            return 5200, "E-5: Boss (drag & trap)"
        if combat and any(b for b in opp_state(obs).bench if b):
            return 4700, "div-C5: Boss (loose drag)"
        if CHA_USE_SUPPORTER and any(b for b in opp_state(obs).bench if b):
            return 2500, "第5弾: Boss (idle drag)"
        return -1, "save Boss"

    # ── ATTACH（S-5 + R-10 + R-08） ──

    def _score_attach(self, obs, opt):
        p = self.p
        fc, hc, dc = p["fc"], p["hc"], p["dc"]
        card = option_card(obs, opt)
        target = option_target(obs, opt)
        if card is None or target is None:
            return 0, "attach none"
        cid, tid = card.id, target.id

        if cid == GRAVITY_GEMSTONE:
            # div-C1: 攻撃より下の帯 = 「攻撃できないターンの埋め手」（実測: 上位勢は
            # 宝石を持ったまま攻撃するターンが多く、装着は22試合で20回に留まる）だったが、
            # 第5弾（ユーザー指示）で CHA_USE_TOOL 既定 ON = 攻撃前に必ず着ける（FS1950 の上へ）。
            if has_tool(target):
                return -1, "target has tool"
            active = active_pokemon(obs)
            if tid == COMFEY and active is not None and target is active:
                return (2080 if CHA_USE_TOOL else 700), "E-5/div-C1: Gemstone on active Comfey (filler)"
            if tid == COMFEY:
                return (2060 if CHA_USE_TOOL else 650), "E-5/div-C1: Gemstone on bench Comfey (filler)"
            if active is not None and target is active:
                return (2040 if CHA_USE_TOOL else 600), "E-5: Gemstone on active (filler)"
            return -1, "save Gravity Gemstone"

        if cid not in ENERGY_CARDS:
            return -500, "skip non-energy attach"
        if obs.current.energyAttached:
            return -1, "already attached"

        if tid == COMFEY:
            if energy_count(target) >= 1:
                return -1, "R-10: Comfey already paid (cost 1)"
            active = active_pokemon(obs)
            # div-C4: 手張りはハンマー等のグッズより先（上位勢はエネ→グッズの順）
            # div-C12（2026-07-11 実測・調整日07-08/09）: 帯を 15500 → 19800 に引き上げ、
            # ポフィン(18000)/パッド(17000)/NZ(19500) より前に手張りを済ませる
            # （human=ATTACH ours=Poffin/Pad/NZ が 07-08 ×8 + 07-09 ×4、逆方向計6件。
            #  1ターン1回の権利を先に確実に消費する順序が上位勢の型）
            if CHA_FUEL_TARGET:
                # CHA_FUEL_TARGET【棄却・opt-in 2026-07-22】: S-5 の同点（負け試合 =
                # ベンチ間 m=0 / テレパス vs 基本 m=50 / アクティブ vs ベンチ m=100）に
                # 挙動を変える意見を与える版。A/B 実測で集計悪化のため既定 OFF。
                #   (1) アクティブ +3500（今番の FS 即撃ち）
                #   (2) ベンチ間は壁 +2000 — 注: コンフィ HP70 < 汎用打点想定 220 のため
                #       実質不発（発火はミラーの打点想定40のみ）
                #   (3) 両種所持時のみ種の使い分け +1000（連鎖生存→テレパス/死→基本）
                # 上限 19800+3500+1000=24300 は進化帯 24000 と交差しうる。
                bonus = 0
                if active is not None and target is active:
                    bonus += 3500
                elif target.hp > self.opp_max_damage(obs):
                    bonus += 2000
                if hc[BASIC_P] >= 1 and hc[TELEPATH] >= 1:
                    comfey_in_deck = 4 - fc[COMFEY] - hc[COMFEY] - dc[COMFEY]
                    chain_live = p["bench_free"] >= 2 and comfey_in_deck >= 1
                    preferred = TELEPATH if chain_live else BASIC_P
                    bonus += 1000 if cid == preferred else 0
            else:
                # CHA_MARGIN【採用 2026-07-22】: 既存の選好（アクティブ>ベンチ、テレパス>基本）
                # の順序はそのままに段差だけ 100→2100 / 50→1050 に拡幅 = 監査の decisive
                # 閾値 1000 を跨がせる（S-5 の m=50/m=100 クラスタ解消。ベンチ間同種 m=0 は
                # 実在の選好が無いため対象外）。序列検証: 上限 19800+3150=22950 は
                # EVOLVE 24000 の下・PLAY ポケモン帯 20000-20500 とは交差するが両者とも
                # 番を終えない手で同一ターン実行集合は不変（対戦ハーネスは PYTHONHASHSEED
                # 固定でも非決定的なため軌跡一致検証は不可 — 同一性の根拠は本注釈の全帯
                # 序列照合 + null A/B ±3pt 以内）。R-08 脅威対象は旧段差のまま
                # （拡幅すると 19800+3150-2000=20950 > ポフィン18000 となり「ポフィンで
                #  新コンフィを出してから張る」旧挙動の順序が壊れるため脅威時は旧式固定）。
                wide = CHA_MARGIN and not self.is_threatened(target)
                bonus = ((2100 if wide else 100)
                         if (active is not None and target is active) else 0)
                bonus += (1050 if wide else 50) if cid == TELEPATH else 0   # テレパスはベンチ連鎖付き
            score = 19800 + bonus
            if self.is_threatened(target):
                score -= 2000   # R-08: 負け筋への追い銭防止
            return score, "S-5: fuel Flower Shower"
        # 第8弾: 場スタートのシェイミに逃げエネを張る（入れ替えが手札に無い時だけ = Switch は
        # 無料なので優先）。1枚張れば逃げエネ1を払える → 次の決定で逃げ→キュワワー前出し→FS。
        # 帯 19850 = S-5 手張り(19800)の直上 = 「今番FSを始める」を最優先。
        if (tid == SHAYMIN and self._shaymin_retreat_ready(obs)
                and p["hc"][SWITCH_ITEM] == 0):
            active = active_pokemon(obs)
            if (active is not None and target is active
                    and energy_count(target) < retreat_cost(target)):
                return 19850, "第8弾: fuel Shaymin to retreat (Comfey FS ready)"
        # 第19弾（ユーザー指示）: バトル場のヒトモシ/ランプラーに**積極的に**にげエネを張って、
        # エネ付きキュワワーに交代する。前の2枚は技が炎コストで実質不発＝居座ると今番のミルが
        # 丸ごと止まるので、エネ1枚の対価は安い。入れ替え（無料）が手札にあるならそちら優先。
        if (tid in (LITWICK, LAMPENT) and self._line_retreat_ready(obs)
                and p["hc"][SWITCH_ITEM] == 0):
            active = active_pokemon(obs)
            if (active is not None and target is active
                    and energy_count(target) < retreat_cost(target)):
                # 逃げエネは基本{P}を優先。テレパスは「{P}ポケモンに手張り」でしか山から
                # たね{P}2体を呼べず、ヒトモシ/ランプラーは{R}なので連鎖が不発になる
                # → テレパスはキュワワー用に温存する（基本エネが手札にある時だけ後回し）。
                if cid == TELEPATH and p["hc"][BASIC_P] >= 1:
                    return 19840, "第19弾: fuel line to retreat (基本エネを優先)"
                return 19850, "第19弾: fuel Litwick/Lampent to retreat (Comfey FS ready)"
        return -1, "S-5: energy only on Comfey"

    # ── CARD/ENERGY 選択（サーチ先・前出し・吊り出し等） ──

    def _score_card(self, obs, opt, combat):
        p = self.p
        yi = obs.current.yourIndex
        ctx = obs.select.context
        pi = opt.playerIndex if opt.playerIndex is not None else yi
        card = option_card(obs, opt)
        cid = card.id if card else getattr(opt, "cardId", None)
        fc, hc = p["fc"], p["hc"]

        if ctx in (SelectContext.SWITCH, SelectContext.TO_ACTIVE):
            if pi == yi:
                # E-7: 前出しはコンフィ最優先（実測45/54）。シャンデラ/シェイミは守る
                if cid == COMFEY:
                    if CHA_PROMOTE and not self.is_threatened(card):
                        # CHA_PROMOTE【棄却・opt-in 2026-07-22】: promote Comfey 同点
                        # （m=0 / m=100）への挙動を変える意見（エネ付き +4000 > 壁 +2000 >
                        # 無傷 +1000 > 素。辞書式段差）。壁 +2000 はコンフィ HP70 < 打点
                        # 想定 220 で実質不発。A/B 実測で集計悪化のため既定 OFF。
                        # R-08 脅威駒は旧式のままにして、脅威コンフィがヒトモシ4500等を
                        # 追い越す事故を構造的に防ぐ。
                        bonus = 4000 if energy_count(card) >= 1 else 0
                        bonus += 2000 if card.hp > self.opp_max_damage(obs) else 0
                        bonus += 1000 if damage_on(card) == 0 else 0
                        score, reason = 15000 + bonus, "promote Comfey"
                    else:
                        # CHA_MARGIN【採用 2026-07-22】: 既存の「エネ付き優先」の段差だけ
                        # ×100→×1100 に拡幅（m=100 クラスタを decisive 化。順序厳密不変:
                        # コンフィ帯 [15000,16100+] は他候補 4500/4300/3000/2500 と交差せず、
                        # R-08 −15000 後の帯 [0,1100+] も同順序を保つ。同状態 m=0 は実在の
                        # 選好が無いため対象外）。
                        mult = 1100 if CHA_MARGIN else 100
                        score, reason = 15000 + energy_count(card) * mult, "promote Comfey"
                elif cid == LITWICK:
                    score, reason = 4500, "promote Litwick"   # ライン内はたね=ヒトモシを先に犠牲
                elif cid == LAMPENT:
                    score, reason = 4300, "promote Lampent"
                elif cid == CHANDELURE:
                    score, reason = 3000, "protect Chandelure (engine)"
                elif cid == SHAYMIN:
                    # 第9弾: 非狙撃はシェイミを線より先に犠牲（線を守る）→ ヒトモシ4500 の上 5000。
                    # 狙撃相手は壁のシェイミを温存し線を先に切る → シャンデラ3000 の下 2500。
                    if CHA_ACTIVE_PRIORITY and not self._opp_bench_snipes(obs):
                        score, reason = 5000, "第9弾: sacrifice Shaymin (protect line)"
                    else:
                        score, reason = 2500, "protect Shaymin (wall vs snipe)"
                else:
                    score, reason = 1000, "promote other"
                return self.default_score_promote(obs, opt, score, reason)   # R-08
            # E-5: ボス吊り出し = 拘束（エネ0・にげる重い・NZ稼働中のex）
            # div-C7（2026-07-11 実測・調整日07-08）: マシマシラ+400 を除去。上位勢の吊り先は
            # 5/5 でユキメノコ > マシマシラ（Star-mine ×4 + kidekikish ×1 のクロスピロット）。
            # Adrena-Brain はベンチからでも機能するため吊っても止まらない = 拘束価値なし
            score = 5000 + retreat_cost(card) * 200 - energy_count(card) * 300
            # 第6弾: 攻撃できる駒を吊ると相手が得するだけ（前に出して殴られる）→ 強く忌避。
            # 攻撃条件を満たさない駒（＝ホントの拘束先）を必ず優先する
            if CHA_BOSS_SMART and self._can_attack_now(card):
                score -= 4000
            if p["stadium_id"] == NEUTRAL_ZONE and is_ex(card):
                score += 800   # NZ 稼働中の ex は完全に無力
            return score, "E-5: drag & trap target"

        if ctx == SelectContext.DISCARD_ENERGY:
            # E-6: ハンマー対象。相手側のみ（自分側は minCount 充足の least-bad）
            if pi != yi and card is not None:
                score = 10000 + energy_count(card) * 100
                opp = opp_state(obs)
                if opp.active and card is opp.active[0]:
                    score += 500   # 前を乾かして攻撃を止める
                if cid == OPP_MUNKIDORI:
                    score += 300   # Adrena-Brain 停止
                return score, "E-6: hammer target"
            return -1000, "never discard own energy"

        if ctx == SelectContext.TO_HAND:
            # div-C4（2026-07-07 divergence 実測）: 上位勢の優先表
            # シャンデラ（無条件）> コンフィ > エネ > ヒトモシ > ランプラー
            # div-C9（2026-07-11 実測・調整日07-08/09）: 表を機能条件化 —
            #   (1) ラインの中間（ランプラー）が完全に欠けている時はシャンデラより先に取る
            #       （human=Lampent/ours=Chandelure が 07-08 ×5 + 07-09 ×1。進化はランプラー経由必須）
            #   (2) シャンデラの path 判定に手札のランプラーを含める（確保後はシャンデラ優先 07-09 実測）
            #   (3) 2枚目以降のシャンデラは減衰（human=Comfey/ours=Chandelure ×3。特性ボディは1体で十分）
            #   (4) 場にコンフィ0ならコンフィ最優先（S-0: エンジン無しではミルが始まらない）
            # CHA_MARGIN【採用 2026-07-22】: TO_HAND 表全体を ×50 に等倍スケール
            # （順序・符号は厳密に不変 = 挙動同一。実在する選好差、例えば
            # ランプラー92 vs シャンデラ90 の 2 が 100 になり、監査の絶対閾値 1000 に
            # 対して意見が計測可能になる下地）。同名カード同士の m=0 は論理的に解消不能。
            # CHA_TAKE_ENERGY【棄却・opt-in】: 選択肢に基本{P}とテレパスの両種が
            # 並ぶ時だけ使い分けの意見 +1000: テレパス連鎖が生きている（ベンチ2枠以上
            # ∧ 山にコンフィ残）ならテレパス、死んでいるなら基本（夜のタンカ/エネ転送で
            # 回収できる方を使い、連鎖価値のある特殊エネは温存しない場面を作らない）。
            # A/B 実測で集計悪化のため既定 OFF（TAKE 有効時はスケールも強制 = ±1000 が
            # 未スケール表を飲み込む事故を防ぐ）。
            sc = 50 if (CHA_MARGIN or CHA_TAKE_ENERGY) else 1
            base = (100 - hc.get(cid, 0) * 25) * sc
            if cid == CHANDELURE:
                # 第11弾（ユーザー指示）: 即進化できないシャンデラは持ってこない（低帯へ）。
                # = 場にランプラー or アメ手札∧場ヒトモシ が無ければ探索先にしない。
                if CHA_PAD_PLAYABLE and not self._pad_immediately_playable(CHANDELURE):
                    return -1, "第11弾: skip Chandelure (can't evolve this turn)"
                # 第7弾b（ユーザー指示）: ふしぎなアメが手札 ∧ 場にヒトモシ = アメで即進化できる
                # → 探索（ポケパッド等）はランプラーを飛ばしてシャンデラを最優先で持ってくる
                # （ヒトモシ+アメ+シャンデラ = 1ターン完成。ランプラー経由の2ターン進化より速い）
                if (CHA_PAD_BUILD and hc[RARE_CANDY] >= 1 and fc[LITWICK] >= 1
                        and fc[CHANDELURE] + hc[CHANDELURE] == 0):
                    return base + 130 * sc, "第7弾b: take Chandelure (Rare Candy ready)"
                path = fc[LITWICK] + fc[LAMPENT] + hc[LITWICK] + hc[LAMPENT] >= 1
                first = fc[CHANDELURE] + hc[CHANDELURE] == 0
                return base + ((90 if first else 65) if path else 55) * sc, "div-C4/C9: take Chandelure"
            if cid == COMFEY:
                if fc[COMFEY] == 0:
                    return base + 95 * sc, "div-C9: take Comfey (engine down)"
                return base + (70 if fc[COMFEY] + hc[COMFEY] < 4 else -20) * sc, "div-C4: take Comfey"
            if cid in ENERGY_CARDS:
                bonus = (60 if (p["energy_in_hand"] == 0 and p["comfey_need"] >= 1) else 25) * sc
                if CHA_TAKE_ENERGY:
                    kinds = set()
                    for o in obs.select.option:
                        c2 = option_card(obs, o)
                        if c2 is not None and c2.id in ENERGY_CARDS:
                            kinds.add(c2.id)
                    if len(kinds) >= 2:
                        comfey_in_deck = 4 - fc[COMFEY] - hc[COMFEY] - p["dc"][COMFEY]
                        chain_live = p["bench_free"] >= 2 and comfey_in_deck >= 1
                        preferred = TELEPATH if chain_live else BASIC_P
                        bonus += 1000 if cid == preferred else 0
                    else:
                        bonus += 5 * sc if cid == TELEPATH else 0
                else:
                    bonus += 5 * sc if cid == TELEPATH else 0
                return base + bonus, "take energy"
            if cid == LITWICK:
                if self._chandelure_dead():
                    return -1, "第13弾: skip Litwick (Chandelure dead)"
                if p["line_in_play"] == 0:
                    return base + 75 * sc, "div-C4: take Litwick (start the line)"
                return base + (50 if p["line_in_play"] < 3 else -20) * sc, "take Litwick"
            if cid == LAMPENT:
                # 第11弾: 場にヒトモシがいて即進化できる時だけ持ってくる（手札のヒトモシは同ターン
                # 進化不可なので対象外 = fc[LITWICK] のみ）。
                if CHA_PAD_PLAYABLE and not self._pad_immediately_playable(LAMPENT):
                    return -1, "第11弾: skip Lampent (no Litwick in play)"
                if fc[LAMPENT] + hc[LAMPENT] == 0 and fc[LITWICK] + hc[LITWICK] >= 1:
                    return base + 92 * sc, "div-C9: take Lampent (missing middle)"
                return base + (45 if fc[LITWICK] >= 1 else 10) * sc, "take Lampent"
            if cid == SHAYMIN:
                if (CHA_SHAYMIN_VS_SNIPE and fc[SHAYMIN] == 0
                        and self._opp_bench_snipes(obs)):
                    # 第5弾: 狙撃相手なら壁を engine 級で確保（ヒトモシ75/コンフィ70 の上・
                    # 本命のシャンデラ90/ランプラー92/エンジン欠けコンフィ95 の下）
                    return base + 78 * sc, "第5弾: take Shaymin (vs snipe)"
                return base + (20 if fc[SHAYMIN] == 0 else -30) * sc, "take Shaymin"
            if cid == RARE_CANDY:
                return base + (40 if fc[LITWICK] >= 1 and hc[CHANDELURE] >= 1 else 0) * sc, "take Candy"
            return base, "take other"

        if ctx == SelectContext.TO_BENCH:
            # S-2/div-C3（2026-07-07 divergence 実測）: コンフィ最優先（57 vs 20）で常にヒトモシより上
            if p["bench_free"] <= 0:
                return -1, "bench full"
            if cid == COMFEY:
                # 第7弾: 場のキュワワーは3体で十分（4体目はベンチ献上＋ライン枠を潰す）
                if CHA_COMFEY_CAP and fc[COMFEY] >= COMFEY_FIELD_CAP:
                    return -1, "第7弾: 3 Comfey is enough (no 4th)"
                return 120 - fc[COMFEY] * 10, "div-C3: bench Comfey first"
            if cid == LITWICK:
                if self._chandelure_dead():
                    return -1, "第13弾: don't bench Litwick (Chandelure dead)"
                return 70 - p["line_in_play"] * 15, "S-2: bench Litwick"
            if cid == SHAYMIN:
                if (CHA_SHAYMIN_VS_SNIPE and fc[SHAYMIN] == 0
                        and self._opp_bench_snipes(obs)):
                    return 110, "第5弾: bench Shaymin (vs snipe)"   # コンフィ120の下・ヒトモシ70の上
                return (60 if fc[SHAYMIN] == 0 else -30), "S-2: bench Shaymin"
            return 10, "bench other"

        if ctx == SelectContext.DISCARD:
            # 第10弾: 手札を減らす（クセロシキ等）時は次ターン暇しない残し方（サポート最低1枚）
            if CHA_DISCARD_KEEP:
                return self._score_discard(obs, opt)
            return self.default_score_discard(obs, opt)   # R-13
        if ctx == SelectContext.DISCARD_CARD_OR_ATTACHED_CARD:
            return self.default_score_discard(obs, opt)   # R-13（付与エネ含む場面は従来通り）

        if ctx == SelectContext.TO_DECK:
            if cid in CHANDELURE_LINE:
                return 100, "to deck line"
            if cid == COMFEY:
                return 90, "to deck Comfey"
            return 10, "to deck other"

        if ctx in (SelectContext.DAMAGE, getattr(SelectContext, "DAMAGE_COUNTER", SelectContext.DAMAGE)):
            return self.default_score_damage_target(obs, opt)   # R-15

        return 500, "generic card"


# ═══════════════ エントリポイント ═══════════════
# R-25【ハード】: Kaggle のローダーは「main.py で最後に定義された callable」をエージェントとして
# 呼ぶ（kaggle_environments の get_last_callable）。def agent は必ずファイル末尾の callable にする。

_impl = make_agent(ChandelurePolicy)


def read_deck_csv():
    return _read_deck_csv()


def agent(obs_dict):
    return _impl(obs_dict)
