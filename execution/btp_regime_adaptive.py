"""
Regime-adaptive: K cambia automaticamente in base alla volatilita.
Usa ATR percentile (ultimi 50 periodi) per rilevare il regime.
"""
import pandas as pd, numpy as np

ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

def regime_adaptive_backtest(df, vol_window=50):
    n=len(df); high,low,close=df["high"].values,df["low"].values,df["close"].values

    # ATR
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

    # ATR percentile (rolling rank)
    atr_pct = np.full(n, 0.5)
    for i in range(vol_window, n):
        roll = atr[i-vol_window:i]
        atr_pct[i] = np.sum(roll <= atr[i]) / vol_window

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

    # Confirmed pivots
    ph_raw=np.full(n,False); pl_raw=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph_raw[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl_raw[i]=True

    # ------- REGIME-ADAPTIVE CONFIG --------
    # Low vol (pct<30%):   K=2.0 tight TP, fixed exit
    # Med vol (30-70%):    K=3.0 med TP
    # High vol (pct>70%):  K=4.0 wide TP, OR switch to trailing, OR skip trade
    regimes = {
        "LOW":  {"k": 2.0, "label": "BASSA"},
        "MED":  {"k": 3.0, "label": "MEDIA"},
        "HIGH": {"k": 4.0, "label": "ALTA"},
    }
    # Also test: in HIGH vol, use ATR trailing instead of fixed TP
    use_trailing_in_high = True

    trades=[]; in_trade=False
    entry_price=0; entry_idx=0; entry_dir=""; sl_price=0; tp_price=0; trailing_stop=0
    regime_log = []

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
            atr_v=float(atr[i-1]); pct=atr_pct[i-1]

            # Determine regime
            if pct < 0.3: regime = "LOW"
            elif pct > 0.7: regime = "HIGH"
            else: regime = "MED"
            k = regimes[regime]["k"]
            regime_log.append(regime)

            if sd=="LONG":
                entry_dir="LONG"
                sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                if use_trailing_in_high and regime == "HIGH":
                    tp_price = None  # use trailing
                    trailing_stop = sl_price
                else:
                    tp_price = entry_price + k * atr_v
            else:
                entry_dir="SHORT"
                sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                if use_trailing_in_high and regime == "HIGH":
                    tp_price = None
                    trailing_stop = sl_price
                else:
                    tp_price = entry_price - k * atr_v
            in_trade=True; continue

        if in_trade:
            lo=float(low[i]); hi=float(high[i]); atr_v=float(atr[i-1])
            exit_here=False; exit_p=0

            if entry_dir=="LONG":
                if tp_price is not None:
                    # Fixed TP
                    if lo<=sl_price: exit_p=sl_price; exit_here=True
                    elif hi>=tp_price: exit_p=tp_price; exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                else:
                    # Trailing in high vol
                    if lo<=sl_price: exit_p=sl_price; exit_here=True
                    else:
                        new_trail = hi - 3.0 * atr_v
                        trailing_stop = max(sl_price, new_trail, trailing_stop)
                        if lo<=trailing_stop: exit_p=trailing_stop; exit_here=True
                        elif flip_short: exit_p=float(df.loc[i,"open"]); exit_here=True
                        elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
            else:
                if tp_price is not None:
                    if hi>=sl_price: exit_p=sl_price; exit_here=True
                    elif lo<=tp_price: exit_p=tp_price; exit_here=True
                    elif (i-entry_idx)>=40: exit_p=float(close[i]); exit_here=True
                else:
                    if hi>=sl_price: exit_p=sl_price; exit_here=True
                    else:
                        new_trail = lo + 3.0 * atr_v
                        trailing_stop = min(sl_price, new_trail, trailing_stop)
                        if hi>=trailing_stop: exit_p=trailing_stop; exit_here=True
                        elif flip_long: exit_p=float(df.loc[i,"open"]); exit_here=True
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

    eq=0; peak=0; max_dd=0
    for t in trades: eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)

    # Per-regime breakdown
    r_counts = {"LOW":0,"MED":0,"HIGH":0}
    for r in regime_log: r_counts[r] += 1

    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd,
        "regimes":r_counts}

# Also test: simple regime-switching K only (no trailing)
def simple_regime_k(df, vol_window=50):
    n=len(df); high,low,close=df["high"].values,df["low"].values,df["close"].values
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    atr_pct=np.full(n,0.5)
    for i in range(vol_window,n): roll=atr[i-vol_window:i]; atr_pct[i]=np.sum(roll<=atr[i])/vol_window

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
            entry_price=float(df.loc[i,"open"]); entry_idx=i; atr_v=float(atr[i-1])
            pct=atr_pct[i-1]
            k = 2.0 if pct < 0.3 else (4.0 if pct > 0.7 else 3.0)
            if sd=="LONG":
                entry_dir="LONG"; sl_price=(cp_low-0.5*atr_v) if cp_low is not None else (entry_price-2*atr_v)
                tp_price=entry_price+k*atr_v
            else:
                entry_dir="SHORT"; sl_price=(cp_high+0.5*atr_v) if cp_high is not None else (entry_price+2*atr_v)
                tp_price=entry_price-k*atr_v
            if sl_price>=entry_price: sl_price=entry_price-2*atr_v
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
    eq=0; peak=0; max_dd=0
    for t in trades: eq+=t["pnl"]*1000-6; peak=max(peak,eq); max_dd=min(max_dd,eq-peak)
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"dd":max_dd}

# --- TEST ---
df_full = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df_full.columns=["data","open","high","low","close","volume"]
df_full["ora"]=pd.to_datetime(df_full["data"])

df_new = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
df_new.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: df_new[c]=df_new[c].astype(float)
df_new["ora"]=pd.to_datetime(df_new["data"], dayfirst=True)

print("=== REGIME-ADATTIVO: K cambia con ATR percentile ===")
configs = [
    ("K fisso=3.0 (baseline)", lambda df: run_backtest_simple(df, 3.0)),
    ("K regime (basso/medio/alto)", lambda df: simple_regime_k(df)),
    ("K regime + trailing in alta vol", lambda df: regime_adaptive_backtest(df)),
]

# Helper for K=3.0 baseline
def run_backtest_simple(df, base_K):
    # same as fixed K=3.0 from previous test
    n=len(df); h,l,c=df["high"].values,df["low"].values,df["close"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; a=np.zeros(n); alpha=1/ST_PERIOD; a[0]=tr[0]
    for i in range(1,n): a[i]=a[i-1]+alpha*(tr[i]-a[i-1])
    hl2=(h+l)/2; fu=np.zeros(n); fl=np.zeros(n); st=np.zeros(n); d=np.ones(n,dtype=int)
    for i in range(n):
        if i==0: fu[i]=hl2[i]+ST_MULT*a[i]; fl[i]=hl2[i]-ST_MULT*a[i]; st[i]=fu[i]; d[i]=-1; continue
        pc=c[i-1]; ub=hl2[i]+ST_MULT*a[i]; lb=hl2[i]-ST_MULT*a[i]
        fu[i]=ub if (ub<fu[i-1] or pc>fu[i-1]) else fu[i-1]
        fl[i]=lb if (lb>fl[i-1] or pc<fl[i-1]) else fl[i-1]
        if st[i-1]==fu[i-1]:
            if c[i]>fu[i]: st[i]=fl[i]; d[i]=1
            else: st[i]=fu[i]; d[i]=-1
        else:
            if c[i]<fl[i]: st[i]=fu[i]; d[i]=-1
            else: st[i]=fl[i]; d[i]=1
    ph=np.full(n,False); pl=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl[i]=True
    trades=[]; it=False; ep=0; ei=0; ed=""; sp=0; tpp=0
    for i in range(ST_PERIOD+2, n):
        pv=d[i-1]; pp=d[i-2]; flg=(pv==1 and pp==-1); fs=(pv==-1 and pp==1)
        if not it:
            sd=None
            if flg: sd="LONG"
            elif fs: sd="SHORT"
            else: continue
            ch=None; cl=None
            for j in range(i-5,-1,-1):
                if ph[j]: ch=float(df.loc[j,"high"]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(df.loc[j,"low"]); break
            ep=float(df.loc[i,"open"]); ei=i; av=float(a[i-1])
            if sd=="LONG": ed="LONG"; sp=(cl-0.5*av) if cl is not None else (ep-2*av); tpp=ep+base_K*av
            else: ed="SHORT"; sp=(ch+0.5*av) if ch is not None else (ep+2*av); tpp=ep-base_K*av
            if sp>=ep: sp=ep-2*av
            it=True; continue
        if it:
            lo=float(l[i]); hi=float(h[i]); ex=False; exp=0
            if ed=="LONG":
                if lo<=sp: exp=sp; ex=True
                elif hi>=tpp: exp=tpp; ex=True
                elif (i-ei)>=40: exp=float(c[i]); ex=True
            else:
                if hi>=sp: exp=sp; ex=True
                elif lo<=tpp: exp=tpp; ex=True
                elif (i-ei)>=40: exp=float(c[i]); ex=True
            if ex:
                pnl=round(exp-ep,2) if ed=="LONG" else round(ep-exp,2)
                trades.append({"pnl":pnl}); it=False; continue
    if it:
        pnl=round(float(c[-1])-ep,2) if ed=="LONG" else round(ep-float(c[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf}

for name, fn in configs:
    print(f"\n--- {name} ---")
    r_full = fn(df_full)
    r_new = fn(df_new)
    print(f"  {'':<30} {'Trade':<8} {'Win%':<8} {'PnLpt':<10} {'PnLEUR':<14} {'PF':<8}")
    print(f"  {'2.7 anni':<30} {r_full['total']:<8} {r_full['wr']:<8.1f} {r_full['pnl']:<+10.2f} {r_full['pnl_eur']:<+14.0f} {r_full['pf']:<8.2f}")
    print(f"  {'3 mesi recenti':<30} {r_new['total']:<8} {r_new['wr']:<8.1f} {r_new['pnl']:<+10.2f} {r_new['pnl_eur']:<+14.0f} {r_new['pf']:<8.2f}")
