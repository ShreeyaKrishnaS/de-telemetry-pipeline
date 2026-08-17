with workflow_runs as (
    select * from {{ ref('stg_workflow_runs') }}
),
jobs as (
    select * from {{ ref('stg_jobs') }}
),
job_aggregates as (
    select 
        workflow_run_id,
        count(job_id) as total_jobs,
        count(case when conclusion = 'success' then 1 end) as successful_jobs,
        count(case when conclusion in ('failure', 'timed_out', 'cancelled') then 1 end) as failed_jobs,
        min(started_at) as first_job_started_at,
        max(completed_at) as last_job_completed_at 
    from jobs 
    group by workflow_run_id
),
final as (
    select 
        w.workflow_run_id,
        w.workflow_name,
        w.head_branch,
        w.head_sha,
        w.event_type,
        w.status,
        w.conclusion,
        w.triggered_by,
        w.run_attempt,
        w.created_at,
        w.updated_at,
        j.total_jobs,
        coalesce(j.successful_jobs, 0) as successful_jobs,
        coalesce(j.failed_jobs, 0) as failed_jobs,
        j.first_job_started_at,
        j.last_job_completed_at,
        datediff('second', j.first_job_started_at, j.last_job_completed_at) as total_execution_duration_seconds,
        case 
            when coalesce(j.failed_jobs, 0) > 0 then true
            else false
        end as has_job_failure
    from workflow_runs w
    left join job_aggregates j 
        on w.workflow_run_id = j.workflow_run_id
)
select * from final