import os
import json
import gzip
import hashlib
import uuid
import logging
from typing import List, Dict, Any
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class RawDataSink:
    """Handles metadata envelope generation, JSONL + GZIP compression,"""

    def __init__(self, base_dir: str = "data/raw"):
        self.base_dir = base_dir

    def _generate_metadata_envelope(self, payload: List[Dict[str, Any]], endpoint: str) -> Dict[str, Any]:
        """Wraps raw record lists with operational audit metadata."""
        raw_json_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(raw_json_bytes).hexdigest()

        return {
            "execution_id": str(uuid.uuid4()),
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "source_endpoint": endpoint,
            "record_count": len(payload),
            "payload_hash": payload_hash,
            "data": payload,
        }

    def save_entity_partitioned(
        self,
        owner: str,
        repo: str,
        entity_name: str,
        records: List[Dict[str, Any]],
        endpoint: str
    ) -> str:
        """Saves compressed JSONL payloads in partitioned paths:

        data/raw/{owner}/{repo}/{entity_name}/{YYYY}/{MM}/{DD}/{entity_name}_{timestamp}.jsonl.gz
        """
        if not records:
            logger.warning(f"No records provided for {owner}/{repo} ({entity_name}). Skipping write.")
            return ""

        # 1. Wrap records in metadata envelope
        envelope = self._generate_metadata_envelope(records, endpoint)

        # 2. Build partitioned path
        now = datetime.now(timezone.utc)
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")
        timestamp = now.strftime("%Y%m%d_%H%M%S")

        partition_dir = os.path.join(self.base_dir, owner, repo, entity_name, year, month, day)
        os.makedirs(partition_dir, exist_ok=True)

        filename = f"{entity_name}_{timestamp}.jsonl.gz"
        file_path = os.path.join(partition_dir, filename)

        # 3. Write compressed JSONL (.jsonl.gz)
        with gzip.open(file_path, "wt", encoding="utf-8") as gz_file:
            gz_file.write(json.dumps(envelope) + "\n")

        logger.info(f"Successfully landed {len(records)} compressed records to Lake: {file_path}")
        return file_path


if __name__ == "__main__":
    from src.extract.github_client import GitHubClient

    client = GitHubClient()
    sink = RawDataSink()

    # Test extracting and saving workflow runs
    owner, repo = "pallets", "flask"
    runs = client.fetch_workflow_runs_incremental(owner, repo, days_back=3, max_pages=1)

    if runs:
        saved_path = sink.save_entity_partitioned(
            owner=owner,
            repo=repo,
            entity_name="workflow_runs",
            records=runs,
            endpoint=f"/repos/{owner}/{repo}/actions/runs"
        )
        print(f"\n[+] Raw Data Lake File Landed At: {saved_path}")