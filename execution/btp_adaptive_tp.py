"""
Test: TP ADATTIVO = entry +/- ATR * K * (ATR/ATR_ma20)
Se volatilita alta -> TP piu largo. Se bassa -> TP piu stretto.
Full backtest 2.7 anni + validazione su 27 febbraio.
"""
import pandas as pd, numpy as np

ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

def load_data(path, is_full=True):
    if is_full:
        df = pd.read_csv(path, sep="\t", decimal=".")
        df.columns=["data","open","high","low","close","volume"]
    else:
        df = pd.read_csv(path, sep="\t", header=None, decimal=",")
        df.columns=["data","high","low","open","close","volume"]
    df["ora"]=pd.to_datetime(df["data"])
    return df

def run_backtest(df, base_K, adaptive=True, ma_window=20):
    n=len(df)
    high,low,close=df["high"].values,df["low"].values,df["close"].values

    # ATR
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

    # ATR moving average (for adaptive)
    atr_ma = pd.Series(atr).rolling(ma_window).mean().values

    # ST
    hl2=(high+low)/2; fu=np.zeros(n); fl=np.zeros(n); st=np.zeros(n); direction=np.ones(n,dtype=int)
    for i in range(n):
        if i==0: fu[i]=hl2[i]+ST_MULT*atr[i]; fl[i]=hl2[i]-ST_MULT*atr[i]; st[i]=fu[i]; direction[i]=-1; continue
        pc=close[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
        fu[i]=ub if (ub<fu[i-1] or pc>fu[i-1]) else fu[i-1]
        fl[i]=lb if (lb>fl[i-1] or pc<fl[i-1]) else fl[i-1]
        if st[i-1]==fu[i-1]:
            if close[i]>fu[i]: st[i]=fl[i]; direction[i]=1
            else: st[i]=fu[i]; direction[i]=-1
        else:
            if close[i]<fl[i]: st[i]=fu[i]; direction[i]=-1
            else: st[i]=fl[i]; direction[i]=1

    # Confirmed pivots (SL)
    ph_raw=np.full(n,False); pl_raw=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_raw[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_raw[i]=True

    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0

    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        flip_long=(prev==1 and pprev==-1); flip_short=(prev==-1 and pprev==1)

        if not in_trade:
            sd=None
            if flip_long: sd="LONG"
            elif flip_short: sd="SHORT"
            else: continue

            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break

            entry_price=float(df.loc[i,"open"]); entry_idx=i
            atr_v=float(atr[i-1]); atr_a=float(atr_ma[i-1]) if not np.isnan(atr_ma[i-1]) else atr_v

            # ADAPTIVE multiplier
            if adaptive and atr_a > 0:
                ratio = atr_v / atr_a
                k_eff = base_K * ratio
            else:
                k_eff = base_K

            if sd=="LONG":
                entry_dir="LONG"
                sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                tp_price=entry_price+k_eff*atr_v
                if sl_price >= entry_price: sl_price=entry_price-2*atr_v
            else:
                entry_dir="SHORT"
                sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                tp_price=entry_price-k_eff*atr_v
                if sl_price <= entry_price: sl_price=entry_price+2*atr_v
            in_trade=True; continue

        if in_trade:
            lo=float(low[i]); hi=float(high[i])
            exit_here=False; exit_p=0
            if entry_dir=="LONG":
                if lo<=sl_price: exit_p=sl_price; exit_here=True; reason="SL"
                elif hi>=tp_price: exit_p=tp_price; exit_here=True; reason="TP"
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True; reason="TIME"
            else:
                if hi>=sl_price: exit_p=sl_price; exit_here=True; reason="SL"
                elif lo<=tp_price: exit_p=tp_price; exit_here=True; reason="TP"
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True; reason="TIME"
            if exit_here:
                pnl=round(exit_p-entry_price,2) if entry_dir=="LONG" else round(entry_price-exit_p,2)
                trades.append({"pnl":pnl,"reason":reason}); in_trade=False; continue

    if in_trade:
        pnl=round(float(close[-1])-entry_price,2) if entry_dir=="LONG" else round(entry_price-float(close[-1]),2)
        trades.append({"pnl":pnl,"reason":"END"})

    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0

    eq=0; peak=0; max_dd=0
    for t in trades:
        eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd,
        "tp_cnt":sum(1 for t in trades if t.get("reason")=="TP"),
        "sl_cnt":sum(1 for t in trades if t.get("reason")=="SL")}

# --- LOAD DATA ---
df_full = load_data("dati/btp_1h_full.txt", is_full=True)
df_new = load_data("dati/27 febbraio.txt", is_full=False)
print(f"Full: {len(df_full)} candles | New: {len(df_new)} candles\n")

# --- TEST VARIOUS K VALUES ---
ks = [0.5, 0.8, 1.0, 1.2, 1.5, 1.7, 2.0, 2.5, 3.0, 4.0]

print("=== TP FISSO (K costante) su FULL DATASET ===")
for label, df in [("FULL (2.7 anni)", df_full), ("NUOVO (3 mesi)", df_new)]:
    print(f"\n--- {label} ---")
    results = []
    for k in ks:
        r = run_backtest(df, k, adaptive=False)
        results.append({"k":k, **r})
    r_sorted = sorted(results, key=lambda x:x["pf"], reverse=True)
    print(f"{'K':<6} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8} {'DD':<10} {'TP':<6} {'SL':<6}")
    print("="*75)
    for r in r_sorted[:5]:
        print(f"{r['k']:<6} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f} {r['dd']:<10.0f} {r['tp_cnt']:<6} {r['sl_cnt']:<6}")

# --- TEST ADAPTIVE ---
print("\n\n=== TP ADATTIVO K * (ATR/ATR_ma20) su FULL DATASET ===")
for label, df in [("FULL (2.7 anni)", df_full), ("NUOVO (3 mesi)", df_new)]:
    print(f"\n--- {label} ---")
    results = []
    for k in ks:
        r = run_backtest(df, k, adaptive=True)
        results.append({"k":k, **r})
    r_sorted = sorted(results, key=lambda x:x["pf"], reverse=True)
    print(f"{'K base':<8} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8} {'DD':<10} {'TP':<6} {'SL':<6}")
    print("="*75)
    for r in r_sorted[:5]:
        print(f"{r['k']:<8} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f} {r['dd']:<10.0f} {r['tp_cnt']:<6} {r['sl_cnt']:<6}")

# --- ALSO TEST USING ATR_ma20 DIRECTLY (TP = entry +/- ATR_ma20 * K) ---
print("\n\n=== TP BASATO SU ATR_MA20 (no ratio, usa media) ===")
def run_backtest_ma(df, base_K):
    n=len(df)
    high,low,close=df["high"].values,df["low"].values,df["close"].values
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    atr_ma = pd.Series(atr).rolling(20).mean().values

    hl2=(high+low)/2; fu=np.zeros(n); fl=np.zeros(n); st=np.zeros(n); direction=np.ones(n,dtype=int)
    for i in range(n):
        if i==0: fu[i]=hl2[i]+ST_MULT*atr[i]; fl[i]=hl2[i]-ST_MULT*atr[i]; st[i]=fu[i]; direction[i]=-1; continue
        pc=close[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
        fu[i]=ub if (ub<fu[i-1] or pc>fu[i-1]) else fu[i-1]
        fl[i]=lb if (lb>fl[i-1] or pc<fl[i-1]) else fl[i-1]
        if st[i-1]==fu[i-1]:
            if close[i]>fu[i]: st[i]=fl[i]; direction[i]=1
            else: st[i]=fu[i]; direction[i]=-1
        else:
            if close[i]<fl[i]: st[i]=fu[i]; direction[i]=-1
            else: st[i]=fl[i]; direction[i]=1

    ph_raw=np.full(n,False); pl_raw=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_raw[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_raw[i]=True

    trades=[]; in_trade=False; entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0
    for i in range(ST_PERIOD+2, n):
        prev=direction[i-1]; pprev=direction[i-2]
        flip_long=(prev==1 and pprev==-1); flip_short=(prev==-1 and pprev==1)
        if not in_trade:
            sd=None
            if flip_long: sd="LONG"
            elif flip_short: sd="SHORT"
            else: continue
            cp_high=None; cp_low=None
            for j in range(i-5, -1, -1):
                if ph_raw[j]: cp_high=float(df.loc[j,"high"]); break
            for j in range(i-5, -1, -1):
                if pl_raw[j]: cp_low=float(df.loc[j,"low"]); break
            entry_price=float(df.loc[i,"open"]); entry_idx=i
            atr_v=float(atr[i-1]); atr_a=float(atr_ma[i-1]) if not np.isnan(atr_ma[i-1]) else atr_v
            if sd=="LONG":
                entry_dir="LONG"; sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                tp_price=entry_price+base_K*atr_a
                if sl_price>=entry_price: sl_price=entry_price-2*atr_v
            else:
                entry_dir="SHORT"; sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                tp_price=entry_price-base_K*atr_a
                if sl_price<=entry_price: sl_price=entry_price+2*atr_v
            in_trade=True; continue
        if in_trade:
            lo=float(low[i]); hi=float(high[i]); exit_here=False; exit_p=0
            if entry_dir=="LONG":
                if lo<=sl_price: exit_p=sl_price; exit_here=True
                elif hi>=tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
            else:
                if hi>=sl_price: exit_p=sl_price; exit_here=True
                elif lo<=tp_price: exit_p=tp_price; exit_here=True
                elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
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
    return {"k":base_K,"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf}

for label, df in [("FULL (2.7 anni)", df_full), ("NUOVO (3 mesi)", df_new)]:
    print(f"\n--- {label} ---")
    results = []
    for k in ks:
        r = run_backtest_ma(df, k)
        results.append(r)
    r_sorted = sorted(results, key=lambda x:x["pf"], reverse=True)
    print(f"{'K base':<8} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8}")
    print("="*65)
    for r in r_sorted[:3]:
        print(f"{r['k']:<8} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pnl_eur']:<+14.0f} {r['pf']:<8.2f}")
