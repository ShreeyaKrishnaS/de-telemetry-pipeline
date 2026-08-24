with source as (
    select * from {{ source('bronze', 'workflow_runs_raw') }}
),

flattened_jobs as (
    select
        r.raw_payload:id::number as workflow_run_id,
        coalesce(j.value:id::number, r.raw_payload:id::number) as job_id,
        coalesce(j.value:name::varchar, r.raw_payload:name::varchar, 'Default Job') as job_name,
        coalesce(j.value:status::varchar, r.raw_payload:status::varchar) as status,
        coalesce(j.value:conclusion::varchar, r.raw_payload:conclusion::varchar) as conclusion,
        coalesce(j.value:started_at::timestamp_ntz, r.raw_payload:run_started_at::timestamp_ntz) as started_at,
        coalesce(j.value:completed_at::timestamp_ntz, r.raw_payload:updated_at::timestamp_ntz) as completed_at,
        coalesce(j.value:runner_name::varchar, 'GitHub Hosted Runner') as runner_name,
        coalesce(j.value:steps, array_construct(
            object_construct(
                'number', 1,
                'name', coalesce(r.raw_payload:name::varchar, 'Workflow Execution'),
                'status', r.raw_payload:status::varchar,
                'conclusion', r.raw_payload:conclusion::varchar,
                'started_at', r.raw_payload:run_started_at::varchar,
                'completed_at', r.raw_payload:updated_at::varchar
            )
        )) as raw_steps_array,
        r.source_file_name,
        r.loaded_at
    from source r,
    lateral flatten(input => coalesce(r.raw_payload:jobs, array_construct(object_construct())), outer => true) j
)

select * from flattened_jobs
where job_id is not null