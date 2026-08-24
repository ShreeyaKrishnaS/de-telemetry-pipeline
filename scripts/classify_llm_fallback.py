import json
import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from pydantic import BaseModel
import snowflake.connector
import yaml

load_dotenv()


class ErrorClassification(BaseModel):
    category: str
    assigned_team: str
    recommended_fix: str


def get_snowflake_connection():
    profile_path = Path.home() / ".dbt" / "profiles.yml"
    with open(profile_path, "r") as f:
        profiles = yaml.safe_load(f)

    creds = profiles["telemetry_dbt"]["outputs"]["dev"]

    return snowflake.connector.connect(
        user=creds["user"],
        password=creds["password"],
        account=creds["account"],
        warehouse=creds.get("warehouse", "TELEMETRY_WH"),
        database=creds["database"],
        schema="SILVER",
        role=creds.get("role", "ACCOUNTADMIN"),
    )


def classify_error_with_llm(client: genai.Client, failure_context: str, max_retries: int = 5) -> ErrorClassification:
    prompt = f"""
    You are an expert Senior Site Reliability Engineer / DevOps Engineer.
    Analyze the following CI/CD pipeline step failure metadata and classify it into:
    1. A short, standardized category (e.g., "Linting & Style Checks", "Unit Test Failure", "Smokeshow / Preview Build Failure", "Authentication Failure").
    2. The most appropriate engineering team to assign it to (e.g., "Frontend / QA", "Platform SRE", "Backend Engineering", "Core Maintainers").
    3. A clear, concise, actionable fix instruction for the developer.

    Failure Context:
    {failure_context}
    """

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ErrorClassification,
                    temperature=0.1,
                ),
            )
            result_dict = json.loads(response.text)
            return ErrorClassification(**result_dict)
        except ClientError as e:
            if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
                backoff_time = 15 * attempt
                print(f"    [!] Rate limit hit. Sleeping for {backoff_time}s to reset quota (Attempt {attempt}/{max_retries})...")
                time.sleep(backoff_time)
            else:
                raise e

    raise RuntimeError(f"Failed to classify error after {max_retries} attempts.")


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set in your .env file.")

    ai_client = genai.Client(api_key=api_key)
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        fetch_query = """
            SELECT job_id, step_number, failure_reason, step_name, workflow_name
            FROM TELEMETRY_DB.SILVER.fct_actionable_failures
            WHERE classification_source = 'UNCLASSIFIED_FALLBACK';
        """
        cursor.execute(fetch_query)
        unclassified_records = cursor.fetchall()

        print(f"[*] Found {len(unclassified_records)} unclassified record(s) remaining.")

        if not unclassified_records:
            print("[✓] All 27 failures are already classified!")
            return

        for job_id, step_number, failure_reason, step_name, workflow_name in unclassified_records:
            context_log = f"Workflow: {workflow_name} | Step: {step_name} | Reason: {failure_reason}"
            print(f"\nProcessing Job ID {job_id}, Step {step_number} ({step_name})...")

            classification = classify_error_with_llm(ai_client, context_log)
            print(f"  -> Predicted Category: {classification.category}")
            print(f"  -> Assigned Team:      {classification.assigned_team}")
            print(f"  -> Recommended Fix:    {classification.recommended_fix}")

            update_query = """
                UPDATE TELEMETRY_DB.SILVER.fct_actionable_failures
                SET 
                    category = %s,
                    assigned_team = %s,
                    recommended_fix = %s,
                    classification_source = 'LLM_FALLBACK'
                WHERE job_id = %s AND step_number = %s;
            """
            cursor.execute(
                update_query,
                (
                    classification.category,
                    classification.assigned_team,
                    classification.recommended_fix,
                    job_id,
                    step_number,
                ),
            )
            conn.commit()

            # 12s sleep to safely stay within the 5 requests/minute free-tier ceiling
            time.sleep(12)

        print("\n[✓] 100% of pipeline failures are classified and updated in Snowflake!")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()