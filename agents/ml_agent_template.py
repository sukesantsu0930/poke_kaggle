import json
import os
import pickle

from cg.api import Observation, to_observation_class


_MODEL = None
_CONFIG = None


def _agent_path(name: str) -> str:
    if os.path.exists(name):
        return name
    return "/kaggle_simulations/agent/" + name


def _load_model():
    global _MODEL
    if _MODEL is None:
        with open(_agent_path("model.pkl"), "rb") as file:
            _MODEL = pickle.load(file)
    return _MODEL


def _load_config():
    global _CONFIG
    if _CONFIG is None:
        path = _agent_path("model_config.json")
        if os.path.exists(path):
            with open(path, "r") as file:
                _CONFIG = json.load(file)
        else:
            _CONFIG = {}
    return _CONFIG


def read_deck_csv() -> list[int]:
    path = _agent_path("deck.csv")
    with open(path, "r") as file:
        return [int(line.strip()) for line in file if line.strip()]


def _fallback(obs: Observation) -> list[int]:
    if obs.select is None or obs.select.maxCount == 0:
        return []
    return list(range(obs.select.minCount))


def agent(obs_dict: dict) -> list[int]:
    obs: Observation = to_observation_class(obs_dict)
    if obs.select is None:
        return read_deck_csv()

    model = _load_model()
    config = _load_config()

    # Replace this block with your feature extraction and inference.
    # Return indexes into obs.select.option, not card IDs or action IDs.
    _ = model, config
    return _fallback(obs)
