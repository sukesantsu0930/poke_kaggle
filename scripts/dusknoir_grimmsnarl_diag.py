"""対オーロンゲ（マリィのオーロンゲex）敗因診断（2026-07-26）。

最悪対面 marnie 21% の負け筋を「誰にサイドを取られ、誰を取れなかったか」に分解する。
盤面スナップショットの差分でKOを検出する（エンジンに KO ログ型が無いため）:
  相手のサイド残が減った瞬間 = こちらのポケモンが気絶した = 消えた自軍IDを記録
  自分のサイド残が減った瞬間 = 相手のポケモンが気絶した = 消えた相手IDを記録
自壊（カーズドボム）も「相手のサイド残が減る」ので、ボム発火ターンを別途記録して切り分ける。

使い方: python scripts/dusknoir_grimmsnarl_diag.py --games 60
"""
import argparse
import io
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in ["scripts", "submission", "agents/_base"]:
    sys.path.insert(0, str(ROOT / p))

from ab_battle import load_agent, read_deck, reset_agent, get_policy  # noqa: E402
from gauntlet import read_field, build_opponent                      # noqa: E402
from cg import api, game as cg_game                                  # noqa: E402
from cg.api import LogType                                           # noqa: E402

AGENT_DIR = ROOT / "agents/dragapult_dusknoir_rb"
DECK = ROOT / "decks/fleet/dragapult_dusknoir_paper.csv"
FIELD = ROOT / "research/meta/2026-07-20_uniform_field.csv"

DREEPY, DRAKLOAK, DRAGAPULT_EX = 119, 120, 121
DUSKULL, DUSCLOPS, DUSKNOIR = 131, 132, 133
MUNKIDORI, FEZANDIPITI, MEOWTH, BUDEW = 112, 140, 1071, 235
IMPIDIMP, MORGREM, GRIMMSNARL = 646, 647, 648
ATK_PHANTOM_DIVE = 154
ATK_ITCHY_POLLEN = 323

NAMES = {DREEPY: "ドラメシヤ", DRAKLOAK: "ドロンチ", DRAGAPULT_EX: "ドラパルトex",
         DUSKULL: "ヨマワル", DUSCLOPS: "サマヨール", DUSKNOIR: "ヨノワール",
         MUNKIDORI: "マシマシラ", FEZANDIPITI: "キチキギスex", MEOWTH: "ニャースex",
         BUDEW: "スボミー", IMPIDIMP: "マリィのベロバー", MORGREM: "マリィのギモー",
         GRIMMSNARL: "オーロンゲex", 305: "ノコッチ", 66: "ノココッチ", 649: "マリィのモルペコ"}


CARD_NAMES = {}
try:
    import csv as _csv
    with io.open(str(ROOT / "JP_Card_Data.csv"), encoding="utf-8") as _f:
        for _r in _csv.DictReader(_f):
            CARD_NAMES.setdefault(int(_r["カード ID"]), _r["カード名"])
except Exception:
    pass


def board_ids(player):
    return Counter(pk.id for pk in (list(player.active or []) + list(player.bench or []))
                   if pk is not None)


def snapshot(player):
    """場のポケモンを (最上段 serial → id) と『進化元として吸収された serial 集合』で持つ。

    サイド枚数の増減と盤面の更新はエンジン上で同一ステップに来ない（KO 解決 → 次の観測で
    サイド取得）ため、サイド差分に同期した盤面差分では KO を取り逃す。よって盤面側だけを
    見て「最上段 serial が場から消え、かつ誰かの進化元にもなっていない」＝場を離れた＝KO
    として検出する（進化は old serial が新しい最上段の preEvolution に入るので除外される）。"""
    tops, pre = {}, set()
    for pk in (list(player.active or []) + list(player.bench or [])):
        if pk is None:
            continue
        tops[pk.serial] = pk.id
        for c in (pk.preEvolution or []):
            if c is not None:
                pre.add(c.serial)
    return tops, pre


def gone_from_board(prev, cur):
    """前スナップショット→現スナップショットで場を離れた最上段の id リスト。"""
    prev_tops, _ = prev
    cur_tops, cur_pre = cur
    return [cid for serial, cid in prev_tops.items()
            if serial not in cur_tops and serial not in cur_pre]


def run(games, seat, our_deck, opp_row, max_steps, agent_dir=None):
    mod = load_agent(agent_dir or AGENT_DIR)
    opp_mod, opp_deck = build_opponent(opp_row)
    policy = get_policy(mod)
    agg = Counter()
    ko_by_opp = Counter()      # 相手に取られた自軍
    ko_by_us = Counter()       # こちらが取った相手
    bomb_targets = Counter()
    plays = Counter()          # (自/相, cardId) → 使用回数
    prizes_taken = Counter()   # 自分/相手が取ったサイド総数
    dive_turns, grim_land_turns, end_turns = [], [], []
    loss_prizes = []           # 負け試合で自分が取れていたサイド枚数

    for g in range(games):
        reset_agent(mod)
        reset_agent(opp_mod)
        decks = (our_deck, opp_deck) if seat == 0 else (opp_deck, our_deck)
        obs, _ = cg_game.battle_start(list(decks[0]), list(decks[1]))
        if obs is None:
            continue
        prev = None
        first_dive = None
        grim_land = None
        bombs = 0
        result = None
        try:
            for _ in range(max_steps):
                typed = api.to_observation_class(obs)
                cur = typed.current
                if cur is None:
                    break
                if cur.result != -1:
                    result = cur.result
                    break
                me, opp = cur.players[seat], cur.players[1 - seat]
                turn = getattr(cur, "turn", -1)
                snap = (snapshot(me), snapshot(opp), len(me.prize), len(opp.prize))
                if prev is not None:
                    for cid in gone_from_board(prev[0], snap[0]):
                        ko_by_opp[cid] += 1          # 自軍が場を離れた（KO・自壊）
                    for cid in gone_from_board(prev[1], snap[1]):
                        ko_by_us[cid] += 1           # 相手が場を離れた（＝こちらが取った）
                prev = snap
                if grim_land is None and GRIMMSNARL in snap[1][0].values():
                    grim_land = turn

                if cur.yourIndex == seat:
                    policy.decision_log = []
                    action = mod.agent(obs)
                    for rec in (policy.decision_log or []):
                        sel = rec.get("selected") or []
                        reason = next((o["reason"] for o in rec["options"]
                                       if sel and o["i"] == sel[0]), "")
                        if "Cursed Blast" in reason and "hold" not in reason:
                            bombs += 1
                            bp = getattr(policy, "bomb_plan", None) or {}
                            cards = ([opp.active[0]] if opp.active else [None]) + list(opp.bench)
                            i = bp.get("coord", -1)
                            tgt = cards[i] if 0 <= i < len(cards) and cards[i] else None
                            bomb_targets[(bp.get("mode"), tgt.id if tgt else None)] += 1
                    policy.decision_log = None
                else:
                    action = opp_mod.agent(obs)
                for log in (typed.logs or []):
                    if log.type == LogType.ATTACK and log.attackId == ATK_PHANTOM_DIVE:
                        agg["dive_atk"] += 1
                        if first_dive is None:
                            first_dive = turn
                    if log.type == LogType.ATTACK and log.attackId == ATK_ITCHY_POLLEN:
                        agg["itchy_atk"] += 1
                    if log.type == LogType.PLAY:
                        who = "自" if getattr(log, "playerIndex", -1) == seat else "相"
                        plays[(who, getattr(log, "cardId", -1))] += 1
                obs = cg_game.battle_select(action)
            end_turns.append(turn)
        finally:
            try:
                cg_game.battle_finish()
            except Exception:
                pass

        agg["games"] += 1
        won = (result == seat)
        agg["wins"] += 1 if won else 0
        agg["bombs"] += bombs
        if first_dive:
            agg["dive_games"] += 1
            dive_turns.append(first_dive)
        if grim_land:
            grim_land_turns.append(grim_land)
        if prev is not None:
            prizes_taken["自"] += 6 - prev[2]
            prizes_taken["相"] += 6 - prev[3]
            if not won:
                loss_prizes.append(6 - prev[2])
        grim_ko_now = ko_by_us.get(GRIMMSNARL, 0)
        if grim_ko_now > agg["grim_ko_prev"]:
            agg["grim_ko_games"] += 1
        agg["grim_ko_prev"] = grim_ko_now

    return (agg, ko_by_opp, ko_by_us, plays, dive_turns, grim_land_turns,
            end_turns, loss_prizes, prizes_taken, bomb_targets)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--games", type=int, default=40, help="1席あたりの試合数")
    ap.add_argument("--opponent", default="marnie")
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--agent", default=str(AGENT_DIR), help="対象エージェントdir")
    ap.add_argument("--deck", default=str(DECK), help="対象デッキCSV")
    args = ap.parse_args()

    our_deck = read_deck(Path(args.deck))
    row = {r["archetype"]: r for r in read_field(FIELD)}[args.opponent]

    tot = Counter()
    ko_opp, ko_us, plays, prizes = Counter(), Counter(), Counter(), Counter()
    bombs = Counter()
    dives, lands, ends, lossp = [], [], [], []
    for seat in (0, 1):
        a, ko, kou, pl, d, gl, et, lp, pz, bt = run(args.games, seat, our_deck, row,
                                                    args.max_steps, Path(args.agent))
        tot.update(a); ko_opp.update(ko); ko_us.update(kou)
        plays.update(pl); prizes.update(pz); bombs.update(bt)
        dives += d; lands += gl; ends += et; lossp += lp

    n = tot["games"] or 1
    print(f"=== {Path(args.agent).name} vs {args.opponent}（{tot['games']}戦・両席）===")
    print(f"勝率 {tot['wins']}/{tot['games']} = {tot['wins']/n:.1%}   平均決着ターン T{sum(ends)/max(1,len(ends)):.1f}")
    print(f"ダイブ到達 {tot['dive_games']/n:.0%}（平均初回 T{sum(dives)/max(1,len(dives)):.1f}）  "
          f"ボム発火 {tot['bombs']/n:.2f}/試合")
    print(f"攻撃回数: ファントムダイブ {tot['dive_atk']/2/n:.2f}/試合  "
          f"むずむずかふん {tot['itchy_atk']/2/n:.2f}/試合")
    print(f"相手オーロンゲex 着地 T{sum(lands)/max(1,len(lands)):.1f}（{len(lands)}/{tot['games']}試合）")
    print(f"オーロンゲex を取れた試合: {tot['grim_ko_games']}/{tot['games']} = {tot['grim_ko_games']/n:.0%}")
    if lossp:
        print(f"負け試合の自分のサイド取得数: 平均 {sum(lossp)/len(lossp):.2f}枚  "
              f"分布 {dict(sorted(Counter(lossp).items()))}")
    print("\n--- 相手に取られた自軍（サイド献上の内訳・自壊込み） ---")
    for cid, c in ko_opp.most_common():
        print(f"  {NAMES.get(cid, cid):<12} {c:>4}回  ({c/n:.2f}/試合)")
    print("\n--- こちらが取った相手（※ノココッチは にげあしドロー の自主帰還を含む） ---")
    for cid, c in ko_us.most_common():
        print(f"  {NAMES.get(cid, cid):<12} {c:>4}回  ({c/n:.2f}/試合)")
    print(f"\nサイド取得総数: 自 {prizes['自']/n:.2f}/試合 / 相 {prizes['相']/n:.2f}/試合")
    print("\n--- カーズドボムの照準（mode1=単体で取り切り / 2=正面200と合算 / 3=ばら撒き60と合算） ---")
    for (mode, cid), c in sorted(bombs.items(), key=lambda kv: -kv[1]):
        print(f"  mode{mode} → {NAMES.get(cid, cid):<12} {c:>4}回  ({c/n:.2f}/試合)")
    print("\n--- カード使用回数（/試合、0.10以上） ---")
    for (who, cid), c in sorted(plays.items(), key=lambda kv: -kv[1]):
        if c / n < 0.10:
            continue
        print(f"  [{who}] {CARD_NAMES.get(cid, cid):<22} {c/n:.2f}")


if __name__ == "__main__":
    main()
