import argparse
import logging
import time
from pathlib import Path

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler

import chunker
import extractors
import ingester
import manifest
import scanner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def run_ingestion():
    config = load_config()
    folders = config["folders"]
    mem0_url = config["mem0_url"]
    user_id = config["user_id"]
    chunk_size = config.get("chunk_size_tokens", 1000)
    chunk_overlap = config.get("chunk_overlap_tokens", 100)
    ocr_enabled = config.get("ocr_enabled", True)
    supported_extensions = config.get("supported_extensions", [".txt", ".md", ".pdf", ".docx"])

    logger.info(f"Starting ingestion run for {len(folders)} folder(s)")

    conn = manifest.get_connection()
    changed_files = scanner.get_changed_files(conn, folders, supported_extensions)

    if not changed_files:
        logger.info("No new or modified files found")
        return

    logger.info(f"Found {len(changed_files)} file(s) to process")
    processed = 0
    failed = 0

    for file_path in changed_files:
        logger.info(f"Processing: {file_path}")

        text = extractors.extract_text(file_path, ocr_enabled=ocr_enabled)
        if not text or not text.strip():
            logger.warning(f"No text extracted from {file_path}, skipping")
            continue

        chunks = chunker.chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

        metadata = {
            "source_path": str(file_path),
            "file_type": file_path.suffix.lower(),
            "file_name": file_path.name,
        }

        success = ingester.ingest_chunks(chunks, mem0_url, user_id, metadata)

        if success:
            file_hash = scanner.compute_hash(file_path)
            stat = file_path.stat()
            manifest.upsert_record(
                conn,
                path=str(file_path),
                modified_time=stat.st_mtime,
                size=stat.st_size,
                content_hash=file_hash,
                ingested_at=time.time(),
            )
            processed += 1
            logger.info(f"Ingested: {file_path} ({len(chunks)} chunk(s))")
        else:
            failed += 1
            logger.error(f"Failed to ingest: {file_path}")

    conn.close()
    logger.info(f"Ingestion run complete: {processed} processed, {failed} failed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="mem0 document ingestion service")
    parser.add_argument(
        "--interval",
        type=float,
        default=None,
        help="Poll interval in minutes (overrides config.yaml). Accepts decimals, e.g. 0.5 for 30 seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single ingestion pass and exit (no scheduling).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    config = load_config()
    interval_minutes = args.interval if args.interval is not None else config.get("poll_interval_minutes", 60)

    if args.once:
        logger.info("Running single ingestion pass (--once)")
        run_ingestion()
        return

    logger.info(f"Document ingestion service starting (poll every {interval_minutes} min)")

    run_ingestion()

    scheduler = BlockingScheduler()
    scheduler.add_job(run_ingestion, "interval", minutes=interval_minutes)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Shutting down")


if __name__ == "__main__":
    main()
