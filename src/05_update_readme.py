"""
Step 5 - Write the key results from outputs/key_results.json into README.md.

Run:  python src/05_update_readme.py
"""
import json
import re

from config import OUT_DIR, ROOT

r = json.loads((OUT_DIR / "key_results.json").read_text())

gap = r["gbm_auc"] - r["logit_auc"]
if gap > 0:
    challenger = (f"AUC {r['gbm_auc']:.3f} (+{gap:.3f}); logistic regression kept as champion "
                  f"for explainability, challenger monitored")
else:
    challenger = f"AUC {r['gbm_auc']:.3f}: no gain over the explainable model"

block = f"""<!-- RESULTS:START -->
| | |
|---|---|
| Clients analyzed | **{r['n_clients']:,}** (portfolio default rate {r['default_rate_pct']:.1f}%) |
| PD model (logistic regression, hold-out test set) | **AUC {r['logit_auc']:.3f} · Gini {r['logit_gini']:.3f} · KS {r['logit_ks']:.3f}** |
| Challenger (gradient boosting) | {challenger} |
| Risk separation | Riskiest 10% of clients default at **{r['top_band_default_rate_pct']:.0f}%** vs. **{r['bottom_band_default_rate_pct']:.0f}%** for the safest 10% |
| Riskiest 30% of clients | hold **{r['top3_bands_capture_pct']:.0f}%** of all defaults |
| Recommended cut-off | Approve clients with PD < **{r['optimal_cutoff_pd']:.2f}** ({r['approval_rate_pct']:.0f}% of clients) |
| Bad rate after cut-off | **{r['bad_rate_optimal_pct']:.1f}%** vs. {r['bad_rate_baseline_pct']:.1f}% approving everyone ({r['defaults_avoided_pct']:.0f}% of defaults avoided) |
| Expected profit uplift vs. approve-all | **NT$ {r['profit_uplift_ntd'] / 1e6:,.1f}M** on the test set |

![Risk bands](outputs/figures/08_risk_bands.png)
![Cut-off strategy](outputs/figures/09_cutoff_profit.png)
<!-- RESULTS:END -->"""

readme = ROOT / "README.md"
text = readme.read_text()
text = re.sub(r"<!-- RESULTS:START -->.*?<!-- RESULTS:END -->", block, text, flags=re.DOTALL)
readme.write_text(text)
print("README.md updated with your results.")
