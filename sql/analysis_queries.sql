-- Healthcare Operations Intelligence Platform
-- 25 PostgreSQL business-analysis queries.
-- Submitted charges are not revenue. Gaps and ratios are screening metrics and
-- do not, by themselves, prove operational inefficiency.

SET search_path TO healthcare_analytics, public;

-- 1. Executive portfolio KPIs.
SELECT
    COUNT(DISTINCT provider_ccn) AS hospitals,
    COUNT(DISTINCT drg_code) AS drgs,
    COUNT(DISTINCT provider_state_abbreviation) AS states_and_territories,
    SUM(total_discharges) AS total_discharges,
    ROUND(SUM(estimated_submitted_charges) / SUM(total_discharges), 2)
        AS weighted_avg_submitted_charge,
    ROUND(SUM(estimated_total_payments) / SUM(total_discharges), 2)
        AS weighted_avg_total_payment,
    ROUND(SUM(estimated_medicare_payments) / SUM(total_discharges), 2)
        AS weighted_avg_medicare_payment,
    ROUND(SUM(estimated_submitted_charges), 2) AS estimated_submitted_charges,
    ROUND(SUM(estimated_total_payments), 2) AS estimated_total_payments,
    ROUND(SUM(estimated_medicare_payments), 2) AS estimated_medicare_payments
FROM inpatient_hospital_services;

-- 2. Top 10 hospitals by total discharges.
SELECT
    provider_ccn,
    provider_name,
    provider_state_abbreviation AS state,
    SUM(total_discharges) AS total_discharges
FROM inpatient_hospital_services
GROUP BY provider_ccn, provider_name, provider_state_abbreviation
ORDER BY total_discharges DESC
LIMIT 10;

-- 3. Top 10 DRGs by total discharges.
SELECT
    drg_code,
    drg_description,
    SUM(total_discharges) AS total_discharges
FROM inpatient_hospital_services
GROUP BY drg_code, drg_description
ORDER BY total_discharges DESC
LIMIT 10;

-- 4. State discharge volume and share of the national total.
SELECT
    provider_state_abbreviation AS state,
    SUM(total_discharges) AS total_discharges,
    ROUND(
        100.0 * SUM(total_discharges)
        / SUM(SUM(total_discharges)) OVER (),
        2
    ) AS pct_of_all_discharges
FROM inpatient_hospital_services
GROUP BY provider_state_abbreviation
ORDER BY total_discharges DESC;

-- 5. Highest weighted submitted charges among DRGs with 1,000+ discharges.
SELECT
    drg_code,
    drg_description,
    SUM(total_discharges) AS total_discharges,
    ROUND(SUM(estimated_submitted_charges) / SUM(total_discharges), 2)
        AS weighted_avg_submitted_charge
FROM inpatient_hospital_services
GROUP BY drg_code, drg_description
HAVING SUM(total_discharges) >= 1000
ORDER BY weighted_avg_submitted_charge DESC
LIMIT 20;

-- 6. Hospitals with the largest discharge-weighted payment gaps.
SELECT
    provider_ccn,
    provider_name,
    provider_state_abbreviation AS state,
    SUM(total_discharges) AS total_discharges,
    ROUND(
        SUM(payment_gap * total_discharges) / SUM(total_discharges),
        2
    ) AS weighted_avg_payment_gap
FROM inpatient_hospital_services
GROUP BY provider_ccn, provider_name, provider_state_abbreviation
HAVING SUM(total_discharges) >= 1000
ORDER BY weighted_avg_payment_gap DESC
LIMIT 20;

-- 7. High-volume DRGs with the largest weighted payment gaps.
SELECT
    drg_code,
    drg_description,
    SUM(total_discharges) AS total_discharges,
    ROUND(
        SUM(payment_gap * total_discharges) / SUM(total_discharges),
        2
    ) AS weighted_avg_payment_gap
FROM inpatient_hospital_services
GROUP BY drg_code, drg_description
HAVING SUM(total_discharges) >= 1000
ORDER BY weighted_avg_payment_gap DESC
LIMIT 20;

-- 8. State-level weighted charges, payments, and aggregate coverage.
SELECT
    provider_state_abbreviation AS state,
    SUM(total_discharges) AS total_discharges,
    ROUND(SUM(estimated_submitted_charges) / SUM(total_discharges), 2)
        AS weighted_avg_submitted_charge,
    ROUND(SUM(estimated_total_payments) / SUM(total_discharges), 2)
        AS weighted_avg_total_payment,
    ROUND(SUM(estimated_medicare_payments) / SUM(total_discharges), 2)
        AS weighted_avg_medicare_payment,
    ROUND(
        100.0 * SUM(estimated_total_payments)
        / NULLIF(SUM(estimated_submitted_charges), 0),
        2
    ) AS aggregate_total_payment_coverage_pct
FROM inpatient_hospital_services
GROUP BY provider_state_abbreviation
ORDER BY total_discharges DESC;

-- 9. Rural versus urban comparison using RUCA 1-3 as urban and 4-10 as rural.
SELECT
    CASE
        WHEN provider_ruca BETWEEN 1 AND 3.99 THEN 'Urban'
        WHEN provider_ruca BETWEEN 4 AND 10.99 THEN 'Rural'
        ELSE 'Unknown'
    END AS rural_urban_group,
    COUNT(DISTINCT provider_ccn) AS hospitals,
    SUM(total_discharges) AS total_discharges,
    ROUND(SUM(estimated_submitted_charges) / SUM(total_discharges), 2)
        AS weighted_avg_submitted_charge,
    ROUND(SUM(estimated_total_payments) / SUM(total_discharges), 2)
        AS weighted_avg_total_payment,
    ROUND(
        100.0 * SUM(estimated_total_payments)
        / NULLIF(SUM(estimated_submitted_charges), 0),
        2
    ) AS aggregate_total_payment_coverage_pct
FROM inpatient_hospital_services
GROUP BY rural_urban_group
ORDER BY total_discharges DESC;

-- 10. Coverage percentage distribution statistics.
SELECT
    ROUND(MIN(total_payment_coverage_pct), 2) AS minimum,
    ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (
        ORDER BY total_payment_coverage_pct
    )::NUMERIC, 2) AS p25,
    ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (
        ORDER BY total_payment_coverage_pct
    )::NUMERIC, 2) AS median,
    ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (
        ORDER BY total_payment_coverage_pct
    )::NUMERIC, 2) AS p75,
    ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
        ORDER BY total_payment_coverage_pct
    )::NUMERIC, 2) AS p95,
    ROUND(MAX(total_payment_coverage_pct), 2) AS maximum
FROM inpatient_hospital_services;

-- 11. Charge-to-payment ratio outliers using the 1.5 IQR rule.
WITH quartiles AS (
    SELECT
        PERCENTILE_CONT(0.25) WITHIN GROUP (
            ORDER BY charge_to_total_payment_ratio
        ) AS q1,
        PERCENTILE_CONT(0.75) WITHIN GROUP (
            ORDER BY charge_to_total_payment_ratio
        ) AS q3
    FROM inpatient_hospital_services
), threshold AS (
    SELECT q1, q3, q3 + 1.5 * (q3 - q1) AS upper_fence
    FROM quartiles
)
SELECT
    s.provider_ccn,
    s.provider_name,
    s.provider_state_abbreviation AS state,
    s.drg_code,
    s.drg_description,
    s.total_discharges,
    ROUND(s.charge_to_total_payment_ratio, 2) AS charge_payment_ratio,
    ROUND(t.upper_fence::NUMERIC, 2) AS iqr_upper_fence
FROM inpatient_hospital_services AS s
CROSS JOIN threshold AS t
WHERE s.charge_to_total_payment_ratio > t.upper_fence
ORDER BY s.charge_to_total_payment_ratio DESC;

-- 12. Hospital-DRG combinations in both the top volume and charge deciles.
WITH thresholds AS (
    SELECT
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_discharges)
            AS volume_p90,
        PERCENTILE_CONT(0.90) WITHIN GROUP (
            ORDER BY avg_submitted_covered_charge
        ) AS charge_p90
    FROM inpatient_hospital_services
)
SELECT
    s.provider_ccn,
    s.provider_name,
    s.provider_state_abbreviation AS state,
    s.drg_code,
    s.drg_description,
    s.total_discharges,
    ROUND(s.avg_submitted_covered_charge, 2) AS avg_submitted_charge,
    ROUND(s.avg_total_payment_amount, 2) AS avg_total_payment
FROM inpatient_hospital_services AS s
CROSS JOIN thresholds AS t
WHERE s.total_discharges >= t.volume_p90
  AND s.avg_submitted_covered_charge >= t.charge_p90
ORDER BY s.total_discharges DESC, s.avg_submitted_covered_charge DESC;

-- 13. Hospitals with weighted charges above their state hospital average.
WITH hospital_metrics AS (
    SELECT
        provider_ccn,
        provider_name,
        provider_state_abbreviation AS state,
        SUM(total_discharges) AS total_discharges,
        SUM(estimated_submitted_charges) / SUM(total_discharges)
            AS weighted_avg_charge
    FROM inpatient_hospital_services
    GROUP BY provider_ccn, provider_name, provider_state_abbreviation
), benchmarks AS (
    SELECT state, AVG(weighted_avg_charge) AS state_avg_hospital_charge
    FROM hospital_metrics
    GROUP BY state
)
SELECT
    h.provider_ccn,
    h.provider_name,
    h.state,
    h.total_discharges,
    ROUND(h.weighted_avg_charge, 2) AS weighted_avg_charge,
    ROUND(b.state_avg_hospital_charge, 2) AS state_avg_hospital_charge,
    ROUND(h.weighted_avg_charge - b.state_avg_hospital_charge, 2)
        AS difference_from_state_average
FROM hospital_metrics AS h
JOIN benchmarks AS b USING (state)
WHERE h.weighted_avg_charge > b.state_avg_hospital_charge
ORDER BY difference_from_state_average DESC;

-- 14. Hospital discharge rank within each state.
WITH hospital_volume AS (
    SELECT
        provider_ccn,
        provider_name,
        provider_state_abbreviation AS state,
        SUM(total_discharges) AS total_discharges
    FROM inpatient_hospital_services
    GROUP BY provider_ccn, provider_name, provider_state_abbreviation
)
SELECT
    *,
    DENSE_RANK() OVER (
        PARTITION BY state ORDER BY total_discharges DESC
    ) AS discharge_rank_in_state
FROM hospital_volume
ORDER BY state, discharge_rank_in_state, provider_ccn;

-- 15. Top five DRGs by discharge volume within each hospital.
WITH drg_volume AS (
    SELECT
        provider_ccn,
        provider_name,
        drg_code,
        drg_description,
        total_discharges,
        ROW_NUMBER() OVER (
            PARTITION BY provider_ccn
            ORDER BY total_discharges DESC, drg_code
        ) AS drg_row_number
    FROM inpatient_hospital_services
)
SELECT *
FROM drg_volume
WHERE drg_row_number <= 5
ORDER BY provider_name, drg_row_number;

-- 16. Each hospital's percentage contribution to state discharges.
WITH hospital_volume AS (
    SELECT
        provider_ccn,
        provider_name,
        provider_state_abbreviation AS state,
        SUM(total_discharges) AS hospital_discharges
    FROM inpatient_hospital_services
    GROUP BY provider_ccn, provider_name, provider_state_abbreviation
)
SELECT
    *,
    SUM(hospital_discharges) OVER (PARTITION BY state) AS state_discharges,
    ROUND(
        100.0 * hospital_discharges
        / SUM(hospital_discharges) OVER (PARTITION BY state),
        2
    ) AS pct_of_state_discharges
FROM hospital_volume
ORDER BY state, pct_of_state_discharges DESC;

-- 17. High-volume, high-gap service combinations using national percentiles.
WITH cutoffs AS (
    SELECT
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_discharges)
            AS volume_p90,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY payment_gap)
            AS payment_gap_p90
    FROM inpatient_hospital_services
)
SELECT
    s.provider_ccn,
    s.provider_name,
    s.provider_state_abbreviation AS state,
    s.drg_code,
    s.drg_description,
    s.total_discharges,
    ROUND(s.payment_gap, 2) AS payment_gap
FROM inpatient_hospital_services AS s
CROSS JOIN cutoffs AS c
WHERE s.total_discharges >= c.volume_p90
  AND s.payment_gap >= c.payment_gap_p90
ORDER BY s.total_discharges DESC, s.payment_gap DESC;

-- 18. Hospitals above the national discharge-weighted charge/payment ratio.
WITH hospital_ratios AS (
    SELECT
        provider_ccn,
        provider_name,
        provider_state_abbreviation AS state,
        SUM(estimated_submitted_charges)
            / NULLIF(SUM(estimated_total_payments), 0) AS aggregate_ratio,
        SUM(total_discharges) AS total_discharges
    FROM inpatient_hospital_services
    GROUP BY provider_ccn, provider_name, provider_state_abbreviation
), national AS (
    SELECT
        SUM(estimated_submitted_charges)
            / NULLIF(SUM(estimated_total_payments), 0) AS national_ratio
    FROM inpatient_hospital_services
)
SELECT
    h.*,
    ROUND(n.national_ratio, 2) AS national_ratio
FROM hospital_ratios AS h
CROSS JOIN national AS n
WHERE h.aggregate_ratio > n.national_ratio
ORDER BY h.aggregate_ratio DESC;

-- 19. DRGs with wide geographic variation in state weighted charges.
WITH state_drg AS (
    SELECT
        provider_state_abbreviation AS state,
        drg_code,
        drg_description,
        SUM(total_discharges) AS total_discharges,
        SUM(estimated_submitted_charges) / SUM(total_discharges)
            AS weighted_avg_charge
    FROM inpatient_hospital_services
    GROUP BY provider_state_abbreviation, drg_code, drg_description
    HAVING SUM(total_discharges) >= 100
)
SELECT
    drg_code,
    MAX(drg_description) AS drg_description,
    COUNT(*) AS states_with_100_plus_discharges,
    ROUND(MIN(weighted_avg_charge), 2) AS minimum_state_charge,
    ROUND(MAX(weighted_avg_charge), 2) AS maximum_state_charge,
    ROUND(MAX(weighted_avg_charge) - MIN(weighted_avg_charge), 2)
        AS geographic_charge_range,
    ROUND(STDDEV_SAMP(weighted_avg_charge), 2) AS state_charge_stddev
FROM state_drg
GROUP BY drg_code
HAVING COUNT(*) >= 10
ORDER BY geographic_charge_range DESC;

-- 20. Highest-volume hospital for each DRG within each state.
WITH ranked_services AS (
    SELECT
        provider_state_abbreviation AS state,
        drg_code,
        drg_description,
        provider_ccn,
        provider_name,
        total_discharges,
        RANK() OVER (
            PARTITION BY provider_state_abbreviation, drg_code
            ORDER BY total_discharges DESC
        ) AS volume_rank
    FROM inpatient_hospital_services
)
SELECT *
FROM ranked_services
WHERE volume_rank = 1
ORDER BY state, drg_code, provider_ccn;

-- 21. Hospital payment coverage versus its discharge-weighted state benchmark.
WITH hospital_metrics AS (
    SELECT
        provider_ccn,
        provider_name,
        provider_state_abbreviation AS state,
        100.0 * SUM(estimated_total_payments)
            / NULLIF(SUM(estimated_submitted_charges), 0) AS coverage_pct,
        SUM(total_discharges) AS total_discharges
    FROM inpatient_hospital_services
    GROUP BY provider_ccn, provider_name, provider_state_abbreviation
), state_metrics AS (
    SELECT
        provider_state_abbreviation AS state,
        100.0 * SUM(estimated_total_payments)
            / NULLIF(SUM(estimated_submitted_charges), 0) AS state_coverage_pct
    FROM inpatient_hospital_services
    GROUP BY provider_state_abbreviation
)
SELECT
    h.provider_ccn,
    h.provider_name,
    h.state,
    h.total_discharges,
    ROUND(h.coverage_pct, 2) AS hospital_coverage_pct,
    ROUND(s.state_coverage_pct, 2) AS state_coverage_pct,
    ROUND(h.coverage_pct - s.state_coverage_pct, 2)
        AS percentage_point_difference
FROM hospital_metrics AS h
JOIN state_metrics AS s USING (state)
ORDER BY percentage_point_difference DESC;

-- 22. Hospital service diversity and volume per offered DRG.
SELECT
    provider_ccn,
    provider_name,
    provider_state_abbreviation AS state,
    COUNT(DISTINCT drg_code) AS distinct_drgs,
    SUM(total_discharges) AS total_discharges,
    ROUND(
        SUM(total_discharges)::NUMERIC / COUNT(DISTINCT drg_code),
        2
    ) AS discharges_per_drg
FROM inpatient_hospital_services
GROUP BY provider_ccn, provider_name, provider_state_abbreviation
ORDER BY distinct_drgs DESC, total_discharges DESC;

-- 23. Service records classified into total-payment coverage bands.
SELECT
    CASE
        WHEN total_payment_coverage_pct < 10 THEN 'Below 10%'
        WHEN total_payment_coverage_pct < 20 THEN '10% to <20%'
        WHEN total_payment_coverage_pct < 30 THEN '20% to <30%'
        WHEN total_payment_coverage_pct < 50 THEN '30% to <50%'
        ELSE '50% or above'
    END AS coverage_band,
    COUNT(*) AS service_records,
    SUM(total_discharges) AS total_discharges,
    ROUND(
        100.0 * SUM(total_discharges)
        / SUM(SUM(total_discharges)) OVER (),
        2
    ) AS pct_of_discharges
FROM inpatient_hospital_services
GROUP BY coverage_band
ORDER BY MIN(total_payment_coverage_pct);

-- 24. State volume ranking with adjacent-state comparisons using LAG and LEAD.
WITH state_volume AS (
    SELECT
        provider_state_abbreviation AS state,
        SUM(total_discharges) AS total_discharges
    FROM inpatient_hospital_services
    GROUP BY provider_state_abbreviation
), ranked AS (
    SELECT
        ROW_NUMBER() OVER (ORDER BY total_discharges DESC) AS volume_position,
        state,
        total_discharges,
        LAG(state) OVER (ORDER BY total_discharges DESC) AS next_higher_volume_state,
        LAG(total_discharges) OVER (ORDER BY total_discharges DESC)
            AS next_higher_volume,
        LEAD(state) OVER (ORDER BY total_discharges DESC) AS next_lower_volume_state,
        LEAD(total_discharges) OVER (ORDER BY total_discharges DESC)
            AS next_lower_volume
    FROM state_volume
)
SELECT *
FROM ranked
ORDER BY volume_position;

-- 25. DRG share of estimated total payments (subquery example).
SELECT
    drg_code,
    drg_description,
    ROUND(SUM(estimated_total_payments), 2) AS estimated_total_payments,
    ROUND(
        100.0 * SUM(estimated_total_payments)
        / (SELECT SUM(estimated_total_payments)
           FROM inpatient_hospital_services),
        2
    ) AS pct_of_all_estimated_total_payments
FROM inpatient_hospital_services
GROUP BY drg_code, drg_description
ORDER BY estimated_total_payments DESC
LIMIT 25;
