-- =====================================================================
-- 01_clean.sql
-- Builds a clean, analysis-ready table from the raw UCI data.
--   raw table  : raw_clients   (loaded as-is from the CSV)
--   clean table: clients       (renamed columns, fixed codes, new features)
--
-- Data notes (UCI "Default of Credit Card Clients", Taiwan, Apr-Sep 2005)
--   PAY_0 .. PAY_6  repayment status. PAY_0 = September (most recent),
--                   PAY_6 = April. -2 = no consumption, -1 = paid in full,
--                   0 = revolving (min. payment made), 1..9 = months late.
--   BILL_AMT1..6    statement balance (1 = September)
--   PAY_AMT1..6     amount paid (1 = September)
--   Amounts are in New Taiwan dollars (NT$).
-- =====================================================================

DROP TABLE IF EXISTS clients;

CREATE TABLE clients AS
SELECT
    ID                                   AS client_id,
    LIMIT_BAL                            AS credit_limit,
    AGE                                  AS age,

    -- EDUCATION codes 0, 5 and 6 are undocumented -> group as "Other"
    CASE EDUCATION
        WHEN 1 THEN 'Graduate School'
        WHEN 2 THEN 'University'
        WHEN 3 THEN 'High School'
        ELSE        'Other'
    END                                  AS education,

    -- Kept ONLY for portfolio/fairness reporting, never used in the model
    CASE SEX WHEN 1 THEN 'Male' ELSE 'Female' END            AS sex,
    CASE MARRIAGE WHEN 1 THEN 'Married'
                  WHEN 2 THEN 'Single'
                  ELSE 'Other' END                            AS marital_status,

    -- Repayment status: -2 and -1 both mean "nothing overdue" -> floor at 0
    MAX(PAY_0, 0) AS dpd_m1,   -- months past due, September
    MAX(PAY_2, 0) AS dpd_m2,   -- August
    MAX(PAY_3, 0) AS dpd_m3,   -- July
    MAX(PAY_4, 0) AS dpd_m4,   -- June
    MAX(PAY_5, 0) AS dpd_m5,   -- May
    MAX(PAY_6, 0) AS dpd_m6,   -- April

    BILL_AMT1 AS bill_m1, BILL_AMT2 AS bill_m2, BILL_AMT3 AS bill_m3,
    BILL_AMT4 AS bill_m4, BILL_AMT5 AS bill_m5, BILL_AMT6 AS bill_m6,
    PAY_AMT1  AS paid_m1, PAY_AMT2  AS paid_m2, PAY_AMT3  AS paid_m3,
    PAY_AMT4  AS paid_m4, PAY_AMT5  AS paid_m5, PAY_AMT6  AS paid_m6,

    "default.payment.next.month"         AS is_default
FROM raw_clients
WHERE LIMIT_BAL > 0;            -- a client with no credit line can't be analyzed


-- ---------------------------------------------------------------------
-- Engineered features (the "client behavior" signals)
-- ---------------------------------------------------------------------
ALTER TABLE clients ADD COLUMN utilization_m1   REAL;    -- latest balance / limit
ALTER TABLE clients ADD COLUMN avg_utilization  REAL;    -- 6-month average
ALTER TABLE clients ADD COLUMN max_dpd          INTEGER; -- worst delinquency in 6 months
ALTER TABLE clients ADD COLUMN months_delinquent INTEGER;-- # of months with any delay
ALTER TABLE clients ADD COLUMN payment_ratio    REAL;    -- paid / previous bill (5-mo total)
ALTER TABLE clients ADD COLUMN age_band         TEXT;
ALTER TABLE clients ADD COLUMN limit_band       TEXT;
ALTER TABLE clients ADD COLUMN utilization_band TEXT;

UPDATE clients SET
    utilization_m1  = MAX(bill_m1, 0) * 1.0 / credit_limit,
    avg_utilization = (MAX(bill_m1,0) + MAX(bill_m2,0) + MAX(bill_m3,0)
                     + MAX(bill_m4,0) + MAX(bill_m5,0) + MAX(bill_m6,0))
                      / 6.0 / credit_limit,
    max_dpd = MAX(dpd_m1, dpd_m2, dpd_m3, dpd_m4, dpd_m5, dpd_m6),
    months_delinquent = (dpd_m1 > 0) + (dpd_m2 > 0) + (dpd_m3 > 0)
                      + (dpd_m4 > 0) + (dpd_m5 > 0) + (dpd_m6 > 0),
    -- payment in month t pays the bill of month t+1 (the previous statement)
    payment_ratio = CASE
        WHEN (MAX(bill_m2,0)+MAX(bill_m3,0)+MAX(bill_m4,0)+MAX(bill_m5,0)+MAX(bill_m6,0)) = 0
            THEN 1.0
        ELSE MIN( (paid_m1 + paid_m2 + paid_m3 + paid_m4 + paid_m5) * 1.0 /
                  (MAX(bill_m2,0)+MAX(bill_m3,0)+MAX(bill_m4,0)+MAX(bill_m5,0)+MAX(bill_m6,0)),
                  1.0)
    END;

UPDATE clients SET
    age_band = CASE
        WHEN age < 25 THEN '1. <25'
        WHEN age < 35 THEN '2. 25-34'
        WHEN age < 45 THEN '3. 35-44'
        WHEN age < 55 THEN '4. 45-54'
        ELSE               '5. 55+'
    END,
    limit_band = CASE
        WHEN credit_limit <  50000 THEN '1. <50K'
        WHEN credit_limit < 100000 THEN '2. 50K-100K'
        WHEN credit_limit < 200000 THEN '3. 100K-200K'
        WHEN credit_limit < 400000 THEN '4. 200K-400K'
        ELSE                            '5. 400K+'
    END,
    utilization_band = CASE
        WHEN utilization_m1 < 0.10 THEN '1. <10%'
        WHEN utilization_m1 < 0.30 THEN '2. 10-30%'
        WHEN utilization_m1 < 0.50 THEN '3. 30-50%'
        WHEN utilization_m1 < 0.80 THEN '4. 50-80%'
        WHEN utilization_m1 < 1.00 THEN '5. 80-100%'
        ELSE                            '6. Over limit'
    END;


-- ---------------------------------------------------------------------
-- Data-quality checks (testing & validation). Each should return 0.
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dq_checks;
CREATE TABLE dq_checks AS
SELECT 'duplicate client_id' AS check_name,
       (SELECT COUNT(*) - COUNT(DISTINCT client_id) FROM clients) AS failures
UNION ALL
SELECT 'target not 0/1',
       (SELECT COUNT(*) FROM clients WHERE is_default NOT IN (0, 1))
UNION ALL
SELECT 'age outside 18-100',
       (SELECT COUNT(*) FROM clients WHERE age < 18 OR age > 100)
UNION ALL
SELECT 'null credit_limit',
       (SELECT COUNT(*) FROM clients WHERE credit_limit IS NULL)
UNION ALL
SELECT 'rows lost vs raw',
       (SELECT COUNT(*) FROM raw_clients) - (SELECT COUNT(*) FROM clients);
