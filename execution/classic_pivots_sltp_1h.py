import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

LOOKBACK = 5
ATR_PERIOD = 14
DATA_PATH = "dati/1oraprova.txt"
SIGNALS_PATH = "output/supertrend_signals_1h.json"
OUTPUT_DIR = "output"
PIVOT_OUT = os.path.join(OUTPUT_DIR, "pivot_levels_1h.json")
SETUP_OUT = os.path.join(OUTPUT_DIR, "trade_setup_1h.json")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 1. Carica dati ──────────────────────────────────────────────
df = pd.read_csv(DATA_PATH, sep="\t", skiprows=2)
df.columns = ["ora", "high", "low", "open", "close", "volume"]

for col in ["high", "low", "open", "close"]:
    df[col] = df[col].astype(str).str.replace(",", ".").astype(float)
df["volume"] = df["volume"].astype(str).str.replace(",", ".").astype(float)

df["ora"] = pd.to_datetime(df["ora"], format="%d/%m/%Y %H:%M:%S", dayfirst=True)
df = df.reset_index(drop=True)

n = len(df)

# ── 2. Pivot highs / lows ───────────────────────────────────────
pivot_high_flag = np.full(n, False)
pivot_low_flag  = np.full(n, False)

for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, LOOKBACK + 1)):
        pivot_high_flag[i] = True
    if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, LOOKBACK + 1)):
        pivot_low_flag[i] = True

# ── 3. Carry-forward nearest pivot ──────────────────────────────
nearest_ph = [None] * n
nearest_pl = [None] * n
last_ph = None
last_pl = None

for i in range(n):
    if pivot_high_flag[i]:
        last_ph = float(df.loc[i, "high"])
    if pivot_low_flag[i]:
        last_pl = float(df.loc[i, "low"])
    nearest_ph[i] = last_ph
    nearest_pl[i] = last_pl

df["nearest_pivot_high"] = nearest_ph
df["nearest_pivot_low"]  = nearest_pl

# ── 4. ATR (SMA 14) ─────────────────────────────────────────────
prev_close = df["close"].shift(1)
tr = pd.concat([
    (df["high"] - df["low"]).abs(),
    (df["high"] - prev_close).abs(),
    (df["low"]  - prev_close).abs()
], axis=1).max(axis=1)
df["atr"] = tr.rolling(window=ATR_PERIOD, min_periods=ATR_PERIOD).mean()

# ── Salva pivot levels ──────────────────────────────────────────
pivot_list = []
for i in range(n):
    if pivot_high_flag[i]:
        pivot_list.append({
            "timestamp": df.loc[i, "ora"].strftime("%Y-%m-%d %H:%M:%S"),
            "type": "pivot_high",
            "price": float(df.loc[i, "high"])
        })
    if pivot_low_flag[i]:
        pivot_list.append({
            "timestamp": df.loc[i, "ora"].strftime("%Y-%m-%d %H:%M:%S"),
            "type": "pivot_low",
            "price": float(df.loc[i, "low"])
        })

with open(PIVOT_OUT, "w") as f:
    json.dump(pivot_list, f, indent=2)

print(f"Pivot trovati: {len(pivot_list)}")

# ── 5. Leggi segnali e calcola setup ────────────────────────────
if os.path.exists(SIGNALS_PATH):
    with open(SIGNALS_PATH, "r") as f:
        raw = json.load(f)

    signals = raw.get("segnali", [])

    setups = []
    for sig in signals:
        ts_str = sig["data"]
        direction = sig["direzione"]
        entry_price = sig["prezzo_entry"]
        atr_val = sig["atr"]

        ts_dt = pd.to_datetime(ts_str, format="%d/%m/%Y %H:%M", dayfirst=True)

        match = df[df["ora"] == ts_dt]
        if match.empty:
            continue
        idx = match.index[0]

        ph_raw = df.loc[idx, "nearest_pivot_high"]
        pl_raw = df.loc[idx, "nearest_pivot_low"]
        ph = None if pd.isna(ph_raw) else ph_raw
        pl = None if pd.isna(pl_raw) else pl_raw

        if direction == "LONG":
            if pl is None:
                continue
            sl = round(pl - 0.5 * atr_val, 2)
            tp = round(ph, 2) if ph is not None else None
        elif direction == "SHORT":
            if ph is None:
                continue
            sl = round(ph + 0.5 * atr_val, 2)
            tp = round(pl, 2) if pl is not None else None
        else:
            continue

        setups.append({
            "timestamp": ts_str,
            "direction": direction,
            "entry": round(entry_price, 2),
            "sl": sl,
            "tp": tp,
            "pivot_low_used": round(pl, 2) if pl is not None else None,
            "pivot_high_used": round(ph, 2) if ph is not None else None,
            "atr_used": round(atr_val, 4)
        })

    with open(SETUP_OUT, "w") as f:
        json.dump(setups, f, indent=2)

    print(f"Setup generati: {len(setups)}")
else:
    print(f"File segnali non trovato: {SIGNALS_PATH}")
    print("Salvati solo i pivot levels.")

print("Fatto.")
