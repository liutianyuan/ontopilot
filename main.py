from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent


def ensure_local_config() -> None:
    settings_path = ROOT_DIR / "config" / "settings.yaml"
    settings_example_path = ROOT_DIR / "config" / "settings.yaml.example"
    env_path = ROOT_DIR / ".env"
    env_example_path = ROOT_DIR / ".env.example"

    if not settings_path.exists() and settings_example_path.exists():
        shutil.copyfile(settings_example_path, settings_path)
        print("Created config/settings.yaml from config/settings.yaml.example")

    if not env_path.exists() and env_example_path.exists():
        shutil.copyfile(env_example_path, env_path)
        print("Created .env from .env.example")


def load_env_file() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    load_dotenv(env_path)


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required. Run: uv run python main.py")

    ensure_local_config()
    load_env_file()

    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8100"))
    reload = os.environ.get("RELOAD", "1") not in {"0", "false", "False"}

    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
