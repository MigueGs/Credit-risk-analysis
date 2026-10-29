"""
Step 3 - Client-behavior analysis: which patterns come before a default?
Saves charts to outputs/figures/.

Run:  python src/03_eda.py
"""
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import DB_PATH, FIG_DIR, OUT_DIR

BLUE, RED, GREY = "#1F5FAD", "#C8102E", "#8A8F98"
plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 10})


def bar(df, x, y, title, fname, avg=None, color=BLUE):
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(df[x].astype(str), df[y], color=color)
    ax.bar_label(bars, fmt="%.1f%%", padding=2, fontsize=9)
    if avg is not None:
        ax.axhline(avg, color=GREY, ls="--", lw=1)
        ax.text(-0.4, avg, f"portfolio avg {avg:.1f}%", va="bottom",
                ha="left", color=GREY, fontsize=8)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.set_ylabel("Default rate (%)")
    ax.set_xlabel("")
    plt.xticks(rotation=0)
    fig.tight_layout()
    fig.savefig(FIG_DIR / fname)
    plt.close(fig)


def main() -> None:
    with sqlite3.connect(DB_PATH) as con:
        clients = pd.read_sql("SELECT * FROM clients", con)

    avg = clients.is_default.mean() * 100
    print(f"Portfolio default rate: {avg:.2f}%")

    k = lambda name: pd.read_csv(OUT_DIR / f"{name}.csv")  # KPI tables from step 2

    bar(k("kpi_default_by_delinquency"), "delinquency_status", "default_rate_pct",
        "Default rate by current delinquency status", "01_default_by_delinquency.png", avg, RED)
    bar(k("kpi_default_by_utilization"), "utilization_band", "default_rate_pct",
        "Default rate by credit utilization (Sep)", "02_default_by_utilization.png", avg)
    bar(k("kpi_default_by_limit"), "limit_band", "default_rate_pct",
        "Default rate by credit limit (NT$)", "03_default_by_limit.png", avg)
    bar(k("kpi_default_by_history"), "months_delinquent", "default_rate_pct",
        "Default rate by # of late months (last 6)", "04_default_by_history.png", avg, RED)

    # Monthly trend
    t = k("kpi_monthly_trend")
    fig, ax1 = plt.subplots(figsize=(7, 4))
    ax1.plot(t.month, t.delinquency_60plus_pct, marker="o", color=RED, label="60+ days past due")
    ax1.set_ylabel("60+ days past due (%)", color=RED)
    ax2 = ax1.twinx()
    ax2.plot(t.month, t.utilization_pct, marker="s", color=BLUE, label="Utilization")
    ax2.set_ylabel("Portfolio utilization (%)", color=BLUE)
    ax2.spines["top"].set_visible(False)
    ax1.set_ylim(0, max(t.delinquency_60plus_pct) * 1.4)   # start at 0: no exaggerated swings
    ax2.set_ylim(0, max(t.utilization_pct) * 1.4)
    ax1.set_title("Monthly 60+ DPD rate vs. utilization (2005)", loc="left", fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "05_monthly_trend.png")
    plt.close(fig)

    # Payment behavior: defaulters vs. non-defaulters
    fig, ax = plt.subplots(figsize=(7, 4))
    for label, color, grp in [("No default", BLUE, 0), ("Default", RED, 1)]:
        ax.hist(clients.loc[clients.is_default == grp, "payment_ratio"], bins=20,
                range=(0, 1), alpha=0.6, density=True, color=color, label=label)
    ax.set_title("Share of bills paid (5 months): defaulters vs. others",
                 loc="left", fontweight="bold")
    ax.set_xlabel("Payment ratio (amount paid / amount billed)")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "06_payment_ratio.png")
    plt.close(fig)

    # Key behavior facts printed for the README / interview
    late = clients[clients.dpd_m1 >= 2].is_default.mean() * 100
    current = clients[clients.dpd_m1 == 0].is_default.mean() * 100
    low_pay = clients[clients.payment_ratio < 0.10].is_default.mean() * 100
    hi_pay = clients[clients.payment_ratio >= 0.50].is_default.mean() * 100
    print(f"Default rate - 2+ months late today: {late:.1f}% vs current: {current:.1f}% "
          f"({late / current:.1f}x)")
    print(f"Default rate - pays <10% of bills: {low_pay:.1f}% vs pays 50%+: {hi_pay:.1f}%")
    print(f"Charts saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
