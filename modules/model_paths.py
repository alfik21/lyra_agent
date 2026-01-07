from __future__ import annotations

from pathlib import Path
import os
import json


def get_models_path() -> Path:
    env = os.environ.get("LYRA_MODELS_PATH")
    if env:
        return Path(env).expanduser()

    archive = Path("/media/tomek/arhiwum/AI_MODELS/models.json")
    if archive.exists():
        return archive

    return Path.home() / "lyra_agent" / "models.json"


def get_models_dir() -> Path:
    return get_models_path().parent


def load_models(default: dict | None = None) -> dict:
    path = get_models_path()
    if not path.exists():
        return default if default is not None else {"active": "", "available": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default if default is not None else {"active": "", "available": {}}


def save_models(data: dict) -> None:
    path = get_models_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
