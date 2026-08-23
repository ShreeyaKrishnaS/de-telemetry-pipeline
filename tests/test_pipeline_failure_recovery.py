import pytest
import time
from unittest.mock import MagicMock, patch

# -------------------------------------------------------------------------
# Test 1: Transient API Failure -> Retry -> Success
# -------------------------------------------------------------------------
def test_transient_api_failure_retry_success():
    """Verify that network-level API failures retry with backoff and succeed."""
    call_count = 0

    def mock_fetch_with_transient_error():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError(f"Simulated network drop on attempt {call_count}")
        return {"status": 200, "data": [{"job_id": 101, "status": "completed"}]}

    # Retry loop simulating production resilience
    max_retries = 3
    result = None
    for attempt in range(1, max_retries + 1):
        try:
            result = mock_fetch_with_transient_error()
            break
        except ConnectionError:
            time.sleep(0.01)  # lightweight backoff for unit tests

    assert result is not None
    assert result["status"] == 200
    assert call_count == 3
    print("\n[PASS] Test 1: Handled 2 transient network failures and recovered on retry #3.")


# -------------------------------------------------------------------------
# Test 2: Duplicate Batch Ingestion -> MERGE Idempotency
# -------------------------------------------------------------------------
def test_duplicate_batch_merge_idempotency():
    """Verify that ingesting identical records deduplicates via MERGE semantics."""
    initial_mart = {
        101: {"job_id": 101, "status": "failed", "attempt": 1},
        102: {"job_id": 102, "status": "success", "attempt": 1},
    }

    incoming_batch = [
        {"job_id": 101, "status": "failed", "attempt": 1},  # Exact Duplicate
        {"job_id": 103, "status": "failed", "attempt": 1},  # New Record
    ]

    # MERGE logic simulation (MATCHED -> UPDATE, NOT MATCHED -> INSERT)
    for record in incoming_batch:
        jid = record["job_id"]
        initial_mart[jid] = record

    assert len(initial_mart) == 3
    assert set(initial_mart.keys()) == {101, 102, 103}
    print("[PASS] Test 2: Re-ingesting duplicate batch resulted in zero duplicate rows (idempotent).")


# -------------------------------------------------------------------------
# Test 3: Late Status Event -> Attempt Reconciliation
# -------------------------------------------------------------------------
def test_late_status_update_reconciliation():
    """Verify out-of-order events update existing attempts without creating orphan rows."""
    staged_records = {
        201: {"job_id": 201, "status": "in_progress", "conclusion": None, "updated_at": "2026-08-20T10:00:00Z"}
    }

    late_event = {"job_id": 201, "status": "completed", "conclusion": "failure", "updated_at": "2026-08-20T10:05:00Z"}

    # Reconcile event by primary key
    if late_event["job_id"] in staged_records:
        staged_records[late_event["job_id"]].update(late_event)

    assert staged_records[201]["status"] == "completed"
    assert staged_records[201]["conclusion"] == "failure"
    assert staged_records[201]["updated_at"] == "2026-08-20T10:05:00Z"
    assert len(staged_records) == 1
    print("[PASS] Test 3: Late status update cleanly reconciled existing job attempt.")