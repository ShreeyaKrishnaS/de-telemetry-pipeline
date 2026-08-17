with steps as (
    select * from {{ ref('stg_steps') }}
),
jobs as (
    select * from {{ ref('stg_jobs') }}
),
workflow_runs as (
    select * from {{ ref('stg_workflow_runs') }}
),
failed_steps as (
    select 
        s.job_id,
        s.step_number,
        s.step_name,
        s.status as step_status,
        s.conclusion as step_conclusion,
        s.started_at as step_started_at,
        s.completed_at as step_completed_at,
        j.workflow_run_id,
        j.job_name,
        j.runner_name,
        w.workflow_name,
        w.head_branch,
        w.head_sha,
        w.triggered_by,
        w.event_type
    from steps s
    inner join jobs j
        on s.job_id = j.job_id
    inner join workflow_runs w
        on j.workflow_run_id = w.workflow_run_id
    where s.conclusion in ('failure', 'timed_out', 'cancelled')
       or j.conclusion in ('failure', 'timed_out', 'cancelled')
)
select * from failed_steps