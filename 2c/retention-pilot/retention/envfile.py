"""Read a .env file (KEY=VALUE lines) into os.environ without overwriting values already set."""
from __future__ import annotations

import os


def load_env(path: str) -> list[str]:
    loaded = []
    if not os.path.exists(path):
        return loaded
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded
