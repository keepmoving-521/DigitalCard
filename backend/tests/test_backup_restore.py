import json
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.backup_restore import create_backup, restore_backup, sha256


def test_backup_restore_and_checksum_validation() -> None:
    workspace = Path("data/test-backup-restore") / str(uuid4())
    workspace.mkdir(parents=True)
    try:
        source = workspace / "source.db"
        with sqlite3.connect(source) as connection:
            connection.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
            connection.execute("INSERT INTO sample (value) VALUES ('before-backup')")
        backup = create_backup(source, workspace / "backups", "1.0.0")
        manifest = json.loads(backup.with_suffix(".json").read_text(encoding="utf-8"))
        assert manifest["sha256"] == sha256(backup)
        target = workspace / "restored.db"
        restore_backup(backup, target)
        with sqlite3.connect(target) as connection:
            assert connection.execute("SELECT value FROM sample").fetchone() == ("before-backup",)

        backup.write_bytes(backup.read_bytes() + b"tampered")
        with pytest.raises(ValueError, match="checksum"):
            restore_backup(backup, workspace / "invalid.db")
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
