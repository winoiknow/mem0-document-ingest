import logging
import time

import requests

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2


def ingest_chunks(
    chunks: list[str],
    mem0_url: str,
    user_id: str,
    metadata: dict,
) -> bool:
    endpoint = f"{mem0_url.rstrip('/')}/memories"
    success = True

    for i, chunk in enumerate(chunks):
        chunk_metadata = {**metadata, "chunk_index": i, "total_chunks": len(chunks)}
        payload = {
            "messages": [{"role": "user", "content": chunk}],
            "user_id": user_id,
            "metadata": chunk_metadata,
        }

        if not _post_with_retry(endpoint, payload):
            success = False

    return success


def _post_with_retry(endpoint: str, payload: dict) -> bool:
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.post(
                endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
            if resp.status_code in (200, 201):
                return True
            elif resp.status_code == 429:
                wait = BACKOFF_BASE ** (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait}s before retry")
                time.sleep(wait)
            else:
                logger.error(f"mem0 returned {resp.status_code}: {resp.text[:200]}")
                return False
        except requests.exceptions.RequestException as e:
            wait = BACKOFF_BASE ** (attempt + 1)
            logger.error(f"Request failed (attempt {attempt + 1}): {e}, retrying in {wait}s")
            time.sleep(wait)

    logger.error(f"Failed after {MAX_RETRIES} retries")
    return False
