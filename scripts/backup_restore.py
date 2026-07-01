import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote


def sqlite_path(database_url: str, root: Path) -> Path:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix) or database_url == "sqlite:///:memory:":
        raise ValueError("The built-in backup tool supports file-based SQLite databases only")
    value = Path(unquote(database_url.removeprefix(prefix)))
    return value.resolve() if value.is_absolute() else (root / value).resolve()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_database(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise ValueError(f"SQLite integrity check failed: {result}")


def create_backup(source: Path, output_dir: Path, version: str = "unknown") -> Path:
    if not source.is_file():
        raise FileNotFoundError(f"Database does not exist: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = output_dir / f"digitalcard-{timestamp}.db"
    with (
        closing(sqlite3.connect(source)) as source_db,
        closing(sqlite3.connect(destination)) as backup_db,
    ):
        source_db.backup(backup_db)
    verify_database(destination)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "version": version,
        "source": str(source),
        "file": destination.name,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256(destination),
    }
    destination.with_suffix(".json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination


def restore_backup(backup: Path, target: Path, force: bool = False) -> Path | None:
    manifest_path = backup.with_suffix(".json")
    if not backup.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("Backup database and matching manifest are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("sha256") != sha256(backup):
        raise ValueError("Backup checksum does not match its manifest")
    verify_database(backup)
    if target.exists() and not force:
        raise FileExistsError("Target database exists; pass --force after stopping the API")
    target.parent.mkdir(parents=True, exist_ok=True)
    safety_copy = None
    if target.exists():
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        safety_copy = target.with_name(f"{target.stem}.pre-restore-{timestamp}{target.suffix}")
        with (
            closing(sqlite3.connect(target)) as source_db,
            closing(sqlite3.connect(safety_copy)) as backup_db,
        ):
            source_db.backup(backup_db)
    temporary = target.with_suffix(f"{target.suffix}.restore.tmp")
    if temporary.exists():
        temporary.unlink()
    with (
        closing(sqlite3.connect(backup)) as source_db,
        closing(sqlite3.connect(temporary)) as target_db,
    ):
        source_db.backup(target_db)
    verify_database(temporary)
    os.replace(temporary, target)
    return safety_copy


def database_url_from_env(root: Path) -> str:
    if value := os.getenv("DATABASE_URL"):
        return value
    env_file = root / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return "sqlite:///./data/digitalcard.db"


def main() -> None:
    parser = argparse.ArgumentParser(description="DigitalCard SQLite backup and restore")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--output", type=Path, default=Path("data/backups"))
    backup_parser.add_argument("--version", default="unknown")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("backup", type=Path)
    restore_parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = sqlite_path(database_url_from_env(root), root)
    if args.command == "backup":
        result = create_backup(target, (root / args.output).resolve(), args.version)
        print(result)
    else:
        safety = restore_backup(args.backup.resolve(), target, args.force)
        print(f"Restored {target}")
        if safety:
            print(f"Previous database saved as {safety}")


if __name__ == "__main__":
    main()
