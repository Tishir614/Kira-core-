import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KIRA_LOCAL_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_llama(tmp_path, monkeypatch):
    wrapper = tmp_path / "llama-server"
    wrapper.write_text(f"#!/bin/sh\nexec {sys.executable} {Path(__file__).parent / 'fake_llama_server.py'} \"$@\"\n")
    wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("LLAMA_SERVER_BIN", str(wrapper))
    return wrapper
