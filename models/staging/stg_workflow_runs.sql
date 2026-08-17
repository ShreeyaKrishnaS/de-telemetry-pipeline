with source as (
    select * from {{ source('bronze', 'workflow_runs_raw') }}
),

flattened as (
    select
        raw_payload:id::number as workflow_run_id,
        raw_payload:name::varchar as workflow_name,
        raw_payload:head_branch::varchar as head_branch,
        raw_payload:head_sha::varchar as head_sha,
        raw_payload:event::varchar as event_type,
        raw_payload:status::varchar as status,
        raw_payload:conclusion::varchar as conclusion,
        raw_payload:actor.login::varchar as triggered_by,
        raw_payload:created_at::timestamp_ntz as created_at,
        raw_payload:updated_at::timestamp_ntz as updated_at,
        raw_payload:run_attempt::number as run_attempt,
        source_file_name,
        loaded_at
    from source
)

select * from flattened
where workflow_run_id is not null