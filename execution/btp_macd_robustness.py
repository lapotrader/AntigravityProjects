"""
MACD su BTP 1h — Robustness analysis.
Trova i parametri "plateau": quelli che al variare di +/-1 restano solidi.
"""
import pandas as pd, numpy as np

# Carica dati
df = pd.read_csv("dati/btp_1h_full.txt", sep="\t", decimal=".")
df.columns=["data","open","high","low","close","volume"]
df["dt"] = pd.to_datetime(df["data"])
df.set_index("dt", inplace=True)
for c in ["open","high","low","close","volume"]: df[c]=df[c].astype(float)

n=len(df); split=n//2
df_is = df.iloc[:split]
df_oos = df.iloc[split:]

def macd_strategy(df, fast=12, slow=26, sig=9, tp_mult=3.0):
    n=len(df); h=df["high"].values; l=df["low"].values
    c=df["close"].values; op=df["open"].values

    # MACD con shift
    ema_fast = pd.Series(c).ewm(span=fast, adjust=False).mean().shift(1).values
    ema_slow = pd.Series(c).ewm(span=slow, adjust=False).mean().shift(1).values
    macd_line = ema_fast - ema_slow
    sig_line = pd.Series(macd_line).ewm(span=sig, adjust=False).mean().shift(1).values

    # Segnali crossover
    xover = np.zeros(n)
    for i in range(slow+2, n):
        if macd_line[i] > sig_line[i] and macd_line[i-1] <= sig_line[i-1]: xover[i]=1
        elif macd_line[i] < sig_line[i] and macd_line[i-1] >= sig_line[i-1]: xover[i]=-1

    # ATR
    tr=np.maximum(h-l,np.maximum(np.abs(h-np.roll(c,1)),np.abs(l-np.roll(c,1))))
    tr[0]=h[0]-l[0]; atr=np.zeros(n); a=1/30; atr[0]=tr[0]
    for i in range(1,n): atr[i]=atr[i-1]+a*(tr[i]-atr[i-1])
    atr=np.roll(atr,1); atr[0]=atr[1]

    ph=np.full(n,False); pl=np.full(n,False)
    for i in range(5,n-5):
        if all(c[i]>c[i-k] for k in range(1,6)) and all(c[i]>c[i+k] for k in range(1,6)): ph[i]=True
        if all(c[i]<c[i-k] for k in range(1,6)) and all(c[i]<c[i+k] for k in range(1,6)): pl[i]=True

    trades=[]; it=False; ep=0; ei=0; ed=""; sp=0; tpp=0
    for i in range(slow+3, n):
        if not it:
            if xover[i]==0: continue
            sd="LONG" if xover[i]==1 else "SHORT"
            ch=None; cl=None
            for j in range(i-5,-1,-1):
                if ph[j]: ch=float(c[j]); break
            for j in range(i-5,-1,-1):
                if pl[j]: cl=float(c[j]); break
            ep=float(op[i]); ei=i; av=float(atr[i])
            if av<=0: continue
            if sd=="LONG":
                ed="LONG"; sp=(cl-0.5*av) if cl is not None else (ep-2*av); tpp=ep+tp_mult*av
                if sp>=ep: sp=ep-2*av
            else:
                ed="SHORT"; sp=(ch+0.5*av) if ch is not None else (ep+2*av); tpp=ep-tp_mult*av
                if sp<=ep: sp=ep+2*av
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
            trades.append(pnl); it=False
    return trades

def calc_metrics(trades):
    if len(trades)<3: return 0,0,0,0
    w=sum(1 for x in trades if x>0); l=len(trades)-w
    gw=sum(x for x in trades if x>0); gl=abs(sum(x for x in trades if x<=0))
    pf=gw/gl if gl else 999
    ret=sum(trades)
    return pf, len(trades), w/len(trades)*100 if len(trades) else 0, ret

# Griglia fine
fasts = list(range(5, 14))
slows = list(range(13, 28))
sigs = [3, 5, 7, 9]
tps = [2.0, 3.0, 4.0, 5.0]

print("Scanning MACD grid...")
results = []
for fast in fasts:
    if fast >= min(slows): continue
    for slow in slows:
        if slow <= fast: continue
        for sig in sigs:
            for tp in tps:
                t_is = macd_strategy(df_is, fast, slow, sig, tp)
                t_os = macd_strategy(df_oos, fast, slow, sig, tp)
                pf_is, n_is, wr_is, ret_is = calc_metrics(t_is)
                pf_os, n_os, wr_os, ret_os = calc_metrics(t_os)
                if n_is>=5 and n_os>=5:
                    results.append({"fast":fast,"slow":slow,"sig":sig,"tp":tp,
                        "pf_is":pf_is,"pf_os":pf_os,"n_is":n_is,"n_os":n_os,"ret":ret_is+ret_os,
                        "score":pf_is*pf_os if pf_os>0 else 0})

df_r = pd.DataFrame(results)
print(f"Total valid combos: {len(df_r)}")

# Robustness: per ogni combo, media PF dei vicini (fast+/-1, slow+/-2, sig uguale, tp uguale)
def robustness(row, grid):
    """PF medio dei parametri vicini (stessa sig e tp, fast+/-1, slow+/-2)"""
    f,s,sg,t = row["fast"],row["slow"],row["sig"],row["tp"]
    mask = (grid["sig"]==sg) & (grid["tp"]==t) & \
           (grid["fast"]>=f-1) & (grid["fast"]<=f+1) & \
           (grid["slow"]>=s-2) & (grid["slow"]<=s+2)
    sub = grid[mask]
    if len(sub)<2: return 0
    # Media armonica di pf_is * pf_os per i vicini
    scores = sub["pf_is"] * sub["pf_os"]
    return scores.mean()

df_r["robust"] = df_r.apply(lambda r: robustness(r, df_r), axis=1)
df_r["final"] = df_r["pf_is"] * df_r["pf_os"] * df_r["robust"] / 100

print("\n=== TOP 20 MACD PARAM SETS (sorted by IS×OOS×Robustness) ===")
print(f"{'fast':<6} {'slow':<6} {'sig':<5} {'tp':<5} {'PF_IS':<8} {'PF_OS':<8} {'N_IS':<6} {'N_OS':<6} {'Ret':<8} {'Robust':<8} {'Score':<8}")
print("-"*75)
top = df_r.sort_values("final", ascending=False).head(20)
for _, r in top.iterrows():
    print(f"{r['fast']:<6} {r['slow']:<6} {r['sig']:<5} {r['tp']:<5.0f} {r['pf_is']:<8.3f} {r['pf_os']:<8.3f} {r['n_is']:<6} {r['n_os']:<6} {r['ret']:<+7.2f} {r['robust']:<8.2f} {r['final']:<8.2f}")

# Stampa dettaglio dei migliori plateau
print("\n\n=== PLATEAU ROBUSTI ===")
# Raggruppa per fast/slow vicine (fast+/-1, slow+/-2)
seen = set()
for _, r in df_r.sort_values("final", ascending=False).iterrows():
    key = (r["fast"]//2, r["slow"]//3, r["sig"], r["tp"])
    if key in seen: continue
    seen.add(key)
    # Gruppo: fast+/-1, slow+/-2, stessa sig, stesso tp
    mask = (df_r["sig"]==r["sig"]) & (df_r["tp"]==r["tp"]) & \
           (df_r["fast"]>=r["fast"]-1) & (df_r["fast"]<=r["fast"]+1) & \
           (df_r["slow"]>=r["slow"]-2) & (df_r["slow"]<=r["slow"]+2)
    grp = df_r[mask]
    avg_pf_is = grp["pf_is"].mean()
    avg_pf_os = grp["pf_os"].mean()
    print(f"\nPlateau: fast={r['fast']}+/-1 slow={r['slow']}+/-2 sig={r['sig']} tp={r['tp']:.0f}")
    print(f"  N combos: {len(grp)}  |  Media PF_IS: {avg_pf_is:.3f}  Media PF_OS: {avg_pf_os:.3f}")
    print(f"  Parametri nel plateau:")
    for _, rr in grp.iterrows():
        print(f"    fast={rr['fast']:<2} slow={rr['slow']:<2} PF_IS={rr['pf_is']:.3f} PF_OS={rr['pf_os']:.3f} N={rr['n_is']+rr['n_os']} Ret={rr['ret']:+.2f}")
    if len(seen)>=8: break

# Miglior singolo combo
print("\n\n=== MIGLIOR COMBO SINGOLO ===")
best = df_r.loc[df_r["final"].idxmax()]
print(f"MACD({best['fast']},{best['slow']},{best['sig']}) tp={best['tp']:.0f}")
print(f"PF_IS={best['pf_is']:.3f} PF_OS={best['pf_os']:.3f} Trades={best['n_is']+best['n_os']:.0f} Ret={best['ret']:+.2f}")

# Top 5 plateau
print("\n\n=== TOP 5 PLATEAU ===")
seen2 = set()
cnt=0
for _, r in df_r.sort_values("final", ascending=False).iterrows():
    key = (r["fast"]//2, r["slow"]//3, r["sig"], r["tp"])
    if key in seen2: continue
    seen2.add(key)
    mask = (df_r["sig"]==r["sig"]) & (df_r["tp"]==r["tp"]) & \
           (df_r["fast"]>=r["fast"]-1) & (df_r["fast"]<=r["fast"]+1) & \
           (df_r["slow"]>=r["slow"]-2) & (df_r["slow"]<=r["slow"]+2)
    grp = df_r[mask]
    print(f"  [{cnt+1}] MACD fast={r['fast']}+/-1 slow={r['slow']}+/-2 sig={r['sig']} tp={r['tp']:.0f}  "
          f"PF_IS={grp['pf_is'].mean():.3f} PF_OS={grp['pf_os'].mean():.3f} n={len(grp)}")
    cnt+=1
    if cnt>=5: break

# Test su dati 2026
print("\n\n=== TEST SU DATI 2026 ===")
ndf = pd.read_csv("dati/27 febbraio.txt", sep="\t", header=None, decimal=",")
ndf.columns=["data","high","low","open","close","volume"]
for c in ["high","low","open","close","volume"]: ndf[c]=ndf[c].astype(float)
ndf["dt"] = pd.to_datetime(ndf["data"], dayfirst=True)
ndf.sort_values("dt", inplace=True)
ndf.set_index("dt", inplace=True)

print(f"{'Combo':<30} {'PF_IS':<8} {'PF_OS':<8} {'PF_2026':<8} {'N_2026':<6} {'Ret_2026':<10}")
print("-"*70)
for _, r in df_r.sort_values("final", ascending=False).head(10).iterrows():
    t_new = macd_strategy(ndf, int(r["fast"]), int(r["slow"]), int(r["sig"]), r["tp"])
    pf_26, n_26, wr_26, ret_26 = calc_metrics(t_new)
    label = f"MACD({r['fast']:.0f},{r['slow']:.0f},{r['sig']:.0f}) tp={r['tp']:.0f}"
    print(f"{label:<30} {r['pf_is']:<8.3f} {r['pf_os']:<8.3f} {pf_26:<8.3f} {n_26:<6} {ret_26:<+9.2f}")
