"""
Step 2 - Run the KPI queries in sql/02_kpis.sql and export each one as a CSV
for Power BI (outputs/kpi_*.csv).

Run:  python src/02_kpis.py
"""
import re
import sqlite3

import pandas as pd

from config import DB_PATH, OUT_DIR, SQL_DIR


def parse_queries(sql_text: str) -> dict[str, str]:
    """Split the SQL file into {name: query} using the '-- @name:' markers."""
    parts = re.split(r"^-- @name:\s*(\w+)\s*$", sql_text, flags=re.MULTILINE)
    # parts = [header, name1, query1, name2, query2, ...]
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def main() -> None:
    queries = parse_queries((SQL_DIR / "02_kpis.sql").read_text())
    pd.set_option("display.width", 140)

    with sqlite3.connect(DB_PATH) as con:
        for name, query in queries.items():
            df = pd.read_sql(query, con)
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)
            print(f"\n=== {name} ===")
            print(df.to_string(index=False))

    print(f"\n{len(queries)} KPI tables exported to {OUT_DIR}")


if __name__ == "__main__":
    main()
