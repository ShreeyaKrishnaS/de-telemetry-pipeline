with source as (
    select * from {{ source('bronze', 'workflow_runs_raw') }}
),

flattened_jobs as (
    select
        r.raw_payload:id::number as workflow_run_id,
        j.value:id::number as job_id,
        j.value:name::varchar as job_name,
        j.value:status::varchar as status,
        j.value:conclusion::varchar as conclusion,
        j.value:started_at::timestamp_ntz as started_at,
        j.value:completed_at::timestamp_ntz as completed_at,
        j.value:runner_name::varchar as runner_name,
        j.value:steps as raw_steps_array,
        r.source_file_name,
        r.loaded_at
    from source r,
    lateral flatten(input => r.raw_payload:jobs, outer => true) j
)

select * from flattened_jobs
where job_id is not null