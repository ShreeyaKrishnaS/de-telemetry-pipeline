with failure_events as (
    select * from {{ ref('int_failure_events') }}
),

classified as (
    select
        fe.workflow_run_id,
        fe.job_id,
        fe.step_number,
        fe.step_name,
        fe.job_name,
        fe.workflow_name,
        fe.head_branch,
        fe.head_sha,
        fe.triggered_by,
        fe.event_type,
        fe.step_started_at,
        fe.step_completed_at,
        coalesce(fe.step_conclusion, 'failure') as failure_reason,

        -- 1. Deterministic Rule Matching (SQL Level)
        case
            when lower(coalesce(fe.step_name, '')) like '%pre-commit%' 
              or lower(coalesce(fe.workflow_name, '')) like '%lint%' 
              or lower(coalesce(fe.job_name, '')) like '%pre-commit%'
                then 'Linting & Style Checks'
            when lower(coalesce(fe.step_name, '')) like '%test%' 
              or lower(coalesce(fe.workflow_name, '')) like '%test%' 
              or lower(coalesce(fe.job_name, '')) like '%test%'
                then 'Unit Test Failure'
            when lower(coalesce(fe.step_name, '')) like '%smoke%' 
              or lower(coalesce(fe.workflow_name, '')) like '%smoke%' 
              or lower(coalesce(fe.job_name, '')) like '%smoke%'
                then 'Smokeshow / Preview Build Failure'
            else 'UNCLASSIFIED_FALLBACK'
        end as category,

        -- 2. Assigned Engineering Team
        case
            when lower(coalesce(fe.step_name, '')) like '%pre-commit%' 
              or lower(coalesce(fe.workflow_name, '')) like '%lint%' 
              or lower(coalesce(fe.job_name, '')) like '%pre-commit%'
                then 'Core Maintainers'
            when lower(coalesce(fe.step_name, '')) like '%test%' 
              or lower(coalesce(fe.workflow_name, '')) like '%test%' 
              or lower(coalesce(fe.job_name, '')) like '%test%'
                then 'Backend Engineering'
            when lower(coalesce(fe.step_name, '')) like '%smoke%' 
              or lower(coalesce(fe.workflow_name, '')) like '%smoke%' 
              or lower(coalesce(fe.job_name, '')) like '%smoke%'
                then 'Frontend / QA'
            else 'Platform Triage'
        end as assigned_team,

        -- 3. Recommended Remediation Fix
        case
            when lower(coalesce(fe.step_name, '')) like '%pre-commit%' 
              or lower(coalesce(fe.workflow_name, '')) like '%lint%' 
              or lower(coalesce(fe.job_name, '')) like '%pre-commit%'
                then 'Run `pre-commit run --all-files` locally to auto-fix code formatting and linting hook failures.'
            when lower(coalesce(fe.step_name, '')) like '%test%' 
              or lower(coalesce(fe.workflow_name, '')) like '%test%' 
              or lower(coalesce(fe.job_name, '')) like '%test%'
                then 'Inspect test execution logs for assertion failures, reproduce locally with pytest, and patch regression.'
            when lower(coalesce(fe.step_name, '')) like '%smoke%' 
              or lower(coalesce(fe.workflow_name, '')) like '%smoke%' 
              or lower(coalesce(fe.job_name, '')) like '%smoke%'
                then 'Verify SMOKESHOW credentials in repository secrets and validate build artifact output directory.'
            else 'Inspect execution logs for failure context.'
        end as recommended_fix,

        -- 4. Classification Source Tag
        case
            when lower(coalesce(fe.step_name, '')) like '%pre-commit%' 
              or lower(coalesce(fe.step_name, '')) like '%test%' 
              or lower(coalesce(fe.step_name, '')) like '%smoke%'
                then 'DETERMINISTIC_RULE'
            else 'UNCLASSIFIED_FALLBACK'
        end as classification_source,

        case
            when lower(coalesce(fe.step_name, '')) like '%test%' then 1
            else 2
        end as priority

    from failure_events fe
)

select * from classified