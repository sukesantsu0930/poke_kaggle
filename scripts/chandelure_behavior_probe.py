"""ルールの「行動指標」を直接測るプローブ（2026-07-27・ユーザー方針）。

背景: 行動分布を少し変えただけのルールは勝率にはほぼ出ない（LB ノイズ床 ±50〜70点・
ローカル 640戦/枠 ±2.6pt を実測済み）。だから**ルールを作るときに「どういう振る舞いが
増えてほしいか」を指標として定義し、勝率でなくその指標で評価する**。
勝率は非劣化ゲートとしてだけ使う。

このスクリプトは N 戦を実対戦させ、リプレイ＋行動ログから以下を機械計算する:

  [第16弾] lillie   : リーリエ使用回数 / 赤字打ち回数(手札<9) / 山の正味増減（枚）
  [第16弾] poffin   : ポフィン使用回数 / 違反回数（キュワワー在庫≥1 ∧ ライン≥2 で使用）
  [第18弾] support  : クセロシキ/ビワ/ボス使用時の相手手札の平均 /
                      早すぎるボス回数（相手手札>3 ∧ クセロシキを握ったままボス）
  [第19弾] stuck    : 「前がヒトモシ/ランプラー ∧ ベンチにエネ付きキュワワー」で始まった
                      自分の手番の数 / うちその番に FS を撃てなかった数（=丸損ターン）
  [全般]   tempo    : FS 回数/戦、終局時の自山/相手山

使い方:
  python scripts/chandelure_behavior_probe.py --opponent crustle_wall --games 30
  python scripts/chandelure_behavior_probe.py --opponent marnie_luca --games 30 \
      --env CHA_LINE_RETREAT=0        # トグル OFF との行動差を見る
"""
import argparse
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base"]:
    sys.path.insert(0, str(ROOT / p))

from chandelure_make_loss_replays import OPP_AGENT  # noqa: E402

ID_RE = re.compile(r"\(ID (\d+)\)")
LILLIE, POFFIN, XEROSIC, ERI, BOSS = 1227, 1086, 1197, 1186, 1182
COMFEY, LITWICK, LAMPENT, CHAND = 164, 97, 494, 98
SWITCH_ITEM = 1123
NEUTRAL_ZONE = 1247


def sel_ids(rec):
    """agentlog レコードの selected ラベル列からカードIDを抜く。"""
    return [int(m.group(1)) for s in rec["selected"] for m in [ID_RE.search(s)] if m]


def is_fs_attack(rec):
    return any("attack Flower Shower" in s for s in rec["selected"])


def energy_n(pk):
    for k in ("energies", "energyCards"):
        v = pk.get(k)
        if v:
            return len(v)
    return 0


def probe_game(payload, alog):
    """1試合ぶんの行動指標。payload[step] = その決定時点の観測（step は alog と共有）。"""
    m = Counter()
    sup_hand = {XEROSIC: [], ERI: [], BOSS: []}
    turns = {}          # turn -> list of (rec, state)
    for rec in alog:
        if rec["actor"] != "agent0":
            continue
        step = rec["step"]
        if step >= len(payload):
            continue
        cur = (payload[step].get("current") or {})
        if cur.get("turn") != rec["turn"]:
            continue                      # 整合しない稀ケースは捨てる（保守的）
        me, opp = cur["players"][0], cur["players"][1]
        turns.setdefault(rec["turn"], []).append((rec, cur))

        ids = sel_ids(rec)
        if rec["select_context"] == "MAIN":
            hand_ids = [c["id"] for c in (me.get("hand") or []) if c]
            if any(f"play Lillie" in s for s in rec["selected"]):
                hand = len(hand_ids)
                m["lillie_plays"] += 1
                m["lillie_net"] += hand - 9      # サイド6固定=8ドロー、山へ hand-1
                if hand < 9:
                    m["lillie_red"] += 1
                act_now = me["active"][0] if me["active"] else None
                mill_ok = (act_now is not None and act_now["id"] == COMFEY
                           and energy_n(act_now) >= 1)
                # [第23弾①] 山が厚いのに回復打ち。序盤テンポ(≤T3)と③のミル不能番は除外
                if me["deckCount"] >= 12 and rec["turn"] >= 4 and mill_ok:
                    m["lillie_slack"] += 1
            # [第23弾②] 進化先にバトル場を選んだ（ベンチに同じ進化元がいるのに）
            for s in rec["selected"]:
                if "evolve" in s and "target=ACTIVE" in s:
                    mm = ID_RE.search(s)
                    eid = int(mm.group(1)) if mm else 0
                    bench_ids = [pk["id"] for pk in me["bench"] if pk]
                    if (eid == LAMPENT and LITWICK in bench_ids) or \
                       (eid == CHAND and LAMPENT in bench_ids):
                        m["evolve_active_bad"] += 1
            if POFFIN in ids and any("play" in s for s in rec["selected"]):
                m["poffin_plays"] += 1
                field = [pk for pk in (me["active"] + me["bench"]) if pk]
                stock = sum(1 for pk in me["bench"] if pk and pk["id"] == COMFEY)
                line = sum(1 for pk in field if pk["id"] in (LITWICK, LAMPENT, CHAND))
                if stock >= 1 and line >= 2:
                    m["poffin_violation"] += 1
            for sid in (XEROSIC, ERI, BOSS):
                if sid in ids and any("play" in s for s in rec["selected"]):
                    sup_hand[sid].append(opp["handCount"])
                    if sid == BOSS and opp["handCount"] > 3 and XEROSIC in hand_ids:
                        m["boss_premature"] += 1
        if is_fs_attack(rec):
            m["fs_attacks"] += 1

    # 第19弾: 手番の先頭 MAIN で「前がヒトモシ/ランプラー ∧ エネ付きキュワワーがベンチ」
    for t, recs in turns.items():
        mains = [(r, c) for r, c in recs if r["select_context"] == "MAIN"]
        if not mains:
            continue
        _, cur0 = mains[0]
        me = cur0["players"][0]
        act = me["active"][0] if me["active"] else None
        fueled = any(pk and pk["id"] == COMFEY and energy_n(pk) >= 1
                     for pk in me["bench"])
        if act and act["id"] in (LITWICK, LAMPENT) and fueled:
            m["stuck_turns"] += 1
            if not any(is_fs_attack(r) for r, _ in recs):
                m["stuck_no_fs"] += 1
        # [第20弾] 非キュワワーが前 ∧ ベンチにキュワワー ∧ 入れ替えを手札に持っている
        hand0 = [c["id"] for c in (me.get("hand") or []) if c]
        bench_comfey = any(pk and pk["id"] == COMFEY for pk in me["bench"])
        if (act and act["id"] != COMFEY and bench_comfey
                and SWITCH_ITEM in hand0):
            m["switch_chance"] += 1
            used = any(SWITCH_ITEM in sel_ids(r) and any("play" in s for s in r["selected"])
                       for r, _ in recs)
            if not used:
                m["switch_held"] += 1
        # [第22弾] ボス以外のサポートを所持しながらサポート未使用でターン終了
        NONBOSS_SUP = {LILLIE, 1225, 1231, XEROSIC, ERI}   # Lillie/Hilda/Dawn/Xerosic/Eri
        ALL_SUP = NONBOSS_SUP | {BOSS}
        # 「打てば意味がある」= Hilda/Dawn は無条件・クセロシキは相手手札≥4・
        # ビワは相手手札≥1・リーリエは黒字（手札≥10）のみ。赤字リーリエ等の温存は正当。
        opp_hand_n = cur0["players"][1]["handCount"]
        actionable = (1225 in hand0 or 1231 in hand0
                      or (XEROSIC in hand0 and opp_hand_n >= 4)
                      or (ERI in hand0 and opp_hand_n >= 1)
                      or (LILLIE in hand0 and len(hand0) >= 10))
        if any(c in NONBOSS_SUP for c in hand0):
            m["sup_slot_turns"] += 1
            played_sup = any(
                any(sid in ALL_SUP for sid in sel_ids(r))
                and any("play" in s for s in r["selected"])
                for r, _ in recs)
            if not played_sup:
                m["sup_slot_idle"] += 1
                if actionable:
                    m["sup_slot_idle_bad"] += 1
        # [調査] 第16弾の使用条件（ベンチにキュワワー無し or ライン<2）を満たすのに
        # ポフィンを握ったままターンを終えた回数と、その原因の内訳
        field0 = [pk for pk in (me["active"] + me["bench"]) if pk]
        bench_ids0 = [pk["id"] for pk in me["bench"] if pk]
        line0 = sum(1 for pk in field0 if pk["id"] in (LITWICK, LAMPENT, CHAND))
        comfey0 = sum(1 for pk in field0 if pk["id"] == COMFEY)
        bench_free0 = 5 - len(bench_ids0)
        should_poffin = (POFFIN in hand0 and bench_free0 > 0
                         and (COMFEY not in bench_ids0 or line0 < 2))
        if should_poffin:
            m["poffin_due"] += 1
            played = any(POFFIN in sel_ids(r) and any("play" in s for s in r["selected"])
                         for r, _ in recs)
            if not played:
                m["poffin_missed"] += 1
                my_deck0 = me["deckCount"]
                opp_deck0 = cur0["players"][1]["deckCount"]
                chand_in_play = any(pk["id"] == CHAND for pk in field0)
                fueled_comfey = any(pk["id"] == COMFEY and energy_n(pk) >= 1
                                    for pk in field0)
                if my_deck0 <= 13 and opp_deck0 <= 10:
                    m["poffin_missed_lo"] += 1
                elif comfey0 >= 3 and line0 >= 3:
                    m["poffin_missed_saturated"] += 1
                elif chand_in_play and fueled_comfey and comfey0 >= 2:
                    m["poffin_missed_divc2"] += 1     # 交戦期 div-C2 温存の疑い
                else:
                    m["poffin_missed_other"] += 1
        # [第23弾③] ミルできない番（前が燃料付きキュワワーでない）に妨害を優先した
        act0 = me["active"][0] if me["active"] else None
        can_mill = (act0 is not None and act0["id"] == COMFEY
                    and energy_n(act0) >= 1)
        if not can_mill and LILLIE in hand0:
            played_disrupt = any(
                any(sid in (XEROSIC, ERI) for sid in sel_ids(r))
                and any("play" in s for s in r["selected"]) for r, _ in recs)
            played_lillie = any(
                any("play Lillie" in s for s in r["selected"]) for r, _ in recs)
            if played_disrupt and not played_lillie:
                m["nofs_disrupt_bad"] += 1
        # [第21弾] 相手サイド≤2 ∧ NZ を手札に所持 ∧ スタジアムが NZ でない
        opp0 = cur0["players"][1]
        opp_prize = len(opp0.get("prize") or [])
        stadium = [c["id"] for c in (cur0.get("stadium") or []) if c]
        if (opp_prize <= 2 and NEUTRAL_ZONE in hand0
                and NEUTRAL_ZONE not in stadium):
            m["nz_chance"] += 1
            used = any(NEUTRAL_ZONE in sel_ids(r) and any("play" in s for s in r["selected"])
                       for r, _ in recs)
            if not used:
                m["nz_held"] += 1

    last = payload[-1].get("current") or {}
    if last.get("players"):
        m["end_my_deck"] = last["players"][0]["deckCount"]
        m["end_opp_deck"] = last["players"][1]["deckCount"]
    return m, sup_hand


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", default="agents/chandelure_rb")
    ap.add_argument("--deck", default="decks/fleet/chandelure_top.csv")
    ap.add_argument("--opponent", default="crustle_wall", choices=sorted(OPP_AGENT))
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--env", action="append", default=[],
                    help="KEY=VAL（エージェント import 前に設定。繰り返し可）")
    args = ap.parse_args()

    for kv in args.env:
        k, _, v = kv.partition("=")
        os.environ[k] = v

    from export_visualizer_json import load_agent, read_deck, run_game  # noqa: E402
    from ab_battle import reset_agent                                   # noqa: E402

    opp_dir, opp_deck_path = OPP_AGENT[args.opponent]
    a0 = load_agent(ROOT / args.agent, "probe_agent0")
    a1 = load_agent(ROOT / opp_dir, "probe_agent1")
    d0 = read_deck(ROOT / args.deck)
    d1 = read_deck(ROOT / opp_deck_path)

    total = Counter()
    sup_all = {XEROSIC: [], ERI: [], BOSS: []}
    wins = games = 0
    end_my, end_opp = [], []
    for _ in range(args.games):
        reset_agent(a0)
        reset_agent(a1)
        try:
            payload, meta, alog = run_game(a0, a1, list(d0), list(d1), 1000)
        except Exception as exc:                                        # noqa: BLE001
            print(f"  skip ({type(exc).__name__}: {exc})")
            continue
        games += 1
        wins += 1 if meta["result"] == 0 else 0
        m, sup = probe_game(payload, alog)
        end_my.append(m.pop("end_my_deck", 0))
        end_opp.append(m.pop("end_opp_deck", 0))
        total.update(m)
        for k in sup_all:
            sup_all[k].extend(sup[k])

    g = max(1, games)
    env_note = " ".join(args.env) or "(既定)"
    print(f"=== behavior probe: {args.agent} vs {args.opponent} "
          f"{games}戦 {wins}勝 ({wins/g:.0%})  env: {env_note} ===")
    print(f"[第16弾] Lillie : {total['lillie_plays']/g:.2f}回/戦  "
          f"赤字 {total['lillie_red']/g:.2f}回/戦  山の正味 {total['lillie_net']/g:+.1f}枚/戦")
    print(f"[第16弾] Poffin : {total['poffin_plays']/g:.2f}回/戦  "
          f"違反(在庫あり打ち) {total['poffin_violation']/g:.2f}回/戦")
    for sid, name in ((XEROSIC, "クセロシキ"), (ERI, "ビワ"), (BOSS, "ボス")):
        v = sup_all[sid]
        avg = sum(v) / len(v) if v else float("nan")
        print(f"[第18弾] {name:<6}: {len(v)/g:.2f}回/戦  使用時の相手手札 平均 {avg:.1f}枚")
    print(f"[第18弾] 早すぎるボス(相手手札>3∧クセロシキ温存中): {total['boss_premature']/g:.2f}回/戦")
    print(f"[第19弾] 前詰まりターン: {total['stuck_turns']/g:.2f}回/戦  "
          f"うちFS撃てず(丸損) {total['stuck_no_fs']/g:.2f}回/戦")
    print(f"[第20弾] 入替可能ターン(非キュワワー前∧入替所持): {total['switch_chance']/g:.2f}回/戦  "
          f"うち握ったまま終了 {total['switch_held']/g:.2f}回/戦")
    print(f"[第21弾] NZ張り時(相手サイド≤2∧NZ所持): {total['nz_chance']/g:.2f}回/戦  "
          f"うち握ったまま終了 {total['nz_held']/g:.2f}回/戦")
    print(f"[第22弾] サポ所持ターン(ボス以外): {total['sup_slot_turns']/g:.2f}回/戦  "
          f"うち未使用で終了 {total['sup_slot_idle']/g:.2f}回/戦  "
          f"うち不当な温存 {total['sup_slot_idle_bad']/g:.2f}回/戦")
    print(f"[第23弾] 山厚(≥12)でのリーリエ回復: {total['lillie_slack']/g:.2f}回/戦  "
          f"前を進化(ベンチに進化元あり): {total['evolve_active_bad']/g:.2f}回/戦  "
          f"ミル不能番に妨害優先: {total['nofs_disrupt_bad']/g:.2f}回/戦")
    print(f"[調査]   打つべきポフィン所持ターン: {total['poffin_due']/g:.2f}回/戦  "
          f"うち握ったまま終了 {total['poffin_missed']/g:.2f}回/戦  "
          f"(LO {total['poffin_missed_lo']/g:.2f} / 飽和 {total['poffin_missed_saturated']/g:.2f} / "
          f"div-C2疑い {total['poffin_missed_divc2']/g:.2f} / 他 {total['poffin_missed_other']/g:.2f})")
    print(f"[全般]   FS: {total['fs_attacks']/g:.1f}回/戦  "
          f"終局 自山 {sum(end_my)/g:.1f} / 相手山 {sum(end_opp)/g:.1f}")


if __name__ == "__main__":
    main()
