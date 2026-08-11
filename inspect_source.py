import os
import requests
from datetime import datetime, timedelta

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

REPOSITORIES = ["pallets/flask", "fastapi/fastapi"]
LOOKBACK_DAYS = 60

def inspect_repository(repo: str):
    print(f"\n==========================================")
    print(f" Inspecting: {repo}")
    print(f"==========================================")
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS)
    date_filter = f"{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
    
    url = f"https://api.github.com/repos/{repo}/actions/runs"
    params = {
        "created": date_filter,
        "per_page": 100,
        "page": 1
    }
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 401:
        print(" [!] Authentication failed. Check your GITHUB_TOKEN.")
        return
    elif response.status_code != 200:
        print(f" [!] Error fetching runs: HTTP {response.status_code} - {response.text}")
        return

    data = response.json()
    total_count = data.get("total_count", 0)
    runs = data.get("workflow_runs", [])
    
    rate_remaining = response.headers.get("X-RateLimit-Remaining")
    rate_limit = response.headers.get("X-RateLimit-Limit")
    print(f" [+] API Rate Limit Remaining: {rate_remaining}/{rate_limit}")
    print(f" [+] Total Runs in last {LOOKBACK_DAYS} days: {total_count}")
    
    if not runs:
        print(" [!] No runs found in window.")
        return

    failed_runs = [r for r in runs if r.get("conclusion") == "failure"]
    successful_runs = [r for r in runs if r.get("conclusion") == "success"]
    in_progress_runs = [r for r in runs if r.get("status") in ["in_progress", "queued"]]
    
    print(f" [+] Sample Page Analysis (First 100 runs):")
    print(f"     - Successful: {len(successful_runs)}")
    print(f"     - Failed: {len(failed_runs)}")
    print(f"     - In Progress / Queued: {len(in_progress_runs)}")
    
    if failed_runs:
        sample_run = failed_runs[0]
        run_id = sample_run["id"]
        print(f"\n [+] Testing Job Log Access on Failed Run ID #{run_id}...")
        
        jobs_url = f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/jobs"
        jobs_resp = requests.get(jobs_url, headers=HEADERS)
        if jobs_resp.status_code == 200:
            jobs = jobs_resp.json().get("jobs", [])
            failed_jobs = [j for j in jobs if j.get("conclusion") == "failure"]
            print(f"     - Jobs in run: {len(jobs)} | Failed jobs: {len(failed_jobs)}")
            
            if failed_jobs:
                sample_job_id = failed_jobs[0]["id"]
                log_url = f"https://api.github.com/repos/{repo}/actions/jobs/{sample_job_id}/logs"
                log_resp = requests.head(log_url, headers=HEADERS, allow_redirects=True)
                print(f"     - Job Log HEAD Request Status: HTTP {log_resp.status_code} (200 = Available)")
        else:
            print(f"     [!] Failed to inspect jobs: HTTP {jobs_resp.status_code}")

if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("[WARNING] Running without GITHUB_TOKEN!")
    
    for repo in REPOSITORIES:
        inspect_repository(repo)