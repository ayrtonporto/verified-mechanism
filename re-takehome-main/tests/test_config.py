from __future__ import annotations

from re_harness.config import load_local_env


def test_dotenv_does_not_override_exported_environment(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=file-key\nN_WORKERS=7\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", "exported-key")
    monkeypatch.delenv("N_WORKERS", raising=False)
    load_local_env(tmp_path)
    import os

    assert os.environ["OPENROUTER_API_KEY"] == "exported-key"
    assert os.environ["N_WORKERS"] == "7"

