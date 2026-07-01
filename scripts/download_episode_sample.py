from __future__ import annotations

import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path

from kaggle.api.kaggle_api_extended import KaggleApi


def ensure_token_from_local_file() -> None:
    if os.environ.get("KAGGLE_API_TOKEN"):
        return
    token_path = Path(".kaggle/access_token")
    if token_path.exists():
        os.environ["KAGGLE_API_TOKEN"] = token_path.read_text(encoding="utf-8").strip()


def list_files(api: KaggleApi, dataset: str, limit: int) -> list[dict[str, int | str]]:
    rows: list[dict[str, int | str]] = []
    page_token = None
    while len(rows) < limit:
        page_size = min(200, limit - len(rows))
        response = api.dataset_list_files(dataset, page_token=page_token, page_size=page_size)
        files = response.files or []
        if not files:
            break
        for file in files:
            rows.append({"name": file.name, "size": int(file.total_bytes or 0)})
            if len(rows) >= limit:
                break
        page_token = response.next_page_token
        if not page_token:
            break
    return rows


def write_manifest(rows: list[dict[str, int | str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "size"])
        writer.writeheader()
        writer.writerows(rows)


def log_line(log_path: Path | None, message: str) -> None:
    stamped = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(stamped, flush=True)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(stamped + "\n")


def download_missing(
    api: KaggleApi,
    dataset: str,
    rows: list[dict[str, int | str]],
    output_dir: Path,
    sleep_seconds: float,
    log_path: Path | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(rows, 1):
        file_name = str(row["name"])
        output_path = output_dir / file_name
        expected_size = int(row["size"])
        if output_path.exists() and (expected_size <= 0 or output_path.stat().st_size == expected_size):
            if index % 50 == 0 or index == len(rows):
                log_line(log_path, f"skip {index}/{len(rows)} {file_name}")
            continue
        log_line(log_path, f"download {index}/{len(rows)} {file_name}")
        api.dataset_download_file(dataset, file_name, path=str(output_dir), quiet=True)
        if output_path.exists():
            log_line(log_path, f"done {index}/{len(rows)} {file_name} bytes={output_path.stat().st_size}")
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaggle Daily Top Episodes を指定件数だけ取得します。")
    parser.add_argument("--dataset", default="kaggle/pokemon-tcg-ai-battle-episodes-2026-06-30")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output-dir", default="downloads/episodes/2026-06-30")
    parser.add_argument("--manifest", default="research/episode_deck_analysis/2026-06-30_files_1000.csv")
    parser.add_argument("--log", default="research/episode_deck_analysis/download_episodes.log")
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.0)
    args = parser.parse_args()

    ensure_token_from_local_file()
    api = KaggleApi()
    api.authenticate()

    rows = list_files(api, args.dataset, args.limit)
    write_manifest(rows, Path(args.manifest))
    total_gb = sum(int(row["size"]) for row in rows) / 1024**3
    log_path = Path(args.log) if args.log else None
    log_line(log_path, f"listed={len(rows)} total_gb={total_gb:.2f} manifest={args.manifest}")

    if not args.list_only:
        download_missing(api, args.dataset, rows, Path(args.output_dir), args.sleep, log_path)


if __name__ == "__main__":
    main()
