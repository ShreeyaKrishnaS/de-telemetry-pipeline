with workflow_runs as (
    select * from {{ ref('stg_workflow_runs') }}
),
final as (
    select 
        workflow_name,
        head_branch,
        count(distinct workflow_run_id) as total_runs,
        min(created_at) as first_seen_at,
        max(created_at) as last_seen_at
    from workflow_runs
    group by workflow_name, head_branch
)
select * from final