"""
Test ST(30, 1.5) + Pivot Trailing sui nuovi dati (27/02 - 28/05/2026)
"""
import pandas as pd
import numpy as np
import os

LOOKBACK = 5
ST_PERIOD = 30
ST_MULT = 1.5
PATH = "dati/27 febbraio.txt"

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns = ["data", "high", "low", "open", "close", "volume"]
for col in ["high","low","open","close","volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
df = df.reset_index(drop=True)
n = len(df)

print(f"Caricate {n} candele 1h: {df['ora'].iloc[0]} -> {df['ora'].iloc[-1]}")
print(f"Range prezzi: {df['low'].min():.2f} - {df['high'].max():.2f}")

# --- SuperTrend(30, 1.5) ---
high, low, close = df["high"].values, df["low"].values, df["close"].values
tr = np.maximum(high - low,
                np.maximum(np.abs(high - np.roll(close, 1)),
                           np.abs(low - np.roll(close, 1))))
tr[0] = high[0] - low[0]
atr = np.zeros(n); alpha = 1/ST_PERIOD
atr[0] = tr[0]
for i in range(1, n):
    atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])

hl2 = (high + low) / 2
basic_ub = hl2 + ST_MULT * atr
basic_lb = hl2 - ST_MULT * atr

final_ub = np.zeros(n); final_lb = np.zeros(n)
st = np.zeros(n); direction = np.ones(n, dtype=int)
for i in range(n):
    if i == 0:
        final_ub[i] = basic_ub[i]; final_lb[i] = basic_lb[i]
        st[i] = final_ub[i]; direction[i] = -1; continue
    pc = close[i-1]
    final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i-1] or pc > final_ub[i-1]) else final_ub[i-1]
    final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i-1] or pc < final_lb[i-1]) else final_lb[i-1]
    if st[i-1] == final_ub[i-1]:
        if close[i] > final_ub[i]: st[i] = final_lb[i]; direction[i] = 1
        else: st[i] = final_ub[i]; direction[i] = -1
    else:
        if close[i] < final_lb[i]: st[i] = final_ub[i]; direction[i] = -1
        else: st[i] = final_lb[i]; direction[i] = 1

# --- Pivot detection ---
ph_flag = np.full(n, False); pl_flag = np.full(n, False)
for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, LOOKBACK+1)):
        ph_flag[i] = True
    if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, LOOKBACK+1)):
        pl_flag[i] = True

# prev pivot (SL)
ph_prev = [None]*n; pl_prev = [None]*n
lp = None; ll = None
for i in range(n):
    if ph_flag[i]: lp = float(df.loc[i, "high"])
    if pl_flag[i]: ll = float(df.loc[i, "low"])
    ph_prev[i] = lp; pl_prev[i] = ll

# next pivot (TP)
ph_next = [None]*n; pl_next = [None]*n
np_h = None; np_l = None
for i in range(n-1, -1, -1):
    if ph_flag[i]: np_h = float(df.loc[i, "high"])
    if pl_flag[i]: np_l = float(df.loc[i, "low"])
    ph_next[i] = np_h; pl_next[i] = np_l

# --- Signals ---
signals = []
for i in range(ST_PERIOD + 2, n):
    prev = direction[i-1]; pprev = direction[i-2]
    if prev == 1 and pprev == -1:
        dir_label = "LONG"
    elif prev == -1 and pprev == 1:
        dir_label = "SHORT"
    else: continue

    entry = round(float(df.loc[i, "open"]), 2)
    atr_v = float(atr[i-1])

    if dir_label == "LONG":
        pl = pl_prev[i]
        if pl is None: continue
        sl = round(pl - 0.5 * atr_v, 2)
        tp = round(ph_next[i], 2) if ph_next[i] is not None else round(entry + abs(entry-sl), 2)
    else:
        ph = ph_prev[i]
        if ph is None: continue
        sl = round(ph + 0.5 * atr_v, 2)
        tp = round(pl_next[i], 2) if pl_next[i] is not None else round(entry - abs(sl-entry), 2)

    if sl is None or tp is None: continue
    if (dir_label == "LONG" and sl >= entry) or (dir_label == "SHORT" and sl <= entry): continue
    # Fix TP: for LONG, TP must be above entry; for SHORT, TP must be below entry
    if dir_label == "LONG" and tp <= entry:
        tp = round(entry + abs(entry - sl), 2)
    if dir_label == "SHORT" and tp >= entry:
        tp = round(entry - abs(sl - entry), 2)

    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp - entry), 2)
    rr = round(reward/risk, 2) if risk > 0 else 0

    signals.append({
        "data": df.loc[i, "ora"].strftime("%d/%m/%Y %H:%M"),
        "dir": dir_label, "entry": entry, "sl": sl, "tp": tp,
        "risk": risk, "reward": reward, "rr": rr
    })

print(f"\nSegnali generati: {len(signals)}")

if signals:
    print(f"\n{'#':<4} {'Data':<20} {'Dir':<8} {'Entry':<9} {'SL':<9} {'TP':<9} {'Rischio':<8} {'Reward':<8} {'R/R':<6}")
    print("-" * 88)
    for k, s in enumerate(signals):
        print(f"{k+1:<4} {s['data']:<20} {s['dir']:<8} {s['entry']:<9.2f} {s['sl']:<9.2f} {s['tp']:<9.2f} {s['risk']:<8.2f} {s['reward']:<8.2f} {s['rr']:<6.2f}")

    print("\n--- SIMULAZIONE ---")
    wins = 0; losses = 0; pnl_pts = 0.0
    for s in signals:
        i = df[df["ora"] == pd.to_datetime(s["data"], format="%d/%m/%Y %H:%M")].index[0]
        entry = s["entry"]; sl = s["sl"]; tp = s["tp"]; dir_label = s["dir"]
        result = None
        for j in range(i+1, n):
            if dir_label == "LONG":
                if df.loc[j, "low"] <= sl: result = "SL"; exit_p = sl; break
                if df.loc[j, "high"] >= tp: result = "TP"; exit_p = tp; break
            else:
                if df.loc[j, "high"] >= sl: result = "SL"; exit_p = sl; break
                if df.loc[j, "low"] <= tp: result = "TP"; exit_p = tp; break
        if result is None: continue
        pnl = round(exit_p - entry, 2) if dir_label == "LONG" else round(entry - exit_p, 2)
        pnl_eur = round(pnl * 1000 - 6, 2)
        if result == "TP": wins += 1
        else: losses += 1
        pnl_pts += pnl
        print(f"  {s['data']:<20} {dir_label:<6} Entry={entry:<7.2f} -> {result:<4} PnL={pnl:<+7.2f}pt ({pnl_eur:<+8.2f} EUR)")

    total = wins + losses
    print(f"\n--- RISULTATI ---")
    print(f"  Trade:    {total}")
    print(f"  Win:      {wins} ({wins/total*100:.1f}%)")
    print(f"  Loss:     {losses} ({losses/total*100:.1f}%)")
    print(f"  PnL:      {pnl_pts:+.2f} punti ({pnl_pts*1000 - total*6:+.2f} EUR netti)")
else:
    print("Nessun segnale generato.")
