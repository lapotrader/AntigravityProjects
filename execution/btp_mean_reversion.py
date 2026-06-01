"""
Mean Reversion su BTP 1h.
Il BTP e 70% laterale -> compra quando oversold, vendi quando overbought.
Approcci: Bollinger Bands, ATR channel, RSI.
"""
import pandas as pd, numpy as np

ST_PERIOD=30; LOOKBACK=5

def mean_reversion_backtest(df, method="bb", bb_period=20, bb_std=2.0, atr_mult=2.0, rsi_period=14, rsi_low=30, rsi_high=70):
    """
    method: "bb" = Bollinger Bands, "atr" = ATR channel, "rsi" = RSI
    Entry when price reaches extreme, exit when it reverts to mean.
    """
    n=len(df)
    high,low,close=df["high"].values,df["low"].values,df["close"].values
    open_p=df["open"].values

    # ATR (for SL)
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

    # SMA + Std (Bollinger)
    sma = pd.Series(close).rolling(bb_period).mean().values
    std = pd.Series(close).rolling(bb_period).std().values

    # RSI
    delta = pd.Series(close).diff()
    gain = delta.clip(lower=0).rolling(rsi_period).mean().values
    loss = (-delta.clip(upper=0)).rolling(rsi_period).mean().values
    rsi = np.full(n, 50.0)
    for i in range(rsi_period, n):
        if loss[i] == 0: rsi[i] = 100
        else: rsi[i] = 100 - 100 / (1 + gain[i]/loss[i])

    # Confirmed pivots for SL (safety)
    ph_raw=np.full(n,False); pl_raw=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_raw[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_raw[i]=True

    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0

    for i in range(bb_period+rsi_period+10, n):
        if np.isnan(sma[i]) or np.isnan(std[i]) or np.isnan(rsi[i]): continue

        if not in_trade:
            signal=False; sd=None

            if method == "bb":
                bb_lower = sma[i] - bb_std * std[i]
                bb_upper = sma[i] + bb_std * std[i]
                if close[i-1] < bb_lower: signal=True; sd="LONG"
                elif close[i-1] > bb_upper: signal=True; sd="SHORT"

            elif method == "atr":
                atr_ch_low = sma[i] - atr_mult * atr[i-1]
                atr_ch_high = sma[i] + atr_mult * atr[i-1]
                if close[i-1] < atr_ch_low: signal=True; sd="LONG"
                elif close[i-1] > atr_ch_high: signal=True; sd="SHORT"

            elif method == "rsi":
                if rsi[i-1] < rsi_low: signal=True; sd="LONG"
                elif rsi[i-1] > rsi_high: signal=True; sd="SHORT"

            if not signal: continue

            # Entry at open of next candle
            entry_price=float(open_p[i]); entry_idx=i

            # SL: confirmed pivot + ATR buffer
            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break
            atr_v=float(atr[i-1])

            if sd=="LONG":
                entry_dir="LONG"
                sl_price = min(entry_price - 2*atr_v, (cp_low - atr_v) if cp_low is not None else entry_price - 3*atr_v)
                tp_price = sma[i]  # revert to mean
                if tp_price <= entry_price: tp_price = entry_price + atr_v
            else:
                entry_dir="SHORT"
                sl_price = max(entry_price + 2*atr_v, (cp_high + atr_v) if cp_high is not None else entry_price + 3*atr_v)
                tp_price = sma[i]
                if tp_price >= entry_price: tp_price = entry_price - atr_v

            in_trade=True; continue

        if in_trade:
            lo=float(low[i]); hi=float(high[i]); cl=float(close[i])
            exit_here=False; exit_p=0

            if entry_dir=="LONG":
                if lo <= sl_price: exit_p=sl_price; exit_here=True
                elif hi >= tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx) >= 30: exit_p=cl; exit_here=True
            else:
                if hi >= sl_price: exit_p=sl_price; exit_here=True
                elif lo <= tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx) >= 30: exit_p=cl; exit_here=True

            if exit_here:
                pnl=round(exit_p-entry_price,2) if entry_dir=="LONG" else round(entry_price-exit_p,2)
                trades.append({"pnl":pnl}); in_trade=False; continue

    if in_trade:
        pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
        trades.append({"pnl":pnl})

    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf}

# --- LOAD ---
df_full = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df_full.columns=["data","open","high","low","close","volume"]
df_full["ora"]=pd.to_datetime(df_full["data"])

df_new = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
df_new.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df_new[c]=df_new[c].astype(float)
df_new["ora"]=pd.to_datetime(df_new["data"], dayfirst=True)

print("=== MEAN REVERSION - BTP 1h ===\n")

# --- BOLLINGER BANDS ---
print("1. BOLLINGER BANDS (SMA_20 +/- K*std)")
print(f"{'K std':<8} {'PF full':<10} {'PnL full':<12} {'Trade full':<12} {'PF new':<10} {'PnL new':<12} {'Trade new':<12}")
print("="*76)
for k in [1.5, 2.0, 2.5, 3.0]:
    r_full = mean_reversion_backtest(df_full, method="bb", bb_std=k)
    r_new = mean_reversion_backtest(df_new, method="bb", bb_std=k)
    print(f"{k:<8} {r_full['pf']:<10.2f} {r_full['pnl']:<+12.2f} {r_full['total']:<12} {r_new['pf']:<10.2f} {r_new['pnl']:<+12.2f} {r_new['total']:<12}")

# --- ATR CHANNEL ---
print("\n2. ATR CHANNEL (SMA_20 +/- ATR*K)")
print(f"{'ATR K':<8} {'PF full':<10} {'PnL full':<12} {'Trade full':<12} {'PF new':<10} {'PnL new':<12} {'Trade new':<12}")
print("="*76)
for k in [1.5, 2.0, 2.5, 3.0, 4.0]:
    r_full = mean_reversion_backtest(df_full, method="atr", atr_mult=k)
    r_new = mean_reversion_backtest(df_new, method="atr", atr_mult=k)
    print(f"{k:<8} {r_full['pf']:<10.2f} {r_full['pnl']:<+12.2f} {r_full['total']:<12} {r_new['pf']:<10.2f} {r_new['pnl']:<+12.2f} {r_new['total']:<12}")

# --- RSI ---
print("\n3. RSI")
print(f"{'RSI lim':<10} {'PF full':<10} {'PnL full':<12} {'Trade full':<12} {'PF new':<10} {'PnL new':<12} {'Trade new':<12}")
print("="*76)
for limits in [(20,80), (25,75), (30,70), (35,65)]:
    r_full = mean_reversion_backtest(df_full, method="rsi", rsi_low=limits[0], rsi_high=limits[1])
    r_new = mean_reversion_backtest(df_new, method="rsi", rsi_low=limits[0], rsi_high=limits[1])
    print(f"{limits[0]}-{limits[1]:<6} {r_full['pf']:<10.2f} {r_full['pnl']:<+12.2f} {r_full['total']:<12} {r_new['pf']:<10.2f} {r_new['pnl']:<+12.2f} {r_new['total']:<12}")

# --- CONFRONTO CON STRATEGIA ORIGINALE ---
print("\n\n=== CONFRONTO FINALE ===")
best_full = {"name":"","pf":0,"pnl":0,"total":0}
best_new = {"name":"","pf":0,"pnl":0,"total":0}

# BB best
for k in [1.5, 2.0, 2.5, 3.0]:
    r=mean_reversion_backtest(df_full,method="bb",bb_std=k)
    if r["pf"]>best_full["pf"]: best_full={"name":f"BB K={k}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}
    r=mean_reversion_backtest(df_new,method="bb",bb_std=k)
    if r["pf"]>best_new["pf"]: best_new={"name":f"BB K={k}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}

# ATR best
for k in [1.5,2.0,2.5,3.0,4.0]:
    r=mean_reversion_backtest(df_full,method="atr",atr_mult=k)
    if r["pf"]>best_full["pf"]: best_full={"name":f"ATRch K={k}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}
    r=mean_reversion_backtest(df_new,method="atr",atr_mult=k)
    if r["pf"]>best_new["pf"]: best_new={"name":f"ATRch K={k}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}

# RSI best
for limits in [(20,80),(25,75),(30,70),(35,65)]:
    r=mean_reversion_backtest(df_full,method="rsi",rsi_low=limits[0],rsi_high=limits[1])
    if r["pf"]>best_full["pf"]: best_full={"name":f"RSI {limits[0]}-{limits[1]}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}
    r=mean_reversion_backtest(df_new,method="rsi",rsi_low=limits[0],rsi_high=limits[1])
    if r["pf"]>best_new["pf"]: best_new={"name":f"RSI {limits[0]}-{limits[1]}","pf":r["pf"],"pnl":r["pnl"],"total":r["total"]}

print(f"\nMIGLIORE SU FULL 2.7 ANNI: {best_full['name']} | PF={best_full['pf']:.2f} | PnL={best_full['pnl']:+.2f}pt ({best_full['total']} trade)")
print(f"MIGLIORE SU 3 MESI NUOVI: {best_new['name']} | PF={best_new['pf']:.2f} | PnL={best_new['pnl']:+.2f}pt ({best_new['total']} trade)")

print(f"\n{'Strategia':<35} {'PF 2.7y':<10} {'PnL 2.7y':<14} {'PF new':<10} {'PnL new':<14}")
print("="*83)
print(f"{'ST + Regime-Adaptive TP (vecchia)':<35} {'1.16':<10} {'+11.18pt':<14} {'2.08':<10} {'+7.38pt':<14}")
print(f"{best_full['name']:<35} {best_full['pf']:<10.2f} {best_full['pnl']:<+14.2f} {'?':<10} {'?':<14}")
