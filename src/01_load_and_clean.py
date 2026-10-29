"""
Step 1 - Load the raw data into SQLite and build the clean table with SQL.

Run:  python src/01_load_and_clean.py
"""
import sqlite3

import pandas as pd

from config import DB_PATH, RAW_CANDIDATES, SQL_DIR

TARGET = "default.payment.next.month"


def read_raw() -> pd.DataFrame:
    for path in RAW_CANDIDATES:
        if path.exists():
            if path.suffix == ".csv":
                df = pd.read_csv(path)
            else:  # original UCI Excel file has an extra header row
                df = pd.read_excel(path, header=1)
            print(f"Loaded {path.name}: {len(df):,} rows, {df.shape[1]} columns")
            break
    else:
        raise FileNotFoundError(
            "Raw data not found. Download UCI_Credit_Card.csv (see data/README.md) "
            "and put it in the data/ folder."
        )

    # Normalize the few naming differences between the CSV and Excel versions
    df = df.rename(columns={"default payment next month": TARGET, "PAY_1": "PAY_0"})
    expected = {"ID", "LIMIT_BAL", "SEX", "EDUCATION", "MARRIAGE", "AGE", "PAY_0", TARGET}
    missing = expected - set(df.columns)
    if missing:
        raise ValueError(f"Unexpected file format, missing columns: {missing}")
    return df


def main() -> None:
    raw = read_raw()

    with sqlite3.connect(DB_PATH) as con:
        raw.to_sql("raw_clients", con, if_exists="replace", index=False)
        con.executescript((SQL_DIR / "01_clean.sql").read_text())

        n = con.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        print(f"Clean table 'clients' created: {n:,} rows")

        print("\nData-quality checks (0 = pass):")
        checks = pd.read_sql("SELECT * FROM dq_checks", con)
        for _, row in checks.iterrows():
            status = "PASS" if row.failures == 0 else "CHECK"
            print(f"  [{status}] {row.check_name}: {row.failures}")

    print(f"\nDatabase saved to {DB_PATH}")


if __name__ == "__main__":
    main()
