-- Run from the project root with psql after running sql/schema.sql.
-- Default:
--   psql -d healthcare_operations -f sql/data_import.sql
-- Run this file while the current directory is the project root so the
-- project-relative CSV path below resolves correctly.

\set ON_ERROR_STOP on

\echo Using project-relative CSV path: data/processed/healthcare_operations_clean.csv

BEGIN;

TRUNCATE TABLE healthcare_analytics.inpatient_hospital_services
    RESTART IDENTITY;

-- psql requires the entire \copy meta-command to remain on one physical line.
\copy healthcare_analytics.inpatient_hospital_services (provider_ccn, provider_name, provider_city, provider_street_address, provider_state_fips, provider_zip5, provider_state_abbreviation, provider_ruca, provider_ruca_description, drg_code, drg_description, total_discharges, avg_submitted_covered_charge, avg_total_payment_amount, avg_medicare_payment_amount, payment_gap, medicare_payment_gap, total_payment_coverage_pct, medicare_coverage_pct, estimated_submitted_charges, estimated_total_payments, estimated_medicare_payments, charge_to_total_payment_ratio) FROM 'data/processed/healthcare_operations_clean.csv' WITH (FORMAT CSV, HEADER TRUE, ENCODING 'UTF8');

COMMIT;

ANALYZE healthcare_analytics.inpatient_hospital_services;

-- Import validation: expected row count is 145,879 for the current source file.
SELECT
    COUNT(*) AS imported_rows,
    COUNT(DISTINCT provider_ccn) AS hospitals,
    COUNT(DISTINCT drg_code) AS drgs,
    COUNT(DISTINCT provider_state_abbreviation) AS states_and_territories,
    SUM(total_discharges) AS total_discharges
FROM healthcare_analytics.inpatient_hospital_services;

SELECT
    COUNT(*) FILTER (WHERE total_discharges <= 0) AS invalid_discharges,
    COUNT(*) FILTER (WHERE avg_submitted_covered_charge < 0) AS negative_charges,
    COUNT(*) FILTER (WHERE avg_total_payment_amount < 0) AS negative_total_payments,
    COUNT(*) FILTER (WHERE avg_medicare_payment_amount < 0) AS negative_medicare_payments,
    COUNT(*) FILTER (WHERE charge_to_total_payment_ratio IS NULL) AS undefined_ratios
FROM healthcare_analytics.inpatient_hospital_services;
