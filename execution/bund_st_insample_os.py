"""
BUND 1h — ST + regime-adaptive TP
IN-SAMPLE: 2018-2025 (primi 7 anni)
OUT-OF-SAMPLE: 2026 (contratto marzo 2026)
"""
import pandas as pd, numpy as np

ST_PERIOD=30; ST_MULT=1.5; LOOKBACK=5

def st_regime(df, name=""):
    n=len(df); h,l,c,op=df["high"].values,df["low"].values,df["close"].values,df["open"].values
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
        if all(df.iloc[i]["high"]>df.iloc[i-k]["high"] for k in range(1,LOOKBACK+1)) and \
           all(df.iloc[i]["high"]>df.iloc[i+k]["high"] for k in range(1,LOOKBACK+1)): ph[i]=True
        if all(df.iloc[i]["low"]<df.iloc[i-k]["low"] for k in range(1,LOOKBACK+1)) and \
           all(df.iloc[i]["low"]<df.iloc[i+k]["low"] for k in range(1,LOOKBACK+1)): pl[i]=True
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
                if ph[j]: ch=float(df.iloc[j]["high"]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(df.iloc[j]["low"]); break
            ep=float(op[i]); ei=i; av=float(atr[i-1])
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
                trades.append({"pnl":pnl,"entry":str(df.iloc[ei].name),"exit":str(df.iloc[i].name)}); it=False; continue
    if it:
        pnl=round(float(c[-1])-ep,2) if ed=="LONG" else round(ep-float(c[-1]),2)
        trades.append({"pnl":pnl})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades)
    gross_win=sum(t["pnl"] for t in trades if t["pnl"]>0)
    gross_loss=abs(sum(t["pnl"] for t in trades if t["pnl"]<=0))
    pf=gross_win/gross_loss if gross_loss else 999
    wr=wins/total*100 if total else 0
    avg_win=np.mean([t["pnl"] for t in trades if t["pnl"]>0]) if wins else 0
    avg_loss=np.mean([t["pnl"] for t in trades if t["pnl"]<=0]) if losses else 0
    return {"name":name,"total":total,"wins":wins,"losses":losses,"wr":wr,"pnl":pnl_pts,"pf":pf,
            "avg_win":avg_win,"avg_loss":avg_loss,"gross_win":gross_win,"gross_loss":gross_loss}

# === CARICA DATI ===
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

# Split in-sample / out-of-sample sul continuo
insample = cont[cont.index < "2026-01-01"].copy()
oos_cont = cont[cont.index >= "2026-01-01"].copy()

# Contratto specifico marzo 2026
raw = pd.read_csv("dati/Eurex.Bund marzo 2026.txt", sep="\t", skiprows=3,
    names=["ora","high","low","open","close","volume"], decimal=",")
for c in ["high","low","open","close","volume"]: raw[c] = raw[c].astype(float)
raw["dt"] = pd.to_datetime(raw["ora"], format="%d%m%Y %H%M%S")
raw.sort_values("dt", inplace=True)
raw.set_index("dt", inplace=True)

# === TEST ===
print("="*70)
print("ST + REGIME-ADAPTIVE TP — BUND 1h")
print("="*70)
print(f"{'Dataset':<20} {'Periodo':<22} {'Trades':<8} {'Win%':<8} {'PnLpt':<10} {'PF':<10} {'AvgWin':<10} {'AvgLoss':<10}")
print("-"*98)

r = st_regime(insample, "IS 2018-2025")
print(f"{r['name']:<20} {'2018-2025':<22} {r['total']:<8} {r['wr']:<7.1f}% {r['pnl']:<+9.2f} {r['pf']:<9.2f} {r['avg_win']:<+9.2f} {r['avg_loss']:<+9.2f}")

r = st_regime(oos_cont, "OOS continuo 2026")
print(f"{r['name']:<20} {'gen-giu 2026':<22} {r['total']:<8} {r['wr']:<7.1f}% {r['pnl']:<+9.2f} {r['pf']:<9.2f} {r['avg_win']:<+9.2f} {r['avg_loss']:<+9.2f}")

r = st_regime(raw, "OOS contratto mar26")
print(f"{r['name']:<20} {'mar-giu 2026':<22} {r['total']:<8} {r['wr']:<7.1f}% {r['pnl']:<+9.2f} {r['pf']:<9.2f} {r['avg_win']:<+9.2f} {r['avg_loss']:<+9.2f}")

# Sub OOS: solo post-expiry
raw_post = raw[raw.index >= "2026-03-20"].copy()
r = st_regime(raw_post, "OOS post-expiry")
print(f"{r['name']:<20} {'20 mar-15 mag':<22} {r['total']:<8} {r['wr']:<7.1f}% {r['pnl']:<+9.2f} {r['pf']:<9.2f} {r['avg_win']:<+9.2f} {r['avg_loss']:<+9.2f}")

# Stats
print("\n=== STATS ===")
for label, df in [("IS 2018-2025", insample), ("OOS contratto", raw)]:
    c=df["close"].values; h=df["high"].values; l=df["low"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; a=np.zeros(len(df)); a[0]=tr[0]
    for i in range(1,len(df)): a[i]=a[i-1]+(1/30)*(tr[i]-a[i-1])
    print(f"  {label:<20} candles={len(df)} prezzo={c[-1]:.2f} ATR_med={np.mean(a):.3f}")
