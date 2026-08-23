import json
import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel
import snowflake.connector
import yaml

# Load Gemini API key from .env file
load_dotenv()


class ErrorClassification(BaseModel):
    category: str
    assigned_team: str
    recommended_fix: str


def get_snowflake_connection():
    # Automatically read credentials from dbt profiles.yml
    profile_path = Path.home() / ".dbt" / "profiles.yml"

    with open(profile_path, "r") as f:
        profiles = yaml.safe_load(f)

    creds = profiles["telemetry_dbt"]["outputs"]["dev"]

    return snowflake.connector.connect(
        user=creds["user"],
        password=creds["password"],
        account=creds["account"],
        warehouse=creds.get("warehouse", "COMPUTE_WH"),
        database=creds["database"],
        schema=creds.get("schema", "SILVER"),
        role=creds.get("role", "SYSADMIN"),
    )


def classify_error_with_llm(client: genai.Client, failure_reason: str) -> ErrorClassification:
    prompt = f"""
    You are an expert Senior Site Reliability Engineer / DevOps Engineer.
    Analyze the following CI/CD pipeline step failure log and classify it into:
    1. A short, standardized category (e.g., "Memory Exhaustion", "Authentication Failure", "Syntax Error", "Disk Space Exhaustion").
    2. The most appropriate engineering team to assign it to (e.g., "Backend Team", "DevOps / SRE", "Platform Engineering", "Security Team").
    3. A clear, concise, actionable fix instruction for the developer.

    Failure Log:
    {failure_reason}
    """

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


def main():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set in your .env file.")

    ai_client = genai.Client(api_key=api_key)
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    try:
        fetch_query = """
            SELECT job_id, step_number, failure_reason
            FROM fct_actionable_failures
            WHERE classification_source = 'UNCLASSIFIED_FALLBACK';
        """
        cursor.execute(fetch_query)
        unclassified_records = cursor.fetchall()

        print(f"Found {len(unclassified_records)} unclassified record(s) to process.")

        if not unclassified_records:
            print("All failures are already classified via deterministic rules.")
            return

        for job_id, step_number, failure_reason in unclassified_records:
            print(f"\nProcessing Job ID {job_id}, Step {step_number}...")
            print(f"Log: {failure_reason[:80]}...")

            classification = classify_error_with_llm(ai_client, failure_reason)
            print(f"  -> Predicted Category: {classification.category}")
            print(f"  -> Assigned Team:     {classification.assigned_team}")
            print(f"  -> Recommended Fix:   {classification.recommended_fix}")

            update_query = """
                UPDATE fct_actionable_failures
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

        print("\nLLM Fallback classification completed successfully!")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()