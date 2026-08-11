import os
import time
import logging
import requests
from typing import Dict, List, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class GitHubClient:
    """REST API Client for interacting with GitHub Actions endpoints with built-in

    pagination, rate-limit inspection, and exponential backoff retry mechanics.
    """

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.warning(
                "No GITHUB_TOKEN provided! Requests will be capped at 60 req/hr."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if self.token:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.token}"}
            )

    def _request_with_retry(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        max_retries: int = 5,
    ) -> requests.Response:
        """Executes HTTP GET requests with rate-limit tracking and exponential backoff.

        :param url: Target REST API URL
        :param params: HTTP query parameters
        :param max_retries: Maximum number of retry attempts before raising
        :return: Successful requests.Response object
        """
        params = params or {}
        retries = 0
        backoff_sec = 2

        while retries <= max_retries:
            response = self.session.get(url, params=params, timeout=15)

            # Extract rate limit headers from GitHub response
            rate_remaining = response.headers.get("X-RateLimit-Remaining")
            rate_reset = response.headers.get("X-RateLimit-Reset")

            if response.status_code == 200:
                logger.debug(
                    f"Request successful. Rate limit remaining: {rate_remaining}"
                )
                return response

            # Handle 429 (Rate Limited) or 403 with 0 remaining calls
            if response.status_code == 429 or (
                response.status_code == 403 and rate_remaining == "0"
            ):
                reset_time = (
                    int(rate_reset) if rate_reset else time.time() + backoff_sec
                )
                sleep_duration = (
                    max(reset_time - int(time.time()), backoff_sec) + 1
                )
                logger.warning(
                    f"Rate limit hit (HTTP {response.status_code}). Backing off for {sleep_duration} seconds..."
                )
                time.sleep(sleep_duration)
                retries += 1
                backoff_sec *= 2
                continue

            # Handle transient server errors (5xx)
            if response.status_code >= 500:
                logger.warning(
                    f"Server error (HTTP {response.status_code}). Retrying in {backoff_sec}s (Attempt {retries + 1}/{max_retries})..."
                )
                time.sleep(backoff_sec)
                retries += 1
                backoff_sec *= 2
                continue

            # Raise immediate exception for 400, 401, 404 client errors
            response.raise_for_status()

        raise requests.HTTPError(
            f"Exceeded max retries ({max_retries}) for URL: {url}"
        )

    def fetch_workflow_runs(
        self,
        owner: str,
        repo: str,
        created_filter: Optional[str] = None,
        max_pages: int = 10,
    ) -> List[Dict[str, Any]]:
        """Paginates through workflow runs for a target repository.

        :param owner: Repo owner (e.g., 'pallets')
        :param repo: Repo name (e.g., 'flask')
        :param created_filter: Date filter (e.g., '2026-07-01..2026-08-10')
        :param max_pages: Safety cap on total pages during testing
        :return: List of raw workflow run dictionaries
        """
        endpoint = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"
        params = {"per_page": 100, "page": 1}
        if created_filter:
            params["created"] = created_filter

        all_runs: List[Dict[str, Any]] = []

        while params["page"] <= max_pages:
            logger.info(
                f"Fetching {owner}/{repo} workflow runs — Page {params['page']}..."
            )
            response = self._request_with_retry(endpoint, params=params)
            data = response.json()

            runs = data.get("workflow_runs", [])
            if not runs:
                logger.info(
                    f"No more runs found for {owner}/{repo} at page {params['page']}."
                )
                break

            all_runs.extend(runs)

            # If page returns fewer items than requested (per_page=100), we hit the end
            if len(runs) < params["per_page"]:
                break

            params["page"] += 1

        logger.info(
            f"Completed extraction for {owner}/{repo}. Retrieved {len(all_runs)} total workflow runs across {params['page']} page(s)."
        )
        return all_runs


if __name__ == "__main__":
    # Test client against both target repositories
    client = GitHubClient()

    for target_repo in ["pallets/flask", "fastapi/fastapi"]:
        owner, repo = target_repo.split("/")
        logger.info(f"\n--- Testing Extraction for {target_repo} ---")
        extracted_runs = client.fetch_workflow_runs(
            owner, repo, max_pages=2
        )
        print(f" [+] Extracted {len(extracted_runs)} runs from {target_repo}.")
        if extracted_runs:
            sample = extracted_runs[0]
            print(
                f" [+] Sample Run ID: {sample['id']} | Status: {sample['status']} | Conclusion: {sample['conclusion']}"
            )