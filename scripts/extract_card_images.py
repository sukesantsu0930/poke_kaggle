import argparse
import csv
import json
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "Card_ID List_JP.pdf"
DEFAULT_CSV = ROOT / "JP_Card_Data.csv"
DEFAULT_OUTPUT = ROOT / "card_images" / "jp"


def load_card_ids(csv_path: Path) -> list[int]:
    ids = set()
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            ids.add(int(row["カード ID"]))
    return sorted(ids)


def extract_images(pdf_path: Path, card_ids: list[int], output_dir: Path, limit: int | None = None):
    output_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    manifest = {}
    exported = 0
    skipped = 0

    for card_id in card_ids:
        if limit is not None and exported >= limit:
            break
        page_index = card_id + 38
        if page_index >= doc.page_count:
            print(f"NG card_id={card_id}: PDF page is out of range")
            skipped += 1
            continue

        page = doc[page_index]
        images = page.get_images(full=True)
        if not images:
            print(f"NG card_id={card_id}: image not found on page {page_index + 1}")
            skipped += 1
            continue

        xref = images[0][0]
        image = doc.extract_image(xref)
        ext = "jpg" if image.get("ext") == "jpeg" else image.get("ext", "png")
        out_path = output_dir / f"{card_id}.{ext}"
        out_path.write_bytes(image["image"])
        manifest[str(card_id)] = out_path.name
        exported += 1

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return exported, skipped, output_dir / "manifest.json"


def main():
    parser = argparse.ArgumentParser(description="Card_ID List_JP.pdfからカード画像を抽出します。")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF))
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--limit", type=int, help="動作確認用。先頭N件だけ抽出します。")
    args = parser.parse_args()

    card_ids = load_card_ids(Path(args.csv))
    exported, skipped, manifest = extract_images(
        Path(args.pdf),
        card_ids,
        Path(args.output_dir),
        args.limit,
    )
    print(f"OK exported={exported} skipped={skipped} manifest={manifest}")


if __name__ == "__main__":
    main()
