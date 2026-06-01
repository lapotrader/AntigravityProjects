"""
BUND 1h vs BTP 1h — Confronto diretto.
ST + regime-adapt TP + BB mean reversion.
STESSO TIMEFRAME, STESSI PARAMETRI.
"""
import pandas as pd, numpy as np

ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

def test_st_regime(df):
    """ST + regime-adaptive TP (SL corretto per short)"""
    n=len(df); h,l,c=df["high"].values,df["low"].values,df["close"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    atr_pct=np.full(n,0.5)
    for i in range(50,n): roll=atr[i-50:i]; atr_pct[i]=np.sum(roll<=atr[i])/50
    hl2=(h+l)/2; fu=np.zeros(n); fl=np.zeros(n); st=np.zeros(n); d=np.ones(n,dtype=int)
    for i in range(n):
        if i==0: fu[i]=hl2[i]+ST_MULT*atr[i]; fl[i]=hl2[i]-ST_MULT*atr[i]; st[i]=fu[i]; d[i]=-1; continue
        pc=c[i-1]; ub=hl2[i]+ST_MULT*atr[i]; lb=hl2[i]-ST_MULT*atr[i]
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
            ep=float(df.loc[i,"open"]); ei=i; av=float(atr[i-1])
            pct=atr_pct[i-1]; k=2.0 if pct<0.3 else (4.0 if pct>0.7 else 3.0)
            if sd=="LONG": ed="LONG"; sp=(cl-0.5*av) if cl is not None else (ep-2*av); tpp=ep+k*av
            else: ed="SHORT"; sp=(ch+0.5*av) if ch is not None else (ep+2*av); tpp=ep-k*av
            if ed=="LONG" and sp>=ep: sp=ep-2*av
            if ed=="SHORT" and sp<=ep: sp=ep+2*av
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
    pnl_pts=sum(t["pnl"] for t in trades)
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pf":pf}

def test_bb(df, k=2.0):
    """Bollinger mean reversion"""
    n=len(df); h,l,c=df["high"].values,df["low"].values,df["close"].values; op=df["open"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; atr=np.zeros(n); alpha=1/ST_PERIOD; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    sma=pd.Series(c).rolling(20).mean().values; std=pd.Series(c).rolling(20).std().values
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
            if c[i-1]<bl: sd="LONG"
            elif c[i-1]>bu: sd="SHORT"
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
            lo=float(l[i]); hi=float(h[i]); ex=False; exp=0
            if ed=="LONG":
                if lo<=sp: exp=sp; ex=True
                elif hi>=tpp: exp=tpp; ex=True
                elif (i-ei)>=30: exp=float(c[i]); ex=True
            else:
                if hi>=sp: exp=sp; ex=True
                elif lo<=tpp: exp=tpp; ex=True
                elif (i-ei)>=30: exp=float(c[i]); ex=True
            if ex:
                pnl=round(exp-ep,2) if ed=="LONG" else round(ep-exp,2)
                trades.append({"pnl":pnl}); it=False; continue
    if it:
        pnl=round(float(c[-1])-ep,2) if ed=="LONG" else round(ep-float(c[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades)
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    return {"total":total,"wr":wr,"pnl":pnl_pts,"pf":pf}

# --- LOAD ---
bund = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
bund.columns=["data","open","high","low","close","volume"]
bund["ora"]=pd.to_datetime(bund["data"])

btp = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
btp.columns=["data","open","high","low","close","volume"]
btp["ora"]=pd.to_datetime(btp["data"])

# Also load new BTP data for 3-month comparison
btp_new = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
btp_new.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: btp_new[c]=btp_new[c].astype(float)
btp_new["ora"]=pd.to_datetime(btp_new["data"], dayfirst=True)

print(f"BUND 1h: {len(bund)} candles ({bund['ora'].iloc[0]} -> {bund['ora'].iloc[-1]})")
print(f"BTP 1h:  {len(btp)} candles ({btp['ora'].iloc[0]} -> {btp['ora'].iloc[-1]})")
print(f"BTP new: {len(btp_new)} candles ({btp_new['ora'].iloc[0]} -> {btp_new['ora'].iloc[-1]})")

# --- ST + REGIME-ADAPTIVE ---
print("\n=== ST + REGIME-ADAPTIVE TP ===")
print(f"{'Strumento':<15} {'Periodo':<12} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PF':<8}")
print("="*60)
r = test_st_regime(bund)
print(f"{'BUND':<15} {'8 anni':<12} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pf']:<8.2f}")
r = test_st_regime(btp)
print(f"{'BTP':<15} {'2.7 anni':<12} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pf']:<8.2f}")
r = test_st_regime(btp_new)
print(f"{'BTP NEW':<15} {'3 mesi':<12} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pf']:<8.2f}")

# --- BB MEAN REVERSION ---
print("\n=== BOLLINGER BANDS MEAN REVERSION ===")
for k in [2.0, 2.5]:
    print(f"\n  K={k}:")
    print(f"  {'Strumento':<15} {'Periodo':<12} {'Trade':<7} {'Win%':<8} {'PnLpt':<10} {'PF':<8}")
    print(f"  {'-'*60}")
    for label, df in [("BUND", bund), ("BTP", btp), ("BTP NEW", btp_new)]:
        r = test_bb(df, k)
        print(f"  {label:<15} {'---':<12} {r['total']:<7} {r['wr']:<8.1f} {r['pnl']:<+10.2f} {r['pf']:<8.2f}")

# --- STATS ---
print("\n\n=== STATISTICHE CONFRONTO ===")
for label, df in [("BUND 1h", bund), ("BTP 1h", btp)]:
    c=df["close"].values; h=df["high"].values; l=df["low"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; a=np.zeros(len(df)); a[0]=tr[0]
    for i in range(1,len(df)): a[i]=a[i-1]+(1/30)*(tr[i]-a[i-1])
    rets=c/np.roll(c,1)-1; rets[0]=0
    ann_vol=np.std(rets[1:])*np.sqrt(252*8.5)
    print(f"  {label:<15} ATR_med={np.mean(a):.3f} Prezzo={c[-1]:.2f} Vol_annua={ann_vol*100:.1f}%")
