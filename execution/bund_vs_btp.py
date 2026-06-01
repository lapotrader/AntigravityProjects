"""
BUND 220m — Stessa batteria di test del BTP.
ST(30,1.5) + regime-adapt TP + mean reversion.
Confronto diretto BTP vs BUND.
"""
import pandas as pd, numpy as np

ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

def test_st_strategy(df):
    """ST + regime-adaptive TP (come btp)"""
    n=len(df)
    high,low,close=df["high"].values,df["low"].values,df["close"].values

    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])

    atr_pct=np.full(n,0.5)
    for i in range(50,n): roll=atr[i-50:i]; atr_pct[i]=np.sum(roll<=atr[i])/50

    hl2=(high+low)/2; fu=np.zeros(n); fl=np.zeros(n); st=np.zeros(n); d=np.ones(n,dtype=int)
    for i in range(n):
        if i==0: fu[i]=hl2[i]+ST_MULT*atr[i]; fl[i]=hl2[i]-ST_MULT*atr[i]; st[i]=fu[i]; d[i]=-1; continue
        pc=close[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
        fu[i]=ub if (ub<fu[i-1] or pc>fu[i-1]) else fu[i-1]
        fl[i]=lb if (lb>fl[i-1] or pc<fl[i-1]) else fl[i-1]
        if st[i-1]==fu[i-1]:
            if close[i]>fu[i]: st[i]=fl[i]; d[i]=1
            else: st[i]=fu[i]; d[i]=-1
        else:
            if close[i]<fl[i]: st[i]=fu[i]; d[i]=-1
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
            ep=float(df.loc[i,"open"]); ei=i; av=float(atr[i-1])
            pct=atr_pct[i-1]; k=2.0 if pct<0.3 else (4.0 if pct>0.7 else 3.0)
            if sd=="LONG": ed="LONG"; sp=(cl-0.5*av) if cl is not None else (ep-2*av); tpp=ep+k*av
            else: ed="SHORT"; sp=(ch+0.5*av) if ch is not None else (ep+2*av); tpp=ep-k*av
            if ed=="LONG" and sp>=ep: sp=ep-2*av
            if ed=="SHORT" and sp<=ep: sp=ep+2*av
            it=True; continue
        if it:
            lo=float(low[i]); hi=float(high[i]); ex=False; exp=0
            if ed=="LONG":
                if lo<=sp: exp=sp; ex=True
                elif hi>=tpp: exp=tpp; ex=True
                elif (i-ei)>=40: exp=float(close[i]); ex=True
            else:
                if hi>=sp: exp=sp; ex=True
                elif lo<=tpp: exp=tpp; ex=True
                elif (i-ei)>=40: exp=float(close[i]); ex=True
            if ex:
                pnl=round(exp-ep,2) if ed=="LONG" else round(ep-exp,2)
                trades.append({"pnl":pnl}); it=False; continue
    if it:
        pnl=round(float(close[-1])-ep,2) if ed=="LONG" else round(ep-float(close[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades); pnl_eur=pnl_pts*1000-total*6
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pnl_eur":pnl_eur,"pf":pf,"name":"ST+regime_adapt"}

def test_bb_strategy(df, k=2.0):
    """Bollinger Bands mean reversion"""
    n=len(df); high,low,close=df["high"].values,df["low"].values,df["close"].values; op=df["open"].values
    tr=np.maximum(high-low,np.maximum(np.abs(high-np.roll(close,1)),np.abs(low-np.roll(close,1))))
    tr[0]=high[0]-low[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    sma=pd.Series(close).rolling(20).mean().values; std=pd.Series(close).rolling(20).std().values
    ph=np.full(n,False); pl=np.full(n,False)
    for i in range(LOOKBACK, n-LOOKBACK):
        if all(df.loc[i,"high"]>df.loc[i-k,"high"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"high"]>df.loc[i+k,"high"] for k in range(1,LOOKBACK+1)): ph[i]=True
        if all(df.loc[i,"low"]<df.loc[i-k,"low"] for k in range(1,LOOKBACK+1)) and \
           all(df.loc[i,"low"]<df.loc[i+k,"low"] for k in range(1,LOOKBACK+1)): pl[i]=True
    trades=[]; it=False; ep=0; ei=0; ed=""; sp=0; tpp=0
    for i in range(50, n):
        if np.isnan(sma[i]) or np.isnan(std[i]): continue
        if not it:
            bl=sma[i]-k*std[i]; bu=sma[i]+k*std[i]; sd=None
            if close[i-1]<bl: sd="LONG"
            elif close[i-1]>bu: sd="SHORT"
            else: continue
            ch=None; cl=None
            for j in range(i-5,-1,-1):
                if ph[j]: ch=float(df.loc[j,"high"]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(df.loc[j,"low"]); break
            ep=float(op[i]); ei=i; av=float(atr[i-1])
            if sd=="LONG": ed="LONG"; sp=min(ep-2*av,(cl-av) if cl is not None else ep-3*av); tpp=sma[i]
            else: ed="SHORT"; sp=max(ep+2*av,(ch+av) if ch is not None else ep+3*av); tpp=sma[i]
            if ed=="LONG" and tpp<=ep: tpp=ep+av
            if ed=="SHORT" and tpp>=ep: tpp=ep-av
            it=True; continue
        if it:
            lo=float(low[i]); hi=float(high[i]); ex=False; exp=0
            if ed=="LONG":
                if lo<=sp: exp=sp; ex=True
                elif hi>=tpp: exp=tpp; ex=True
                elif (i-ei)>=30: exp=float(close[i]); ex=True
            else:
                if hi>=sp: exp=sp; ex=True
                elif lo<=tpp: exp=tpp; ex=True
                elif (i-ei)>=30: exp=float(close[i]); ex=True
            if ex:
                pnl=round(exp-ep,2) if ed=="LONG" else round(ep-exp,2)
                trades.append({"pnl":pnl}); it=False; continue
    if it:
        pnl=round(float(close[-1])-ep,2) if ed=="LONG" else round(ep-float(close[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades)
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pf":pf,"name":f"BB_K={k}"}

# --- LOAD BUND ---
bund = pd.read_csv("dati/bund_220m.txt", sep="\t", decimal=".")
bund.columns=["data","open","high","low","close","volume"]
bund["ora"]=pd.to_datetime(bund["data"])
print(f"BUND: {len(bund)} candles 220m ({bund['ora'].iloc[0]} -> {bund['ora'].iloc[-1]})")

# --- LOAD BTP ---
btp = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
btp.columns=["data","open","high","low","close","volume"]
btp["ora"]=pd.to_datetime(btp["data"])
print(f"BTP: {len(btp)} candles 1h ({btp['ora'].iloc[0]} -> {btp['ora'].iloc[-1]})")

# Price reference (1 punto = ?)
# BTP: 1 pt = 1000 EUR
# BUND: 1 pt = 1000 EUR (future bund)

# --- TEST ST STRATEGY ---
print("\n=== ST + REGIME-ADAPTIVE TP ===")
for label, df in [("BUND 220m", bund), ("BTP 1h", btp)]:
    r = test_st_strategy(df)
    print(f"  {label:<15} Trade={r['total']:<4} WR={r['wr']:<5.1f} PnL={r['pnl']:<+8.2f}pt PF={r['pf']:<6.2f}")

# --- TEST BB MEAN REVERSION ---
print("\n=== BOLLINGER BANDS MEAN REVERSION ===")
for k in [1.5, 2.0, 2.5]:
    print(f"\n  K={k}:")
    for label, df in [("BUND 220m", bund), ("BTP 1h", btp)]:
        r = test_bb_strategy(df, k)
        print(f"    {label:<15} Trade={r['total']:<4} WR={r['wr']:<5.1f} PnL={r['pnl']:<+8.2f}pt PF={r['pf']:<6.2f}")

# --- ATR STATS COMPARISON ---
print("\n\n=== STATS STRUMENTO ===")
for label, df in [("BUND 220m", bund), ("BTP 1h", btp)]:
    c=df["close"].values; h=df["high"].values; l=df["low"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; a=np.zeros(len(df)); a[0]=tr[0]
    for i in range(1,len(df)): a[i]=a[i-1]+(1/30)*(tr[i]-a[i-1])
    returns = c / np.roll(c, 1) - 1; returns[0]=0
    ann_vol = np.std(returns[1:]) * np.sqrt(252*8.5)  # 8.5 bars per day for bund (24h/2.8h), for 1h it's diff
    print(f"  {label:<15} ATR_med={np.mean(a):.3f} Prezzo={c[-1]:.2f} Vol_annua={ann_vol*100:.1f}% Range={c.min():.1f}-{c.max():.1f}")

# --- MARKET REGIME COMPARISON ---
print("\n=== REGIME DI MERCATO (Markov 1 dev) ===")
for label, df in [("BUND 220m", bund), ("BTP 1h", btp)]:
    c=df["close"].values
    rets=c/np.roll(c,1)-1; rets[0]=0
    vol=pd.Series(rets).rolling(50).std().values
    vp=np.roll(vol,1); vp[0]=vol[0]
    sw=sum(1 for i in range(1,len(df)) if abs(rets[i])<=vp[i]); tot=len(df)-1
    bull=sum(1 for i in range(1,len(df)) if rets[i]>vp[i])
    bear=sum(1 for i in range(1,len(df)) if rets[i]<-vp[i])
    print(f"  {label:<15} Sideways={sw/tot*100:.0f}% Bull={bull/tot*100:.0f}% Bear={bear/tot*100:.0f}%")
