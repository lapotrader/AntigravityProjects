"""
BTP 1h — ST(30, 1.5) entry + ATR trailing exit.
Zero look-ahead, completamente replicabile in live.
"""
import pandas as pd, numpy as np, os, json

PATH = "dati/27 febbraio.txt"
ST_PERIOD = 30; ST_MULT = 1.5
TRAIL_MULT = 2.0  # ATR multiplier for trailing stop

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns = ["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df[c] = df[c].astype(float)
df["ora"] = pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
n = len(df)
print(f"BTP 1h TRAILING EXIT - ST({ST_PERIOD},{ST_MULT}) + ATRx{TRAIL_MULT}")
print(f"Dati: {df['ora'].iloc[0]} -> {df['ora'].iloc[-1]} ({n} candele)\n")

# --- SuperTrend(30, 1.5) ---
high, low, close = df["high"].values, df["low"].values, df["close"].values
tr = np.maximum(high - low,
    np.maximum(np.abs(high - np.roll(close, 1)), np.abs(low - np.roll(close, 1))))
tr[0] = high[0] - low[0]
atr = np.zeros(n); alpha = 1/ST_PERIOD; atr[0] = tr[0]
for i in range(1, n): atr[i] = atr[i-1] + alpha * (tr[i] - atr[i-1])

hl2 = (high + low) / 2
basic_ub = hl2 + ST_MULT * atr; basic_lb = hl2 - ST_MULT * atr
final_ub = np.zeros(n); final_lb = np.zeros(n); st = np.zeros(n)
direction = np.ones(n, dtype=int)
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

# --- Trading logic with ATR trailing ---
trades = []
in_trade = False
entry_price = 0; entry_idx = 0; entry_dir = ""
trailing_stop = 0; highest_since_entry = 0; lowest_since_entry = 0

for i in range(ST_PERIOD + 2, n):
    prev = direction[i-1]; pprev = direction[i-2]
    flip_long = (prev == 1 and pprev == -1)
    flip_short = (prev == -1 and pprev == 1)

    if not in_trade:
        if flip_long:
            entry_price = float(df.loc[i, "open"])
            entry_idx = i; entry_dir = "LONG"
            trailing_stop = entry_price - TRAIL_MULT * float(atr[i-1])
            highest_since_entry = entry_price; lowest_since_entry = entry_price
            in_trade = True
            continue
        elif flip_short:
            entry_price = float(df.loc[i, "open"])
            entry_idx = i; entry_dir = "SHORT"
            trailing_stop = entry_price + TRAIL_MULT * float(atr[i-1])
            highest_since_entry = entry_price; lowest_since_entry = entry_price
            in_trade = True
            continue

    if in_trade:
        hi = float(high[i]); lo = float(low[i]); cl = float(close[i])
        atr_v = float(atr[i-1])

        # Update extremes
        if entry_dir == "LONG":
            highest_since_entry = max(highest_since_entry, hi)
            new_stop = highest_since_entry - TRAIL_MULT * atr_v
            trailing_stop = max(trailing_stop, new_stop)

            # Exit: ST flip or trailing hit or time stop (40 bars)
            exit_here = False; exit_price = 0; exit_reason = ""
            if lo <= trailing_stop:
                exit_price = trailing_stop; exit_here = True; exit_reason = "TRAIL"
            elif flip_short:
                exit_price = float(df.loc[i, "open"]); exit_here = True; exit_reason = "ST_FLIP"
            elif (i - entry_idx) >= 40:
                exit_price = cl; exit_here = True; exit_reason = "TIME"

            if exit_here:
                pnl = round(exit_price - entry_price, 2)
                trades.append({"entry": entry_idx, "exit": i, "dir": "LONG",
                    "entry_px": entry_price, "exit_px": exit_price,
                    "pnl": pnl, "pnl_eur": round(pnl*1000 - 6, 2),
                    "bars": i - entry_idx, "reason": exit_reason,
                    "entry_date": df.loc[entry_idx,"ora"].strftime("%d/%m/%Y %H:%M"),
                    "exit_date": df.loc[i,"ora"].strftime("%d/%m/%Y %H:%M")})
                in_trade = False
                continue

        else:  # SHORT
            lowest_since_entry = min(lowest_since_entry, lo)
            new_stop = lowest_since_entry + TRAIL_MULT * atr_v
            trailing_stop = min(trailing_stop, new_stop)

            exit_here = False; exit_price = 0; exit_reason = ""
            if hi >= trailing_stop:
                exit_price = trailing_stop; exit_here = True; exit_reason = "TRAIL"
            elif flip_long:
                exit_price = float(df.loc[i, "open"]); exit_here = True; exit_reason = "ST_FLIP"
            elif (i - entry_idx) >= 40:
                exit_price = cl; exit_here = True; exit_reason = "TIME"

            if exit_here:
                pnl = round(entry_price - exit_price, 2)
                trades.append({"entry": entry_idx, "exit": i, "dir": "SHORT",
                    "entry_px": entry_price, "exit_px": exit_price,
                    "pnl": pnl, "pnl_eur": round(pnl*1000 - 6, 2),
                    "bars": i - entry_idx, "reason": exit_reason,
                    "entry_date": df.loc[entry_idx,"ora"].strftime("%d/%m/%Y %H:%M"),
                    "exit_date": df.loc[i,"ora"].strftime("%d/%m/%Y %H:%M")})
                in_trade = False
                continue

# Close open trade at end
if in_trade:
    pnl = round(float(close[-1]) - entry_price, 2) if entry_dir == "LONG" else round(entry_price - float(close[-1]), 2)
    trades.append({"entry": entry_idx, "exit": n-1, "dir": entry_dir,
        "entry_px": entry_price, "exit_px": float(close[-1]),
        "pnl": pnl, "pnl_eur": round(pnl*1000 - 6, 2),
        "bars": n-1 - entry_idx, "reason": "END",
        "entry_date": df.loc[entry_idx,"ora"].strftime("%d/%m/%Y %H:%M"),
        "exit_date": df.loc[n-1,"ora"].strftime("%d/%m/%Y %H:%M")})

# --- Results ---
total = len(trades)
wins = sum(1 for t in trades if t["pnl"] > 0)
losses = total - wins
total_pnl_pts = sum(t["pnl"] for t in trades)
total_pnl_eur = sum(t["pnl_eur"] for t in trades)
avg_win = np.mean([t["pnl"] for t in trades if t["pnl"] > 0]) if wins else 0
avg_loss = np.mean([t["pnl"] for t in trades if t["pnl"] <= 0]) if losses else 0
pf = abs(sum(t["pnl"] for t in trades if t["pnl"] > 0) / sum(t["pnl"] for t in trades if t["pnl"] <= 0)) if losses else 999

# Equity curve
eq = [0]; dd = [0]; peak = 0
for t in trades:
    eq.append(eq[-1] + t["pnl_eur"])
    peak = max(peak, eq[-1])
    dd.append(eq[-1] - peak)
max_dd = min(dd)
max_dd_pct = round(max_dd / 50000 * 100, 1) if abs(max_dd) > 0 else 0

print(f"{'#':<4} {'Data Entry':<20} {'Data Exit':<20} {'Dir':<7} {'Entry':<9} {'Exit':<9} {'PnL':<9} {'PnL€':<10} {'Bars':<6} {'Motivo':<10}")
print("=" * 110)
for k, t in enumerate(trades):
    pnl_s = f"+{t['pnl']:.2f}" if t['pnl'] > 0 else f"{t['pnl']:.2f}"
    print(f"{k+1:<4} {t['entry_date']:<20} {t['exit_date']:<20} {t['dir']:<7} {t['entry_px']:<9.2f} {t['exit_px']:<9.2f} {pnl_s:<9} {t['pnl_eur']:<+9.2f}€ {t['bars']:<6} {t['reason']:<10}")

print(f"\n--- RISULTATI (ATRx{TRAIL_MULT}) ---")
print(f"  Trade:        {total}")
print(f"  Win:          {wins} ({wins/total*100:.1f}%)")
print(f"  Loss:         {losses} ({losses/total*100:.1f}%)")
print(f"  PnL:          {total_pnl_pts:+.2f} pt ({total_pnl_eur:+.2f}€)")
print(f"  Avg Win:      +{avg_win:.2f} pt ({avg_win*1000-6:.0f}€)")
print(f"  Avg Loss:     {avg_loss:.2f} pt ({avg_loss*1000-6:.0f}€)")
print(f"  Profit Factor: {pf:.2f}")
print(f"  Max DD:       {max_dd:.0f}€ ({max_dd_pct}%)")
print(f"  Avg Bars:     {np.mean([t['bars'] for t in trades]):.1f}")

# Exit reason breakdown
print(f"\n  Exit reasons:")
for r in ["TRAIL", "ST_FLIP", "TIME", "END"]:
    cnt = sum(1 for t in trades if t["reason"] == r)
    if cnt: print(f"    {r}: {cnt} ({cnt/total*100:.0f}%)")
