with failed_logs as (
    select * from {{ ref('stg_failed_logs') }}
),

final as (
    select
        failure_reason,
        count(distinct workflow_run_id) as affected_workflow_runs,
        count(distinct job_id) as affected_jobs,
        count(*) as total_occurrences
    from failed_logs
    where failure_reason is not null
    group by failure_reason
)

select * from final