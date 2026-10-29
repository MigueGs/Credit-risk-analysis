# Data

Raw data is not committed to the repository (it is public and easy to download).

**Option A (recommended): Kaggle CSV**
1. Go to https://www.kaggle.com/datasets/uciml/default-of-credit-card-clients-dataset
2. Download `UCI_Credit_Card.csv`
3. Put it in this folder: `data/UCI_Credit_Card.csv`

**Option B: original UCI Excel file**
1. Go to https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients
2. Download and unzip it
3. Put `default of credit card clients.xls` in this folder (needs `pip install xlrd`)

`src/01_load_and_clean.py` accepts either file.

Source: Yeh, I. C., & Lien, C. H. (2009). *The comparisons of data mining techniques for the predictive accuracy of probability of default of credit card clients.* Expert Systems with Applications, 36(2), 2473–2480.
