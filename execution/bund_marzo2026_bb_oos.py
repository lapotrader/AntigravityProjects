"""Backtest BB mean reversion out-of-sample su BUND marzo 2026."""
import pandas as pd, numpy as np

# Carica dati BUND marzo 2026
raw = pd.read_csv("dati/Eurex.Bund marzo 2026.txt", sep="\t", skiprows=3,
    names=["ora","high","low","open","close","volume"], decimal=",")
for c in ["high","low","open","close","volume"]: raw[c] = raw[c].astype(float)
raw["dt"] = pd.to_datetime(raw["ora"], format="%d%m%Y %H%M%S")
raw.sort_values("dt", inplace=True)

print(f"BUND marzo 2026: {len(raw)} candles, {raw['dt'].iloc[0]} -> {raw['dt'].iloc[-1]}")
print(f"Prezzo: {raw['close'].iloc[0]:.2f} -> {raw['close'].iloc[-1]:.2f}")

# Confronto con bund_1h.txt (continuo) per lo stesso periodo
cont = pd.read_csv("dati/bund_1h.txt", sep="\t", decimal=".")
cont.columns=["data","open","high","low","close","volume"]
cont["dt"] = pd.to_datetime(cont["data"])
mask = (cont["dt"] >= raw["dt"].iloc[0]) & (cont["dt"] <= raw["dt"].iloc[-1])
cont_sub = cont[mask].copy()
print(f"\nConfronto prezzi:")
for i, r in raw.iterrows():
    match = cont_sub[cont_sub["dt"] == r["dt"]]
    if len(match) == 1:
        diff = abs(r["close"] - float(match.iloc[0]["close"]))
        if diff > 0.05:
            print(f"  Divergenza a {r['dt']}: contratto={r['close']:.2f} continuo={float(match.iloc[0]['close']):.2f} (diff={diff:.2f})")

# BB Mean Reversion su contratto marzo 2026
def bb_test(df, k=2.0, atr_period=30):
    n=len(df); h,l,c,op=df["high"].values,df["low"].values,df["close"].values,df["open"].values
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; atr=np.zeros(n); alpha=1/atr_period; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+alpha*(tr[i]-atr[i-1])
    sma=pd.Series(c).rolling(20).mean().values; std=pd.Series(c).rolling(20).std().values
    ph=np.full(n,False); pl=np.full(n,False); lk=5
    for i in range(lk, n-lk):
        if all(df.iloc[i]["high"]>df.iloc[i-k]["high"] for k in range(1,lk+1)) and \
           all(df.iloc[i]["high"]>df.iloc[i+k]["high"] for k in range(1,lk+1)): ph[i]=True
        if all(df.iloc[i]["low"]<df.iloc[i-k]["low"] for k in range(1,lk+1)) and \
           all(df.iloc[i]["low"]<df.iloc[i+k]["low"] for k in range(1,lk+1)): pl[i]=True
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
                if ph[j]: ch=float(df.iloc[j]["high"]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(df.iloc[j]["low"]); break
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
                trades.append({"pnl":pnl,"entry":str(df.iloc[ei]["dt"]),"exit":str(df.iloc[i]["dt"]),"dir":ed}); it=False; continue
    if it:
        pnl=round(float(c[-1])-ep,2) if ed=="LONG" else round(ep-float(c[-1]),2)
        trades.append({"pnl":pnl,"entry":str(df.iloc[ei]["dt"]),"exit":str(df.iloc[-1]["dt"]),"dir":ed})
    total=len(trades); wins=sum(1 for t in trades if t["pnl"]>0); losses=total-wins
    pnl_pts=sum(t["pnl"] for t in trades)
    pf=abs(sum(t["pnl"] for t in trades if t["pnl"]>0)/sum(t["pnl"] for t in trades if t["pnl"]<=0)) if losses else 999
    wr=wins/total*100 if total else 0
    avg_win=np.mean([t["pnl"] for t in trades if t["pnl"]>0]) if wins else 0
    avg_loss=np.mean([t["pnl"] for t in trades if t["pnl"]<=0]) if losses else 0
    return {"total":total,"wins":wins,"losses":losses,"wr":wr,"pnl":pnl_pts,"pf":pf,
            "avg_win":avg_win,"avg_loss":avg_loss}

print("\n=== BB MEAN REVERSION OOS SU BUND MARZO 2026 ===")
print(f"{'K':<6} {'Trades':<8} {'Win%':<8} {'PnLpt':<10} {'PF':<10} {'AvgWin':<10} {'AvgLoss':<10}")
print("="*62)
for k in [2.0, 2.5]:
    r = bb_test(raw, k)
    print(f"{k:<6} {r['total']:<8} {r['wr']:<7.1f}% {r['pnl']:<+9.2f} {r['pf']:<9.2f} {r['avg_win']:<+9.2f} {r['avg_loss']:<+9.2f}")

# Sub-analisi: solo dopo marzo (expiry)
raw_apr = raw[raw["dt"] >= "2026-03-20"].copy()
print("\n--- Solo post-expiry (20 mar -> 15 mag) ---")
for k in [2.0, 2.5]:
    r = bb_test(raw_apr, k)
    print(f"K={k}: {r['total']} trades, WR={r['wr']:.1f}%, PnL={r['pnl']:+.2f}pt, PF={r['pf']:.2f}")
