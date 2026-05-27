"""Aggrega tick BTP (6.2M righe) in candele 1h."""
import pandas as pd
import numpy as np
import os, time

SRC = "dati/btp 2023-25.txt"
DST = "dati/btp_1h_full.txt"

t0 = time.time()
print(f"Caricamento tick data...")

df = pd.read_csv(SRC, sep="\t", header=None, names=["ts", "price", "volume"], dtype={"price": float, "volume": int})
df["ts"] = pd.to_datetime(df["ts"])

print(f"Caricati {len(df):,} tick in {time.time()-t0:.1f}s")
print(f"Range: {df['ts'].min()} -> {df['ts'].max()}")

# Round to hour floor
df["hour"] = df["ts"].dt.floor("h")

# Aggregate OHLCV
bars = df.groupby("hour", observed=False).agg(
    open=("price", "first"),
    high=("price", "max"),
    low=("price", "min"),
    close=("price", "last"),
    volume=("volume", "sum")
).reset_index()

bars.columns = ["data", "open", "high", "low", "close", "volume"]
bars = bars.sort_values("data").reset_index(drop=True)

bars.to_csv(DST, sep="\t", index=False)
print(f"\nSalvate {len(bars):,} candele 1h in {DST}")
print(f"Range: {bars['data'].min()} -> {bars['data'].max()}")
print(f"Tempo totale: {time.time()-t0:.1f}s")
