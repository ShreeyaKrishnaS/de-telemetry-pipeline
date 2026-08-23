with failure_events as (
    select * from {{ ref('int_failure_events') }}
),

failed_logs as (
    select * from {{ ref('stg_failed_logs') }}
),

failure_base as (
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
        coalesce(l.failure_reason, f.step_conclusion,'Uknown Failure') as failure_reason,
        l.duration_seconds as failed_step_duration_seconds
    from failure_events f
    left join failed_logs l
        on f.job_id = l.job_id
        and f.step_number = l.step_number
),

error_classifications as (
    select error_pattern,
    category,
    assigned_team,
    priority,
    recommended_fix 
    from {{ref('error_classification_rules')}}
),
matched_errors as (
   select 
   f.*,
    e.error_pattern,
    e.category,
    e.assigned_team,
    e.priority,
    e.recommended_fix,
    row_number()over(
        partition by f.job_id, f.step_number
        order by e.priority asc
    ) as rank_num
    from failure_base f
    left join error_classifications e
    on f.failure_reason ILIKE e.error_pattern

)
select 
workflow_run_id,
job_id,
step_number,
workflow_name,
job_name,
step_name,
runner_name,
head_branch,
head_sha,
triggered_by,
event_type,
step_started_at,
step_completed_at,
failure_reason,
priority,
failed_step_duration_seconds,
coalesce(category,'unclassified') as category,
coalesce(assigned_team,'platform Triage') as assigned_team,
coalesce(recommended_fix,'Inspect raw runner logs') as recommended_fix,
case
when category is not null then 'RULE_MATCH'
else 'UNCLASSIFIED_FALLBACK'
end as classification_source
from matched_errors 
where rank_num = 1
 