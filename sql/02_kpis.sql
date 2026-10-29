-- =====================================================================
-- 02_kpis.sql
-- Credit-portfolio KPIs. Each query is saved by src/02_kpis.py as a CSV
-- in outputs/ so it can be loaded straight into Power BI.
-- Queries are separated by a line starting with "-- @name:".
-- =====================================================================

-- @name: kpi_portfolio_summary
-- Headline numbers for the dashboard cards
SELECT
    COUNT(*)                                        AS total_clients,
    SUM(is_default)                                 AS defaulted_clients,
    ROUND(AVG(is_default) * 100, 2)                 AS default_rate_pct,
    ROUND(SUM(credit_limit), 0)                     AS total_credit_limit,
    ROUND(SUM(MAX(bill_m1, 0)), 0)                  AS total_balance,
    ROUND(SUM(MAX(bill_m1, 0)) * 100.0 / SUM(credit_limit), 2) AS portfolio_utilization_pct,
    ROUND(AVG(CASE WHEN dpd_m1 > 0 THEN 1.0 ELSE 0 END) * 100, 2) AS current_delinquency_pct,
    -- balance held by clients who later defaulted = exposure at risk
    ROUND(SUM(CASE WHEN is_default = 1 THEN MAX(bill_m1, 0) ELSE 0 END), 0) AS balance_at_default
FROM clients;

-- @name: kpi_default_by_delinquency
-- Most predictive single view: how late is the client today?
SELECT
    CASE WHEN dpd_m1 >= 3 THEN '3+ months late'
         WHEN dpd_m1 = 2  THEN '2 months late'
         WHEN dpd_m1 = 1  THEN '1 month late'
         ELSE                  'Current' END       AS delinquency_status,
    COUNT(*)                                       AS clients,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM clients), 2) AS pct_of_portfolio,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct
FROM clients
GROUP BY 1
ORDER BY default_rate_pct;

-- @name: kpi_default_by_utilization
SELECT
    utilization_band,
    COUNT(*)                                       AS clients,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct,
    ROUND(AVG(credit_limit), 0)                    AS avg_credit_limit
FROM clients
GROUP BY utilization_band
ORDER BY utilization_band;

-- @name: kpi_default_by_limit
SELECT
    limit_band,
    COUNT(*)                                       AS clients,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct,
    ROUND(AVG(utilization_m1) * 100, 1)            AS avg_utilization_pct
FROM clients
GROUP BY limit_band
ORDER BY limit_band;

-- @name: kpi_default_by_age
SELECT
    age_band,
    COUNT(*)                                       AS clients,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct
FROM clients
GROUP BY age_band
ORDER BY age_band;

-- @name: kpi_default_by_education
SELECT
    education,
    COUNT(*)                                       AS clients,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct
FROM clients
GROUP BY education
ORDER BY default_rate_pct DESC;

-- @name: kpi_default_by_history
-- Repeat offenders: how many of the last 6 months were late?
SELECT
    months_delinquent,
    COUNT(*)                                       AS clients,
    ROUND(AVG(is_default) * 100, 2)                AS default_rate_pct
FROM clients
GROUP BY months_delinquent
ORDER BY months_delinquent;

-- @name: kpi_monthly_trend
-- 60+ days past due (2+ months late) and utilization by month (April -> September 2005).
-- 2+ is used on purpose: in this dataset the "1 month late" code only appears in the
-- latest month (PAY_0), so a 1+ definition would create a fake jump in September.
SELECT '2005-04' AS month, ROUND(AVG(dpd_m6 >= 2) * 100, 2) AS delinquency_60plus_pct,
       ROUND(SUM(MAX(bill_m6,0)) * 100.0 / SUM(credit_limit), 2) AS utilization_pct FROM clients
UNION ALL
SELECT '2005-05', ROUND(AVG(dpd_m5 >= 2) * 100, 2),
       ROUND(SUM(MAX(bill_m5,0)) * 100.0 / SUM(credit_limit), 2) FROM clients
UNION ALL
SELECT '2005-06', ROUND(AVG(dpd_m4 >= 2) * 100, 2),
       ROUND(SUM(MAX(bill_m4,0)) * 100.0 / SUM(credit_limit), 2) FROM clients
UNION ALL
SELECT '2005-07', ROUND(AVG(dpd_m3 >= 2) * 100, 2),
       ROUND(SUM(MAX(bill_m3,0)) * 100.0 / SUM(credit_limit), 2) FROM clients
UNION ALL
SELECT '2005-08', ROUND(AVG(dpd_m2 >= 2) * 100, 2),
       ROUND(SUM(MAX(bill_m2,0)) * 100.0 / SUM(credit_limit), 2) FROM clients
UNION ALL
SELECT '2005-09', ROUND(AVG(dpd_m1 >= 2) * 100, 2),
       ROUND(SUM(MAX(bill_m1,0)) * 100.0 / SUM(credit_limit), 2) FROM clients;

-- @name: kpi_roll_rate
-- Roll rate (classic collections metric): of clients that were current or
-- 60+ days past due in August, where were they in September?
SELECT
    CASE WHEN dpd_m2 >= 2 THEN 'Aug: 60+ days past due'
         ELSE                  'Aug: Current' END            AS from_status,
    COUNT(*)                                                AS clients,
    ROUND(AVG(dpd_m1 < 2) * 100, 2)                          AS sep_current_pct,
    ROUND(AVG(dpd_m1 >= 2) * 100, 2)                         AS sep_60plus_pct,
    ROUND(AVG(dpd_m1 > dpd_m2) * 100, 2)                     AS rolled_worse_pct,
    ROUND(AVG(is_default) * 100, 2)                          AS default_rate_pct
FROM clients
GROUP BY 1
ORDER BY 1;
