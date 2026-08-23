import os
import json
import gzip
import pytest
from src.extract.s3_writer import RawDataSink


def test_save_entity_partitioned(tmp_path):
    """Tests that RawDataSink writes partitioned .jsonl.gz files with valid metadata envelopes."""
    # Use pytest's tmp_path fixture as a temporary base directory
    sink = RawDataSink(base_dir=str(tmp_path))

    mock_records = [
        {"id": 1, "composite_key": "1_1", "status": "completed"},
        {"id": 2, "composite_key": "2_1", "status": "failed"},
    ]

    saved_path = sink.save_entity_partitioned(
        owner="pallets",
        repo="flask",
        entity_name="workflow_runs",
        records=mock_records,
        endpoint="/repos/pallets/flask/actions/runs"
    )

    # 1. Verify file exists
    assert os.path.exists(saved_path)
    assert saved_path.endswith(".jsonl.gz")

    # 2. Decompress and read the metadata envelope
    with gzip.open(saved_path, "rt", encoding="utf-8") as gz_file:
        line = gz_file.readline()
        envelope = json.loads(line)

    # 3. Verify envelope attributes
    assert envelope["source_endpoint"] == "/repos/pallets/flask/actions/runs"
    assert envelope["record_count"] == 2
    assert "execution_id" in envelope
    assert "payload_hash" in envelope
    assert len(envelope["data"]) == 2
    assert envelope["data"][0]["composite_key"] == "1_1"


def test_save_entity_partitioned_empty_records(tmp_path):
    """Tests that empty record lists do not create phantom files."""
    sink = RawDataSink(base_dir=str(tmp_path))

    saved_path = sink.save_entity_partitioned(
        owner="pallets",
        repo="flask",
        entity_name="workflow_runs",
        records=[],
        endpoint="/repos/pallets/flask/actions/runs"
    )

    assert saved_path == ""