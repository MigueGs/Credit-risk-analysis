"""
Step 4 - Probability-of-default (PD) model + credit strategy.

  1. Logistic regression (explainable champion) vs. gradient boosting (challenger)
  2. Industry metrics: AUC, Gini, KS
  3. Risk bands (deciles)
  4. Cut-off strategy: which PD threshold maximizes expected profit?
  5. Fairness check by sex (reported only - sex is NOT a model input)

Run:  python src/04_model.py
"""
import json
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from config import (DB_PATH, FIG_DIR, LGD, OUT_DIR, RANDOM_STATE,
                    REVENUE_RATE, TEST_SIZE)

# Behavioral features only - no sex, marital status or age (see config.py)
FEATURES = [
    "log_credit_limit",
    "dpd_m1", "dpd_m2", "dpd_m3", "dpd_m4", "dpd_m5", "dpd_m6",
    "max_dpd", "months_delinquent",
    "utilization_m1", "avg_utilization",
    "payment_ratio",
]
BLUE, RED, GREY = "#1F5FAD", "#C8102E", "#8A8F98"


def ks_statistic(y, p):
    """Max distance between the cumulative distributions of goods and bads."""
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def evaluate(name, y, p):
    auc = roc_auc_score(y, p)
    return {"model": name, "auc": round(auc, 4), "gini": round(2 * auc - 1, 4),
            "ks": round(ks_statistic(y, p), 4)}


def risk_bands(test: pd.DataFrame) -> pd.DataFrame:
    """Split clients into 10 equal groups by PD (1 = safest, 10 = riskiest)."""
    t = test.copy()
    t["risk_band"] = pd.qcut(t.pd.rank(method="first"), 10, labels=range(1, 11)).astype(int)
    g = (t.groupby("risk_band")
           .agg(clients=("is_default", "size"), defaults=("is_default", "sum"),
                avg_pd=("pd", "mean"), min_pd=("pd", "min"), max_pd=("pd", "max"))
           .reset_index())
    g["default_rate_pct"] = (g.defaults / g.clients * 100).round(2)
    g["avg_pd_pct"] = (g.avg_pd * 100).round(2)
    # % of all defaults captured when declining this band and riskier ones
    g["cum_defaults_captured_pct"] = (g.defaults[::-1].cumsum()[::-1]
                                      / g.defaults.sum() * 100).round(1)
    return t, g.drop(columns="avg_pd")


def cutoff_strategy(test: pd.DataFrame) -> pd.DataFrame:
    """
    For each PD cut-off: clients ABOVE it are declined / have their line restricted.
    Expected profit = revenue on good approved balances - losses on bad approved balances.
    """
    bal = test.balance.values
    y = test.is_default.values
    p = test.pd.values
    rows = []
    for c in np.round(np.arange(0.05, 1.0001, 0.01), 2):
        approved = p < c
        good, bad = approved & (y == 0), approved & (y == 1)
        revenue = REVENUE_RATE * bal[good].sum()
        loss = LGD * bal[bad].sum()
        rows.append({
            "cutoff_pd": c,
            "approval_rate_pct": round(approved.mean() * 100, 2),
            "bad_rate_approved_pct": round(y[approved].mean() * 100, 2) if approved.any() else 0,
            "defaults_avoided_pct": round((~approved & (y == 1)).sum() / y.sum() * 100, 2),
            "revenue": round(revenue, 0),
            "credit_loss": round(loss, 0),
            "expected_profit": round(revenue - loss, 0),
        })
    return pd.DataFrame(rows)


def main() -> None:
    with sqlite3.connect(DB_PATH) as con:
        df = pd.read_sql("SELECT * FROM clients", con)

    df["log_credit_limit"] = np.log(df.credit_limit)
    df["balance"] = df.bill_m1.clip(lower=0)          # exposure used for $ impact
    X, y = df[FEATURES], df.is_default

    X_tr, X_te, y_tr, y_te, idx_tr, idx_te = train_test_split(
        X, y, df.index, test_size=TEST_SIZE, stratify=y, random_state=RANDOM_STATE)

    # ---- 1. Models -----------------------------------------------------
    logit = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
    logit.fit(X_tr, y_tr)
    gbm = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                         max_depth=4, random_state=RANDOM_STATE)
    gbm.fit(X_tr, y_tr)

    p_logit = logit.predict_proba(X_te)[:, 1]
    p_gbm = gbm.predict_proba(X_te)[:, 1]
    metrics = pd.DataFrame([evaluate("Logistic Regression (champion)", y_te, p_logit),
                            evaluate("Gradient Boosting (challenger)", y_te, p_gbm)])
    metrics.to_csv(OUT_DIR / "model_metrics.csv", index=False)
    print("Model performance on the 30% hold-out test set:")
    print(metrics.to_string(index=False))

    # ---- 2. Explainability: odds ratios per 1 std. dev. ------------------
    coefs = logit.named_steps["logisticregression"].coef_[0]
    drivers = (pd.DataFrame({"feature": FEATURES, "coefficient": coefs,
                             "odds_ratio_per_1sd": np.exp(coefs)})
                 .sort_values("coefficient", key=abs, ascending=False).round(3))
    drivers.to_csv(OUT_DIR / "model_drivers.csv", index=False)
    print("\nTop risk drivers (logistic regression):")
    print(drivers.head(6).to_string(index=False))

    # ---- 3. Risk bands ----------------------------------------------------
    test = df.loc[idx_te, ["client_id", "is_default", "balance", "credit_limit",
                           "sex", "education", "utilization_m1", "dpd_m1"]].copy()
    test["pd"] = p_logit
    test, bands = risk_bands(test)
    bands.to_csv(OUT_DIR / "risk_bands.csv", index=False)
    print("\nRisk bands (deciles of PD):")
    print(bands.to_string(index=False))

    # ---- 4. Cut-off strategy ---------------------------------------------
    cut = cutoff_strategy(test)
    cut.to_csv(OUT_DIR / "cutoff_strategy.csv", index=False)
    best = cut.loc[cut.expected_profit.idxmax()]
    base = cut.loc[cut.cutoff_pd == 1.0].iloc[0]       # approve everyone
    uplift = best.expected_profit - base.expected_profit
    print(f"\nApprove-all baseline : profit {base.expected_profit:,.0f} NT$, "
          f"bad rate {base.bad_rate_approved_pct:.1f}%")
    print(f"Optimal PD cut-off {best.cutoff_pd:.2f}: approve {best.approval_rate_pct:.1f}%, "
          f"bad rate {best.bad_rate_approved_pct:.1f}%, avoid {best.defaults_avoided_pct:.1f}% "
          f"of defaults, profit {best.expected_profit:,.0f} NT$ (+{uplift:,.0f})")

    # ---- 5. Scored clients for Power BI + fairness check -----------------
    test["decision"] = np.where(test.pd < best.cutoff_pd, "Approve", "Decline / Restrict")
    test.round({"pd": 4}).to_csv(OUT_DIR / "scored_clients.csv", index=False)
    fair = (test.groupby("sex")
                .agg(clients=("pd", "size"),
                     approval_rate_pct=("decision", lambda d: (d == "Approve").mean() * 100),
                     actual_default_rate_pct=("is_default", lambda s: s.mean() * 100))
                .round(2).reset_index())
    fair.to_csv(OUT_DIR / "fairness_check.csv", index=False)
    print("\nFairness check at the chosen cut-off (sex is not a model input):")
    print(fair.to_string(index=False))

    # ---- Charts --------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6, 5))
    for name, p, color in [("Logistic", p_logit, BLUE), ("Gradient Boosting", p_gbm, GREY)]:
        fpr, tpr, _ = roc_curve(y_te, p)
        ax.plot(fpr, tpr, color=color, label=f"{name} (AUC {roc_auc_score(y_te, p):.3f})")
    ax.plot([0, 1], [0, 1], ls="--", color="#cccccc")
    ax.set(xlabel="False positive rate", ylabel="True positive rate")
    ax.set_title("ROC curve - PD model", loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="lower right")
    fig.tight_layout(); fig.savefig(FIG_DIR / "07_roc_curve.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    b = ax.bar(bands.risk_band.astype(str), bands.default_rate_pct,
               color=[BLUE] * 7 + [RED] * 3)
    ax.bar_label(b, fmt="%.0f%%", fontsize=8, padding=2)
    ax.set(xlabel="Risk band (1 = lowest PD, 10 = highest)", ylabel="Actual default rate (%)")
    ax.set_title("Model rank-orders risk: default rate by risk band", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIG_DIR / "08_risk_bands.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(cut.approval_rate_pct, cut.expected_profit / 1e6, color=BLUE)
    ax.scatter([best.approval_rate_pct], [best.expected_profit / 1e6], color=RED, zorder=3)
    ax.annotate(f"Optimal: PD < {best.cutoff_pd:.2f}\napprove {best.approval_rate_pct:.0f}%",
                (best.approval_rate_pct, best.expected_profit / 1e6),
                textcoords="offset points", xytext=(20, -60), fontsize=9,
                arrowprops=dict(arrowstyle="->", color=GREY))
    ax.set(xlabel="Approval rate (%)", ylabel="Expected profit (NT$ millions)")
    ax.set_title("Cut-off strategy: profit vs. approval rate", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIG_DIR / "09_cutoff_profit.png"); plt.close(fig)

    # ---- Key results (used for the README and resume bullets) ----------------
    results = {
        "n_clients": int(len(df)),
        "default_rate_pct": round(df.is_default.mean() * 100, 2),
        "logit_auc": metrics.auc[0], "logit_gini": metrics.gini[0], "logit_ks": metrics.ks[0],
        "gbm_auc": metrics.auc[1],
        "top_band_default_rate_pct": float(bands.default_rate_pct.iloc[-1]),
        "bottom_band_default_rate_pct": float(bands.default_rate_pct.iloc[0]),
        "top3_bands_capture_pct": float(bands.cum_defaults_captured_pct.iloc[7]),
        "optimal_cutoff_pd": float(best.cutoff_pd),
        "approval_rate_pct": float(best.approval_rate_pct),
        "bad_rate_baseline_pct": float(base.bad_rate_approved_pct),
        "bad_rate_optimal_pct": float(best.bad_rate_approved_pct),
        "defaults_avoided_pct": float(best.defaults_avoided_pct),
        "profit_uplift_ntd": float(uplift),
        "profit_uplift_pct": round(float(uplift / abs(base.expected_profit) * 100), 1)
                             if base.expected_profit != 0 else None,
    }
    (OUT_DIR / "key_results.json").write_text(json.dumps(results, indent=2))
    print(f"\nKey results saved to {OUT_DIR / 'key_results.json'}")


if __name__ == "__main__":
    main()
