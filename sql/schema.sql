-- Healthcare Operations Intelligence Platform
-- PostgreSQL schema for the cleaned CMS hospital-DRG analytical dataset.

CREATE SCHEMA IF NOT EXISTS healthcare_analytics;

DROP TABLE IF EXISTS healthcare_analytics.inpatient_hospital_services;

CREATE TABLE healthcare_analytics.inpatient_hospital_services (
    service_record_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_ccn CHAR(6) NOT NULL,
    provider_name VARCHAR(50) NOT NULL,
    provider_city VARCHAR(20) NOT NULL,
    provider_street_address VARCHAR(43) NOT NULL,
    provider_state_fips CHAR(2) NOT NULL,
    provider_zip5 CHAR(5) NOT NULL,
    provider_state_abbreviation CHAR(2) NOT NULL,
    provider_ruca NUMERIC(4, 1) NOT NULL,
    provider_ruca_description VARCHAR(100) NOT NULL,
    drg_code CHAR(3) NOT NULL,
    drg_description VARCHAR(88) NOT NULL,
    total_discharges INTEGER NOT NULL,
    avg_submitted_covered_charge NUMERIC(16, 8) NOT NULL,
    avg_total_payment_amount NUMERIC(16, 8) NOT NULL,
    avg_medicare_payment_amount NUMERIC(16, 8) NOT NULL,
    payment_gap NUMERIC(16, 8) NOT NULL,
    medicare_payment_gap NUMERIC(16, 8) NOT NULL,
    total_payment_coverage_pct NUMERIC(16, 10),
    medicare_coverage_pct NUMERIC(16, 10),
    estimated_submitted_charges NUMERIC(20, 8) NOT NULL,
    estimated_total_payments NUMERIC(20, 8) NOT NULL,
    estimated_medicare_payments NUMERIC(20, 8) NOT NULL,
    charge_to_total_payment_ratio NUMERIC(16, 10),

    CONSTRAINT uq_provider_drg UNIQUE (provider_ccn, drg_code),
    CONSTRAINT chk_total_discharges_positive CHECK (total_discharges > 0),
    CONSTRAINT chk_submitted_charge_nonnegative
        CHECK (avg_submitted_covered_charge >= 0),
    CONSTRAINT chk_total_payment_nonnegative
        CHECK (avg_total_payment_amount >= 0),
    CONSTRAINT chk_medicare_payment_nonnegative
        CHECK (avg_medicare_payment_amount >= 0),
    CONSTRAINT chk_total_coverage_nonnegative
        CHECK (total_payment_coverage_pct IS NULL OR total_payment_coverage_pct >= 0),
    CONSTRAINT chk_medicare_coverage_nonnegative
        CHECK (medicare_coverage_pct IS NULL OR medicare_coverage_pct >= 0),
    CONSTRAINT chk_charge_payment_ratio_nonnegative
        CHECK (
            charge_to_total_payment_ratio IS NULL
            OR charge_to_total_payment_ratio >= 0
        )
);

COMMENT ON TABLE healthcare_analytics.inpatient_hospital_services IS
    'One row per CMS hospital and DRG service combination.';
COMMENT ON COLUMN healthcare_analytics.inpatient_hospital_services.estimated_submitted_charges IS
    'Average submitted covered charge multiplied by discharges; not actual revenue.';
COMMENT ON COLUMN healthcare_analytics.inpatient_hospital_services.estimated_total_payments IS
    'Average total payment amount multiplied by discharges.';
COMMENT ON COLUMN healthcare_analytics.inpatient_hospital_services.estimated_medicare_payments IS
    'Average Medicare payment amount multiplied by discharges.';
COMMENT ON COLUMN healthcare_analytics.inpatient_hospital_services.charge_to_total_payment_ratio IS
    'Submitted covered charge divided by total payment; a screening metric, not proof of inefficiency.';

CREATE INDEX idx_inpatient_services_state
    ON healthcare_analytics.inpatient_hospital_services (provider_state_abbreviation);

CREATE INDEX idx_inpatient_services_provider
    ON healthcare_analytics.inpatient_hospital_services (provider_ccn);

CREATE INDEX idx_inpatient_services_drg
    ON healthcare_analytics.inpatient_hospital_services (drg_code);

CREATE INDEX idx_inpatient_services_discharges
    ON healthcare_analytics.inpatient_hospital_services (total_discharges DESC);

CREATE INDEX idx_inpatient_services_ratio
    ON healthcare_analytics.inpatient_hospital_services (
        charge_to_total_payment_ratio DESC
    );
