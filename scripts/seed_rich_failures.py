from pathlib import Path
import snowflake.connector
import yaml

profile_path = Path.home() / ".dbt" / "profiles.yml"
creds = yaml.safe_load(open(profile_path))["telemetry_dbt"]["outputs"]["dev"]

conn = snowflake.connector.connect(
    user=creds["user"],
    password=creds["password"],
    account=creds["account"],
    warehouse=creds.get("warehouse", "TELEMETRY_WH"),
    database=creds["database"],
    schema=creds.get("schema", "SILVER"),
    role=creds.get("role", "ACCOUNTADMIN"),
)

cursor = conn.cursor()

# Diverse failure dataset covering multiple teams, rules, and LLM triage
simulated_records = [
    # 1. Deterministic Rule Match: OOM
    (1001, 2001, 1, 'build-and-test', 'unit-tests', 'run-pytest', 'gha-runner-linux-01', 'feat/auth-v2', 'c8d4e1', 'push', 'push', 
     'Process completed with exit code 137: Out of Memory (OOMKilled)', 1, 120, 'Memory Allocation', 'Platform Infrastructure', 
     'Increase container memory limits or optimize PyTorch memory footprint.', 'RULE_MATCH'),

    # 2. Deterministic Rule Match: Docker Auth
    (1002, 2002, 2, 'docker-publish', 'build-push-image', 'docker-login', 'gha-runner-linux-02', 'main', 'fa91b3', 'workflow_dispatch', 'workflow_dispatch', 
     'denied: requested access to the resource is denied: unauthorized', 1, 15, 'Authentication / Credentials', 'Security & IAM', 
     'Rotate AWS ECR token or verify GitHub Actions secrets permissions.', 'RULE_MATCH'),

    # 3. Deterministic Rule Match: Network Timeout
    (1003, 2003, 3, 'integration-pipeline', 'run-e2e', 'cypress-tests', 'gha-runner-linux-03', 'fix/db-pool', '99a4c7', 'pull_request', 'pull_request', 
     'Connection timed out after 30000ms establishing connection to postgres://telemetry-db', 2, 180, 'Network / Timeout', 'Database Ops', 
     'Verify DB security groups and connection pool timeout limits.', 'RULE_MATCH'),

    # 4. Deterministic Rule Match: Linting / Formatting
    (1004, 2004, 1, 'code-quality', 'lint-check', 'black-and-flake8', 'gha-runner-linux-04', 'feat/streaming', 'e4b110', 'pull_request', 'pull_request', 
     'flake8: E501 line too long (124 > 88 characters) in src/engine/parser.py', 3, 25, 'Code Quality / Lint', 'Software Engineering', 
     'Run `black .` locally and commit formatting changes.', 'RULE_MATCH'),

    # 5. LLM Fallback: Flaky Test Race Condition
    (1005, 2005, 4, 'nightly-regression', 'async-worker-tests', 'test_event_dispatcher', 'gha-runner-linux-05', 'main', '33b8f1', 'schedule', 'schedule', 
     'AssertionError: Expected 5 events emitted within 200ms, but received 4 due to thread lock latency', 2, 95, 'Async Thread Race Condition', 'Data Engineering', 
     'Increase concurrency lock timeouts or mock async workers in unit test suite.', 'LLM_FALLBACK'),

    # 6. LLM Fallback: Snowflake Warehouse Suspended
    (1006, 2006, 2, 'etl-sync', 'snowflake-load', 'copy-into-bronze', 'gha-runner-linux-06', 'main', '88ff02', 'workflow_dispatch', 'workflow_dispatch', 
     '000606 (57P03): Warehouse TELEMETRY_WH is suspended or queue capacity exceeded during copy', 1, 40, 'Data Warehouse Quota / Capacity', 'Data Engineering', 
     'Configure AUTO_RESUME = TRUE on TELEMETRY_WH or resize to Medium.', 'LLM_FALLBACK')
]

insert_sql = """
INSERT INTO fct_actionable_failures (
    workflow_run_id, job_id, step_number, workflow_name, job_name, step_name,
    runner_name, head_branch, head_sha, triggered_by, event_type,
    failure_reason, priority, failed_step_duration_seconds,
    category, assigned_team, recommended_fix, classification_source
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

cursor.executemany(insert_sql, simulated_records)
conn.commit()
print(f"Successfully inserted {len(simulated_records)} rich telemetry failure records!")

cursor.close()
conn.close()