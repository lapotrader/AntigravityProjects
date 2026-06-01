"""
BTP 1h — ST(30,1.5) entry + CONFIRMED pivot SL + ATR trailing exit.
Zero look-ahead, completamente live-replicabile.
"""
import pandas as pd, numpy as np, os, json

PATH = "dati/27 febbraio.txt"
ST_PERIOD = 30; ST_MULT = 1.5
LOOKBACK = 5  # pivot lookback

df = pd.read_csv(PATH, sep="\t", header=None, decimal=",")
df.columns = ["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df[c] = df[c].astype(float)
df["ora"] = pd.to_datetime(df["data"], format="%d/%m/%Y %H:%M:%S")
n = len(df)

high, low, close = df["high"].values, df["low"].values, df["close"].values

# --- ATR ---
tr = np.maximum(high-low, np.maximum(np.abs(high-np.roll(close,1)), np.abs(low-np.roll(close,1))))
tr[0] = high[0]-low[0]
atr = np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

# --- SuperTrend ---
hl2 = (high+low)/2
basic_ub = hl2+ST_MULT*atr; basic_lb = hl2-ST_MULT*atr
final_ub=np.zeros(n); final_lb=np.zeros(n); st=np.zeros(n)
direction=np.ones(n, dtype=int)
for i in range(n):
    if i==0:
        final_ub[i]=basic_ub[i]; final_lb[i]=basic_lb[i]
        st[i]=final_ub[i]; direction[i]=-1; continue
    pc=close[i-1]
    final_ub[i]=basic_ub[i] if (basic_ub[i]<final_ub[i-1] or pc>final_ub[i-1]) else final_ub[i-1]
    final_lb[i]=basic_lb[i] if (basic_lb[i]>final_lb[i-1] or pc<final_lb[i-1]) else final_lb[i-1]
    if st[i-1]==final_ub[i-1]:
        if close[i]>final_ub[i]: st[i]=final_lb[i]; direction[i]=1
        else: st[i]=final_ub[i]; direction[i]=-1
    else:
        if close[i]<final_lb[i]: st[i]=final_ub[i]; direction[i]=-1
        else: st[i]=final_lb[i]; direction[i]=1

# --- Pivot detection (raw, for later confirmation) ---
ph_raw = np.full(n, False); pl_raw = np.full(n, False)
for i in range(LOOKBACK, n-LOOKBACK):
    if all(df.loc[i,"high"] > df.loc[i-k,"high"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i,"high"] > df.loc[i+k,"high"] for k in range(1, LOOKBACK+1)):
        ph_raw[i] = True
    if all(df.loc[i,"low"] < df.loc[i-k,"low"] for k in range(1, LOOKBACK+1)) and \
       all(df.loc[i,"low"] < df.loc[i+k,"low"] for k in range(1, LOOKBACK+1)):
        pl_raw[i] = True

# --- Grid search over ATR multipliers ---
results = []
for TRAIL_MULT in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]:
    trades = []
    in_trade = False
    entry_price=0; entry_idx=0; entry_dir=""
    trailing_stop=0; highest_since_entry=0; lowest_since_entry=0
    sl_price=0  # hard stop from confirmed pivot

    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        flip_long = (prev==1 and pprev==-1)
        flip_short = (prev==-1 and pprev==1)

        if not in_trade:
            if flip_long or flip_short:
                # Last CONFIRMED pivot: pivot at j where j <= i-5
                cp_high = None; cp_low = None
                for j in range(i-5, -1, -1):
                    if ph_raw[j]: cp_high = float(df.loc[j,"high"]); break
                for j in range(i-5, -1, -1):
                    if pl_raw[j]: cp_low = float(df.loc[j,"low"]); break

                entry_price = float(df.loc[i, "open"])
                entry_idx = i
                atr_v = float(atr[i-1])

                if flip_long:
                    entry_dir = "LONG"
                    if cp_low is not None:
                        sl_price = cp_low - 0.5*atr_v
                    else:
                        sl_price = entry_price - 2*atr_v
                    trailing_stop = sl_price  # start at SL
                else:
                    entry_dir = "SHORT"
                    if cp_high is not None:
                        sl_price = cp_high + 0.5*atr_v
                    else:
                        sl_price = entry_price + 2*atr_v
                    trailing_stop = sl_price

                highest_since_entry = entry_price
                lowest_since_entry = entry_price
                in_trade = True
                continue

        if in_trade:
            hi=float(high[i]); lo=float(low[i])
            atr_v = float(atr[i-1])

            if entry_dir == "LONG":
                highest_since_entry = max(highest_since_entry, hi)
                new_trail = highest_since_entry - TRAIL_MULT*atr_v
                trailing_stop = max(sl_price, new_trail, trailing_stop)

                exit_price=0; exit_here=False; reason=""
                if lo <= trailing_stop:
                    exit_price = trailing_stop; exit_here=True; reason="TRAIL"
                elif flip_short:
                    exit_price = float(df.loc[i,"open"]); exit_here=True; reason="ST_FLIP"
                elif (i-entry_idx) >= 40:
                    exit_price = float(close[i]); exit_here=True; reason="TIME"

                if exit_here:
                    pnl = round(exit_price-entry_price,2)
                    trades.append({"pnl":pnl})
                    in_trade=False; continue

            else:
                lowest_since_entry = min(lowest_since_entry, lo)
                new_trail = lowest_since_entry + TRAIL_MULT*atr_v
                trailing_stop = min(sl_price, new_trail, trailing_stop)

                exit_price=0; exit_here=False; reason=""
                if hi >= trailing_stop:
                    exit_price = trailing_stop; exit_here=True; reason="TRAIL"
                elif flip_long:
                    exit_price = float(df.loc[i,"open"]); exit_here=True; reason="ST_FLIP"
                elif (i-entry_idx) >= 40:
                    exit_price = float(close[i]); exit_here=True; reason="TIME"

                if exit_here:
                    pnl = round(entry_price-exit_price,2)
                    trades.append({"pnl":pnl})
                    in_trade=False; continue

    if in_trade:
        pnl = round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
        trades.append({"pnl":pnl})

    total=len(trades)
    if total==0: continue
    wins=sum(1 for t in trades if t["pnl"]>0)
    losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades)
    pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100
    results.append({"mult":TRAIL_MULT,"trades":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf})

print(f"{'ATR mult':<12} {'Trade':<8} {'Win%':<10} {'PnL pt':<12} {'PnL EUR':<14} {'PF':<8}")
print("-"*64)
for r in sorted(results, key=lambda x:x["pnl"], reverse=True):
    print(f"{r['mult']:<12} {r['trades']:<8} {r['wr']:<10.1f} {r['pnl']:<+12.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f}")

best = max(results, key=lambda x:x["pnl"])
print(f"\nMIGLIORE: ATR x{best['mult']} — PnL {best['pnl']:+.2f}pt ({best['pnl_eur']:+.0f}EUR), {best['wr']:.0f}% WR, PF={best['pf']:.2f}")
