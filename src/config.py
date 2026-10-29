"""Shared paths and business assumptions for the project."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SQL_DIR = ROOT / "sql"
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
DB_PATH = DATA_DIR / "credit_risk.db"

# Accepted raw file names (Kaggle CSV or the original UCI Excel file)
RAW_CANDIDATES = [
    DATA_DIR / "UCI_Credit_Card.csv",
    DATA_DIR / "default of credit card clients.xls",
]

# ---------------------------------------------------------------------
# Business assumptions for the cut-off (approval) strategy.
# They are simplified on purpose and stated openly in the README.
# ---------------------------------------------------------------------
LGD = 0.80              # Loss Given Default: share of the balance lost when a client defaults
REVENUE_RATE = 0.15     # yearly revenue (interest + fees) earned on a good client's balance
RANDOM_STATE = 42
TEST_SIZE = 0.30

# Protected / sensitive attributes: reported for fairness checks only,
# NEVER used as model inputs (fair-lending best practice).
EXCLUDED_FROM_MODEL = ["sex", "marital_status", "age", "age_band"]

for d in (OUT_DIR, FIG_DIR):
    d.mkdir(parents=True, exist_ok=True)
