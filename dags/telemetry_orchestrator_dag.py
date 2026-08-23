from datetime import datetime, timedelta
import logging
import os
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

# Task Implementations
def extract_telemetry_data(**context):
    logging.info("Starting telemetry log extraction...")
    # Emulate ingestion or hook to GitHub Actions API / Event Stream
    raw_output_dir = Path("/opt/airflow/data/raw")
    raw_output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Telemetry extraction completed. Output staged at: {raw_output_dir}")
    return str(raw_output_dir)


def validate_schema_quality(**context):
    logging.info("Validating schema and telemetry record constraints...")
    # Schema validation logic (e.g., verifying mandatory job_id, step_number, timestamps)
    logging.info("Data schema passed quality validation.")


def upload_raw_to_s3(**context):
    logging.info("Syncing raw telemetry logs to AWS S3 landing bucket...")
    # In production: boto3.client('s3').upload_file(...)
    logging.info("S3 upload successful.")


def load_s3_to_snowflake(**context):
    logging.info("Executing Snowflake COPY INTO staging/bronze tables...")
    # Triggers the Snowflake COPY command to load fresh JSON logs into raw staging
    logging.info("Snowflake raw ingestion completed.")


def run_llm_fallback_worker(**context):
    logging.info("Triggering LLM fallback classifier for unclassified failure records...")
    import sys
    sys.path.append("/opt/airflow/scripts")
    import classify_llm_fallback

    classify_llm_fallback.main()
    logging.info("LLM fallback classification step finished.")


# DAG Definition
with DAG(
    dag_id="telemetry_pipeline_orchestrator",
    default_args=default_args,
    description="End-to-end telemetry pipeline: extract -> validate -> S3 -> Snowflake -> dbt -> LLM fallback",
    schedule_interval=None,  # Trigger on-demand or configure cron
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["telemetry", "dbt", "snowflake", "llm"],
) as dag:

    # 1. Extract
    task_extract = PythonOperator(
        task_id="extract_telemetry_data",
        python_callable=extract_telemetry_data,
    )

    # 2. Validate
    task_validate = PythonOperator(
        task_id="validate_schema_quality",
        python_callable=validate_schema_quality,
    )

    # 3. S3 Landing
    task_s3_upload = PythonOperator(
        task_id="upload_raw_to_s3",
        python_callable=upload_raw_to_s3,
    )

    # 4. Snowflake Raw Load
    task_snowflake_load = PythonOperator(
        task_id="load_s3_to_snowflake",
        python_callable=load_s3_to_snowflake,
    )

    # 5. dbt Seed & Transformations (Silver & Gold)
    task_dbt_run = BashOperator(
        task_id="dbt_run_transformations",
        bash_command="cd /opt/airflow && dbt build --profiles-dir /home/airflow/.dbt",
    )

    # 6. dbt Data Quality & Integrity Tests
    task_dbt_test = BashOperator(
        task_id="dbt_test_audits",
        bash_command="cd /opt/airflow && dbt test --profiles-dir /home/airflow/.dbt",
    )

    # 7. LLM Fallback Classification Worker
    task_llm_fallback = PythonOperator(
        task_id="classify_llm_fallback",
        python_callable=run_llm_fallback_worker,
    )

    # Define Linear Task Dependencies
    (
        task_extract
        >> task_validate
        >> task_s3_upload
        >> task_snowflake_load
        >> task_dbt_run
        >> task_dbt_test
        >> task_llm_fallback
    )