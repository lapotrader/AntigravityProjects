"""Aggrega tick BUND 1m in candele 1h."""
import pandas as pd, numpy as np

SRC = "dati/bund_m1.txt"
DST = "dati/bund_1h.txt"

print("Loading BUND 1m data...")
df = pd.read_csv(SRC, sep=",", header=None,
    names=["date","time","open","high","low","close","volume"])
df["datetime"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"], format="%Y%m%d %H:%M:%S")
df.set_index("datetime", inplace=True)
for c in ["open","high","low","close","volume"]: df[c] = df[c].astype(float)

print(f"Loaded {len(df)} rows: {df.index[0]} -> {df.index[-1]}")

# Resample to 1h
hourly = df.resample("h").agg({
    "open": "first",
    "high": "max",
    "low": "min",
    "close": "last",
    "volume": "sum"
}).dropna()

print(f"Resampled to {len(hourly)} 1h candles: {hourly.index[0]} -> {hourly.index[-1]}")

# Save in same format as BTP: data\topen\thigh\tlow\tclose\tvolume
hourly.to_csv(DST, sep="\t", date_format="%Y-%m-%d %H:%M:%S",
    columns=["open","high","low","close","volume"])
print(f"Saved to {DST}")
