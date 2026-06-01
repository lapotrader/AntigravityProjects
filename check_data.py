import pandas as pd, numpy as np
df = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df.columns=["data","open","high","low","close","volume"]
df["dt"] = pd.to_datetime(df["data"])
print(f"Rows: {len(df)}, Date range: {df['dt'].min()} to {df['dt'].max()}")
hours = df["dt"].dt.hour.value_counts().sort_index()
print("Hour distribution:")
for h, c in hours.items():
    print(f"  {h:02d}:00 -> {c} bars")
avg = len(df) / df["dt"].dt.date.nunique()
print(f"Avg bars per day: {avg:.1f}")
# Days with most bars
by_date = df.groupby(df["dt"].dt.date).size()
print(f"Min bars/day: {by_date.min()}, Max bars/day: {by_date.max()}")
print(f"Bars in 2026 new data: ", end="")
ndf = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
print(len(ndf))
