"""Test helpers: a clean environment, a network block and quiet output."""
from __future__ import annotations

import contextlib
import io
import os
import socket
import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

_PREFIXES = ("ANTHROPIC_", "OPENAI_", "GEMINI_", "GOOGLE_API", "STORE_FULL_TEXT_", "MONTHLY_BUDGET",
             "EST_COST", "ALLOW_UNPRICED", "PROVIDERS", "PANEL_INSTRUCTION", "SLEEP_BETWEEN", "OUTPUT_DIR")
_LOCATION = ("USER_COUNTRY", "USER_REGION", "USER_CITY", "USER_TIMEZONE", "USER_LOCATION")


def clean_env(**overrides):
    """Patch os.environ: drop every monitor setting, skip .env files, then apply overrides."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(_PREFIXES) and k not in _LOCATION}
    env["MONITOR_SKIP_ENV_FILES"] = "1"
    env["SLEEP_BETWEEN_CALLS"] = "0"
    env.update({k: str(v) for k, v in overrides.items()})
    return mock.patch.dict(os.environ, env, clear=True)


def _refuse(*args, **kwargs):
    raise AssertionError("network access attempted in a test that has to stay offline")


@contextlib.contextmanager
def no_network():
    with mock.patch.object(socket.socket, "connect", _refuse), \
         mock.patch.object(socket, "create_connection", _refuse), \
         mock.patch.object(socket, "getaddrinfo", _refuse):
        yield


@contextlib.contextmanager
def quiet():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        yield buf
