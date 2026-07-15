"""オープン対戦履歴から「アタッカーとして運用されるポケモン」を抽出する（P-02 の知識形成）。

ドラパルトの Phantom Dive 配分探索は、相手ベンチのポケモンが「バトル場に出て正面200を
受けに来るアタッカーか、ベンチ常駐の置物か」で振り分ける。この判定はカードDBの技スペック
だけでは決まらない（Solrock/Fan Rotom は技があるが置物、Fezandipiti は damage=0 だが狙撃）。
そこで実対戦で「active に居るあいだに ATTACK（技宣言）を選んだか」を集計し、実運用の
アタッカー度を測る。

アタッカー度 = ATTACK を宣言した (episode, player) 数 / active に出た (episode, player) 数
2値化: 自動閾値（既定 0.5）以上をアタッカーとする。対象は HP>120 のポケモンのみ
（HP<=120 は「ばら撒き2発で取り切れる」ので役割判定が不要 — 設計 md 参照）。

使い方:
  uv run python scripts\\extract_attacker_pokemon.py --episodes downloads\\episodes ^
      [--hp-min 121] [--threshold 0.5] [--min-appear 5] ^
      [--out-md research\\meta\\attacker_pokemon.md] [--out-csv research\\meta\\attacker_pokemon.csv]

注: エピソードの steps[t][pi].observation への答えは steps[t+1][pi].action（off-by-one）。
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "submission"))

from cg.api import OptionType, all_card_data, to_observation_class  # noqa: E402

CARD = {c.cardId: c for c in all_card_data()}


def card_name(cid: int) -> str:
    c = CARD.get(cid)
    return c.name if c is not None else f"id{cid}"


def active_pokemon_id(obs, pi: int) -> int | None:
    """その手番の自分（pi）のバトル場ポケモンの id。"""
    try:
        active = obs.current.players[pi].active
    except Exception:
        return None
    if active and active[0] is not None:
        return active[0].id
    return None


def chose_attack(obs, action) -> bool:
    """action に ATTACK オプションが含まれるか。"""
    sel = obs.select
    if sel is None or not sel.option or not isinstance(action, list):
        return False
    for i in action:
        if 0 <= i < len(sel.option) and sel.option[i].type == OptionType.ATTACK:
            return True
    return False


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", required=True,
                    help="エピソードJSONのルート（サブディレクトリも再帰）")
    ap.add_argument("--hp-min", type=int, default=121,
                    help="この HP 以上のポケモンだけ集計（既定121 = 120超）")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="アタッカー度の2値化閾値（既定0.5）")
    ap.add_argument("--min-appear", type=int, default=5,
                    help="この試合数以上 active に出たポケモンだけ判定（既定5）")
    ap.add_argument("--out-md", default="research/meta/attacker_pokemon.md")
    ap.add_argument("--out-csv", default="research/meta/attacker_pokemon.csv")
    args = ap.parse_args()

    # (pokemon_id) -> {"appear": set((ep,pi)), "attack": set((ep,pi))}
    appear: dict[int, set] = defaultdict(set)
    attack: dict[int, set] = defaultdict(set)

    files = sorted(glob.glob(str(ROOT / args.episodes / "**" / "*.json"), recursive=True))
    n_ep = 0
    for fp in files:
        try:
            ep = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        steps = ep.get("steps", [])
        if len(steps) < 3:
            continue
        n_ep += 1
        ep_id = Path(fp).stem
        for pi in (0, 1):
            for t in range(1, len(steps) - 1):
                try:
                    if steps[t][pi].get("status") != "ACTIVE":
                        continue
                    od = steps[t][pi].get("observation")
                    if not od or not od.get("select"):
                        continue
                    action = steps[t + 1][pi].get("action")
                    if not isinstance(action, list):
                        continue
                    obs = to_observation_class(od)
                    aid = active_pokemon_id(obs, pi)
                    if aid is None:
                        continue
                    key = (ep_id, pi)
                    appear[aid].add(key)
                    if chose_attack(obs, action):
                        attack[aid].add(key)
                except Exception:
                    continue

    # 集計 → HP>hp_min のみ・出現閾値以上
    rows = []
    for cid, ap_set in appear.items():
        card = CARD.get(cid)
        hp = getattr(card, "hp", 0) if card is not None else 0
        if hp < args.hp_min:
            continue
        n_appear = len(ap_set)
        if n_appear < args.min_appear:
            continue
        n_attack = len(attack.get(cid, ()))
        rate = n_attack / n_appear if n_appear else 0.0
        rows.append({
            "id": cid, "name": card_name(cid), "hp": hp,
            "appear": n_appear, "attack": n_attack,
            "rate": round(rate, 3),
            "attacker": int(rate >= args.threshold),
        })
    rows.sort(key=lambda r: (-r["attacker"], -r["rate"], -r["appear"]))

    attacker_ids = [r["id"] for r in rows if r["attacker"]]

    out_csv = ROOT / args.out_csv
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "hp", "appear", "attack",
                                          "rate", "attacker"])
        w.writeheader()
        w.writerows(rows)

    lines = [
        "# アタッカー運用ポケモン（対戦履歴からの実測。extract_attacker_pokemon.py 生成）",
        "",
        f"- データ源: `{args.episodes}`（{n_ep} エピソード）",
        f"- 対象: HP >= {args.hp_min} かつ active 出現 >= {args.min_appear} 試合",
        f"- アタッカー度 = ATTACK宣言試合数 / active出現試合数、閾値 {args.threshold} で2値化",
        f"- アタッカー判定 = {len(attacker_ids)} 種 / 集計対象 {len(rows)} 種",
        "",
        "## ATTACKER_IDS_LEARNED（agent が読む集合）",
        "",
        "```python",
        f"ATTACKER_IDS_LEARNED = {{{', '.join(str(i) for i in sorted(attacker_ids))}}}",
        "```",
        "",
        "## 全集計（アタッカー度降順）",
        "",
        "| id | name | HP | 出現 | 攻撃 | 度 | アタッカー |",
        "|---:|---|---:|---:|---:|---:|:---:|",
    ]
    for r in rows:
        mark = "✓" if r["attacker"] else ""
        lines.append(f"| {r['id']} | {r['name']} | {r['hp']} | {r['appear']} | "
                     f"{r['attack']} | {r['rate']:.2f} | {mark} |")
    out_md = ROOT / args.out_md
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"episodes={n_ep}  集計対象={len(rows)}種  アタッカー判定={len(attacker_ids)}種")
    print(f"-> {out_csv}")
    print(f"-> {out_md}")
    print("\nATTACKER_IDS_LEARNED =", "{" + ", ".join(str(i) for i in sorted(attacker_ids)) + "}")


if __name__ == "__main__":
    main()
