-- Power BI semantic-model views.
-- Run after schema.sql and data_import.sql.

SET search_path TO healthcare_analytics, public;

CREATE OR REPLACE VIEW vw_dim_hospital AS
SELECT DISTINCT
    provider_ccn,
    provider_name,
    provider_street_address,
    provider_city,
    provider_state_fips,
    provider_state_abbreviation,
    provider_zip5,
    provider_ruca,
    provider_ruca_description,
    CASE
        WHEN provider_ruca BETWEEN 1 AND 3.99 THEN 'Urban'
        WHEN provider_ruca BETWEEN 4 AND 10.99 THEN 'Rural'
        ELSE 'Unknown'
    END AS rural_urban_group
FROM inpatient_hospital_services;

CREATE OR REPLACE VIEW vw_dim_drg AS
SELECT DISTINCT
    drg_code,
    drg_description,
    'DRG ' || drg_code || ' - ' || drg_description AS drg_label
FROM inpatient_hospital_services;

CREATE OR REPLACE VIEW vw_fact_hospital_drg AS
SELECT
    service_record_id,
    provider_ccn,
    drg_code,
    total_discharges,
    avg_submitted_covered_charge,
    avg_total_payment_amount,
    avg_medicare_payment_amount,
    payment_gap,
    medicare_payment_gap,
    total_payment_coverage_pct,
    medicare_coverage_pct,
    estimated_submitted_charges,
    estimated_total_payments,
    estimated_medicare_payments,
    charge_to_total_payment_ratio
FROM inpatient_hospital_services;

COMMENT ON VIEW vw_dim_hospital IS
    'One row per hospital for Power BI filtering and geographic analysis.';
COMMENT ON VIEW vw_dim_drg IS
    'One row per DRG for Power BI filtering and service-line analysis.';
COMMENT ON VIEW vw_fact_hospital_drg IS
    'Hospital-DRG fact view containing volume and approved financial metrics.';

-- Expected validation results: 2,906 hospitals, 540 DRGs, 145,879 fact rows.
SELECT
    (SELECT COUNT(*) FROM vw_dim_hospital) AS hospital_dimension_rows,
    (SELECT COUNT(*) FROM vw_dim_drg) AS drg_dimension_rows,
    (SELECT COUNT(*) FROM vw_fact_hospital_drg) AS fact_rows,
    (SELECT SUM(total_discharges) FROM vw_fact_hospital_drg)
        AS total_discharges;
