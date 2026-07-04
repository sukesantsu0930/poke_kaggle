import argparse
import csv
import html
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from deck_validation import validate_deck_ids


ROOT = Path(__file__).resolve().parents[1]
JP_CARD_DATA = ROOT / "JP_Card_Data.csv"
OFFICIAL_DECK_URL = "https://www.pokemon-card.com/deck/confirm.html/deckID/{code}/"

DECK_FIELDS = (
    "deck_pke",
    "deck_gds",
    "deck_tool",
    "deck_tech",
    "deck_sup",
    "deck_sta",
    "deck_ene",
    "deck_ajs",
)

BASIC_ENERGY_BY_NAME = {
    "基本草エネルギー": 1,
    "基本炎エネルギー": 2,
    "基本水エネルギー": 3,
    "基本雷エネルギー": 4,
    "基本超エネルギー": 5,
    "基本闘エネルギー": 6,
    "基本悪エネルギー": 7,
    "基本鋼エネルギー": 8,
}

# Some cards in the Kaggle JP card CSV use competition/internal expansion marks
# that differ from the official card image and deck page notation.
# Keep these as narrow print-level aliases so same-name cards stay unambiguous.
PRINT_ALIASES = {
    ("シェイミ", "SV9A", "6"): ("シェイミ", "MA", "1"),
}


@dataclass(frozen=True)
class OfficialCard:
    official_id: int
    name: str
    expansion: str | None
    collection_no: str | None
    count: int


@dataclass(frozen=True)
class KaggleCard:
    card_id: int
    name: str
    expansion: str
    collection_no: str


class DeckCodeCompileError(Exception):
    def __init__(self, stage: str, errors: list[str], warnings: list[str] | None = None):
        super().__init__("\n".join(errors))
        self.stage = stage
        self.errors = errors
        self.warnings = warnings or []


def normalize_name(value: str) -> str:
    return (
        value.replace("【", "")
        .replace("】", "")
        .replace("(ACE SPEC)", "")
        .replace("（ACE SPEC）", "")
        .strip()
    )


def normalize_collection_no(value: str) -> str:
    return value.split("/", 1)[0].lstrip("0")


def normalize_expansion(value: str) -> str:
    return value.strip().upper()


def fetch_deck_page(deck_code: str) -> str:
    url = OFFICIAL_DECK_URL.format(code=deck_code)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_hidden_value(page: str, field: str) -> str:
    match = re.search(
        rf'name="{re.escape(field)}"\s+id="{re.escape(field)}"\s+value="([^"]*)"',
        page,
    )
    if not match:
        return ""
    return html.unescape(match.group(1))


def parse_official_names(page: str) -> dict[int, tuple[str, str | None, str | None]]:
    names: dict[int, tuple[str, str | None, str | None]] = {}
    pattern = re.compile(r"PCGDECK\.searchItemName\[(\d+)\]='((?:\\'|[^'])*)';")
    for official_id_raw, raw_name in pattern.findall(page):
        official_id = int(official_id_raw)
        display_name = html.unescape(raw_name.replace("\\'", "'"))
        match = re.match(r"^(.*?)\(([^()\s]+)\s+([0-9A-Za-z]+)/[0-9A-Za-z]+\)$", display_name)
        if match:
            name, expansion, collection_no = match.groups()
            names[official_id] = (name, expansion, collection_no)
        else:
            names[official_id] = (display_name, None, None)
    return names


def parse_official_deck(page: str) -> list[OfficialCard]:
    names = parse_official_names(page)
    cards: list[OfficialCard] = []
    for field in DECK_FIELDS:
        value = parse_hidden_value(page, field)
        if not value:
            continue
        for item in value.split("-"):
            if not item:
                continue
            parts = item.split("_")
            if len(parts) < 2:
                raise ValueError(f"Unexpected deck item format: {item}")
            official_id = int(parts[0])
            count = int(parts[1])
            if official_id not in names:
                raise ValueError(f"Official card name was not found: {official_id}")
            name, expansion, collection_no = names[official_id]
            cards.append(
                OfficialCard(
                    official_id=official_id,
                    name=name,
                    expansion=expansion,
                    collection_no=collection_no,
                    count=count,
                )
            )
    return cards


def load_kaggle_cards(path: Path) -> list[KaggleCard]:
    cards_by_id: dict[int, KaggleCard] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        for row in reader:
            card_id = int(row["カード ID"])
            cards_by_id.setdefault(
                card_id,
                KaggleCard(
                    card_id=card_id,
                    name=row["カード名"],
                    expansion=row["エキスパンションマーク"],
                    collection_no=row["コレクション番号"],
                ),
            )
    return list(cards_by_id.values())


def build_indexes(cards: list[KaggleCard]):
    by_print: dict[tuple[str, str, str], int] = {}
    by_name: dict[str, set[int]] = {}
    for card in cards:
        name = normalize_name(card.name)
        by_name.setdefault(name, set()).add(card.card_id)
        by_print[
            (
                name,
                normalize_expansion(card.expansion),
                normalize_collection_no(card.collection_no),
            )
        ] = card.card_id
    return by_print, by_name


def map_official_to_kaggle(
    official_cards: list[OfficialCard],
    by_print: dict[tuple[str, str, str], int],
    by_name: dict[str, set[int]],
) -> tuple[list[int], list[str], list[str]]:
    deck: list[int] = []
    notes: list[str] = []
    errors: list[str] = []
    for card in official_cards:
        normalized_name = normalize_name(card.name)
        kaggle_id = BASIC_ENERGY_BY_NAME.get(normalized_name)

        if kaggle_id is None and card.expansion and card.collection_no:
            official_key = (
                normalized_name,
                normalize_expansion(card.expansion),
                normalize_collection_no(card.collection_no),
            )
            kaggle_id = by_print.get(official_key)
            if kaggle_id is None and official_key in PRINT_ALIASES:
                alias_key = PRINT_ALIASES[official_key]
                kaggle_id = by_print.get(alias_key)
                if kaggle_id is not None:
                    notes.append(
                        f"{describe_official_card(card)}: 公式表記 {card.expansion} "
                        f"{card.collection_no} を Kaggle表記 {alias_key[1]} "
                        f"{alias_key[2]} としてKaggle ID {kaggle_id}に対応しました。"
                    )

        if kaggle_id is None:
            candidates = sorted(by_name.get(normalized_name, set()))
            if len(candidates) == 1:
                kaggle_id = candidates[0]
                notes.append(
                    f"{describe_official_card(card)}: 公式の収録情報では一致せず、同名カードとしてKaggle ID {kaggle_id}に対応しました。"
                )
            elif not candidates:
                errors.append(
                    "対応するKaggleカードが見つかりません: "
                    f"{describe_official_card(card)}"
                )
                continue
            else:
                errors.append(
                    "同名カードが複数あり自動対応できません: "
                    f"{describe_official_card(card)} candidates={candidates}"
                )
                continue

        deck.extend([kaggle_id] * card.count)
    return deck, notes, errors


def describe_official_card(card: OfficialCard) -> str:
    print_info = ""
    if card.expansion and card.collection_no:
        print_info = f" {card.expansion} {card.collection_no}"
    return (
        f"{card.name}{print_info} x{card.count} "
        f"(official_id={card.official_id})"
    )


def default_output_path(deck_code: str) -> Path:
    safe_code = re.sub(r"[^0-9A-Za-z]+", "_", deck_code).strip("_")
    return ROOT / "decks" / "local" / f"deck_{safe_code}.csv"


def write_deck(path: Path, deck: list[int]):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(str(card_id) for card_id in deck) + "\n", encoding="utf-8")


def import_deck_code(deck_code: str, output: Path) -> tuple[Path, list[str]]:
    try:
        page = fetch_deck_page(deck_code)
    except Exception as exc:
        raise DeckCodeCompileError(
            "fetch",
            [f"公式サイトからデッキコードを取得できませんでした: {deck_code}: {type(exc).__name__}: {exc}"],
        ) from exc

    try:
        official_cards = parse_official_deck(page)
    except Exception as exc:
        raise DeckCodeCompileError(
            "parse",
            [f"公式ページ内のデッキ情報を解析できませんでした: {type(exc).__name__}: {exc}"],
        ) from exc

    if not official_cards:
        raise DeckCodeCompileError(
            "parse",
            [f"デッキコードからカード一覧を取得できませんでした: {deck_code}"],
        )

    by_print, by_name = build_indexes(load_kaggle_cards(JP_CARD_DATA))
    deck, notes, map_errors = map_official_to_kaggle(official_cards, by_print, by_name)
    if map_errors:
        raise DeckCodeCompileError("map", map_errors, notes)

    if len(deck) != 60:
        raise DeckCodeCompileError(
            "count",
            [f"変換後のデッキが60枚ではありません: {len(deck)}枚"],
            notes,
        )

    validation = validate_deck_ids(deck, path=f"deck_code:{deck_code}")
    if not validation.ok:
        raise DeckCodeCompileError("validate", validation.errors, notes + validation.warnings)

    write_deck(output, deck)
    return output, notes + validation.warnings


def main():
    parser = argparse.ArgumentParser(description="公式デッキコードをKaggle用deck CSVに変換します。")
    parser.add_argument("deck_code", help="例: 4GGxYc-KmW2Iv-8c4c8c")
    parser.add_argument("--output", help="出力先CSV。省略時は decks/local/deck_<code>.csv")
    args = parser.parse_args()

    output = Path(args.output) if args.output else default_output_path(args.deck_code)
    try:
        path, notes = import_deck_code(args.deck_code, output)
    except DeckCodeCompileError as exc:
        print(f"NG stage={exc.stage}")
        for error in exc.errors:
            print(f"ERROR: {error}")
        for warning in exc.warnings:
            print(f"WARN: {warning}")
        raise SystemExit(1)

    print(f"OK {path}")
    for note in notes:
        print(f"WARN: {note}")


if __name__ == "__main__":
    main()
