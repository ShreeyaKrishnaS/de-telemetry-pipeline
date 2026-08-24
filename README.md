# CI/CD Telemetry Lakehouse & Automated Failure Intelligence

An end-to-end data lakehouse pipeline orchestrating the ingestion, warehousing, dimensional transformation, and AI-assisted classification of CI/CD build telemetry from GitHub Actions into Snowflake and dbt Core.

---

## Architecture Overview

```text
  [GitHub Actions REST API]
              │
              ▼ (Python Requests + Rate Limiting)
     [Raw Ingestion Layer] ──► Date-Partitioned JSONL Lake (.jsonl.gz)
              │
              ▼ (Snowflake Stage + Idempotent MERGE)
  [Snowflake Bronze (Raw)]
              │
              ▼ (dbt Core Transformations & 30 Automated Tests)
  [Snowflake Silver (Cleaned)]
              │
              ├──► [Snowflake Gold (Marts / Star Schema)]
              │            │
              │            ▼
              │   [Streamlit Observability Dashboard]
              │
              ▼ (Deterministic Rules + Gemini API Fallback)
    [Actionable Failure & Triage Layer]
```

---

## Tech Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Ingestion** | Python 3.11, Requests | GitHub REST API extraction, pagination, and log staging |
| **Storage & Lake** | JSONL, Gzip | Partitioned file landing and raw archive |
| **Data Warehouse** | Snowflake | Bronze staging, MERGE statements, and analytical storage |
| **Transformation** | dbt Core 1.8+ | 11 Medallion models (Staging, Intermediate, Marts) |
| **Data Quality** | dbt Test | 30 automated schema, uniqueness, and referential tests |
| **Intelligence** | Gemini 1.5 Flash API | Fallback log classification and automated fix recommendations |
| **Orchestration** | Apache Airflow 2.8+ | Dockerized multi-stage DAG running bi-hourly |
| **Visualization** | Streamlit | Dark-mode Failure Intelligence and build health dashboard |

---

## Data Modeling (Medallion Architecture)

* **Bronze Layer (`RAW`):** Idempotent ingestion of raw workflow runs, jobs, and step execution logs.
* **Silver Layer (`SILVER`):** Type-casting, surrogate key generation, and timestamp normalization (`stg_workflow_runs`, `stg_jobs`, `stg_steps`, `stg_failed_logs`).
* **Gold Layer (`GOLD`):** Star-schema dimensional marts (`dim_repositories`, `dim_commits`, `dim_error_categories`, `fct_workflow_runs`, `fct_step_executions`, `fct_actionable_failures`).

---

## Key Features

1. **Idempotent ELT Ingestion:** Safe backfill and incremental merge logic in Snowflake preventing duplicate workflow runs.
2. **Hybrid Failure Classification:** Combines deterministic SQL regex rules with LLM fallback categorization to classify stack traces and route incidents to responsible teams (DevOps, Data Platform, QA).
3. **100% Automated Test Pass Rate:** 30 comprehensive dbt tests verifying null constraints, primary key uniqueness, and cross-table foreign key relationships.
4. **Live Operational Dashboard:** Streamlit UI providing pass rate analytics, step duration distributions, and actionable failure drill-downs.

---

## Local Setup & Quickstart

### 1. Clone & Configure Environment
```bash
git clone https://github.com/ShreeyaKrishnaS/de-telemetry-pipeline.git
cd de-telemetry-pipeline
cp .env.example .env
```

### 2. Launch Services with Docker Compose
```bash
docker-compose up -d
```

### 3. Run dbt Build & Test
```bash
dbt build
dbt test
```

### 4. Launch Streamlit Dashboard
```bash
streamlit run app.py
```
