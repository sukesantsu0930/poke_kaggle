import argparse
import csv
import html
import os
import re
from collections import Counter
from pathlib import Path

from deck_validation import validate_deck_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARD_DATA = ROOT / "JP_Card_Data.csv"
DEFAULT_IMAGE_DIR = ROOT / "card_images" / "jp"
DEFAULT_OUTPUT_DIR = ROOT / "experiments" / "deck_views"


def read_deck(path: Path) -> list[int]:
    deck = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        value = raw.strip()
        if not value:
            continue
        try:
            deck.append(int(value))
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: card ID is not an integer: {value!r}") from exc
    return deck


def load_card_rows(path: Path) -> dict[int, dict[str, str]]:
    rows = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            card_id = int(row["カード ID"])
            rows.setdefault(card_id, row)
    return rows


def safe_stem(path: Path) -> str:
    stem = re.sub(r"[^0-9A-Za-z_.-]+", "_", path.stem).strip("_")
    return stem or "deck"


def card_kind(row: dict[str, str] | None) -> str:
    if row is None:
        return "不明"
    raw = row.get("ポケモンの進化の段階/エネルギー・トレーナーズの種類", "")
    category = row.get("カテゴリ", "")
    if "エネルギー" in raw:
        return "エネルギー"
    if raw.startswith("ポケモン/") or category == "ポケモン":
        return "ポケモン"
    return "トレーナーズ"


def kind_order(kind: str) -> int:
    return {"ポケモン": 0, "トレーナーズ": 1, "エネルギー": 2, "不明": 3}.get(kind, 9)


def image_src(card_id: int, image_dir: Path, output_path: Path) -> str | None:
    for ext in ("jpg", "png", "jpeg", "webp"):
        path = image_dir / f"{card_id}.{ext}"
        if path.exists():
            return Path(os.path.relpath(path, output_path.parent)).as_posix()
    return None


def card_label(card_id: int, row: dict[str, str] | None) -> str:
    if row is None:
        return f"ID {card_id}"
    return row.get("カード名") or f"ID {card_id}"


def detail_text(row: dict[str, str] | None) -> str:
    if row is None:
        return "カードデータなし"
    parts = []
    kind = row.get("ポケモンの進化の段階/エネルギー・トレーナーズの種類", "")
    hp = row.get("HP", "")
    card_type = row.get("タイプ", "")
    expansion = row.get("エキスパンションマーク", "")
    number = row.get("コレクション番号", "")
    if kind and kind != "n/a":
        parts.append(kind)
    if card_type and card_type != "n/a":
        parts.append(card_type)
    if hp and hp != "n/a":
        parts.append(f"HP {hp}")
    if expansion and expansion != "n/a":
        parts.append(expansion)
    if number and number != "n/a":
        parts.append(number)
    return " / ".join(parts) if parts else "n/a"


def render_card(card_id: int, count: int, row: dict[str, str] | None, image_dir: Path, output_path: Path) -> str:
    name = html.escape(card_label(card_id, row))
    detail = html.escape(detail_text(row))
    src = image_src(card_id, image_dir, output_path)
    if src:
        image = f'<img src="{html.escape(src)}" alt="{name}">'
    else:
        image = f'<div class="missing-image">画像なし<br>ID {card_id}</div>'
    return f"""
      <article class="card">
        <div class="image-wrap">
          {image}
          <div class="count">x{count}</div>
        </div>
        <div class="card-name">{name}</div>
        <div class="meta">ID {card_id}</div>
        <div class="meta">{detail}</div>
      </article>
    """


def section_html(
    title: str,
    items: list[tuple[int, int]],
    rows: dict[int, dict[str, str]],
    image_dir: Path,
    output_path: Path,
) -> str:
    if not items:
        return ""
    total = sum(count for _, count in items)
    cards = "\n".join(
        render_card(card_id, count, rows.get(card_id), image_dir, output_path)
        for card_id, count in items
    )
    return f"""
    <section>
      <h2>{html.escape(title)} <span>{total}枚 / {len(items)}種</span></h2>
      <div class="grid">
        {cards}
      </div>
    </section>
    """


def build_html(deck_path: Path, output_path: Path, card_data: Path, image_dir: Path) -> Path:
    deck = read_deck(deck_path)
    validation = validate_deck_file(deck_path)
    rows = load_card_rows(card_data)
    counts = Counter(deck)

    grouped: dict[str, list[tuple[int, int]]] = {
        "ポケモン": [],
        "トレーナーズ": [],
        "エネルギー": [],
        "不明": [],
    }
    for card_id, count in counts.items():
        grouped.setdefault(card_kind(rows.get(card_id)), []).append((card_id, count))

    def sort_key(item: tuple[int, int]):
        card_id, count = item
        row = rows.get(card_id)
        return (
            kind_order(card_kind(row)),
            row.get("ポケモンの進化の段階/エネルギー・トレーナーズの種類", "") if row else "",
            card_label(card_id, row),
            card_id,
            -count,
        )

    for items in grouped.values():
        items.sort(key=sort_key)

    status_class = "ok" if validation.ok else "ng"
    status_text = "OK" if validation.ok else "NG"
    messages = validation.errors + validation.warnings
    message_html = ""
    if messages:
        message_html = "<ul>" + "".join(f"<li>{html.escape(message)}</li>" for message in messages) + "</ul>"

    section_blocks = "\n".join(
        section_html(title, grouped.get(title, []), rows, image_dir, output_path)
        for title in ("ポケモン", "トレーナーズ", "エネルギー", "不明")
    )

    source = html.escape(str(deck_path))
    body = f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(deck_path.stem)} deck view</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f5f7;
      --panel: #ffffff;
      --line: #d9dee7;
      --text: #16202d;
      --muted: #5e6a7a;
      --accent: #1f6feb;
      --danger: #b42318;
      --ok: #137333;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: "Segoe UI", "Meiryo", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(244, 245, 247, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(8px);
    }}
    .header-inner {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 16px 20px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 24px;
      line-height: 1.25;
    }}
    .source {{
      color: var(--muted);
      font-size: 13px;
      word-break: break-all;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 4px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel);
      font-size: 13px;
      font-weight: 600;
    }}
    .pill.ok {{ color: var(--ok); border-color: #b7dfc2; }}
    .pill.ng {{ color: var(--danger); border-color: #f1b7b0; }}
    main {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 20px;
    }}
    section {{
      margin: 0 0 28px;
    }}
    h2 {{
      display: flex;
      align-items: baseline;
      gap: 10px;
      margin: 0 0 12px;
      font-size: 20px;
    }}
    h2 span {{
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(132px, 1fr));
      gap: 12px;
    }}
    .card {{
      min-width: 0;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 8px;
      box-shadow: 0 1px 2px rgba(12, 18, 28, 0.06);
    }}
    .image-wrap {{
      position: relative;
      width: 100%;
      aspect-ratio: 63 / 88;
      background: #e8ebf0;
      border-radius: 6px;
      overflow: hidden;
    }}
    img {{
      display: block;
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    .count {{
      position: absolute;
      right: 6px;
      top: 6px;
      min-width: 34px;
      padding: 3px 7px;
      border-radius: 999px;
      background: rgba(22, 32, 45, 0.88);
      color: white;
      font-size: 15px;
      font-weight: 800;
      text-align: center;
    }}
    .card-name {{
      margin-top: 8px;
      font-size: 14px;
      font-weight: 700;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .meta {{
      margin-top: 3px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
      overflow-wrap: anywhere;
    }}
    .missing-image {{
      display: grid;
      place-items: center;
      height: 100%;
      color: var(--muted);
      font-size: 13px;
      text-align: center;
      line-height: 1.5;
    }}
    .messages {{
      margin-top: 12px;
      color: var(--danger);
      font-size: 13px;
    }}
    .messages ul {{
      margin: 6px 0 0;
      padding-left: 20px;
    }}
  </style>
</head>
<body>
  <header>
    <div class="header-inner">
      <h1>{html.escape(deck_path.stem)}</h1>
      <div class="source">{source}</div>
      <div class="summary">
        <span class="pill {status_class}">検証 {status_text}</span>
        <span class="pill">合計 {len(deck)}枚</span>
        <span class="pill">ポケモン {sum(count for _, count in grouped["ポケモン"])}枚</span>
        <span class="pill">トレーナーズ {sum(count for _, count in grouped["トレーナーズ"])}枚</span>
        <span class="pill">エネルギー {sum(count for _, count in grouped["エネルギー"])}枚</span>
        <span class="pill">ユニーク {len(counts)}種</span>
        <span class="pill">たね {validation.basic_pokemon_count}枚</span>
      </div>
      <div class="messages">{message_html}</div>
    </div>
  </header>
  <main>
    {section_blocks}
  </main>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(body, encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="deck CSV をローカル画像つきHTMLに可視化します。")
    parser.add_argument("deck_csv", help="可視化する deck CSV")
    parser.add_argument("--card-data", default=str(DEFAULT_CARD_DATA))
    parser.add_argument("--image-dir", default=str(DEFAULT_IMAGE_DIR))
    parser.add_argument("--output", help="出力HTML。省略時は experiments/deck_views/<deck名>.html")
    parser.add_argument("--open", action="store_true", help="生成後に既定ブラウザで開きます。")
    args = parser.parse_args()

    deck_path = Path(args.deck_csv)
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"{safe_stem(deck_path)}.html"
    built = build_html(
        deck_path,
        output_path,
        Path(args.card_data),
        Path(args.image_dir),
    )
    print(built)
    if args.open:
        os.startfile(str(built.resolve()))


if __name__ == "__main__":
    main()
