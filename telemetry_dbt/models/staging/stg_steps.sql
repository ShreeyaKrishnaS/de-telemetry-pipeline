with jobs as (
    select * from {{ ref('stg_jobs') }}
),

flattened_steps as (
    select
        j.job_id,
        j.workflow_run_id,
        s.value:number::number as step_number,
        s.value:name::varchar as step_name,
        s.value:status::varchar as status,
        s.value:conclusion::varchar as conclusion,
        s.value:started_at::timestamp_ntz as started_at,
        s.value:completed_at::timestamp_ntz as completed_at,
        datediff(
            'second',
            s.value:started_at::timestamp_ntz,
            s.value:completed_at::timestamp_ntz
        ) as duration_seconds
    from jobs j,
    lateral flatten(input => j.raw_steps_array, outer => true) s
)

select * from flattened_steps
where step_number is not null