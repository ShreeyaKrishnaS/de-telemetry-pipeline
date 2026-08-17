with workflow_runs as (
    select * from {{ ref('stg_workflow_runs') }}
),

final as (
    select
        head_sha,
        head_branch,
        triggered_by,
        count(distinct workflow_run_id) as total_runs,
        min(created_at) as first_commit_run_at,
        max(created_at) as last_commit_run_at
    from workflow_runs
    where head_sha is not null
    group by head_sha, head_branch, triggered_by
)

select * from final