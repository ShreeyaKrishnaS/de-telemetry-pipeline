import os
import time
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class GitHubClient:
    """REST API Client for GitHub Actions telemetry with rate-limit tracking,"""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        if not self.token:
            logger.warning("No GITHUB_TOKEN provided! Requests capped at 60 req/hr.")

        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    def _request_with_retry(self, url: str, params: Optional[Dict[str, Any]] = None, max_retries: int = 5) -> requests.Response:
        params = params or {}
        retries = 0
        backoff_sec = 2

        while retries <= max_retries:
            response = self.session.get(url, params=params, timeout=15)
            rate_remaining = response.headers.get("X-RateLimit-Remaining")
            rate_reset = response.headers.get("X-RateLimit-Reset")

            if response.status_code == 200:
                return response

            if response.status_code == 429 or (response.status_code == 403 and rate_remaining == "0"):
                reset_time = int(rate_reset) if rate_reset else time.time() + backoff_sec
                sleep_duration = max(reset_time - int(time.time()), backoff_sec) + 1
                logger.warning(f"Rate limit hit. Sleeping for {sleep_duration}s...")
                time.sleep(sleep_duration)
                retries += 1
                backoff_sec *= 2
                continue

            if response.status_code >= 500:
                time.sleep(backoff_sec)
                retries += 1
                backoff_sec *= 2
                continue

            response.raise_for_status()

        raise requests.HTTPError(f"Exceeded max retries for URL: {url}")

    def fetch_workflow_runs_incremental(
        self,
        owner: str,
        repo: str,
        days_back: int = 7,
        max_pages: int = 5
    ) -> List[Dict[str, Any]]:
        """Fetches workflow runs using a created date range filter and preserves

        composite attempt identifiers (run_id, run_attempt).
        """
        endpoint = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs"
        
        # 1. Created window for API request
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days_back)
        created_filter = f"{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
        print(f"created_filter{created_filter}")
        params = {"per_page": 100, "page": 1, "created": created_filter}
        processed_runs: List[Dict[str, Any]] = []

        while params["page"] <= max_pages:
            logger.info(f"Fetching {owner}/{repo} runs (Created Filter: {created_filter}) — Page {params['page']}...")
            response = self._request_with_retry(endpoint, params=params)
            data = response.json()
            runs = data.get("workflow_runs", [])

            if not runs:
                logger.info(f"No more runs found on page {params['page']}.")
                break

            for run in runs:
                run_id = run.get("id")
                run_attempt = run.get("run_attempt", 1)
                
                # Composite Key creation: "31477751036_1"
                composite_key = f"{run_id}_{run_attempt}"
                
                # Enrich the dictionary with explicitly tracked metadata
                run["composite_key"] = composite_key
                run["repo_owner"] = owner
                run["repo_name"] = repo
                
                processed_runs.append(run)

            if len(runs) < params["per_page"]:
                break

            params["page"] += 1

        logger.info(f"Successfully retrieved {len(processed_runs)} incremental runs for {owner}/{repo}.")
        return processed_runs
    def fetch_run_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """Fetches all jobs and steps associated with a specific workflow run ID.

        Endpoint: GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs
        """
        endpoint = f"{self.BASE_URL}/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        response = self._request_with_retry(endpoint)
        data = response.json()
        jobs = data.get("jobs", [])

        processed_jobs = []
        for job in jobs:
            job_id = job.get("id")
            run_attempt = job.get("run_attempt", 1)
            
            # Composite key for job attempt: "31477751036_12345678_1"
            job["composite_job_key"] = f"{run_id}_{job_id}_{run_attempt}"
            job["run_composite_key"] = f"{run_id}_{run_attempt}"
            
            processed_jobs.append(job)

        return processed_jobs

if __name__ == "__main__":
    client = GitHubClient()
    runs = client.fetch_workflow_runs_incremental("pallets", "flask", days_back=7, max_pages=1)
    
    if runs:
        sample_run = runs[0]
        print(f"\n[+] Extracted Run ID: {sample_run['id']} | Composite Key: {sample_run['composite_key']}")
        
        # Fetch jobs for this specific run
        jobs = client.fetch_run_jobs("pallets", "flask", sample_run["id"])
        print(f"[+] Total Jobs found in Run #{sample_run['id']}: {len(jobs)}")
        
        if jobs:
            sample_job = jobs[0]
            print(f" [+] Sample Job Name: {sample_job['name']} | Status: {sample_job['status']} | Conclusion: {sample_job['conclusion']}")
            print(f" [+] Total Steps in Job: {len(sample_job.get('steps', []))}")