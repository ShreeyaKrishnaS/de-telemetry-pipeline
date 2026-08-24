import os
import glob
import yaml
from pathlib import Path
import snowflake.connector

def get_snowflake_conn():
    profile_path = Path.home() / ".dbt" / "profiles.yml"
    creds = yaml.safe_load(open(profile_path))["telemetry_dbt"]["outputs"]["dev"]
    return snowflake.connector.connect(
        user=creds["user"],
        password=creds["password"],
        account=creds["account"],
        warehouse=creds.get("warehouse", "TELEMETRY_WH"),
        database=creds["database"],
        schema="BRONZE",
        role=creds.get("role", "ACCOUNTADMIN")
    )

def load_local_lake_to_bronze():
    conn = get_snowflake_conn()
    cursor = conn.cursor()

    # 1. Create Stage and Table
    cursor.execute("CREATE STAGE IF NOT EXISTS TELEMETRY_DB.BRONZE.LAKE_INTERNAL_STAGE;")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS TELEMETRY_DB.BRONZE.WORKFLOW_RUNS_RAW (
        raw_payload VARIANT,
        source_file_name VARCHAR,
        loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
    );
    """)

    # 2. Put local .jsonl.gz files into Snowflake Stage
    files = glob.glob("data/raw/**/workflow_runs/**/*.jsonl.gz", recursive=True)
    print(f"[*] Found {len(files)} raw partitioned data files. Uploading to Snowflake internal stage...")

    for file_path in files:
        clean_path = os.path.abspath(file_path).replace("\\", "/")
        put_cmd = f"PUT 'file://{clean_path}' @TELEMETRY_DB.BRONZE.LAKE_INTERNAL_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE;"
        cursor.execute(put_cmd)

    # 3. Create temporary landing table to parse JSON array
    cursor.execute("""
    CREATE OR REPLACE TEMPORARY TABLE TELEMETRY_DB.BRONZE.TMP_ENVELOPES (
        envelope VARIANT,
        source_file_name VARCHAR
    );
    """)

    # 4. Copy raw GZIP JSONL into temporary landing table
    cursor.execute("""
    COPY INTO TELEMETRY_DB.BRONZE.TMP_ENVELOPES
    FROM (
        SELECT $1, METADATA$FILENAME
        FROM @TELEMETRY_DB.BRONZE.LAKE_INTERNAL_STAGE
    )
    FILE_FORMAT = (TYPE = 'JSON');
    """)

    # 5. Flatten array envelope and Idempotently MERGE into Bronze
    merge_sql = """
    MERGE INTO TELEMETRY_DB.BRONZE.WORKFLOW_RUNS_RAW AS target
    USING (
        SELECT 
            f.value AS raw_payload,
            t.source_file_name AS source_file_name,
            f.value:id::STRING AS run_id,
            COALESCE(f.value:run_attempt::STRING, '1') AS run_attempt
        FROM TELEMETRY_DB.BRONZE.TMP_ENVELOPES t,
             LATERAL FLATTEN(input => t.envelope:data) f
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY f.value:id::STRING, COALESCE(f.value:run_attempt::STRING, '1')
            ORDER BY f.value:updated_at::TIMESTAMP_NTZ DESC NULLS LAST
        ) = 1
    ) AS source
    ON target.raw_payload:id::STRING = source.run_id
       AND COALESCE(target.raw_payload:run_attempt::STRING, '1') = source.run_attempt
    WHEN MATCHED THEN
        UPDATE SET 
            target.raw_payload = source.raw_payload,
            target.source_file_name = source.source_file_name,
            target.loaded_at = CURRENT_TIMESTAMP()
    WHEN NOT MATCHED THEN
        INSERT (raw_payload, source_file_name, loaded_at)
        VALUES (source.raw_payload, source.source_file_name, CURRENT_TIMESTAMP());
    """
    cursor.execute(merge_sql)
    conn.commit()

    # 6. Audit Row Counts
    cursor.execute("""
    SELECT 
        COUNT(*) AS total_rows,
        COUNT(DISTINCT raw_payload:id::STRING || '_' || COALESCE(raw_payload:run_attempt::STRING, '1')) AS distinct_keys
    FROM TELEMETRY_DB.BRONZE.WORKFLOW_RUNS_RAW;
    """)
    total_rows, distinct_keys = cursor.fetchone()
    print(f"[✓] Ingestion Complete! Total Bronze Rows: {total_rows} | Distinct Composite Keys: {distinct_keys}")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    load_local_lake_to_bronze()