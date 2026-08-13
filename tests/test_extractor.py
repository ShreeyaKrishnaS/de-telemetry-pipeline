import pytest
import responses
from src.extract.github_client import GitHubClient


@responses.activate
def test_fetch_workflow_runs_incremental_composite_key():
    """Tests that fetch_workflow_runs_incremental generates the correct composite key."""
    client = GitHubClient(token="mock_token")

    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        json={
            "workflow_runs": [
                {"id": 1001, "run_attempt": 1, "status": "completed"},
                {"id": 1001, "run_attempt": 2, "status": "completed"},
            ]
        },
        status=200,
    )

    runs = client.fetch_workflow_runs_incremental("pallets", "flask", days_back=7, max_pages=1)

    assert len(runs) == 2
    assert runs[0]["composite_key"] == "1001_1"
    assert runs[1]["composite_key"] == "1001_2"


@responses.activate
def test_fetch_run_jobs_and_steps():
    """Tests fetching nested jobs and verifying composite job keys."""
    client = GitHubClient(token="mock_token")

    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs/1001/jobs",
        json={
            "jobs": [
                {
                    "id": 5001,
                    "run_attempt": 1,
                    "name": "test-suite",
                    "status": "completed",
                    "steps": [{"name": "Set up Python", "status": "completed"}],
                }
            ]
        },
        status=200,
    )

    jobs = client.fetch_run_jobs("pallets", "flask", 1001)

    assert len(jobs) == 1
    assert jobs[0]["composite_job_key"] == "1001_5001_1"
    assert jobs[0]["run_composite_key"] == "1001_1"
    assert len(jobs[0]["steps"]) == 1


@responses.activate
def test_malformed_response_handling():
    """Tests that empty or malformed JSON payloads don't crash the extractor."""
    client = GitHubClient(token="mock_token")

    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        json={},  # Missing 'workflow_runs' key
        status=200,
    )

    runs = client.fetch_workflow_runs_incremental("pallets", "flask", days_back=7, max_pages=1)
    assert runs == []