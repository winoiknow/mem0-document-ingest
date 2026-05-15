import hashlib
import logging
import os
from pathlib import Path

import manifest

logger = logging.getLogger(__name__)


def compute_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def scan_folders(folders: list[str], supported_extensions: list[str]) -> list[Path]:
    found = []
    for folder in folders:
        folder_path = Path(folder)
        if not folder_path.exists():
            logger.warning(f"Folder does not exist: {folder}")
            continue
        for root, _, files in os.walk(folder_path):
            for filename in files:
                file_path = Path(root) / filename
                if file_path.suffix.lower() in supported_extensions:
                    found.append(file_path)
    return found


def get_changed_files(conn, folders: list[str], supported_extensions: list[str]) -> list[Path]:
    all_files = scan_folders(folders, supported_extensions)
    changed = []

    for file_path in all_files:
        stat = file_path.stat()
        record = manifest.get_record(conn, str(file_path))

        if record is None:
            logger.info(f"New file: {file_path}")
            changed.append(file_path)
        elif stat.st_mtime > record["modified_time"] or stat.st_size != record["size"]:
            file_hash = compute_hash(file_path)
            if file_hash != record["content_hash"]:
                logger.info(f"Modified file: {file_path}")
                changed.append(file_path)

    return changed
