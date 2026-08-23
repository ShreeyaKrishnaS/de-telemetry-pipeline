from pathlib import Path
import snowflake.connector
import yaml

profile_path = Path.home() / ".dbt" / "profiles.yml"
creds = yaml.safe_load(open(profile_path))["telemetry_dbt"]["outputs"]["dev"]

conn = snowflake.connector.connect(
    user=creds["user"],
    password=creds["password"],
    account=creds["account"],
    warehouse=creds.get("warehouse", "COMPUTE_WH"),
    database=creds["database"],
    schema=creds.get("schema", "SILVER"),
    role=creds.get("role", "SYSADMIN"),
)

cursor = conn.cursor()

insert_stmt = """
INSERT INTO fct_actionable_failures (
    workflow_run_id,
    job_id,
    step_number,
    workflow_name,
    job_name,
    step_name,
    runner_name,
    head_branch,
    head_sha,
    triggered_by,
    event_type,
    step_started_at,
    step_completed_at,
    failure_reason,
    priority,
    failed_step_duration_seconds,
    category,
    assigned_team,
    recommended_fix,
    classification_source
) VALUES (
    999999,
    888888,
    1,
    'deploy-prod',
    'deploy-kubernetes',
    'apply-manifests',
    'k8s-runner-01',
    'main',
    'a1b2c3d4e5f6',
    'push',
    'workflow_dispatch',
    CURRENT_TIMESTAMP(),
    CURRENT_TIMESTAMP(),
    'Error: Pod evicted due to ephemeral-storage limit exceeded: usage 12Gi exceeds limit 10Gi on node-pool-prod-3',
    99,
    45,
    'unclassified',
    'platform Triage',
    'Inspect raw runner logs',
    'UNCLASSIFIED_FALLBACK'
);
"""

cursor.execute(insert_stmt)
conn.commit()
print("Successfully inserted simulated unclassified test row into Snowflake!")

cursor.close()
conn.close()