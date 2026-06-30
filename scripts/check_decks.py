import argparse
from pathlib import Path

from deck_validation import validate_all_decks, validate_deck_file


def print_result(result):
    status = "OK" if result.ok else "NG"
    print(
        f"{status} {result.path} "
        f"cards={result.card_count} basic={result.basic_pokemon_count} ace={result.ace_spec_count}"
    )
    for error in result.errors:
        print(f"  ERROR: {error}")
    for warning in result.warnings:
        print(f"  WARN: {warning}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--deck-dir", default="decks")
    args = parser.parse_args()

    if args.paths:
        results = [validate_deck_file(Path(path)) for path in args.paths]
    else:
        results = validate_all_decks(Path(args.deck_dir))

    for result in results:
        print_result(result)

    if any(not result.ok for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
