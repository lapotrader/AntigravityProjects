"""
BUND — RSI+Volume puro. Verifica risultato subagente.
"""
import pandas as pd, numpy as np

cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
cont.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: cont[c]=cont[c].astype(float)

RSI_PERIOD=14; RSI_LOW=20; RSI_HIGH=75; VOL_MULT=2.0; TP_ATR=2.0; SL_ATR=2.0

def rsi_vol_signal(df):
    c=df["close"].values; v=df["volume"].values; n=len(c)
    sig=np.zeros(n); delta=pd.Series(c).diff()
    gain=delta.clip(lower=0).rolling(RSI_PERIOD).mean().shift(1).values
    loss=(-delta.clip(upper=0)).rolling(RSI_PERIOD).mean().shift(1).values
    rsi=np.full(n,50.0)
    for i in range(RSI_PERIOD+1,n):
        if loss[i]!=0: rsi[i]=100-100/(1+gain[i]/loss[i])
    vsma=pd.Series(v).rolling(20).mean().shift(1).values
    for i in range(RSI_PERIOD+2,n):
        if np.isnan(rsi[i]) or np.isnan(vsma[i]): continue
        if rsi[i]<RSI_LOW and v[i-1]>vsma[i]*VOL_MULT: sig[i]=1
        elif rsi[i]>RSI_HIGH and v[i-1]>vsma[i]*VOL_MULT: sig[i]=-1
    return sig

def run(df, onoff=False):
    n=len(df); h=df["high"].values; l=df["low"].values
    c=df["close"].values; op=df["open"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; atr=np.zeros(n); a=1/30; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+a*(tr[i]-atr[i-1])
    atr=np.roll(atr,1); atr[0]=atr[1]
    sig=rsi_vol_signal(df)
    ph=np.full(n,False); pl=np.full(n,False)
    for i in range(5,n-5):
        if all(c[i]>c[i-k] for k in range(1,6)) and all(c[i]>c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i]<c[i-k] for k in range(1,6)) and all(c[i]<c[i+k] for k in range(1,6)): pl[i]=True
    trades=[]; it=False; ep=0; ei=0; ed=""; sp=0; tpp=0
    for i in range(60,n):
        if not it:
            if sig[i]>=1: sd="LONG"
            elif sig[i]<=-1: sd="SHORT"
            else: continue
            ch=None; cl=None
            for j in range(i-5,-1,-1):
                if ph[j]: ch=float(c[j]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(c[j]); break
            ep=float(op[i]); ei=i; av=float(atr[i])
            if av<=0: continue
            if sd=="LONG":
                ed="LONG"; sp=(cl-0.5*av) if cl is not None else (ep-SL_ATR*av)
                tpp=ep+TP_ATR*av
                if sp>=ep: sp=ep-SL_ATR*av
                if tpp<=ep: tpp=ep+av
            else:
                ed="SHORT"; sp=(ch+0.5*av) if ch is not None else (ep+SL_ATR*av)
                tpp=ep-TP_ATR*av
                if sp<=ep: sp=ep+SL_ATR*av
                if tpp>=ep: tpp=ep-av
            it=True; continue
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
            trades.append({"pnl":pnl,"ts":str(df.index[i])}); it=False
    if not onoff: return trades
    months=sorted(set(t["ts"][:7] for t in trades))
    mpnl={}
    for t in trades:
        m=t["ts"][:7]; mpnl[m]=mpnl.get(m,0)+t["pnl"]
    ml=sorted(mpnl.keys()); on={}
    for i,m in enumerate(ml):
        if i<3: on[m]=True
        else: on[m]=sum(mpnl[ml[j]] for j in range(i-3,i))>=0
    return [t for t in trades if on.get(t["ts"][:7],True)]

print("RSI+Volume PURO")
print("="*60)

for name, df, onoff in [
    ("IS 2018-2019", cont[cont.index<"2020-01-01"], False),
    ("IS 2018-2019+OF", cont[cont.index<"2020-01-01"], True),
    ("VAL 2020-2022", cont[(cont.index>="2020-01-01")&(cont.index<"2023-01-01")], False),
    ("VAL 2020-2022+OF", cont[(cont.index>="2020-01-01")&(cont.index<"2023-01-01")], True),
    ("OOS 2023-2026", cont[cont.index>="2023-01-01"], False),
    ("OOS 2023-2026+OF", cont[cont.index>="2023-01-01"], True),
]:
    t=run(df,onoff)
    if len(t)==0: print(f"{name:<20}: 0 trades"); continue
    w=sum(1 for x in t if x["pnl"]>0); l=len(t)-w
    gw=sum(x["pnl"] for x in t if x["pnl"]>0)
    gl=abs(sum(x["pnl"] for x in t if x["pnl"]<=0))
    pf=gw/gl if gl else 999
    print(f"{name:<20}: {len(t):<4} tr WR={w/len(t)*100:5.1f}% "
          f"PnL={sum(x['pnl'] for x in t):+7.2f} PF={pf:.3f}")

# Full + contratto
print("\n--- FULL + CONTRATTO ---")
for label, df in [("FULL 18-26",cont),("Contratto mar26",
    pd.concat([pd.read_csv("dati/Eurex.Bund marzo 2026.txt",sep="\t",skiprows=3,
        names=["ora","high","low","open","close","volume"],decimal=",")
        .assign(dt=lambda x: pd.to_datetime(x["ora"],format="%d%m%Y %H%M%S"))
        .sort_values("dt").set_index("dt")
        .astype({c:float for c in["high","low","open","close","volume"]})]))]:
    for onoff in [False, True]:
        t=run(df,onoff)
        if len(t)==0: print(f"  {label:20} {'ON/OFF' if onoff else 'NOFIL':8}: 0 tr"); continue
        w=sum(1 for x in t if x["pnl"]>0); l=len(t)-w
        gw=sum(x["pnl"] for x in t if x["pnl"]>0)
        gl=abs(sum(x["pnl"] for x in t if x["pnl"]<=0))
        print(f"  {label:20} {'ON/OFF' if onoff else 'NOFIL':8}: {len(t):<4} tr "
              f"WR={w/len(t)*100:5.1f}% PnL={sum(x['pnl'] for x in t):+7.2f} PF={gw/gl if gl else 999:.3f}")
