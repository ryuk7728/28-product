-- Replace PROJECT_ID and DATASET_ID before execution.
WITH identities AS (
  SELECT
    policy_id,
    canonical_key_id,
    sample_index,
    COUNT(*) AS row_count,
    COUNT(DISTINCT result_id) AS distinct_result_count
  FROM `PROJECT_ID.DATASET_ID.results`
  GROUP BY policy_id, canonical_key_id, sample_index
),
key_counts AS (
  SELECT
    policy_id,
    canonical_key_id,
    COUNT(*) AS slot_count,
    COUNTIF(status = 'COMPLETED') AS completed_count,
    COUNTIF(status = 'REDEAL') AS redeal_count,
    COUNTIF(status = 'ABORT') AS abort_count
  FROM `PROJECT_ID.DATASET_ID.results`
  GROUP BY policy_id, canonical_key_id
)
SELECT
  (SELECT COUNT(*) FROM `PROJECT_ID.DATASET_ID.results`) AS total_rows,
  (SELECT COUNT(DISTINCT result_id) FROM `PROJECT_ID.DATASET_ID.results`) AS unique_results,
  (SELECT COUNTIF(row_count > 1 OR distinct_result_count > 1) FROM identities) AS duplicate_slots,
  (SELECT COUNTIF(slot_count != 100) FROM key_counts) AS keys_without_100_slots,
  (SELECT COUNT(*) FROM key_counts) AS represented_keys;
