from __future__ import annotations

import argparse
import json
from pathlib import Path


def extract_visualizer_payload(episode: dict) -> list[dict]:
    for step in episode.get("steps", []):
        for agent_step in step:
            payload = agent_step.get("visualize")
            if isinstance(payload, list) and payload:
                return payload
    raise ValueError("No visualize payload found in episode JSON.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Kaggle episode JSON から公式 Visualizer 用 JSON を抜き出します。")
    parser.add_argument("episode_json", help="downloads/episodes/.../<episode_id>.json")
    parser.add_argument("--out-dir", default="experiments/visualizer")
    args = parser.parse_args()

    input_path = Path(args.episode_json)
    episode = json.loads(input_path.read_text(encoding="utf-8"))
    payload = extract_visualizer_payload(episode)

    episode_id = episode.get("info", {}).get("EpisodeId", input_path.stem)
    out_path = Path(args.out_dir) / f"kaggle_episode_{episode_id}_visualizer.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
