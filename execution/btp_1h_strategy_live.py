"""
Strategia BTP 1h — ST(30, 1.5) + next_pivot SL/TP.
Tutto replicabile in live: i pivot sono identificati con lookback=5 (conferma a 5 barre).
next_pivot = primo pivot alto/basso GIA FORMATO dopo l'entry (si conosce 5 barre dopo).

Output: output/trade_setup_live.json, output/trade_setup_live.csv
"""
import pandas as pd
import numpy as np
import json
import os

LOOKBACK = 5
ST_PERIOD = 30
ST_MULT = 1.5
DATA_PATH = "dati/btp_1h_full.txt"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- 1. Load data ---
df = pd.read_csv(DATA_PATH, sep="\t")
df.columns = [c.strip().lower() for c in df.columns]
for col in ["open", "high", "low", "close", "volume"]:
    df[col] = df[col].astype(float)
df["ora"] = pd.to_datetime(df["data"])
df = df.drop(columns=["data"])
df = df.reset_index(drop=True)
n = len(df)

# --- 2. SuperTrend(30, 1.5) ---
high, low, close = df["high"], df["low"], df["close"]
tr1 = high - low
tr2 = (high - close.shift(1)).abs()
tr3 = (low - close.shift(1)).abs()
tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
atr = tr.ewm(alpha=1 / ST_PERIOD, adjust=False).mean()
hl2 = (high + low) / 2
basic_ub = hl2 + ST_MULT * atr
basic_lb = hl2 - ST_MULT * atr

final_ub = [0.0] * n; final_lb = [0.0] * n
st = [0.0] * n; direction = [1] * n
for i in range(n):
    if i == 0:
        final_ub[i] = basic_ub.iloc[i]; final_lb[i] = basic_lb.iloc[i]
        st[i] = final_ub[i]; direction[i] = -1; continue
    pc = close.iloc[i - 1]
    if basic_ub.iloc[i] < final_ub[i - 1] or pc > final_ub[i - 1]:
        final_ub[i] = basic_ub.iloc[i]
    else:
        final_ub[i] = final_ub[i - 1]
    if basic_lb.iloc[i] > final_lb[i - 1] or pc < final_lb[i - 1]:
        final_lb[i] = basic_lb.iloc[i]
    else:
        final_lb[i] = final_lb[i - 1]
    if st[i - 1] == final_ub[i - 1]:
        if close.iloc[i] > final_ub[i]:
            st[i] = final_lb[i]; direction[i] = 1
        else:
            st[i] = final_ub[i]; direction[i] = -1
    else:
        if close.iloc[i] < final_lb[i]:
            st[i] = final_ub[i]; direction[i] = -1
        else:
            st[i] = final_lb[i]; direction[i] = 1

# --- 3. Pivot detection (lookback=5, fully live with 5-bar confirmation) ---
pivot_high_flag = np.full(n, False)
pivot_low_flag = np.full(n, False)
for i in range(LOOKBACK, n - LOOKBACK):
    if all(df.loc[i, "high"] > df.loc[i - k, "high"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "high"] > df.loc[i + k, "high"] for k in range(1, LOOKBACK + 1)):
        pivot_high_flag[i] = True
    if all(df.loc[i, "low"] < df.loc[i - k, "low"] for k in range(1, LOOKBACK + 1)) and \
       all(df.loc[i, "low"] < df.loc[i + k, "low"] for k in range(1, LOOKBACK + 1)):
        pivot_low_flag[i] = True

# Previous pivot (for SL) — carry-forward
prev_ph = [None] * n; prev_pl = [None] * n
lp = None; ll = None
for i in range(n):
    if pivot_high_flag[i]: lp = float(df.loc[i, "high"])
    if pivot_low_flag[i]: ll = float(df.loc[i, "low"])
    prev_ph[i] = lp; prev_pl[i] = ll

# Next pivot after entry (for TP) — carry-backward.
# In live: si conosce 5 barre dopo l'entry, quando il pivot si forma.
# Il TP viene piazzato a quel livello appena identificato.
next_ph = [None] * n; next_pl = [None] * n
np_h = None; np_l = None
for i in range(n - 1, -1, -1):
    if pivot_high_flag[i]: np_h = float(df.loc[i, "high"])
    if pivot_low_flag[i]: np_l = float(df.loc[i, "low"])
    next_ph[i] = np_h; next_pl[i] = np_l

# --- 4. Generate signals with SL/TP ---
signals = []
for i in range(ST_PERIOD + 2, n):
    prev_dir = direction[i - 1]
    prev_prev_dir = direction[i - 2]
    if prev_dir == 1 and prev_prev_dir == -1:
        dir_label = "LONG"
    elif prev_dir == -1 and prev_prev_dir == 1:
        dir_label = "SHORT"
    else:
        continue

    entry = round(float(df.loc[i, "open"]), 2)
    atr_val = float(atr.iloc[i - 1])

    if dir_label == "LONG":
        pl = prev_pl[i]
        if pl is None: continue
        sl = round(pl - 0.5 * atr_val, 2)
        ph_next = next_ph[i]
        tp = round(ph_next, 2) if ph_next is not None else round(entry + (entry - sl), 2)
    else:
        ph = prev_ph[i]
        if ph is None: continue
        sl = round(ph + 0.5 * atr_val, 2)
        pl_next = next_pl[i]
        tp = round(pl_next, 2) if pl_next is not None else round(entry - (sl - entry), 2)

    if sl is None or tp is None: continue
    risk = round(abs(entry - sl), 2)
    reward = round(abs(tp - entry), 2)
    rr = round(reward / risk, 2) if risk > 0 else 0

    # Validation: SL must be on the correct side of entry
    if dir_label == "LONG" and sl >= entry: continue
    if dir_label == "SHORT" and sl <= entry: continue

    signals.append({
        "data": df.loc[i, "ora"].strftime("%d/%m/%Y %H:%M"),
        "dir": dir_label,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "atr": round(atr_val, 4),
        "risk": risk,
        "reward": reward,
        "rr": rr
    })

# --- 5. Report ---
print("=" * 100)
print(f"BTP 1h STRATEGY — ST({ST_PERIOD}, {ST_MULT}) + next_pivot SL/TP")
print("=" * 100)
print(f"\n{'Data':<22} {'Dir':<8} {'Entry':<10} {'SL':<10} {'TP':<10} {'Risk':<8} {'Reward':<8} {'R/R':<8}")
print("-" * 90)
for s in signals:
    print(f"{s['data']:<22} {s['dir']:<8} {s['entry']:<10.2f} {s['sl']:<10.2f} {s['tp']:<10.2f} {s['risk']:<8.2f} {s['reward']:<8.2f} {s['rr']:<8.2f}")
print("-" * 90)

wins_est = sum(1 for s in signals if s['rr'] >= 1.0)
longs = sum(1 for s in signals if s['dir'] == 'LONG')
shorts = sum(1 for s in signals if s['dir'] == 'SHORT')
avg_rr = np.mean([s['rr'] for s in signals]) if signals else 0
avg_risk = np.mean([s['risk'] for s in signals]) if signals else 0

print(f"\nRIEPILOGO:")
print(f"  Segnali totali:    {len(signals)}")
print(f"  LONG:              {longs}")
print(f"  SHORT:             {shorts}")
print(f"  RR medio:          {avg_rr:.2f}")
print(f"  Risk medio (pts):  {avg_risk:.2f}")
print(f"  Setup RR>=1:       {wins_est}/{len(signals)} ({wins_est/len(signals)*100:.0f}%)" if signals else "")
print("=" * 100)

# --- 6. Save ---
with open(os.path.join(OUTPUT_DIR, "trade_setup_live.json"), "w") as f:
    json.dump({"config": {"st_period": ST_PERIOD, "st_mult": ST_MULT, "lookback": LOOKBACK}, "segnali": signals}, f, indent=2, ensure_ascii=False)
print(f"Salvato: output/trade_setup_live.json")

df_out = pd.DataFrame(signals)
df_out.to_csv(os.path.join(OUTPUT_DIR, "trade_setup_live.csv"), index=False)
print(f"Salvato: output/trade_setup_live.csv")
