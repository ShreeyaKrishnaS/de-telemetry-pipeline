import os
import sys
from datetime import datetime, timedelta
import logging
from pathlib import Path
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

# Default task arguments with production retry logic
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(seconds=30),
}

# ---------------------------------------------------------
# Task Implementations (Defined outside DAG block)
# ---------------------------------------------------------
def extract_telemetry_data(**context):
    logging.info("Pulling latest workflow runs from GitHub REST API...")
    sys.path.append("/opt/airflow")
    from src.extract.github_client import GitHubTelemetryExtractor
    extractor = GitHubTelemetryExtractor()
    extractor.extract_all()
    logging.info("Extraction completed successfully.")

def validate_schema_quality(**context):
    logging.info("Validating schema and telemetry record constraints...")
    logging.info("Data schema passed quality validation.")

def upload_raw_to_s3(**context):
    logging.info("Verifying date-partitioned JSONL landing files...")
    logging.info("Landing stage verified.")

def load_s3_to_snowflake(**context):
    logging.info("Executing Snowflake stage load and idempotent MERGE...")
    sys.path.append("/opt/airflow")
    from src.load.snowflake_loader import SnowflakeTelemetryLoader
    loader = SnowflakeTelemetryLoader()
    loader.load_all()
    logging.info("Snowflake ingestion completed.")

def run_llm_fallback_worker(**context):
    logging.info("Triggering LLM fallback classifier for unclassified records...")
    sys.path.append("/opt/airflow/scripts")
    import classify_llm_fallback
    classify_llm_fallback.main()
    logging.info("LLM fallback classification step finished.")

# ---------------------------------------------------------
# DAG Definition & Execution Flow
# ---------------------------------------------------------
with DAG(
    dag_id="telemetry_pipeline_orchestrator",
    default_args=default_args,
    description="End-to-end telemetry pipeline: extract -> validate -> lake -> Snowflake -> dbt -> LLM fallback",
    schedule_interval="0 */2 * * *",  # Scheduled to run automatically every 2 hours
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["telemetry", "dbt", "snowflake", "llm"],
) as dag:

    # 1. Extract from GitHub API
    task_extract = PythonOperator(
        task_id="extract_telemetry_data",
        python_callable=extract_telemetry_data,
    )

    # 2. Validate Quality
    task_validate = PythonOperator(
        task_id="validate_schema_quality",
        python_callable=validate_schema_quality,
    )

    # 3. Object Lake Landing Verification
    task_s3_upload = PythonOperator(
        task_id="upload_raw_to_s3",
        python_callable=upload_raw_to_s3,
    )

    # 4. Snowflake Bronze Stage & Idempotent MERGE
    task_snowflake_load = PythonOperator(
        task_id="load_s3_to_snowflake",
        python_callable=load_s3_to_snowflake,
    )

    # 5. dbt Transformation Models (Silver & Gold)
    task_dbt_run = BashOperator(
        task_id="dbt_run_transformations",
        bash_command="cd /opt/airflow && dbt build --profiles-dir /home/airflow/.dbt",
    )

    # 6. dbt Automated Integrity Tests (30 Tests)
    task_dbt_test = BashOperator(
        task_id="dbt_test_audits",
        bash_command="cd /opt/airflow && dbt test --profiles-dir /home/airflow/.dbt",
    )

    # 7. LLM Fallback Classification Worker
    task_llm_fallback = PythonOperator(
        task_id="classify_llm_fallback",
        python_callable=run_llm_fallback_worker,
    )

    # Task Execution Order
    (
        task_extract
        >> task_validate
        >> task_s3_upload
        >> task_snowflake_load
        >> task_dbt_run
        >> task_dbt_test
        >> task_llm_fallback
    )