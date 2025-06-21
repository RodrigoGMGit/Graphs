import importlib
import json
import os
import sys

def test_config_env(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg.json"
    cfg.write_text(json.dumps({"data_dir": "xyz"}))
    monkeypatch.setenv("CHAPTERSYNC_CONFIG", str(cfg))
    if "chapter_sync" in sys.modules:
        importlib.reload(sys.modules["chapter_sync"])
    else:
        import chapter_sync  # noqa: F401
    from chapter_sync import config
    assert config.data_dir == "xyz"

