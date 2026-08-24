with logs as (
    select
        job_id,
        step_number,
        step_name,
        step_status,
        step_conclusion,
        step_started_at,
        step_completed_at
    from {{ ref('fct_step_executions') }}
),

failed_logs as (
    select 
        workflow_run_id,
        job_id,
        step_number,
        workflow_name,
        job_name,
        step_name,
        failure_reason,
        priority,
        category,
        assigned_team,
        recommended_fix
    from {{ ref('fct_actionable_failures') }}
),

test_logs as (
    select
        l.job_id,
        l.step_number,
        l.step_name,
        l.step_status,
        l.step_conclusion,
        l.step_started_at,
        l.step_completed_at,
        f.workflow_run_id,
        f.failure_reason,
        f.category,
        f.assigned_team,
        f.recommended_fix
    from logs l
    join failed_logs f
        on l.job_id = f.job_id 
       and l.step_number = f.step_number
)

select * 
from test_logs
where lower(coalesce(step_status, '')) = 'success' 
   or lower(coalesce(step_conclusion, '')) = 'success'