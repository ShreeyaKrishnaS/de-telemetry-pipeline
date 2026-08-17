with failure_events as (
    select * from {{ ref('int_failure_events') }}
),

failed_logs as (
    select * from {{ ref('stg_failed_logs') }}
),

final as (
    select
        f.workflow_run_id,
        f.job_id,
        f.step_number,
        f.workflow_name,
        f.job_name,
        f.step_name,
        f.runner_name,
        f.head_branch,
        f.head_sha,
        f.triggered_by,
        f.event_type,
        f.step_started_at,
        f.step_completed_at,
        l.failure_reason,
        l.duration_seconds as failed_step_duration_seconds
    from failure_events f
    left join failed_logs l
        on f.job_id = l.job_id
        and f.step_number = l.step_number
)

select * from final