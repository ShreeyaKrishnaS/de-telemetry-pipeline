import pytest
import responses
from requests.exceptions import HTTPError
from src.extract.github_client import GitHubClient


@responses.activate
def test_fetch_workflow_runs_pagination():
    """Tests that the client iterates through pages until runs are empty."""
    client = GitHubClient(token="mock_token")

    # Mock Page 1 (Returns 2 items)
    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        json={"workflow_runs": [{"id": 1}, {"id": 2}]},
        status=200,
    )

    # Mock Page 2 (Returns empty list -> signals end of pagination)
    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        json={"workflow_runs": []},
        status=200,
    )

    runs = client.fetch_workflow_runs("pallets", "flask", max_pages=5)

    assert len(runs) == 2
    assert runs[0]["id"] == 1
    assert runs[1]["id"] == 2


@responses.activate
def test_rate_limit_backoff_retry():
    """Tests that 429 status code triggers a retry and succeeds on the second attempt."""
    client = GitHubClient(token="mock_token")

    # First request: 429 Rate Limit
    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "1"},
        status=429,
    )

    # Second request: 200 Success
    responses.add(
        responses.GET,
        "https://api.github.com/repos/pallets/flask/actions/runs",
        json={"workflow_runs": [{"id": 999}]},
        status=200,
    )

    runs = client.fetch_workflow_runs("pallets", "flask", max_pages=1)

    assert len(runs) == 1
    assert runs[0]["id"] == 999