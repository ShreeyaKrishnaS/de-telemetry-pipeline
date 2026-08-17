with steps as (
    select * from {{ ref('stg_steps') }}
)

select
    workflow_run_id,
    job_id,
    step_number,
    step_name,
    conclusion as failure_reason,
    duration_seconds,
    started_at,
    completed_at
from steps
where conclusion not in ('success', 'skipped')
   or (conclusion is null and status = 'failure')